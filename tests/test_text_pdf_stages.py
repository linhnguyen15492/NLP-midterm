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

from text_pdf_stages import (  # noqa: E402
    STCIDBuilder,
    clean_basic,
    clean_page_text,
    export_alignment_input,
    extract_text_blocks_by_page,
    split_chinese_sentences,
    split_pages_to_sentences,
    write_json,
)


def _make_pdf(path: Path, page_text: str) -> None:
    doc = pymupdf.open()
    try:
        page = doc.new_page()
        # Use a basic font. Keep text simple ASCII + Chinese punctuation to avoid font issues.
        page.insert_text((72, 72), page_text)
        doc.save(path.as_posix())
    finally:
        doc.close()


class TestTextPdfStages(unittest.TestCase):
    def test_extract_text_blocks_by_page_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pdf_path = Path(td) / "sample.pdf"
            _make_pdf(pdf_path, "Hello。World！\nLine2")

            pages = extract_text_blocks_by_page(pdf_path, page_start=1, page_end=1)
            self.assertEqual(1, len(pages))
            self.assertEqual(1, pages[0]["page"])
            self.assertIn("blocks", pages[0])
            self.assertIn("page_text", pages[0])
            self.assertIn("Hello", pages[0]["page_text"])

    def test_clean_page_text_adds_clean_text(self) -> None:
        pages = [{"page": 1, "blocks": [], "page_text": "A   B\n\nC"}]
        cleaned = clean_page_text(pages, cleaner=lambda s: s.replace("\n", " "))
        self.assertIn("clean_text", cleaned[0])
        # cleaner doesn't normalize multiple spaces; clean_page_text only does light intra-word compression
        self.assertEqual("A   B  C", cleaned[0]["clean_text"])

    def test_split_pages_to_sentences_uses_builder_ids(self) -> None:
        idb = STCIDBuilder(domain="H", sub_domain="V", genre="B", file_num=1, chapter=1)
        pages = [{"page": 2, "clean_text": "x y z"}]
        sents = split_pages_to_sentences(pages, splitter=lambda _: ["s1", "s2"], id_builder=idb)
        self.assertEqual(2, len(sents))
        self.assertEqual("HVB_001.001.002.01", sents[0]["stc_id"])
        self.assertEqual("HVB_001.001.002.02", sents[1]["stc_id"])
        self.assertEqual(2, sents[0]["page"])
        self.assertEqual(1, sents[0]["order"])

    def test_export_alignment_input_schema(self) -> None:
        units = [{"stc_id": "X", "page": 1, "order": 1, "text": "t"}]
        payload = export_alignment_input(units, file_id="HVB_001", lang="V")
        self.assertEqual("HVB_001", payload["file_id"])
        self.assertEqual("V", payload["lang"])
        self.assertEqual(units, payload["units"])

    def test_split_chinese_sentences(self) -> None:
        parts = split_chinese_sentences("A。B！ C？\nD；E: F")
        self.assertGreaterEqual(len(parts), 4)
        self.assertEqual("A。", parts[0])
        self.assertTrue(parts[1].startswith("B"))

    def test_clean_basic(self) -> None:
        self.assertEqual("A\n\nB", clean_basic("A\r\n\r\n\r\nB"))

    def test_write_json_writes_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "x.json"
            write_json({"t": "Tiếng Việt"}, out)
            loaded = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual("Tiếng Việt", loaded["t"])


if __name__ == "__main__":
    unittest.main()
