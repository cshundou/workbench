"""
文档模型。
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.document_chunk import DocumentChunk
    from app.models.knowledge_base import KnowledgeBase
    from app.models.tenant import Tenant
    from app.models.user import User


class Document(Base, TimestampMixin):
    """文档表。"""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("status IN (0, 1, 2)", name="ck_documents_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kb_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    uploader_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False, index=True)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    tenant: Mapped["Tenant"] = relationship()
    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
    uploader: Mapped[Optional["User"]] = relationship(back_populates="uploaded_documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship(back_populates="document")
