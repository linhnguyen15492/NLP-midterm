from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from extract_pdf_scan import extract_page_images, write_manifest


if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract intermediate artifacts from scan-based Vietnamese PDFs")
    p.add_argument(
        "--pdf",
        type=Path,
        default=Path(r"data/vie/An_Nam_Chi_Nguyen.pdf"),
        help="Input PDF path",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path(r"data/interim/vie/An_Nam_Chi_Nguyen"),
        help="Output directory for intermediate artifacts",
    )
    p.add_argument("--dpi", type=int, default=200, help="Render DPI for page PNGs")
    p.add_argument("--page-start", type=int, default=1, help="First page (1-based)")
    p.add_argument("--page-end", type=int, default=5, help="Last page (1-based). Use a large number for full run.")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing images")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    manifest = extract_page_images(
        pdf_path=args.pdf,
        out_dir=args.out_dir,
        dpi=args.dpi,
        page_start=args.page_start,
        page_end=args.page_end,
        overwrite=args.overwrite,
    )

    out_json = args.out_dir / "raw_manifest.json"
    write_manifest(manifest, out_json=out_json)

    summary = {
        "pdf": str(args.pdf),
        "out_dir": str(args.out_dir),
        "dpi": args.dpi,
        "pages_written": len(manifest.get("pages", [])),
        "manifest": str(out_json),
        "first_page_png": (manifest.get("pages") or [{}])[0].get("page_png"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

