"""
官方场景团队模板（10+ 预置模板）。
"""

from __future__ import annotations

from typing import Any, Optional

from app.services.workflow.role_catalog import get_preset_role


def _member(role_id: str, subtasks: list[str] | None = None) -> dict[str, Any]:
    """从预设角色构建成员配置。"""
    preset = get_preset_role(role_id)
    if preset is None:
        return {"role_id": role_id, "name": role_id, "avatar": "🤖", "subtasks": subtasks or []}
    return {
        "role_id": role_id,
        "name": preset["name"],
        "avatar": preset["avatar"],
        "responsibility": preset["responsibility"],
        "tools": preset["tools"],
        "color": preset["color"],
        "system_prompt": preset["system_prompt"],
        "subtasks": subtasks or [],
    }


def _build_config(
    template_id: str,
    name: str,
    members: list[dict[str, Any]],
    workflow: str,
    scenario: str = "general",
    description: str = "",
) -> dict[str, Any]:
    """构建标准团队配置。"""
    return {
        "id": template_id,
        "name": name,
        "description": description,
        "scenario": scenario,
        "team_config": {
            "team_id": template_id,
            "task_description": "",
            "team_size": len(members),
            "members": members,
            "workflow": workflow,
            "max_review_rounds": 3,
            "template_id": template_id,
        },
    }


OFFICIAL_TEAM_TEMPLATES: list[dict[str, Any]] = [
    _build_config(
        "classic_five",
        "经典五角色团队",
        [
            _member("project_manager"),
            _member("researcher"),
            _member("engineer"),
            _member("analyst"),
            _member("auditor"),
        ],
        "project_manager → researcher → engineer → analyst → auditor",
        "general",
        "向后兼容的经典五角色模式，适合通用复杂任务",
    ),
    _build_config(
        "data_analysis",
        "数据分析团队",
        [
            _member("project_manager", ["任务拆解", "进度协调"]),
            _member("researcher", ["数据采集"]),
            _member("engineer", ["数据清洗"]),
            _member("analyst", ["指标分析", "趋势解读"]),
            _member("data_visualizer", ["图表生成"]),
            _member("auditor"),
        ],
        "researcher → engineer → analyst → data_visualizer → auditor",
        "analysis",
        "适合数据分析、指标计算、趋势报告类任务",
    ),
    _build_config(
        "content_creation",
        "文案创作团队",
        [
            _member("project_manager"),
            _member("researcher", ["背景资料收集"]),
            _member("copywriter", ["初稿撰写"]),
            _member("content_editor", ["润色校对"]),
            _member("auditor"),
        ],
        "researcher → copywriter → content_editor → auditor",
        "content",
        "适合报告撰写、方案输出、内容创作类任务",
    ),
    _build_config(
        "code_development",
        "代码开发团队",
        [
            _member("project_manager"),
            _member("researcher", ["技术调研"]),
            _member("engineer", ["代码实现"]),
            _member("code_reviewer", ["代码审查"]),
            _member("auditor"),
        ],
        "researcher → engineer → code_reviewer → auditor",
        "tech",
        "适合代码开发、数据处理、工具实现类任务",
    ),
    _build_config(
        "research_report",
        "调研报告团队",
        [
            _member("project_manager"),
            _member("info_researcher", ["深度调研"]),
            _member("analyst", ["分析报告"]),
            _member("copywriter", ["报告撰写"]),
            _member("auditor"),
        ],
        "info_researcher → analyst → copywriter → auditor",
        "research",
        "适合行业调研、竞品分析、市场报告类任务",
    ),
    _build_config(
        "financial_analysis",
        "财务分析团队",
        [
            _member("project_manager"),
            _member("researcher", ["财务数据收集"]),
            _member("financial_analyst", ["ROI 核算", "成本分析"]),
            _member("copywriter", ["财务报告撰写"]),
            _member("auditor"),
        ],
        "researcher → financial_analyst → copywriter → auditor",
        "finance",
        "适合财务分析、成本核算、投资评估类任务",
    ),
    _build_config(
        "compliance_review",
        "合规审查团队",
        [
            _member("project_manager"),
            _member("researcher", ["法规检索"]),
            _member("compliance_officer", ["合规检查"]),
            _member("content_editor", ["格式规范"]),
            _member("auditor"),
        ],
        "researcher → compliance_officer → content_editor → auditor",
        "legal",
        "适合合规审查、政策解读、合同审核类任务",
    ),
    _build_config(
        "marketing_campaign",
        "营销策划团队",
        [
            _member("project_manager"),
            _member("researcher", ["市场调研"]),
            _member("analyst", ["投放分析"]),
            _member("copywriter", ["方案撰写"]),
            _member("data_visualizer", ["数据可视化"]),
            _member("auditor"),
        ],
        "researcher → analyst → copywriter → data_visualizer → auditor",
        "marketing",
        "适合营销策划、广告投放、竞品分析类任务",
    ),
    _build_config(
        "simple_research",
        "轻量调研团队",
        [
            _member("researcher", ["快速调研"]),
            _member("auditor", ["成果审核"]),
        ],
        "researcher → auditor",
        "research",
        "适合简单快速的调研任务（2 人团队）",
    ),
    _build_config(
        "tech_sprint",
        "技术攻坚团队",
        [
            _member("project_manager"),
            _member("engineer", ["核心实现"]),
            _member("code_reviewer", ["质量把关"]),
            _member("engineer", ["优化迭代"]),
            _member("auditor"),
        ],
        "engineer → code_reviewer → engineer → auditor",
        "tech",
        "适合技术攻坚、快速原型开发类任务",
    ),
    _build_config(
        "publishing",
        "内容出版团队",
        [
            _member("project_manager"),
            _member("copywriter", ["内容创作"]),
            _member("content_editor", ["编辑校对"]),
            _member("data_visualizer", ["排版美化"]),
            _member("auditor"),
        ],
        "copywriter → content_editor → data_visualizer → auditor",
        "content",
        "适合内容出版、文档制作类任务",
    ),
    _build_config(
        "data_visualization",
        "数据可视化团队",
        [
            _member("project_manager"),
            _member("analyst", ["数据分析"]),
            _member("data_visualizer", ["图表设计"]),
            _member("copywriter", ["报告说明"]),
            _member("auditor"),
        ],
        "analyst → data_visualizer → copywriter → auditor",
        "design",
        "适合数据可视化、图表报告类任务",
    ),
]


def get_official_template(template_id: str) -> Optional[dict[str, Any]]:
    """按 ID 获取官方模板。"""
    for tpl in OFFICIAL_TEAM_TEMPLATES:
        if tpl["id"] == template_id:
            return tpl
    return None
