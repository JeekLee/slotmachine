# 인프라 아키텍처

---

## 전체 구성도

```
┌─────────────────────────────────────────────────────────┐
│                  ClaudeCode (MCP Plugin)                │
│   server.py (fastmcp)                                   │
│   ┌──────────┐  ┌─────────────┐  ┌───────────────────┐  │
│   │ CLI      │  │ Sync Service│  │ RAG Engine        │  │
│   └────┬─────┘  └──────┬──────┘  └────────┬──────────┘  │
└────────┼───────────────┼─────────────────┼──────────────┘
         │               │                 │
         ▼               ▼                 ▼
┌─────────────────────────────────────────────────────────┐
│                   Neo4j (로컬 Docker)                    │
│         Document 노드 · 태그 엣지 · 임베딩 벡터             │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│  Git Repo   │  │ Claude API  │  │ Obsidian     │
│ (Obsidian   │  │ (Embeddings │  │ Vault        │
│  Vault)     │  │  + Chat)    │  │ (파일 시스템)  │
└─────────────┘  └─────────────┘  └──────────────┘
```

---

## 환경별 구성

| 항목 | Local | Production (향후) |
|------|-------|-----------------|
| Neo4j | Docker Compose (로컬) | Amazon Neptune or Neo4j AuraDB |
| Webhook 서버 | localhost:8000 | 클라우드 배포 |
| 인증 정보 | .env.local + keyring | 시크릿 매니저 |

---

## 로컬 개발 환경 세팅

### 사전 요구사항

| 항목 | 버전 | 비고 |
|------|------|------|
| Docker Desktop | 4.x+ | Docker Compose V2 포함 |
| Python | 3.11+ | uv로 관리 |
| uv | 최신 | `pip install uv` |

### Neo4j 컨테이너 구성

| 항목 | 값 |
|------|-----|
| 이미지 | `neo4j:5.18-community` |
| HTTP (Browser) | `localhost:7474` |
| Bolt (드라이버) | `localhost:7687` |
| 플러그인 | APOC |
| 데이터 저장 | Docker named volume (`neo4j_data`) |
| 인증 | `.env.local`의 `NEO4J_USERNAME` / `NEO4J_PASSWORD` |

### 환경 변수 파일

| 파일 | 용도 | 커밋 여부 |
|------|------|----------|
| `.env.example` | 템플릿 (실제 값 없음) | ✅ 커밋 |
| `.env.local` | 로컬 실제 값 | ❌ .gitignore |
| `.env.staging` | 스테이징 (향후) | ❌ .gitignore |
| `.env.production` | 프로덕션 (향후) | ❌ .gitignore |

### 기동 절차

```bash
# 1. 환경 변수 설정
cp .env.example .env.local
# .env.local 에 NEO4J_PASSWORD, ANTHROPIC_API_KEY 등 실제 값 입력

# 2. Neo4j 컨테이너 기동
docker compose up -d neo4j

# 3. 기동 확인 (브라우저)
# http://localhost:7474

# 4. Python 의존성 설치
uv sync
```

---

## 변경 이력

| 날짜 | 변경 내용 | 담당 |
|------|----------|------|
| 2026-03-13 13:23:16 | 임베딩 프로바이더 확정 — Jina / Voyage / OpenAI / Gemini / Ollama, .env 구조 업데이트 | infra |
| 2026-03-13 13:12:46 | 임베딩 다중 프로바이더 지원 반영 — .env 구조 업데이트 | infra |
| 2026-03-13 13:06:44 | 로컬 개발 환경 세팅 문서화 (Docker Compose, .env 구조) | infra |
| 2026-03-13 12:56:00 | 최초 작성 | infra |
