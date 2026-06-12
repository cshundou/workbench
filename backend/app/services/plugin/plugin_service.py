"""
插件生命周期与市场服务。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.plugin import Plugin, PluginInstallation, PluginReview, Skill
from app.models.user import User
from app.services.plugin.plugin_catalog import PLUGIN_CATALOG
from app.services.plugin.plugin_security import plugin_security_scanner

logger = logging.getLogger(__name__)


class PluginService:
    """插件市场与生命周期管理。"""

    async def ensure_catalog_seeded(self, db: AsyncSession) -> int:
        """确保官方插件目录已入库。"""
        created = 0
        for item in PLUGIN_CATALOG:
            existing = (
                await db.execute(
                    select(Plugin).where(Plugin.plugin_id == item["plugin_id"])
                )
            ).scalar_one_or_none()
            if existing:
                continue
            scan = plugin_security_scanner.scan_manifest(item)
            if not scan.passed and item.get("is_official"):
                logger.warning("官方插件扫描警告 %s: %s", item["plugin_id"], scan.issues)
            sig_check = plugin_security_scanner.verify_signature(
                item.get("signature"), bool(item.get("is_official"))
            )
            if not sig_check.passed:
                logger.warning("插件签名验证失败 %s", item["plugin_id"])

            record = Plugin(
                plugin_id=item["plugin_id"],
                name=item["name"],
                description=item["description"],
                author=item["author"],
                version=item["version"],
                icon=item.get("icon"),
                category=item["category"],
                tags=item.get("tags", []),
                permissions=item.get("permissions", []),
                manifest=item,
                is_official=bool(item.get("is_official")),
                is_featured=bool(item.get("is_featured")),
                signature=item.get("signature"),
                status="published",
            )
            db.add(record)
            await db.flush()
            for skill_name in item.get("skills", []):
                db.add(
                    Skill(
                        tenant_id=None,
                        skill_key=f"{item['plugin_id']}:{skill_name}",
                        name=skill_name.replace("-", " ").title(),
                        description=f"{item['name']} - {skill_name}",
                        source_type="plugin",
                        plugin_id=record.id,
                        handler=f"plugin://{item['plugin_id']}/skills/{skill_name}",
                        permissions=item.get("permissions", []),
                        is_native=False,
                        icon=item.get("icon"),
                        tags=item.get("tags", []),
                    )
                )
            created += 1
        await db.flush()
        logger.info("插件目录种子同步 created=%s", created)
        return created

    async def list_marketplace(
        self,
        db: AsyncSession,
        *,
        tenant_id: Optional[int] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        featured_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """插件市场列表（分类/搜索）。"""
        await self.ensure_catalog_seeded(db)
        stmt = select(Plugin).where(Plugin.status == "published")
        if category:
            stmt = stmt.where(Plugin.category == category)
        if featured_only:
            stmt = stmt.where(Plugin.is_featured.is_(True))
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Plugin.name.ilike(pattern),
                    Plugin.description.ilike(pattern),
                    Plugin.tags.astext.ilike(pattern),
                )
            )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(count_stmt)).scalar_one())
        stmt = stmt.order_by(Plugin.download_count.desc(), Plugin.rating_avg.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list((await db.execute(stmt)).scalars().all())
        install_map: dict[int, PluginInstallation] = {}
        if tenant_id is not None:
            install_rows = (
                await db.execute(
                    select(PluginInstallation).where(
                        PluginInstallation.tenant_id == tenant_id,
                        PluginInstallation.status != "uninstalled",
                    )
                )
            ).scalars().all()
            install_map = {row.plugin_id: row for row in install_rows}

        result_items: list[dict[str, Any]] = []
        for plugin in items:
            data = self._plugin_to_dict(plugin)
            inst = install_map.get(plugin.id)
            data["installation_status"] = inst.status if inst else None
            data["is_installed"] = inst is not None
            result_items.append(data)

        return {
            "items": result_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def update_installed_plugin(
        self,
        db: AsyncSession,
        tenant_id: int,
        plugin_id: str,
    ) -> PluginInstallation:
        """将已安装插件更新到市场最新版本。"""
        plugin = (
            await db.execute(select(Plugin).where(Plugin.plugin_id == plugin_id))
        ).scalar_one_or_none()
        if plugin is None:
            raise NotFoundError(message="插件不存在")

        installation = (
            await db.execute(
                select(PluginInstallation).where(
                    PluginInstallation.tenant_id == tenant_id,
                    PluginInstallation.plugin_id == plugin.id,
                    PluginInstallation.status != "uninstalled",
                )
            )
        ).scalar_one_or_none()
        if installation is None:
            raise NotFoundError(message="插件未安装")

        installation.installed_version = plugin.version
        await db.flush()
        logger.info(
            "插件已更新 tenant=%s plugin=%s version=%s",
            tenant_id,
            plugin_id,
            plugin.version,
        )
        return installation

    async def get_plugin_detail(
        self, db: AsyncSession, plugin_id: str
    ) -> dict[str, Any]:
        """插件详情（含 Skill 列表与评论）。"""
        await self.ensure_catalog_seeded(db)
        plugin = (
            await db.execute(select(Plugin).where(Plugin.plugin_id == plugin_id))
        ).scalar_one_or_none()
        if plugin is None:
            raise NotFoundError(message="插件不存在")

        skills = (
            await db.execute(select(Skill).where(Skill.plugin_id == plugin.id))
        ).scalars().all()
        reviews = (
            await db.execute(
                select(PluginReview)
                .where(PluginReview.plugin_id == plugin.id)
                .order_by(PluginReview.created_at.desc())
                .limit(20)
            )
        ).scalars().all()

        data = self._plugin_to_dict(plugin)
        data["skills"] = [
            {"skill_key": s.skill_key, "name": s.name, "description": s.description}
            for s in skills
        ]
        data["reviews"] = [
            {
                "rating": r.rating,
                "comment": r.comment,
                "user_id": r.user_id,
                "created_at": r.created_at.isoformat(),
            }
            for r in reviews
        ]
        data["manifest"] = plugin.manifest
        return data

    async def install_plugin(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        plugin_id: str,
    ) -> PluginInstallation:
        """安装插件。"""
        await self.ensure_catalog_seeded(db)
        plugin = (
            await db.execute(select(Plugin).where(Plugin.plugin_id == plugin_id))
        ).scalar_one_or_none()
        if plugin is None:
            raise NotFoundError(message="插件不存在")

        scan = plugin_security_scanner.scan_manifest(plugin.manifest or {})
        if not scan.passed:
            raise ValidationError(message=f"插件安全扫描未通过: {'; '.join(scan.issues)}")

        existing = (
            await db.execute(
                select(PluginInstallation).where(
                    PluginInstallation.tenant_id == tenant_id,
                    PluginInstallation.plugin_id == plugin.id,
                    PluginInstallation.status != "uninstalled",
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise ValidationError(message="插件已安装")

        installation = PluginInstallation(
            tenant_id=tenant_id,
            plugin_id=plugin.id,
            installed_by=user.id,
            status="enabled",
            installed_version=plugin.version,
            config={},
        )
        plugin.download_count = int(plugin.download_count or 0) + 1
        db.add(installation)
        await db.flush()
        logger.info("插件已安装 tenant=%s plugin=%s", tenant_id, plugin_id)
        return installation

    async def uninstall_plugin(
        self,
        db: AsyncSession,
        tenant_id: int,
        plugin_id: str,
    ) -> None:
        """卸载插件并清理安装记录。"""
        plugin = (
            await db.execute(select(Plugin).where(Plugin.plugin_id == plugin_id))
        ).scalar_one_or_none()
        if plugin is None:
            raise NotFoundError(message="插件不存在")

        installation = (
            await db.execute(
                select(PluginInstallation).where(
                    PluginInstallation.tenant_id == tenant_id,
                    PluginInstallation.plugin_id == plugin.id,
                    PluginInstallation.status != "uninstalled",
                )
            )
        ).scalar_one_or_none()
        if installation is None:
            raise NotFoundError(message="插件未安装")

        installation.status = "uninstalled"
        installation.config = {}
        await db.flush()
        logger.info("插件已卸载 tenant=%s plugin=%s", tenant_id, plugin_id)

    async def set_plugin_status(
        self,
        db: AsyncSession,
        tenant_id: int,
        plugin_id: str,
        enabled: bool,
    ) -> PluginInstallation:
        """启用/禁用已安装插件。"""
        plugin = (
            await db.execute(select(Plugin).where(Plugin.plugin_id == plugin_id))
        ).scalar_one_or_none()
        if plugin is None:
            raise NotFoundError(message="插件不存在")

        installation = (
            await db.execute(
                select(PluginInstallation).where(
                    PluginInstallation.tenant_id == tenant_id,
                    PluginInstallation.plugin_id == plugin.id,
                    PluginInstallation.status != "uninstalled",
                )
            )
        ).scalar_one_or_none()
        if installation is None:
            raise NotFoundError(message="插件未安装")

        installation.status = "enabled" if enabled else "disabled"
        await db.flush()
        return installation

    async def update_plugin_config(
        self,
        db: AsyncSession,
        tenant_id: int,
        plugin_id: str,
        config: dict[str, Any],
    ) -> PluginInstallation:
        """更新插件配置。"""
        plugin = (
            await db.execute(select(Plugin).where(Plugin.plugin_id == plugin_id))
        ).scalar_one_or_none()
        if plugin is None:
            raise NotFoundError(message="插件不存在")

        installation = (
            await db.execute(
                select(PluginInstallation).where(
                    PluginInstallation.tenant_id == tenant_id,
                    PluginInstallation.plugin_id == plugin.id,
                    PluginInstallation.status != "uninstalled",
                )
            )
        ).scalar_one_or_none()
        if installation is None:
            raise NotFoundError(message="插件未安装")

        installation.config = config
        await db.flush()
        return installation

    async def list_installed(
        self, db: AsyncSession, tenant_id: int
    ) -> list[dict[str, Any]]:
        """已安装插件列表。"""
        stmt = (
            select(PluginInstallation, Plugin)
            .join(Plugin, PluginInstallation.plugin_id == Plugin.id)
            .where(
                PluginInstallation.tenant_id == tenant_id,
                PluginInstallation.status != "uninstalled",
            )
            .order_by(PluginInstallation.updated_at.desc())
        )
        rows = (await db.execute(stmt)).all()
        result: list[dict[str, Any]] = []
        for installation, plugin in rows:
            item = self._plugin_to_dict(plugin)
            item["installation"] = {
                "id": installation.id,
                "status": installation.status,
                "installed_version": installation.installed_version,
                "config": installation.config,
                "installed_at": installation.installed_at.isoformat(),
                "has_update": installation.installed_version != plugin.version,
            }
            result.append(item)
        return result

    async def add_review(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        plugin_id: str,
        rating: int,
        comment: Optional[str] = None,
    ) -> PluginReview:
        """添加插件评分评论。"""
        if rating < 1 or rating > 5:
            raise ValidationError(message="评分范围为 1-5")

        plugin = (
            await db.execute(select(Plugin).where(Plugin.plugin_id == plugin_id))
        ).scalar_one_or_none()
        if plugin is None:
            raise NotFoundError(message="插件不存在")

        existing = (
            await db.execute(
                select(PluginReview).where(
                    PluginReview.plugin_id == plugin.id,
                    PluginReview.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            existing.rating = rating
            existing.comment = comment
            review = existing
        else:
            review = PluginReview(
                plugin_id=plugin.id,
                user_id=user.id,
                tenant_id=tenant_id,
                rating=rating,
                comment=comment,
            )
            db.add(review)

        await db.flush()
        avg_stmt = select(func.avg(PluginReview.rating), func.count()).where(
            PluginReview.plugin_id == plugin.id
        )
        avg_row = (await db.execute(avg_stmt)).one()
        plugin.rating_avg = float(avg_row[0] or 0)
        plugin.rating_count = int(avg_row[1] or 0)
        await db.flush()
        return review

    @staticmethod
    def _plugin_to_dict(plugin: Plugin) -> dict[str, Any]:
        return {
            "id": plugin.id,
            "plugin_id": plugin.plugin_id,
            "name": plugin.name,
            "description": plugin.description,
            "author": plugin.author,
            "version": plugin.version,
            "icon": plugin.icon,
            "category": plugin.category,
            "tags": plugin.tags,
            "permissions": plugin.permissions,
            "is_official": plugin.is_official,
            "is_featured": plugin.is_featured,
            "download_count": plugin.download_count,
            "rating_avg": plugin.rating_avg,
            "rating_count": plugin.rating_count,
        }


plugin_service = PluginService()
