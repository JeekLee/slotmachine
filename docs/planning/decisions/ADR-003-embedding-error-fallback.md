# ADR-003: Embedding 오류 처리 전략 — 맥락 기반 문서 분할 + 사용자 승인

- 날짜: 2026-03-16
- 상태: 결정됨 (Accepted) — v2 (2026-03-16 재결정)
- 결정자: PM

---

## 컨텍스트

임베딩 API 호출 시 다음 상황에서 오류가 발생할 수 있다:

- 문서 길이가 프로바이더 토큰 한도를 초과 (Jina/OpenAI: ~8K tokens, Voyage: 프로바이더별 상이)
- 네트워크 오류, API Rate Limit 등 일시적 장애

현재 구현은 임베딩 예외가 sync 루프 상위 `except`에서 통째로 잡혀
문서 자체가 GraphDB에서 누락된다 (데이터 손실).

초기 검토(v1)에서는 truncation + embedding-less upsert 폴백 방식을 결정했으나,
이후 검토에서 이 방식은 근본 문제(문서가 너무 큼)를 해결하지 못한다는 점이 지적됐다.
Archives 포함 모든 PARA 카테고리가 임베딩 대상이므로, 원본을 유지하는 한 문제는 반복된다.

---

## 결정

**임베딩 실패 문서는 LLM으로 맥락 기반 분할 후 사용자 승인을 받아 처리한다. 원본 문서는 삭제한다.**

### 처리 경로 — Case 1: INBOX 처리 중 embedding 실패

```
classify_inbox 실행
  └─► 문서 embedding 시도
        └─► 실패 (토큰 초과 등)
              └─► LLM으로 맥락 기반 분할 제안 (분할 결과 + 근거 표시)
                    └─► 사용자 승인
                          ├─► 승인 → 분할된 각 문서로 PARA 분류 진행 / 원본 삭제
                          └─► 거부 → 해당 문서 건너뜀 (경고 표시)
```

### 처리 경로 — Case 2: save/sync 중 기존 문서 embedding 실패

```
save / sync 실행
  └─► embedding 실패 문서 수집 (sync 중단 없이 계속 진행)
        └─► sync 완료 후 "N개 문서 분할 필요" 리포트
              └─► LLM으로 맥락 기반 분할 제안
                    └─► 사용자 승인
                          ├─► 승인 → 분할 파일 vault에 저장 / 원본 삭제 / GraphDB 갱신
                          └─► 거부 → embedding-less upsert (키워드 검색만 가능)로 폴백
```

### 원본 문서 처리: 삭제

Archives 포함 모든 PARA 카테고리가 임베딩 대상이므로,
원본을 Archives로 이동하거나 유지하면 동일 문제가 반복된다.
사용자 승인 후 원본을 삭제하고 분할 문서로 완전 대체한다.

### 일시적 오류(네트워크, Rate Limit 등) 구분

토큰 초과 오류는 분할 대상으로 처리하고,
일시적 오류(네트워크 장애, Rate Limit)는 tenacity 재시도로 처리한다.
재시도 후에도 실패하면 embedding-less upsert로 폴백한다.

### 공통 모듈

`splitter` 모듈을 신설해 두 케이스가 동일한 분할 로직을 재사용한다.

---

## Feature 정의

| Feature ID | 설명 | 트리거 |
|------------|------|--------|
| **F1-08** | sync 중 embedding 실패 문서 수집 → 완료 후 분할 제안 → 승인 → vault 저장 + GraphDB 갱신 | `save`, `sync` |
| **F3-08** | classify_inbox 중 embedding 실패 → 맥락 분할 제안 → 승인 → 분할 문서로 PARA 분류 진행 | `inbox` |

---

## 결과

**장점**
- 근본 해결 — 원본 삭제로 동일 문제 반복 없음
- vault 품질 향상 — 너무 큰 문서가 atomic note로 정리됨
- 사용자 통제 — 모든 파일 조작이 승인 후에만 발생

**단점 / 트레이드오프**
- 구현 복잡도 증가 — splitter 모듈, 승인 UX, 파일 삭제 처리 필요
- 거부 시 해당 문서는 벡터 검색 불가 (embedding-less 폴백)
- LLM 분할 품질에 의존 — 부적절한 분할이 나올 수 있음 (사용자 승인으로 완화)

## 대안 검토

| 대안 | 기각 이유 |
|------|---------|
| truncation + embedding-less upsert (v1) | 근본 해결 아님, Archives 이동 시에도 문제 반복 |
| GraphDB 청킹(Chunk 노드) | 스키마 변경, 검색 역참조 복잡도, vault는 변경 안 됨 |
| 원본 Archives 이동 | Archives도 임베딩 대상 — 동일 문제 반복 |
| 원본 유지 + 분할 문서 병존 | vault에 중복 내용, 장기적으로 혼란 |
