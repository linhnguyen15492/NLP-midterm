from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple, Set

import pymupdf  # PyMuPDF
from openpyxl import Workbook
from rapidfuzz.distance import Levenshtein

# ----------------------------------------------------------------------
# 0. CONFIGURATION & ENCODING
# ----------------------------------------------------------------------
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ----------------------------------------------------------------------
# 1. DATA MODELS
# ----------------------------------------------------------------------
@dataclass
class STCIDBuilder:
    domain: str
    sub_domain: str
    genre: str
    file_num: int
    chapter: int
    page: int

    def generate(self, sentence_idx: int) -> str:
        dsg = f"{self.domain}{self.sub_domain}{self.genre}"
        return f"{dsg}_{self.file_num:03d}.{self.chapter:03d}.{self.page:03d}.{sentence_idx:02d}"


# Dictionary for character similarity (S1 dict mockup for Vietnamese)
S1_SIMILARITY_VIET = {
    "D": {"D": 1.0, "Đ": 0.8, "O": 0.5},
    "đ": {"đ": 1.0, "d": 0.8},
    "d": {"d": 1.0, "đ": 0.8},
    "o": {"o": 1.0, "ô": 0.9, "ơ": 0.9, "a": 0.6},
    "ô": {"ô": 1.0, "o": 0.9, "ơ": 0.8},
    "ơ": {"ơ": 1.0, "o": 0.9, "ô": 0.8},
    "u": {"u": 1.0, "ư": 0.9, "v": 0.7},
    "ư": {"ư": 1.0, "u": 0.9},
    "a": {"a": 1.0, "ă": 0.9, "â": 0.9, "o": 0.6},
    "ă": {"ă": 1.0, "a": 0.9, "â": 0.8},
    "â": {"â": 1.0, "a": 0.9, "ă": 0.8},
    "e": {"e": 1.0, "ê": 0.9},
    "ê": {"ê": 1.0, "e": 0.9},
}


# ----------------------------------------------------------------------
# STAGE 1: EXTRACTION (PDF -> JSON)
# ----------------------------------------------------------------------
class ExtractionStage:
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path

    def run(self, page_num: int, output_json_path: Path) -> Dict:
        """
        Extract page text and coordinates using PyMuPDF's rawdict.
        Saves the results to an intermediate JSON file.
        """
        print(
            f"[Stage 1: Extraction] Processing page {page_num} of {self.pdf_path.name}"
        )
        doc = pymupdf.open(self.pdf_path)
        if page_num > len(doc):
            page_num = len(doc)

        page = doc[page_num - 1]
        raw_dict = page.get_text("rawdict")

        page_width = raw_dict.get("width", 0.0)
        page_height = raw_dict.get("height", 0.0)

        extracted_lines = []

        for block in raw_dict.get("blocks", []):
            for line in block.get("lines", []):
                line_text_parts = []
                line_chars = []
                for span in line.get("spans", []):
                    for char_info in span.get("chars", []):
                        c = char_info.get("c", "")
                        bbox = char_info.get("bbox", (0.0, 0.0, 0.0, 0.0))
                        line_text_parts.append(c)
                        if c.strip():
                            line_chars.append(
                                {
                                    "char": c,
                                    "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
                                }
                            )

                full_text = "".join(line_text_parts).strip()
                if len(full_text) > 3 and not full_text.isdigit() and line_chars:
                    # Sort characters from left to right inside the line
                    line_chars.sort(key=lambda x: x["bbox"][0])
                    extracted_lines.append({"text": full_text, "chars": line_chars})

        # Sort lines from top to bottom
        extracted_lines.sort(
            key=lambda x: sum(c["bbox"][1] for c in x["chars"]) / len(x["chars"])
        )

        # Build payload
        payload = {
            "page_num": page_num,
            "width": page_width,
            "height": page_height,
            "lines": extracted_lines,
        }

        # Save to JSON
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        doc.close()
        print(f"   Saved extracted JSON to: {output_json_path}")
        return payload


