"""Save / Sync 파이프라인.

/slotmachine:save — git add+commit+push 후 GraphDB 증분 업데이트
/slotmachine:sync — git pull 후 GraphDB 증분 업데이트

두 파이프라인 모두 main 브랜치에 직접 push/pull하는 단순 플로우를 전제로 한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import git

from slotmachine.sync.embedding import BaseEmbeddingProvider
from slotmachine.sync.git_manager import GitManager
from slotmachine.sync.graphdb import GraphDB
from slotmachine.sync.incremental_sync import IncrementalSyncResult, incremental_sync

logger = logging.getLogger(__name__)


@dataclass
class SaveResult:
    """save 파이프라인 실행 결과."""

    commit_hash: str | None = None
    sync_result: IncrementalSyncResult = field(default_factory=IncrementalSyncResult)
    nothing_to_commit: bool = False
    error: str | None = None

    @property
    def success(self) -> bool:
        """에러 없이 완료됐으면 True."""
        return self.error is None


@dataclass
class LiveSyncResult:
    """sync 파이프라인 실행 결과."""

    previous_head: str | None = None
    new_head: str | None = None
    sync_result: IncrementalSyncResult = field(default_factory=IncrementalSyncResult)
    nothing_to_sync: bool = False
    error: str | None = None

    @property
    def success(self) -> bool:
        """에러 없이 완료됐으면 True."""
        return self.error is None


def save(
    vault_path: Path,
    db: GraphDB,
    *,
    embedding_provider: BaseEmbeddingProvider | None = None,
    commit_message: str | None = None,
    remote: str = "origin",
    branch: str = "main",
    para_folder_map: dict[str, str] | None = None,
    inbox_folder: str = "INBOX",
) -> SaveResult:
    """vault 변경사항을 git push하고 GraphDB를 증분 업데이트한다.

    플로우: git add → commit → push → diff → incremental_sync

    Args:
        vault_path: Obsidian vault 루트 경로 (git repo와 동일)
        db: 초기화된 GraphDB 인스턴스
        embedding_provider: 임베딩 프로바이더 (None이면 임베딩 생략)
        commit_message: 커밋 메시지 (None이면 자동 생성)
        remote: 원격 저장소 이름
        branch: 대상 브랜치 이름
    Returns:
        SaveResult
    """
    result = SaveResult()
    try:
        git_mgr = GitManager(vault_path)
        old_head = git_mgr.current_head()

        staged = git_mgr.add_all()
        if not staged:
            logger.info("Save: 변경사항 없음 — 커밋 생략")
            result.nothing_to_commit = True
            return result

        message = commit_message or git_mgr.generate_commit_message(staged)
        result.commit_hash = git_mgr.commit(message)
        git_mgr.push(remote, branch)

        diff = git_mgr.diff_files(old_head, result.commit_hash)
        result.sync_result = incremental_sync(
            diff, vault_path, db,
            embedding_provider=embedding_provider,
            para_folder_map=para_folder_map,
            inbox_folder=inbox_folder,
        )

        db.upsert_sync_meta(result.commit_hash)

    except git.GitCommandError as exc:
        result.error = f"Git 오류: {exc}"
        logger.error("Save 실패 (Git): %s", exc)
    except Exception as exc:
        result.error = str(exc)
        logger.error("Save 실패: %s", exc)

    return result


def live_sync(
    vault_path: Path,
    db: GraphDB,
    *,
    embedding_provider: BaseEmbeddingProvider | None = None,
    remote: str = "origin",
    branch: str = "main",
    para_folder_map: dict[str, str] | None = None,
    inbox_folder: str = "INBOX",
) -> LiveSyncResult:
    """원격 변경사항을 pull하고 GraphDB를 증분 업데이트한다.

    플로우: git pull → diff (pull 전후 HEAD 비교) → incremental_sync

    Args:
        vault_path: Obsidian vault 루트 경로
        db: 초기화된 GraphDB 인스턴스
        embedding_provider: 임베딩 프로바이더 (None이면 임베딩 생략)
        remote: 원격 저장소 이름
        branch: 대상 브랜치 이름
    Returns:
        LiveSyncResult
    """
    result = LiveSyncResult()
    try:
        git_mgr = GitManager(vault_path)
        result.previous_head = git_mgr.current_head()

        result.new_head = git_mgr.pull(remote, branch)

        if result.previous_head == result.new_head:
            logger.info("Sync: 원격에 새 변경사항 없음")
            result.nothing_to_sync = True
            return result

        if result.new_head is None:
            logger.warning("Sync: pull 후 HEAD가 None — 빈 저장소")
            result.nothing_to_sync = True
            return result

        diff = git_mgr.diff_files(result.previous_head, result.new_head)
        result.sync_result = incremental_sync(
            diff, vault_path, db,
            embedding_provider=embedding_provider,
            para_folder_map=para_folder_map,
            inbox_folder=inbox_folder,
        )

        db.upsert_sync_meta(result.new_head)

    except git.GitCommandError as exc:
        result.error = f"Git 오류: {exc}"
        logger.error("Sync 실패 (Git): %s", exc)
    except Exception as exc:
        result.error = str(exc)
        logger.error("Sync 실패: %s", exc)

    return result
