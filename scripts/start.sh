#!/usr/bin/env bash
# AI Workbench 一键启动脚本（本地开发模式）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[start]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*"; }

# ---------- 1. Docker 优先 ----------
if command -v docker &>/dev/null; then
  log "检测到 Docker，使用 docker compose 启动..."
  [ -f .env ] || cp .env.example .env
  docker compose up -d --build
  sleep 5
  docker compose exec -T backend alembic upgrade head 2>/dev/null || true
  docker compose exec -T backend python -m scripts.init_data 2>/dev/null || true
  log "服务已启动："
  echo "  前端: http://localhost:5173 或 http://localhost (Nginx)"
  echo "  后端: http://localhost:8000/docs"
  echo "  账号: admin / admin123"
  exit 0
fi

warn "未检测到 Docker，切换为本地开发模式..."

# ---------- 2. 准备 .env ----------
if [ ! -f .env ]; then
  cp .env.example .env
  log "已创建 .env"
fi

# 确保使用 localhost 连接
if grep -q '@postgres:5432' .env 2>/dev/null; then
  sed -i '' 's|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://ai_workbench:ai_workbench_secret@localhost:5432/ai_workbench|' .env
  sed -i '' 's|^REDIS_URL=.*|REDIS_URL=redis://localhost:6379/0|' .env
  log "已将 DATABASE_URL / REDIS_URL 切换为 localhost"
fi

# ---------- 3. 启动 PostgreSQL ----------
PG_BIN=""
for p in /opt/homebrew/opt/postgresql@16/bin /opt/homebrew/opt/postgresql/bin /usr/local/opt/postgresql@16/bin; do
  [ -x "$p/pg_isready" ] && PG_BIN="$p" && break
done

if [ -n "$PG_BIN" ]; then
  if ! "$PG_BIN/pg_isready" -q 2>/dev/null; then
    log "启动 PostgreSQL..."
    /opt/homebrew/bin/brew services start postgresql@16 2>/dev/null || \
    /opt/homebrew/bin/brew services start postgresql 2>/dev/null || true
    sleep 3
  fi
  # 创建数据库和用户（首次）
  if "$PG_BIN/pg_isready" -q 2>/dev/null; then
    "$PG_BIN/createdb" ai_workbench 2>/dev/null || true
    log "PostgreSQL 就绪"
  else
    warn "PostgreSQL 未就绪，登录等功能可能不可用"
  fi
else
  warn "未安装 PostgreSQL，请执行: brew install postgresql@16"
fi

# ---------- 4. 启动 Redis ----------
if command -v redis-cli &>/dev/null || [ -x /opt/homebrew/bin/redis-cli ]; then
  REDIS_CLI="${REDIS_CLI:-$(command -v redis-cli || echo /opt/homebrew/bin/redis-cli)}"
  if ! "$REDIS_CLI" ping &>/dev/null; then
    log "启动 Redis..."
    /opt/homebrew/bin/brew services start redis 2>/dev/null || true
    sleep 2
  fi
  log "Redis 就绪"
else
  warn "未安装 Redis，请执行: brew install redis"
fi

# ---------- 5. 后端 ----------
log "准备后端环境..."
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

# 数据库迁移与初始化
if [ -n "$PG_BIN" ] && "$PG_BIN/pg_isready" -q 2>/dev/null; then
  export DATABASE_URL="postgresql+asyncpg://$(whoami)@localhost:5432/ai_workbench"
  # 若 .env 有完整连接串则优先使用
  if [ -f "$ROOT/.env" ]; then
    export $(grep -E '^DATABASE_URL=' "$ROOT/.env" | xargs) 2>/dev/null || true
  fi
  alembic upgrade head 2>/dev/null || warn "数据库迁移跳过（可能需手动创建用户/库）"
  python -m scripts.init_data 2>/dev/null || warn "初始化数据跳过"
fi

# 后台启动后端
if lsof -i :8000 &>/dev/null; then
  warn "端口 8000 已被占用，跳过后端启动"
else
  log "启动后端 (http://localhost:8000)..."
  nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 \
    > "$ROOT/logs/backend.log" 2>&1 &
  echo $! > "$ROOT/logs/backend.pid"
fi

# ---------- 6. 前端 ----------
cd "$ROOT/frontend"
[ -d node_modules ] || npm install --silent

if lsof -i :5173 &>/dev/null; then
  warn "端口 5173 已被占用，跳过前端启动"
else
  log "启动前端 (http://localhost:5173)..."
  mkdir -p "$ROOT/logs"
  nohup npm run dev -- --host 0.0.0.0 --port 5173 \
    > "$ROOT/logs/frontend.log" 2>&1 &
  echo $! > "$ROOT/logs/frontend.pid"
fi

sleep 3
log "========================================="
log "  AI Workbench 已启动"
log "  前端: http://localhost:5173"
log "  后端: http://localhost:8000/docs"
log "  账号: admin / admin123"
log "  日志: logs/backend.log  logs/frontend.log"
log "  停止: ./scripts/stop.sh"
log "========================================="
