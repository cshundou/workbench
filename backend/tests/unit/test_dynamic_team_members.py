"""动态团队成员面板单元测试。"""

from app.services.workflow.group_chat_engine import GroupChatEngine


class TestDynamicMembers:
    """动态成员列表。"""

    def test_dynamic_members_from_team_config(self) -> None:
        team_config = {
            "members": [
                {"role_id": "researcher", "name": "研究员", "avatar": "🔍", "subtasks": ["调研"]},
                {"role_id": "auditor", "name": "审核员", "avatar": "✅", "subtasks": ["审核"]},
            ]
        }
        members = GroupChatEngine.get_members(team_config=team_config)
        assert len(members) == 2
        assert members[0]["role"] == "researcher"
        assert members[0]["status"] == "pending"
        assert members[1]["is_auditor"] is True

    def test_classic_five_backward_compat(self) -> None:
        members = GroupChatEngine.get_members()
        assert len(members) == 5

    def test_member_task_count(self) -> None:
        team_config = {
            "members": [
                {
                    "role_id": "researcher",
                    "name": "研究员",
                    "avatar": "🔍",
                    "subtasks": ["任务1", "任务2"],
                },
            ]
        }
        subtasks = [
            {"role": "researcher", "task": "任务1", "status": "completed"},
            {"role": "researcher", "task": "任务2", "status": "pending"},
        ]
        members = GroupChatEngine.get_members(
            team_config=team_config,
            subtasks=subtasks,
            statuses={"researcher": "working"},
        )
        assert members[0]["completed_count"] == 1
        assert members[0]["total_count"] == 2

    def test_audit_highlight(self) -> None:
        team_config = {
            "members": [
                {"role_id": "auditor", "name": "审核员", "avatar": "✅", "subtasks": ["审核"]},
            ]
        }
        members = GroupChatEngine.get_members(
            team_config=team_config,
            session_status="reviewing",
            review_count=1,
        )
        assert members[0]["review_round"] == 2

    def test_reject_info(self) -> None:
        team_config = {
            "members": [
                {"role_id": "engineer", "name": "工程师", "avatar": "💻"},
                {"role_id": "auditor", "name": "审核员", "avatar": "✅"},
            ]
        }
        members = GroupChatEngine.get_members(
            team_config=team_config,
            reject_info={"assignee": "engineer", "reason": "数据错误"},
        )
        engineer = next(m for m in members if m["role"] == "engineer")
        assert engineer["status"] == "revision"
        assert engineer["reject_reason"] == "数据错误"
