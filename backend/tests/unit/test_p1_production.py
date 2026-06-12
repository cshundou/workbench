"""P1 生产级补全单元测试。"""

import json

import pytest

from app.services.workflow.hybrid_checkpoint import HybridCheckpointSaver
from app.services.workflow.postgres_saver import PostgresSaver
from app.services.workflow.redis_saver import RedisSaver
from app.services.plugin.skill_sandbox import SandboxContext, SkillSandbox
from app.services.plugin.plugin_security import plugin_security_scanner
from app.services.workflow.template_catalog import OFFICIAL_TEMPLATE_CATALOG
from app.services.monitor_service import MonitorService


class TestHybridCheckpoint:
    """混合 Checkpoint 存储。"""

    def test_create_hybrid_saver(self) -> None:
        import redis

        client = redis.Redis.from_url("redis://localhost:6379/15", decode_responses=False)
        saver = HybridCheckpointSaver(client)
        assert saver is not None
        assert hasattr(saver, "get") and hasattr(saver, "put")


class TestSkillSandboxP1:
    """沙箱加固。"""

    @pytest.mark.asyncio
    async def test_scan_blocks_eval(self) -> None:
        sandbox = SkillSandbox()
        ctx = SandboxContext(
            tenant_id=1,
            user_id=1,
            skill_key="test:skill",
            declared_permissions=["network:outbound"],
            source_code="eval('bad')",
        )
        with pytest.raises(PermissionError):
            sandbox.scan_before_run(ctx)

    def test_security_scanner_detects_os_system(self) -> None:
        result = plugin_security_scanner.scan_source("os.system('rm')", "run.py")
        assert result.passed is False


class TestGroupChatMonitor:
    """群聊监控指标结构。"""

    @pytest.mark.asyncio
    async def test_get_group_chat_stats_empty(self) -> None:
        service = MonitorService()
        stats = await service.get_group_chat_stats(days=7)
        assert "session_count" in stats
        assert "review_pass_rate" in stats


class TestTemplateMarket:
    """行业模板市场。"""

    def test_official_templates_50_plus(self) -> None:
        assert len(OFFICIAL_TEMPLATE_CATALOG) >= 50
