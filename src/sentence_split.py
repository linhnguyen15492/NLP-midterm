from underthesea import sent_tokenize


def split_vietnamese_sentences(cleaned_text: str):
    sentences = sent_tokenize(cleaned_text)

    return [s.strip() for s in sentences if len(s.strip()) > 2]
