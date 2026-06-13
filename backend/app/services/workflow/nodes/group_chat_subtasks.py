"""
群聊协同子任务辅助函数（供统一工作流引擎复用）。
"""

from __future__ import annotations

from typing import Any, Optional

from app.services.workflow.nodes.constants import AGENT_ROLES, SUBTASK_ROLE_MAP
from app.services.workflow.role_catalog import ROLE_AGENT_TYPE_MAP, build_role_lookup


def enrich_subtasks_from_team_config(
    team_config: dict[str, Any],
    task: str,
) -> list[dict[str, Any]]:
    """
    根据动态团队配置生成子任务列表（支持串行依赖与并行组）。

    按 workflow 成员顺序分配子任务，跳过审核员与项目经理（除拆解外）。
    """
    members = team_config.get("members", [])
    subtasks: list[dict[str, Any]] = []
    idx = 0
    for member in members:
        role_id = member.get("role_id") or member.get("role", "")
        if role_id in ("auditor",):
            continue
        member_subtasks = member.get("subtasks") or []
        if role_id == "project_manager" and not member_subtasks:
            member_subtasks = ["任务拆解与协调"]
        if not member_subtasks:
            member_subtasks = [f"执行：{task[:80]}"]
        agent_type = ROLE_AGENT_TYPE_MAP.get(role_id, "search")
        if agent_type == "scheduler":
            agent_type = "search"
        for subtask_desc in member_subtasks:
            idx += 1
            subtasks.append(
                {
                    "id": f"subtask_{idx}",
                    "agent": agent_type,
                    "role": role_id,
                    "task": subtask_desc if role_id != "project_manager" else task,
                    "status": "pending",
                    "depends_on": member.get("depends_on", []),
                    "parallel_group": member.get("parallel_group"),
                    "phase": int(member.get("phase") or 2),
                }
            )
    if not subtasks:
        return enrich_subtasks_with_roles([], task)
    # 确保有汇总分析步骤
    analysis_roles = {
        r for r, t in ROLE_AGENT_TYPE_MAP.items() if t == "analysis"
    }
    if not any(s.get("role") in analysis_roles for s in subtasks):
        idx += 1
        subtasks.append(
            {
                "id": f"subtask_{idx}",
                "agent": "analysis",
                "role": "analyst",
                "task": f"基于团队成果汇总报告：{task}",
                "status": "pending",
            }
        )
    return subtasks


def enrich_subtasks_with_roles(
    raw_subtasks: list[dict[str, Any]],
    task: str,
) -> list[dict[str, Any]]:
    """将调度拆解结果转换为带群聊角色的子任务列表。"""
    subtasks: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_subtasks):
        agent_type = item.get("agent", "search")
        role = SUBTASK_ROLE_MAP.get(agent_type, "analyst")
        subtasks.append(
            {
                "id": f"subtask_{idx + 1}",
                "agent": agent_type,
                "role": role,
                "task": item.get("task", task),
                "status": "pending",
                "phase": 2 if role != "project_manager" else 1,
                "depends_on": ["project_manager"] if role not in ("project_manager",) else [],
            }
        )
    if not subtasks:
        subtasks.append(
            {
                "id": "subtask_1",
                "agent": "search",
                "role": "researcher",
                "task": task,
                "status": "pending",
                "phase": 2,
                "depends_on": ["project_manager"],
            }
        )
    if not any(s.get("role") == "analyst" for s in subtasks):
        exec_roles = [
            s.get("role")
            for s in subtasks
            if s.get("role") not in ("analyst", "project_manager", "auditor")
        ]
        subtasks.append(
            {
                "id": f"subtask_{len(subtasks) + 1}",
                "agent": "analysis",
                "role": "analyst",
                "task": f"基于已有资料汇总并生成分析报告：{task}",
                "status": "pending",
                "phase": 3,
                "depends_on": exec_roles,
            }
        )
    return subtasks


def _dependencies_met(
    subtask: dict[str, Any],
    subtasks: list[dict[str, Any]],
) -> bool:
    """检查子任务依赖是否已满足。"""
    depends_on = subtask.get("depends_on") or []
    if not depends_on:
        return True
    completed_roles = {
        s.get("role")
        for s in subtasks
        if s.get("status") == "completed"
    }
    return all(dep in completed_roles for dep in depends_on)


def get_pending_subtask(
    subtasks: list[dict[str, Any]],
    current_phase: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """获取下一个待执行子任务（按阶段 + 依赖调度）。"""
    for subtask in subtasks:
        status = subtask.get("status")
        if status in ("completed", "error"):
            continue
        if current_phase is not None and subtask.get("phase") != current_phase:
            continue
        if _dependencies_met(subtask, subtasks):
            return subtask
    return None


def has_pending_in_phase(
    subtasks: list[dict[str, Any]],
    phase: int,
) -> bool:
    """当前阶段是否仍有未完成的就绪子任务。"""
    return get_pending_subtask(subtasks, current_phase=phase) is not None


def get_next_phase(
    subtasks: list[dict[str, Any]],
    current_phase: int,
) -> Optional[int]:
    """获取下一个仍有待办任务的阶段号。"""
    phases = sorted(
        {
            int(s.get("phase") or 2)
            for s in subtasks
            if s.get("status") not in ("completed", "error")
            and int(s.get("phase") or 2) > current_phase
            and int(s.get("phase") or 2) < 99
        }
    )
    return phases[0] if phases else None


def mark_subtask_completed(subtasks: list[dict[str, Any]], subtask_id: str) -> None:
    """标记子任务完成。"""
    for subtask in subtasks:
        if subtask.get("id") == subtask_id:
            subtask["status"] = "completed"
            break


def calc_group_chat_progress(
    subtasks: list[dict[str, Any]],
    status: str,
    base_progress: float = 0.0,
) -> float:
    """计算群聊整体进度百分比。"""
    if not subtasks:
        return base_progress
    completed = sum(1 for t in subtasks if t.get("status") == "completed")
    base = (completed / len(subtasks)) * 80
    if status == "reviewing":
        return min(base + 10, 90)
    if status == "completed":
        return 100.0
    return min(base, 80.0)


def build_final_answer(
    task: str,
    deliverables: list[dict[str, Any]],
    review_result: dict[str, Any] | None,
    team_config: dict[str, Any] | None = None,
) -> str:
    """汇总最终交付物为报告文本。"""
    lookup = build_role_lookup((team_config or {}).get("members"))
    parts = [f"# 任务交付报告\n\n**任务**：{task}\n"]
    for item in deliverables:
        role_key = item.get("role", "")
        role_name = lookup.get(role_key, {}).get("name") or AGENT_ROLES.get(
            role_key, {}
        ).get("name", "成员")
        parts.append(f"\n## {role_name}交付\n\n{item.get('content', '')}")
    review = review_result or {}
    parts.append(f"\n\n---\n**审核结论**：{review.get('summary', '通过')}")
    return "\n".join(parts)
