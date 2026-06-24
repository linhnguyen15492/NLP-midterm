from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lxml import etree

from clean_text import clean_vietnamese_text
from extract_pdf_paddleocr import extract_render_stage, ocr_pages_stage, write_json
from sentence_split import split_vietnamese_sentences
from text_pdf_stages import STCIDBuilder, export_alignment_input

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def export_viet_xml(
    out_xml: Path,
    *,
    file_id: str,
    meta: dict[str, str],
    id_builder: STCIDBuilder,
    units: list[dict[str, Any]],
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

    by_page: dict[int, list[dict[str, Any]]] = {}
    for u in units:
        by_page.setdefault(int(u["page"]), []).append(u)

    for page_no in sorted(by_page):
        page_el = etree.SubElement(sect_el, "PAGE", ID=id_builder.page_id(page=page_no))
        for u in by_page[page_no]:
            stc_el = etree.SubElement(page_el, "STC", ID=u["stc_id"])
            etree.SubElement(stc_el, "V").text = u["text"]

    out_xml.parent.mkdir(parents=True, exist_ok=True)
    out_xml.write_bytes(
        etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8")
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="OCR extractor (PaddleOCR) for Vietnamese scan/text PDFs -> 4 stages"
    )
    p.add_argument("--pdf", type=Path, default=Path(r"data/vie/Cong_Du_Tiep_Ky_1.pdf"))
    p.add_argument(
        "--out-dir", type=Path, default=Path(r"output/vie/cong_du_tiep_ky_1_paddleocr")
    )
    p.add_argument("--dpi", type=int, default=200)
    p.add_argument("--page-start", type=int, default=1)
    p.add_argument("--page-end", type=int, default=3)
    p.add_argument("--file-id", type=str, default="HVB_002")
    p.add_argument("--domain", type=str, default="H")
    p.add_argument("--sub-domain", type=str, default="V")
    p.add_argument("--genre", type=str, default="B")
    p.add_argument("--file-num", type=int, default=2)
    p.add_argument("--chapter", type=int, default=1)
    p.add_argument(
        "--lang-model",
        type=str,
        default="en",
        help="PaddleOCR lang model (often 'en' for Latin)",
    )
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

    # Stage 01: render
    s1 = extract_render_stage(
        args.pdf,
        out_dir=interim / "stage_01_render",
        dpi=args.dpi,
        page_start=args.page_start,
        page_end=args.page_end,
        overwrite=False,
    )
    write_json(s1, interim / "stage_01_render.json")

    # Stage 02: OCR (PaddleOCR)
    try:
        s2 = ocr_pages_stage(s1, lang=args.lang_model, use_gpu=False)
        write_json(s2, interim / "stage_02_ocr.json")
        ocr_error = None
    except Exception as e:
        # Still write a stage_02 file so the pipeline is inspectable.
        ocr_error = f"{type(e).__name__}: {e}"
        s2 = {"engine": "paddleocr", "error": ocr_error, "pages": []}
        write_json(s2, interim / "stage_02_ocr.json")

    # Stage 03: clean + sentence split (Vietnamese)
    units: list[dict[str, Any]] = []
    if not ocr_error:
        for p in s2.get("pages", []):
            page_no = int(p["page"])
            # Rebuild page text from OCR lines (order returned by OCR).
            page_text = "\n".join(
                (ln.get("text") or "").strip()
                for ln in p.get("lines", [])
                if (ln.get("text") or "").strip()
            )
            cleaned = clean_vietnamese_text(page_text)
            sents = split_vietnamese_sentences(cleaned) if cleaned else []
            for idx, sent in enumerate(sents, start=1):
                units.append(
                    {
                        "stc_id": id_builder.stc_id(page=page_no, sentence_idx=idx),
                        "page": page_no,
                        "order": idx,
                        "text": sent,
                    }
                )

    s3 = {"file_id": args.file_id, "lang": "V", "units": units}
    write_json(s3, interim / "stage_03_sentences.json")

    # Stage 04: alignment input (same schema used for C/V pairing)
    s4 = export_alignment_input(units, file_id=args.file_id, lang="V")
    write_json(s4, interim / "stage_04_alignment_input.json")

    # Optional final XML (still useful even if later you align with Han)
    meta = {
        "title": "Cong Du Tiep Ky 1",
        "volume": "",
        "author": "",
        "period": "",
        "language": "Viet",
        "source": str(args.pdf),
        "sect_name": "MAIN",
    }
    out_xml = final / f"{args.file_id}.xml"
    export_viet_xml(
        out_xml, file_id=args.file_id, meta=meta, id_builder=id_builder, units=units
    )

    summary = {
        "pdf": str(args.pdf),
        "out_dir": str(out_dir),
        "pages_requested": [args.page_start, args.page_end],
        "ocr_error": ocr_error,
        "stages": {
            "stage_01_render": str(interim / "stage_01_render.json"),
            "stage_02_ocr": str(interim / "stage_02_ocr.json"),
            "stage_03_sentences": str(interim / "stage_03_sentences.json"),
            "stage_04_alignment_input": str(interim / "stage_04_alignment_input.json"),
        },
        "final_xml": str(out_xml),
        "units": len(units),
    }
    write_json(summary, out_dir / "summary.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
