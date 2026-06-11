#!/usr/bin/env bash
# PostgreSQL 数据库全量备份脚本（交付标准 8.3，保留 30 天）
# 增量备份支持说明：
# 1) 本脚本负责全量逻辑备份（pg_dump）。
# 2) 增量备份建议通过 PostgreSQL WAL 归档实现，单独维护 incremental 脚本：
#    - 开启 postgresql.conf: archive_mode=on
#    - 配置 archive_command 将 WAL 持续归档到外部存储
# 3) 推荐策略：每日全量 + 每小时 WAL 增量归档。
#
# Cron 示例（请替换为真实绝对路径）：
#   0 2 * * * /path/to/ai-workbench/scripts/backup_db.sh >> /var/log/ai-workbench/db_backup.log 2>&1
#   5 * * * * /path/to/ai-workbench/scripts/backup_db_incremental.sh >> /var/log/ai-workbench/db_backup_incremental.log 2>&1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

POSTGRES_USER="${POSTGRES_USER:-ai_workbench}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-ai_workbench_secret}"
POSTGRES_DB="${POSTGRES_DB:-ai_workbench}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
BACKUP_DIR="${DB_BACKUP_DIR:-${PROJECT_ROOT}/data/backups/db}"
RETENTION_DAYS="${DB_BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[INFO] 备份数据库 ${POSTGRES_DB}@${POSTGRES_HOST}:${POSTGRES_PORT}"
export PGPASSWORD="${POSTGRES_PASSWORD}"

if command -v docker >/dev/null 2>&1 && docker compose -f "${PROJECT_ROOT}/docker-compose.yml" ps postgres 2>/dev/null | grep -q "Up"; then
  docker compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T postgres \
    pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" | gzip > "${BACKUP_FILE}"
else
  pg_dump -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" | gzip > "${BACKUP_FILE}"
fi

unset PGPASSWORD

echo "[INFO] 备份完成: ${BACKUP_FILE}"
echo "[INFO] 清理 ${RETENTION_DAYS} 天前的旧备份..."
find "${BACKUP_DIR}" -name 'db_backup_*.sql.gz' -type f -mtime +"${RETENTION_DAYS}" -delete

echo "[INFO] 当前备份列表:"
ls -lh "${BACKUP_DIR}"/db_backup_*.sql.gz 2>/dev/null || echo "  (无)"
