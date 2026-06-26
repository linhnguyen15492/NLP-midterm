from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

import fitz
from openpyxl import Workbook

SOURCE_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
LATIN_PATTERN = re.compile(r"[A-Za-zÀ-ỹà-ỹ]")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？!?；;:\n])\s+")


@dataclass
class SentenceRecord:
    index: int
    page: int
    order: int
    text: str
    lang: str
    top: float


@dataclass
class AlignmentRecord:
    stc_id: str
    c_text: str
    v_text: str
    page: int
    confidence: float


def extract_text_pages(
    pdf_path: Path, max_pages: int | None = None
) -> list[tuple[int, str]]:
    document = fitz.open(pdf_path)
    pages: list[tuple[int, str]] = []
    for page_index, page in enumerate(document, start=1):
        if max_pages is not None and page_index > max_pages:
            break
        block_texts: list[str] = []
        for block in page.get_text("blocks"):
            if len(block) < 7:
                continue
            block_type = block[6]
            text = block[4].strip()
            if block_type == 0 and text:
                block_texts.append(text)
        pages.append((page_index, "\n\n".join(block_texts)))
    document.close()
    return pages


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    segments = re.split(r"\n\s*\n", cleaned)
    sentences: list[str] = []
    for segment in segments:
        chunk = segment.strip()
        if not chunk:
            continue
        split_parts = re.split(SENTENCE_SPLIT_PATTERN, chunk)
        if len(split_parts) == 1:
            sentences.append(chunk)
        else:
            sentences.extend(part.strip() for part in split_parts if part.strip())
    return sentences


def detect_lang(text: str) -> str:
    chinese_hits = len(SOURCE_PATTERN.findall(text))
    latin_hits = len(LATIN_PATTERN.findall(text))
    if chinese_hits > latin_hits:
        return "C"
    if latin_hits > 0:
        return "V"
    return "UNK"


def build_sentence_records(pages: Iterable[tuple[int, str]]) -> list[SentenceRecord]:
    records: list[SentenceRecord] = []
    sentence_index = 1
    for page_number, page_text in pages:
        page_units = split_sentences(page_text)
        for order, sentence in enumerate(page_units, start=1):
            records.append(
                SentenceRecord(
                    index=sentence_index,
                    page=page_number,
                    order=order,
                    text=sentence,
                    lang=detect_lang(sentence),
                    top=float(order),
                )
            )
            sentence_index += 1
    return records


def align_sentences(records: list[SentenceRecord]) -> list[AlignmentRecord]:
    by_page: dict[int, dict[str, list[SentenceRecord]]] = {}
    for record in records:
        page_entry = by_page.setdefault(record.page, {"C": [], "V": [], "UNK": []})
        page_entry.setdefault(record.lang, []).append(record)

    alignments: list[AlignmentRecord] = []
    stc_counter = 1

    for page_number in sorted(by_page):
        chinese_items = by_page[page_number].get("C", [])
        vietnamese_items = by_page[page_number].get("V", [])
        pair_count = min(len(chinese_items), len(vietnamese_items))
        for pair_index in range(pair_count):
            chinese_item = chinese_items[pair_index]
            vietnamese_item = vietnamese_items[pair_index]
            length_ratio = min(len(chinese_item.text), len(vietnamese_item.text)) / max(
                len(chinese_item.text), len(vietnamese_item.text), 1
            )
            confidence = round(0.55 + 0.35 * length_ratio, 3)
            alignments.append(
                AlignmentRecord(
                    stc_id=f"ABC_{stc_counter:03d}.{page_number:03d}.01",
                    c_text=chinese_item.text,
                    v_text=vietnamese_item.text,
                    page=page_number,
                    confidence=confidence,
                )
            )
            stc_counter += 1

    return alignments


def export_xml(alignments: list[AlignmentRecord], output_path: Path) -> None:
    root = ET.Element("DOC")
    for item in alignments:
        stc = ET.SubElement(root, "STC_ID", {"value": item.stc_id})
        c_node = ET.SubElement(stc, "C")
        c_node.text = item.c_text
        v_node = ET.SubElement(stc, "V")
        v_node.text = item.v_text
        confidence_node = ET.SubElement(stc, "CONFIDENCE")
        confidence_node.text = f"{item.confidence:.3f}"

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def export_excel(alignments: list[AlignmentRecord], output_path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "alignment"
    worksheet.append(["STC_ID", "C", "V", "page", "confidence"])
    for item in alignments:
        worksheet.append(
            [item.stc_id, item.c_text, item.v_text, item.page, item.confidence]
        )
    workbook.save(output_path)


def export_debug_json(sentences: list[SentenceRecord], output_path: Path) -> None:
    payload = [
        {
            "index": item.index,
            "page": item.page,
            "order": item.order,
            "lang": item.lang,
            "text": item.text,
        }
        for item in sentences
    ]
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_sample(
    pdf_path: Path, output_dir: Path, page_start: int = 1, page_end: int | None = 3
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Extracting text from {pdf_path.name}")
    pages = extract_text_pages(pdf_path)
    pages = [page for page in pages if page_start <= page[0] <= (page_end or page[0])]

    print("[2/4] Splitting sentences and tagging language")
    sentence_records = build_sentence_records(pages)
    export_debug_json(sentence_records, output_dir / "sentences.json")

    print("[3/4] Aligning C/V sentence pairs")
    alignments = align_sentences(sentence_records)

    print("[4/4] Exporting XML and Excel")
    export_xml(alignments, output_dir / "alignment.xml")
    export_excel(alignments, output_dir / "alignment.xlsx")

    summary = {
        "pages_extracted": len(pages),
        "sentences": len(sentence_records),
        "alignments": len(alignments),
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def resolve_pdf_path() -> Path:
    candidate = Path("pdf/An Nam Chí Lược.pdf")
    if candidate.exists():
        return candidate
    pdf_dir = Path("pdf")
    for path in pdf_dir.glob("*.pdf"):
        if "An Nam" in path.name and "Lược" in path.name:
            return path
    raise FileNotFoundError("Could not find the An Nam Chí Lược PDF in pdf/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample Hán-Việt corpus pipeline")
    parser.add_argument("--pdf", type=Path, default=None, help="PDF input path")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/sample"),
        help="Output directory",
    )
    parser.add_argument(
        "--page-start", type=int, default=1, help="First page to sample"
    )
    parser.add_argument("--page-end", type=int, default=3, help="Last page to sample")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = args.pdf or resolve_pdf_path()
    build_sample(
        pdf_path=pdf_path,
        output_dir=args.output_dir,
        page_start=args.page_start,
        page_end=args.page_end,
    )


if __name__ == "__main__":
    main()
