"""Git 연동 모듈 — GitManager.

gitpython을 사용해 Obsidian vault의 git 작업을 처리한다.
push/pull 실패 시 tenacity로 최대 3회 자동 재시도한다.
브랜치는 항상 main에 직접 push하는 단순 플로우를 전제로 한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import git
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class DiffResult:
    """git diff 분석 결과 — .md 파일에 한정."""

    added: list[Path] = field(default_factory=list)
    modified: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)

    @property
    def changed(self) -> list[Path]:
        """생성 + 수정 파일 목록."""
        return self.added + self.modified

    @property
    def is_empty(self) -> bool:
        """변경된 파일이 없으면 True."""
        return not (self.added or self.modified or self.deleted)


class GitManager:
    """gitpython 기반 Git 작업 래퍼.

    Obsidian vault의 저장(save) 및 동기화(sync) 작업을 처리한다.
    """

    def __init__(self, repo_path: Path) -> None:
        """GitManager를 초기화한다.

        Args:
            repo_path: git repository 루트 경로
        Raises:
            git.InvalidGitRepositoryError: repo_path가 git repository가 아닌 경우
        """
        self._repo = git.Repo(repo_path, search_parent_directories=True)
        self._repo_path = Path(self._repo.working_tree_dir)
        logger.debug("GitManager 초기화: %s", self._repo_path)

    def current_head(self) -> str | None:
        """현재 HEAD commit hash를 반환한다.

        Returns:
            HEAD commit hash (40자 hex) — 커밋이 없으면 None
        """
        try:
            return self._repo.head.commit.hexsha
        except ValueError:
            return None

    def add_all(self) -> list[str]:
        """모든 변경사항을 스테이징한다.

        Returns:
            스테이징된 파일 경로 목록 (워킹트리 기준 상대경로)
        """
        self._repo.git.add(A=True)
        staged: list[str] = []
        status = self._repo.git.status("--porcelain")
        for line in status.splitlines():
            if not line or len(line) < 3:
                continue
            index_status = line[0]
            if index_status in ("A", "M", "D", "R", "C"):
                path_part = line[3:].strip()
                # rename 형식 "old -> new" → new만 취함
                if " -> " in path_part:
                    path_part = path_part.split(" -> ")[1]
                staged.append(path_part)
        logger.debug("스테이징 완료: %d개 파일", len(staged))
        return staged

    def commit(self, message: str) -> str:
        """스테이징된 변경사항을 커밋한다.

        Args:
            message: 커밋 메시지
        Returns:
            새 커밋의 hexsha (40자)
        Raises:
            git.GitCommandError: 커밋 실패 시
        """
        commit_obj = self._repo.index.commit(message)
        logger.info("커밋 완료: %s — %s", commit_obj.hexsha[:8], message)
        return commit_obj.hexsha

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(git.GitCommandError),
        reraise=True,
    )
    def push(self, remote: str = "origin", branch: str = "main") -> None:
        """원격 저장소에 push한다. GitCommandError 발생 시 최대 3회 재시도.

        Args:
            remote: 원격 저장소 이름
            branch: 대상 브랜치 이름
        Raises:
            git.GitCommandError: 재시도 후에도 push 실패 시
        """
        self._repo.remote(remote).push(branch)
        logger.info("Push 완료: %s/%s", remote, branch)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(git.GitCommandError),
        reraise=True,
    )
    def pull(self, remote: str = "origin", branch: str = "main") -> str | None:
        """원격 저장소에서 pull한다. GitCommandError 발생 시 최대 3회 재시도.

        Args:
            remote: 원격 저장소 이름
            branch: 대상 브랜치 이름
        Returns:
            pull 후 HEAD commit hash
        Raises:
            git.GitCommandError: 재시도 후에도 pull 실패 시
        """
        self._repo.remote(remote).pull(branch)
        new_head = self.current_head()
        logger.info("Pull 완료: HEAD → %s", new_head[:8] if new_head else "None")
        return new_head

    def diff_files(self, from_commit: str | None, to_commit: str) -> DiffResult:
        """두 커밋 사이의 .md 파일 변경사항을 분석한다.

        Args:
            from_commit: 비교 시작 commit hash. None이면 초기 커밋으로 처리.
            to_commit: 비교 끝 commit hash
        Returns:
            DiffResult (.md 파일의 생성/수정/삭제 목록)
        """
        if from_commit is None:
            to_obj = self._repo.commit(to_commit)
            # 초기 커밋 — to_commit의 모든 .md 파일을 "추가"로 처리
            added = [
                self._repo_path / item.path
                for item in to_obj.tree.traverse()
                if hasattr(item, "path") and item.path.endswith(".md")
            ]
            logger.debug("초기 커밋 diff: .md 파일 %d개 추가", len(added))
            return DiffResult(added=added)

        from_obj = self._repo.commit(from_commit)
        to_obj = self._repo.commit(to_commit)
        added: list[Path] = []
        modified: list[Path] = []
        deleted: list[Path] = []

        for diff in from_obj.diff(to_obj):
            a_is_md = diff.a_path.endswith(".md")
            b_is_md = (diff.b_path or "").endswith(".md")

            if diff.change_type == "A" and b_is_md:
                added.append(self._repo_path / diff.b_path)
            elif diff.change_type == "M" and b_is_md:
                modified.append(self._repo_path / diff.b_path)
            elif diff.change_type == "D" and a_is_md:
                deleted.append(self._repo_path / diff.a_path)
            elif diff.change_type == "R":
                if a_is_md:
                    deleted.append(self._repo_path / diff.a_path)
                if b_is_md:
                    added.append(self._repo_path / diff.b_path)

        logger.debug(
            "Diff 결과: 추가 %d / 수정 %d / 삭제 %d",
            len(added), len(modified), len(deleted),
        )
        return DiffResult(added=added, modified=modified, deleted=deleted)

    @staticmethod
    def generate_commit_message(staged_paths: list[str]) -> str:
        """스테이징된 파일 목록을 기반으로 커밋 메시지를 자동 생성한다.

        Args:
            staged_paths: 스테이징된 파일 경로 목록
        Returns:
            자동 생성된 커밋 메시지
        """
        if not staged_paths:
            return "chore: sync vault [SlotMachine]"

        md_files = [p for p in staged_paths if p.endswith(".md")]
        total = len(staged_paths)

        if total <= 3:
            names = ", ".join(Path(p).stem for p in staged_paths[:3])
            return f"chore: update {names} [SlotMachine]"

        return f"chore: update {total} files ({len(md_files)} notes) [SlotMachine]"
