"""API 访问级别策略单元测试。"""

from app.core.auth_policy import get_api_access_level


def test_public_config_auth() -> None:
    assert get_api_access_level("/api/v1/config/auth", "GET") == "public"


def test_optional_kb_list() -> None:
    assert get_api_access_level("/api/v1/knowledge-bases", "GET") == "optional"


def test_strict_kb_post() -> None:
    assert get_api_access_level("/api/v1/knowledge-bases", "POST") == "strict"
