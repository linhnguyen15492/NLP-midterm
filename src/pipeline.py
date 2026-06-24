from extract_pdf import extract_text
from clean_text import *
from sentence_split import *

path = "data/raw/An_Nam_Chi_Luoc.pdf"

raw_text = extract_text(path)

clean_text = clean_vietnamese_text(raw_text)

sentences = split_vietnamese_sentences(clean_text)

for i in range(len(sentences)):
    print(f"{i + 1}: {sentences[i]}")
