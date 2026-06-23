# Walkthrough: Đồ Án Giữa Kỳ NLP - Dự án số 3 (Đề tài HVB)

Chúng ta đã thiết lập và chạy thành công pipeline xử lý cho **Dự án số 3** thuộc đề tài **HVB** cho cả hai định dạng đầu vào: **Ảnh Scan** và **Văn bản (Text PDF)**.

---

## 1. Tác vụ 3 (Đầu vào Ảnh Scan): Bbox và Căn chỉnh ký tự
Được thiết lập tại tệp [run_midterm_pipeline.py](file:///d:/workspace/NLP-midterm/run_midterm_pipeline.py), sử dụng tệp tài liệu lịch sử [Đại Nam quốc sử diễn ca (Q1) - Lê Ngô Cát, Phạm Đình Toái.pdf](file:///d:/workspace/NLP-midterm/pdf/Đại Nam quốc sử diễn ca (Q1) - Lê Ngô Cát, Phạm Đình Toái.pdf) làm tệp nguồn `HVB_003`.

- **Phương pháp**: Trích xuất tọa độ BBox chi tiết của từng ký tự dùng `page.get_text("rawdict")` từ PyMuPDF đóng vai trò là OCR Engine thu nhận tọa độ.
- **Giải thuật**: Nhóm các ký tự thành từng dòng độc lập, mô phỏng lỗi nhận diện OCR (10%) và chạy dóng hàng tối ưu Levenshtein (M.E.D) kết hợp với **Từ điển Tương đồng S1** để tự động sửa lỗi và dán nhãn trạng thái (`black`, `green`, `red`).
- **Kết quả đầu ra**: Lưu tại thư mục [output/hvb_003](file:///d:/workspace/NLP-midterm/output/hvb_003/):
  - XML: [hvb_003_ocr_alignment.xml](file:///d:/workspace/NLP-midterm/output/hvb_003/hvb_003_ocr_alignment.xml)
  - Excel: [hvb_003_ocr_alignment.xlsx](file:///d:/workspace/NLP-midterm/output/hvb_003/hvb_003_ocr_alignment.xlsx)

---

## 2. Tác vụ 1 (Đầu vào Text PDF): Tách câu & Dóng hàng song ngữ
Được thiết lập riêng tại tệp [run_text_bilingual_pipeline.py](file:///d:/workspace/NLP-midterm/run_text_bilingual_pipeline.py), sử dụng tệp tài liệu song ngữ [Công Dư Tiệp Ký 1.pdf](file:///d:/workspace/NLP-midterm/pdf/Công Dư Tiệp Ký 1.pdf) (Trang 121) làm nguồn dữ liệu.

- **Phương pháp**:
  1. Trích xuất text layer trực tiếp của trang 121 bằng PyMuPDF.
  2. Thực hiện tách câu chuyên sâu (Sentence Segmentation) làm sạch dòng thừa, khoảng trắng và phân tách theo các dấu kết thúc câu (`. ! ? ;`).
  3. Phân loại ngôn ngữ của từng câu (Hán ngữ `C` vs Quốc ngữ `V`) dựa trên tập hợp ký tự Unicode.
  4. Thuật toán dóng hàng song ngữ (Bilingual Alignment) dựa trên từ điển **Sino-Viet Dictionary** so khớp Jaccard Similarity và thuật toán đối sánh tham lam (Greedy index alignment làm dự phòng).
- **Kết quả đầu ra**: Lưu tại thư mục [output/hvb_003_text](file:///d:/workspace/NLP-midterm/output/hvb_003_text/):
  - XML: [hvb_003_text_alignment.xml](file:///d:/workspace/NLP-midterm/output/hvb_003_text/hvb_003_text_alignment.xml)
  - Excel: [hvb_003_text_alignment.xlsx](file:///d:/workspace/NLP-midterm/output/hvb_003_text/hvb_003_text_alignment.xlsx)

---

## 3. Cách chạy các script

1. **Chạy tác vụ Ảnh Scan (Task 3)**:
   ```bash
   uv run python run_midterm_pipeline.py
   ```
2. **Chạy tác vụ Text PDF (Task 1)**:
   ```bash
   uv run python run_text_bilingual_pipeline.py
   ```
 Cả hai script đều chạy độc lập, trích xuất dữ liệu thực tế từ file PDF tương ứng và ghi đầy đủ kết quả đầu ra XML, Excel.
