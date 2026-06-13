"""知识库解析进度 API 状态映射单元测试。"""

from app.services.knowledge_base_service import (
    DOCUMENT_STATUS_DONE,
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_PENDING,
    KnowledgeBaseService,
)


class TestResolveStatusFromParse:
    def test_failed_maps_to_status_2(self) -> None:
        assert (
            KnowledgeBaseService._resolve_status_from_parse("failed", DOCUMENT_STATUS_PENDING)
            == DOCUMENT_STATUS_FAILED
        )

    def test_completed_maps_to_status_1(self) -> None:
        assert (
            KnowledgeBaseService._resolve_status_from_parse("completed", DOCUMENT_STATUS_PENDING)
            == DOCUMENT_STATUS_DONE
        )

    def test_processing_maps_to_pending(self) -> None:
        assert (
            KnowledgeBaseService._resolve_status_from_parse("processing", DOCUMENT_STATUS_DONE)
            == DOCUMENT_STATUS_PENDING
        )
