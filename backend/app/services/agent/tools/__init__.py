"""Agent 内置工具包。"""

from app.services.agent.tools.base import BaseTool, ToolResult
from app.services.agent.tools.calculator import CalculatorTool
from app.services.agent.tools.knowledge_base import KnowledgeBaseTool
from app.services.agent.tools.python_repl import PythonReplTool
from app.services.agent.tools.sql_query import SqlQueryTool
from app.services.agent.tools.tavily_search import TavilySearchTool
from app.services.agent.tools.generate_ppt import GeneratePptTool
from app.services.agent.tools.ui_automation import UiAutomationTool

# 内置工具名称常量
TOOL_KNOWLEDGE_BASE = "knowledge_base_search"
TOOL_TAVILY_SEARCH = "tavily_search"
TOOL_PYTHON_REPL = "python_repl"
TOOL_SQL_QUERY = "sql_query"
TOOL_CALCULATOR = "calculator"
TOOL_UI_AUTOMATION = "ui_automation"
TOOL_GENERATE_PPT = "generate_ppt"

AVAILABLE_TOOL_DEFINITIONS: list[dict[str, str]] = [
    {
        "name": TOOL_KNOWLEDGE_BASE,
        "label": "知识库检索",
        "description": "搜索企业私有知识库中的信息",
    },
    {
        "name": TOOL_TAVILY_SEARCH,
        "label": "联网搜索",
        "description": "通过 Tavily 搜索互联网上的最新信息",
    },
    {
        "name": TOOL_PYTHON_REPL,
        "label": "Python 执行",
        "description": "执行 Python 代码进行数据计算与分析",
    },
    {
        "name": TOOL_SQL_QUERY,
        "label": "SQL 查询",
        "description": "将自然语言转换为 SQL 并查询数据库",
    },
    {
        "name": TOOL_CALCULATOR,
        "label": "计算器",
        "description": "执行数学表达式计算",
    },
    {
        "name": TOOL_UI_AUTOMATION,
        "label": "UI 自动化",
        "description": "网页抓取与 RPA 轻量自动化（无 API 系统对接）",
    },
    {
        "name": TOOL_GENERATE_PPT,
        "label": "PPT 生成",
        "description": "根据结构化大纲生成 PPTX 演示文稿文件",
    },
]

__all__ = [
    "AVAILABLE_TOOL_DEFINITIONS",
    "BaseTool",
    "CalculatorTool",
    "GeneratePptTool",
    "KnowledgeBaseTool",
    "PythonReplTool",
    "SqlQueryTool",
    "TavilySearchTool",
    "ToolResult",
    "TOOL_CALCULATOR",
    "TOOL_GENERATE_PPT",
    "TOOL_KNOWLEDGE_BASE",
    "TOOL_PYTHON_REPL",
    "TOOL_SQL_QUERY",
    "TOOL_TAVILY_SEARCH",
    "TOOL_UI_AUTOMATION",
    "UiAutomationTool",
]
