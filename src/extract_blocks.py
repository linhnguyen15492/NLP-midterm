import pymupdf
import json
import re
from collections import Counter
from utils.io import save_json

PAGE_PATTERNS = [
    r"^\d+$",
    r"^Trang\s+\d+$",
    r"^Page\s+\d+$",
    r"^\-\d+\-$",
    r"^\[\d+\]$",
    r"^第.*頁$",
]

CHAPTER_PATTERNS = [
    r"^卷.+$",
    r"^第.+卷$",
    r"^第.+回$",
    r"^第.+章$",
    r"^Quyển.+$",
    r"^Chương.+$",
]


def is_page_number(text):

    text = text.strip()

    for p in PAGE_PATTERNS:
        if re.match(p, text):
            return True

    return False


def is_chapter(text):

    for p in CHAPTER_PATTERNS:
        if re.match(p, text):
            return True

    return False


def detect_repeated_blocks(pages):

    counter = Counter()

    for page in pages:

        for block in page["blocks"]:

            text = block["text"].strip()

            if text:
                counter[text] += 1

    threshold = len(pages) * 0.7

    repeated = set()

    for text, freq in counter.items():

        if freq >= threshold:
            repeated.add(text)

    return repeated


def detect_title(first_pages):

    candidates = []

    font_sizes = []

    for page in first_pages:
        for block in page["blocks"]:
            font_sizes.append(block["font_size"])

    avg_size = sum(font_sizes) / len(font_sizes)

    for page in first_pages:

        for block in page["blocks"]:

            if block["font_size"] > avg_size * 1.5 and len(block["text"]) < 100:
                candidates.append(block)

    return candidates


def classify_blocks(pages):

    repeated = detect_repeated_blocks(pages)

    titles = detect_title(pages[:3])

    title_texts = {t["text"] for t in titles}

    for page in pages:

        h = page["height"]

        for block in page["blocks"]:

            text = block["text"]

            x0, y0, x1, y1 = block["bbox"]

            block_type = "content"

            if text in title_texts:
                block_type = "title"

            elif is_page_number(text):
                block_type = "page_number"

            elif is_chapter(text):
                block_type = "chapter"

            elif text in repeated:

                if y0 < h * 0.15:
                    block_type = "header"

                elif y1 > h * 0.85:
                    block_type = "footer"

            block["type"] = block_type

    return pages


def extract_pdf_blocks(pdf_path):

    doc = pymupdf.open(pdf_path)

    pages = []

    for page_id in range(len(doc)):

        page = doc[page_id]

        page_dict = page.get_text("dict")

        page_width = page.rect.width
        page_height = page.rect.height

        blocks = []

        for block in page_dict["blocks"]:

            if "lines" not in block:
                continue

            text = ""

            font_size = []

            font_name = []

            for line in block["lines"]:
                for span in line["spans"]:
                    text += span["text"]
                    text += " "

                    font_size.append(span["size"])
                    font_name.append(span["font"])

            text = text.strip()

            if not text:
                continue

            x0, y0, x1, y1 = block["bbox"]

            blocks.append(
                {
                    "text": text,
                    "bbox": [x0, y0, x1, y1],
                    "font_size": (sum(font_size) / len(font_size) if font_size else 0),
                    "font_name": (font_name[0] if font_name else ""),
                }
            )

        pages.append(
            {
                "page": page_id + 1,
                "width": page_width,
                "height": page_height,
                "blocks": blocks,
            }
        )

    return pages


def main():
    pdf = "data/raw/An_Nam_Chi_Luoc.pdf"

    pages = extract_pdf_blocks(pdf)
    print(pages[0])

    pages = classify_blocks(pages)

    save_json(pages, "layout.json")


if __name__ == "__main__":
    main()
