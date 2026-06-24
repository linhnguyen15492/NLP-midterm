from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import pymupdf  # PyMuPDF

if sys.platform.startswith("win"):
    # Avoid mojibake when printing Vietnamese paths/text on Windows consoles.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


@dataclass
class EmbeddedImage:
    block_no: int
    bbox: list[float]  # [x0, y0, x1, y1] in PDF points
    width: int
    height: int
    ext: str  # e.g. "jpeg", "png"
    xres: int | None
    yres: int | None
    bpc: int | None
    colorspace: str | None
    size: int  # bytes
    sha1: str
    path: str


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def render_page_png(page: pymupdf.Page, out_path: Path, dpi: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mat = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    pix.save(out_path.as_posix())


def extract_page_images(
    pdf_path: Path,
    out_dir: Path,
    *,
    dpi: int = 200,
    page_start: int = 1,
    page_end: int | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Extract intermediate artifacts for scan-based PDFs:
    - Render each page to PNG.
    - Extract embedded image blocks (if present) to their native bytes (jpeg/png).
    - Save a raw JSON manifest for downstream OCR / alignment steps.

    This does NOT do OCR. It only prepares reproducible intermediate outputs.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    out_dir = Path(out_dir)
    pages_dir = out_dir / "pages"
    embedded_dir = out_dir / "embedded"

    doc = pymupdf.open(pdf_path)
    try:
        total_pages = len(doc)
        if page_end is None:
            page_end = total_pages
        page_start = max(1, page_start)
        page_end = min(total_pages, page_end)

        manifest: dict[str, Any] = {
            "source_pdf": str(pdf_path),
            "page_count": total_pages,
            "dpi": dpi,
            "pages": [],
        }

        for page_no in range(page_start, page_end + 1):
            page = doc[page_no - 1]

            # 1) Render the full page for OCR/debug later.
            page_png = pages_dir / f"p{page_no:04d}.png"
            if overwrite or not page_png.exists():
                render_page_png(page, page_png, dpi=dpi)

            # 2) Extract embedded images (scan PDFs typically have 1 image block per page).
            page_dict = page.get_text("dict")
            embedded_images: list[EmbeddedImage] = []
            for block in page_dict.get("blocks", []):
                if block.get("type") != 1:
                    continue
                img_bytes = block.get("image")
                ext = (block.get("ext") or "bin").lower()
                if not isinstance(img_bytes, (bytes, bytearray)) or not img_bytes:
                    continue

                sha1 = _sha1(bytes(img_bytes))
                out_name = f"p{page_no:04d}_b{int(block.get('number', 0)):03d}_{sha1[:10]}.{ext}"
                out_path = embedded_dir / out_name
                if overwrite or not out_path.exists():
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(bytes(img_bytes))

                embedded_images.append(
                    EmbeddedImage(
                        block_no=int(block.get("number", 0)),
                        bbox=[float(x) for x in block.get("bbox", (0, 0, 0, 0))],
                        width=int(block.get("width", 0) or 0),
                        height=int(block.get("height", 0) or 0),
                        ext=ext,
                        xres=(
                            int(block.get("xres"))
                            if block.get("xres") is not None
                            else None
                        ),
                        yres=(
                            int(block.get("yres"))
                            if block.get("yres") is not None
                            else None
                        ),
                        bpc=(
                            int(block.get("bpc"))
                            if block.get("bpc") is not None
                            else None
                        ),
                        colorspace=(
                            str(block.get("colorspace"))
                            if block.get("colorspace") is not None
                            else None
                        ),
                        size=int(block.get("size", len(img_bytes)) or len(img_bytes)),
                        sha1=sha1,
                        path=str(out_path),
                    )
                )

            manifest["pages"].append(
                {
                    "page": page_no,
                    "page_size": [float(page.rect.width), float(page.rect.height)],
                    "page_png": str(page_png),
                    "embedded_images": [asdict(img) for img in embedded_images],
                    "has_text_layer": False,  # for this scan-extractor, we assume scan unless caller checks otherwise
                    "ocr": None,  # to be filled by a later OCR stage
                }
            )

        return manifest
    finally:
        doc.close()


def write_manifest(manifest: dict[str, Any], out_json: Path) -> None:
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
