"""
Skill 沙箱隔离器。

提供进程级超时、权限校验与资源限制（基础层，Phase 3 可扩展 K8s Pod 隔离）。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from app.core.config import settings
from app.services.plugin.permissions import VALID_SKILL_PERMISSIONS

logger = logging.getLogger(__name__)

SkillExecutor = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass
class SandboxContext:
    """沙箱执行上下文。"""

    tenant_id: int
    user_id: Optional[int]
    skill_key: str
    declared_permissions: list[str] = field(default_factory=list)
    level: str = "basic"
    timeout_seconds: float = 30.0


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

    async def run(
        self,
        ctx: SandboxContext,
        executor: SkillExecutor,
        parameters: dict[str, Any],
    ) -> Any:
        """
        在沙箱中执行 Skill。

        - 超时控制
        - 权限校验
        - 异常捕获与日志
        """
        self.validate_permissions(ctx.declared_permissions, ctx.declared_permissions)
        invalid_declared = set(ctx.declared_permissions) - VALID_SKILL_PERMISSIONS
        if invalid_declared:
            raise PermissionError(f"Skill 声明了无效权限: {invalid_declared}")
        timeout = ctx.timeout_seconds or self.default_timeout

        logger.info(
            "沙箱执行 skill=%s tenant=%s level=%s timeout=%ss",
            ctx.skill_key,
            ctx.tenant_id,
            ctx.level,
            timeout,
        )
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


skill_sandbox = SkillSandbox()
