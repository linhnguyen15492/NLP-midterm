from __future__ import annotations

import json
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

    def test_ocr_pages_stage_parses_dummy_output(self) -> None:
        """
        Unit test for parsing PaddleOCR output without requiring the real paddleocr package.
        """

        class DummyOCR:
            def __init__(self, **_kwargs):
                pass

            def ocr(self, _img_path: str, cls: bool = True):
                # PaddleOCR-like structure:
                # [
                #   [poly, (text, conf)],
                #   ...
                # ]
                return [
                    (
                        [[0, 0], [10, 0], [10, 10], [0, 10]],
                        ("Xin chao", 0.98),
                    ),
                    (
                        [[0, 20], [10, 20], [10, 30], [0, 30]],
                        ("Viet Nam", 0.87),
                    ),
                ]

        class DummyPaddleOCR:
            def __init__(self, **kwargs):
                self._impl = DummyOCR(**kwargs)

            def ocr(self, img_path: str, cls: bool = True):
                return self._impl.ocr(img_path, cls=cls)

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            pdf_path = td_path / "x.pdf"
            _make_pdf(pdf_path, "Hello")

            render = extract_pdf_paddleocr.extract_render_stage(pdf_path, td_path / "out", dpi=72, page_start=1, page_end=1)

            with patch.object(extract_pdf_paddleocr, "_import_paddleocr", return_value=DummyPaddleOCR):
                out = extract_pdf_paddleocr.ocr_pages_stage(render, lang="en", use_gpu=False, det=True, rec=True, cls=True)
                self.assertEqual("paddleocr", out["engine"])
                self.assertEqual("en", out["lang"])
                self.assertEqual(1, len(out["pages"]))
                lines = out["pages"][0]["lines"]
                self.assertEqual(2, len(lines))
                self.assertEqual("Xin chao", lines[0]["text"])
                self.assertAlmostEqual(0.98, lines[0]["conf"], places=6)
                self.assertEqual([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]], lines[0]["poly"])

    def test_runner_stage_outputs_with_mocked_paddleocr(self) -> None:
        """
        Integration-style test of the 4-stage runner with mocked PaddleOCR so that:
        - stage_02 has OCR lines
        - stage_03/04 produce non-empty units
        """

        class DummyPaddleOCR:
            def __init__(self, **_kwargs):
                pass

            def ocr(self, _img_path: str, cls: bool = True):
                return [
                    (
                        [[0, 0], [10, 0], [10, 10], [0, 10]],
                        ("Xin chao Viet Nam.", 0.99),
                    )
                ]

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            pdf_path = td_path / "x.pdf"
            _make_pdf(pdf_path, "Hello")

            out_dir = td_path / "out"

            import run_extract_vie_paddleocr_stages as runner  # noqa: E402

            argv = [
                "run_extract_vie_paddleocr_stages.py",
                "--pdf",
                str(pdf_path),
                "--out-dir",
                str(out_dir),
                "--page-start",
                "1",
                "--page-end",
                "1",
                "--dpi",
                "72",
                "--file-id",
                "HVB_777",
                "--file-num",
                "777",
                "--chapter",
                "1",
                "--lang-model",
                "en",
            ]

            old_argv = sys.argv
            try:
                sys.argv = argv
                with patch.object(extract_pdf_paddleocr, "_import_paddleocr", return_value=DummyPaddleOCR):
                    runner.main()
            finally:
                sys.argv = old_argv

            summary_path = out_dir / "summary.json"
            self.assertTrue(summary_path.exists())

            stage3 = json.loads((out_dir / "interim" / "stage_03_sentences.json").read_text(encoding="utf-8"))
            stage4 = json.loads((out_dir / "interim" / "stage_04_alignment_input.json").read_text(encoding="utf-8"))
            self.assertEqual("HVB_777", stage4["file_id"])
            self.assertEqual("V", stage4["lang"])
            self.assertGreaterEqual(len(stage3["units"]), 1)
            self.assertGreaterEqual(len(stage4["units"]), 1)
            self.assertTrue((out_dir / "final" / "HVB_777.xml").exists())


if __name__ == "__main__":
    unittest.main()
