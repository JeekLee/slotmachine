# SlotMachine PRD
**Product Requirements Document**
버전 1.0 | 작성일: 2025-06 | 상태: Draft

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [배경 및 문제 정의](#2-배경-및-문제-정의)
3. [프로젝트 목표](#3-프로젝트-목표)
4. [타겟 사용자](#4-타겟-사용자)
5. [핵심 가치 제안](#5-핵심-가치-제안)
6. [주요 기능 (Features)](#6-주요-기능-features)
7. [기능 상세 요구사항](#7-기능-상세-요구사항)
8. [기술 아키텍처 개요](#8-기술-아키텍처-개요)
9. [릴리즈 로드맵](#9-릴리즈-로드맵)
10. [Task Breakdown](#10-task-breakdown)
11. [리스크 및 제약사항](#11-리스크-및-제약사항)
12. [성공 지표 (KPI)](#12-성공-지표-kpi)
13. [용어 정의](#13-용어-정의)

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | SlotMachine |
| 유형 | MCP 기반 ClaudeCode 플러그인 |
| 개발 언어 | Python 3.11+ |
| 핵심 기술 | GraphDB, RAG, LLM (Claude), Git Webhook |
| 대상 플랫폼 | ClaudeCode (CLI 환경) |
| 연동 도구 | Obsidian, Git Repository, GraphDB (Neo4j 등) |

### 한 줄 정의

> **"나의 모든 지식을 Claude가 기억하는 Second Brain — INBOX에 쌓인 문서는 슬롯머신 돌리듯 한 번에 정리된다."**

---

## 2. 배경 및 문제 정의

### 2.1 현상 (As-Is)

지식 근로자들은 Obsidian과 같은 개인 지식관리(PKM) 도구를 활용해 방대한 문서와 아이디어를 축적한다. 그러나 다음과 같은 고질적인 문제가 반복된다.

- **지식의 고립**: Claude를 비롯한 AI 어시스턴트는 사용자의 개인 지식베이스를 전혀 모른다. 매번 컨텍스트를 복붙해야 하며, 나만의 맥락이 반영된 답변을 받기 어렵다.
- **INBOX 적체**: 빠르게 캡처한 메모, 스크랩, 아이디어가 INBOX에 쌓이지만, 이를 PARA 구조로 정리하는 일은 번거롭고 미뤄지기 쉽다. 결국 INBOX는 블랙홀이 된다.
- **단절된 노트**: 새로 작성한 문서가 기존 지식과 연결되지 못하고 고립된다. 잠재적으로 연관된 문서들이 있어도 수동으로 링크를 걸어주지 않으면 발견되지 않는다.
- **출처 불명의 답변**: AI가 답변을 줘도 "어떤 내 문서를 근거로 했는가"를 알 수 없어 신뢰도가 떨어진다.

### 2.2 원인 분석

| 문제 | 근본 원인 |
|------|----------|
| AI가 개인 지식을 모름 | 개인 문서를 AI가 접근·검색할 수 있는 구조가 없음 |
| INBOX 적체 | 분류 기준(PARA)을 적용하는 수동 작업 비용이 너무 높음 |
| 노트 간 단절 | 관련성 탐색이 수동이며, 링크 삽입도 수작업 |
| 출처 불명 | RAG 파이프라인 부재, 컨텍스트 추적 불가 |

---

## 3. 프로젝트 목표

### 3.1 비전

> Obsidian vault를 **살아있는 Second Brain**으로 만든다.  
> 지식은 자동으로 연결되고, AI는 그 뇌를 통해 나처럼 생각하며 대답한다.

### 3.2 목표 (To-Be)

1. **Claude가 나의 지식베이스를 안다**: Obsidian 문서 전체를 GraphDB에 저장하고, 질문 시 관련 문서를 RAG로 검색해 맥락 있는 답변을 생성한다.
2. **INBOX는 슬롯머신처럼 한 번에 정리된다**: 쌓인 INBOX 문서를 실행 한 번으로 PARA 분류 → 관련 링크 삽입 → 배치까지 자동 처리한다. 마치 슬롯머신 레버를 당기면 결과가 나오듯, 복잡한 정리 작업이 단숨에 완료된다.
3. **지식은 자동으로 연결된다**: 신규 문서 추가 시 기존 지식과의 관련성을 분석해 Obsidian 위키링크를 자동 제안한다.
4. **답변에는 항상 근거가 따라온다**: 생성된 모든 답변에 참조한 내 문서의 링크를 함께 제공한다.

### 3.3 범위 (Scope)

**In Scope**
- Obsidian vault를 담은 git repository 연동
- GraphDB 기반 문서 저장 및 검색
- git push 기반 자동 동기화
- INBOX 문서 PARA 자동 분류
- 문서 간 관련성 분석 및 위키링크 제안
- RAG 기반 답변 생성 및 출처 제공

**Out of Scope (v1.0)**
- Obsidian 플러그인 직접 개발 (파일 시스템 접근 방식 사용)
- 다중 사용자 / 팀 협업 기능
- Obsidian 외 다른 PKM 도구 지원 (Notion, Logseq 등)
- 모바일 환경 지원

---

## 4. 타겟 사용자

### Primary User

| 항목 | 내용 |
|------|------|
| 페르소나 | Obsidian을 메인 PKM으로 사용하는 개발자 / 지식 근로자 |
| 기술 수준 | git 사용 경험 있음, CLI 환경에 익숙 |
| 핵심 니즈 | AI와 함께 개인 지식을 활용하고 싶다 |
| 페인포인트 | INBOX 정리가 밀린다, 노트가 연결이 안 된다, AI가 내 맥락을 모른다 |

### Secondary User

| 항목 | 내용 |
|------|------|
| 페르소나 | Second Brain / PARA 방법론에 관심 있는 생산성 추구자 |
| 기술 수준 | git 기본 사용 가능, CLI 사용 가능 |
| 핵심 니즈 | 지식 정리 자동화, 스마트한 노트 연결 |

---

## 5. 핵심 가치 제안

### 5.1 Second Brain, Now Powered by AI

기존 Second Brain 방법론(PARA, Zettelkasten 등)은 사용자가 모든 연결과 분류를 직접 수행해야 했다. SlotMachine은 이 수작업을 AI가 대신하면서, 개인의 Obsidian vault를 **Claude가 실시간으로 접근·활용할 수 있는 살아있는 지식 엔진**으로 전환한다.

```
기존: 내가 → 문서 작성 → 수동 분류 → 수동 링크 → Claude에 직접 전달
SlotMachine: 내가 → 문서 작성 → (자동 분류 + 자동 링크 + GraphDB 저장) → Claude가 알아서 참조
```

### 5.2 INBOX를 슬롯머신처럼

> INBOX에 쌓인 문서들, 정리하려다 또 미뤘는가?  
> SlotMachine의 레버를 당겨라. 분류, 연결, 배치가 한 번에 끝난다.

| 기존 방식 | SlotMachine |
|----------|-------------|
| INBOX 문서를 하나씩 열어서 내용 파악 | 일괄 분석 후 분류 결과 한 번에 제시 |
| PARA 카테고리를 직접 판단 | LLM이 PARA 분류 및 근거 제공 |
| 관련 문서 직접 찾아서 링크 삽입 | 관련 문서 자동 탐색 및 링크 제안 |
| 파일 직접 이동 | 승인 한 번으로 자동 이동 및 git commit |

### 5.3 가치 요약

| 가치 | 설명 |
|------|------|
| 🧠 Second Brain 실현 | Claude가 나의 지식베이스를 기억하고 맥락 있게 대답 |
| 🎰 Zero-friction 정리 | INBOX 적체 문제를 슬롯머신 한 번으로 해결 |
| 🔗 자동 지식 연결 | 새 문서와 기존 지식의 관련성을 자동으로 연결 |
| 📎 투명한 근거 | 모든 답변에 참조 문서 링크 제공 |
| ⚡ 실시간 동기화 | git push만 해도 지식베이스가 자동 업데이트 |

---

## 6. 주요 기능 (Features)

| # | Feature | 설명 | 우선순위 |
|---|---------|------|----------|
| F1 | Git Repository 연동 및 GraphDB 저장 | Obsidian vault를 GraphDB에 구조화 저장 | P0 |
| F2 | Push 기반 실시간 동기화 | git push 시 변경사항 자동 반영 | P0 |
| F3 | INBOX PARA 자동 분류 | INBOX 문서를 LLM이 PARA로 자동 분류 | P0 |
| F4 | 문서 간 관련성 분석 및 자동 링크 | 신규 문서와 기존 문서의 관련성 탐색 및 위키링크 제안 | P1 |
| F5 | RAG 기반 답변 + 출처 제공 | GraphDB 검색 기반 맥락 포함 답변 생성 | P0 |

---

## 7. 기능 상세 요구사항

---

### F1. Git Repository 연동 및 GraphDB 저장

#### 목적
Obsidian vault가 있는 git repository를 등록하고, 모든 Markdown 문서를 GraphDB의 노드/엣지 구조로 변환·저장한다. 이것이 SlotMachine Second Brain의 물리적 기반이다.

#### 기능 요구사항

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| F1-01 | git remote URL 등록 (SSH / Personal Access Token 인증 지원) | Must |
| F1-02 | Markdown 파일 파싱: 제목, 태그, 본문, 내부 링크([[…]]), 생성일/수정일 추출 | Must |
| F1-03 | 문서 → GraphDB 노드 변환, 내부 링크·태그·폴더 구조 → 엣지 변환 | Must |
| F1-04 | 초기 Full Sync: 전체 vault를 GraphDB에 일괄 적재 | Must |
| F1-05 | 문서 임베딩(벡터) 생성 및 GraphDB에 저장 — 다중 프로바이더 지원 (Jina / Voyage / OpenAI / Gemini / Ollama) | Must |
| F1-06 | Sync 진행률 표시 (대용량 vault 대응) | Should |
| F1-07 | 멀티 vault 지원 (복수의 git repo 등록) | Could |

#### GraphDB 스키마 (개요)

```
Node: Document
  - id: string (파일 경로 기반 hash)
  - title: string
  - path: string
  - content: string
  - tags: string[]
  - created_at: datetime
  - updated_at: datetime
  - embedding: float[] (벡터)
  - para_category: enum (Projects | Areas | Resources | Archives | Inbox)

Edge: LINKS_TO       (문서 → 문서, 내부 위키링크)
Edge: TAGGED_WITH    (문서 → 태그 노드)
Edge: IN_FOLDER      (문서 → 폴더 노드)
Edge: RELATED_TO     (문서 → 문서, 유사도 기반 자동 생성)
```

---

### F2. Plugin-driven Git Save / Sync

#### 목적
MCP 플러그인이 git 작업을 직접 수행해 GraphDB를 최신 상태로 유지한다.
사용자는 `save` 커맨드로 문서를 저장·push하고, `sync` 커맨드로 원격 변경사항을 로컬 GraphDB에 반영한다.
임베딩 및 GraphDB 반영 대상은 **main 브랜치에 커밋·머지된 문서에 한정**한다.

#### 설계 결정 (ADR-001)

Webhook 서버 방식을 폐기하고 Plugin-driven Git 방식을 채택. 상세 근거: `docs/planning/decisions/ADR-001-f2-git-sync-strategy.md`

#### 기능 요구사항

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| F2-01 | `save` 커맨드: git add + 자동 커밋 메시지 생성 + push to main | Must |
| F2-02 | `save` 후 GraphDB 증분 업데이트 — push된 커밋의 변경 파일 즉시 반영 | Must |
| F2-03 | `sync` 커맨드: git pull origin main + GraphDB 증분 업데이트 | Must |
| F2-04 | git diff 분석 모듈 — pull/push 전후 HEAD 비교로 생성/수정/삭제 .md 파일 식별 | Must |
| F2-05 | 삭제 문서의 GraphDB 노드 및 관련 엣지 제거 | Must |
| F2-06 | 동기화 이력 로그 저장 — sqlite3 기반 (성공/실패/변경 수) | Must |
| F2-07 | 동기화 실패 시 재시도 — tenacity 기반 자동 재시도 | Should |
| F2-09 | sync 중 삭제 감지 시 다른 문서 본문의 `[[삭제된_제목]]` 위키링크 제거 | Should |

#### 동기화 플로우

```
[save]
  사용자: /slotmachine:save
    └─► git add .
          └─► git commit (자동 메시지)
                └─► git push origin main
                      └─► push 전후 diff 분석
                            ├─► 생성/수정 파일 → GraphDB upsert + 임베딩 생성
                            └─► 삭제 파일 → GraphDB 노드 및 엣지 제거

[sync]
  사용자: /slotmachine:sync
    └─► git pull origin main
          └─► pull 전후 diff 분석
                ├─► 생성/수정 파일 → GraphDB upsert + 임베딩 갱신
                └─► 삭제 파일 → GraphDB 노드 및 엣지 제거
```

---

### F3. INBOX PARA 자동 분류 (🎰 핵심 SlotMachine 경험)

#### 목적
INBOX에 쌓인 문서들을 한 번의 명령으로 PARA 구조로 자동 분류·정리한다. 슬롯머신 레버를 당기는 것처럼, 복잡한 정리 작업이 단숨에 처리되는 핵심 경험을 제공한다.

#### 배경: PARA 방법론

| 카테고리 | 정의 | 예시 |
|----------|------|------|
| Projects | 마감 기한이 있는 현재 진행 중인 작업 | "Q3 보고서 작성", "앱 출시 준비" |
| Areas | 지속적으로 관리가 필요한 영역 | "건강", "재무", "커리어" |
| Resources | 미래에 유용할 수 있는 참고 자료 | "읽은 책 요약", "기술 아티클" |
| Archives | 완료되었거나 더 이상 활성화되지 않은 항목 | 완료된 프로젝트, 오래된 노트 |

#### 기능 요구사항

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| F3-01 | INBOX 폴더 경로 설정 및 감지 | Must |
| F3-02 | INBOX 내 전체 문서에 대해 LLM 기반 PARA 분류 수행 | Must |
| F3-03 | 분류 결과와 근거(왜 이 카테고리인지) 사용자에게 제시 | Must |
| F3-04 | 사용자 일괄 승인 또는 개별 수정 후 파일 이동 실행 | Must |
| F3-05 | 파일 이동 후 자동 git commit (커밋 메시지 자동 생성) | Must |
| F3-06 | 분류 확신도(confidence score) 표시, 낮으면 사용자 판단 요청 | Should |
| F3-07 | 분류 이력 저장 및 사용자 피드백 반영한 분류 품질 개선 | Could |
| F3-09 | 분류 시 파일명 자동 제안 — 관련 문서 파일명 패턴 우선, fallback은 목적지 폴더 기존 파일명 패턴 참고 | Should |
| F3-10 | F3-09 rename 실행 시 다른 문서 본문의 `[[구_제목]]` → `[[새_제목]]` 일괄 교체 | Should |

#### 사용자 경험 시나리오

```
사용자: slotmachine inbox

[SlotMachine 🎰]
INBOX에서 7개의 문서를 발견했습니다. 분류를 시작합니다...

──────────────────────────────────────────────────────────────────────────────────
 #  현재 파일명                분류          확신도  제안 파일명                     참고 기준
──────────────────────────────────────────────────────────────────────────────────
 1  앱_출시_체크리스트.md     Projects ✅   95%    2024_앱출시_체크리스트.md        동일폴더 패턴
 2  독서노트_원칙.md           Resources ✅  90%    원칙_Principles_독서노트.md      관련문서 패턴
 3  아이디어_메모.md           Inbox  ⚠️    45%    (확인 필요 — 제안 보류)          -
 4  건강관리_루틴.md           Areas ✅      88%    건강_관리루틴_Daily.md           동일폴더 패턴
 5  2023_프로젝트A_회고.md    Archives ✅   92%    2023_프로젝트A_회고.md           변경 불필요
 6  클린코드_요약.md           Resources ✅  87%    CleanCode_요약_Martin.md         관련문서 패턴
 7  오늘할일.md                Projects ✅   78%    2024-03_오늘할일.md              동일폴더 패턴

6개 자동 분류 완료. #3은 직접 확인이 필요합니다.
승인하시겠습니까? [전체 승인: Y / 개별 수정: E / 취소: N]

> Y

✅ 6개 문서 이동 및 파일명 변경 완료.
   git commit: "chore: PARA classify 6 inbox items [SlotMachine]"
```

#### F3-09 파일명 자동 제안 상세

파일명 제안은 다음 우선순위로 동작한다.

| 우선순위 | 조건 | 동작 |
|---------|------|------|
| 1 | 유사도 threshold 이상의 관련 문서 존재 | 관련 문서들의 파일명 패턴·구조를 LLM이 학습해 제안 |
| 2 | 관련 문서 없음 (threshold 미달) | 목적지 PARA 폴더 내 기존 문서 파일명 패턴 참고 |
| 3 | 목적지 폴더가 비어있거나 패턴 파악 불가 | 기존 파일명 유지 |

- 파일명 변경은 파일 이동과 동시에 처리 (rename + move)
- 사용자는 개별 수정(`E`) 시 파일명도 직접 편집 가능
- 기존 파일명이 이미 적절하다고 판단되면 "변경 불필요"로 표시

---

### F4. 문서 간 관련성 분석 및 자동 링크

#### 목적
새로 추가되거나 INBOX에서 분류된 문서와 기존 지식베이스 간의 관련성을 자동 탐색하고, Obsidian 위키링크([[…]])를 제안·삽입한다. Second Brain의 신경망을 자동으로 강화한다.

#### 링크 정책

| 정책 | 결정 내용 |
|------|---------|
| Archives 격리 | Archives 문서는 링크 후보 및 relink 피벗에서 완전 제외. 역방향 링크 삽입도 하지 않음. 기존 링크는 유지. |
| 기본 threshold | **0.65** — 문서당 태그 5~7개 환경에서 우연한 태그 중복(+0.15 boost)을 감안한 값. 순수 벡터 유사도 0.50 이상은 돼야 통과. |
| threshold 방향 | 단일값 유지 (카테고리별 차등 없음). vault 초반엔 0.50으로 낮춰 쓰다가 문서가 쌓이면 올리는 패턴 권장. |
| 링크 거절 기억 | v1.0 범위 외. 사용 중 필요 시 추가 (Could). |

#### 기능 요구사항

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| F4-01 | 대상 문서에 대해 GraphDB 벡터 검색으로 유사 문서 탐색 | Must |
| F4-02 | 그래프 근접성(공통 태그, 공통 링크)을 함께 고려한 관련도 계산 | Must |
| F4-03 | 관련도 임계값(threshold) 이상의 문서만 링크 후보로 제안 — 기본값 0.65 | Must |
| F4-04 | 링크 삽입 위치: `## Related` 섹션 끝에 추가. 섹션 없으면 파일 끝에 신규 생성 | Must |
| F4-05 | 이미 존재하는 링크 중복 삽입 방지 | Must |
| F4-07 | 관련성 임계값 사용자 설정 가능 | Should |
| F4-08 | `/slotmachine:relink` — 링크 재판단 커맨드 | Should |

#### F4-08 링크 재판단 상세

vault에 문서가 추가·변경될수록 기존 문서와의 연관관계가 누락될 수 있다. `/slotmachine:relink`는 이를 보완하기 위한 on-demand 재판단 커맨드다.

**핵심 설계 원칙**
- 신규/변경 문서를 **피벗**으로 `find_related`를 실행한다. 기존 문서를 개별 재탐색하지 않는다.
- 링크는 **단방향**으로만 삽입한다. 피벗 문서 → 관련 문서 방향만. 역방향(기존 문서 → 피벗)은 해당 문서를 직접 열어 `suggest_links`로 별도 실행한다.
- 임베딩은 GraphDB에 저장된 벡터를 재사용하므로 **임베딩 API 호출 없음**, **LLM 호출 없음**.

**두 가지 모드**

| 모드 | 커맨드 | 대상 | 비용 |
|------|--------|------|------|
| Delta (기본) | `/slotmachine:relink` | 마지막 재판단 이후 추가·변경된 문서 | O(변경 문서 수) Neo4j 쿼리 |
| Full | `/slotmachine:relink --all` | 전체 vault | O(전체 문서 수) Neo4j 쿼리, 진행률 표시 |

**세부 요구사항**

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| F4-08-01 | Document 노드에 `links_evaluated_at` 타임스탬프 추가 — `apply_links` 실행 시 자동 갱신 | Must |
| F4-08-02 | Delta 모드: `links_evaluated_at`가 없거나 문서 `updated_at` 이후인 문서를 피벗으로 선별 | Must |
| F4-08-03 | 피벗 문서 기준 `find_related` 실행 → 피벗→후보 단방향 링크로 제안 | Must |
| F4-08-04 | Full 모드: 실행 전 대상 문서 수 및 예상 소요 시간 표시 후 사용자 확인 | Must |
| F4-08-05 | 배치 결과를 문서별 테이블로 표시 (문서명 / 신규 링크 후보 수 / 방향) | Must |
| F4-08-06 | 전체 승인 / 개별 수정 / 취소 인터랙션 — `apply_links` 기존 플로우 재사용 | Must |
| F4-08-07 | `--para` 옵션으로 PARA 카테고리 범위 지정 가능 | Should |
| F4-08-08 | Full 모드 진행률 표시 | Should |

---

### F5. RAG 기반 답변 + 출처 링크 제공

#### 목적
ClaudeCode 내에서 질문 시 GraphDB에서 관련 문서를 검색해 컨텍스트로 활용하고, 나의 지식베이스에 기반한 맥락 있는 답변을 생성한다. 모든 답변에는 참조한 문서의 Obsidian 링크가 첨부된다.

#### 기능 요구사항

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| F5-01 | 사용자 질의에 대해 GraphDB 벡터 검색으로 관련 문서 검색 | Must |
| F5-02 | 검색된 문서를 MCP 툴 응답으로 반환 → Claude Code(호스트)가 컨텍스트에 포함하여 답변 생성 (MCP 서버가 Claude API 직접 호출하지 않음) | Must |
| F5-03 | 답변 하단에 참조 문서 목록 및 Obsidian URI 링크 제공 | Must |
| F5-04 | 관련 문서가 없을 경우 "개인 지식베이스 참조 없음" 명시 | Must |
| F5-05 | 검색 결과 문서 수 및 관련도 점수 표시 옵션 | Should |
| F5-06 | 컨텍스트 토큰 제한 내에서 가장 관련도 높은 문서 우선 선택 | Must |
| F5-07 | 특정 PARA 카테고리 내에서만 검색하는 범위 지정 옵션 | Could |

#### 답변 형식 예시

```
[SlotMachine 🧠 Second Brain 참조 중...]
관련 문서 3개 발견 (유사도: 0.91, 0.87, 0.83)

───────────────────────────────────
[답변 내용]
...클린 아키텍처 관점에서 보면, 의존성 역전 원칙을 적용하여...

📎 참조 문서:
  - [[클린코드_요약]] obsidian://open?vault=MyVault&file=클린코드_요약
  - [[아키텍처_패턴_노트]] obsidian://open?vault=MyVault&file=아키텍처_패턴_노트
  - [[2024_리팩토링_프로젝트]] obsidian://open?vault=MyVault&file=2024_리팩토링_프로젝트
───────────────────────────────────
```

---

## 8. 기술 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────┐
│                     ClaudeCode (MCP Plugin)                  │
│                                                              │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  CLI     │  │  Sync        │  │  RAG Engine            │  │
│  │  Commands│  │  Service     │  │  (Query → Retrieve     │  │
│  │          │  │              │  │   → Generate)          │  │
│  └────┬─────┘  └──────┬───────┘  └──────────┬────────────┘  │
│       │               │                     │               │
└───────┼───────────────┼─────────────────────┼───────────────┘
        │               │                     │
        ▼               ▼                     ▼
┌───────────────────────────────────────────────────────────┐
│                      GraphDB (Neo4j)                       │
│          Documents · Tags · Folders · Embeddings           │
└───────────────────────────────┬───────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
      ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
      │  Git Repo    │  │ Claude API   │  │  Obsidian    │
      │  (Obsidian   │  │              │  │  Vault       │
      │   Vault)     │  └──────────────┘  │  (File sys)  │
      └──────────────┘                   └──────────────┘
```

### 기술 스택 (권장)

| 레이어 | 기술 선택 | 비고 |
|--------|----------|------|
| MCP Plugin | Python 3.11+ | `mcp` SDK (Anthropic 공식 Python SDK) |
| MCP 서버 프레임워크 | `fastmcp` or `anthropic-mcp` | Python MCP 서버 구현 표준 |
| GraphDB | Neo4j (로컬 우선) + `neo4j` Python 드라이버 | Amazon Neptune (클라우드 옵션) |
| 임베딩 모델 | Provider 추상화 레이어 — Jina / Voyage / OpenAI / Gemini / Ollama | 프로바이더 변경 시 벡터 차원 고정으로 Full Re-sync 필요 |
| Git 연동 | `gitpython` | Python 기반 git 제어 |
| 파일 파싱 | `python-frontmatter` + `mistletoe` or `markdown-it-py` | Markdown AST 파싱 |
| HTTP 서버 (Webhook) | `fastapi` + `uvicorn` | 경량 비동기 웹 서버 |
| 설정 관리 | `pydantic-settings` + YAML | `~/.slotmachine/config.yaml` |
| 패키지 관리 | `uv` or `poetry` | 의존성 관리 및 빌드 |
| 테스트 | `pytest` + `pytest-asyncio` | 비동기 테스트 지원 |

---

## 9. 릴리즈 로드맵

### Milestone 개요

| Phase | 기간 | 목표 | 포함 Feature |
|-------|------|------|-------------|
| Phase 1: Foundation | Sprint 1~2 | 기반 인프라 구축 | F1 (full sync) |
| Phase 2: Live Sync | Sprint 3 | 실시간 동기화 | F2 |
| Phase 3: SlotMachine Core | Sprint 4 | INBOX 자동 분류 | F3 |
| Phase 4: Knowledge Graph | Sprint 5 | 자동 링크 연결 | F4 |
| Phase 5: Second Brain RAG | Sprint 6 | RAG 답변 + 출처 | F5 |
| Phase 6: Polish & Beta | Sprint 7 | 통합 테스트, UX 개선, 문서화 | 전체 |

---

## 10. Task Breakdown

### Phase 1: Foundation (F1 — Git 연동 및 GraphDB 저장)

- [ ] MCP 서버 기본 프로젝트 구조 셋업 (Python 3.11+, `uv` or `poetry` 환경)
- [ ] `slotmachine init` 커맨드 구현 (git URL, 인증, vault 경로 설정)
- [ ] SSH / PAT 인증 처리 및 자격증명 안전 저장 (`keyring` 라이브러리 활용)
- [ ] Markdown 파일 파서 구현 (`python-frontmatter` + `mistletoe`, 제목/태그/내부링크 추출)
- [ ] GraphDB 스키마 설계 및 Neo4j 연결 모듈 구현 (`neo4j` Python 드라이버)
- [ ] Document → 노드 변환 / 내부링크·태그 → 엣지 변환 로직
- [ ] 임베딩 생성 모듈 구현 (`anthropic` SDK Embeddings API 연동)
- [ ] Full Sync 파이프라인 구현 (비동기 배치 처리 + `tqdm` 진행률 표시)
- [ ] 단위 테스트: `pytest` 기반 파서, 변환 로직, DB 저장

### Phase 2: Live Sync (F2 — Push 동기화)

- [ ] Webhook 수신 서버 구현 (`fastapi` + `uvicorn`, 로컬 or ngrok 지원)
- [ ] `gitpython` 기반 git diff 분석 모듈: 생성/수정/삭제 파일 식별
- [ ] 증분 업데이트 로직 구현 (변경 파일만 GraphDB 반영)
- [ ] 삭제 문서 처리: 노드 제거 + 관련 엣지 정리
- [ ] Sync 이력 로그 저장 (`sqlite3` 내장 모듈 활용)
- [ ] `slotmachine status` 커맨드 구현
- [ ] 오류 처리 및 재시도 로직 (`tenacity` 라이브러리)
- [ ] 통합 테스트: push 시나리오 end-to-end (`pytest-asyncio`)

### Phase 3: SlotMachine Core (F3 — INBOX 분류)

- [ ] PARA 분류 프롬프트 설계 및 반복 튜닝
- [ ] INBOX 폴더 감지 및 문서 일괄 로드
- [ ] LLM 분류 결과 파싱 (카테고리 + 확신도 + 근거)
- [ ] CLI 분류 결과 표시 UI (테이블 형식)
- [ ] 사용자 일괄 승인 / 개별 수정 인터랙션 구현
- [ ] 파일 이동 실행 모듈
- [ ] 이동 후 자동 git add + commit 처리
- [ ] 확신도 낮은 문서 별도 표시 및 처리 플로우
- [ ] 사용성 테스트 및 프롬프트 개선

### Phase 4: Knowledge Graph (F4 — 자동 링크)

- [ ] 벡터 유사도 검색 모듈 구현 (GraphDB 또는 벡터 DB)
- [ ] 그래프 근접성 계산 알고리즘 (공통 태그/링크 가중치)
- [ ] 관련도 임계값 설정 및 후보 필터링 로직
- [ ] 링크 삽입 위치 결정 로직 (문맥 기반)
- [ ] 중복 링크 방지 처리
- [ ] 양방향 링크 옵션 처리
- [ ] 링크 제안 → 사용자 확인 → 실제 파일 수정 플로우
- [ ] 파일 수정 후 git commit 처리

### Phase 5: Second Brain RAG (F5 — RAG 답변)

- [ ] 질의 처리 파이프라인 구현 (Query → Vectorize → Search → Generate)
- [ ] Top-K 문서 검색 및 컨텍스트 구성 로직
- [ ] 토큰 제한 내 컨텍스트 최적화 (관련도 순 우선 선택)
- [ ] Claude API 연동: 시스템 프롬프트에 컨텍스트 주입
- [ ] 출처 링크 포맷 구현 (Obsidian URI scheme)
- [ ] "참조 없음" 케이스 처리
- [ ] PARA 카테고리 범위 지정 검색 옵션
- [ ] 답변 품질 평가 기준 수립 및 내부 테스트

### Phase 6: Polish & Beta

- [ ] 전체 기능 통합 테스트
- [ ] 설정 파일 스키마 확정 및 검증
- [ ] 에러 메시지 및 사용자 가이드 메시지 정리
- [ ] README 및 사용자 문서 작성
- [ ] 설치 스크립트 (`pip install slotmachine` or `uv tool install slotmachine`) 패키징
- [ ] 베타 사용자 피드백 수집 및 반영

---

## 11. 리스크 및 제약사항

| # | 리스크 | 영향도 | 발생 가능성 | 대응 방안 |
|---|--------|--------|------------|----------|
| R1 | GraphDB 운영 비용 (클라우드 사용 시) | 중 | 중 | 로컬 Neo4j 우선 지원, 클라우드는 옵션으로 제공 |
| R2 | 대용량 vault 초기 sync 성능 | 고 | 고 | 배치 처리 + 진행률 표시, 백그라운드 실행 지원 |
| R3 | PARA 분류 정확도 | 고 | 중 | 확신도 표시 + 사용자 승인 단계 필수화, 프롬프트 반복 튜닝 |
| R4 | 자동 링크의 관련성 노이즈 | 중 | 중 | 임계값 조정 가능, 제안 형태로만 제공 (자동 삽입 금지) |
| R5 | git 인증 정보 보안 | 고 | 저 | 토큰 암호화 저장, OS keychain 활용 |
| R6 | Obsidian vault 구조 다양성 | 중 | 고 | 표준 폴더 구조 가이드 제공, 커스텀 INBOX 경로 설정 지원 |
| R7 | Claude API 토큰 비용 | 중 | 중 | 캐싱 전략, 임베딩 재사용, 불필요한 API 호출 최소화 |
| R8 | MCP 사양 변경 | 중 | 저 | 추상화 레이어로 MCP 의존성 격리 |

---

## 12. 성공 지표 (KPI)

### 정량적 지표

| 지표 | 목표 (v1.0 출시 3개월 후) |
|------|--------------------------|
| INBOX 분류 정확도 | 85% 이상 (사용자 승인율 기준) |
| Sync 소요 시간 (1,000문서 기준) | Full sync 5분 이내, 증분 sync 30초 이내 |
| RAG 답변 관련성 | 사용자 평가 4.0/5.0 이상 |
| INBOX 적체 감소 | 사용 전 대비 INBOX 문서 수 70% 감소 |

### 정성적 지표

- 사용자가 "Claude가 내 지식을 알고 있다"는 경험을 느낀다
- INBOX 정리에 소요되는 시간과 심리적 부담이 줄었다고 느낀다
- 노트 간 연결이 이전보다 풍부해졌다고 느낀다
- 답변의 출처를 확인할 수 있어 신뢰도가 높아졌다고 느낀다

---

## 13. 용어 정의

| 용어 | 정의 |
|------|------|
| Second Brain | 개인의 외부 지식 저장·관리 시스템. 디지털 노트 도구를 통해 생각, 아이디어, 정보를 체계적으로 저장하는 방법론 |
| PARA | Tiago Forte의 지식 분류 방법론. Projects / Areas / Resources / Archives |
| PKM | Personal Knowledge Management. 개인 지식관리 |
| RAG | Retrieval-Augmented Generation. 외부 지식베이스에서 관련 정보를 검색해 LLM 답변 생성에 활용하는 기술 |
| MCP | Model Context Protocol. Claude 모델과 외부 도구를 연결하는 프로토콜 |
| GraphDB | 데이터를 노드(Node)와 엣지(Edge)로 표현하는 데이터베이스. 문서 간 관계 표현에 적합 |
| Embedding | 텍스트를 수치 벡터로 변환한 표현. 의미적 유사도 계산에 사용 |
| 위키링크 | Obsidian에서 문서 간 연결을 표현하는 `[[문서명]]` 형식의 내부 링크 |
| INBOX | Obsidian에서 새로 캡처된 미분류 문서들이 임시로 저장되는 폴더 |
| Vault | Obsidian의 노트 저장소 단위. 하나의 로컬 폴더가 하나의 Vault |
| Full Sync | 전체 vault 문서를 GraphDB에 처음부터 전체 적재하는 작업 |
| Incremental Sync | 변경된 문서만 GraphDB에 반영하는 증분 업데이트 방식 |

---

*본 PRD는 SlotMachine v1.0 개발의 기준 문서입니다. 변경 사항 발생 시 버전을 업데이트하고 변경 이력을 관리합니다.*

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.7 | 2026-03-20 00:00:00 | 링크 단방향 정책 확정 — F4-06 양방향 옵션 삭제, relink 양방향 로직 제거 | pm |
| 1.6 | 2026-03-20 00:00:00 | 죽은 링크 정책 확정 — SlotMachine 직접 rename/delete 시에만 처리, Obsidian 조작은 Obsidian에 위임. F2-09, F3-10 추가 | pm |
| 1.5 | 2026-03-20 00:00:00 | F4 링크 정책 확정 — Archives 완전 격리, threshold 기본값 0.65, F4-04 삽입 위치 구현 기준으로 수정 | pm |
| 1.4 | 2026-03-20 00:00:00 | F4-08 추가 — `/slotmachine:relink` 링크 재판단 커맨드 (신규 문서 피벗·양방향·Delta/Full 모드) | pm |
| 1.3 | 2026-03-19 00:00:00 | F3-09 추가 — 분류 시 파일명 자동 제안 (관련문서 패턴 우선, fallback: 목적지 폴더 패턴) | pm |
| 1.2 | 2026-03-13 13:23:16 | F1-05 임베딩 프로바이더 확정 — Jina / Voyage / OpenAI / Gemini / Ollama | infra+pm |
| 1.1 | 2026-03-13 13:12:46 | F1-05 임베딩 다중 프로바이더 지원으로 수정, F5-02 MCP 설계 원칙 반영 (서버가 Claude API 직접 호출 않음) | infra+pm |
| 1.0 | 2025-06-01 00:00:00 | 최초 작성 | - |
