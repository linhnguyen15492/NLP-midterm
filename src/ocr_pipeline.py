import json
from pathlib import Path
from typing import Any
from paddleocr import PaddleOCR


def run_ocr_pipeline(
    manifest_path: Path,
    out_manifest_path: Path,
    lang: str = "ch",
) -> None:
    """
    Đọc manifest từ step trước, tiến hành OCR từng trang bằng PaddleOCR,
    và cập nhật kết quả vào trường 'ocr' của manifest.

    lang="ch": Dùng model OCR cho tiếng Trung.
    """
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Không tìm thấy manifest tại: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Khởi tạo PaddleOCR
    # use_angle_cls=True giúp tự động xoay chữ nếu trang bị ngược/nghiêng
    print("--- Đang khởi tạo PaddleOCR Engine ---")
    ocr_engine = PaddleOCR(use_angle_cls=True, lang=lang)

    print(f"--- Bắt đầu OCR cho {len(manifest['pages'])} trang ---")
    for page_entry in manifest["pages"]:
        page_no = page_entry["page"]
        img_path = page_entry["page_png"]

        if not Path(img_path).exists():
            print(f"[Warning] Không tìm thấy file ảnh cho trang {page_no}: {img_path}")
            continue

        print(f"Đang xử lý Trang {page_no:04d}...")

        # Chạy OCR
        # Kết quả trả về là một list chứa các bounding box và text tương ứng
        result = ocr_engine.ocr(img_path)

        ocr_blocks = []
        full_text_lines = []

        # PaddleOCR có thể trả về None nếu trang trắng hoặc không detect được gì
        if result and result[0]:
            for line in result[0]:
                bbox = line[0]  # Toạ độ 4 góc: [[x0, y0], [x1, y1], [x2, y2], [x3, y3]]
                text, score = line[1]  # Nội dung text và độ tự tin (confidence score)

                full_text_lines.append(text)
                ocr_blocks.append(
                    {"bbox": bbox, "text": text, "confidence": float(score)}
                )

        # Cập nhật thông tin OCR vào cấu trúc cấu trúc dữ liệu của bạn
        page_entry["ocr"] = {
            "engine": "PaddleOCR",
            "full_text": "\n".join(full_text_lines),
            "blocks": ocr_blocks,
        }
        if len(full_text_lines) > 0:
            page_entry["has_text_layer"] = True

    # Lưu lại manifest mới đã có đầy đủ dữ liệu OCR
    out_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"--- Hoàn thành! Đã xuất manifest tích hợp OCR tại: {out_manifest_path} ---")


# --- Cách tích hợp vào luồng chạy của bạn ---
if __name__ == "__main__":
    # Giả sử bạn đã chạy hàm extract_page_images của bạn và lưu ra file `raw_manifest.json`
    raw_json = Path("data\\interim\\sino\\An_Nam_Chi_Nguyen_sino\\raw_manifest.json")
    ocr_json = Path("data\\interim\\sino\\An_Nam_Chi_Nguyen_sino\\ocr_manifest.json")

    # Chạy OCR pipeline
    run_ocr_pipeline(manifest_path=raw_json, out_manifest_path=ocr_json)
