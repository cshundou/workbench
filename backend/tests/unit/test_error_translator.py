"""错误翻译与用户建议单元测试。"""

from app.utils.error_translator import translate_error, translate_error_message


class TestErrorTranslator:
    """错误中文化与建议规则。"""

    def test_none_type_assignment_knowledge_node(self) -> None:
        raw = "'NoneType' object does not support item assignment"
        facing = translate_error(
            raw,
            context={"failed_node_id": "knowledge_agent"},
        )
        assert facing.error_code == "WORKFLOW_STATE_CORRUPT"
        assert "知识库节点" in facing.user_message
        assert facing.raw_error == raw
        assert len(facing.suggestions) >= 1

    def test_unknown_error_fallback(self) -> None:
        facing = translate_error("some weird internal crash xyz")
        assert facing.error_code == "UNKNOWN"
        assert "执行失败" in facing.user_message
        assert facing.raw_error == "some weird internal crash xyz"

    def test_translate_existing_chinese_message(self) -> None:
        facing = translate_error_message("工作流已被用户终止")
        assert facing.user_message == "工作流已被用户终止"
        assert facing.error_code == "BUSINESS_ERROR"

    def test_kb_not_configured_pattern(self) -> None:
        facing = translate_error("ValidationError: 未配置知识库")
        assert facing.error_code == "KB_NOT_CONFIGURED"
        assert "知识库" in facing.user_message

    def test_async_loop_error(self) -> None:
        facing = translate_error("Task got Future attached to a different loop")
        assert facing.error_code == "ASYNC_LOOP_ERROR"
        assert "重新执行" in facing.user_message
