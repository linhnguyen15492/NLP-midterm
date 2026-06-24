from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf  # PyMuPDF


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import extract_pdf_paddleocr  # noqa: E402


def _make_pdf(path: Path, page_text: str) -> None:
    doc = pymupdf.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), page_text)
        doc.save(path.as_posix())
    finally:
        doc.close()


class TestExtractPdfPaddleOcr(unittest.TestCase):
    def test_extract_render_stage_writes_pngs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            pdf_path = td_path / "x.pdf"
            _make_pdf(pdf_path, "Hello")

            out_dir = td_path / "out"
            manifest = extract_pdf_paddleocr.extract_render_stage(pdf_path, out_dir, dpi=72, page_start=1, page_end=1)
            self.assertEqual(1, len(manifest["pages"]))
            png = Path(manifest["pages"][0]["page_png"])
            self.assertTrue(png.exists())

    def test_ocr_pages_stage_errors_when_paddleocr_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            pdf_path = td_path / "x.pdf"
            _make_pdf(pdf_path, "Hello")

            render = extract_pdf_paddleocr.extract_render_stage(pdf_path, td_path / "out", dpi=72, page_start=1, page_end=1)

            with patch.object(extract_pdf_paddleocr, "_import_paddleocr", side_effect=RuntimeError("no paddleocr")):
                with self.assertRaises(RuntimeError):
                    extract_pdf_paddleocr.ocr_pages_stage(render, lang="en")


if __name__ == "__main__":
    unittest.main()

