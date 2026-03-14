---
description: 원격 저장소(main)를 pull하고 GraphDB를 증분 동기화
allowed-tools: Bash(cat ~/.slotmachine/*), mcp__slotmachine__sync_vault
---

# /slotmachine:sync — 원격 동기화

원격 저장소(GitHub main 브랜치)의 변경사항을 로컬 GraphDB에 반영한다.

다른 기기 또는 팀원이 push한 내용을 GraphDB에 적용할 때 사용한다.

## 처리 흐름

1. `git pull origin main` — 원격 변경사항 수신
2. HEAD 변화 감지 — 이전/신규 커밋 비교
3. 증분 GraphDB 동기화 — 변경된 문서만 처리

## 사전 조건 확인

`~/.slotmachine/settings.env`가 없으면:
- "설정이 없습니다. `/slotmachine:config`를 먼저 실행하세요." 라고 알리고 중단한다

## 실행

`sync_vault` MCP 툴을 호출한다.

완료 후 다음을 한국어로 보고한다:
- 이전 HEAD → 신규 HEAD (각 앞 8자)
- 추가 / 수정 / 삭제된 문서 수
- 실패한 문서가 있으면 건수
- 새 변경사항이 없으면: "원격에 새 변경사항이 없습니다"

## 예시

```
/slotmachine:sync
```
