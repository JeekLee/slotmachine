# Sprint 7
기간: 착수일 기준 1주
목표: 링크 시스템 고도화 — relink 커맨드, Archives 격리, threshold 조정, dead link 정리

---

## In Progress

_(없음)_

---

## Todo

_(없음)_

---

## Done

- [x] [F4-09] Archives 링크 생태계 완전 격리 — `find_related` 후보 필터, threshold 기본값 0.65 적용 | developer
- [x] [F4-10] threshold 기본값 0.5 → 0.65 — `server.py`, `linker.py`, `commands/link.md` 반영 | developer
- [x] [F4-08-01] Document 노드 `links_evaluated_at` 타임스탬프 — `apply_links` 실행 후 자동 갱신 | developer
- [x] [F4-08-02] Delta 모드: `get_delta_documents` — `links_evaluated_at IS NULL OR updated_at > links_evaluated_at` | developer
- [x] [F4-08-03] `relink` MCP 툴 — delta/all 모드, para_filter 지원, 단방향 링크 후보 반환 | developer
- [x] [F4-08-06] `/slotmachine:relink` 슬래시 커맨드 — `commands/relink.md`, `.claude/commands/relink.md` | developer
- [x] [F2-09] sync 삭제 시 `remove_wikilinks_in_vault` — 다른 문서의 `[[삭제된_제목]]` 제거 | developer
- [x] [F3-10] classify rename 시 `replace_wikilinks_in_vault` — `[[구_제목]]` → `[[새_제목]]` 일괄 교체 | developer

---

## 블로커 / 이슈

_(발생 시 기록)_

---

# Sprint 6 (완료)
기간: 착수일 기준 1주
목표: Phase 5 마무리 (F5-07) + Phase 6 Polish — 통합 테스트, README, 패키징

## Done

- [x] [F5-07] `recall` PARA 카테고리 범위 지정 검색 옵션 — para_filter 파라미터 추가 | developer
- [x] [P6-01] F4+F5 통합 테스트 — test_integration_f4_f5.py (12 passed) | developer
- [x] [P6-02] README.md 업데이트 — /slotmachine:link, status, 아키텍처 반영 | developer
- [x] [P6-03] pyproject.toml 버전 0.4.0 bump | developer
- [x] [P6-04] Inbox 문서 GraphDB 적재 제외 — full_sync/incremental_sync 스킵 처리 | developer
- [x] [F1-08] sync 중 embedding 실패(oversized) 수집 → apply_split MCP tool + splitter 모듈 구현 | developer
- [x] [F3-08] classify_inbox oversized 플래그 노출 → apply_split으로 분할 후 PARA 분류 진행 | developer
- [x] [F3-09] 분류 시 파일명 자동 제안 — 관련 문서 패턴 우선 / fallback: 목적지 폴더 패턴 / rename+move 동시 처리 / inbox.md 5.5단계 추가 | developer

---

## 블로커 / 이슈

_(발생 시 기록)_
