"""
智能团队组建引擎：任务驱动的动态组队四步逻辑。
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from app.services.workflow.role_catalog import (
    CLASSIC_FIVE_ROLE_IDS,
    PRESET_PROFESSIONAL_ROLES,
    get_preset_role,
)
from app.services.workflow.team_template_catalog import (
    OFFICIAL_TEAM_TEMPLATES,
    get_official_template,
)

from app.services.delivery.task_intent import detect_delivery_format

logger = logging.getLogger(__name__)

# 领域关键词映射
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "presentation": [
        "ppt",
        "pptx",
        "幻灯片",
        "演示文稿",
        "演示材料",
        "汇报材料",
        "路演",
        "课件",
        "powerpoint",
        "presentation",
    ],
    "tech": ["代码", "开发", "编程", "api", "系统", "架构", "bug", "python", "java"],
    "finance": ["财务", "roi", "成本", "预算", "核算", "利润", "收入", "投资"],
    "marketing": ["营销", "广告", "投放", "推广", "品牌", "竞品", "市场"],
    "legal": ["法律", "合规", "合同", "条款", "法规", "政策"],
    "research": ["调研", "研究", "报告", "分析", "行业", "趋势"],
    "content": ["文案", "撰写", "编辑", "润色", "内容", "文章"],
}

# 复杂度评估关键词
COMPLEXITY_KEYWORDS: dict[str, list[str]] = {
    "simple": ["简单", "快速", "简要", "概述", "一句话"],
    "complex": ["全面", "深度", "详细", "完整", "多维度", "综合", "系统"],
}


class TeamBuilder:
    """
    团队组建器：领域识别 → 复杂度评估 → 角色匹配 → 分工规划。
    """

    MIN_TEAM_SIZE = 2
    MAX_TEAM_SIZE = 8

    def build(
        self,
        task: str,
        *,
        template_id: Optional[str] = None,
        custom_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        根据任务描述组建团队，返回标准化团队配置。

        Args:
            task: 任务描述
            template_id: 可选模板 ID（classic_five 或官方模板）
            custom_config: 用户自定义团队配置（优先使用）
        """
        if custom_config:
            config = dict(custom_config)
            config.setdefault("team_id", f"team_{uuid.uuid4().hex[:12]}")
            config.setdefault("task_description", task)
            config["members"] = self._ensure_auditor(config.get("members", []))
            config["team_size"] = len(config["members"])
            return config

        if template_id == "classic_five":
            return self.build_classic_five(task)

        official = get_official_template(template_id) if template_id else None
        if official:
            config = dict(official["team_config"])
            config["team_id"] = f"team_{uuid.uuid4().hex[:12]}"
            config["task_description"] = task
            config["template_id"] = template_id
            return config

        domain = self.identify_domain(task)
        delivery_format = detect_delivery_format(task)
        if delivery_format == "ppt":
            domain = "presentation"
        complexity = self.assess_complexity(task)
        team_size = self.determine_team_size(complexity)
        members = self.match_roles(task, domain, team_size, complexity=complexity)
        members = self.plan_work_distribution(task, members)
        members = self._ensure_auditor(members)

        workflow = self._build_workflow_string(members)
        config: dict[str, Any] = {
            "team_id": f"team_{uuid.uuid4().hex[:12]}",
            "task_description": task,
            "team_size": len(members),
            "members": members,
            "workflow": workflow,
            "workflow_phases": self.build_workflow_phases(members),
            "max_review_rounds": 3,
            "domain": domain,
            "complexity": complexity,
            "template_id": "dynamic",
            "delivery_format": delivery_format,
        }
        logger.info(
            "团队组建完成 domain=%s complexity=%s size=%d",
            domain,
            complexity,
            len(members),
        )
        return config

    def build_classic_five(self, task: str) -> dict[str, Any]:
        """经典五角色模板（向后兼容）。"""
        members: list[dict[str, Any]] = []
        for role_id in CLASSIC_FIVE_ROLE_IDS:
            preset = get_preset_role(role_id)
            if preset is None:
                continue
            members.append(
                {
                    "role_id": role_id,
                    "name": preset["name"],
                    "avatar": preset["avatar"],
                    "responsibility": preset["responsibility"],
                    "tools": preset["tools"],
                    "color": preset["color"],
                    "system_prompt": preset["system_prompt"],
                    "subtasks": self._default_subtasks_for_role(role_id, task),
                }
            )
        members = self.plan_work_distribution(task, members)
        delivery_format = detect_delivery_format(task)
        return {
            "team_id": f"team_{uuid.uuid4().hex[:12]}",
            "task_description": task,
            "team_size": len(members),
            "members": members,
            "workflow": "project_manager → researcher → engineer → analyst → auditor",
            "workflow_phases": self.build_workflow_phases(members),
            "max_review_rounds": 3,
            "domain": "presentation" if delivery_format == "ppt" else "general",
            "complexity": "medium",
            "template_id": "classic_five",
            "delivery_format": delivery_format,
        }

    @staticmethod
    def identify_domain(task: str) -> str:
        """步骤1：任务领域识别。"""
        task_lower = task.lower()
        scores: dict[str, int] = {domain: 0 for domain in DOMAIN_KEYWORDS}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw in task_lower:
                    scores[domain] += 1
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else "general"

    @staticmethod
    def assess_complexity(task: str) -> str:
        """步骤2：复杂度评估（simple / medium / complex）。"""
        task_lower = task.lower()
        if any(kw in task_lower for kw in COMPLEXITY_KEYWORDS["simple"]):
            return "simple"
        if any(kw in task_lower for kw in COMPLEXITY_KEYWORDS["complex"]):
            return "complex"
        # 根据任务长度和步骤词估算
        step_indicators = len(re.findall(r"[、，,;；]|以及|并且|同时", task))
        if len(task) < 30 and step_indicators == 0:
            return "simple"
        if len(task) > 100 or step_indicators >= 3:
            return "complex"
        return "medium"

    def determine_team_size(self, complexity: str) -> int:
        """根据复杂度确定团队规模（2-8 人）。"""
        size_map = {"simple": 3, "medium": 5, "complex": 7}
        return min(max(size_map.get(complexity, 5), self.MIN_TEAM_SIZE), self.MAX_TEAM_SIZE)

    def match_roles(
        self,
        task: str,
        domain: str,
        team_size: int,
        *,
        complexity: str = "medium",
    ) -> list[dict[str, Any]]:
        """步骤3：从角色库匹配专业角色。"""
        # 领域 → 优先角色
        domain_roles: dict[str, list[str]] = {
            "tech": ["project_manager", "engineer", "code_reviewer", "analyst", "auditor"],
            "finance": [
                "project_manager",
                "researcher",
                "financial_analyst",
                "copywriter",
                "auditor",
            ],
            "marketing": [
                "project_manager",
                "researcher",
                "analyst",
                "copywriter",
                "data_visualizer",
                "auditor",
            ],
            "legal": [
                "project_manager",
                "researcher",
                "compliance_officer",
                "copywriter",
                "auditor",
            ],
            "content": [
                "project_manager",
                "researcher",
                "copywriter",
                "content_editor",
                "auditor",
            ],
            "research": [
                "project_manager",
                "researcher",
                "info_researcher",
                "analyst",
                "auditor",
            ],
            "presentation": {
                "simple": [
                    "project_manager",
                    "analyst",
                    "ppt_designer",
                    "auditor",
                ],
                "medium": [
                    "project_manager",
                    "copywriter",
                    "ppt_designer",
                    "auditor",
                ],
                "complex": [
                    "project_manager",
                    "researcher",
                    "copywriter",
                    "ppt_designer",
                    "auditor",
                ],
            },
            "general": [
                "project_manager",
                "researcher",
                "engineer",
                "analyst",
                "auditor",
            ],
        }
        if domain == "presentation":
            preset_roles = domain_roles["presentation"].get(
                complexity,
                domain_roles["presentation"]["medium"],
            )
            role_ids = list(preset_roles)
        else:
            role_ids = domain_roles.get(domain, domain_roles["general"])
        # 按 team_size 裁剪（保留 auditor）
        selected: list[str] = []
        for rid in role_ids:
            if len(selected) >= team_size:
                break
            if rid == "auditor":
                continue
            selected.append(rid)
        if "auditor" not in selected and len(selected) < team_size:
            selected.append("auditor")
        elif "auditor" not in selected:
            selected[-1] = "auditor"

        members: list[dict[str, Any]] = []
        for role_id in selected[:team_size]:
            preset = get_preset_role(role_id)
            if preset is None:
                continue
            members.append(
                {
                    "role_id": role_id,
                    "name": preset["name"],
                    "avatar": preset["avatar"],
                    "responsibility": preset["responsibility"],
                    "tools": preset["tools"],
                    "color": preset["color"],
                    "system_prompt": preset["system_prompt"],
                    "subtasks": [],
                }
            )
        return members

    def plan_work_distribution(
        self,
        task: str,
        members: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """步骤4：分工规划，为每个角色分配子任务与阶段依赖。"""
        execution_roles = {
            m["role_id"]
            for m in members
            if m["role_id"] not in ("auditor", "project_manager", "analyst")
        }
        for member in members:
            role_id = member["role_id"]
            member["subtasks"] = self._default_subtasks_for_role(role_id, task)
            if role_id == "analyst":
                member["depends_on"] = [
                    m["role_id"]
                    for m in members
                    if m["role_id"] in execution_roles
                ]
                member["phase"] = 3
            elif role_id == "auditor":
                member["depends_on"] = [
                    m["role_id"] for m in members if m["role_id"] != "auditor"
                ]
                member["phase"] = 99
            elif role_id == "project_manager":
                member["depends_on"] = []
                member["phase"] = 1
            else:
                member["depends_on"] = ["project_manager"]
                member["phase"] = 2
        return members

    @staticmethod
    def build_workflow_phases(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """生成分阶段工作流描述（供统筹节点与前端时间线使用）。"""
        phase_map: dict[int, list[str]] = {}
        for member in members:
            role_id = member.get("role_id", "")
            if role_id == "auditor":
                continue
            phase = int(member.get("phase") or 2)
            phase_map.setdefault(phase, []).append(member.get("name", role_id))
        phases: list[dict[str, Any]] = [
            {
                "phase": 0,
                "label": "智能组队",
                "roles": [],
            },
        ]
        for phase_num in sorted(phase for phase in phase_map if phase < 99):
            roles = phase_map[phase_num]
            label = (
                "任务拆解与协调"
                if phase_num == 1
                else ("成果汇总分析" if phase_num == 3 else "执行阶段")
            )
            phases.append(
                {
                    "phase": phase_num,
                    "label": f"阶段{phase_num}：{label}",
                    "roles": roles,
                }
            )
        phases.append(
            {
                "phase": 100,
                "label": "终审交付",
                "roles": [
                    m.get("name", "审核员")
                    for m in members
                    if m.get("role_id") == "auditor"
                ],
            }
        )
        return phases

    @staticmethod
    def _default_subtasks_for_role(role_id: str, task: str) -> list[str]:
        """为角色生成默认子任务。"""
        subtask_map: dict[str, list[str]] = {
            "project_manager": ["任务拆解", "进度协调", "最终汇总"],
            "researcher": ["资料检索与整理"],
            "info_researcher": ["深度信息挖掘", "多源数据比对"],
            "engineer": ["数据处理与实现"],
            "code_reviewer": ["代码质量审查"],
            "analyst": ["数据分析与报告撰写"],
            "financial_analyst": ["财务核算", "ROI 分析"],
            "copywriter": ["报告撰写与润色"],
            "ppt_designer": ["选择模板并生成 PPT 文件"],
            "content_editor": ["内容校验与格式统一"],
            "compliance_officer": ["合规性检查"],
            "data_visualizer": ["幻灯片结构优化", "视觉层次与排版方案"],
            "auditor": ["完整性审核", "准确性审核", "合规性审核"],
        }
        if detect_delivery_format(task) == "ppt":
            subtask_map["copywriter"] = ["撰写演示文稿大纲与每页要点"]
            subtask_map["ppt_designer"] = ["选择模板、排版并生成 PPT 文件"]
            subtask_map["data_visualizer"] = ["优化幻灯片结构与视觉呈现"]
            subtask_map["researcher"] = ["检索演示主题相关资料"]
            subtask_map["analyst"] = ["汇总资料并补充幻灯片数据要点"]
            subtask_map["auditor"] = [
                "内容完整性审核",
                "版式与视觉审核",
                "合规性审核",
            ]
        defaults = subtask_map.get(role_id, [f"处理任务：{task[:50]}"])
        return defaults

    @staticmethod
    def _ensure_auditor(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """确保团队至少包含 1 名审核员。"""
        has_auditor = any(
            m.get("role_id") in ("auditor", "compliance_officer") for m in members
        )
        if has_auditor:
            return members
        auditor_preset = get_preset_role("auditor")
        if auditor_preset:
            members.append(
                {
                    "role_id": "auditor",
                    "name": auditor_preset["name"],
                    "avatar": auditor_preset["avatar"],
                    "responsibility": auditor_preset["responsibility"],
                    "tools": auditor_preset["tools"],
                    "color": auditor_preset["color"],
                    "system_prompt": auditor_preset["system_prompt"],
                    "subtasks": ["最终审核"],
                }
            )
        return members

    @staticmethod
    def _build_workflow_string(members: list[dict[str, Any]]) -> str:
        """生成工作流描述字符串。"""
        non_audit = [
            m["role_id"] for m in members if m.get("role_id") not in ("auditor",)
        ]
        parts = non_audit + ["auditor"]
        return " → ".join(parts)

    @staticmethod
    def list_official_templates() -> list[dict[str, Any]]:
        """返回官方场景模板列表。"""
        return [
            {
                "id": tpl["id"],
                "name": tpl["name"],
                "description": tpl.get("description", ""),
                "scenario": tpl.get("scenario", "general"),
                "team_size": len(tpl["team_config"].get("members", [])),
            }
            for tpl in OFFICIAL_TEAM_TEMPLATES
        ]


team_builder = TeamBuilder()
