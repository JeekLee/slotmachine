# Runbook

운영 중 발생하는 작업 및 장애 대응 절차를 기록한다.

---

## Neo4j 로컬 기동 / 중단

```bash
# 기동
docker compose up -d neo4j

# 중단
docker compose down

# 로그 확인
docker compose logs -f neo4j
```

---

## Sync 상태 확인

```bash
slotmachine status
```

---

## 장애 대응

_운영 중 추가 예정_

---

## 변경 이력

| 날짜 | 내용 | 담당 |
|------|------|------|
| 2026-03-13 12:56:00 | 최초 작성 | infra |
