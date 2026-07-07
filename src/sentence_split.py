from __future__ import annotations

import json
from pathlib import Path

from underthesea import sent_tokenize


def split_vietnamese_sentences(cleaned_text: str):
    sentences = sent_tokenize(cleaned_text)

    return [s.strip() for s in sentences if len(s.strip()) > 2]


def build_sentence_records(cleaned_text: str) -> list[dict[str, object]]:
    sentences = split_vietnamese_sentences(cleaned_text)
    return [
        {"sentence_id": idx, "sentence": sentence}
        for idx, sentence in enumerate(sentences, start=1)
    ]


def write_sentence_json(records: list[dict[str, object]], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    input_path = "output/cleaned_text/cleaned_viet.txt"
    output_path = Path("output/sentences/viet_sentences.json")
    with open(input_path, "r", encoding="utf-8") as f:
        cleaned_text = f.read()
    records = build_sentence_records(cleaned_text)
    write_sentence_json(records, output_path)
    print(json.dumps({"output_path": str(output_path), "sentences": len(records)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
