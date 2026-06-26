from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lxml import etree

from clean_text import clean_vietnamese_text
from sentence_split import split_vietnamese_sentences
from text_pdf_stages import (
    STCIDBuilder,
    clean_page_text,
    export_alignment_input,
    extract_text_blocks_by_page,
    split_chinese_sentences,
    split_pages_to_sentences,
    write_json,
)

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def export_viet_xml(
    out_xml: Path,
    *,
    file_id: str,
    meta: dict[str, str],
    id_builder: STCIDBuilder,
    sentences: list[dict],
) -> None:
    """
    Export XML close to sample format in data/Sample_format/Viet_sample.xml:
      <root><FILE ID=...><meta>...</meta><SECT><PAGE><STC><V>...</V></STC>...
    """
    root = etree.Element("root")
    file_el = etree.SubElement(root, "FILE", ID=file_id)

    meta_el = etree.SubElement(file_el, "meta")
    for tag, key in [
        ("TITLE", "title"),
        ("VOLUME", "volume"),
        ("AUTHOR", "author"),
        ("PERIOD", "period"),
        ("LANGUAGE", "language"),
        ("SOURCE", "source"),
    ]:
        val = meta.get(key)
        if val:
            etree.SubElement(meta_el, tag).text = val

    sect_el = etree.SubElement(
        file_el, "SECT", ID=id_builder.sect_id(), NAME=meta.get("sect_name", "MAIN")
    )

    by_page: dict[int, list[dict]] = {}
    for s in sentences:
        by_page.setdefault(int(s["page"]), []).append(s)

    for page_no in sorted(by_page):
        page_el = etree.SubElement(sect_el, "PAGE", ID=id_builder.page_id(page=page_no))
        for s in by_page[page_no]:
            stc_el = etree.SubElement(page_el, "STC", ID=s["stc_id"])
            etree.SubElement(stc_el, "V").text = s["text"]

    out_xml.parent.mkdir(parents=True, exist_ok=True)
    out_xml.write_bytes(
        etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8")
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Staged extractor for text-layer PDFs (Vietnamese side)"
    )
    p.add_argument("--pdf", type=Path, default=Path(r"data/vie/An_Nam_Chi_Luoc.pdf"))
    p.add_argument(
        "--out-dir", type=Path, default=Path(r"output/vie/an_nam_chi_luoc_stages")
    )
    p.add_argument("--file-id", type=str, default="HVB_001")
    p.add_argument(
        "--lang",
        type=str,
        default="V",
        help="Language code for alignment_input.json (V or C)",
    )
    p.add_argument("--domain", type=str, default="H")
    p.add_argument("--sub-domain", type=str, default="V")
    p.add_argument("--genre", type=str, default="B")
    p.add_argument("--file-num", type=int, default=1)
    p.add_argument("--chapter", type=int, default=1)
    p.add_argument("--page-start", type=int, default=1)
    p.add_argument("--page-end", type=int, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir: Path = args.out_dir
    interim = out_dir / "interim"
    final = out_dir / "final"

    id_builder = STCIDBuilder(
        domain=args.domain,
        sub_domain=args.sub_domain,
        genre=args.genre,
        file_num=args.file_num,
        chapter=args.chapter,
    )

    # Select cleaner/splitter based on lang. (Vietnamese uses underthesea; Chinese uses regex.)
    if args.lang.upper() == "C":
        cleaner = lambda s: s.strip()  # noqa: E731
        splitter = split_chinese_sentences
    else:
        cleaner = clean_vietnamese_text
        splitter = split_vietnamese_sentences

    # Stage 01: extract blocks
    pages = extract_text_blocks_by_page(
        args.pdf, page_start=args.page_start, page_end=args.page_end
    )
    write_json(
        {"pdf": str(args.pdf), "pages": pages}, interim / "stage_01_extract.json"
    )

    # Stage 02: clean
    pages_clean = clean_page_text(pages, cleaner=cleaner)
    write_json(
        {"pdf": str(args.pdf), "pages": pages_clean}, interim / "stage_02_clean.json"
    )

    # Stage 03: sentences
    sentences = split_pages_to_sentences(
        pages_clean, splitter=splitter, id_builder=id_builder
    )
    write_json(
        {"pdf": str(args.pdf), "sentences": sentences},
        interim / "stage_03_sentences.json",
    )

    # Stage 04: alignment input (pair this with Han-side JSON of same schema)
    alignment_input = export_alignment_input(
        sentences, file_id=args.file_id, lang=args.lang
    )
    write_json(alignment_input, interim / "stage_04_alignment_input.json")

    # Final: XML
    meta = {
        "title": "An Nam Chi Luoc",
        "volume": "",
        "author": "Le Tac",
        "period": "The Ky 14 (1335)",
        "language": "Viet",
        "source": str(args.pdf),
        "sect_name": "MAIN",
    }
    out_xml = final / f"{args.file_id}.xml"
    export_viet_xml(
        out_xml,
        file_id=args.file_id,
        meta=meta,
        id_builder=id_builder,
        sentences=sentences,
    )

    summary = {
        "pdf": str(args.pdf),
        "out_dir": str(out_dir),
        "stages": {
            "stage_01_extract": str(interim / "stage_01_extract.json"),
            "stage_02_clean": str(interim / "stage_02_clean.json"),
            "stage_03_sentences": str(interim / "stage_03_sentences.json"),
            "stage_04_alignment_input": str(interim / "stage_04_alignment_input.json"),
        },
        "final_xml": str(out_xml),
        "pages": len(pages),
        "sentences": len(sentences),
    }
    write_json(summary, out_dir / "summary.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
