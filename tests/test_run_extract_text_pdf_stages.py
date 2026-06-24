from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf  # PyMuPDF


# Allow importing modules from src/ (repo doesn't package them).
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))


def _make_pdf(path: Path, page_text: str) -> None:
    doc = pymupdf.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), page_text)
        doc.save(path.as_posix())
    finally:
        doc.close()


class TestRunExtractTextPdfStages(unittest.TestCase):
    def test_runner_creates_stage_files_lang_c(self) -> None:
        # Use lang=C path to avoid underthesea dependency and keep splitting deterministic.
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            pdf_path = td_path / "sample.pdf"
            _make_pdf(pdf_path, "A。B！\nC。")

            out_dir = td_path / "out"

            import run_extract_text_pdf_stages as runner  # noqa: E402

            argv = [
                "run_extract_text_pdf_stages.py",
                "--pdf",
                str(pdf_path),
                "--out-dir",
                str(out_dir),
                "--file-id",
                "HVB_999",
                "--lang",
                "C",
                "--domain",
                "H",
                "--sub-domain",
                "S",
                "--genre",
                "B",
                "--file-num",
                "999",
                "--chapter",
                "1",
                "--page-start",
                "1",
                "--page-end",
                "1",
            ]

            old_argv = sys.argv
            try:
                sys.argv = argv
                runner.main()
            finally:
                sys.argv = old_argv

            summary_path = out_dir / "summary.json"
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual("C", json.loads((out_dir / "interim" / "stage_04_alignment_input.json").read_text(encoding="utf-8"))["lang"])

            # Stage files exist
            for p in summary["stages"].values():
                self.assertTrue(Path(p).exists(), f"Missing stage file: {p}")
            self.assertTrue(Path(summary["final_xml"]).exists())


if __name__ == "__main__":
    unittest.main()

