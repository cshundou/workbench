"""企业级升级（阶段二/三）单元测试。"""

from app.core.guardrails import guardrails_service
from app.core.permission_policy import (
    DATA_SCOPE_SELF,
    check_data_scope,
    check_scene_access,
    parse_role_policy,
)
from app.services.workflow.template_catalog import (
    OFFICIAL_TEMPLATE_CATALOG,
    list_catalog_templates,
)


def test_template_catalog_has_50_plus() -> None:
    """模板市场至少 50 个官方模板。"""
    assert len(OFFICIAL_TEMPLATE_CATALOG) >= 50
    items = list_catalog_templates()
    assert len(items) >= 50


def test_industry_templates_exist() -> None:
    """至少 3 个行业深度模板。"""
    industries = {t.get("industry") for t in list_catalog_templates() if t.get("industry")}
    assert len(industries) >= 3


def test_pii_desensitization() -> None:
    """敏感内容 PII 脱敏。"""
    text = "联系我 13812345678 或卡号 6222021234567890123"
    result = guardrails_service.desensitize_pii(text)
    assert "13812345678" not in result
    assert "[手机号已脱敏]" in result


def test_four_d_permission_data_scope() -> None:
    """四维权限：数据范围 self 仅本人。"""
    assert check_data_scope(DATA_SCOPE_SELF, owner_id=1, user_id=1) is True
    assert check_data_scope(DATA_SCOPE_SELF, owner_id=1, user_id=2) is False


def test_four_d_permission_scene_weekday() -> None:
    """四维权限：场景规则解析。"""
    policy = parse_role_policy({"permissions": ["agent:read"], "data_scope": "all"})
    assert "agent:read" in policy["permissions"]
    assert check_scene_access({}) is True


def test_mcp_builtin_presets() -> None:
    """内置 MCP 预设非空。"""
    from app.services.mcp.mcp_service import BUILTIN_MCP_PRESETS

    assert len(BUILTIN_MCP_PRESETS) >= 3


def test_connector_presets() -> None:
    """企业连接器预置类型。"""
    from app.services.connector_service import CONNECTOR_PRESETS

    assert "dingtalk" in CONNECTOR_PRESETS
    assert "wecom" in CONNECTOR_PRESETS
    assert "feishu" in CONNECTOR_PRESETS
