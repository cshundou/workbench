"""
工作流版本历史模型。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.workflow import Workflow


class WorkflowVersion(Base):
    """工作流版本快照（不可删除）。"""

    __tablename__ = "workflow_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    graph_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    change_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    workflow: Mapped["Workflow"] = relationship()
    publisher: Mapped[Optional["User"]] = relationship()
