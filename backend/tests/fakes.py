import uuid

from app.services.retrieval import Candidate


def make_candidate(
    n: int = 1,
    content: str | None = None,
    similarity: float | None = 0.8,
    filename: str = "policy.pdf",
    page: int | None = 1,
    **kwargs,
) -> Candidate:
    return Candidate(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename=filename,
        page_number=page,
        chunk_index=n - 1,
        content=content or f"Passage number {n} about refunds.",
        similarity=similarity,
        **kwargs,
    )


class FakeRetriever:
    """Returns canned passages and records how it was called."""

    def __init__(self, candidates: list[Candidate] | None = None):
        self.candidates = candidates or []
        self.calls: list[dict] = []

    def retrieve(self, *, owner_id, query, collection_id=None, top_k=6):
        self.calls.append(
            {"owner_id": owner_id, "query": query, "collection_id": collection_id, "top_k": top_k}
        )
        return list(self.candidates)[:top_k]


class FakeLLM:
    """`reply` is a string, or a function of the passages. `error` is raised if set."""

    name = "fake"

    def __init__(self, reply="", error: Exception | None = None):
        self.reply = reply
        self.error = error
        self.calls: list[tuple] = []

    def answer(self, question, passages):
        self.calls.append((question, list(passages)))
        if self.error:
            raise self.error
        return self.reply(passages) if callable(self.reply) else self.reply
