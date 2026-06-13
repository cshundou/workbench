"""
文档解析进度 Redis 存储单元测试。
"""

import json

import pytest

from app.services.rag.rag_service import (
    PARSE_PROGRESS_KEY_PREFIX,
    RAGService,
)


class TestParseProgressRedis:
    """parse_progress:{doc_id} Redis 读写。"""

    @pytest.mark.asyncio
    async def test_set_and_get_progress(self, patch_get_redis) -> None:
        await RAGService.set_parse_progress(101, 50, "向量化中", status="processing")
        info = await RAGService.get_parse_progress(101)
        assert info is not None
        assert info["document_id"] == 101
        assert info["progress"] == 50
        assert info["message"] == "向量化中"
        assert info["status"] == "processing"

    @pytest.mark.asyncio
    async def test_progress_persists_in_redis_storage(self, patch_get_redis) -> None:
        """模拟服务重启：新 RAGService 实例仍可从 Redis 读取进度。"""
        await RAGService.set_parse_progress(202, 75, "向量化中 (3/4)")
        raw = patch_get_redis.storage.get(f"{PARSE_PROGRESS_KEY_PREFIX}202")
        assert raw is not None
        data = json.loads(raw)
        assert data["progress"] == 75

        info = await RAGService.get_parse_progress(202)
        assert info["progress"] == 75

    @pytest.mark.asyncio
    async def test_clear_progress(self, patch_get_redis) -> None:
        await RAGService.set_parse_progress(303, 100, "完成", status="completed")
        await RAGService.clear_parse_progress(303)
        assert await RAGService.get_parse_progress(303) is None

    @pytest.mark.asyncio
    async def test_missing_progress_returns_none(self, patch_get_redis) -> None:
        assert await RAGService.get_parse_progress(999) is None

    @pytest.mark.asyncio
    async def test_failed_progress_status(self, patch_get_redis) -> None:
        await RAGService.set_parse_progress(
            404,
            0,
            "Embedding API 密钥无效",
            status="failed",
        )
        info = await RAGService.get_parse_progress(404)
        assert info is not None
        assert info["status"] == "failed"
        assert "密钥" in info["message"]
