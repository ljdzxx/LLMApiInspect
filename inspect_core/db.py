from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS probe_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id TEXT NOT NULL,
    target_title TEXT NOT NULL,
    target_subtitle TEXT NOT NULL,
    protocol TEXT NOT NULL,
    model TEXT NOT NULL,
    started_at_ms INTEGER NOT NULL,
    started_at_iso TEXT NOT NULL,
    bucket_start_ms INTEGER NOT NULL,
    first_token_at_ms INTEGER,
    latency_ms INTEGER,
    success INTEGER NOT NULL,
    http_status INTEGER,
    error TEXT,
    response_preview TEXT
);

CREATE INDEX IF NOT EXISTS idx_probe_results_target_bucket
ON probe_results (target_id, bucket_start_ms);

CREATE INDEX IF NOT EXISTS idx_probe_results_started_at
ON probe_results (started_at_ms);
"""


def init_db(database_path: str) -> None:
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect(database_path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(database_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_probe_result(database_path: str, result: dict) -> None:
    with connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO probe_results (
                target_id,
                target_title,
                target_subtitle,
                protocol,
                model,
                started_at_ms,
                started_at_iso,
                bucket_start_ms,
                first_token_at_ms,
                latency_ms,
                success,
                http_status,
                error,
                response_preview
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["target_id"],
                result["target_title"],
                result["target_subtitle"],
                result["protocol"],
                result["model"],
                result["started_at_ms"],
                result["started_at_iso"],
                result["bucket_start_ms"],
                result.get("first_token_at_ms"),
                result.get("latency_ms"),
                1 if result["success"] else 0,
                result.get("http_status"),
                result.get("error"),
                result.get("response_preview"),
            ),
        )


def fetch_results(database_path: str, start_ms: int, end_ms: int) -> list[sqlite3.Row]:
    with connect(database_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM probe_results
            WHERE bucket_start_ms >= ? AND bucket_start_ms <= ?
            ORDER BY bucket_start_ms ASC, id ASC
            """,
            (start_ms, end_ms),
        ).fetchall()
    return list(rows)


def fetch_latest_results(database_path: str, limit: int = 20) -> list[sqlite3.Row]:
    with connect(database_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM probe_results
            ORDER BY started_at_ms DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return list(rows)
