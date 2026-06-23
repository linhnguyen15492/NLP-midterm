# NLP-midterm

## Đề xuất giải pháp cho thư mục `pdf/`

Mục tiêu của bộ dữ liệu này là xây dựng ngữ liệu song song Hán - Việt chuyên ngành lịch sử Trung Quốc. Với các file hiện có trong `pdf/`, nên triển khai theo hướng pipeline 2 nhánh:

1. Nhánh `Text` cho PDF đã có text layer hoặc trích xuất được text khá sạch.
2. Nhánh `OCR` cho PDF scan, ảnh chụp, hoặc file có text layer nhưng chất lượng kém.

### 1) Phân loại các file trong `pdf/`

Từ kiểm tra nhanh cấu trúc PDF, có thể chia như sau:

- `An Nam Chí Nguyên.pdf`: PDF ảnh, cần OCR.
- `Đại Việt Lịch Triều Đăng Khoa Lục 1.pdf`: PDF ảnh, cần OCR.
- `An Nam Chí Lược.pdf`: có khả năng có text layer, nên thử trích text trước rồi mới OCR fallback.
- `Công Dư Tiệp Ký 1.pdf`: có text layer, phù hợp cho nhánh Text.
- `Đại Nam quốc sử diễn ca (Q1) - Lê Ngô Cát, Phạm Đình Toái.pdf`: có text layer + image, nên ưu tiên text extraction và chỉ OCR các trang hoặc vùng bị lỗi.

### 2) Luồng xử lý đề xuất

#### Nhánh OCR

- Render PDF ra ảnh 300-400 DPI.
- Chạy OCR theo trang, sau đó gom lại theo block/đoạn.
- Làm sạch kết quả: bỏ header/footer lặp, sửa lỗi dấu câu, chuẩn hóa khoảng trắng, nối từ bị ngắt dòng.
- Tách câu bằng rule + model dựa trên dấu câu, mẫu số trang, tiêu đề mục.

#### Nhánh Text

- Trích text trực tiếp từ PDF.
- Nếu tỷ lệ ký tự hợp lệ thấp hoặc mất nhiều dòng, chuyển sang OCR fallback.
- Tách câu theo đoạn và dấu câu.
- Chuẩn hóa Unicode, bỏ ký tự rác, gộp dòng bị wrap.

### 3) Dóng hàng Hán - Việt

Nên dùng 2 tầng:

- Tầng 1: dóng hàng theo cấu trúc tài liệu, ví dụ cùng trang, cùng chương, cùng tiêu đề, cùng số mục.
- Tầng 2: nếu cấu trúc không đủ, dùng aligner dựa trên độ tương đồng câu, độ dài câu và từ khóa Hán - Việt.

Khuyến nghị thuật toán:

- Cắt theo đoạn trước, rồi align câu trong từng đoạn.
- Dùng dynamic programming cho các trường hợp 1-1, 1-n, n-1.
- Gán điểm dựa trên độ dài, dấu câu, số token, và embedding song ngữ nếu có.

### 4) Quy tắc thực thi cho từng file

- `An Nam Chí Nguyên.pdf` và `Đại Việt Lịch Triều Đăng Khoa Lục 1.pdf`: OCR trước, sau đó mới tách câu và dò alignment.
- `Công Dư Tiệp Ký 1.pdf`, `Đại Nam quốc sử diễn ca (Q1) - Lê Ngô Cát, Phạm Đình Toái.pdf`, `An Nam Chí Lược.pdf`: trích text trước, kiểm tra chất lượng, OCR fallback khi cần.

### 5) Cấu trúc đầu ra khuyến nghị

- `output/raw_text/`: text thô theo trang.
- `output/clean_text/`: text đã chuẩn hóa.
- `output/sentences/`: câu đã tách.
- `output/alignment/`: cặp Hán - Việt đã dóng hàng.
- `output/logs/`: log lỗi OCR, trang lỗi, trang cần xem lại tay.

### 6) Tiêu chí kiểm tra chất lượng

