"""
知识库模型。
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.chat_history import ChatHistory
    from app.models.document import Document
    from app.models.tenant import Tenant
    from app.models.user import User


class KnowledgeBase(Base, TimestampMixin):
    """知识库表。"""

    __tablename__ = "knowledge_bases"
    __table_args__ = (
        CheckConstraint("status IN (0, 1)", name="ck_knowledge_bases_status"),
        UniqueConstraint("tenant_id", "name", name="uq_knowledge_bases_tenant_id_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    embedding_model: Mapped[str] = mapped_column(
        String(50),
        default="text-embedding-ada-002",
        nullable=False,
    )
    chunk_size: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="knowledge_bases")
    owner: Mapped[Optional["User"]] = relationship(back_populates="owned_knowledge_bases")
    documents: Mapped[List["Document"]] = relationship(back_populates="knowledge_base")
    chat_histories: Mapped[List["ChatHistory"]] = relationship(back_populates="knowledge_base")
