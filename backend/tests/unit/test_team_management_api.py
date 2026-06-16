"""团队管理 API 逻辑单测。"""

from app.api.v1.professional_roles import _merge_member_with_role


def test_merge_member_with_role_uses_remote_prompt() -> None:
    role_map = {
        "researcher": {
            "role_id": "researcher",
            "name": "研究员",
            "avatar": "🔍",
            "responsibility": "远程角色职责",
            "tools": ["search", "knowledge"],
            "system_prompt": "你是远程加载研究员。",
            "color": "#00B42A",
        }
    }
    member = {"role_id": "researcher", "name": "旧名称"}
    merged = _merge_member_with_role(member, role_map)
    assert merged["name"] == "研究员"
    assert merged["system_prompt"] == "你是远程加载研究员。"
    assert merged["execution_mode"] == "task"
    assert merged["task_tools"] == ["browser", "terminal"]


def test_merge_member_with_role_defaults_to_llm_mode() -> None:
    role_map = {
        "copywriter": {
            "role_id": "copywriter",
            "name": "文案策划师",
            "tools": ["document"],
            "system_prompt": "你是文案。",
        }
    }
    merged = _merge_member_with_role({"role_id": "copywriter"}, role_map)
    assert merged["execution_mode"] == "llm"
    assert merged["task_tools"] == []
