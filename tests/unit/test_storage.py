from ragbench.core.models import (
    QueryExecutionRecord,
    QueryInteractionSource,
    RagExecutionStatus,
    SearchMode,
)
from ragbench.infrastructure.storage import JsonlExecutionStorage, SQLiteExecutionStorage


def test_sqlite_storage_checkpoint_and_resume(tmp_path):
    db_file = tmp_path / "test_checkpoint.sqlite3"
    storage = SQLiteExecutionStorage(db_file)

    rec1 = QueryExecutionRecord(
        index=0,
        query="Pergunta 1",
        response="Resposta 1",
        mode=SearchMode.HYBRID,
        status=RagExecutionStatus.SUCCESS,
        total_latency_seconds=1.23,
    )
    rec2 = QueryExecutionRecord(
        index=1,
        query="Pergunta 2",
        response=None,
        mode=SearchMode.HYBRID,
        status=RagExecutionStatus.ERROR,
        error_message="Timeout",
        total_latency_seconds=10.0,
    )

    storage.save_record(rec1)
    storage.save_record(rec2)

    completed = storage.get_completed_indices()
    # Apenas o rec1 foi bem sucedido
    assert 0 in completed
    assert 1 not in completed

    all_recs = storage.load_all_records()
    assert len(all_recs) == 2
    assert all_recs[0].query == "Pergunta 1"
    assert all_recs[1].error_message == "Timeout"


def test_jsonl_storage(tmp_path):
    log_file = tmp_path / "test_results.jsonl"
    storage = JsonlExecutionStorage(log_file)

    rec = QueryExecutionRecord(
        index=10,
        query="Pergunta JSONL",
        response="Resposta JSONL",
        source=QueryInteractionSource.SEMANTIC_CACHE,
        similarity_score=0.98,
    )
    storage.save_record(rec)

    records = storage.load_all_records()
    assert len(records) == 1
    assert records[0].index == 10
    assert records[0].similarity_score == 0.98
