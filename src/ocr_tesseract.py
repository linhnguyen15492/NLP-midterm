from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def is_tesseract_available() -> bool:
    # pytesseract needs the tesseract executable in PATH (or pytesseract.pytesseract.tesseract_cmd set).
    return shutil.which("tesseract") is not None


def ocr_page_words(image_path: Path, *, lang: str = "vie") -> dict[str, Any]:
    if pytesseract is None:
        raise RuntimeError("pytesseract is not importable in this environment.")
    if not is_tesseract_available():
        raise RuntimeError("tesseract executable not found in PATH.")

    with Image.open(image_path) as img:
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
    words: list[dict[str, Any]] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        conf_raw = str(data.get("conf", [""])[i]).strip()
        conf = None
        if conf_raw and conf_raw != "-1":
            try:
                conf = float(conf_raw)
            except ValueError:
                conf = None
        words.append({"text": text, "bbox": [float(x), float(y), float(x + w), float(y + h)], "conf": conf})

    return {"engine": "tesseract", "lang": lang, "words": words}


def apply_ocr_to_manifest(manifest_path: Path, *, lang: str = "vie") -> Path:
    """
    Reads a raw manifest (from extract_pdf_scan.py) and writes a new JSON with OCR filled in.
    Output path: <out_dir>/raw_manifest.ocr.json
    """
    manifest_path = Path(manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    for page in payload.get("pages", []):
        png_path = Path(page["page_png"])
        page["ocr"] = ocr_page_words(png_path, lang=lang)

    out_path = manifest_path.with_suffix(".ocr.json")
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
