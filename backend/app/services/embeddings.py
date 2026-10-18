import hashlib
import math
import re
import threading
from typing import Protocol

from app.core.config import settings
from app.models.chunk import EMBEDDING_DIM

_TOKEN = re.compile(r"[^\W_]+")


class EmbeddingError(Exception):
    pass


class Embedder(Protocol):
    model_name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class HashEmbedder:
    """A deterministic stand-in: hashes each word into one of 384 buckets.

    It captures shared words, not real meaning. Used by the tests and for
    offline development (EMBEDDING_PROVIDER=hash). It is NOT for real use.
    """

    model_name = f"hash-{EMBEDDING_DIM}"

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        for token in _TOKEN.findall(text.lower()):
            digest = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
            vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            vector[0] = 1.0  # empty text still gets a valid unit vector
            return vector
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class SentenceTransformerEmbedder:
    """Real semantic embeddings. The model downloads on first use, then is cached."""

    def __init__(self, model_name: str, query_prefix: str, batch_size: int):
        self.model_name = model_name
        self._query_prefix = query_prefix
        self._batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self.model_name)
        return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,  # unit length, so cosine = dot product
            show_progress_bar=False,
        )
        result = [vector.tolist() for vector in vectors]
        if result and len(result[0]) != EMBEDDING_DIM:
            raise EmbeddingError(
                f"{self.model_name} produces {len(result[0])}-dimensional vectors; "
                f"the database expects {EMBEDDING_DIM}"
            )
        return result

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts) if texts else []

    def embed_query(self, text: str) -> list[float]:
        # bge models were trained to see this prefix on queries (not on documents).
        return self._encode([self._query_prefix + text])[0]


_embedders: dict[tuple[str, str], Embedder] = {}
_embedders_lock = threading.Lock()


def get_embedder() -> Embedder:
    """One shared instance per configuration, so the model loads only once."""
    key = (settings.embedding_provider, settings.embedding_model)
    with _embedders_lock:
        if key not in _embedders:
            if settings.embedding_provider == "hash":
                _embedders[key] = HashEmbedder()
            elif settings.embedding_provider == "sentence_transformers":
                _embedders[key] = SentenceTransformerEmbedder(
                    settings.embedding_model,
                    settings.embedding_query_prefix,
                    settings.embedding_batch_size,
                )
            else:
                raise ValueError(f"Unknown EMBEDDING_PROVIDER '{settings.embedding_provider}'")
        return _embedders[key]
