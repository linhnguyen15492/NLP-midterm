from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pymupdf  # PyMuPDF


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


def extract_text_blocks_by_page(
    pdf_path: Path,
    *,
    page_start: int = 1,
    page_end: int | None = None,
    join_blocks_with: str = "\n\n",
) -> list[dict[str, Any]]:
    """
    Stage 01: Extract text-layer blocks + bbox per page.

    Output format (per page):
      {
        "page": 1,
        "blocks": [{"bbox":[x0,y0,x1,y1], "text":"..."}],
        "page_text": "block1\\n\\nblock2..."
      }
    """
    pdf_path = Path(pdf_path)
    doc = pymupdf.open(pdf_path)
    try:
        total_pages = len(doc)
        if page_end is None:
            page_end = total_pages
        page_start = max(1, page_start)
        page_end = min(total_pages, page_end)

        pages: list[dict[str, Any]] = []
        for page_no in range(page_start, page_end + 1):
            page = doc[page_no - 1]
            blocks_out: list[dict[str, Any]] = []
            for b in page.get_text("blocks"):
                # (x0, y0, x1, y1, "text", block_no, block_type)
                if len(b) < 7:
                    continue
                x0, y0, x1, y1, text, _, block_type = b
                if block_type != 0:
                    continue
                t = (text or "").strip()
                if not t:
                    continue
                blocks_out.append({"bbox": [float(x0), float(y0), float(x1), float(y1)], "text": t})

            page_text = join_blocks_with.join(b["text"] for b in blocks_out)
            pages.append({"page": page_no, "blocks": blocks_out, "page_text": page_text})
        return pages
    finally:
        doc.close()


def clean_page_text(pages: list[dict[str, Any]], cleaner: Callable[[str], str]) -> list[dict[str, Any]]:
    """
    Stage 02: Clean text per page.
    Keeps Stage 01 blocks, adds "clean_text".
    """
    cleaned: list[dict[str, Any]] = []
    for p in pages:
        page_text = p.get("page_text", "") or ""
        t = cleaner(page_text)
        # Common PDF text-layer artifact: "V i ện  Đ ại  H ọc" style spacing.
        # Compress intra-word spacing a bit to help sentence splitting.
        t = re.sub(r"(?<=\\w)\\s+(?=\\w)", " ", t)
        out = dict(p)
        out["clean_text"] = t
        cleaned.append(out)
    return cleaned


def split_pages_to_sentences(
    pages: list[dict[str, Any]],
    *,
    splitter: Callable[[str], list[str]],
    id_builder: STCIDBuilder,
) -> list[dict[str, Any]]:
    """
    Stage 03: Sentence segmentation per page.
    Output is a flat list of sentence records with STC_ID for downstream alignment/export.
    """
    sentences: list[dict[str, Any]] = []
    for p in pages:
        page_no = int(p["page"])
        clean_text = p.get("clean_text", "") or ""
        parts = splitter(clean_text) if clean_text else []
        for idx, s in enumerate(parts, start=1):
            s2 = (s or "").strip()
            if not s2:
                continue
            sentences.append(
                {
                    "stc_id": id_builder.stc_id(page=page_no, sentence_idx=idx),
                    "page": page_no,
                    "order": idx,
                    "text": s2,
                }
            )
    return sentences


def export_alignment_input(
    sentences: list[dict[str, Any]],
    *,
    file_id: str,
    lang: str,
) -> dict[str, Any]:
    """
    Stage 04: Alignment-ready JSON schema.

    This file is meant to be paired with a corresponding Han (C) JSON of the same schema,
    then aligned (1-1 or m-n) by your alignment algorithm.
    """
    return {"file_id": file_id, "lang": lang, "units": sentences}


def write_json(obj: Any, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


_CH_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;:])\s*|\n+")


def clean_basic(text: str) -> str:
    text = (text or "").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_chinese_sentences(text: str) -> list[str]:
    cleaned = clean_basic(text)
    if not cleaned:
        return []
    parts = re.split(_CH_SENT_SPLIT, cleaned)
    return [p.strip() for p in parts if p.strip()]
