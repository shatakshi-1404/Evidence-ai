from app.core.config import settings
from app.evaluation.dataset import load_corpus, load_questions, load_thresholds
from app.evaluation.metrics import has_evidence
from app.services.chunking import chunk_pages
from app.services.extraction import ExtractedPage, normalize_text


def test_dataset_is_well_formed():
    questions = load_questions()
    ids = [q.id for q in questions]
    assert len(ids) == len(set(ids)), "question ids must be unique"
    assert any(q.answerable for q in questions) and any(not q.answerable for q in questions)
    for q in questions:
        assert q.question.strip()
        if q.answerable:
            assert q.evidence, f"{q.id} is answerable but lists no evidence"
        else:
            assert not q.evidence, f"{q.id} is unanswerable but lists evidence"


def test_every_evidence_phrase_exists_in_the_corpus():
    corpus_text = " ".join(doc.text for doc in load_corpus())
    for q in load_questions():
        for phrase in q.evidence:
            assert has_evidence(corpus_text, [phrase]), f"{q.id}: '{phrase}' not found in the corpus"


def test_every_answerable_question_has_a_chunk_containing_its_evidence():
    """After real chunking (with overlap), at least one passage holds the whole phrase."""
    chunks = []
    for doc in load_corpus():
        page = ExtractedPage(None, normalize_text(doc.text))
        chunks += [c.text for c in chunk_pages([page], settings.chunk_size, settings.chunk_overlap)]
    for q in load_questions():
        if q.answerable:
            assert any(has_evidence(chunk, q.evidence) for chunk in chunks), (
                f"{q.id}: no single chunk contains its evidence; the phrase straddles a chunk boundary"
            )


def test_thresholds_file_uses_known_names():
    known = {"hybrid_hit_at_5", "hybrid_mrr", "answered_rate", "refusal_rate", "cited_evidence_rate"}
    assert set(load_thresholds()) <= known
