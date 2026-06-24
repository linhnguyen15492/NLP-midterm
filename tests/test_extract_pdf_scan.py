from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


# Allow importing modules from src/ (repo doesn't package them).
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from extract_pdf_scan import extract_page_images, write_manifest  # noqa: E402


class TestExtractPdfScan(unittest.TestCase):
    def test_extract_page_images_creates_files_and_manifest(self) -> None:
        pdf_path = REPO_ROOT / "data" / "vie" / "An_Nam_Chi_Nguyen.pdf"
        self.assertTrue(pdf_path.exists(), f"Missing test fixture PDF: {pdf_path}")

        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "interim"
            manifest = extract_page_images(
                pdf_path=pdf_path,
                out_dir=out_dir,
                dpi=72,  # keep the test light
                page_start=1,
                page_end=1,
                overwrite=True,
            )

            self.assertIn("page_count", manifest)
            self.assertEqual(1, len(manifest["pages"]))
            page = manifest["pages"][0]
            self.assertEqual(1, page["page"])

            page_png = Path(page["page_png"])
            self.assertTrue(page_png.exists(), f"Expected rendered PNG to exist: {page_png}")

            embedded = page.get("embedded_images", [])
            # For this scan PDF, we expect at least one embedded image on page 1.
            self.assertGreaterEqual(len(embedded), 1)
            for img in embedded:
                self.assertIn("ext", img)
                self.assertIn("path", img)
                self.assertTrue(Path(img["path"]).exists(), f"Expected embedded image to exist: {img['path']}")

    def test_write_manifest_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_json = Path(td) / "raw_manifest.json"
            manifest = {"source_pdf": "x.pdf", "page_count": 1, "dpi": 72, "pages": [{"page": 1}]}
            write_manifest(manifest, out_json=out_json)
            self.assertTrue(out_json.exists())
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(manifest["page_count"], loaded["page_count"])


if __name__ == "__main__":
    unittest.main()

