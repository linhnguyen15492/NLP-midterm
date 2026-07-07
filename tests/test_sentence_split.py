from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from sentence_split import build_sentence_records, write_sentence_json  # noqa: E402


class TestSentenceSplit(unittest.TestCase):
    def test_build_sentence_records_assigns_ids(self) -> None:
        records = build_sentence_records("Xin chào. Đây là câu thứ hai.")
        self.assertEqual(2, len(records))
        self.assertEqual({"sentence_id": 1, "sentence": "Xin chào."}, records[0])
        self.assertEqual({"sentence_id": 2, "sentence": "Đây là câu thứ hai."}, records[1])

    def test_write_sentence_json_writes_list_of_records(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "sentences.json"
            payload = [{"sentence_id": 1, "sentence": "Xin chào."}]
            write_sentence_json(payload, out_path)

            loaded = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(payload, loaded)


if __name__ == "__main__":
    unittest.main()