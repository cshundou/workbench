"""
专业角色与团队模板 Pydantic 模式。
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ProfessionalRoleCreate(BaseModel):
    """创建自定义专业角色。"""

    role_id: str = Field(..., min_length=1, max_length=50, description="角色标识")
    name: str = Field(..., min_length=1, max_length=100, description="角色名称")
    avatar: str = Field(default="🤖", max_length=20, description="头像 emoji")
    category: str = Field(default="custom", max_length=50, description="角色分类")
    system_prompt: str = Field(..., min_length=1, description="系统提示词")
    tools: List[str] = Field(default_factory=list, description="可用工具列表")
    responsibility: str = Field(..., min_length=1, description="职责描述")
    color: str = Field(default="#1677FF", max_length=20, description="主题色")


class ProfessionalRoleUpdate(BaseModel):
    """更新专业角色。"""

    name: Optional[str] = Field(default=None, max_length=100)
    avatar: Optional[str] = Field(default=None, max_length=20)
    category: Optional[str] = Field(default=None, max_length=50)
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    responsibility: Optional[str] = None
    color: Optional[str] = Field(default=None, max_length=20)


class ProfessionalRoleResponse(BaseModel):
    """专业角色响应。"""

    id: int
    tenant_id: Optional[int] = None
    role_id: str
    name: str
    avatar: str
    category: str
    system_prompt: str
    tools: List[str]
    responsibility: str
    color: str
    is_preset: bool
    is_builtin: bool
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamMemberConfig(BaseModel):
    """团队成员配置。"""

    role_id: str
    name: str
    avatar: str = "🤖"
    responsibility: str = ""
    tools: List[str] = Field(default_factory=list)
    subtasks: List[str] = Field(default_factory=list)
    system_prompt: Optional[str] = None
    color: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list, description="依赖的角色 ID 列表")
    parallel_group: Optional[str] = Field(default=None, description="并行组标识")
    execution_mode: str = Field(
        default="llm",
        description="执行模式：llm=纯大模型，task=任务执行（工具驱动）",
    )
    task_tools: List[str] = Field(
        default_factory=list,
        description="任务模式允许的能力工具，如 browser/terminal",
    )


class TeamConfig(BaseModel):
    """结构化团队配置（团队组建器输出）。"""

    team_id: str
    task_description: str
    team_size: int
    members: List[TeamMemberConfig]
    workflow: str = ""
    max_review_rounds: int = 3
    domain: str = "general"
    complexity: str = "medium"
    template_id: Optional[str] = "dynamic"


class TeamBuildRequest(BaseModel):
    """智能组队请求。"""

    task: str = Field(..., min_length=1, description="任务描述")
    template_id: Optional[str] = Field(
        default=None,
        description="团队模板 ID（支持经典模板别名或数据库模板 ID）",
    )
    team_config: Optional[TeamConfig] = Field(
        default=None,
        description="用户自定义团队配置（覆盖自动组队）",
    )


class TeamTemplateCreate(BaseModel):
    """创建团队模板。"""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    scenario: str = Field(default="custom", max_length=50)
    team_config: dict[str, Any]
    is_public: bool = False


class TeamTemplateResponse(BaseModel):
    """团队模板响应。"""

    id: int
    tenant_id: Optional[int] = None
    user_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    scenario: str
    team_config: dict[str, Any]
    is_official: bool
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamAdjustRequest(BaseModel):
    """中途调整团队请求。"""

    members: List[TeamMemberConfig]
    reassign_subtasks: Optional[dict[str, str]] = Field(
        default=None,
        description="子任务 ID 到角色 ID 的重新分配",
    )
