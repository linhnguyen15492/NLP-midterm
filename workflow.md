# Workflow: PDF (text/image) -> Raw JSON -> Alignment -> XML

Tài liệu này ghi lại quy trình khuyến nghị để xây dựng ngữ liệu theo yêu cầu trong:

- `requirements/MidTerm_Requirement_full.pdf` (yêu cầu chung/riêng, output XML, thẻ metadata, ví dụ C/V).
- `SinoNom_OCR_TransliterationAlignment.pdf` (quy ước ID dạng `DSG_fff.ccc.ppp.ss` và hướng dẫn dóng hàng).
- Mẫu XML tham chiếu trực tiếp trong repo: `data/Sample_format/Han_sample.xml`, `data/Sample_format/HanViet_sample.xml`, `data/Sample_format/Viet_sample.xml`.

Mục tiêu của workflow:

1. Extract ngữ liệu thô từ PDF (PDF có text layer và PDF scan chỉ có ảnh).
2. Lưu *ngữ liệu thô* ra JSON (để debug, tái chạy, và tách bạch extract vs align).
3. Chỉ sau đó mới chạy alignment/annotation.
4. Cuối cùng export XML theo đúng cấu trúc mẫu (`<root><FILE>...`) và quy ước ID.

---

## 1) Quy ước thư mục (khuyến nghị)

Giữ nguyên `data/raw/` làm nơi chứa đầu vào, và thêm các thư mục trung gian:

- `data/raw/`: PDF đầu vào.
- `data/interim/raw_json/`: JSON thô sau extract (một file JSON cho một PDF).
- `data/interim/page_images/`: ảnh render theo trang (phục vụ OCR/debug).
- `data/interim/alignment/`: JSON sau khi split câu + dóng hàng.
- `output/xml/`: XML đầu ra cuối.

Lý do: tách rõ “extract” và “align/export” để dễ kiểm lỗi và không phải OCR lại từ đầu.

---

## 2) Chuẩn ID và cấu trúc XML cần bám

### 2.1. Cấu trúc XML (bám theo file mẫu trong `data/Sample_format/`)

Mẫu chung:

```xml
<root>
  <FILE ID="PKS_001">
    <meta>
      <TITLE>...</TITLE>
      <VOLUME>...</VOLUME>
      <AUTHOR>...</AUTHOR>
      <PERIOD>...</PERIOD>
      <LANGUAGE>Hán-Việt|Hán|Việt</LANGUAGE>
      <TRANSLATOR>...</TRANSLATOR> <!-- nếu có -->
      <SOURCE>...</SOURCE>
    </meta>
    <SECT ID="PKS_001.001" NAME="...">
      <PAGE ID="PKS_001.001.001">
        <STC ID="PKS_001.001.001.01">
          <C>...</C> <!-- nếu song ngữ -->
          <V>...</V> <!-- nếu song ngữ -->
        </STC>
      </PAGE>
    </SECT>
  </FILE>
</root>
```

Trong `MidTerm_Requirement_full.pdf` có nhắc output XML phải chứa metadata và mỗi câu/cặp câu có ID, với song ngữ Hán–Việt dùng tag ngôn ngữ `<C>...</C><V>...</V>`.

### 2.2. Quy ước ID theo `SinoNom_OCR_TransliterationAlignment.pdf`

Tài liệu hướng dẫn nêu ID dạng:

`DSG_fff.ccc.ppp.ss`

- `D` (Domain), `S` (Sub-domain), `G` (Genre) là 3 trường đầu.
- `fff`: số hiệu file ngữ liệu thô trong lĩnh vực con đó.
- `ccc`: chapter/section (tập/chương/hồi/đoạn…).
- `ppp`: page (trang đối với PDF ảnh; hoặc đoạn/paragraph đối với txt).
- `ss`: số sentence hoặc số box trong page đó.

Ghi chú quan trọng:

- Tài liệu cũng nhắc “14 ký tự”: thực tế trong mẫu XML của repo, ID có dấu phân tách (`_` và `.`). Khi implement nên validate theo *pattern* (cấu trúc trường) + uniqueness, thay vì chỉ kiểm đúng 14 ký tự thô.
- Nhóm giảng viên sẽ cung cấp phần mã gốc kiểu `DSG_fff`/`PKS_001` cho từng tác phẩm. Các phần còn lại nhóm tự đánh số nhất quán.

---

## 3) Pipeline đề xuất (từng bước)

### Bước 0: Chuẩn bị metadata + mapping ID gốc

1. Chốt `FILE_ID` do giảng viên cấp (ví dụ `PKS_001` hoặc `DSG_fff`).
2. Chuẩn bị metadata tối thiểu theo mẫu: `TITLE, VOLUME, AUTHOR, PERIOD, LANGUAGE, (TRANSLATOR), SOURCE`.
3. Xác định cách chia `SECT` (chapter/section) và `PAGE`:
   - PDF scan: `PAGE` thường map theo trang PDF.
   - PDF text/txt: `PAGE` có thể map theo paragraph/đoạn.

