import json
import sqlite3
from pathlib import Path

from ragbench.core.interfaces import BaseExecutionStorage
from ragbench.core.models import (
    QueryExecutionRecord,
    QueryInteractionSource,
    RagExecutionStatus,
    SearchMode,
)


class SQLiteExecutionStorage(BaseExecutionStorage):
    """Armazenamento transacional baseado em SQLite com suporte a checkpoints atômicos."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_records (
                    query_index INTEGER PRIMARY KEY,
                    query TEXT NOT NULL,
                    response TEXT,
                    mode TEXT NOT NULL,
                    top_k INTEGER NOT NULL,
                    model TEXT,
                    source TEXT NOT NULL,
                    similarity_score REAL,
                    total_latency_seconds REAL,
                    rag_retrieval_latency_seconds REAL,
                    ttft_seconds REAL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    timestamp REAL NOT NULL,
                    datetime_str TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_record(self, record: QueryExecutionRecord) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO execution_records (
                    query_index, query, response, mode, top_k, model, source,
                    similarity_score, total_latency_seconds, rag_retrieval_latency_seconds,
                    ttft_seconds, status, error_message, timestamp, datetime_str
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record.index,
                    record.query,
                    record.response,
                    record.mode.value if isinstance(record.mode, SearchMode) else str(record.mode),
                    record.top_k,
                    record.model,
                    record.source.value
                    if isinstance(record.source, QueryInteractionSource)
                    else str(record.source),
                    record.similarity_score,
                    record.total_latency_seconds,
                    record.rag_retrieval_latency_seconds,
                    record.ttft_seconds,
                    record.status.value
                    if isinstance(record.status, RagExecutionStatus)
                    else str(record.status),
                    record.error_message,
                    record.timestamp,
                    record.datetime_str,
                ),
            )
            conn.commit()

    def get_completed_indices(self) -> set[int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT query_index FROM execution_records WHERE status = 'success'")
            rows = cursor.fetchall()
            return {row[0] for row in rows}

    def load_all_records(self) -> list[QueryExecutionRecord]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM execution_records ORDER BY query_index ASC")
            rows = cursor.fetchall()

            records = []
            for row in rows:
                rec_dict = dict(row)
                rec_dict["index"] = rec_dict.pop("query_index")
                records.append(QueryExecutionRecord(**rec_dict))
            return records


class JsonlExecutionStorage(BaseExecutionStorage):
    """Armazenamento baseado em arquivo JSONL com append-only."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def save_record(self, record: QueryExecutionRecord) -> None:
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")

    def get_completed_indices(self) -> set[int]:
        if not self.file_path.exists():
            return set()

        completed = set()
        with open(self.file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("status") == "success":
                        completed.add(data.get("index"))
                except json.JSONDecodeError:
                    continue
        return completed

    def load_all_records(self) -> list[QueryExecutionRecord]:
        if not self.file_path.exists():
            return []

        records = []
        with open(self.file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    records.append(QueryExecutionRecord(**data))
                except json.JSONDecodeError:
                    continue
        return records
