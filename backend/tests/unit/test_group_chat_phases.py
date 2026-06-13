"""群聊分阶段调度单元测试（内联逻辑，避免 LangGraph 依赖链）。"""

from typing import Any, Optional


def _dependencies_met(subtask: dict[str, Any], subtasks: list[dict[str, Any]]) -> bool:
    depends_on = subtask.get("depends_on") or []
    if not depends_on:
        return True
    completed_roles = {
        s.get("role") for s in subtasks if s.get("status") == "completed"
    }
    return all(dep in completed_roles for dep in depends_on)


def _get_pending_subtask(
    subtasks: list[dict[str, Any]],
    current_phase: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    for subtask in subtasks:
        if subtask.get("status") in ("completed", "error"):
            continue
        if current_phase is not None and subtask.get("phase") != current_phase:
            continue
        if _dependencies_met(subtask, subtasks):
            return subtask
    return None


class TestGroupChatPhases:
    """分阶段子任务调度（与 group_chat_subtasks 逻辑一致）。"""

    def test_get_pending_respects_phase_and_depends_on(self) -> None:
        subtasks = [
            {
                "id": "1",
                "role": "project_manager",
                "status": "pending",
                "phase": 1,
                "depends_on": [],
            },
            {
                "id": "2",
                "role": "researcher",
                "status": "pending",
                "phase": 2,
                "depends_on": ["project_manager"],
            },
        ]
        first = _get_pending_subtask(subtasks, current_phase=1)
        assert first is not None and first.get("role") == "project_manager"
        assert _get_pending_subtask(subtasks, current_phase=2) is None
        subtasks[0]["status"] = "completed"
        second = _get_pending_subtask(subtasks, current_phase=2)
        assert second is not None and second.get("role") == "researcher"
