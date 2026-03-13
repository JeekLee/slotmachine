# Backlog

PRD 기준 전체 Feature 목록. Sprint 계획 시 여기서 꺼내 sprint-current.md로 이동한다.

---

## Phase 2 — Live Sync (F2)

- [ ] [F2-01] Webhook 수신 서버 구현 (fastapi + uvicorn) | developer + infra
- [ ] [F2-02] gitpython 기반 git diff 분석 모듈 | developer
- [ ] [F2-03] 증분 업데이트 로직 (변경 파일만 GraphDB 반영) | developer
- [ ] [F2-04] 삭제 문서 처리 (노드 + 엣지 제거) | developer
- [ ] [F2-05] Sync 이력 로그 저장 (sqlite3) | developer
- [ ] [F2-06] `slotmachine status` 커맨드 구현 | developer
- [ ] [F2-07] 오류 처리 및 재시도 로직 (tenacity) | developer
- [ ] [F2-08] push 시나리오 통합 테스트 | developer

## Phase 3 — SlotMachine Core (F3)

- [ ] [F3-01] INBOX 폴더 감지 및 문서 일괄 로드 | developer
- [ ] [F3-02] PARA 분류 프롬프트 설계 및 튜닝 | pm + developer
- [ ] [F3-03] LLM 분류 결과 파싱 (카테고리 + 확신도 + 근거) | developer
- [ ] [F3-04] CLI 분류 결과 표시 UI | developer
- [ ] [F3-05] 사용자 일괄 승인 / 개별 수정 인터랙션 | developer
- [ ] [F3-06] 파일 이동 + 자동 git commit | developer
- [ ] [F3-07] 확신도 낮은 문서 별도 처리 플로우 | developer

## Phase 4 — Knowledge Graph (F4)

- [ ] [F4-01] 벡터 유사도 검색 모듈 | developer
- [ ] [F4-02] 그래프 근접성 계산 알고리즘 | developer
- [ ] [F4-03] 관련도 임계값 기반 후보 필터링 | developer
- [ ] [F4-04] 위키링크 삽입 위치 추천 로직 | developer
- [ ] [F4-05] 중복 링크 방지 및 양방향 링크 처리 | developer

## Phase 5 — Second Brain RAG (F5)

- [ ] [F5-01] RAG 질의 파이프라인 구현 | developer
- [ ] [F5-02] Top-K 문서 검색 및 컨텍스트 구성 | developer
- [ ] [F5-03] 토큰 제한 내 컨텍스트 최적화 | developer
- [ ] [F5-04] 출처 링크 포맷 (Obsidian URI) 구현 | developer
- [ ] [F5-05] "참조 없음" 케이스 처리 | developer

## Phase 6 — Polish & Beta

- [ ] 전체 기능 통합 테스트 | developer
- [ ] README 및 사용자 문서 작성 | pm + developer
- [ ] `pip install slotmachine` 패키징 | developer + infra
- [ ] 베타 피드백 수집 및 반영 | pm
