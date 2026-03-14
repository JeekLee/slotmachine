---
description: 개인 지식베이스에서 RAG 검색 — 외부 소스 없이 vault 문서만 사용
allowed-tools: Bash(cat ~/.slotmachine/*), mcp__slotmachine__recall
---

# /slotmachine:recall — 개인 지식베이스 검색

`$ARGUMENTS`의 쿼리로 Obsidian vault에서 관련 문서를 검색하고 답변을 생성한다.

## 사전 조건 확인

`~/.slotmachine/settings.env`가 없으면:
- "설정이 없습니다. `/slotmachine:config`와 `/slotmachine:init`을 먼저 실행하세요." 라고 알리고 중단한다

## 실행

`recall` MCP 툴을 호출한다 (쿼리: `$ARGUMENTS`, top_k: 5).

## 답변 규칙 (반드시 준수)

- **웹 검색, 외부 소스, 학습 데이터를 사용하지 않는다**
- 오직 `recall` 툴이 반환한 `context` 필드의 내용만 사용한다
- vault에서 관련 문서를 찾지 못하면 솔직하게 알린다 — 추측하거나 외부 지식을 보완하지 않는다
- 답변 마지막에 참조 문서 목록(제목 + Obsidian URI)을 첨부한다

## 응답 형식

```
{쿼리에 대한 답변 — vault 내용 기반}

---
참조 문서:
- [[문서 제목]] obsidian://open?vault=...
```

## 예시

```
/slotmachine:recall 프로젝트 아키텍처 결정 이유
/slotmachine:recall 지난주 회의에서 결정한 사항
/slotmachine:recall Python async 패턴
```
