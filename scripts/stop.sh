#!/usr/bin/env bash
# AI Workbench 停止脚本
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

stop_pid() {
  local pidfile="$1"
  local name="$2"
  if [ -f "$pidfile" ]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "[stop] 已停止 $name (PID $pid)"
    fi
    rm -f "$pidfile"
  fi
}

stop_pid "$ROOT/logs/backend.pid" "后端"
stop_pid "$ROOT/logs/worker.pid" "ARQ Worker"
stop_pid "$ROOT/logs/frontend.pid" "前端"

if command -v docker &>/dev/null && [ -f "$ROOT/docker-compose.yml" ]; then
  cd "$ROOT" && docker compose down 2>/dev/null && echo "[stop] Docker 服务已停止"
fi

echo "[stop] 完成"