# ----------------------------------------------------------------------
# STAGE 2: ALIGNMENT (JSON -> JSON)
# ----------------------------------------------------------------------
class AlignmentStage:
    def __init__(self, id_builder: STCIDBuilder):
        self.id_builder = id_builder

    def simulate_ocr_errors(
        self, chars: List[Dict], error_rate: float = 0.1
    ) -> List[Dict]:
        """Introduce simulated OCR errors for alignment demonstration"""
        import random

        random.seed(42)

        ocr_chars = []
        substitutions = {
            "Đ": "D",
            "đ": "d",
            "ô": "o",
            "ơ": "o",
            "â": "a",
            "ă": "a",
            "ê": "e",
            "ư": "u",
            "í": "i",
            "á": "a",
            "ọ": "o",
        }

        for c in chars:
            char_val = c["char"]
            if char_val in substitutions and random.random() < error_rate:
                char_val = substitutions[char_val]
            ocr_chars.append({"char": char_val, "bbox": c["bbox"]})
        return ocr_chars

    def align_characters(self, ocr_chars: List[Dict], gt_text: str) -> List[Dict]:
        """Align OCR characters with ground-truth text using Levenshtein distance"""
        gt_filtered = [c for c in gt_text if c.strip()]
        ocr_vals = [c["char"] for c in ocr_chars]

        ops = Levenshtein.editops(ocr_vals, gt_filtered)

        ocr_to_gt = {i: i for i in range(min(len(ocr_vals), len(gt_filtered)))}
        for op in ops:
            op_type, src_pos, dest_pos = op
            if op_type == "replace":
                ocr_to_gt[src_pos] = dest_pos
            elif op_type == "delete":
                ocr_to_gt[src_pos] = -1

        aligned_chars = []
        for i, o_char in enumerate(ocr_chars):
            gt_pos = ocr_to_gt.get(i, -1)
            if gt_pos == -1 or gt_pos >= len(gt_filtered):
                aligned_chars.append(
                    {
                        "orig_char": o_char["char"],
                        "char": "",
                        "status": "red",
                        "bbox": o_char["bbox"],
                    }
                )
                continue

            gt_char = gt_filtered[gt_pos]
            ocr_char = o_char["char"]

            if ocr_char == gt_char:
                status = "black"
            else:
                s1_candidates = S1_SIMILARITY_VIET.get(ocr_char, {ocr_char: 1.0})
                status = "green" if gt_char in s1_candidates else "red"

            aligned_chars.append(
                {
                    "orig_char": ocr_char,
                    "char": gt_char,
                    "status": status,
                    "bbox": o_char["bbox"],
                }
            )

        return aligned_chars

    def run(self, input_json_path: Path, output_json_path: Path) -> List[Dict]:
        """
        Loads the extracted JSON, performs sentence/character-level alignment,
        and saves aligned results to an intermediate JSON file.
        """
        print(f"[Stage 2: Alignment] Aligning data from: {input_json_path}")
        with open(input_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        page_num = data["page_num"]
        lines = data["lines"]

        aligned_records = []

        for idx, line in enumerate(lines, start=1):
            stc_id = self.id_builder.generate(idx)
            gt_text = line["text"]
            gt_chars = line["chars"]

            # 1. Simulate OCR detection & recognition process
            ocr_chars = self.simulate_ocr_errors(gt_chars, error_rate=0.10)

            # 2. Perform M.E.D. Levenshtein alignment
            aligned_chars = self.align_characters(ocr_chars, gt_text)

            # 3. Calculate alignment confidence score
            correct_count = sum(
                1 for c in aligned_chars if c["status"] in ("black", "green")
            )
            confidence = correct_count / len(aligned_chars) if aligned_chars else 0.0

            aligned_records.append(
                {
                    "stc_id": stc_id,
                    "page_num": page_num,
                    "text": gt_text,
                    "confidence": confidence,
                    "chars": aligned_chars,
                }
            )

        # Save aligned data
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(aligned_records, f, ensure_ascii=False, indent=2)

        print(f"   Saved aligned JSON to: {output_json_path}")
        return aligned_records


# ----------------------------------------------------------------------
# STAGE 3: EXPORT (JSON -> XML & Excel)
# ----------------------------------------------------------------------
class ExportStage:
    def __init__(self, xml_title: str, author: str, language: str, era: str):
        self.xml_title = xml_title
        self.author = author
        self.language = language
        self.era = era

    def run(self, input_json_path: Path, output_xml_path: Path, output_xlsx_path: Path):
        """
        Reads aligned JSON and exports final XML and Excel documents.
        """
        print(f"[Stage 3: Export] Exporting aligned data from: {input_json_path}")
        with open(input_json_path, "r", encoding="utf-8") as f:
            aligned_records = json.load(f)

        # 1. Build XML Tree
        xml_root = ET.Element("DOC")
        metadata = ET.SubElement(xml_root, "METADATA")
        ET.SubElement(metadata, "TITLE").text = self.xml_title
        ET.SubElement(metadata, "AUTHOR").text = self.author
        ET.SubElement(metadata, "LANGUAGE").text = self.language
        ET.SubElement(metadata, "ERA").text = self.era

        body = ET.SubElement(xml_root, "BODY")

        # 2. Build Excel Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "BBox Alignment"
        ws.append(
            [
                "STC_ID",
                "Page",
                "OCR Char",
                "Corrected Char",
                "Status",
                "xmin",
                "ymin",
                "xmax",
                "ymax",
                "Confidence",
            ]
        )

        for record in aligned_records:
            stc_id = record["stc_id"]
            page_num = record["page_num"]
            text = record["text"]
            confidence = record["confidence"]
            chars = record["chars"]

            # Write to XML
            stc_node = ET.SubElement(body, "STC_ID", {"id": stc_id})
            ET.SubElement(stc_node, "TEXT").text = text
            bboxes_node = ET.SubElement(stc_node, "BBOXES")

            for char_info in chars:
                orig_c = char_info["orig_char"]
                corr_c = char_info["char"]
                status = char_info["status"]
                bbox = char_info["bbox"]

                # XML node
                ET.SubElement(
                    bboxes_node,
                    "BBOX",
                    {
                        "char": corr_c if corr_c else orig_c,
                        "orig_char": orig_c,
                        "status": status,
                        "xmin": f"{bbox[0]:.1f}",
                        "ymin": f"{bbox[1]:.1f}",
                        "xmax": f"{bbox[2]:.1f}",
                        "ymax": f"{bbox[3]:.1f}",
                    },
                )

                # Excel row
                ws.append(
                    [
                        stc_id,
                        page_num,
                        orig_c,
                        corr_c,
                        status,
                        round(bbox[0], 1),
                        round(bbox[1], 1),
                        round(bbox[2], 1),
                        round(bbox[3], 1),
                        round(confidence, 3),
                    ]
                )

        # Write XML file
        pretty_write_xml(xml_root, output_xml_path)
        # Write Excel file
        wb.save(output_xlsx_path)

        print(f"   Exported final XML: {output_xml_path}")
        print(f"   Exported final Excel: {output_xlsx_path}")


# ----------------------------------------------------------------------
# RUNNER
# ----------------------------------------------------------------------
def resolve_pdf_path() -> Path:
    pdf_dir = Path("pdf")
    for path in pdf_dir.glob("*.pdf"):
        if "Nam" in path.name and "ca" in path.name.lower():
            return path
    raise FileNotFoundError("Could not find the Đại Nam Quốc Sử Diễn Ca PDF in pdf/")


def main():
    print("=== MULTI-STAGE JSON PIPELINE RUNNER (HVB) ===")

    # 1. Resolve PDF path
    try:
        pdf_path = resolve_pdf_path()
    except FileNotFoundError as e:
        print(f"[Error] {e}")
        sys.exit(1)

    # Define folder structure
    intermediate_dir = Path("output/intermediate")
    output_dir = Path("output/hvb_003_stages")

    # Stage filenames
    extracted_json = intermediate_dir / "extracted_pages.json"
    aligned_json = intermediate_dir / "aligned_results.json"
    final_xml = output_dir / "hvb_003_ocr_alignment.xml"
    final_xlsx = output_dir / "hvb_003_ocr_alignment.xlsx"

    # Page setup
    page_num = 10

    # Builders
    id_builder = STCIDBuilder(
        domain="H", sub_domain="V", genre="B", file_num=3, chapter=1, page=page_num
    )

    # --- STAGE 1: EXTRACTION ---
    stage1 = ExtractionStage(pdf_path)
    stage1.run(page_num=page_num, output_json_path=extracted_json)

    # --- STAGE 2: ALIGNMENT ---
    stage2 = AlignmentStage(id_builder)
    stage2.run(input_json_path=extracted_json, output_json_path=aligned_json)

    # --- STAGE 3: EXPORT ---
    stage3 = ExportStage(
        xml_title="Đại Nam Quốc Sử Diễn Ca",
        author="Lê Ngô Cát và Phạm Đình Toái",
        language="Vietnamese (Monolingual)",
        era="Nhà Nguyễn (1949)",
    )
    stage3.run(
        input_json_path=aligned_json,
        output_xml_path=final_xml,
        output_xlsx_path=final_xlsx,
    )

    print("\n=== STAGE-BASED PIPELINE RUN COMPLETED ===")
    print(f"Intermediate JSONs: {intermediate_dir.resolve()}")
    print(f"Final Outputs: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
