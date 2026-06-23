from extract_pdf import extract_text
from clean_text import clean_vietnamese
from sentence_split import split_vietnamese

text = extract_text("data\\raw\\An_Nam_Chi_Luoc.pdf")

cleaned_text = clean_vietnamese(text)

sentences = split_vietnamese(cleaned_text)

print("Number of sentences:", len(sentences))
print("First 5 sentences:")
for i in range(min(5, len(sentences))):
    print(f"{i + 1}: {sentences[i]}")
