from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import pymupdf  # PyMuPDF

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


@dataclass
class OcrLine:
    text: str
    conf: float | None
    # 4-point polygon from PaddleOCR: [[x,y],[x,y],[x,y],[x,y]]
    poly: list[list[float]]


def render_page_png(page: pymupdf.Page, out_path: Path, *, dpi: int = 200) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mat = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    pix.save(out_path.as_posix())


def extract_render_stage(
    pdf_path: Path,
    out_dir: Path,
    *,
    dpi: int = 200,
    page_start: int = 1,
    page_end: int | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Stage 01: render per-page PNGs (input for OCR).
    """
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    pages_dir = out_dir / "pages"

    doc = pymupdf.open(pdf_path)
    try:
        total_pages = len(doc)
        if page_end is None:
            page_end = total_pages
        page_start = max(1, page_start)
        page_end = min(total_pages, page_end)

        pages: list[dict[str, Any]] = []
        for page_no in range(page_start, page_end + 1):
            page = doc[page_no - 1]
            png = pages_dir / f"p{page_no:04d}.png"
            if overwrite or not png.exists():
                render_page_png(page, png, dpi=dpi)
            pages.append(
                {
                    "page": page_no,
                    "page_png": str(png),
                    "page_size": [float(page.rect.width), float(page.rect.height)],
                }
            )

        return {
            "source_pdf": str(pdf_path),
            "page_count": total_pages,
            "dpi": dpi,
            "pages": pages,
        }
    finally:
        doc.close()


def _import_paddleocr():
    try:
        from paddleocr import PaddleOCR  # type: ignore

        return PaddleOCR
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "paddleocr is not available. Install it first (e.g. `uv pip install -p .venv paddleocr`)."
        ) from e


def ocr_pages_stage(
    render_manifest: dict[str, Any],
    *,
    lang: str = "en",
    use_gpu: bool = False,
    det: bool = True,
    rec: bool = True,
    cls: bool = True,
) -> dict[str, Any]:
    """
    Stage 02: OCR via PaddleOCR over rendered page PNGs.

    Output per page:
      {"page": 1, "lines": [{"text": "...", "conf": 0.98, "poly": [[x,y]...]}]}
    """
    PaddleOCR = _import_paddleocr()

    # Workarounds for some Paddle + IR/oneDNN combinations that crash on certain models.
    # These flags are best-effort (vary by Paddle version) and should be set early.
    try:  # pragma: no cover
        import paddle

        # Try both env-style and python flags where available.
        flag_candidates = {
            "FLAGS_use_mkldnn": False,
            "FLAGS_use_onednn": False,
            "FLAGS_new_executor": False,
            "FLAGS_enable_pir_api": False,
            "FLAGS_enable_pir_in_executor": False,
        }
        # paddle.set_flags expects {str: bool/int}
        paddle.set_flags(
            {
                k: int(v) if isinstance(v, bool) else v
                for k, v in flag_candidates.items()
            }
        )
    except Exception:
        pass

    # Note: PaddleOCR may download model weights on first run (needs network).
    # PaddleOCR ctor arguments vary by version; try progressively smaller kwarg sets.
    ctor_candidates = [
        {"use_angle_cls": cls, "lang": lang, "use_gpu": use_gpu, "show_log": False},
        {"use_angle_cls": cls, "lang": lang, "use_gpu": use_gpu},
        {"use_angle_cls": cls, "lang": lang},
        {"lang": lang},
        {},
    ]
    last_err: Exception | None = None
    ocr = None
    for kwargs in ctor_candidates:
        try:
            ocr = PaddleOCR(**kwargs)
            last_err = None
            break
        except Exception as e:  # pragma: no cover
            last_err = e
            continue
    if ocr is None:  # pragma: no cover
        raise RuntimeError(f"Failed to initialize PaddleOCR: {last_err}") from last_err

    pages_out: list[dict[str, Any]] = []
    for p in render_manifest.get("pages", []):
        page_no = int(p["page"])
        img_path = p["page_png"]
        # PaddleOCR.ocr signature differs between versions.
        # Try a few common signatures (some versions don't accept `cls`).
        try:
            result = ocr.ocr(img_path, det=det, rec=rec, cls=cls)
        except TypeError:
            try:
                result = ocr.ocr(img_path, det=det, rec=rec)
            except TypeError:
                try:
                    result = ocr.ocr(img_path, cls=cls)
                except TypeError:
                    result = ocr.ocr(img_path)

        lines: list[OcrLine] = []

        # PaddleOCR 3.x (via PaddleX) returns OCRResult objects.
        items = result or []
        if isinstance(items, list) and items and hasattr(items[0], "json"):
            for r in items:
                j = getattr(r, "json", None)
                if not isinstance(j, dict):
                    continue
                res = j.get("res") or {}
                dt_polys = res.get("dt_polys") or []
                rec_texts = res.get("rec_texts") or []
                rec_scores = res.get("rec_scores") or []
                for poly, text, score in zip(dt_polys, rec_texts, rec_scores):
                    if not text:
                        continue
                    try:
                        poly_f = [[float(x), float(y)] for x, y in poly]
                    except Exception:
                        poly_f = []
                    conf = None
                    try:
                        conf = float(score)
                    except Exception:
                        conf = None
                    lines.append(OcrLine(text=str(text), conf=conf, poly=poly_f))
        else:
            # Older PaddleOCR returns tuples/lists:
            # - [ [poly, (text, conf)], ... ]
            # - [ [ [poly, (text, conf)], ... ] ]  (wrapped for single image)
            if (
                isinstance(items, list)
                and len(items) == 1
                and isinstance(items[0], list)
                and items[0]
                and isinstance(items[0][0], (list, tuple))
                and len(items[0][0]) == 2
            ):
                items = items[0]

            for item in items:
                if not isinstance(item, (list, tuple)) or len(item) < 2:
                    continue
                poly = item[0]
                txt_conf = item[1]
                text = (
                    txt_conf[0]
                    if isinstance(txt_conf, (list, tuple)) and len(txt_conf) > 0
                    else ""
                )
                conf = (
                    txt_conf[1]
                    if isinstance(txt_conf, (list, tuple)) and len(txt_conf) > 1
                    else None
                )
                if not text:
                    continue
                try:
                    poly_f = [[float(x), float(y)] for x, y in poly]
                except Exception:
                    poly_f = []
                lines.append(
                    OcrLine(
                        text=str(text),
                        conf=float(conf) if conf is not None else None,
                        poly=poly_f,
                    )
                )

        pages_out.append(
            {"page": page_no, "page_png": img_path, "lines": [asdict(l) for l in lines]}
        )

    return {
        "source_pdf": render_manifest.get("source_pdf"),
        "lang": lang,
        "engine": "paddleocr",
        "pages": pages_out,
    }


def write_json(obj: Any, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
