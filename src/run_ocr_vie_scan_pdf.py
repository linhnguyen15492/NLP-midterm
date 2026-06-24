from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ocr_tesseract import apply_ocr_to_manifest, is_tesseract_available

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run OCR (Tesseract) on extracted scan-PDF page PNGs"
    )
    p.add_argument(
        "--manifest",
        type=Path,
        default=Path(r"data/interim/vie/An_Nam_Chi_Nguyen/raw_manifest.json"),
        help="Path to raw manifest JSON produced by run_extract_vie_scan_pdf.py",
    )
    p.add_argument(
        "--lang",
        type=str,
        default="vie",
        help="Tesseract language code (e.g. vie, eng)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not is_tesseract_available():
        print(
            json.dumps(
                {
                    "error": "tesseract_not_found",
                    "message": "Không tìm thấy `tesseract` trong PATH. Hãy cài Tesseract OCR (kèm traineddata `vie`) rồi chạy lại.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2)

    out_path = apply_ocr_to_manifest(args.manifest, lang=args.lang)
    print(
        json.dumps(
            {"manifest_in": str(args.manifest), "manifest_out": str(out_path)},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
