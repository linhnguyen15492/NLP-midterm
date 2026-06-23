import re


def clean_vietnamese(text):

    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()