Khuyến nghị lưu metadata riêng (để reuse):

`data/metadata/<FILE_ID>.json`

```json
{
  "file_id": "PKS_001",
  "title": "Dai hoc",
  "volume": "Tu thu",
  "author": "Tang Tu",
  "period": "Chien Quoc",
  "language": "Han-Viet",
  "translator": "Tran Trong Sam",
  "source": "ctext.org"
}
```

### Bước 1: Extract “raw” từ PDF -> JSON thô (không alignment)

Mục tiêu: lấy được tối đa thông tin *nguyên bản* theo trang, gồm:

- Nếu PDF có text layer: danh sách text blocks + bbox.
- Nếu PDF là ảnh scan: render trang ra ảnh + OCR + bbox (word/line/char tuỳ OCR tool).
- Luôn lưu ảnh trang render để debug (dù PDF có text layer, vẫn hữu ích khi cần đối chiếu).

Output: `data/interim/raw_json/<stem>.raw.json`

Schema JSON thô (gợi ý, đủ để làm downstream):

```json
{
  "source_pdf": "data/raw/An_Nam_Chi_Luoc.pdf",
  "file_id": "PKS_001",
  "pages": [
    {
      "page": 1,
      "render_image": "data/interim/page_images/An_Nam_Chi_Luoc/p001.png",
      "has_text_layer": true,
      "text_blocks": [
        { "bbox": [x0, y0, x1, y1], "text": "..." }
      ],
      "ocr": {
        "engine": "tesseract",
        "lang": "vie",
        "words": [
          { "bbox": [x0, y0, x1, y1], "text": "...", "conf": 87 }
        ]
      }
    }
  ]
}
```

### Bước 2: Chuẩn hoá + split câu từ JSON thô -> sentences JSON

Mục tiêu: chuyển raw text (từ text layer hoặc từ OCR) thành danh sách câu có:

- `stc_id` dự kiến (chưa cần có `<C>/<V>`).
- `page`, `order`, `text`, `lang` (nếu là song ngữ cần detect `C`/`V`).
- Tham chiếu ngược về bbox (nếu có) để truy xuất lại vùng ảnh.

Output: `data/interim/alignment/<stem>.sentences.json`

### Bước 3: Alignment / annotation (từ sentences JSON)

Tuỳ loại ngữ liệu:

1. Song ngữ Hán–Việt:
   - Tách câu Hán và câu Việt (detect lang hoặc theo cấu trúc nguồn).
   - Dóng hàng bằng embedding (ví dụ LaBSE trong `sentence-transformers`) hoặc dictionary-based như gợi ý trong tài liệu.
   - Cho phép m-n (không ép 1-1 nếu data thực tế lệch).

2. Đơn ngữ ảnh (Hán hoặc Việt):
   - OCR cho ra bbox + text (word/char).
   - Dóng hàng “bbox <-> ký tự/chuỗi OCR” theo thứ tự đọc (văn bản Hán Nôm dạng dọc cần sort bbox theo cột/phải->trái, trên->dưới).

Output: `data/interim/alignment/<stem>.align.json`

### Bước 4: Export XML (từ align.json + metadata)

- Dựng đúng tree `<root>/<FILE>/<meta>/<SECT>/<PAGE>/<STC>`.
- Với song ngữ: mỗi `<STC>` chứa `<C>` và `<V>`.
- Với đơn ngữ: `<STC>` có thể rỗng trong mẫu, nhưng thực tế bài làm nên điền nội dung theo yêu cầu (tuỳ task: OCR text, NER tags, ...).
- Lưu file: `output/xml/<FILE_ID>.xml`.

---

## 4) Code mẫu (runnable trong repo) cho bước Extract -> Raw JSON

Ghi chú:

- Repo đã cài `pymupdf` (import `fitz`), `pytesseract`, `Pillow` trong `.venv`.
- `pytesseract` cần binary Tesseract cài trên máy + cấu hình PATH. Nếu không có, có thể thay OCR engine bằng API/PaddleOCR (repo có dependency `paddlepaddle`).

Ví dụ code (extract text layer, fallback OCR theo trang, lưu JSON thô):

