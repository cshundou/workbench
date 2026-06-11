#!/usr/bin/env bash
# 后端独立启动脚本
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"

# 从项目根目录 .env 读取关键变量
if [ -f "$ROOT/.env" ]; then
  export DATABASE_URL="$(grep '^DATABASE_URL=' "$ROOT/.env" | head -1 | cut -d= -f2- | tr -d '"')"
  export REDIS_URL="$(grep '^REDIS_URL=' "$ROOT/.env" | head -1 | cut -d= -f2- | tr -d '"')"
  export JWT_SECRET_KEY="$(grep '^JWT_SECRET_KEY=' "$ROOT/.env" | head -1 | cut -d= -f2- | tr -d '"')"
  export APP_ENV="$(grep '^APP_ENV=' "$ROOT/.env" | head -1 | cut -d= -f2- | tr -d '"')"
fi

source .venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
