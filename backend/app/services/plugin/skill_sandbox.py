"""
Skill 沙箱隔离器。

进程级隔离、声明式权限、资源限制与恶意代码检测。
"""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from app.core.config import settings
from app.services.plugin.permissions import VALID_SKILL_PERMISSIONS
from app.services.plugin.plugin_security import plugin_security_scanner

logger = logging.getLogger(__name__)

SkillExecutor = Callable[[dict[str, Any]], Awaitable[Any]]

_DEFAULT_MEMORY_MB = 256
_PROCESS_POOL: Optional[ProcessPoolExecutor] = None


def _get_process_pool() -> ProcessPoolExecutor:
    global _PROCESS_POOL
    if _PROCESS_POOL is None:
        _PROCESS_POOL = ProcessPoolExecutor(max_workers=4)
    return _PROCESS_POOL


def _isolated_async_runner(coro_payload: tuple[str, dict[str, Any]]) -> Any:
    """
    子进程入口：按 skill_key 执行已注册插件处理器（可 pickle 的顶层函数）。
    """
    import asyncio

    skill_key, parameters = coro_payload
    from app.services.plugin.plugin_handlers import execute_plugin_handler

    return asyncio.run(execute_plugin_handler(skill_key, parameters, {}))


@dataclass
class SandboxContext:
    """沙箱执行上下文。"""

    tenant_id: int
    user_id: Optional[int]
    skill_key: str
    declared_permissions: list[str] = field(default_factory=list)
    level: str = "process"
    timeout_seconds: float = 30.0
    memory_limit_mb: int = _DEFAULT_MEMORY_MB
    source_code: Optional[str] = None


class SkillSandbox:
    """Skill 沙箱隔离器。"""

    def __init__(self, default_timeout: Optional[float] = None) -> None:
        self.default_timeout = default_timeout or float(
            getattr(settings, "agent_tool_timeout_seconds", 30)
        )

    def validate_permissions(
        self,
        required: list[str],
        declared: list[str],
    ) -> None:
        """校验 Skill 声明权限是否覆盖所需权限。"""
        invalid = set(required) - VALID_SKILL_PERMISSIONS
        if invalid:
            raise PermissionError(f"无效权限声明: {invalid}")
        missing = set(required) - set(declared)
        if missing:
            raise PermissionError(f"Skill 缺少权限声明: {missing}")

    def scan_before_run(self, ctx: SandboxContext) -> None:
        """运行前恶意代码检测。"""
        if not ctx.source_code:
            return
        scan = plugin_security_scanner.scan_source(ctx.source_code, ctx.skill_key)
        if not scan.passed:
            raise PermissionError(f"Skill 代码安全扫描未通过: {scan.issues[:3]}")

    async def run(
        self,
        ctx: SandboxContext,
        executor: SkillExecutor,
        parameters: dict[str, Any],
    ) -> Any:
        """
        在沙箱中执行 Skill。

        - process 级别：插件类 Skill 在子进程执行
        - basic 级别：asyncio 超时控制（MCP/原生工具）
        """
        self.validate_permissions(ctx.declared_permissions, ctx.declared_permissions)
        invalid_declared = set(ctx.declared_permissions) - VALID_SKILL_PERMISSIONS
        if invalid_declared:
            raise PermissionError(f"Skill 声明了无效权限: {invalid_declared}")
        self.scan_before_run(ctx)
        timeout = ctx.timeout_seconds or self.default_timeout

        logger.info(
            "沙箱执行 skill=%s tenant=%s level=%s timeout=%ss",
            ctx.skill_key,
            ctx.tenant_id,
            ctx.level,
            timeout,
        )

        if ctx.level == "process" and ":" in ctx.skill_key:
            return await self._run_plugin_in_subprocess(ctx, parameters, timeout)

        try:
            return await asyncio.wait_for(executor(parameters), timeout=timeout)
        except asyncio.TimeoutError as exc:
            logger.warning("Skill 沙箱超时 skill=%s", ctx.skill_key)
            raise TimeoutError(f"Skill 执行超时（>{timeout}s）") from exc
        except PermissionError:
            raise
        except Exception as exc:
            logger.exception("Skill 沙箱执行异常 skill=%s: %s", ctx.skill_key, exc)
            raise

    async def _run_plugin_in_subprocess(
        self,
        ctx: SandboxContext,
        parameters: dict[str, Any],
        timeout: float,
    ) -> Any:
        """插件 Skill 在独立子进程运行，崩溃不影响主服务。"""
        loop = asyncio.get_event_loop()
        pool = _get_process_pool()
        started = time.monotonic()
        try:
            future = pool.submit(
                _isolated_async_runner, (ctx.skill_key, parameters)
            )
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: future.result(timeout)),
                timeout=timeout + 2,
            )
            logger.debug(
                "子进程 Skill 完成 skill=%s duration_ms=%s",
                ctx.skill_key,
                int((time.monotonic() - started) * 1000),
            )
            return result
        except (FuturesTimeoutError, asyncio.TimeoutError) as exc:
            logger.warning("Skill 子进程超时 skill=%s", ctx.skill_key)
            raise TimeoutError(f"Skill 执行超时（>{timeout}s）") from exc
        except Exception as exc:
            logger.exception("Skill 子进程失败 skill=%s: %s", ctx.skill_key, exc)
            raise


skill_sandbox = SkillSandbox()
