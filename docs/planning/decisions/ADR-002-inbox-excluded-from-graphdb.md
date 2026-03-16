# ADR-002: INBOX 문서를 GraphDB 적재 대상에서 제외

- 날짜: 2026-03-16
- 상태: 결정됨 (Accepted)
- 결정자: PM + Developer

---

## 컨텍스트

현재 `full_sync` / `incremental_sync`는 vault 내 모든 `.md` 파일을 GraphDB에 적재한다.
INBOX 폴더(`00_Inbox`)는 분류 전 임시 문서를 보관하는 staging area로,
품질이 검증되지 않은 초안·메모·캡처 문서가 혼재한다.

이 문서들이 GraphDB에 포함될 경우:
- `recall` RAG 검색 결과에 노이즈가 섞여 검색 품질 저하
- 임베딩 비용 낭비 (분류 후 이동되면 재처리 필요)
- `suggest_links` 등 linker 결과에도 미검증 문서가 등장

## 결정

**INBOX 폴더에 속하는 문서는 GraphDB 적재 자체를 건너뛴다.**

- `full_sync`: `para_category == "Inbox"`인 파일은 upsert 하지 않고 스킵
- `incremental_sync`: 생성/수정 파일 중 `para_category == "Inbox"`는 스킵
- 삭제 이벤트는 기존 데이터 정합성을 위해 정상 처리 (혹시 이전에 적재된 Inbox 문서 제거)

INBOX 문서가 `classify_inbox` / `apply_classification`을 통해 PARA 카테고리로 이동된 후,
`save` 또는 `sync` 시점에 비로소 GraphDB에 적재된다.

## 결과

**장점**
- RAG 검색 품질 향상 — 정제된 문서만 지식베이스에 포함
- 임베딩 비용 절감 — Inbox 문서는 임베딩 생성 자체를 생략
- PARA 철학과 일치 — "분류 완료 = 지식" 원칙 강화

**단점 / 트레이드오프**
- Inbox 문서 간 링크 추천(suggest_links) 불가 — 허용 가능한 제약
  (Inbox 문서는 임시 문서이므로 wikilink 추천 필요성이 낮음)

## 대안 검토

| 대안 | 기각 이유 |
|------|---------|
| GraphDB엔 적재하되 recall 기본 para_filter에서 제외 | GraphDB에 노이즈 존재, 임베딩 비용 낭비 지속 |
| Inbox 문서에 별도 플래그 부여 후 RAG에서 필터 | 복잡도 증가, 근본 해결 아님 |