- Tỷ lệ OCR đúng theo trang.
- Tỷ lệ câu được tách ổn định sau chuẩn hóa.
- Tỷ lệ alignment tự động và số cặp phải duyệt tay.
- Mức độ đầy đủ của metadata để truy vết nguồn.

### 7) Cách xây dựng corpus từ bộ tài liệu này

Tham khảo tinh thần của file `SinoNom_OCR_TransliterationAlignment.pdf`, nên xây corpus theo chuỗi bước sau:

1. Chuẩn bị dữ liệu gốc theo từng trang.
	- Mỗi file PDF được giữ nguyên làm nguồn chuẩn.
	- Tách theo trang để bảo toàn vị trí và cho phép truy vết lỗi.

2. Tạo lớp văn bản nguồn.
	- Với PDF text: trích text trực tiếp theo trang.
	- Với PDF scan: OCR từng trang, sau đó hậu xử lý để loại ký tự rác, header/footer, xuống dòng giả.

3. Tách đoạn và tách câu.
	- Tách đoạn trước, rồi mới tách câu để giảm lỗi do dòng bị ngắt.
	- Giữ lại `doc_id`, `page_id`, `segment_id`, `sentence_id` để phục vụ alignment.

4. Chuẩn hóa transliteration và dị thể chữ.
	- Chuẩn hóa Unicode, dấu câu, khoảng trắng, số trang, ký hiệu mục.
	- Nếu có nhiều biến thể Hán tự/Hán Nôm cùng một từ, cần quy ước một dạng chuẩn.

5. Dóng hàng song song Hán - Việt.
	- Ưu tiên alignment theo cấu trúc sẵn có như chương, mục, tiểu mục, hoặc chú giải.
	- Khi cấu trúc không đủ, align theo câu bằng độ dài, từ khóa, và ngữ cảnh lân cận.
	- Cho phép các trường hợp 1-1, 1-n, n-1, không ép mọi dòng phải khớp tuyệt đối.

6. Gắn nhãn và kiểm tra thủ công.
	- Các cặp có độ tin cậy thấp cần đưa vào hàng chờ kiểm tra tay.
	- Lưu log các trang lỗi OCR, câu không dò được, và các đoạn thiếu đối ứng.

7. Xuất corpus theo định dạng thống nhất.
	- Nên dùng JSONL hoặc TSV có các trường tối thiểu: `doc_id`, `page_id`, `segment_id`, `source_text`, `target_text`, `alignment_type`, `confidence`.
	- Tách riêng bản thô, bản đã làm sạch, và bản đã alignment để dễ lặp lại pipeline.

### 8) Đề xuất cấu trúc thư mục corpus

- `corpus/source/`: văn bản nguồn theo trang.
- `corpus/normalized/`: văn bản đã chuẩn hóa và tách câu.
- `corpus/alignment/`: dữ liệu song song đã dóng hàng.
- `corpus/review/`: các đoạn cần kiểm tra thủ công.
- `corpus/meta/`: metadata của từng tài liệu, trang, và trạng thái xử lý.

### 9) Chạy mẫu 4 bước

Mẫu hiện tại trong `main.py` đã làm sẵn 4 bước:

1. Trích text từ PDF.
2. Tách đơn vị câu/đoạn và gắn nhãn `C`/`V`.
3. Dóng hàng theo trang.
4. Xuất XML và Excel.

Ví dụ chạy:

```bash
uv run python main.py --pdf "pdf/An Nam Chí Lược.pdf" --page-start 1 --page-end 3 --output-dir output/sample_text
uv run python main.py --pdf "pdf/Công Dư Tiệp Ký 1.pdf" --page-start 121 --page-end 121 --output-dir output/sample_cvk
```

Lưu ý: `An Nam Chí Lược` là mẫu text layer thuần Việt để kiểm tra bước trích text và tách câu; còn `Công Dư Tiệp Ký 1` có trang chứa cả Hán và Việt, phù hợp để xem phần dóng hàng C/V.

Nếu cần, bước tiếp theo là mình có thể dựng luôn một bộ script xử lý cho thư mục `pdf/` theo đúng pipeline này.
