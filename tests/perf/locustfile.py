"""
AI Workbench 性能压测 Locust 脚本。

对标《交付标准》第 4.1 章：单租户 100 并发，核心接口 P95 ≤ 2 秒。

运行示例（需先启动 docker compose）：
    pip install locust
    locust -f tests/perf/locustfile.py --host=http://localhost \\
        --users 100 --spawn-rate 10 --run-time 5m --headless \\
        --csv=tests/perf/results/perf

环境变量：
    LOCUST_USERNAME  登录用户名（默认 admin）
    LOCUST_PASSWORD  登录密码（默认 admin123）
    LOCUST_KB_ID     知识库 ID（默认 1，用于检索压测）
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, between, events, task


# 压测用查询样本（只读检索，不触发 LLM 生成）
SEARCH_QUERIES = [
    "年假有多少天",
    "密码策略要求",
    "费用报销流程",
    "VPN如何连接",
    "绩效考核比例",
    "保密协议期限",
    "产品SLA可用性",
    "会议室如何预约",
    "差旅住宿标准",
    "RAG混合检索",
    "Agent工具有哪些",
    "工作流Redis持久化",
    "发票开具周期",
    "安全事件响应时间",
    "员工福利补贴",
]


class WorkbenchUser(HttpUser):
    """模拟企业用户核心操作路径。"""

    wait_time = between(0.5, 2.0)
    token: str | None = None
    kb_id: int = int(os.getenv("LOCUST_KB_ID", "1"))

    def on_start(self) -> None:
        """登录并缓存 JWT。"""
        username = os.getenv("LOCUST_USERNAME", "admin")
        password = os.getenv("LOCUST_PASSWORD", "admin123")
        with self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
            name="POST /auth/login",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"登录失败: {resp.status_code}")
                return
            body = resp.json()
            self.token = body.get("data", {}).get("access_token")
            if not self.token:
                resp.failure("响应缺少 access_token")

    def _auth_headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def health_check(self) -> None:
        """健康检查（无需认证）。"""
        self.client.get("/api/v1/monitor/health", name="GET /monitor/health")

    @task(5)
    def get_me(self) -> None:
        """获取当前用户信息。"""
        self.client.get(
            "/api/v1/auth/me",
            headers=self._auth_headers(),
            name="GET /auth/me",
        )

    @task(8)
    def list_knowledge_bases(self) -> None:
        """知识库列表。"""
        self.client.get(
            "/api/v1/knowledge-bases?page=1&page_size=20",
            headers=self._auth_headers(),
            name="GET /knowledge-bases",
        )

    @task(10)
    def search_knowledge_base(self) -> None:
        """知识库混合检索（核心 RAG 接口）。"""
        query = random.choice(SEARCH_QUERIES)
        self.client.post(
            f"/api/v1/knowledge-bases/{self.kb_id}/search",
            json={"query": query, "top_k": 5, "use_rag": True},
            headers=self._auth_headers(),
            name="POST /knowledge-bases/{id}/search",
        )

    @task(6)
    def list_agents(self) -> None:
        """智能体列表。"""
        self.client.get(
            "/api/v1/agents?page=1&page_size=20",
            headers=self._auth_headers(),
            name="GET /agents",
        )

    @task(5)
    def list_workflows(self) -> None:
        """工作流列表。"""
        self.client.get(
            "/api/v1/workflows?page=1&page_size=20",
            headers=self._auth_headers(),
            name="GET /workflows",
        )

    @task(4)
    def monitor_overview(self) -> None:
        """监控概览。"""
        self.client.get(
            "/api/v1/monitor/overview",
            headers=self._auth_headers(),
            name="GET /monitor/overview",
        )

    @task(3)
    def api_stats(self) -> None:
        """接口调用统计。"""
        self.client.get(
            "/api/v1/monitor/api-stats?days=7",
            headers=self._auth_headers(),
            name="GET /monitor/api-stats",
        )

    @task(2)
    def token_usage(self) -> None:
        """Token 消耗统计。"""
        self.client.get(
            "/api/v1/monitor/token-usage?group_by=day",
            headers=self._auth_headers(),
            name="GET /monitor/token-usage",
        )


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs) -> None:
    """压测结束时输出简要统计。"""
    stats = environment.stats.total
    if stats.num_requests == 0:
        return
    print("\n" + "=" * 60)
    print("压测汇总")
    print("=" * 60)
    print(f"总请求数:   {stats.num_requests}")
    print(f"失败数:     {stats.num_failures}")
    print(f"平均响应:   {stats.avg_response_time:.0f} ms")
    print(f"P95 响应:   {stats.get_response_time_percentile(0.95):.0f} ms")
    print(f"P99 响应:   {stats.get_response_time_percentile(0.99):.0f} ms")
    print(f"RPS:        {stats.total_rps:.1f}")
    print("=" * 60)
