"""Sync 이력 로그 모듈.

sqlite3를 사용해 save/sync 작업 이력을 로컬에 저장한다.
기본 저장 경로: vault/.slotmachine/sync_history.db
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from slotmachine.sync.incremental_sync import IncrementalSyncResult

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sync_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    operation     TEXT    NOT NULL,
    added         INTEGER NOT NULL DEFAULT 0,
    modified      INTEGER NOT NULL DEFAULT 0,
    deleted       INTEGER NOT NULL DEFAULT 0,
    failed        INTEGER NOT NULL DEFAULT 0,
    commit_hash   TEXT,
    error_summary TEXT
)
"""


@dataclass
class SyncRecord:
    """단일 sync 이력 레코드."""

    id: int
    timestamp: datetime
    operation: str
    added: int
    modified: int
    deleted: int
    failed: int
    commit_hash: str | None
    error_summary: str | None


class SyncHistory:
    """sqlite3 기반 Sync 이력 관리자."""

    def __init__(self, db_path: Path) -> None:
        """SyncHistory를 초기화하고 테이블을 생성한다.

        Args:
            db_path: sqlite3 데이터베이스 파일 경로 (부모 디렉토리가 없으면 자동 생성)
        """
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE)
        logger.debug("SyncHistory 초기화: %s", db_path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def record(
        self,
        operation: str,
        result: IncrementalSyncResult,
        *,
        commit_hash: str | None = None,
    ) -> None:
        """sync 결과를 이력에 기록한다.

        Args:
            operation: 작업 유형 ("save" | "sync")
            result: 증분 동기화 결과
            commit_hash: 관련 commit hash (save 시 사용)
        """
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        error_summary = (
            "; ".join(f"{p.name}: {msg}" for p, msg in result.errors[:5])
            if result.errors
            else None
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_history
                    (timestamp, operation, added, modified, deleted, failed, commit_hash, error_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    operation,
                    result.added,
                    result.modified,
                    result.deleted,
                    result.failed,
                    commit_hash,
                    error_summary,
                ),
            )
        logger.debug(
            "이력 기록: %s (add=%d mod=%d del=%d fail=%d)",
            operation, result.added, result.modified, result.deleted, result.failed,
        )

    def recent(self, limit: int = 10) -> list[SyncRecord]:
        """최근 sync 이력을 최신 순으로 반환한다.

        Args:
            limit: 반환할 최대 레코드 수
        Returns:
            최신 순 SyncRecord 목록
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, timestamp, operation, added, modified, deleted, failed, commit_hash, error_summary
                FROM sync_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            SyncRecord(
                id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                operation=row[2],
                added=row[3],
                modified=row[4],
                deleted=row[5],
                failed=row[6],
                commit_hash=row[7],
                error_summary=row[8],
            )
            for row in rows
        ]

    def clear(self) -> int:
        """모든 이력을 삭제한다.

        Returns:
            삭제된 레코드 수
        """
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM sync_history")
            return cursor.rowcount
