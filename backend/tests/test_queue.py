import time
import uuid

import fakeredis
import pytest

from app.services.queue import DELAYED_KEY, QUEUE_KEY, dequeue, enqueue_ingestion, promote_due


@pytest.fixture()
def r():
    return fakeredis.FakeRedis(decode_responses=True)


def test_jobs_come_out_in_the_order_they_went_in(r):
    ids = [uuid.uuid4() for _ in range(3)]
    for document_id in ids:
        enqueue_ingestion(document_id, client=r)
    assert [dequeue(r, timeout=1) for _ in ids] == ids


def test_empty_queue_returns_none(r):
    assert dequeue(r, timeout=1) is None


def test_delayed_job_is_held_back_until_due(r):
    document_id = uuid.uuid4()
    enqueue_ingestion(document_id, delay_seconds=60, client=r)
    assert promote_due(r) == 0
    assert r.llen(QUEUE_KEY) == 0
    assert r.zcard(DELAYED_KEY) == 1


def test_due_job_is_promoted_exactly_once(r):
    document_id = uuid.uuid4()
    enqueue_ingestion(document_id, delay_seconds=0.001, client=r)
    time.sleep(0.02)
    assert promote_due(r) == 1
    assert promote_due(r) == 0
    assert dequeue(r, timeout=1) == document_id
