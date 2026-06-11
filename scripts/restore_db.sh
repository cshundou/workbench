#!/usr/bin/env bash
# PostgreSQL 数据库恢复脚本（交付标准 8.3）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

POSTGRES_USER="${POSTGRES_USER:-ai_workbench}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-ai_workbench_secret}"
POSTGRES_DB="${POSTGRES_DB:-ai_workbench}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
BACKUP_DIR="${DB_BACKUP_DIR:-${PROJECT_ROOT}/data/backups/db}"
BACKUP_FILE="${1:-}"

if [[ -z "${BACKUP_FILE}" ]]; then
  echo "用法: $0 <备份文件路径>" >&2
  echo "示例: $0 ${BACKUP_DIR}/db_backup_20260611_120000.sql.gz" >&2
  if [[ -d "${BACKUP_DIR}" ]]; then
    echo "" >&2
    echo "可用备份:" >&2
    ls -1t "${BACKUP_DIR}"/db_backup_*.sql.gz 2>/dev/null | head -5 >&2 || true
  fi
  exit 1
fi

if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "[ERROR] 备份文件不存在: ${BACKUP_FILE}" >&2
  exit 1
fi

export PGPASSWORD="${POSTGRES_PASSWORD}"

echo "[WARN] 即将恢复数据库 ${POSTGRES_DB}，现有数据将被覆盖"
read -r -p "确认继续? [y/N] " confirm
if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
  echo "已取消"
  exit 0
fi

echo "[INFO] 从 ${BACKUP_FILE} 恢复数据库..."
if command -v docker >/dev/null 2>&1 && docker compose -f "${PROJECT_ROOT}/docker-compose.yml" ps postgres 2>/dev/null | grep -q "Up"; then
  gunzip -c "${BACKUP_FILE}" | docker compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T postgres \
    psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"
else
  gunzip -c "${BACKUP_FILE}" | psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"
fi

unset PGPASSWORD
echo "[INFO] 数据库恢复完成"
