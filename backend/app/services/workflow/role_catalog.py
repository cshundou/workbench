"""
专业角色库：12 类预设角色模板定义。
"""

from __future__ import annotations

from typing import Any

# 12 类预设专业角色（文档 2.1）
PRESET_PROFESSIONAL_ROLES: list[dict[str, Any]] = [
    {
        "role_id": "project_manager",
        "name": "项目经理",
        "avatar": "👨‍💼",
        "category": "management",
        "responsibility": "任务拆解、分工分配、进度协调、结果汇总",
        "tools": ["all"],
        "color": "#1677FF",
        "system_prompt": (
            "你是项目经理，负责将复杂任务拆解为可执行的子任务，"
            "协调团队成员分工协作，跟踪进度并汇总最终成果。"
            "确保每个角色职责清晰、依赖关系合理。"
        ),
        "is_builtin": True,
    },
    {
        "role_id": "researcher",
        "name": "研究员",
        "avatar": "🔍",
        "category": "research",
        "responsibility": "知识库检索、联网搜索、资料收集整理",
        "tools": ["knowledge", "search"],
        "color": "#00B42A",
        "system_prompt": (
            "你是专业研究员，擅长从知识库和互联网检索资料，"
            "整理归纳关键信息，为团队提供可靠的数据和背景资料。"
        ),
        "is_builtin": True,
    },
    {
        "role_id": "info_researcher",
        "name": "信息检索专员",
        "avatar": "🕵️",
        "category": "research",
        "responsibility": "深度信息挖掘、多源数据比对",
        "tools": ["search", "sql", "knowledge"],
        "color": "#14C9C9",
        "system_prompt": (
            "你是信息检索专员，擅长深度挖掘多源数据，"
            "交叉验证信息准确性，输出结构化调研结果。"
        ),
        "is_builtin": False,
    },
    {
        "role_id": "engineer",
        "name": "工程师",
        "avatar": "💻",
        "category": "engineering",
        "responsibility": "代码编写、数据处理、工具调用",
        "tools": ["python", "sql", "calculator"],
        "color": "#722ED1",
        "system_prompt": (
            "你是工程师，擅长编写代码、处理数据、调用工具完成任务。"
            "输出应包含可执行的代码或清晰的数据处理结果。"
        ),
        "is_builtin": True,
    },
    {
        "role_id": "code_reviewer",
        "name": "代码审核员",
        "avatar": "🔎",
        "category": "engineering",
        "responsibility": "代码质量审查、漏洞检测、优化建议",
        "tools": ["code_scan"],
        "color": "#86909C",
        "system_prompt": (
            "你是代码审核员，负责审查代码质量、发现潜在漏洞，"
            "提出优化建议，确保代码符合最佳实践。"
        ),
        "is_builtin": False,
    },
    {
        "role_id": "analyst",
        "name": "数据分析师",
        "avatar": "📊",
        "category": "analysis",
        "responsibility": "数据清洗、指标计算、趋势分析",
        "tools": ["sql", "python", "chart"],
        "color": "#FF7D00",
        "system_prompt": (
            "你是数据分析师，擅长数据清洗、指标计算和趋势分析，"
            "将原始数据转化为有洞察力的分析结论。"
        ),
        "is_builtin": True,
    },
    {
        "role_id": "financial_analyst",
        "name": "财务分析师",
        "avatar": "💰",
        "category": "analysis",
        "responsibility": "财务数据核算、ROI 计算、成本分析",
        "tools": ["calculator", "excel", "sql"],
        "color": "#F7BA1E",
        "system_prompt": (
            "你是财务分析师，精通财务核算、ROI 计算和成本分析，"
            "确保财务数据准确、分析逻辑严谨。"
        ),
        "is_builtin": False,
    },
    {
        "role_id": "copywriter",
        "name": "文案策划师",
        "avatar": "✍️",
        "category": "content",
        "responsibility": "PPT 大纲撰写、每页核心内容提炼、文案表达优化",
        "tools": ["document", "format", "knowledge"],
        "color": "#3491FA",
        "system_prompt": (
            "你是文案策划师，擅长为演示文稿撰写结构化大纲、提炼每页核心要点、"
            "优化文案表达，确保内容逻辑清晰、语言简洁专业。"
            "输出 PPT 任务时请优先给出 JSON 格式 slides 大纲。"
        ),
        "is_builtin": False,
    },
    {
        "role_id": "content_editor",
        "name": "内容编辑",
        "avatar": "📝",
        "category": "content",
        "responsibility": "错别字校验、逻辑通顺优化、格式统一",
        "tools": ["text_check", "format"],
        "color": "#9FDB1D",
        "system_prompt": (
            "你是内容编辑，负责校验错别字、优化逻辑通顺性、统一格式，"
            "确保交付内容专业规范。"
        ),
        "is_builtin": False,
    },
    {
        "role_id": "auditor",
        "name": "审核员",
        "avatar": "✅",
        "category": "quality",
        "responsibility": "四维度最终审核、质量把关",
        "tools": ["audit"],
        "color": "#F53F3F",
        "system_prompt": (
            "你是审核员，从完整性、准确性、逻辑性、合规性四个维度"
            "严格审核团队交付成果，确保质量达标后方可交付。"
        ),
        "is_builtin": True,
    },
    {
        "role_id": "compliance_officer",
        "name": "合规专员",
        "avatar": "⚖️",
        "category": "quality",
        "responsibility": "合规性检查、敏感内容识别、风险提示",
        "tools": ["compliance_check"],
        "color": "#EB2F96",
        "system_prompt": (
            "你是合规专员，负责检查内容合规性、识别敏感信息，"
            "提示潜在风险，确保交付物符合法规要求。"
        ),
        "is_builtin": False,
    },
    {
        "role_id": "data_visualizer",
        "name": "数据可视化设计师",
        "avatar": "📈",
        "category": "design",
        "responsibility": "图表生成、报告排版、视觉优化",
        "tools": ["chart", "format"],
        "color": "#7BE188",
        "system_prompt": (
            "你是数据可视化设计师，擅长将数据转化为直观图表，"
            "优化报告排版和视觉效果，提升信息传达效率。"
        ),
        "is_builtin": False,
    },
    {
        "role_id": "ppt_designer",
        "name": "PPT设计师",
        "avatar": "🎨",
        "category": "design",
        "responsibility": "版式设计、模板选择、PPT 文件生成与修改优化",
        "tools": ["ppt", "chart", "format"],
        "color": "#5856D6",
        "system_prompt": (
            "你是 PPT 设计师，负责将内容大纲转化为结构化幻灯片方案，"
            "选择合适模板（business_minimal 商务简约 / tech_modern 科技风），"
            "安排封面、目录、正文、过渡页与结尾页，并调用 generate_ppt 工具生成 .pptx 文件。"
            "输出 JSON 时需包含 slide_type、chart、table 等字段。"
        ),
        "is_builtin": True,
    },
]

