#!/usr/bin/env bash
# SlotMachine MCP 서버 부트스트랩
# 역할: venv 준비 → (Docker Neo4j 필요 시 시작) → slotmachine.server 실행
# 이 스크립트가 MCP 서버의 단일 진입점이다.

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SLOTMACHINE_CONFIG="${HOME}/.slotmachine/settings.env"

# ── Python 실행 파일 경로 (OS 분기) ──────────────────────────────────────────
if [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "cygwin"* || -n "${WINDIR:-}" ]]; then
  PYTHON="$PLUGIN_ROOT/.venv/Scripts/python"
else
  PYTHON="$PLUGIN_ROOT/.venv/bin/python"
fi

# ── venv 없으면 설치 ──────────────────────────────────────────────────────────
if [[ ! -x "$PYTHON" ]]; then
  echo "[slotmachine] venv not found — installing dependencies..." >&2
  cd "$PLUGIN_ROOT"

  if command -v uv &>/dev/null; then
    uv sync --quiet
  else
    python3 -m venv .venv
    if [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "cygwin"* || -n "${WINDIR:-}" ]]; then
      .venv/Scripts/pip install -e . --quiet
    else
      .venv/bin/pip install -e . --quiet
    fi
  fi
fi

# ── SETUP_ONLY 모드: 설치만 하고 종료 ────────────────────────────────────────
if [[ "${SETUP_ONLY:-}" == "1" ]]; then
  echo "[slotmachine] setup complete" >&2
  exit 0
fi

# ── Docker Neo4j 자동 시작 (NEO4J_MODE=docker 일 때) ─────────────────────────
NEO4J_MODE=$(grep '^NEO4J_MODE=' "$SLOTMACHINE_CONFIG" 2>/dev/null \
  | cut -d= -f2 | tr -d '[:space:]' || echo "external")

if [[ "$NEO4J_MODE" == "docker" ]]; then
  if ! command -v docker &>/dev/null; then
    echo "[slotmachine] WARNING: NEO4J_MODE=docker 이지만 Docker를 찾을 수 없습니다." >&2
    echo "[slotmachine] Docker를 설치하거나 외부 Neo4j URI를 설정하세요." >&2
  else
    cd "$PLUGIN_ROOT"
    CONTAINER_STATE=$(docker inspect --format '{{.State.Status}}' slotmachine-neo4j 2>/dev/null || echo "missing")
    if [[ "$CONTAINER_STATE" == "running" ]]; then
      : # 이미 실행 중
    elif [[ "$CONTAINER_STATE" == "missing" ]]; then
      echo "[slotmachine] Neo4j 컨테이너 생성 및 시작 중..." >&2
      NEO4J_PASSWORD=slotmachine docker compose up -d 2>/dev/null \
        || echo "[slotmachine] WARNING: Neo4j 컨테이너 시작에 실패했습니다." >&2
    else
      # exited / restarting 등 — 강제 재생성
      echo "[slotmachine] Neo4j 컨테이너 재생성 중 (이전 상태: $CONTAINER_STATE)..." >&2
      docker rm -f slotmachine-neo4j 2>/dev/null || true
      NEO4J_PASSWORD=slotmachine docker compose up -d 2>/dev/null \
        || echo "[slotmachine] WARNING: Neo4j 컨테이너 시작에 실패했습니다." >&2
    fi
  fi
fi

# ── MCP 서버 시작 ─────────────────────────────────────────────────────────────
exec "$PYTHON" -m slotmachine.server
