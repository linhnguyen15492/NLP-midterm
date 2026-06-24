import json
import sys
from typing import List
import pymupdf
from pathlib import Path

path = "data/raw/An_Nam_Chi_Luoc.pdf"


def extract_text(path):
    pdf_path = Path(path)
    if not pdf_path.exists():
        print(f"[Lỗi] Không tìm thấy file {pdf_path}")
        sys.exit(1)

    doc = pymupdf.open(pdf_path)

    raw_text = list()
    for page in doc:
        page_num = page.number
        text = page.get_text("text")
        raw_text.append({"page_num": page_num, "text": text})

    print(f"Trích xuất text layer gồm trang {len(doc)}...")

    return raw_text


def save_to_json(raw_text, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw_text, f)


def main():

    text = extract_text(path)
    print(text)
    print(f"ổng số ký tự: {len(text)}")
    save_to_json(text, "output/processed/extracted_text.json")


if __name__ == "__main__":
    main()
