"""
内置工作流模板定义。

供「从模板创建」功能使用，仅复制拓扑不复制执行历史。
"""

from typing import Any

from app.services.workflow.graph_builder import STANDARD_GRAPH_DEFINITION

# 竞品调研：并行知识库 + 搜索 + 执行后审核
COMPETITOR_RESEARCH_TEMPLATE: dict[str, Any] = {
    "name": "竞品调研报告",
    "description": "并行检索内部资料、联网搜索与数据计算，汇总生成竞品调研报告",
    "graph_definition": STANDARD_GRAPH_DEFINITION,
}

# 政策问答：知识库 + 人工确认 + 审核
POLICY_QA_TEMPLATE: dict[str, Any] = {
    "name": "政策合规问答",
    "description": "基于企业知识库回答政策问题，支持人工审核后输出",
    "graph_definition": {
        "nodes": [
            {
                "id": "scheduler",
                "type": "scheduler",
                "label": "调度中心",
                "position": {"x": 400, "y": 0},
                "config": {},
            },
            {
                "id": "knowledge_agent",
                "type": "knowledge",
                "label": "知识库 Agent",
                "position": {"x": 250, "y": 160},
                "config": {},
            },
            {
                "id": "human_intervention",
                "type": "human",
                "label": "人工介入",
                "position": {"x": 400, "y": 320},
                "config": {},
            },
            {
                "id": "reviewer",
                "type": "reviewer",
                "label": "审核 Agent",
                "position": {"x": 400, "y": 480},
                "config": {},
            },
        ],
        "edges": [
            {"id": "e1", "source": "scheduler", "target": "knowledge_agent"},
            {"id": "e2", "source": "knowledge_agent", "target": "human_intervention"},
            {"id": "e3", "source": "human_intervention", "target": "reviewer"},
        ],
    },
}

# 数据分析：执行 + 循环优化
DATA_ANALYSIS_TEMPLATE: dict[str, Any] = {
    "name": "数据分析流水线",
    "description": "执行 Agent 处理数据，循环优化直到满足指标条件",
    "graph_definition": {
        "nodes": [
            {
                "id": "scheduler",
                "type": "scheduler",
                "label": "调度中心",
                "position": {"x": 400, "y": 0},
                "config": {},
            },
            {
                "id": "execution_agent",
                "type": "execution",
                "label": "执行 Agent",
                "position": {"x": 400, "y": 160},
                "config": {},
            },
            {
                "id": "loop_check",
                "type": "loop",
                "label": "循环检查",
                "position": {"x": 400, "y": 320},
                "config": {
                    "loop_condition": "分析结果已包含明确的数值结论且误差可接受",
                    "max_iterations": 5,
                },
            },
            {
                "id": "reviewer",
                "type": "reviewer",
                "label": "审核 Agent",
                "position": {"x": 400, "y": 480},
                "config": {},
            },
        ],
        "edges": [
            {"id": "e1", "source": "scheduler", "target": "execution_agent"},
            {"id": "e2", "source": "execution_agent", "target": "loop_check"},
            {"id": "e3", "source": "loop_check", "target": "execution_agent"},
            {"id": "e4", "source": "loop_check", "target": "reviewer"},
        ],
    },
}

WORKFLOW_TEMPLATES: dict[str, dict[str, Any]] = {
    "competitor_research": COMPETITOR_RESEARCH_TEMPLATE,
    "policy_qa": POLICY_QA_TEMPLATE,
    "data_analysis": DATA_ANALYSIS_TEMPLATE,
}


def list_workflow_templates() -> list[dict[str, Any]]:
    """返回模板列表（不含完整 graph，仅元数据）。"""
    return [
        {
            "id": template_id,
            "name": item["name"],
            "description": item["description"],
            "node_count": len(item["graph_definition"].get("nodes", [])),
        }
        for template_id, item in WORKFLOW_TEMPLATES.items()
    ]


def get_workflow_template(template_id: str) -> dict[str, Any] | None:
    """按 ID 获取模板完整定义。"""
    return WORKFLOW_TEMPLATES.get(template_id)
