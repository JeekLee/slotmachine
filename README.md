# SlotMachine 🎰

> **"나의 모든 지식을 Claude가 기억하는 Second Brain — INBOX에 쌓인 문서는 슬롯머신 돌리듯 한 번에 정리된다."**

Obsidian vault를 Neo4j GraphDB에 연동해 RAG 기능을 제공하는 **Claude Code MCP 플러그인**.
INBOX 문서 자동 분류(PARA), vault 동기화, 개인 지식베이스 검색을 슬래시 커맨드 하나로 처리한다.

---

## 주요 기능

| 기능 | 커맨드 | 설명 |
|------|--------|------|
| INBOX 자동 분류 | `/slotmachine:inbox` | INBOX 문서를 PARA로 분류·재작성·이동 |
| 위키링크 자동 제안 | `/slotmachine:link` | 문서 관련 문서 탐색 + 위키링크 삽입 |
| vault 저장 | `/slotmachine:save` | git commit + push + GraphDB 증분 업데이트 |
| vault 동기화 | `/slotmachine:sync` | git pull + GraphDB 증분 업데이트 |
| 지식베이스 검색 | `/slotmachine:recall` | vault 문서 RAG 검색 |
| 상태 점검 | `/slotmachine:status` | MCP·Neo4j·vault·임베딩 전체 상태 확인 |
| 초기 설정 | `/slotmachine:config` | vault 경로, Neo4j, 임베딩 프로바이더 설정 |
| 스키마 초기화 | `/slotmachine:init` | Neo4j 스키마 생성 + vault 전체 적재 |

---

## 사전 요구사항

