import hashlib
import math
import re

from app.core.config import settings

_model = None


def _hash_embed(text: str) -> list[float]:
    dim = settings.embedding_dim
    v = [0.0] * dim
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        v[h % dim] += 1.0 if (h >> 64) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed_texts(texts: list[str], is_query=False) -> list[list[float]]:
    if settings.embedding_backend == "st":
        global _model
        if _model is None:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(settings.embedding_model)
        if is_query:
            texts = ["Represent this sentence for searching relevant passages: " + t for t in texts]
        return _model.encode(texts, normalize_embeddings=True).tolist()
    return [_hash_embed(t) for t in texts]
