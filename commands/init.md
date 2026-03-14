---
description: Neo4j 스키마 초기화 + vault 전체 적재 — config 이후 최초 1회 실행
allowed-tools: Bash(cat ~/.slotmachine/*), mcp__slotmachine__init_vault
---

# /slotmachine:init — DB 초기화 및 vault 적재

Neo4j 스키마를 초기화하고 Obsidian vault 전체를 GraphDB에 적재한다.

## 사전 조건 확인

`~/.slotmachine/settings.env`가 없으면:
- "설정이 없습니다. `/slotmachine:config`를 먼저 실행하세요." 라고 알리고 중단한다

## 실행

`init_vault` MCP 툴을 호출한다.

완료 후 다음을 한국어로 보고한다:
- 적재된 문서 수 (성공 / 실패)
- 임베딩 활성화 여부
- 실패한 문서가 있으면 처음 5개의 오류 내용
- 다음 단계: `/slotmachine:save` 또는 `/slotmachine:recall <쿼리>`

이미 데이터가 있어도 upsert 방식이므로 안전하게 재실행할 수 있다는 것을 안내한다.

## 예시

```
/slotmachine:init
```
