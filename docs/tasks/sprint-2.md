# Sprint 2
기간: 착수일 기준 2주
목표: Phase 2 Live Sync 완료 — Plugin-driven git save/sync 및 GraphDB 증분 업데이트 파이프라인 구축

---

## In Progress

_(없음)_

---

## Todo

_(없음 — Sprint 2 완료)_

---

## Done

- [x] [F2-09] 통합 테스트 — save/sync 시나리오 end-to-end (79개 신규, 전체 174/174 pass) | developer | 2026-03-13 17:30:00
- [x] [F2-07] MCP 서버 — server.py에 `save_vault` / `sync_vault` 툴 등록 (fastmcp) | developer | 2026-03-13 17:30:00
- [x] [F2-08] 재시도 로직 — tenacity로 push/pull GitCommandError 시 최대 3회 재시도 | developer | 2026-03-13 17:30:00
- [x] [F2-06] Sync 이력 로그 — sqlite3 기반 SyncHistory 저장 (성공/실패/변경 수) | developer | 2026-03-13 17:30:00
- [x] [F2-03] `save` 파이프라인 — git add + 자동 커밋 메시지 생성 + push to main + GraphDB 증분 업데이트 | developer | 2026-03-13 17:30:00
- [x] [F2-04] `sync` 파이프라인 — git pull origin main + diff + GraphDB 증분 업데이트 | developer | 2026-03-13 17:30:00
- [x] [F2-05] 증분 업데이트 로직 — 변경 파일 upsert / 삭제 파일 delete GraphDB 반영 | developer | 2026-03-13 17:30:00
- [x] [F2-02] diff 분석 모듈 — push/pull 전후 HEAD 비교, 생성/수정/삭제 .md 파일 목록 반환 | developer | 2026-03-13 17:30:00
- [x] [F2-01] GitManager 구현 — gitpython 기반 add/commit/push/pull/diff 래퍼 클래스 + DiffResult | developer | 2026-03-13 17:30:00

---

## 블로커 / 이슈

_(발생 시 기록)_
