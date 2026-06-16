"""任务模式能力解析单测。"""

from app.services.workflow.task_mode_resolver import (
    build_member_node_config,
    infer_execution_mode,
    resolve_task_tool_names,
)


def test_infer_execution_mode_from_tools() -> None:
    assert infer_execution_mode({"tools": ["search"]}) == "task"
    assert infer_execution_mode({"tools": ["document"]}) == "llm"


def test_resolve_task_tool_names_browser_terminal() -> None:
    tools = resolve_task_tool_names(
        {"task_tools": ["browser", "terminal"], "tools": ["search"]}
    )
    assert "ui_automation" in tools
    assert "python_repl" in tools
    assert "tavily_search" in tools


def test_build_member_node_config_task_mode_only_tools() -> None:
    config = build_member_node_config(
        {
            "execution_mode": "task",
            "task_tools": ["browser", "terminal"],
        }
    )
    assert config["execution_mode"] == "task"
    assert config["use_member_tools_only"] is True
    assert "ui_automation" in config["tools"]
    assert "python_repl" in config["tools"]
