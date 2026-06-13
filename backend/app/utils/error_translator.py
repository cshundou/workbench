"""
面向用户的错误翻译与修改建议。

将 Python 技术异常转为中文说明，并附带可操作的修复建议。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ErrorSuggestion:
    """单条修改建议。"""

    title: str
    description: str
    action_type: Optional[str] = None
    action_target: Optional[str] = None
    priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "action_type": self.action_type,
            "action_target": self.action_target,
            "priority": self.priority,
        }


@dataclass
class UserFacingError:
    """面向用户的错误信息。"""

    user_message: str
    error_code: str
    suggestions: list[ErrorSuggestion] = field(default_factory=list)
    raw_error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_message": self.user_message,
            "error_code": self.error_code,
            "suggestions": [s.to_dict() for s in self.suggestions],
            "raw_error": self.raw_error,
        }


def _base_suggestions_for_code(
    error_code: str,
    context: dict[str, Any],
) -> list[ErrorSuggestion]:
    """按错误码返回默认建议，并结合上下文增强。"""
    kb_id = context.get("kb_id")
    failed_node = context.get("failed_node_id") or context.get("failed_node")
    workflow_id = context.get("workflow_id")
    kb_route = f"/knowledge/{kb_id}" if kb_id else "/knowledge"
    execute_route = f"/workflows/{workflow_id}/execute" if workflow_id else None

    mapping: dict[str, list[ErrorSuggestion]] = {
        "WORKFLOW_STATE_CORRUPT": [
            ErrorSuggestion(
                title="重新执行工作流",
                description="当前失败可能由执行状态异常引起，请重新发起一次执行。",
                action_type="retry",
                action_target=execute_route,
                priority=1,
            ),
            ErrorSuggestion(
                title="联系管理员",
                description="若反复出现相同错误，请将执行 ID 提供给管理员排查。",
                priority=2,
            ),
        ],
        "KB_NOT_CONFIGURED": [
            ErrorSuggestion(
                title="选择知识库",
                description="执行页右侧需选择知识库，知识库 Agent 才能检索内部资料。",
                action_type="config",
                priority=1,
            ),
            ErrorSuggestion(
                title="前往知识库管理",
                description="确认目标知识库已创建且包含可用文档。",
                action_type="route",
                action_target=kb_route,
                priority=2,
            ),
        ],
        "KB_ACCESS_DENIED": [
            ErrorSuggestion(
                title="检查知识库权限",
                description="确认当前账号对该知识库具有读取权限。",
                action_type="route",
                action_target=kb_route,
                priority=1,
            ),
        ],
        "KB_EMPTY_DOCUMENTS": [
            ErrorSuggestion(
                title="上传并解析文档",
                description="知识库尚无已完成解析的文档，请先上传并等待解析完成。",
                action_type="route",
                action_target=kb_route,
                priority=1,
            ),
        ],
        "KB_DOC_LIST_PARSE": [
            ErrorSuggestion(
                title="刷新页面",
                description="文档列表数据加载异常，请刷新后重试。",
                action_type="retry",
                priority=1,
            ),
        ],
        "UNKNOWN": [
            ErrorSuggestion(
                title="查看执行日志",
                description="展开下方执行日志，定位具体失败节点与上下文。",
                action_type="open_node",
                action_target=str(failed_node) if failed_node else None,
                priority=1,
            ),
        ],
    }
    suggestions = list(mapping.get(error_code, mapping["UNKNOWN"]))

    doc_count = context.get("kb_document_count")
    if doc_count == 0 and error_code not in ("KB_NOT_CONFIGURED", "KB_EMPTY_DOCUMENTS"):
        suggestions.append(
            ErrorSuggestion(
                title="检查知识库文档",
                description="所选知识库可能没有可用文档，建议上传资料后再执行。",
                action_type="route",
                action_target=kb_route,
                priority=3,
            )
        )

    return sorted(suggestions, key=lambda s: s.priority)


def translate_error(
    exc: Exception | str,
    *,
    context: dict[str, Any] | None = None,
) -> UserFacingError:
    """
    将原始异常翻译为中文用户可读错误，并生成修改建议。

    Args:
        exc: 异常对象或错误字符串
        context: 可选上下文（failed_node_id、kb_id、workflow_id 等）
    """
    ctx = context or {}
    raw = str(exc).strip()
    failed_node = str(ctx.get("failed_node_id") or ctx.get("failed_node") or "")
    is_knowledge_node = "knowledge" in failed_node.lower()

    # asyncio 跨事件循环（群聊/工作流后台任务）
    if re.search(
        r"attached to a different loop|different event loop|Future.*loop",
        raw,
        re.IGNORECASE,
    ):
        return UserFacingError(
            user_message="后台任务线程异常，协作执行被中断，请点击「重新执行」重试",
            error_code="ASYNC_LOOP_ERROR",
            suggestions=_base_suggestions_for_code("WORKFLOW_STATE_CORRUPT", ctx),
            raw_error=raw,
        )

    # NoneType 下标赋值（工作流状态损坏）
    if re.search(r"NoneType.*item assignment", raw, re.IGNORECASE):
        msg = (
            "工作流内部状态异常，知识库节点未能正常记录执行结果"
            if is_knowledge_node
            else "工作流内部状态异常，节点未能正常记录执行结果"
        )
        return UserFacingError(
            user_message=msg,
            error_code="WORKFLOW_STATE_CORRUPT",
            suggestions=_base_suggestions_for_code("WORKFLOW_STATE_CORRUPT", ctx),
            raw_error=raw,
        )

    # 知识库未配置
    if any(
        kw in raw
        for kw in (
            "未配置知识库",
            "kb_id",
            "知识库 ID",
            "请选择知识库",
            "Knowledge base",
        )
    ) or "ValidationError" in raw and "知识库" in raw:
        return UserFacingError(
            user_message="未选择或未配置知识库，无法执行知识库检索",
            error_code="KB_NOT_CONFIGURED",
            suggestions=_base_suggestions_for_code("KB_NOT_CONFIGURED", ctx),
            raw_error=raw,
        )

    # 知识库访问
    if any(kw in raw for kw in ("不存在", "无权", "403", "NotFound", "无权限")) and (
        "知识库" in raw or "knowledge" in raw.lower() or "kb" in raw.lower()
    ):
        return UserFacingError(
            user_message="所选知识库不存在或无权访问",
            error_code="KB_ACCESS_DENIED",
            suggestions=_base_suggestions_for_code("KB_ACCESS_DENIED", ctx),
            raw_error=raw,
        )

    # 知识库检索/查询失败（已有中文前缀）
    if raw.startswith("查询失败:") or raw.startswith("知识库查询失败"):
        return UserFacingError(
            user_message=raw.replace("查询失败:", "知识库检索失败：").strip(),
            error_code="KB_QUERY_FAILED",
            suggestions=_base_suggestions_for_code("KB_EMPTY_DOCUMENTS", ctx),
            raw_error=raw,
        )

    if raw.startswith("配置错误:"):
        return UserFacingError(
            user_message=raw.replace("配置错误:", "配置错误：").strip(),
            error_code="KB_NOT_CONFIGURED",
            suggestions=_base_suggestions_for_code("KB_NOT_CONFIGURED", ctx),
            raw_error=raw,
        )

    # 用户终止
    if "用户终止" in raw or "cancelled" in raw.lower():
        return UserFacingError(
            user_message="工作流已被用户终止",
            error_code="USER_CANCELLED",
            suggestions=[],
            raw_error=raw,
        )

    # 工作流空状态
    if "空状态" in raw:
        return UserFacingError(
            user_message="工作流执行未返回有效状态，请重试",
            error_code="WORKFLOW_EMPTY_STATE",
            suggestions=_base_suggestions_for_code("WORKFLOW_STATE_CORRUPT", ctx),
            raw_error=raw,
        )

    # 文档列表类前端错误
    if "filter is not a function" in raw or "some is not a function" in raw:
        return UserFacingError(
            user_message="文档数据加载异常，请刷新页面后重试",
            error_code="KB_DOC_LIST_PARSE",
            suggestions=_base_suggestions_for_code("KB_DOC_LIST_PARSE", ctx),
            raw_error=raw,
        )

    execution_id = ctx.get("execution_id")
    suffix = f"（执行 ID: {execution_id}）" if execution_id else ""
    return UserFacingError(
        user_message=f"执行失败，请联系管理员并提供执行记录{suffix}",
        error_code="UNKNOWN",
        suggestions=_base_suggestions_for_code("UNKNOWN", ctx),
        raw_error=raw,
    )


def translate_error_message(
    error_message: str,
    *,
    context: dict[str, Any] | None = None,
) -> UserFacingError:
    """对已存储的错误字符串进行二次翻译（若已是中文业务文案则保留）。"""
    raw = error_message.strip()
    if not raw:
        return UserFacingError(
            user_message="工作流执行失败，详见执行日志",
            error_code="UNKNOWN",
            suggestions=_base_suggestions_for_code("UNKNOWN", context or {}),
        )

    # 已是中文业务文案（非典型 Python 异常）则直接返回并补充建议
    if not re.search(
        r"(Error|Exception|Traceback|NoneType|'[a-z_]+' object)",
        raw,
        re.IGNORECASE,
    ):
        return UserFacingError(
            user_message=raw,
            error_code="BUSINESS_ERROR",
            suggestions=_base_suggestions_for_code("UNKNOWN", context or {}),
            raw_error=None,
        )

    return translate_error(raw, context=context)
