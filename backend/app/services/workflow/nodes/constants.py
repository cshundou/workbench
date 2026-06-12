"""
群聊协同与工作流节点共享常量。
"""

from __future__ import annotations

from typing import Any

MAX_REVIEW_RETRIES = 3

# 标准五角色定义（群聊视图展示）
AGENT_ROLES: dict[str, dict[str, str]] = {
    "project_manager": {
        "id": "project_manager",
        "name": "项目经理",
        "avatar": "👨‍💼",
        "color": "#1677FF",
    },
    "researcher": {
        "id": "researcher",
        "name": "研究员",
        "avatar": "🔍",
        "color": "#00B42A",
    },
    "engineer": {
        "id": "engineer",
        "name": "工程师",
        "avatar": "💻",
        "color": "#722ED1",
    },
    "analyst": {
        "id": "analyst",
        "name": "分析师",
        "avatar": "📊",
        "color": "#FF7D00",
    },
    "auditor": {
        "id": "auditor",
        "name": "审核员",
        "avatar": "✅",
        "color": "#F53F3F",
    },
}

# 子任务 agent 类型到群聊角色的映射
SUBTASK_ROLE_MAP: dict[str, str] = {
    "knowledge": "researcher",
    "search": "researcher",
    "execution": "engineer",
    "analysis": "analyst",
}

PROGRESS_STEPS: list[dict[str, str]] = [
    {"key": "decompose", "label": "任务拆解"},
    {"key": "research", "label": "资料检索"},
    {"key": "engineering", "label": "工程实现"},
    {"key": "analysis", "label": "数据分析"},
    {"key": "review", "label": "成果审核"},
    {"key": "delivery", "label": "最终交付"},
]

# 工作流节点 id 到群聊角色的映射
NODE_GROUP_CHAT_ROLE: dict[str, str] = {
    "scheduler": "project_manager",
    "gc_init": "project_manager",
    "knowledge_agent": "researcher",
    "search_agent": "researcher",
    "execution_agent": "engineer",
    "reviewer": "auditor",
    "gc_audit": "auditor",
    "forced_audit": "auditor",
    "supervisor": "project_manager",
}
