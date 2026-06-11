"""
Python 代码执行工具（受限沙箱）。
"""

import asyncio
import io
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict

from app.core.config import settings
from app.core.logging import get_logger
from app.services.agent.tools.base import BaseTool, ToolResult

logger = get_logger(__name__)

# 禁止导入的高风险模块
_FORBIDDEN_MODULES = {
    "os",
    "subprocess",
    "shutil",
    "socket",
    "requests",
    "httpx",
    "pathlib",
}


class PythonReplTool(BaseTool):
    """在安全受限环境中执行 Python 代码。"""

    name = "python_repl"
    description = "执行 Python 代码进行数据计算、格式转换和简单分析"
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "要执行的 Python 代码",
            },
        },
        "required": ["code"],
    }

    @staticmethod
    def _validate_code(code: str) -> str | None:
        """基础代码安全检查。"""
        lowered = code.lower()
        for module in _FORBIDDEN_MODULES:
            if f"import {module}" in lowered or f"from {module}" in lowered:
                return f"禁止使用模块: {module}"
        if "__" in code and "import" not in code:
            return "禁止使用双下划线内置访问"
        return None

    @staticmethod
    def _run_code_sync(code: str) -> tuple[str, str]:
        """同步执行 Python 代码并捕获输出。"""
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        local_vars: dict[str, Any] = {}

        safe_builtins = {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "print": print,
            "range": range,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
        }

        global_vars = {"__builtins__": safe_builtins}

        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(code, global_vars, local_vars)  # noqa: S102

        return stdout_buffer.getvalue(), stderr_buffer.getvalue()

    async def _run_code_docker(self, code: str) -> tuple[str, str]:
        """在 Docker 容器中隔离执行 Python 代码。"""
        timeout = settings.python_repl_timeout_seconds
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--memory=128m",
            "--cpus=0.5",
            settings.python_repl_docker_image,
            "python",
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return "", f"执行超时（{timeout}s）"
        return (
            stdout_bytes.decode("utf-8", errors="replace"),
            stderr_bytes.decode("utf-8", errors="replace"),
        )

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """异步执行 Python 代码。"""
        try:
            code = parameters["code"]
            validation_error = self._validate_code(code)
            if validation_error:
                return ToolResult(success=False, content=None, error=validation_error)

            if settings.python_repl_mode == "docker":
                stdout, stderr = await self._run_code_docker(code)
            else:
                loop = asyncio.get_running_loop()
                stdout, stderr = await loop.run_in_executor(None, self._run_code_sync, code)

            return ToolResult(
                success=True,
                content={
                    "stdout": stdout,
                    "stderr": stderr,
                    "result": stdout.strip() or "代码执行完成（无输出）",
                },
            )
        except Exception as exc:
            logger.error("PythonReplTool 执行失败: %s", exc)
            return ToolResult(
                success=False,
                content={
                    "traceback": traceback.format_exc(),
                },
                error=str(exc),
            )
