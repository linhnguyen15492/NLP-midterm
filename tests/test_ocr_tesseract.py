from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


# Allow importing modules from src/ (repo doesn't package them).
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import ocr_tesseract  # noqa: E402


class TestOcrTesseract(unittest.TestCase):
    def test_is_tesseract_available_can_be_mocked(self) -> None:
        with patch.object(ocr_tesseract.shutil, "which", return_value=None):
            self.assertFalse(ocr_tesseract.is_tesseract_available())
        with patch.object(ocr_tesseract.shutil, "which", return_value=r"C:\tesseract.exe"):
            self.assertTrue(ocr_tesseract.is_tesseract_available())

    def test_ocr_page_words_raises_when_tesseract_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            img_path = Path(td) / "page.png"
            Image.new("RGB", (10, 10), color=(255, 255, 255)).save(img_path)

            with patch.object(ocr_tesseract, "is_tesseract_available", return_value=False):
                with self.assertRaises(RuntimeError) as ctx:
                    ocr_tesseract.ocr_page_words(img_path, lang="vie")
                self.assertIn("not found", str(ctx.exception).lower())

    def test_ocr_page_words_with_mocked_pytesseract(self) -> None:
        class DummyPytesseract:
            class Output:
                DICT = object()

            @staticmethod
            def image_to_data(_img, lang: str, output_type):
                # Minimal structure used by ocr_page_words
                return {
                    "text": ["Xin", "chao", ""],
                    "left": [1, 20, 0],
                    "top": [2, 3, 0],
                    "width": [10, 11, 0],
                    "height": [12, 13, 0],
                    "conf": ["90", "85", "-1"],
                }

        with tempfile.TemporaryDirectory() as td:
            img_path = Path(td) / "page.png"
            Image.new("RGB", (100, 50), color=(255, 255, 255)).save(img_path)

            with patch.object(ocr_tesseract, "is_tesseract_available", return_value=True):
                with patch.object(ocr_tesseract, "pytesseract", DummyPytesseract):
                    out = ocr_tesseract.ocr_page_words(img_path, lang="vie")
                    self.assertEqual("tesseract", out["engine"])
                    self.assertEqual("vie", out["lang"])
                    self.assertEqual(2, len(out["words"]))
                    self.assertEqual("Xin", out["words"][0]["text"])

    def test_apply_ocr_to_manifest_writes_new_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            img_path = td_path / "p0001.png"
            Image.new("RGB", (20, 20), color=(255, 255, 255)).save(img_path)

            manifest_path = td_path / "raw_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "source_pdf": "x.pdf",
                        "pages": [{"page": 1, "page_png": str(img_path), "ocr": None}],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch.object(ocr_tesseract, "ocr_page_words", return_value={"engine": "tesseract", "words": []}):
                out_path = ocr_tesseract.apply_ocr_to_manifest(manifest_path, lang="vie")
                self.assertTrue(out_path.exists())
                loaded = json.loads(out_path.read_text(encoding="utf-8"))
                self.assertIn("ocr", loaded["pages"][0])
                self.assertEqual("tesseract", loaded["pages"][0]["ocr"]["engine"])


if __name__ == "__main__":
    unittest.main()

