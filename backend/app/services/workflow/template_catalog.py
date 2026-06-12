"""
工作流模板市场目录（50+ 官方模板）。

按业务场景与行业分类生成模板元数据与图定义。
"""

from typing import Any

from app.services.workflow.graph_builder import STANDARD_GRAPH_DEFINITION

# 基础拓扑变体
_POLICY_GRAPH: dict[str, Any] = {
    "nodes": [
        {"id": "scheduler", "type": "scheduler", "label": "调度中心", "position": {"x": 400, "y": 0}, "config": {}},
        {"id": "knowledge_agent", "type": "knowledge", "label": "知识库 Agent", "position": {"x": 400, "y": 160}, "config": {}},
        {"id": "reviewer", "type": "reviewer", "label": "审核 Agent", "position": {"x": 400, "y": 320}, "config": {}},
    ],
    "edges": [
        {"id": "e1", "source": "scheduler", "target": "knowledge_agent"},
        {"id": "e2", "source": "knowledge_agent", "target": "reviewer"},
    ],
}

_PARALLEL_GRAPH = STANDARD_GRAPH_DEFINITION

_CATEGORIES: dict[str, list[str]] = {
    "客服": [
        "智能客服问答", "工单自动分类", "投诉处理助手", "FAQ 自动生成",
        "多轮对话引导", "客户情绪分析", "售后服务跟进", "退换货政策咨询",
        "产品使用指导", "VIP 客户专属服务",
    ],
    "销售": [
        "销售线索评分", "竞品对比分析", "报价方案生成", "合同条款审查",
        "客户画像分析", "销售话术推荐", "商机跟进提醒", "渠道业绩分析",
        "大客户方案", "销售预测报告",
    ],
    "市场": [
        "营销文案生成", "活动策划方案", "社媒内容日历", "品牌舆情监测",
        "广告投放分析", "市场调研报告", "用户增长分析", "SEO 关键词研究",
        "竞品广告追踪", "活动 ROI 评估",
    ],
    "人事": [
        "简历智能筛选", "面试问题生成", "员工手册问答", "绩效考核辅助",
        "入职流程引导",
    ],
    "财务": [
        "财务报表解读", "费用报销审核", "预算执行分析", "税务政策咨询",
        "成本优化建议",
    ],
    "行政": [
        "会议纪要生成", "行政通知起草", "办公用品采购", "差旅政策咨询",
        "固定资产管理",
    ],
}

_INDUSTRIES: dict[str, list[str]] = {
    "制造业": ["产线质检报告", "设备维护工单", "供应链风险预警"],
    "金融": ["信贷风险评估", "合规审查助手", "投研简报生成"],
    "医疗": ["病历摘要生成", "用药指南问答", "医保政策解读"],
    "教育": ["课程大纲设计", "作业批改辅助", "学情分析报告"],
    "零售": ["库存补货建议", "促销效果分析", "会员运营策略"],
}


def _slugify(text: str) -> str:
    """生成模板 ID 片段。"""
    return text.replace(" ", "_").replace("/", "_")[:40]


def _build_template(
    template_id: str,
    name: str,
    category: str,
    *,
    industry: str | None = None,
    graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建单条模板记录。"""
    desc_suffix = f"（{industry}行业）" if industry else ""
    use_parallel = category in ("销售", "市场", "客服") and "竞品" in name or "并行" in name
    return {
        "id": template_id,
        "name": name,
        "description": f"{category}场景：{name}{desc_suffix}，基于多 Agent 协同自动完成",
        "category": category,
        "industry": industry,
        "graph_definition": graph or (_PARALLEL_GRAPH if use_parallel else _POLICY_GRAPH),
        "is_official": True,
    }


def build_all_templates() -> dict[str, dict[str, Any]]:
    """构建全部 50+ 官方模板。"""
    templates: dict[str, dict[str, Any]] = {}
    for category, names in _CATEGORIES.items():
        for name in names:
            tid = f"official_{_slugify(category)}_{_slugify(name)}"
            templates[tid] = _build_template(tid, name, category)

    for industry, names in _INDUSTRIES.items():
        for name in names:
            tid = f"industry_{_slugify(industry)}_{_slugify(name)}"
            templates[tid] = _build_template(
                tid, name, "行业方案", industry=industry, graph=_PARALLEL_GRAPH
            )

    return templates


OFFICIAL_TEMPLATE_CATALOG: dict[str, dict[str, Any]] = build_all_templates()


def list_catalog_templates(
    *,
    category: str | None = None,
    industry: str | None = None,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    """分页友好的模板列表（元数据）。"""
    items: list[dict[str, Any]] = []
    for tid, tpl in OFFICIAL_TEMPLATE_CATALOG.items():
        if category and tpl.get("category") != category:
            continue
        if industry and tpl.get("industry") != industry:
            continue
        if keyword:
            kw = keyword.lower()
            if kw not in tpl["name"].lower() and kw not in tpl.get("description", "").lower():
                continue
        items.append(
            {
                "id": tid,
                "name": tpl["name"],
                "description": tpl["description"],
                "category": tpl.get("category"),
                "industry": tpl.get("industry"),
                "is_official": tpl.get("is_official", True),
                "node_count": len(tpl["graph_definition"].get("nodes", [])),
            }
        )
    return items


def get_catalog_template(template_id: str) -> dict[str, Any] | None:
    """获取模板完整定义。"""
    return OFFICIAL_TEMPLATE_CATALOG.get(template_id)
