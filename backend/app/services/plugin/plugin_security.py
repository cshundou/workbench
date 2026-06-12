"""
插件恶意代码扫描器（基础规则引擎）。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 高危模式（Phase 3 可接入专业 SAST）
_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"eval\s*\(", "使用 eval 动态执行代码"),
    (r"exec\s*\(", "使用 exec 动态执行代码"),
    (r"__import__\s*\(", "动态导入模块"),
    (r"os\.system\s*\(", "系统命令执行"),
    (r"subprocess\.", "子进程调用"),
    (r"rm\s+-rf", "危险删除命令"),
    (r"DROP\s+TABLE", "SQL 删表语句"),
    (r";\s*DELETE\s+FROM", "SQL 批量删除"),
    (r"base64\.b64decode", "可疑编码载荷"),
    (r"curl\s+.*\|\s*bash", "远程脚本下载执行"),
]


@dataclass
class ScanResult:
    """扫描结果。"""

    passed: bool
    issues: list[str] = field(default_factory=list)
    risk_level: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": self.issues,
            "risk_level": self.risk_level,
        }


class PluginSecurityScanner:
    """插件包安全扫描。"""

    def scan_manifest(self, manifest: dict[str, Any]) -> ScanResult:
        """扫描 plugin.json 配置。"""
        issues: list[str] = []
        permissions = manifest.get("permissions") or []
        for perm in permissions:
            if perm not in {
                "network:outbound", "network:inbound", "storage:read", "storage:write",
                "system:env", "agent:message", "user:info", "filesystem:read",
                "filesystem:write", "process:spawn", "database:query", "mcp:invoke",
            }:
                issues.append(f"未知权限声明: {perm}")

        if manifest.get("backend", {}).get("routes") and "network:inbound" not in permissions:
            issues.append("注册后端路由但未声明 network:inbound 权限")

        return ScanResult(passed=len(issues) == 0, issues=issues, risk_level="medium" if issues else "low")

    def scan_source(self, content: str, filename: str = "") -> ScanResult:
        """扫描源代码文本。"""
        issues: list[str] = []
        for pattern, desc in _DANGEROUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(f"[{filename or 'source'}] {desc}")

        risk = "high" if len(issues) >= 3 else ("medium" if issues else "low")
        return ScanResult(passed=len(issues) == 0, issues=issues, risk_level=risk)

    def verify_signature(self, signature: Optional[str], is_official: bool) -> ScanResult:
        """验证官方插件签名（简化：官方插件需有 signature 字段）。"""
        if not is_official:
            return ScanResult(passed=True)
        if not signature:
            return ScanResult(
                passed=False,
                issues=["官方插件缺少数字签名"],
                risk_level="high",
            )
        if len(signature) < 32:
            return ScanResult(
                passed=False,
                issues=["数字签名格式无效"],
                risk_level="high",
            )
        return ScanResult(passed=True)


plugin_security_scanner = PluginSecurityScanner()
