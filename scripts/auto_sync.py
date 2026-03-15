#!/usr/bin/env python3
"""UserPromptSubmit hook — vault를 자동으로 GraphDB에 동기화한다.

Claude Code가 프롬프트를 받을 때마다 실행되며, COOLDOWN_SECONDS 이내에는 재실행하지 않는다.
stdout 출력은 Claude Code 컨텍스트에 주입된다.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

COOLDOWN_SECONDS = 600  # 10분


def main() -> None:
    stamp_file = Path.home() / ".slotmachine" / "last_auto_sync"
    now = time.time()

    # 쿨다운 체크 — 마지막 실행 후 COOLDOWN_SECONDS 미만이면 건너뜀
    if stamp_file.exists():
        try:
            if now - float(stamp_file.read_text().strip()) < COOLDOWN_SECONDS:
                return
        except ValueError:
            pass

    try:
        from slotmachine.config import get_settings
        from slotmachine.sync.graphdb import GraphDB
        from slotmachine.sync.pipelines import live_sync
        from slotmachine.sync.sync_history import SyncHistory
    except ImportError as exc:
        print(f"[SlotMachine] auto-sync skip (import error): {exc}", file=sys.stderr)
        return

    try:
        settings = get_settings()
    except Exception:
        # 설정 파일 없으면 조용히 종료 (init 전 상태)
        return

    try:
        db = GraphDB(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)

        embedding_provider = None
        try:
            from slotmachine.sync.embedding import get_provider
            embedding_provider = get_provider(settings)
        except Exception:
            pass

        history = SyncHistory(settings.vault_path / ".slotmachine" / "sync_history.db")
        result = live_sync(
            settings.vault_path,
            db,
            embedding_provider=embedding_provider,
            sync_history=history,
        )

        # 성공 시 타임스탬프 갱신
        stamp_file.parent.mkdir(parents=True, exist_ok=True)
        stamp_file.write_text(str(now))

        if result.nothing_to_sync:
            pass  # 변경 없으면 출력 생략
        elif result.success:
            r = result.sync_result
            print(
                f"[SlotMachine] vault 동기화 완료 — "
                f"+{r.added} 추가 / ~{r.modified} 수정 / -{r.deleted} 삭제"
            )
        else:
            print(f"[SlotMachine] vault 동기화 실패: {result.error}", file=sys.stderr)

    except Exception as exc:
        print(f"[SlotMachine] auto-sync error: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
