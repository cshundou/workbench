"""
知识库 API 集成测试（无需数据库，验证路由可达与健康检查）。
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    """监控健康检查接口应返回 200。"""
    response = await client.get("/api/v1/monitor/health")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200


@pytest.mark.asyncio
async def test_unauthenticated_kb_list_returns_401(client: AsyncClient) -> None:
    """未认证访问知识库列表应被拒绝。"""
    response = await client.get("/api/v1/knowledge-bases")
    assert response.status_code == 401