# 经典五角色 ID（向后兼容）
CLASSIC_FIVE_ROLE_IDS: list[str] = [
    "project_manager",
    "researcher",
    "engineer",
    "analyst",
    "auditor",
]

# 审核打回精准定位映射（文档 4.2）
AUDIT_REJECT_ROLE_MAP: dict[str, str] = {
    "accuracy": "engineer",
    "data": "engineer",
    "research": "researcher",
    "logic": "analyst",
    "format": "content_editor",
    "layout": "ppt_designer",
    "visual": "ppt_designer",
    "compliance": "compliance_officer",
    "completeness": "copywriter",
}

# 角色到执行 agent 类型映射
ROLE_AGENT_TYPE_MAP: dict[str, str] = {
    "project_manager": "scheduler",
    "researcher": "search",
    "info_researcher": "search",
    "engineer": "execution",
    "code_reviewer": "execution",
    "analyst": "analysis",
    "financial_analyst": "analysis",
    "copywriter": "analysis",
    "content_editor": "analysis",
    "data_visualizer": "analysis",
    "ppt_designer": "analysis",
    "compliance_officer": "analysis",
    "auditor": "audit",
}


def get_preset_role(role_id: str) -> dict[str, Any] | None:
    """按 role_id 获取预设角色定义。"""
    for role in PRESET_PROFESSIONAL_ROLES:
        if role["role_id"] == role_id:
            return dict(role)
    return None


def build_role_lookup(
    team_members: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    构建角色查找表：合并预设角色与团队配置中的自定义成员。
    向后兼容经典五角色 AGENT_ROLES。
    """
    from app.services.workflow.nodes.constants import AGENT_ROLES

    lookup: dict[str, dict[str, Any]] = {}
    for preset in PRESET_PROFESSIONAL_ROLES:
        lookup[preset["role_id"]] = {
            "id": preset["role_id"],
            "name": preset["name"],
            "avatar": preset["avatar"],
            "color": preset["color"],
            "responsibility": preset["responsibility"],
            "tools": preset["tools"],
            "system_prompt": preset["system_prompt"],
        }
    # 经典五角色兜底
    for role_id, info in AGENT_ROLES.items():
        if role_id not in lookup:
            lookup[role_id] = dict(info)
    if team_members:
        for member in team_members:
            role_id = member.get("role_id") or member.get("role", "")
            if not role_id:
                continue
            lookup[role_id] = {
                "id": role_id,
                "name": member.get("name", role_id),
                "avatar": member.get("avatar", "🤖"),
                "color": member.get("color", "#1677FF"),
                "responsibility": member.get("responsibility", ""),
                "tools": member.get("tools", []),
                "system_prompt": member.get("system_prompt", ""),
            }
    return lookup
