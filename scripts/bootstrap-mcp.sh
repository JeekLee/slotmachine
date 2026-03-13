#!/usr/bin/env bash
# SlotMachine MCP 서버 부트스트랩
# 역할: venv 준비 → slotmachine.server 실행
# 이 스크립트가 MCP 서버의 단일 진입점이다.

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

  # uv 우선, 없으면 pip fallback
  if command -v uv &>/dev/null; then
    uv sync --quiet
  else
    python3 -m venv .venv
    # OS별 pip 경로
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

# ── MCP 서버 시작 ─────────────────────────────────────────────────────────────
exec "$PYTHON" -m slotmachine.server
