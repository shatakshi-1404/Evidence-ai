import math

from app.models.chunk import EMBEDDING_DIM
from app.services.embeddings import HashEmbedder, get_embedder


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_vectors_have_expected_size_and_unit_length():
    vector = HashEmbedder().embed_query("refund policy")
    assert len(vector) == EMBEDDING_DIM
    assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0, rel_tol=1e-9)


def test_embedding_is_deterministic():
    embedder = HashEmbedder()
    assert embedder.embed_query("same text") == embedder.embed_query("same text")


def test_related_text_scores_higher_than_unrelated():
    embedder = HashEmbedder()
    query = embedder.embed_query("how long do refunds take")
    related, unrelated = embedder.embed_documents(
        [
            "Refunds take five business days to arrive.",
            "The mitochondria is the powerhouse of the cell.",
        ]
    )
    assert cosine(query, related) > cosine(query, unrelated)


def test_empty_text_does_not_produce_nan():
    assert all(math.isfinite(x) for x in HashEmbedder().embed_query(""))


def test_factory_returns_hash_embedder_under_test():
    assert get_embedder().model_name == f"hash-{EMBEDDING_DIM}"
