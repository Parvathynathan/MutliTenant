import ollama

from .config import EMBEDDING_MODEL


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [
        ollama.embeddings(model=EMBEDDING_MODEL, prompt=text)["embedding"]
        for text in texts
    ]