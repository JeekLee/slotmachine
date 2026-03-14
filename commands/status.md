---
description: MCP 서버, Neo4j, Vault, Git, 임베딩 등 SlotMachine 전체 컴포넌트 상태 점검
allowed-tools: mcp__slotmachine__status_check
---

# /slotmachine:status — 상태 점검

`status_check` MCP 툴을 호출해 결과를 아래 형식으로 보여준다.

## 실행

인자 없이 즉시 `status_check`를 호출한다.

## 출력 형식

결과를 마크다운 표로 정리한다. 각 항목의 `ok` 값에 따라 상태 이모지를 붙인다:
- `ok: true` → ✅
- `ok: false` → ❌

```
## SlotMachine 상태 점검  YYYY-MM-DD HH:MM UTC

| 컴포넌트     | 상태 | 세부 정보                          |
|------------|------|----------------------------------|
| MCP 서버   | ✅   | 실행 중                           |
| 설정 파일   | ✅   | ~/.slotmachine/settings.env      |
| Vault      | ✅   | /path/to/vault  (문서 123개, INBOX 5개) |
| Neo4j      | ✅   | bolt://localhost:7687  노드 456개  |
| Git        | ✅   | https://github.com/…  (branch: main, 변경 없음) |
| 임베딩     | ✅   | jina / jina-embeddings-v3  API Key 설정됨 |
```

- `ok: false` 항목은 `hint` 또는 `message`를 표 아래에 별도로 출력한다.
- 모든 항목이 ✅이면 마지막에 한 줄 요약을 추가한다:
  ```
  모든 컴포넌트 정상 — SlotMachine 사용 준비 완료 🎰
  ```
- ❌가 있으면 수정이 필요한 항목을 번호 목록으로 안내한다.
