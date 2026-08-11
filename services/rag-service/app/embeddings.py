import hashlib
import math
import re
from typing import Iterable, List

try:
    from langchain_core.embeddings import Embeddings
except Exception:  # pragma: no cover - keeps local unit tests light if deps are absent
    class Embeddings:  # type: ignore[no-redef]
        pass


TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


class LocalHashEmbeddings(Embeddings):
    """Small deterministic embedding model for demos without an API key."""

    dimensions = 64

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self.dimensions
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            weight = 1.0 + min(len(token), 12) / 12.0
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 8) for value in vector]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:
        return [self._embed(text) for text in texts]


def create_embedding_model(provider: str, openai_api_key: str):
    if provider == "openai" and openai_api_key:
        from langchain_openai import OpenAIEmbeddings

        model = OpenAIEmbeddings(model="text-embedding-3-small", api_key=openai_api_key)
        model.dimensions = 1536
        return model

    return LocalHashEmbeddings()


def embedding_dimensions(model) -> int:
    return int(getattr(model, "dimensions", LocalHashEmbeddings.dimensions))


def cosine_similarity(left: List[float], right: List[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot / (left_norm * right_norm)

