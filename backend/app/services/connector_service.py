"""
企业系统连接器服务。

预置钉钉、企业微信、飞书、通用 REST 等连接器类型。
"""

import logging
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.enterprise_connector import EnterpriseConnector
from app.models.user import User

logger = logging.getLogger(__name__)

CONNECTOR_PRESETS: dict[str, dict[str, Any]] = {
    "dingtalk": {
        "label": "钉钉",
        "required_fields": ["webhook_url"],
        "description": "通过钉钉机器人 Webhook 发送消息",
    },
    "wecom": {
        "label": "企业微信",
        "required_fields": ["corp_id", "agent_id", "secret"],
        "description": "企业微信应用消息推送",
    },
    "feishu": {
        "label": "飞书",
        "required_fields": ["app_id", "app_secret"],
        "description": "飞书开放平台机器人",
    },
    "generic_rest": {
        "label": "通用 REST",
        "required_fields": ["base_url"],
        "description": "标准 REST API 连接器",
    },
    "mysql": {
        "label": "MySQL",
        "required_fields": ["host", "database", "username", "password"],
        "description": "MySQL 数据库连接器（只读查询）",
    },
}


class ConnectorService:
    """企业连接器 CRUD 与调用。"""

    def list_presets(self) -> list[dict[str, Any]]:
        """返回预置连接器类型列表。"""
        return [
            {"type": key, **value} for key, value in CONNECTOR_PRESETS.items()
        ]

    async def list_connectors(
        self, db: AsyncSession, tenant_id: int
    ) -> list[EnterpriseConnector]:
        """列出租户连接器。"""
        stmt = (
            select(EnterpriseConnector)
            .where(EnterpriseConnector.tenant_id == tenant_id)
            .order_by(EnterpriseConnector.updated_at.desc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def create_connector(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        connector_type: str,
        name: str,
        config: dict[str, Any],
    ) -> EnterpriseConnector:
        """创建连接器。"""
        preset = CONNECTOR_PRESETS.get(connector_type)
        if preset is None:
            raise ValidationError(message=f"不支持的连接器类型: {connector_type}")
        for field in preset["required_fields"]:
            if not config.get(field):
                raise ValidationError(message=f"缺少必填配置: {field}")

        record = EnterpriseConnector(
            tenant_id=tenant_id,
            owner_id=user.id,
            connector_type=connector_type,
            name=name,
            config=config,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        return record

    async def test_connector(self, connector: EnterpriseConnector) -> dict[str, Any]:
        """测试连接器连通性。"""
        try:
            if connector.connector_type == "dingtalk":
                webhook = connector.config.get("webhook_url", "")
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        webhook,
                        json={"msgtype": "text", "text": {"content": "AI Workbench 连接测试"}},
                    )
                    return {"success": resp.status_code < 400, "status": resp.status_code}
            if connector.connector_type == "generic_rest":
                base_url = connector.config.get("base_url", "")
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(base_url)
                    return {"success": resp.status_code < 500, "status": resp.status_code}
            return {"success": True, "message": "配置已保存（该类型需业务侧验证）"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def get_or_raise(
        self, db: AsyncSession, connector_id: int, tenant_id: int
    ) -> EnterpriseConnector:
        stmt = select(EnterpriseConnector).where(
            EnterpriseConnector.id == connector_id,
            EnterpriseConnector.tenant_id == tenant_id,
        )
        record = (await db.execute(stmt)).scalar_one_or_none()
        if record is None:
            raise NotFoundError(message="连接器不存在")
        return record


connector_service = ConnectorService()
