"""
ARQ Worker 配置入口。
"""

from arq.connections import RedisSettings

from app.core.config import settings
from app.services.task_worker import (
    execute_workflow_task,
    parse_document_task,
    resume_workflow_task,
)


class WorkerSettings:
    """ARQ Worker 配置。"""

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [
        parse_document_task,
        execute_workflow_task,
        resume_workflow_task,
    ]
    job_timeout = 1800  # 30 分钟
    keep_result = 3600  # 结果保留 1 小时
    allow_abort_jobs = True  # 支持 Job.abort() 撤销正在执行的任务
