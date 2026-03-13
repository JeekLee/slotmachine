# Sprint 1
기간: 착수일 기준 2주
목표: Phase 1 Foundation 완료 — Git 연동 및 GraphDB 저장 파이프라인 구축

---

## In Progress

_(착수 후 이동)_



---

## Todo

_(없음 — Sprint 1 완료)_

---

## Done

- [x] [F1-04] Phase 1 통합 테스트 — parser→embed→graphdb 전 파이프라인 검증 (16개) | developer | 2026-03-13 17:00:00
- [x] [F1-05] 임베딩 생성 모듈 구현 — BaseEmbeddingProvider + Jina/Voyage/OpenAI/Gemini/Ollama + get_provider() | developer | 2026-03-13 16:30:00
- [x] [F1-04] Full Sync 파이프라인 구현 — full_sync() + SyncResult, tqdm 진행률, 오류 격리 | developer | 2026-03-13 16:00:00
- [x] [F1-03] Neo4j 연결 모듈 구현 — graphdb.py (Document/Tag/Folder CRUD, 스키마 초기화) | developer | 2026-03-13 15:30:00
- [x] [F1-03] GraphDB 스키마 설계 — Document 노드, LINKS_TO/TAGGED_WITH/IN_FOLDER 엣지 정의 | developer+infra | 2026-03-13 15:30:00
- [x] [F1-03] Document → 노드 변환 / 내부링크·태그·폴더 → 엣지 변환 로직 (upsert_document) | developer | 2026-03-13 15:30:00
- [x] [F1-02] Markdown 파서 구현 — parse_document() (제목·태그·위키링크·프론트매터 추출) | developer | 2026-03-13 15:00:00
- [x] [F1-02] 파서 단위 테스트 18개 작성 (pytest, 18/18 pass) | developer | 2026-03-13 15:00:00
- [x] [F1-01] uv 프로젝트 초기화 — pyproject.toml 재작성 (poetry → uv, 전체 의존성 정의) | developer | 2026-03-13 13:30:22
- [x] [F1-01] pydantic-settings 기반 config.py 작성 (5개 임베딩 프로바이더 지원) | developer | 2026-03-13 13:30:22
- [x] [F1-01] Neo4j 로컬 환경 설정 (Docker Compose) | infra | 2026-03-13 13:06:44
- [x] [F1-01] .env.example 작성 및 환경 변수 정의 | infra | 2026-03-13 13:06:44

---

## 블로커 / 이슈

_(발생 시 기록)_
