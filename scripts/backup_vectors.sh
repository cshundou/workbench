#!/usr/bin/env bash
# Chroma 向量库全量备份脚本（交付标准 3.2 / 8.3）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CHROMA_DIR="${CHROMA_PERSIST_DIR:-${PROJECT_ROOT}/data/chroma}"
BACKUP_DIR="${VECTOR_BACKUP_DIR:-${PROJECT_ROOT}/data/backups/vectors}"
RETENTION_DAYS="${VECTOR_BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_NAME="chroma_backup_${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${BACKUP_DIR}/${ARCHIVE_NAME}"

if [[ ! -d "${CHROMA_DIR}" ]]; then
  echo "[ERROR] Chroma 目录不存在: ${CHROMA_DIR}" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

echo "[INFO] 备份 Chroma 向量库: ${CHROMA_DIR}"
tar -czf "${ARCHIVE_PATH}" -C "$(dirname "${CHROMA_DIR}")" "$(basename "${CHROMA_DIR}")"

echo "[INFO] 备份完成: ${ARCHIVE_PATH}"
echo "[INFO] 清理 ${RETENTION_DAYS} 天前的旧备份..."
find "${BACKUP_DIR}" -name 'chroma_backup_*.tar.gz' -type f -mtime +"${RETENTION_DAYS}" -delete

echo "[INFO] 当前备份列表:"
ls -lh "${BACKUP_DIR}"/chroma_backup_*.tar.gz 2>/dev/null || echo "  (无)"
