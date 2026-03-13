---
description: SlotMachine 초기 설정 — vault 경로, Neo4j, git, 임베딩 프로바이더를 ~/.slotmachine/settings.env에 저장
allowed-tools: Bash(cat ~/.slotmachine/*), Read, mcp__slotmachine__config_vault
---

# /slotmachine:config — 초기 설정

SlotMachine 플러그인의 초기 설정을 진행한다.

`$ARGUMENTS`에 값이 있으면 즉시 처리하고, 없으면 대화로 수집한다.

## 활성화 확인

설정 진행 전 `~/.slotmachine/settings.env`가 이미 존재하는 경우:
- 현재 값(API 키는 마스킹)을 보여주고 재설정 여부를 확인한다
- 재설정하지 않으면 중단하고 `/slotmachine:init` 또는 `/slotmachine:save`를 안내한다

## 수집 항목

인자가 없으면 다음 항목을 한 번에 모아서 묻는다:

1. **vault_path** (필수) — Obsidian vault 절대 경로
2. **neo4j_password** (필수) — Neo4j 비밀번호
3. **git_repo_url** (선택) — git remote URL (HTTPS 또는 SSH)
4. **embedding_provider** (선택, 기본: jina) — `jina` / `openai` / `voyage` / `gemini` / `ollama`
5. **해당 프로바이더의 API key** (선택)

## 실행

모든 값을 수집한 뒤 `config_vault` MCP 툴을 호출한다.

완료 후 다음 단계를 안내한다:
```
설정이 저장되었습니다 → ~/.slotmachine/settings.env
다음 단계:
  1. MCP 서버 재시작 (Claude Code 재시작)
  2. /slotmachine:init 실행 — DB 초기화 및 vault 전체 적재
```

## 예시

```
/slotmachine:config
/slotmachine:config vault_path=/Users/me/vault neo4j_password=secret
```
