"""添加用户最后登录 IP 字段。"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007_workflow_execution_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login_ip", sa.String(45), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_login_ip")
