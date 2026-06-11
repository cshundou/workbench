#!/usr/bin/env bash
# Chroma 向量库恢复脚本（交付标准 3.2 / 8.3）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CHROMA_DIR="${CHROMA_PERSIST_DIR:-${PROJECT_ROOT}/data/chroma}"
BACKUP_DIR="${VECTOR_BACKUP_DIR:-${PROJECT_ROOT}/data/backups/vectors}"
ARCHIVE_PATH="${1:-}"

if [[ -z "${ARCHIVE_PATH}" ]]; then
  echo "用法: $0 <备份文件路径>" >&2
  echo "示例: $0 ${BACKUP_DIR}/chroma_backup_20260611_120000.tar.gz" >&2
  if [[ -d "${BACKUP_DIR}" ]]; then
    echo "" >&2
    echo "可用备份:" >&2
    ls -1t "${BACKUP_DIR}"/chroma_backup_*.tar.gz 2>/dev/null | head -5 >&2 || true
  fi
  exit 1
fi

if [[ ! -f "${ARCHIVE_PATH}" ]]; then
  echo "[ERROR] 备份文件不存在: ${ARCHIVE_PATH}" >&2
  exit 1
fi

PARENT_DIR="$(dirname "${CHROMA_DIR}")"
CHROMA_NAME="$(basename "${CHROMA_DIR}")"

if [[ -d "${CHROMA_DIR}" ]]; then
  SAFETY_BACKUP="${BACKUP_DIR}/pre_restore_${CHROMA_NAME}_$(date +%Y%m%d_%H%M%S).tar.gz"
  mkdir -p "${BACKUP_DIR}"
  echo "[INFO] 恢复前安全备份当前向量库 -> ${SAFETY_BACKUP}"
  tar -czf "${SAFETY_BACKUP}" -C "${PARENT_DIR}" "${CHROMA_NAME}"
  rm -rf "${CHROMA_DIR}"
fi

mkdir -p "${PARENT_DIR}"
echo "[INFO] 从 ${ARCHIVE_PATH} 恢复向量库到 ${CHROMA_DIR}"
tar -xzf "${ARCHIVE_PATH}" -C "${PARENT_DIR}"

echo "[INFO] 向量库恢复完成"
