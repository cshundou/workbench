"""插件系统单元测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.plugin.permissions import VALID_SKILL_PERMISSIONS
from app.services.plugin.plugin_catalog import PLUGIN_CATALOG
from app.services.plugin.plugin_security import plugin_security_scanner
from app.services.plugin.native_skills import NATIVE_SKILL_KEYS, build_native_skill_defs
from app.services.plugin.skill_sandbox import SandboxContext, skill_sandbox


class TestPluginPermissions:
    """权限常量验收。"""

    def test_has_ten_plus_permissions(self) -> None:
        assert len(VALID_SKILL_PERMISSIONS) >= 10


class TestPluginCatalog:
    """官方插件目录。"""

    def test_catalog_has_ten_plugins(self) -> None:
        assert len(PLUGIN_CATALOG) >= 10

    def test_all_plugins_have_signature_when_official(self) -> None:
        for item in PLUGIN_CATALOG:
            if item.get("is_official"):
                assert item.get("signature"), f"{item['plugin_id']} 缺少签名"


class TestNativeSkills:
    """原生 Skill 转换。"""

    def test_five_native_skills(self) -> None:
        assert len(NATIVE_SKILL_KEYS) == 5

    def test_build_native_defs(self) -> None:
        defs = build_native_skill_defs()
        assert len(defs) == 5
        keys = {d["skill_key"] for d in defs}
        assert keys == set(NATIVE_SKILL_KEYS)


class TestPluginSecurity:
    """安全扫描。"""

    def test_scan_clean_manifest(self) -> None:
        manifest = {"plugin_id": "test", "permissions": ["network:outbound"]}
        result = plugin_security_scanner.scan_manifest(manifest)
        assert result.passed

    def test_scan_rejects_eval(self) -> None:
        result = plugin_security_scanner.scan_source("eval('hack')", "main.py")
        assert not result.passed


class TestSkillSandbox:
    """沙箱隔离。"""

    @pytest.mark.asyncio
    async def test_run_success(self) -> None:
        ctx = SandboxContext(tenant_id=1, user_id=1, skill_key="test")

        async def executor(params: dict) -> str:
            return f"ok:{params['x']}"

        result = await skill_sandbox.run(ctx, executor, {"x": 1})
        assert result == "ok:1"

    @pytest.mark.asyncio
    async def test_run_timeout(self) -> None:
        import asyncio

        ctx = SandboxContext(tenant_id=1, user_id=1, skill_key="slow", timeout_seconds=0.1)

        async def slow_executor(params: dict) -> None:
            await asyncio.sleep(1)

        with pytest.raises(TimeoutError):
            await skill_sandbox.run(ctx, slow_executor, {})

    def test_validate_missing_permission(self) -> None:
        with pytest.raises(PermissionError):
            skill_sandbox.validate_permissions(
                ["network:outbound"],
                ["storage:read"],
            )
