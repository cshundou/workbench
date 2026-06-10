"""
数据库初始化脚本。

创建默认租户、超级管理员角色（拥有全部权限）及 admin 用户。

用法（在 backend 目录下执行）:
    python -m scripts.init_data
"""

import asyncio
import sys
from pathlib import Path

# 将 backend 目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import async_session_factory, close_db, init_db
from app.core.logging import get_logger, setup_logging
from app.core.permissions import DEFAULT_ADMIN_PERMISSIONS
from app.core.security import get_password_hash
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User

setup_logging()
logger = get_logger(__name__)

DEFAULT_TENANT_NAME = "默认租户"
DEFAULT_TENANT_DOMAIN = "default"
ADMIN_ROLE_NAME = "超级管理员"
ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"


async def init_default_data() -> None:
    """
    初始化默认租户、角色与用户。

    若数据已存在则跳过，保证脚本可重复执行。
    """
    await init_db()

    async with async_session_factory() as session:
        try:
            # 创建或获取默认租户
            tenant_stmt = select(Tenant).where(Tenant.domain == DEFAULT_TENANT_DOMAIN)
            tenant_result = await session.execute(tenant_stmt)
            tenant = tenant_result.scalar_one_or_none()

            if tenant is None:
                tenant = Tenant(
                    name=DEFAULT_TENANT_NAME,
                    domain=DEFAULT_TENANT_DOMAIN,
                    status=1,
                )
                session.add(tenant)
                await session.flush()
                logger.info("创建默认租户 id=%s domain=%s", tenant.id, tenant.domain)
            else:
                logger.info("默认租户已存在 id=%s", tenant.id)

            # 创建或获取超级管理员角色
            role_stmt = select(Role).where(
                Role.tenant_id == tenant.id,
                Role.name == ADMIN_ROLE_NAME,
            )
            role_result = await session.execute(role_stmt)
            admin_role = role_result.scalar_one_or_none()

            if admin_role is None:
                admin_role = Role(
                    tenant_id=tenant.id,
                    name=ADMIN_ROLE_NAME,
                    description="超级管理员，拥有所有权限",
                    permissions={"permissions": DEFAULT_ADMIN_PERMISSIONS},
                )
                session.add(admin_role)
                await session.flush()
                logger.info("创建超级管理员角色 id=%s", admin_role.id)
            else:
                logger.info("超级管理员角色已存在 id=%s", admin_role.id)

            # 创建或获取 admin 用户
            user_stmt = select(User).where(
                User.tenant_id == tenant.id,
                User.username == ADMIN_USERNAME,
            )
            user_result = await session.execute(user_stmt)
            admin_user = user_result.scalar_one_or_none()

            if admin_user is None:
                admin_user = User(
                    tenant_id=tenant.id,
                    username=ADMIN_USERNAME,
                    email=ADMIN_EMAIL,
                    password_hash=get_password_hash(ADMIN_PASSWORD),
                    role_id=admin_role.id,
                    status=1,
                )
                session.add(admin_user)
                await session.flush()
                logger.info("创建 admin 用户 id=%s", admin_user.id)
            else:
                logger.info("admin 用户已存在 id=%s", admin_user.id)

            await session.commit()
            logger.info(
                "初始化完成: tenant_id=%s, role_id=%s, user_id=%s",
                tenant.id,
                admin_role.id,
                admin_user.id,
            )
            print("数据库初始化成功")
            print(f"  租户: {tenant.name} ({tenant.domain})")
            print(f"  角色: {admin_role.name}")
            print(f"  用户: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
        except Exception as exc:
            await session.rollback()
            logger.error("初始化数据失败: %s", exc)
            raise
        finally:
            await close_db()


def main() -> None:
    """脚本入口。"""
    try:
        asyncio.run(init_default_data())
    except Exception as exc:
        print(f"初始化失败: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
