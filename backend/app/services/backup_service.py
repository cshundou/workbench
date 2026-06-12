"""
自动化备份服务。

通过 ARQ 定时任务调用备份脚本，支持数据库与向量库全量备份。
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class BackupService:
    """备份与恢复任务执行。"""

    async def run_db_backup(self) -> dict[str, Any]:
        """执行数据库全量备份脚本。"""
        script = _PROJECT_ROOT / "scripts" / "backup_db.sh"
        return await self._run_script(script, "database")

    async def run_vector_backup(self) -> dict[str, Any]:
        """执行向量库备份脚本。"""
        script = _PROJECT_ROOT / "scripts" / "backup_vectors.sh"
        return await self._run_script(script, "vectors")

    async def run_full_backup(self) -> dict[str, Any]:
        """执行完整备份（数据库 + 向量库）。"""
        db_result = await self.run_db_backup()
        vec_result = await self.run_vector_backup()
        return {"database": db_result, "vectors": vec_result}

    async def _run_script(self, script: Path, label: str) -> dict[str, Any]:
        """异步执行 shell 备份脚本。"""
        if not script.exists():
            logger.error("备份脚本不存在 path=%s", script)
            return {"success": False, "error": f"脚本不存在: {script}"}

        try:
            proc = await asyncio.create_subprocess_exec(
                "bash",
                str(script),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(_PROJECT_ROOT),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
            success = proc.returncode == 0
            output = stdout.decode("utf-8", errors="replace")
            if not success:
                logger.error("备份失败 label=%s stderr=%s", label, stderr.decode())
            else:
                logger.info("备份完成 label=%s", label)
            return {
                "success": success,
                "label": label,
                "output": output[-2000:] if output else "",
                "error": stderr.decode("utf-8", errors="replace")[-500:] if not success else None,
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": "备份超时（>600s）"}
        except Exception as exc:
            logger.exception("备份异常 label=%s: %s", label, exc)
            return {"success": False, "error": str(exc)}


backup_service = BackupService()


async def backup_database_task(_ctx: dict) -> str:
    """ARQ 定时任务：数据库备份。"""
    result = await backup_service.run_db_backup()
    if not result.get("success"):
        raise RuntimeError(result.get("error", "数据库备份失败"))
    return "database backup completed"


async def backup_vectors_task(_ctx: dict) -> str:
    """ARQ 定时任务：向量库备份。"""
    result = await backup_service.run_vector_backup()
    if not result.get("success"):
        raise RuntimeError(result.get("error", "向量库备份失败"))
    return "vector backup completed"
