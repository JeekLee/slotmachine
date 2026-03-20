# Backlog

PRD 기준 전체 Feature 목록. Sprint 계획 시 여기서 꺼내 sprint-current.md로 이동한다.

---

## Phase 1 — Foundation (F1)

- [x] [F1-01 ~ F1-06] 초기 구현 완료 (Sprint 1~2)
- [ ] [F1-08] sync 중 embedding 실패 문서 수집 → 분할 제안 → 승인 → vault 저장 + 원본 삭제 + GraphDB 갱신 | developer ← Sprint 6

## Phase 2 — Live Sync (F2)

- [ ] [F2-01] Webhook 수신 서버 구현 (fastapi + uvicorn) | developer + infra
- [ ] [F2-02] gitpython 기반 git diff 분석 모듈 | developer
- [ ] [F2-03] 증분 업데이트 로직 (변경 파일만 GraphDB 반영) | developer
- [ ] [F2-04] 삭제 문서 처리 (노드 + 엣지 제거) | developer
- [ ] [F2-05] Sync 이력 로그 저장 (sqlite3) | developer
- [ ] [F2-06] `slotmachine status` 커맨드 구현 | developer
- [ ] [F2-07] 오류 처리 및 재시도 로직 (tenacity) | developer
- [ ] [F2-08] push 시나리오 통합 테스트 | developer
- [ ] [F2-09] sync 중 삭제 감지 시 다른 문서 본문의 `[[삭제된_제목]]` 위키링크 제거 | developer

## Phase 3 — SlotMachine Core (F3)

- [ ] [F3-01] INBOX 폴더 감지 및 문서 일괄 로드 | developer
- [ ] [F3-02] PARA 분류 프롬프트 설계 및 튜닝 | pm + developer
- [ ] [F3-03] LLM 분류 결과 파싱 (카테고리 + 확신도 + 근거) | developer
- [ ] [F3-04] CLI 분류 결과 표시 UI | developer
- [ ] [F3-05] 사용자 일괄 승인 / 개별 수정 인터랙션 | developer
- [ ] [F3-06] 파일 이동 + 자동 git commit | developer
- [ ] [F3-07] 확신도 낮은 문서 별도 처리 플로우 | developer
- [ ] [F3-08] classify_inbox 중 embedding 실패 → 맥락 분할 제안 → 승인 → 분할 문서로 PARA 분류 진행 + 원본 삭제 | developer ← Sprint 6
- [ ] [F3-10] F3-09 rename 실행 시 다른 문서 본문의 `[[구_제목]]` → `[[새_제목]]` 일괄 교체 | developer

## Phase 4 — Knowledge Graph (F4) ✅ Sprint 5 완료

- [x] [F4-01] 벡터 유사도 검색 모듈 | developer
- [x] [F4-02] 그래프 근접성 계산 알고리즘 | developer
- [x] [F4-03] 관련도 임계값 기반 후보 필터링 | developer
- [x] [F4-04] `suggest_links` MCP 툴 + 위키링크 삽입 위치 추천 | developer
- [x] [F4-05] 중복 링크 방지 및 양방향 링크 처리 | developer
- [ ] [F4-09] Archives 카테고리를 링크 후보·relink 피벗·역방향 삽입 대상에서 제외 | developer
- [ ] [F4-10] threshold 기본값 0.5 → 0.65 변경 + TAG_BOOST_UNIT 적정성 검토 | developer
- [ ] [F4-11] 링크 거절 기억 — 사용자가 거절한 쌍을 IGNORED_PAIR 엣지로 저장하여 재제안 방지 | developer (Could)
- [ ] [F4-08-01] Document 노드에 `links_evaluated_at` 타임스탬프 추가 — `apply_links` 실행 시 자동 갱신 | developer
- [ ] [F4-08-02] Delta 모드: `links_evaluated_at` 기준 재판단 대상 문서 선별 로직 | developer
- [ ] [F4-08-03] 피벗 문서 기준 `find_related` 실행 → 양방향 링크 후보 생성 | developer
- [ ] [F4-08-04] Full 모드: 대상 수 / 예상 시간 표시 + 확인 인터랙션 | developer
- [ ] [F4-08-05] 배치 결과 테이블 표시 + 전체 승인/개별 수정/취소 인터랙션 | developer
- [ ] [F4-08-06] `/slotmachine:relink` 슬래시 커맨드 정의 | developer
- [ ] [F4-08-07] `--para` 범위 지정 옵션 | developer
- [ ] [F4-08-08] Full 모드 진행률 표시 | developer

## Phase 5 — Second Brain RAG (F5) ✅ Sprint 6 완료

- [x] [F5-01] RAG 질의 파이프라인 구현 | developer
- [x] [F5-02] Top-K 문서 검색 및 컨텍스트 구성 | developer
- [x] [F5-03] 토큰 제한 내 컨텍스트 최적화 (top_k) | developer
- [x] [F5-04] 출처 링크 포맷 (Obsidian URI) 구현 | developer
- [x] [F5-05] "참조 없음" 케이스 처리 | developer
- [x] [F5-07] PARA 카테고리 범위 지정 검색 옵션 (para_filter) | developer

## Phase 6 — Polish & Beta

- [ ] 전체 기능 통합 테스트 | developer
- [ ] README 및 사용자 문서 작성 | pm + developer
- [ ] `pip install slotmachine` 패키징 | developer + infra
- [ ] 베타 피드백 수집 및 반영 | pm
