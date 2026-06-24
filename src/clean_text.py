import re
from typing import List


def clean_vietnamese(text):

    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def clean_vietnamese_text(raw_text: str) -> str:
    """
    Hàm làm sạch văn bản trích xuất từ PDF:
    - Loại bỏ các dòng trống rác.
    - Chuẩn hóa khoảng trắng.
    - Loại bỏ các dòng chỉ là số trang hoặc số thứ tự.
    - Tách câu dựa trên dấu kết thúc câu.
    """
    # Làm sạch dòng và chuẩn hóa dấu câu
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

    cleaned_lines = []

    for line in lines:
        # Bỏ qua dòng chỉ là số trang hoặc số thứ tự
        if line.isdigit() or line.startswith("- ") and line[2:].strip().isdigit():
            continue

        if re.match(r"^-+\s*\d+\s*-+$", line):
            continue

        if re.match(r"^Trang\s+\d+$", line):
            continue

        cleaned_lines.append(line)

    text = " ".join(cleaned_lines)
    text = re.sub(r"\s+", " ", text)

    return text.strip()
