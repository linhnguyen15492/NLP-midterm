import fitz  # pymupdf

doc = fitz.open("data\\raw\\An_Nam_Chi_Luoc.pdf")
text = ""

for page in doc:
    text += page.get_text()

with open("data\\raw\\raw.txt", "w", encoding="utf-8") as f:
    f.write(text)
