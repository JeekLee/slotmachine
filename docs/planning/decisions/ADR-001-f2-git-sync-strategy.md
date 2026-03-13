# ADR-001: F2 동기화 전략 — Webhook 방식 대신 Plugin-driven Git 방식 채택

- 날짜: 2026-03-13
- 상태: 결정됨 (Accepted)
- 결정자: PM + Developer

---

## 컨텍스트

PRD 초안(F2)은 git push 이벤트를 Webhook 서버로 수신해 GraphDB를 업데이트하는 서버 사이드 방식을 명시했다.
그러나 이 방식은 다음 문제를 수반한다:

- FastAPI + uvicorn 서버를 항상 실행 상태로 유지해야 함
- 로컬 환경에서 외부 수신을 위해 ngrok 등 터널링 도구가 필요
- 사용자의 git 작업(push)과 GraphDB 업데이트 사이의 의존 관계가 인프라 복잡도를 높임

## 결정

**Webhook 방식을 폐기하고, MCP 플러그인이 git 작업을 직접 수행하는 Plugin-driven Git 방식을 채택한다.**

### 커맨드 정의

| 커맨드 | 동작 | 설명 |
|--------|------|------|
| `/slotmachine:save` | `git add . → git commit → git push origin main → GraphDB 증분 업데이트` | 저장 후 push된 커밋이 곧바로 GraphDB에 반영됨 |
| `/slotmachine:sync` | `git pull origin main → diff 분석 → GraphDB 증분 업데이트` | 원격 main에 반영된 변경사항을 로컬 GraphDB에 동기화 |

### 브랜치 전략

- **main 직접 push 단순 플로우** (feature 브랜치, PR 없음)
- 단일 사용자 · 로컬 우선 환경에 최적화

### 임베딩 범위

- **main 브랜치에 commit/merge된 문서에 한해서만 임베딩 생성 및 GraphDB 반영**
- 로컬에서 작성 중인 미커밋 파일은 임베딩 대상 제외
- `sync` 실행 시 `git pull` 이후 변경된 파일만 증분 처리

## 결과

**장점**
- Webhook 서버 인프라 불필요 → 설치 및 운영 복잡도 대폭 감소
- 사용자 의도(저장 / 동기화)가 커맨드로 명확히 분리됨
- "main에 올라간 것만 지식베이스" — Second Brain 철학에 부합 (초안·WIP 제외)

**단점 / 트레이드오프**
- 자동 동기화 없음: 사용자가 명시적으로 `sync`를 실행해야 GraphDB가 업데이트됨
- Webhook 기반 자동화 확장(CI/CD 연동 등)이 필요해질 경우 별도 재설계 필요

## 대안 검토

| 대안 | 기각 이유 |
|------|---------|
| Webhook + FastAPI 서버 | 항상 실행 상태 유지 필요, ngrok 의존, 복잡도 과다 |
| 파일시스템 inotify/watch | 미커밋 파일도 감지 → "main 한정" 원칙 위반, OS별 구현 차이 |
| GitHub Actions + 외부 서버 | 외부 인프라 의존, 로컬 우선 원칙 위반 |
