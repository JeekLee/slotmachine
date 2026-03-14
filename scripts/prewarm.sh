#!/usr/bin/env bash
# SlotMachine venv 사전 준비 스크립트
# SessionStart 훅에서 호출 — venv가 없을 때만 uv sync를 실행한다.
# MCP 서버 첫 기동 시 uv sync 대기로 인한 연결 타임아웃을 방지한다.

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "cygwin"* || -n "${WINDIR:-}" ]]; then
  PYTHON="$PLUGIN_ROOT/.venv/Scripts/python"
else
  PYTHON="$PLUGIN_ROOT/.venv/bin/python"
fi

if [[ ! -x "$PYTHON" ]]; then
  SETUP_ONLY=1 bash "$PLUGIN_ROOT/scripts/bootstrap-mcp.sh"
fi
