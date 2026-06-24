from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf  # PyMuPDF
from lxml import etree

from clean_text import clean_vietnamese_text
from sentence_split import split_vietnamese_sentences

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class STCIDBuilder:
    domain: str
    sub_domain: str
    genre: str
    file_num: int
    chapter: int

    def stc_id(self, *, page: int, sentence_idx: int) -> str:
        dsg = f"{self.domain}{self.sub_domain}{self.genre}"
        return f"{dsg}_{self.file_num:03d}.{self.chapter:03d}.{page:03d}.{sentence_idx:02d}"

    def page_id(self, *, page: int) -> str:
        dsg = f"{self.domain}{self.sub_domain}{self.genre}"
        return f"{dsg}_{self.file_num:03d}.{self.chapter:03d}.{page:03d}"

    def sect_id(self) -> str:
        dsg = f"{self.domain}{self.sub_domain}{self.genre}"
        return f"{dsg}_{self.file_num:03d}.{self.chapter:03d}"


def extract_text_by_page(pdf_path: Path) -> list[dict[str, Any]]:
    doc = pymupdf.open(pdf_path)
    try:
        pages: list[dict[str, Any]] = []
        for i in range(len(doc)):
            page_no = i + 1
            page = doc[i]
            raw_text = page.get_text("text")
            pages.append({"page": page_no, "raw_text": raw_text})
        return pages
    finally:
        doc.close()


def build_sentences(
    pages: list[dict[str, Any]], id_builder: STCIDBuilder
) -> list[dict[str, Any]]:
    sentences: list[dict[str, Any]] = []
    for p in pages:
        page_no = int(p["page"])
        cleaned = clean_vietnamese_text(p.get("raw_text", "") or "")
        # Normalize the cover-page "spaced letters" a bit (very common in scans converted to text layer).
        cleaned = re.sub(r"(?<=\w)\s+(?=\w)", " ", cleaned)
        page_sents = split_vietnamese_sentences(cleaned) if cleaned else []

        for idx, s in enumerate(page_sents, start=1):
            sentences.append(
                {
                    "stc_id": id_builder.stc_id(page=page_no, sentence_idx=idx),
                    "page": page_no,
                    "order": idx,
                    "text": s,
                }
            )
    return sentences


def export_viet_xml(
    out_xml: Path,
    *,
    file_id: str,
    meta: dict[str, str],
    id_builder: STCIDBuilder,
    sentences: list[dict[str, Any]],
) -> None:
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

    # group by page
    by_page: dict[int, list[dict[str, Any]]] = {}
    for s in sentences:
        by_page.setdefault(int(s["page"]), []).append(s)

    for page_no in sorted(by_page):
        page_el = etree.SubElement(sect_el, "PAGE", ID=id_builder.page_id(page=page_no))
        for s in by_page[page_no]:
            stc_el = etree.SubElement(page_el, "STC", ID=s["stc_id"])
            # For monolingual Vietnamese, store content under <V> to stay consistent with the bilingual sample tags.
            etree.SubElement(stc_el, "V").text = s["text"]

    out_xml.parent.mkdir(parents=True, exist_ok=True)
    out_xml.write_bytes(
        etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8")
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build monolingual Vietnamese corpus artifacts from a text-layer PDF"
    )
    p.add_argument("--pdf", type=Path, default=Path(r"data/vie/An_Nam_Chi_Luoc.pdf"))
    p.add_argument("--out-dir", type=Path, default=Path(r"output/vie/an_nam_chi_luoc"))
    p.add_argument("--file-id", type=str, default="HVB_001")
    p.add_argument("--file-num", type=int, default=1)
    p.add_argument("--chapter", type=int, default=1)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path: Path = args.pdf
    out_dir: Path = args.out_dir
    interim_dir = out_dir / "interim"
    final_dir = out_dir / "final"

    id_builder = STCIDBuilder(
        domain="H",
        sub_domain="V",
        genre="B",
        file_num=args.file_num,
        chapter=args.chapter,
    )

    pages = extract_text_by_page(pdf_path)
    (interim_dir / "pages_text.json").parent.mkdir(parents=True, exist_ok=True)
    (interim_dir / "pages_text.json").write_text(
        json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    sentences = build_sentences(pages, id_builder=id_builder)
    (interim_dir / "sentences.json").write_text(
        json.dumps(sentences, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    meta = {
        "title": "An Nam Chi Luoc",
        "volume": "",
        "author": "Le Tac",
        "period": "The Ky 14 (1335)",
        "language": "Viet",
        "source": str(pdf_path),
        "sect_name": "MAIN",
    }
    out_xml = final_dir / f"{args.file_id}.xml"
    export_viet_xml(
        out_xml,
        file_id=args.file_id,
        meta=meta,
        id_builder=id_builder,
        sentences=sentences,
    )

    summary = {
        "pdf": str(pdf_path),
        "out_dir": str(out_dir),
        "pages": len(pages),
        "sentences": len(sentences),
        "xml": str(out_xml),
        "interim_pages_json": str(interim_dir / "pages_text.json"),
        "interim_sentences_json": str(interim_dir / "sentences.json"),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
