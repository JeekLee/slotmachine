---
description: vault 변경사항을 git commit+push하고 GraphDB를 증분 업데이트
allowed-tools: Bash(cat ~/.slotmachine/*), mcp__slotmachine__save_vault
---

# /slotmachine:save — 저장 및 GraphDB 업데이트

Obsidian vault의 변경사항을 저장하고 GraphDB를 최신 상태로 유지한다.

`$ARGUMENTS`에 커밋 메시지를 지정할 수 있다. 없으면 자동 생성한다.

## 처리 흐름

1. `git add -A` — 모든 변경사항 스테이징
2. `git commit` — 커밋 (변경사항 없으면 중단)
3. `git push origin main` — 원격 저장소에 푸시
4. 증분 GraphDB 동기화 — 변경된 문서만 처리

## 사전 조건 확인

`~/.slotmachine/settings.env`가 없으면:
- "설정이 없습니다. `/slotmachine:config`를 먼저 실행하세요." 라고 알리고 중단한다

## 실행

`save_vault` MCP 툴을 호출한다.

완료 후 다음을 한국어로 보고한다:
- 커밋 해시 (앞 8자)
- 추가 / 수정 / 삭제된 문서 수
- 실패한 문서가 있으면 건수와 오류 내용
- 변경사항이 없으면: "저장할 변경사항이 없습니다"

## 예시

```
/slotmachine:save
/slotmachine:save 오늘 회의 노트 추가
```
