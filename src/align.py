from sentence_transformers import SentenceTransformer

model = SentenceTransformer("sentence-transformers/LaBSE")


def encode(sentences):
    return model.encode(sentences, convert_to_tensor=True)
