# Hướng Dẫn Thực Hiện Đồ Án Giữa Kỳ NLP: Số hóa & Dóng hàng văn bản Hán Nôm

Tài liệu này phân tích chi tiết các yêu cầu trong thư mục `requirements/` và cung cấp giải pháp kỹ thuật, giải thuật chi tiết cùng code mẫu Python hoàn chỉnh cho từng tác vụ của đồ án giữa kỳ.

---

## 1. Phân Tích Yêu Cầu Chung (General Requirements)

Theo tài liệu [MidTerm_Requirement.pdf](file:///d:/workspace/NLP-midterm/requirements/MidTerm_Requirement.pdf):

1. **Tính tự động hóa cao**: Tất cả các bước xử lý (OCR, tiền xử lý, dóng hàng, gán nhãn NER) nên được đóng gói thành pipeline tự động. Đây là tiêu chí đánh giá quan trọng.
2. **Định dạng đầu ra kép**:
   - **File XML**: Lưu trữ cấu trúc phân cấp, siêu dữ liệu (metadata) và thẻ ngôn ngữ/NER. Mỗi câu phải được gán mã định danh duy nhất `STC_ID` gồm 14 ký tự.
   - **File Excel**: Giúp giảng viên dễ dàng kiểm tra trực quan chéo kết quả dóng hàng và tính toán xác suất.
3. **Mã định danh câu `STC_ID` (14 ký tự)**:
   - Cấu trúc: `DSG_fff.ccc.ppp.ss`
   - Giải nghĩa chi tiết từ trái qua phải:
     - **`D` (Domain - Lĩnh vực, 1 ký tự)**: Ví dụ: `L` (Văn học), `H` (Lịch sử), `R` (Tôn giáo), `M` (Y học), ...
     - **`S` (Sub-domain - Lĩnh vực con, 1 ký tự)**: Ví dụ trong tôn giáo `R` có `RB` (Phật giáo), `RC` (Thiên Chúa giáo).
     - **`G` (Genre - Thể loại, 1 ký tự)**: Quy định Hán/Nôm, thơ/văn xuôi, khắc in/viết tay, ...
     - **`fff` (File number - Số hiệu file, 3 ký tự)**: Mã số tài liệu thô do giảng viên cung cấp (ví dụ: `023`).
     - **`ccc` (Chapter number - Số chương/tập/hồi, 3 ký tự)**: Ví dụ `001` cho chương 1.
     - **`ppp` (Page number - Số trang, 3 ký tự)**: Số trang của chương đó.
     - **`ss` (Sentence number - Số thứ tự câu/box, 2 ký tự)**: Thứ tự câu trong trang.
     - *Ví dụ hoàn chỉnh*: `LBA_023.001.012.04` chỉ câu thứ 4, trang 12, chương 1, của tác phẩm văn học số 23.

---

## 2. Giải Thích Thuật Toán & Phương Pháp Giải Quyết

### A. Sắp xếp Bounding Boxes (Dọc, Phải sang Trái - Right-to-Left, Top-to-Bottom)
Văn bản cổ Hán Nôm được viết theo cột dọc từ trên xuống dưới, và đọc các cột từ phải sang trái. Các thư viện OCR hiện đại (như PaddleOCR) thường trả về các box theo thứ tự đọc ngang từ trái sang phải, trên xuống dưới. Chúng ta cần viết thuật toán sắp xếp lại các box theo chuẩn cổ:
1. Gom các bounding boxes có tọa độ X gần nhau (overlap theo phương ngang) vào cùng một cột dọc.
2. Sắp xếp các cột dọc theo thứ tự X giảm dần (từ phải sang trái).
3. Trong mỗi cột dọc, sắp xếp các box theo thứ tự Y tăng dần (từ trên xuống dưới).

### B. Dóng hàng Ký tự (Character Alignment) bằng M.E.D (Minimum Edit Distance) & Từ điển
Khi thực hiện OCR chữ Hán Nôm và so sánh với bản dịch âm Quốc ngữ tương ứng, chất lượng ảnh có thể gây ra sai sót OCR. Theo hướng dẫn trong [SinoNom_OCR_TransliterationAlignment.pdf](file:///d:/workspace/NLP-midterm/SinoNom_OCR_TransliterationAlignment.pdf), chúng ta áp dụng giải thuật đối sánh ký tự:
- **Ký tự OCR cần kiểm tra**: $sn$ (Sino-Nom)
- **Từ Quốc ngữ tương ứng**: $qn$ (Quốc ngữ)
- **Từ điển sử dụng**:
  - $S1(sn)$: Tập các ký tự có hình dáng tương đồng với $sn$ (Tra cứu từ `SinoNom_Similar.dic`).
  - $S2(qn)$: Tập các chữ Hán Nôm khả dĩ dịch/phiên âm từ chữ $qn$ (Tra cứu từ `QuocNgu_SinoNom.dic`).
- **Luật kiểm tra chéo (Intersection)**:
  - Nếu $sn \in S2$: OCR đúng $\rightarrow$ Giữ nguyên chữ đen.
  - Nếu $sn \notin S2$: Tìm tập giao $S = S1 \cap S2$:
    - **Trường hợp a ($|S| == 1$)**: OCR nhận diện sai nhưng tìm được đúng 1 ký tự sửa lỗi phù hợp. Cập nhật ký tự này và đánh dấu màu xanh lá.
    - **Trường hợp b ($|S| > 1$)**: Tìm thấy nhiều ứng viên. Chọn ký tự có độ tương đồng hình dáng cao nhất với $sn$ trong $S1$. Đánh dấu màu xanh lá.
    - **Trường hợp c ($|S| == 0$)**: Không tìm thấy ứng viên khớp âm. Đánh dấu màu đỏ (lỗi OCR không thể tự sửa).

### C. Dóng hàng Câu Dịch Nghĩa Hán - Việt (Task 1)
Có 3 phương pháp chính:
1. **Dictionary-based**: Tra từ điển Hán-Việt để lấy tập nghĩa của câu Hán, so khớp từ vựng với câu Việt thông qua độ đo Jaccard hoặc tỉ lệ giao.
2. **Translation Similarity**: Dịch câu Hán sang tiếng Việt thông qua API dịch thuật (ví dụ Google Translate, Gemini API, ...) rồi so sánh độ tương đồng từ vựng (BLEU, ROUGE) hoặc khoảng cách chỉnh sửa giữa câu dịch và câu Việt đích.
3. **Multilingual Sentence Embeddings**: Sử dụng các mô hình Transformer đa ngôn ngữ (như `LaBSE`, `minilm-l12-v2`) để encode câu Hán và câu Việt thành các vector ngữ nghĩa, sau đó tính toán Cosine Similarity để ghép cặp (áp dụng thuật toán Gale-Church hoặc Needleman-Wunsch).

### D. Nhận dạng Thực thể có liên kết (NER - Tasks 4 & 5)
Cần nhận diện ít nhất 6 thực thể: `PER` (Tên người), `LOC` (Địa điểm), `ORG` (Tổ chức), `TITLE` (Chức danh/Tước hiệu), `TME` (Thời gian), `NUM` (Con số).
- **Với tiếng Việt**: Dùng thư viện `underthesea`, `vncorenlp`, hoặc fine-tune một mô hình BERT tiếng Việt (`phobert-base-v2-ner`).
- **Với tiếng Hán**: Dùng thư viện `spaCy` (mô hình `zh_core_web_sm`/`md`) hoặc các mô hình NER Hán ngữ cổ chuyên dụng trên Hugging Face.

---

## 3. Code Mẫu Chi Tiết Cho 5 Tác Vụ & Thuật Toán Bổ Trợ

Dưới đây là mã nguồn Python đầy đủ, được module hóa rõ ràng cho từng phần.

### Mã Nguồn Hỗ trợ: Định dạng Xuất XML & Excel
Đầu tiên, định nghĩa cấu trúc dữ liệu và các hàm sinh mã `STC_ID` cùng với hàm xuất XML/Excel dùng chung.

```python
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from openpyxl import Workbook
from dataclasses import dataclass
from typing import List, Dict, Tuple, Set

@dataclass
class STCIDBuilder:
    domain: str        # L (Literature), H (History)...
    sub_domain: str    # B (Buddhism), A (General)...
    genre: str         # G, V, etc.
    file_num: int      # fff (e.g. 23)
    chapter: int       # ccc (e.g. 1)
    page: int          # ppp (e.g. 12)
    
    def generate(self, sentence_idx: int) -> str:
        """Sinh mã STC_ID 14 ký tự: DSG_fff.ccc.ppp.ss"""
        dsg = f"{self.domain}{self.sub_domain}{self.genre}"
        return f"{dsg}_{self.file_num:03d}.{self.chapter:03d}.{self.page:03d}.{sentence_idx:02d}"

def pretty_write_xml(root: ET.Element, filepath: str):
    """Ghi file XML có format thụt lề đẹp mắt"""
    raw_str = ET.tostring(root, 'utf-8')
    parsed = minidom.parseString(raw_str)
    pretty_str = parsed.toprettyxml(indent="  ")
    # Loại bỏ dòng trống thừa do xml.dom sinh ra khi format
    pretty_str = "\n".join([line for line in pretty_str.splitlines() if line.strip()])
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(pretty_str)
```

---

### Tác Vụ 1: Dóng Hàng Dịch Nghĩa Song Ngữ Hán - Việt (Bilingual Alignment)
Minh họa cách dùng từ điển từ vựng để tính điểm Jaccard Similarity nhằm dóng hàng câu Hán và câu Việt tương ứng.

```python
# Giả lập từ điển Hán-Việt đơn giản cho dóng hàng
DICT_HAN_VIET = {
    "南": ["nam", "phương nam"],
    "國": ["quốc", "nước", "quốc gia"],
    "山": ["sơn", "núi"],
    "河": ["hà", "sông"],
    "帝": ["đế", "vua", "hoàng đế"],
    "居": ["cư", "ở", "nơi ở"]
}

def translate_han_words(han_sentence: str) -> Set[str]:
    """Tra nghĩa tiếng Việt của các chữ Hán trong câu"""
    translated_meanings = set()
    for char in han_sentence:
        if char in DICT_HAN_VIET:
            translated_meanings.update(DICT_HAN_VIET[char])
    return translated_meanings

def align_bilingual_sentences(
    c_sentences: List[str], 
    v_sentences: List[str], 
    id_builder: STCIDBuilder
) -> Tuple[List[Dict], Workbook]:
    """
    Dóng hàng câu Hán-Việt dựa trên độ tương đồng từ vựng (Jaccard).
    Xuất ra cấu trúc XML và Excel.
    """
    alignments = []
    
    # Ở đây giả định dóng hàng 1-1 tối ưu theo độ tương đồng nghĩa
    # Trong thực tế, có thể sử dụng giải thuật dynamic programming (Gale-Church) hoặc Vector Similarity
    for idx, c_sen in enumerate(c_sentences):
        c_meanings = translate_han_words(c_sen)
        best_match_idx = -1
        best_score = -1.0
        
        for v_idx, v_sen in enumerate(v_sentences):
            # Tokenize đơn giản bằng cách lowercase và tách từ
            v_words = set(v_sen.lower().split())
            intersection = c_meanings.intersection(v_words)
            union = c_meanings.union(v_words)
            jaccard = len(intersection) / len(union) if union else 0.0
            
            if jaccard > best_score:
                best_score = jaccard
                best_match_idx = v_idx
                
        if best_match_idx != -1 and best_score > 0.05:
            stc_id = id_builder.generate(idx + 1)
            alignments.append({
                "stc_id": stc_id,
                "C": c_sen,
                "V": v_sentences[best_match_idx],
                "score": best_score
            })
            
    # Tạo cây XML đầu ra theo quy chuẩn
    xml_root = ET.Element("DOC")
    metadata = ET.SubElement(xml_root, "METADATA")
    ET.SubElement(metadata, "TITLE").text = "Nam Quốc Sơn Hà"
    ET.SubElement(metadata, "LANGUAGE").text = "Hán-Việt"
    
    body = ET.SubElement(xml_root, "BODY")
    for align in alignments:
        # Sử dụng thuộc tính 'id' hợp lệ trong XML để lưu STC_ID
        stc_node = ET.SubElement(body, "STC_ID", {"id": align["stc_id"]})
        ET.SubElement(stc_node, "C").text = align["C"]
        ET.SubElement(stc_node, "V").text = align["V"]
        ET.SubElement(stc_node, "CONFIDENCE").text = f"{align['score']:.3f}"
        
    # Tạo bảng Excel đầu ra
    wb = Workbook()
    ws = wb.active
    ws.title = "Bilingual Alignment"
    ws.append(["STC_ID", "Chinese (C)", "Vietnamese (V)", "Confidence Score"])
    for align in alignments:
        ws.append([align["stc_id"], align["C"], align["V"], round(align["score"], 3)])
        
    return alignments, xml_root, wb

# Chạy thử nghiệm Task 1
if __name__ == "__main__":
    builder = STCIDBuilder(domain="L", sub_domain="B", genre="A", file_num=23, chapter=1, page=12)
    c_sents = ["南國山河", "南國山河南帝居"]
    v_sents = ["Sông núi nước Nam", "Sông núi nước Nam vua Nam ở"]
    
    alignments, xml_tree, excel_wb = align_bilingual_sentences(c_sents, v_sents, builder)
    print("Dóng hàng thành công cặp Hán-Việt:")
    for al in alignments:
        print(f"[{al['stc_id']}] C: {al['C']} <-> V: {al['V']} (Score: {al['score']:.2f})")
```

---

### Tác Vụ 2 & 3: OCR Đơn Ngữ Hán/Việt (Bbox Sorting & Char-Level Alignment)
Code dưới đây giải quyết bài toán:
1. **Sắp xếp Bboxes** từ phải qua trái, từ trên xuống dưới cho văn bản cột dọc.
2. **Dóng hàng ký tự** (Char alignment) dựa trên Levenshtein (M.E.D) kết hợp từ điển hình dáng chữ tương đồng ($S1$) và từ điển phiên âm Hán-Nôm ($S2$).

```python
# Giả lập từ điển hình dáng tương đồng S1 (SinoNom_Similar.dic)
# Cấu trúc: { ký tự gốc: { ký tự tương đồng: độ tương đồng } }
S1_SIMILARITY = {
    "榥": {"榥": 1.0, "釈": 0.8, "椩": 0.7, "棅": 0.75, "稂": 0.6, "佒": 0.5},
    "山": {"山": 1.0, "仙": 0.5, "彡": 0.4},
}

# Giả lập từ điển phiên âm Hán Nôm S2 (QuocNgu_SinoNom.dic)
# Cấu trúc: { chữ quốc ngữ: [tập hợp các chữ Hán Nôm tương ứng] }
S2_TRANSLATIONS = {
    "trăm": ["百", "佰", "榥", "林"],
    "sơn": ["山", "珊", "衫"],
}

@dataclass
class BBox:
    char: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float

def sort_bboxes_ancient_style(bboxes: List[BBox], col_threshold: float = 30.0) -> List[BBox]:
    """
    Sắp xếp các bounding boxes chữ cột dọc: Phải sang trái (X giảm dần), trên xuống dưới (Y tăng dần).
    col_threshold: khoảng cách tối đa theo trục X để gom các box vào cùng một cột.
    """
    if not bboxes:
        return []
    
    # 1. Gom các box vào từng cột dựa trên tọa độ trung tâm X (X_center)
    columns: List[List[BBox]] = []
    
    # Sắp xếp tạm theo X_center giảm dần (từ phải sang trái) để dễ gom nhóm
    sorted_by_x = sorted(bboxes, key=lambda b: (b.x_min + b.x_max) / 2.0, reverse=True)
    
    for box in sorted_by_x:
        box_x_center = (box.x_min + box.x_max) / 2.0
        placed = False
        # Kiểm tra xem box này có thuộc cột nào đã tạo hay không
        for col in columns:
            col_x_center = sum((b.x_min + b.x_max) / 2.0 for b in col) / len(col)
            if abs(box_x_center - col_x_center) < col_threshold:
                col.append(box)
                placed = True
                break
        if not placed:
            columns.append([box])
            
    # 2. Sắp xếp lại:
    # - Các cột được sắp xếp từ phải sang trái (X_center cột giảm dần)
    # - Trong mỗi cột, các box được sắp xếp từ trên xuống dưới (Y_min tăng dần)
    sorted_bboxes = []
    columns.sort(key=lambda col: sum((b.x_min + b.x_max) / 2.0 for b in col) / len(col), reverse=True)
    
    for col in columns:
        col.sort(key=lambda b: b.y_min)
        sorted_bboxes.extend(col)
        
    return sorted_bboxes

def align_and_verify_characters(
    ocr_chars: List[str], 
    quoc_ngu_words: List[str]
) -> List[Tuple[str, str, str]]:
    """
    Dóng hàng ký tự Hán Nôm với Quốc Ngữ và sửa lỗi OCR.
    Trả về danh sách Tuple: (Ký tự gốc, Ký tự đã sửa đổi, Trạng thái màu sắc)
    Trạng thái màu: 'black' (đúng), 'green' (đã sửa lỗi), 'red' (lỗi không định danh)
    """
    aligned_results = []
    
    # Dóng hàng 1-1 giữa chuỗi OCR chữ Hán Nôm và chữ Quốc ngữ (bằng M.E.D hoặc độ dài tương đương)
    # Ở đây mô phỏng đối sánh từng cặp ký tự tương ứng theo vị trí
    for i in range(min(len(ocr_chars), len(quoc_ngu_words))):
        sn = ocr_chars[i]
        qn = quoc_ngu_words[i]
        
        # Lấy tập hợp S1 và S2
        s1_set = S1_SIMILARITY.get(sn, {sn: 1.0})
        s2_list = S2_TRANSLATIONS.get(qn, [])
        
        # Nếu chữ OCR có trong danh sách dịch của từ Quốc ngữ -> OCR ĐÚNG
        if sn in s2_list:
            aligned_results.append((sn, sn, "black"))
        else:
            # Tra phần giao S = S1 giao S2
            s_intersection = set(s1_set.keys()).intersection(set(s2_list))
            
            if len(s_intersection) == 1:
                # Trường hợp a: Giao bằng 1 chữ -> Lấy chữ đó làm kết quả đúng (màu xanh)
                corrected_char = list(s_intersection)[0]
                aligned_results.append((sn, corrected_char, "green"))
            elif len(s_intersection) > 1:
                # Trường hợp b: Giao nhiều hơn 1 chữ -> Lấy chữ có độ tương đồng hình dáng cao nhất trong S1
                best_char = max(s_intersection, key=lambda c: s1_set.get(c, 0.0))
                aligned_results.append((sn, best_char, "green"))
            else:
                # Trường hợp c: Giao bằng rỗng -> Lỗi không xác định (màu đỏ)
                aligned_results.append((sn, sn, "red"))
                
    return aligned_results

# Chạy thử nghiệm Task 2 & 3
if __name__ == "__main__":
    # 1. Thử nghiệm sắp xếp BBox dọc
    raw_boxes = [
        BBox("山", x_min=200, y_min=50, x_max=240, y_max=90), # Cột 1 (bên phải), hàng 2
        BBox("南", x_min=202, y_min=10, x_max=242, y_max=45), # Cột 1 (bên phải), hàng 1
        BBox("國", x_min=100, y_min=12, x_max=138, y_max=48), # Cột 2 (bên trái), hàng 1
    ]
    sorted_boxes = sort_bboxes_ancient_style(raw_boxes)
    print("\nThứ tự BBoxes sau khi sắp xếp cổ điển:")
    for b in sorted_boxes:
        print(f"Chữ: {b.char} | X_range: [{b.x_min}, {b.x_max}] | Y_range: [{b.y_min}, {b.y_max}]")
        
    # 2. Thử nghiệm đối sánh chéo sửa lỗi OCR
    # Giả sử chữ OCR bị nhận diện sai '榥' thành chữ khác hoặc ngược lại, từ tương ứng là 'trăm'
    ocr_result = ["榥"]
    target_qn = ["trăm"]
    results = align_and_verify_characters(ocr_result, target_qn)
    print("\nKết quả dóng hàng và sửa lỗi OCR:")
    for orig, corr, color in results:
        print(f"OCR gốc: '{orig}' -> Đã sửa: '{corr}' | Trạng thái hiển thị: {color.upper()}")
```

---

### Tác Vụ 4 & 5: Gán Nhãn Thực Thể (Named Entity Recognition - NER) Cho Chữ Hán/Việt
Dưới đây là phương pháp sử dụng mô hình học máy (thông qua thư viện Transformers hoặc RegEx/Dictionary) để gán nhãn thực thể và kết xuất XML lồng thẻ.

```python
# Giả lập một pipeline NER đơn giản bằng Quy tắc/Từ điển cho Hán & Việt cổ
# Trong thực tế học máy: dùng `pipeline("ner", model="...")` của Hugging Face
NER_DICTIONARY = {
    "Lý Thái Tổ": "PER",
    "Lý Công Uẩn": "PER",
    "Thăng Long": "LOC",
    "Hà Nội": "LOC",
    "Nhà Lý": "ORG",
    "1010": "TME",
    "vua": "TITLE",
    "hoàng đế": "TITLE",
    "ba": "NUM",
    "hai mươi": "NUM"
}

def extract_entities_regex(text: str) -> List[Dict]:
    """Trích xuất thực thể từ văn bản dựa trên từ điển"""
    entities = []
    # Tìm kiếm các cụm từ khớp trong từ điển
    for entity_text, label in NER_DICTIONARY.items():
        for match in re.finditer(re.escape(entity_text), text):
            entities.append({
                "start": match.start(),
                "end": match.end(),
                "text": entity_text,
                "label": label
            })
    # Loại bỏ các thực thể bị chồng lấn (lấy thực thể dài hơn)
    entities.sort(key=lambda e: e["start"])
    clean_entities = []
    last_end = -1
    for ent in entities:
        if ent["start"] >= last_end:
            clean_entities.append(ent)
            last_end = ent["end"]
    return clean_entities

def export_ner_to_xml(
    sentence: str, 
    stc_id: str, 
    id_builder: STCIDBuilder
) -> ET.Element:
    """
    Gán nhãn NER lồng trong XML.
    Ví dụ: Vào năm <TME>1010</TME>, vua <PER><TITLE>Lý Thái Tổ</TITLE></PER> dời đô...
    """
    entities = extract_entities_regex(sentence)
    
    # Xây dựng cấu trúc XML lồng
    stc_node = ET.Element("STC_ID", {"id": stc_id})
    
    # Để chèn text xen kẽ thẻ XML con, chúng ta thao tác trực tiếp trên cây
    # XML Element có thuộc tính .text (chữ trước thẻ con thứ nhất) và .tail (chữ sau thẻ con)
    last_idx = 0
    current_parent = stc_node
    
    for ent in entities:
        # Thêm phần text tĩnh trước thực thể
        prefix = sentence[last_idx:ent["start"]]
        if last_idx == 0:
            stc_node.text = prefix
        else:
            # Gán tail cho subelement trước đó
            if len(stc_node) > 0:
                stc_node[-1].tail = prefix
                
        # Tạo thẻ thực thể con
        ent_node = ET.SubElement(stc_node, ent["label"])
        ent_node.text = ent["text"]
        
        last_idx = ent["end"]
        
    # Thêm phần text còn lại cuối câu
    suffix = sentence[last_idx:]
    if len(stc_node) > 0:
        stc_node[-1].tail = suffix
    else:
        stc_node.text = suffix
        
    return stc_node

# Chạy thử nghiệm Task 4 & 5
if __name__ == "__main__":
    test_sentence = "Vào năm 1010, vua Lý Thái Tổ dời đô về Thăng Long."
    builder = STCIDBuilder(domain="H", sub_domain="B", genre="A", file_num=1, chapter=1, page=1)
    stc_id = builder.generate(1)
    
    xml_node = export_ner_to_xml(test_sentence, stc_id, builder)
    
    # Print XML dạng chuỗi đẹp mắt
    raw_str = ET.tostring(xml_node, 'utf-8')
    parsed = minidom.parseString(raw_str)
    print("\nKết quả XML NER lồng thẻ:")
    print(parsed.toprettyxml(indent="  "))
```

---

## 4. Kế Hoạch Đánh Giá & Kiểm Thử (Evaluation Plan)

Để đảm bảo kết quả số hóa đạt độ chính xác cao nhất như giảng viên yêu cầu tại mục **A.5**:

1. **Đánh giá tự động (Automated Evaluation)**:
   - **Tỉ lệ dóng hàng câu (Sentence Alignment Accuracy)**: Đo bằng số cặp dóng đúng trên tập dữ liệu vàng (golden dataset) chia cho tổng số câu trong golden dataset.
   - **Độ chính xác OCR ký tự (Character Error Rate - CER)**: Đo lường khoảng cách chỉnh sửa giữa chuỗi OCR đã qua dóng hàng ký tự ($S1 \cap S2$) với chuỗi chữ Hán chuẩn mực trong golden dataset.
   - **Độ chính xác NER (F1-score)**: Tính toán Precision, Recall và F1-score trên tập thực thể đã được giảng viên gán nhãn sẵn.
2. **Đánh giá thủ công (Manual Verification)**:
   - Sử dụng các file Excel kết xuất để rà soát chéo nhanh các cặp câu có điểm Confidence dưới ngưỡng $0.7$.
   - Lọc các ký tự được gán trạng thái màu đỏ (`red`) trong quá trình dóng hàng ký tự để hiệu chỉnh thủ công bằng mắt.
