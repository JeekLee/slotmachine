# SlotMachine

MCP 기반 ClaudeCode 플러그인.
Obsidian vault를 GraphDB에 연동해 RAG 기능을 제공하는 Second Brain 프로젝트.
INBOX에 쌓인 문서를 슬롯머신 레버 하나로 분류·연결·정리한다.

---

## 프로젝트 현황

| 항목 | 내용 |
|------|------|
| 현재 Phase | Phase 6 — Polish & Beta |
| 현재 Sprint | Sprint 6 |
| 스프린트 문서 | docs/tasks/sprint-current.md |
| PRD | docs/prd/SlotMachine_PRD.md |

---

## 기술 스택

- **언어**: Python 3.11+
- **MCP 서버**: fastmcp
- **GraphDB**: Neo4j (로컬 우선) + neo4j Python 드라이버
- **Git 연동**: gitpython
- **파일 파싱**: python-frontmatter + mistletoe
- **HTTP 서버**: fastapi + uvicorn
- **설정 관리**: pydantic-settings
- **패키지 관리**: uv
- **진행률**: tqdm
- **재시도**: tenacity
- **테스트**: pytest + pytest-asyncio

---

## 디렉토리 구조

```
slotmachine/
├── CLAUDE.md
├── .claude-plugin/
│   └── plugin.json       # Claude Code 플러그인 매니페스트
├── .claude/
│   └── commands/         # 슬래시 커맨드 정의
│       ├── config.md     # /slotmachine:config
│       ├── init.md       # /slotmachine:init
│       ├── save.md       # /slotmachine:save
│       ├── sync.md       # /slotmachine:sync
│       ├── recall.md     # /slotmachine:recall
│       ├── pm.md         # /pm
│       ├── developer.md  # /developer
│       └── infra.md      # /infra
├── scripts/
│   └── bootstrap-mcp.sh  # MCP 서버 진입점 (venv 준비 + 실행)
├── docs/
│   ├── prd/              # PRD 문서
│   ├── planning/         # 기획 문서 및 의사결정 기록(ADR)
│   ├── tasks/            # 스프린트 및 백로그 관리
│   └── infra/            # 인프라 아키텍처 및 runbook
├── slotmachine/          # 소스코드
│   ├── server.py         # MCP 서버 진입점
│   ├── config.py         # 설정 (pydantic-settings)
│   ├── sync/             # F1, F2: Git 연동 및 GraphDB 저장
│   ├── classifier/       # F3: PARA 자동 분류
│   └── rag/              # F5: RAG 엔진
└── tests/
```

---

## 역할 시스템

이 프로젝트는 세 가지 역할로 운영된다.
슬래시 커맨드로 명시적으로 전환하거나, 자연어 요청 시 아래 기준으로 자동 판단한다.

### 슬래시 커맨드

| 커맨드 | 역할 | 주요 산출물 |
|--------|------|------------|
| `/pm` | Product Manager | PRD, Task, 기획 문서, 의사결정 기록 |
| `/developer` | Plugin Developer | 소스코드, 테스트, 코드 리뷰 |
| `/infra` | Infra Manager | 환경 설정, 아키텍처 문서, runbook |

### 자연어 자동 판단 규칙

사용자의 요청을 받으면 아래 기준으로 역할을 먼저 판단한다.
응답 첫 줄에 `[역할]` 을 명시한 뒤 진행한다.

| 요청 유형 / 키워드 | 판단 역할 |
|-------------------|---------|
| PRD, 기획, 요구사항, 우선순위, 스펙, Feature, 일정 | PM |
| 태스크, 스프린트, 백로그, 할 일, 진행 현황 | PM |
| 코드, 구현, 함수, 클래스, 버그, 테스트, 리팩토링 | Developer |
| 환경, 배포, DB, Neo4j, 서버, 설정, .env, 시크릿 | Infra |
| 복합적이거나 판단이 모호한 경우 | 역할을 먼저 질문 후 진행 |

### 역할 판단 예시

```
"오늘 할 태스크 정리해줘"         → [PM]
"parser.py 버그 고쳐줘"           → [Developer]
"Neo4j 로컬 환경 세팅해줘"        → [Infra]
"F1 기획이랑 코드 같이 봐줘"      → 역할 먼저 확인 후 진행
```

---

## 플러그인 배포

### 설치 커맨드 (2단계)

```
/plugin marketplace add JeekLee/slotmachine
/plugin install slotmachine@jeeklee
```

- `claude plugin install` (CLI) 은 존재하지 않음 — 슬래시 커맨드만 유효
- `@jeeklee` 는 `.claude-plugin/marketplace.json`의 `name` 필드값

### commands 디렉토리 구분

| 경로 | 용도 |
|------|------|
| `commands/` | 플러그인으로 노출 (plugin.json이 가리킴) |
| `.claude/commands/` | 개발용 포함 전체 (프로젝트 컨텍스트에서만 로드) |

---

## 공통 원칙

- 모든 Task는 반드시 Feature ID(예: F1-01)와 연결
- 코드 변경 시 관련 Task를 sprint-current.md에 반영
- 의사결정이 발생하면 docs/planning/decisions/에 ADR 작성
- 시크릿과 인증 정보는 절대 코드에 하드코딩 금지
