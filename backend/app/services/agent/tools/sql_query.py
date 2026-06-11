"""
自然语言转 SQL 查询工具。
"""

import re
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.services.agent.tools.base import BaseTool, ToolResult
from app.services.user_key_context import UserKeyContext, create_chat_llm

logger = get_logger(__name__)

# 仅允许 SELECT 查询，防止数据被篡改
_FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class SqlQueryTool(BaseTool):
    """将自然语言问题转换为 SQL 并执行只读查询。"""

    name = "sql_query"
    description = "将自然语言问题转换为 SQL 查询并返回结果，仅支持只读 SELECT 语句"
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "要用自然语言描述的数据库查询问题",
            },
        },
        "required": ["question"],
    }

    def __init__(self, db: AsyncSession, user_ctx: UserKeyContext) -> None:
        self.db = db
        self.user_ctx = user_ctx

    @staticmethod
    def _validate_sql(sql: str) -> str | None:
        """校验 SQL 是否为安全的只读查询。"""
        normalized = sql.strip().rstrip(";")
        if not normalized.upper().startswith("SELECT"):
            return "仅允许 SELECT 查询"
        if _FORBIDDEN_SQL_PATTERN.search(normalized):
            return "SQL 包含不允许的操作类型"
        if ";" in normalized:
            return "不允许多条 SQL 语句"
        allowed_tables = settings.sql_tool_allowed_tables.strip()
        if allowed_tables:
            whitelist = {name.strip().lower() for name in allowed_tables.split(",") if name.strip()}
            referenced = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", normalized, re.IGNORECASE)
            for table_name in referenced:
                if table_name.lower() not in whitelist:
                    return f"表 {table_name} 不在白名单内"
        return None

    async def _generate_sql(self, question: str) -> str:
        """使用 LLM 生成 SQL。"""
        llm = create_chat_llm(self.user_ctx, temperature=0)
        prompt = f"""
你是 PostgreSQL SQL 专家。根据用户问题生成一条 SELECT 查询语句。
要求：
1. 只输出 SQL，不要解释
2. 仅使用 SELECT，禁止 INSERT/UPDATE/DELETE 等
3. 数据库包含以下业务表：users, roles, tenants, knowledge_bases, documents,
   document_chunks, agents, workflows, workflow_executions, chat_histories, token_usage

用户问题：{question}
"""
        response = await llm.ainvoke(prompt)
        sql = str(response.content).strip()
        # 去除 markdown 代码块包裹
        if sql.startswith("```"):
            sql = re.sub(r"^```\w*\n?", "", sql)
            sql = re.sub(r"\n?```$", "", sql)
        return sql.strip()

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """生成并执行 SQL 查询。"""
        try:
            question = parameters["question"]
            sql = await self._generate_sql(question)

            validation_error = self._validate_sql(sql)
            if validation_error:
                return ToolResult(
                    success=False,
                    content={"generated_sql": sql},
                    error=validation_error,
                )

            result = await self.db.execute(text(sql))
            rows = result.mappings().all()
            data = [dict(row) for row in rows[:50]]

            return ToolResult(
                success=True,
                content={
                    "question": question,
                    "sql": sql,
                    "rows": data,
                    "row_count": len(data),
                },
            )
        except Exception as exc:
            logger.error("SqlQueryTool 执行失败: %s", exc)
            return ToolResult(
                success=False,
                content=None,
                error=str(exc),
            )
