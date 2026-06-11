#!/usr/bin/env bash
# AI Workbench 一键启动脚本（本地开发模式）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/logs"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[start]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*"; }

# 加载环境变量（仅导出简单变量，避免 source 破坏 CORS_ORIGINS 等 JSON 字段）
load_env() {
  [ -f .env ] || cp .env.example .env
  export DATABASE_URL
  export REDIS_URL
  export JWT_SECRET_KEY
  export APP_ENV
  DATABASE_URL="$(grep '^DATABASE_URL=' .env | head -1 | cut -d= -f2- | tr -d '"' || true)"
  REDIS_URL="$(grep '^REDIS_URL=' .env | head -1 | cut -d= -f2- | tr -d '"' || true)"
  JWT_SECRET_KEY="$(grep '^JWT_SECRET_KEY=' .env | head -1 | cut -d= -f2- | tr -d '"' || true)"
  APP_ENV="$(grep '^APP_ENV=' .env | head -1 | cut -d= -f2- | tr -d '"' || true)"
  export DATABASE_URL REDIS_URL JWT_SECRET_KEY APP_ENV
}

# 检查 HTTP 服务是否健康
wait_health() {
  local url="$1"
  local name="$2"
  local retries="${3:-15}"
  for i in $(seq 1 "$retries"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      log "$name 健康检查通过"
      return 0
    fi
    sleep 1
  done
  err "$name 启动失败，请查看 logs/"
  return 1
}

# 启动后端（若端口无响应则重启）
start_backend() {
  if curl -sf http://localhost:8000/api/v1/health >/dev/null 2>&1; then
    log "后端已在运行 (http://localhost:8000)"
    return 0
  fi

  # 清理僵死 PID
  if [ -f logs/backend.pid ]; then
    local old_pid
    old_pid=$(cat logs/backend.pid)
    kill "$old_pid" 2>/dev/null || true
    rm -f logs/backend.pid
  fi

  log "启动后端 (http://localhost:8000)..."
  cd "$ROOT/backend"
  [ -d .venv ] || python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -r requirements.txt
  chmod +x run.sh

  # setsid 脱离终端会话，防止进程随 shell 退出
  if command -v setsid &>/dev/null; then
    setsid "$ROOT/backend/run.sh" >> "$ROOT/logs/backend.log" 2>&1 &
  else
    nohup "$ROOT/backend/run.sh" >> "$ROOT/logs/backend.log" 2>&1 &
  fi
  echo $! > "$ROOT/logs/backend.pid"
  disown 2>/dev/null || true
  cd "$ROOT"

  wait_health "http://localhost:8000/api/v1/health" "后端"
}

# 启动前端（每次重启以确保加载最新代码和代理配置）
start_frontend() {
  # 停止旧的前端进程
  if lsof -ti :5173 &>/dev/null; then
    log "重启前端以加载最新代码..."
    lsof -ti :5173 | xargs kill -9 2>/dev/null || true
    sleep 1
  fi

  if [ -f logs/frontend.pid ]; then
    local old_pid
    old_pid=$(cat logs/frontend.pid)
    kill "$old_pid" 2>/dev/null || true
    rm -f logs/frontend.pid
  fi

  log "启动前端 (http://localhost:5173)..."
  cd "$ROOT/frontend"
  [ -d node_modules ] || npm install --silent
  nohup npm run dev -- --host 0.0.0.0 --port 5173 \
    > "$ROOT/logs/frontend.log" 2>&1 &
  echo $! > "$ROOT/logs/frontend.pid"
  cd "$ROOT"

  wait_health "http://localhost:5173/" "前端"
}

# ---------- 1. Docker 优先 ----------
if command -v docker &>/dev/null; then
  log "检测到 Docker，使用 docker compose 启动..."
  load_env
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
load_env

# 确保使用 localhost 连接
if [[ "${DATABASE_URL:-}" == *"@postgres:"* ]]; then
  DATABASE_URL="postgresql+asyncpg://$(whoami)@localhost:5432/ai_workbench"
  export DATABASE_URL
  log "DATABASE_URL 已切换为 localhost"
fi
if [[ "${REDIS_URL:-}" == *"redis://redis:"* ]]; then
  REDIS_URL="redis://localhost:6379/0"
  export REDIS_URL
  log "REDIS_URL 已切换为 localhost"
fi

# ---------- 2. 启动 PostgreSQL ----------
PG_BIN=""
for p in /opt/homebrew/opt/postgresql@16/bin /opt/homebrew/opt/postgresql/bin; do
  [ -x "$p/pg_isready" ] && PG_BIN="$p" && break
done

if [ -n "$PG_BIN" ]; then
  if ! "$PG_BIN/pg_isready" -q 2>/dev/null; then
    log "启动 PostgreSQL..."
    /opt/homebrew/bin/brew services start postgresql@16 2>/dev/null || true
    sleep 3
  fi
  "$PG_BIN/createdb" ai_workbench 2>/dev/null || true
  log "PostgreSQL 就绪"
else
  warn "未安装 PostgreSQL: brew install postgresql@16"
fi

# ---------- 3. 启动 Redis ----------
REDIS_CLI="$(command -v redis-cli || echo /opt/homebrew/bin/redis-cli)"
if [ -x "$REDIS_CLI" ]; then
  if ! "$REDIS_CLI" ping &>/dev/null; then
    log "启动 Redis..."
    /opt/homebrew/bin/brew services start redis 2>/dev/null || true
    sleep 2
  fi
  log "Redis 就绪"
fi

# ---------- 4. 数据库迁移 ----------
if [ -n "$PG_BIN" ] && "$PG_BIN/pg_isready" -q 2>/dev/null; then
  cd "$ROOT/backend" && source .venv/bin/activate 2>/dev/null || true
  alembic upgrade head 2>/dev/null || warn "数据库迁移跳过"
  python -m scripts.init_data 2>/dev/null || warn "初始化数据跳过"
  cd "$ROOT"
fi

# ---------- 5. 启动服务 ----------
start_backend
start_frontend

# ---------- 6. 登录冒烟测试 ----------
LOGIN_RESULT=$(curl -sf -X POST http://localhost:5173/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' 2>/dev/null || echo "FAIL")

if echo "$LOGIN_RESULT" | grep -q '"code":200'; then
  log "登录冒烟测试通过"
else
  err "登录冒烟测试失败: $LOGIN_RESULT"
  exit 1
fi

log "========================================="
log "  AI Workbench 已启动"
log "  前端: http://localhost:5173"
log "  后端: http://localhost:8000/docs"
log "  账号: admin / admin123"
log "  停止: ./scripts/stop.sh"
log "========================================="