- [Claude Code](https://claude.ai/code) CLI
- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (또는 `pip`)
- Neo4j (직접 실행 필요) — 아래 중 하나:
  - **Docker**: `docker run -d --name slotmachine-neo4j -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=neo4j/your-password neo4j:5`
  - **로컬 설치**: [Neo4j Desktop](https://neo4j.com/download/)
  - **클라우드**: [Neo4j Aura](https://neo4j.com/cloud/platform/aura-graph-database/)
- 임베딩 API 키 — 아래 중 하나:
  - [Jina AI](https://jina.ai/) (기본값, 무료 티어 있음)
  - OpenAI / Voyage AI / Google Gemini / Ollama (로컬)

---

## 설치

### 1. 플러그인 설치

Claude Code에서 아래 순서로 실행한다.

```
/plugin marketplace add JeekLee/slotmachine
/plugin install slotmachine@jeeklee
```

MCP 서버 첫 실행 시 `.venv`를 자동으로 생성하고 의존성을 설치한다.

> **로컬 개발 시**: `claude --plugin-dir ./slotmachine` 으로 바로 테스트할 수 있다.

### 2. 초기 설정

Claude Code에서 실행:

```
/slotmachine:config
```

필수 입력값:
- `vault_path`: Obsidian vault 절대 경로
- `neo4j_password`: Neo4j 비밀번호
- 임베딩 프로바이더 API 키

> Neo4j는 `/slotmachine:config` 실행 전에 직접 기동해두어야 한다.

### 3. 스키마 초기화 및 vault 적재

```
/slotmachine:init
```

Neo4j 스키마를 생성하고 vault 전체 문서를 GraphDB에 적재한다. **최초 1회만 실행**.

---

## 사용법

### INBOX 자동 분류 🎰

```
/slotmachine:inbox
```

```
INBOX에 5개의 문서가 있습니다.

#   문서명
──────────────────────────────
1   앱_출시_체크리스트.md
2   독서노트_원칙.md
3   아이디어_메모.md

전체 분류: [Enter] / 특정 문서 선택: 번호 입력 (예: 1 3) / 취소: N

> [Enter]

5개 문서 분류 결과:

#  문서명                    카테고리   배치 위치                  확신도  근거
─────────────────────────────────────────────────────────────────────────
1  앱_출시_체크리스트.md     Projects  20_Projects/Obsidian       높음    마감 기한과 구체적 태스크 포함
2  독서노트_원칙.md           Resources 40_Resources/Books         높음    참고 자료성 내용
3  아이디어_메모.md           Inbox     (유지)                     낮음    내용이 모호해 판단 보류

승인하시겠습니까? [Y / 번호: 수정 / N: 취소]

> Y

✅ 2개 문서 이동 완료.
커밋: a1b2c3d4 — chore: PARA classify 2 inbox items [SlotMachine]
```

### vault 저장 및 동기화

```
/slotmachine:save   # 작업 후 저장 + push + GraphDB 반영
/slotmachine:sync   # 원격 변경사항 pull + GraphDB 반영
```

### 위키링크 자동 제안 🔗

```
/slotmachine:link
```

대상 문서와 관련된 vault 문서를 벡터 유사도 + 그래프 근접성으로 탐색하고, 승인된 문서를 `[[위키링크]]` 형태로 삽입한다.

```
"my_project.md"의 관련 문서 후보 3개:

#   제목                       카테고리    점수
─────────────────────────────────────────────
1   클린코드_요약               Resources  0.87
2   아키텍처_패턴_노트           Resources  0.81
3   2024_리팩토링_프로젝트       Projects   0.76

삽입할 항목을 선택하세요.
[Enter: 전체 삽입 / 번호: 선택 삽입 / N: 취소]

> 1 2

✅ 2개 위키링크 삽입 완료.
커밋: a1b2c3d4 — chore: add 2 wiki links to my_project [SlotMachine]
```

### 개인 지식베이스 검색

```
/slotmachine:recall 검색할 질문이나 키워드
```

vault 문서를 RAG로 검색해 관련 내용과 출처 링크를 제공한다. `Projects` 카테고리만 검색하려면 `para_filter`를 지정할 수 있다.

---

## 임베딩 프로바이더

| 프로바이더 | 기본 모델 | API 키 환경변수 |
|-----------|----------|----------------|
| `jina` (기본값) | `jina-embeddings-v3` | `JINA_API_KEY` |
| `openai` | `text-embedding-3-small` | `OPENAI_API_KEY` |
| `voyage` | `voyage-3` | `VOYAGE_API_KEY` |
| `gemini` | `text-embedding-004` | `GEMINI_API_KEY` |
| `ollama` | `nomic-embed-text` | — (로컬 서버) |

> **주의**: 프로바이더 변경 시 벡터 차원이 달라지므로 `/slotmachine:init` 재실행이 필요하다.

---

## PARA 폴더 구조

기본값:

```
vault/
├── INBOX/          ← 미분류 문서 수집
├── Projects/       ← 진행 중인 프로젝트
├── Areas/          ← 지속 관리 영역
├── Resources/      ← 참고 자료
└── Archives/       ← 완료·보관
```

`/slotmachine:config`에서 각 폴더명과 카테고리별 템플릿 경로를 커스텀 설정할 수 있다.

---

## 아키텍처

```
Claude Code (MCP Plugin)
  ├── classify_inbox        — INBOX 문서 로드 (excerpt 기반)
  ├── get_document_contents — 배치 단위 full_content 로드
  ├── get_templates         — 필요한 카테고리 템플릿만 로드
  ├── apply_classification  — 파일 이동 + git commit
  ├── suggest_links         — 관련 문서 탐색 (벡터 + 그래프 근접성)
  ├── apply_links           — 위키링크 삽입 + git commit
  ├── save_vault            — git push + GraphDB 증분 업데이트
  ├── sync_vault            — git pull + GraphDB 증분 업데이트
  ├── recall                — 벡터/키워드 검색 → RAG 컨텍스트 반환
  └── status_check          — 전체 컴포넌트 상태 점검

GraphDB (Neo4j)
  └── Document 노드 — 임베딩, 태그, 위키링크, PARA 카테고리
        ├── LINKS_TO   (위키링크)
        ├── TAGGED_WITH
        ├── IN_FOLDER
        └── RELATED_TO (유사도 기반, suggest_links가 자동 생성)
```

설정 파일: `~/.slotmachine/settings.env`

---

## 개발

```bash
# 의존성 설치
uv sync

# 테스트
uv run pytest

# MCP 서버 직접 실행
uv run python -m slotmachine.server
```

---

## 라이선스

MIT
