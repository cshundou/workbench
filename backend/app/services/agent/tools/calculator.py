"""
计算器工具：基于 AST 白名单的安全数学表达式求值。
"""

import ast
import operator
from typing import Any

from app.core.logging import get_logger
from app.services.agent.tools.base import BaseTool, ToolResult

logger = get_logger(__name__)

# AST 运算符白名单
_SAFE_OPERATORS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class _SafeEvaluator(ast.NodeVisitor):
    """仅允许数字与四则运算的表达式求值器。"""

    def visit(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("仅支持数字常量")
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _SAFE_OPERATORS:
                raise ValueError(f"不支持的运算符: {op_type.__name__}")
            left = self.visit(node.left)
            right = self.visit(node.right)
            return _SAFE_OPERATORS[op_type](left, right)
        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in _SAFE_OPERATORS:
                raise ValueError(f"不支持的一元运算符: {op_type.__name__}")
            return _SAFE_OPERATORS[op_type](self.visit(node.operand))
        raise ValueError(f"不支持的表达式节点: {type(node).__name__}")


def _safe_eval(expression: str) -> float:
    """安全计算数学表达式。"""
    tree = ast.parse(expression.strip(), mode="eval")
    return float(_SafeEvaluator().visit(tree))


class CalculatorTool(BaseTool):
    """计算器工具。"""

    name = "calculator"
    description = "执行数学表达式计算，支持 +、-、*、/、%、幂运算"
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如 (1+2)*3",
            }
        },
        "required": ["expression"],
    }

    async def execute(self, parameters: dict[str, Any]) -> ToolResult:
        """计算表达式并返回结果。"""
        expression = parameters.get("expression", "")
        if not expression:
            return ToolResult(success=False, content=None, error="表达式不能为空")
        try:
            result = _safe_eval(expression)
            return ToolResult(success=True, content={"expression": expression, "result": result})
        except Exception as exc:
            logger.warning("CalculatorTool 计算失败: %s", exc)
            return ToolResult(success=False, content=None, error=str(exc))
