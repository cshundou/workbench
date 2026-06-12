"""
官方插件 Skill 处理器注册表。

已安装且启用的插件 Skill 通过 handler 映射执行真实业务逻辑（模拟对接第三方 API）。
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

PluginHandler = Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]


async def _echo_handler(
    parameters: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """通用回显处理器。"""
    return {"success": True, "data": parameters, "config_applied": bool(config)}


async def _feishu_send_message(
    parameters: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    return {
        "success": True,
        "platform": "feishu",
        "message_id": "fs-msg-simulated",
        "to": parameters.get("to"),
        "text": parameters.get("text"),
        "webhook": config.get("webhook_url", "(未配置)"),
    }


async def _weather_query(
    parameters: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    city = parameters.get("city", "北京")
    return {
        "success": True,
        "city": city,
        "temperature": "26°C",
        "condition": "晴",
        "forecast": "未来 7 天以晴为主",
        "api_key_configured": bool(config.get("api_key")),
    }


async def _web_search(
    parameters: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    query = parameters.get("query", "")
    return {
        "success": True,
        "query": query,
        "results": [
            {"title": f"关于「{query}」的搜索结果 1", "url": "https://example.com/1"},
            {"title": f"关于「{query}」的搜索结果 2", "url": "https://example.com/2"},
        ],
    }


async def _send_email(
    parameters: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    return {
        "success": True,
        "to": parameters.get("to"),
        "subject": parameters.get("subject"),
        "smtp_host": config.get("smtp_host", "smtp.example.com"),
        "status": "queued",
    }


async def _run_code(
    parameters: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    language = parameters.get("language", "python")
    return {
        "success": True,
        "language": language,
        "stdout": f"// simulated output for: {parameters.get('code', '')[:80]}",
        "sandbox": config.get("sandbox_level", "basic"),
    }


# skill_key -> handler（与 catalog 中 plugin_id:skill_name 对应）
PLUGIN_SKILL_HANDLERS: dict[str, PluginHandler] = {
    "feishu-integration:send-message": _feishu_send_message,
    "feishu-integration:create-event": _echo_handler,
    "feishu-integration:get-approval": _echo_handler,
    "wecom-integration:send-wecom-message": _echo_handler,
    "dingtalk-integration:send-dingtalk-message": _echo_handler,
    "weather-query:weather-query": _weather_query,
    "email-sender:send-email": _send_email,
    "code-runner:run-code": _run_code,
    "web-search:web-search": _web_search,
    "salesforce-connector:sf-query-leads": _echo_handler,
    "report-generator:generate-report": _echo_handler,
    "hr-assistant:query-employee": _echo_handler,
    "hr-assistant:submit-leave": _echo_handler,
}


async def execute_plugin_handler(
    skill_key: str,
    parameters: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """执行已注册插件 Skill 处理器。"""
    handler = PLUGIN_SKILL_HANDLERS.get(skill_key)
    if handler is None:
        logger.warning("未注册插件 Skill 处理器 key=%s，使用默认回显", skill_key)
        return await _echo_handler(parameters, config or {})
    return await handler(parameters, config or {})
