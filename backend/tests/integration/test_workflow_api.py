"""
工作流 API 集成测试。
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_validate_graph_unauthenticated(client: AsyncClient) -> None:
    """未认证访问图校验应被拒绝。"""
    response = await client.post("/api/v1/workflows/1/validate-graph", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_replay_unauthenticated(client: AsyncClient) -> None:
    """未认证访问 replay 应被拒绝。"""
    response = await client.get("/api/v1/workflows/1/executions/1/replay")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_import_url_unauthenticated(client: AsyncClient) -> None:
    """未认证访问 URL 导入应被拒绝。"""
    response = await client.post(
        "/api/v1/knowledge-bases/1/import-url",
        json={"url": "https://example.com"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_unauthenticated_allowed(client: AsyncClient) -> None:
    """refresh 在白名单，无效 token 应返回 401 业务错误而非中间件拦截。"""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert response.status_code in (401, 422)
