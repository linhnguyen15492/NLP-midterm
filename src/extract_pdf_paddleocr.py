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

        return {"source_pdf": str(pdf_path), "page_count": total_pages, "dpi": dpi, "pages": pages}
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

    # Note: PaddleOCR may download model weights on first run (needs network).
    ocr = PaddleOCR(use_angle_cls=cls, lang=lang, use_gpu=use_gpu, det=det, rec=rec, show_log=False)

    pages_out: list[dict[str, Any]] = []
    for p in render_manifest.get("pages", []):
        page_no = int(p["page"])
        img_path = p["page_png"]
        result = ocr.ocr(img_path, cls=cls)

        lines: list[OcrLine] = []
        # PaddleOCR returns: [[ [poly], (text, conf) ], ...] (per image)
        for item in (result or []):
            if not item or len(item) < 2:
                continue
            poly = item[0]
            txt_conf = item[1]
            text = txt_conf[0] if isinstance(txt_conf, (list, tuple)) and len(txt_conf) > 0 else ""
            conf = txt_conf[1] if isinstance(txt_conf, (list, tuple)) and len(txt_conf) > 1 else None
            if not text:
                continue
            try:
                poly_f = [[float(x), float(y)] for x, y in poly]
            except Exception:
                poly_f = []
            lines.append(OcrLine(text=str(text), conf=float(conf) if conf is not None else None, poly=poly_f))

        pages_out.append({"page": page_no, "page_png": img_path, "lines": [asdict(l) for l in lines]})

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