```python
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image
import pytesseract


@dataclass
class TextBlock:
    bbox: list[float]  # [x0, y0, x1, y1]
    text: str


def render_page_png(page: fitz.Page, out_path: Path, dpi: int = 200) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    pix.save(out_path.as_posix())


def extract_text_blocks(page: fitz.Page) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    for b in page.get_text("blocks"):
        # block: (x0, y0, x1, y1, "text", block_no, block_type)
        if len(b) < 7:
            continue
        x0, y0, x1, y1, text, _, block_type = b
        if block_type != 0:
            continue
        t = (text or "").strip()
        if not t:
            continue
        blocks.append(TextBlock(bbox=[float(x0), float(y0), float(x1), float(y1)], text=t))
    return blocks


def ocr_words_from_png(png_path: Path, lang: str) -> list[dict[str, Any]]:
    img = Image.open(png_path)
    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
    words: list[dict[str, Any]] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        conf = float(data["conf"][i]) if str(data["conf"][i]).strip() not in {"-1", ""} else None
        words.append(
            {
                "bbox": [float(x), float(y), float(x + w), float(y + h)],
                "text": text,
                "conf": conf,
            }
        )
    return words


def extract_pdf_to_raw_json(
    pdf_path: Path,
    out_json: Path,
    out_img_dir: Path,
    *,
    file_id: str,
    ocr_lang: str = "vie",
    max_pages: int | None = None,
) -> None:
    doc = fitz.open(pdf_path)
    payload: dict[str, Any] = {"source_pdf": str(pdf_path), "file_id": file_id, "pages": []}

    for page_idx in range(doc.page_count):
        page_no = page_idx + 1
        if max_pages is not None and page_no > max_pages:
            break

        page = doc.load_page(page_idx)
        img_path = out_img_dir / pdf_path.stem / f"p{page_no:03d}.png"
        render_page_png(page, img_path)

        blocks = extract_text_blocks(page)
        has_text_layer = len(blocks) > 0

        ocr = None
        if not has_text_layer:
            # PDF scan: chạy OCR trên ảnh render
            words = ocr_words_from_png(img_path, lang=ocr_lang)
            ocr = {"engine": "tesseract", "lang": ocr_lang, "words": words}

        payload["pages"].append(
            {
                "page": page_no,
                "render_image": str(img_path),
                "has_text_layer": has_text_layer,
                "text_blocks": [asdict(b) for b in blocks],
                "ocr": ocr,
            }
        )

    doc.close()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    extract_pdf_to_raw_json(
        pdf_path=Path("data/raw/An_Nam_Chi_Luoc.pdf"),
        out_json=Path("data/interim/raw_json/An_Nam_Chi_Luoc.raw.json"),
        out_img_dir=Path("data/interim/page_images"),
        file_id="PKS_001",  # thay bằng FILE_ID giảng viên cấp
        ocr_lang="vie",
        max_pages=3,
    )
```

Điểm then chốt của bước này:

- Không split câu / không align ở bước extract.
- JSON thô luôn lưu lại đủ thông tin để “replay” downstream mà không đọc PDF lại.

---

## 5) Code mẫu export XML theo format mẫu

Ví dụ export song ngữ (bám mẫu `data/Sample_format/HanViet_sample.xml`):

```python
from __future__ import annotations

from pathlib import Path
from lxml import etree


def export_hanviet_xml(
    out_path: Path,
    *,
    file_id: str,
    meta: dict,
    sect_id: str,
    sect_name: str,
    page_id: str,
    pairs: list[dict],  # [{ "stc_id": "...", "c": "...", "v": "..." }, ...]
) -> None:
    root = etree.Element("root")
    file_el = etree.SubElement(root, "FILE", ID=file_id)

    meta_el = etree.SubElement(file_el, "meta")
    for tag in ["TITLE", "VOLUME", "AUTHOR", "PERIOD", "LANGUAGE", "TRANSLATOR", "SOURCE"]:
        if tag == "TRANSLATOR" and not meta.get("translator"):
            continue
        child = etree.SubElement(meta_el, tag)
        key = tag.lower()
        if tag == "TRANSLATOR":
            child.text = meta.get("translator", "")
        else:
            child.text = meta.get(key, "")

    sect_el = etree.SubElement(file_el, "SECT", ID=sect_id, NAME=sect_name)
    page_el = etree.SubElement(sect_el, "PAGE", ID=page_id)

    for p in pairs:
        stc_el = etree.SubElement(page_el, "STC", ID=p["stc_id"])
        c_el = etree.SubElement(stc_el, "C")
        c_el.text = p.get("c", "")
        v_el = etree.SubElement(stc_el, "V")
        v_el.text = p.get("v", "")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(
        etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding="utf-8",
        )
    )
```

Khuyến nghị:

- Dùng `lxml` để pretty print và kiểm soát encoding UTF-8.
- Việc sinh `sect_id/page_id/stc_id` nên đi qua 1 hàm duy nhất để đảm bảo format thống nhất.

---

## 6) Checklist kiểm tra trước khi nộp

1. XML well-formed, UTF-8, đúng cấu trúc giống mẫu.
2. `FILE/@ID`, `SECT/@ID`, `PAGE/@ID`, `STC/@ID` unique và nhất quán.
3. Song ngữ Hán–Việt: mỗi `<STC>` có đủ `<C>` và `<V>`.
4. Có metadata tối thiểu: `TITLE/AUTHOR/LANGUAGE/PERIOD/SOURCE` (theo mẫu).
5. Lưu lại JSON thô + JSON alignment để khi bị lỗi có thể trace ngược đến page/bbox.

