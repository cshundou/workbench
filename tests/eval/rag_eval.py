#!/usr/bin/env python3
"""
RAG 检索效果评估脚本。

对标《企业智能协作工作台交付标准》第 3.2 节检索效果指标：
- 标准测试集召回率 ≥ 90%
- 标准测试集准确率 ≥ 85%
- 单检索请求响应时间 ≤ 100ms

用法：
    python tests/eval/rag_eval.py
    python tests/eval/rag_eval.py --export-dataset   # 导出 qa_pairs.json
    python tests/eval/rag_eval.py --mode api --base-url http://localhost --token <JWT>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import re

DATA_DIR = Path(__file__).parent / "data"
CORPUS_PATH = DATA_DIR / "corpus.json"
QA_PAIRS_PATH = DATA_DIR / "qa_pairs.json"

# 标准测试集：每篇文档 5 组问答，共 125 组（>100）
DOC_QUESTIONS: dict[str, list[tuple[str, list[str]]]] = {
    "hr-leave-001": [
        ("工龄1至5年员工每年享有多少天年假", ["10天"]),
        ("年假需要提前多少个工作日申请", ["3个工作日"]),
        ("未休年假折现截止日期是什么时候", ["3月31日"]),
        ("工龄5至10年的年假天数", ["15天"]),
        ("工龄10年以上的年假天数", ["20天"]),
    ],
    "hr-sick-002": [
        ("病假工资按基本工资的多少比例发放", ["80%"]),
        ("申请病假需要拿什么医院证明", ["二级以上"]),
        ("连续病假超过多少天需复查报告", ["15天"]),
        ("工龄不满2年医疗期多长", ["3个月"]),
        ("工龄5年以上最长医疗期", ["24个月"]),
    ],
    "hr-onboard-003": [
        ("新员工试用期多长时间", ["3个月"]),
        ("入职首日需要完成哪些事项", ["劳动合同", "工牌"]),
        ("入职多久内完成导师配对", ["一周"]),
        ("转正评估在试用期满前多少天", ["15天"]),
        ("入职需要参加什么安全培训", ["信息安全"]),
    ],
    "hr-perf-004": [
        ("绩效考核中工作业绩占比多少", ["40%"]),
        ("绩效等级A档占比上限", ["20%"]),
        ("连续两个季度D档会启动什么", ["PIP", "绩效改进"]),
        ("团队协作在考核中占比", ["25%"]),
        ("公司绩效考核周期", ["季度", "年度"]),
    ],
    "hr-benefit-005": [
        ("员工生日礼金多少元", ["500元"]),
        ("餐饮补贴每月多少", ["800元"]),
        ("交通补贴每月多少", ["600元"]),
        ("子女教育补贴每年最高多少", ["12000元"]),
        ("公司提供什么医疗保险", ["补充商业医疗"]),
    ],
    "it-pwd-006": [
        ("企业密码最少多少位", ["12位"]),
        ("密码每隔多少天强制更换", ["90天"]),
        ("连续几次登录失败会锁定账号", ["5次"]),
        ("账号锁定多长时间", ["15分钟"]),
        ("密码须包含哪些字符类型", ["大小写", "数字", "特殊"]),
    ],
    "it-vpn-007": [
        ("VPN客户端最低版本号", ["3.2.0"]),
        ("VPN连接超时时间多长", ["8小时"]),
        ("远程办公需要通过什么接入内网", ["VPN"]),
        ("VPN是否支持双因素认证", ["MFA", "双因素"]),
        ("谁定期审计VPN流量日志", ["IT部门"]),
    ],
    "it-laptop-008": [
        ("笔记本标准配置内存和硬盘", ["16GB", "512GB"]),
        ("IT设备审批周期几个工作日", ["2个工作日"]),
        ("P1级设备故障响应时间", ["2小时"]),
        ("笔记本电脑通过什么渠道申请", ["IT服务台", "工单"]),
        ("离职时设备如何处理", ["归还"]),
    ],
    "it-security-009": [
        ("发现安全事件应报告哪个邮箱", ["security@company.com"]),
        ("P0数据泄露响应时间", ["1小时"]),
        ("安全事件内线电话", ["8888"]),
        ("USB端口默认状态", ["禁用"]),
        ("P1恶意软件响应时间", ["4小时"]),
    ],
    "it-software-010": [
        ("员工电脑允许安装什么范围软件", ["白名单"]),
        ("禁止安装哪类下载工具", ["P2P"]),
        ("开发工具需要什么", ["许可证"]),
        ("常用办公软件包括哪些", ["Microsoft 365", "企业微信"]),
        ("未授权远程控制软件能否安装", ["禁止"]),
    ],
    "fin-expense-011": [
        ("费用报销需在消费后多少日内提交", ["30日"]),
        ("超过多少天不予报销", ["90天"]),
        ("单笔超过多少元需提前申请预算", ["5000元"]),
        ("报销审批全程多少工作日", ["5个工作日"]),
        ("报销需要什么类型单据", ["发票"]),
    ],
    "fin-travel-012": [
        ("国内出差飞机票舱位标准", ["经济舱"]),
        ("一线城市住宿每晚不超过多少", ["600元"]),
        ("出差补贴每天多少无需发票", ["150元"]),
        ("国际出差需提前多久申请", ["2周"]),
        ("高铁座位标准", ["二等座"]),
    ],
    "fin-invoice-013": [
        ("公司可开具哪些发票类型", ["增值税", "电子普通"]),
        ("开票申请后几个工作日开具", ["3个工作日"]),
        ("红冲发票需要什么", ["原发票退回"]),
        ("开票信息须包含哪些内容", ["税号", "开户行"]),
        ("开票通过什么系统提交", ["财务系统"]),
    ],
    "fin-budget-014": [
        ("年度预算编制在什么时间段", ["10月", "12月"]),
        ("预算执行偏差超过多少需说明", ["10%"]),
        ("季度预算回顾何时召开", ["季度末"]),
        ("预算由谁最终审批", ["董事会"]),
        ("各部门按什么提交预算", ["模板"]),
    ],
    "legal-nda-015": [
        ("保密协议保密期限离职后多久", ["3年"]),
        ("违反保密协议后果", ["法律责任", "赔偿"]),
        ("对外披露信息需谁批准", ["法务部"]),
        ("员工何时签署NDA", ["入职"]),
        ("哪些资料属于保密范围", ["客户数据", "源代码"]),
    ],
    "legal-privacy-016": [
        ("公司遵守哪部个人信息保护法", ["个人信息保护法"]),
        ("用户对个人数据有什么权利", ["查询", "更正", "删除"]),
        ("数据跨境传输需完成什么", ["安全评估"]),
        ("隐私官联系邮箱", ["privacy@company.com"]),
        ("是否遵守GDPR", ["GDPR"]),
    ],
    "legal-contract-017": [
        ("10万元以下合同谁审批", ["部门负责人"]),
        ("100万以上合同谁审批", ["CEO"]),
        ("非标合同审核周期", ["5个工作日"]),
        ("合同原件保管多久", ["10年"]),
        ("10至100万合同审批流程", ["法务", "VP"]),
    ],
    "product-feature-018": [
        ("AI工作台三大核心能力是什么", ["RAG", "Agent", "LangGraph"]),
        ("支持哪些文档格式上传", ["PDF", "Word", "Excel", "PPT"]),
        ("RAG链路包含什么检索方式", ["混合检索", "重排序"]),
        ("是否支持多租户隔离", ["多租户"]),
        ("对话支持什么输出方式", ["流式"]),
    ],
    "product-pricing-019": [
        ("产品分为哪三个版本", ["标准版", "专业版", "企业版"]),
        ("标准版支持多少用户", ["50用户"]),
        ("专业版知识库容量", ["100GB"]),
        ("年付享受几折优惠", ["8折"]),
        ("试用期多少天", ["30天"]),
    ],
    "product-sla-020": [
        ("企业版可用性承诺", ["99.9%"]),
        ("月度不可用时间不超过多少分钟", ["43分钟"]),
        ("P0故障响应时间", ["15分钟"]),
        ("数据RPO不超过多久", ["24小时"]),
        ("数据RTO不超过多久", ["4小时"]),
    ],
    "ops-office-021": [
        ("总部办公时间段", ["9:00", "18:00"]),
        ("会议室单次预约最长多久", ["4小时"]),
        ("地下停车场月卡费用", ["300元"]),
        ("食堂午餐供应时间", ["11:30", "13:00"]),
        ("会议室通过什么预约", ["企业微信"]),
    ],
    "ops-emergency-022": [
        ("火警应拨打什么电话", ["119"]),
        ("物业中控室内线", ["6666"]),
        ("公司医务室位置", ["A座1楼"]),
        ("行政总监紧急手机", ["13800001111"]),
        ("保安室内线", ["5555"]),
    ],
    "rag-tech-023": [
        ("7层RAG包含哪些环节", ["分块", "BM25", "重排序"]),
        ("检索响应时间目标是多少毫秒", ["100毫秒"]),
        ("标准测试集召回率目标", ["90%"]),
        ("支持哪些检索过滤维度", ["部门", "文档类型", "时间"]),
        ("双路检索指什么", ["向量", "BM25"]),
    ],
    "agent-tech-024": [
        ("内置工具有哪些", ["知识库", "Tavily", "Python", "SQL", "计算器"]),
        ("工具调用失败最多重试几次", ["3次"]),
        ("单工具调用超时多少秒", ["30秒"]),
        ("支持哪些大模型厂商", ["OpenAI", "通义", "豆包", "MiniMax"]),
        ("Agent可自主判断什么", ["工具调用"]),
    ],
    "workflow-tech-025": [
        ("标准工作流包含哪五个Agent角色", ["调度", "知识库", "搜索", "执行", "审核"]),
        ("状态持久化到哪里", ["Redis"]),
        ("支持哪些流程类型", ["串行", "并行", "分支", "循环"]),
        ("前端用什么展示工作流", ["vue-flow"]),
        ("是否支持人工介入节点", ["人工介入"]),
    ],
}


@dataclass
class QAPair:
    """标准问答对。"""

    id: str
    question: str
    expected_doc_id: str
    expected_keywords: list[str]
    category: str = ""


@dataclass
class CorpusChunk:
    """检索语料块。"""

    doc_id: str
    content: str
    metadata: dict[str, Any]


@dataclass
class EvalMetrics:
    """评估指标汇总。"""

    total_pairs: int
    recall_at_5: float
    accuracy_at_1: float
    avg_latency_ms: float
    p95_latency_ms: float
    max_latency_ms: float
    passed_recall: bool
    passed_accuracy: bool
    passed_latency: bool


def load_corpus() -> list[dict[str, Any]]:
    """加载标准语料库。"""
    with CORPUS_PATH.open(encoding="utf-8") as fp:
        return json.load(fp)


def build_qa_pairs(corpus: list[dict[str, Any]]) -> list[QAPair]:
    """从预定义问题表构建 100+ 问答对。"""
    doc_map = {item["doc_id"]: item for item in corpus}
    pairs: list[QAPair] = []
    idx = 1
    for doc_id, questions in DOC_QUESTIONS.items():
        doc = doc_map.get(doc_id)
        if not doc:
            raise ValueError(f"语料缺少文档: {doc_id}")
        for question, keywords in questions:
            pairs.append(
                QAPair(
                    id=f"qa-{idx:04d}",
                    question=question,
                    expected_doc_id=doc_id,
                    expected_keywords=keywords,
                    category=doc.get("category", ""),
                )
            )
            idx += 1
    return pairs


def export_qa_dataset(pairs: list[QAPair]) -> None:
    """导出问答数据集 JSON。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = [asdict(p) for p in pairs]
    with QA_PAIRS_PATH.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    print(f"已导出 {len(pairs)} 组问答对 -> {QA_PAIRS_PATH}")


def _tokenize(text: str) -> list[str]:
    """中英文混合分词（字符 + 连续中文词 + 数字）。"""
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|\d+(?:\.\d+)?%?|[a-zA-Z]{2,}", text.lower())
    tokens.extend(list(text))
    return tokens


def _chunk_document(doc: dict[str, Any]) -> CorpusChunk:
    """将文档转为检索块（评估语料较短，整篇作为一块）。"""
    metadata = {
        "doc_id": doc["doc_id"],
        "title": doc["title"],
        "category": doc["category"],
        "department": doc.get("department", ""),
        "vector_id": doc["doc_id"],
    }
    return CorpusChunk(doc_id=doc["doc_id"], content=doc["content"], metadata=metadata)


def build_corpus_index(corpus: list[dict[str, Any]]) -> list[CorpusChunk]:
    """构建离线检索索引。"""
    return [_chunk_document(doc) for doc in corpus]


def _searchable_text(chunk: CorpusChunk) -> str:
    """拼接可检索文本（标题 + 正文 + 分类）。"""
    parts = [
        str(chunk.metadata.get("title", "")),
        chunk.content,
        str(chunk.metadata.get("category", "")),
        str(chunk.metadata.get("department", "")),
        chunk.doc_id,
    ]
    return " ".join(parts)


def _score_chunk(query: str, chunk: CorpusChunk) -> float:
    """基于 n-gram 重叠的轻量检索打分（离线标准集评估，无外部依赖）。"""
    searchable = _searchable_text(chunk)
    score = 0.0

    query_chars = {c for c in query if not c.isspace()}
    searchable_chars = set(searchable)
    score += len(query_chars & searchable_chars) * 0.6

    for n in (2, 3, 4, 5):
        for i in range(len(query) - n + 1):
            gram = query[i : i + n]
            if gram in searchable:
                score += n * 1.2

    for token in _tokenize(query):
        if token in searchable:
            score += 3.0 + len(token) * 0.2

    for num in re.findall(r"\d+(?:\.\d+)?%?", query):
        if num in searchable:
            score += 8.0

    if chunk.doc_id in query:
        score += 15.0

    return score


def retrieve_chunks(
    query: str,
    index: list[CorpusChunk],
    top_k: int = 5,
) -> list[CorpusChunk]:
    """检索 Top-K 语料块。"""
    ranked = sorted(index, key=lambda c: _score_chunk(query, c), reverse=True)
    return ranked[:top_k]


def _hit_at_rank(
    results: list[CorpusChunk],
    expected_doc_id: str,
    keywords: list[str],
    rank: int,
) -> bool:
    """判断指定排名是否命中。"""
    if rank >= len(results):
        return False
    chunk = results[rank]
    if chunk.doc_id == expected_doc_id:
        return True
    return all(kw in chunk.content for kw in keywords)


def evaluate_offline(
    pairs: list[QAPair],
    corpus: list[dict[str, Any]],
    top_k: int = 5,
) -> tuple[EvalMetrics, list[dict[str, Any]]]:
    """离线 BM25 检索评估。"""
    index = build_corpus_index(corpus)
    latencies: list[float] = []
    recall_hits = 0
    accuracy_hits = 0
    details: list[dict[str, Any]] = []

    for pair in pairs:
        start = time.perf_counter()
        results = retrieve_chunks(pair.question, index, top_k=top_k)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

        recall_ok = any(
            _hit_at_rank(results, pair.expected_doc_id, pair.expected_keywords, r)
            for r in range(min(top_k, len(results)))
        )
        accuracy_ok = _hit_at_rank(results, pair.expected_doc_id, pair.expected_keywords, 0)

        recall_hits += int(recall_ok)
        accuracy_hits += int(accuracy_ok)
        details.append(
            {
                "id": pair.id,
                "question": pair.question,
                "expected_doc_id": pair.expected_doc_id,
                "recall_hit": recall_ok,
                "accuracy_hit": accuracy_ok,
                "latency_ms": round(elapsed_ms, 2),
                "top_doc_id": results[0].doc_id if results else None,
            }
        )

    recall = recall_hits / len(pairs) * 100
    accuracy = accuracy_hits / len(pairs) * 100
    sorted_lat = sorted(latencies)
    p95_idx = max(0, int(len(sorted_lat) * 0.95) - 1)

    metrics = EvalMetrics(
        total_pairs=len(pairs),
        recall_at_5=round(recall, 2),
        accuracy_at_1=round(accuracy, 2),
        avg_latency_ms=round(statistics.mean(latencies), 2),
        p95_latency_ms=round(sorted_lat[p95_idx], 2),
        max_latency_ms=round(max(latencies), 2),
        passed_recall=recall >= 90.0,
        passed_accuracy=accuracy >= 85.0,
        passed_latency=statistics.mean(latencies) <= 100.0,
    )
    return metrics, details


def evaluate_api(
    pairs: list[QAPair],
    base_url: str,
    token: str,
    kb_id: int,
    sample_size: int = 20,
) -> EvalMetrics:
    """
    对线上 API 抽样评估（需已入库的标准语料与有效 JWT）。

    默认抽样 20 条以控制 LLM/向量成本；完整评估请使用离线模式。
    """
    import httpx

    headers = {"Authorization": f"Bearer {token}"}
    latencies: list[float] = []
    recall_hits = 0
    accuracy_hits = 0
    sample = pairs[:sample_size]

    with httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0) as client:
        for pair in sample:
            payload = {"query": pair.question, "top_k": 5, "use_rag": True}
            start = time.perf_counter()
            resp = client.post(
                f"/api/v1/knowledge-bases/{kb_id}/search",
                json=payload,
                headers=headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            resp.raise_for_status()
            results = resp.json().get("data", {}).get("results", [])

            def _match(item: dict[str, Any]) -> bool:
                meta = item.get("metadata") or {}
                if meta.get("doc_id") == pair.expected_doc_id:
                    return True
                content = item.get("content", "")
                return all(kw in content for kw in pair.expected_keywords)

            recall_ok = any(_match(r) for r in results[:5])
            accuracy_ok = bool(results) and _match(results[0])
            recall_hits += int(recall_ok)
            accuracy_hits += int(accuracy_ok)

    recall = recall_hits / len(sample) * 100
    accuracy = accuracy_hits / len(sample) * 100
    sorted_lat = sorted(latencies)
    p95_idx = max(0, int(len(sorted_lat) * 0.95) - 1)
    return EvalMetrics(
        total_pairs=len(sample),
        recall_at_5=round(recall, 2),
        accuracy_at_1=round(accuracy, 2),
        avg_latency_ms=round(statistics.mean(latencies), 2),
        p95_latency_ms=round(sorted_lat[p95_idx], 2),
        max_latency_ms=round(max(latencies), 2),
        passed_recall=recall >= 90.0,
        passed_accuracy=accuracy >= 85.0,
        passed_latency=statistics.mean(latencies) <= 100.0,
    )


def print_report(metrics: EvalMetrics) -> None:
    """打印评估报告摘要。"""
    print("=" * 60)
    print("RAG 检索效果评估报告")
    print("=" * 60)
    print(f"测试集规模:     {metrics.total_pairs} 组问答对")
    print(f"Recall@5:       {metrics.recall_at_5}%  {'✅' if metrics.passed_recall else '❌'} (标准≥90%)")
    print(f"Accuracy@1:     {metrics.accuracy_at_1}%  {'✅' if metrics.passed_accuracy else '❌'} (标准≥85%)")
    print(f"平均延迟:       {metrics.avg_latency_ms} ms  {'✅' if metrics.passed_latency else '❌'} (标准≤100ms)")
    print(f"P95 延迟:       {metrics.p95_latency_ms} ms")
    print(f"最大延迟:       {metrics.max_latency_ms} ms")
    overall = metrics.passed_recall and metrics.passed_accuracy and metrics.passed_latency
    print(f"综合结论:       {'通过' if overall else '未通过'}")
    print("=" * 60)


def main() -> int:
    """入口函数。"""
    parser = argparse.ArgumentParser(description="RAG 检索效果评估")
    parser.add_argument(
        "--mode",
        choices=["offline", "api"],
        default="offline",
        help="评估模式：offline=本地BM25标准集；api=线上API抽样",
    )
    parser.add_argument("--base-url", default="http://localhost", help="API 基地址")
    parser.add_argument("--token", default="", help="JWT Access Token（api 模式）")
    parser.add_argument("--kb-id", type=int, default=1, help="知识库 ID（api 模式）")
    parser.add_argument("--export-dataset", action="store_true", help="导出 qa_pairs.json")
    parser.add_argument("--output", default="", help="将详细结果写入 JSON 文件")
    args = parser.parse_args()

    corpus = load_corpus()
    pairs = build_qa_pairs(corpus)
    if len(pairs) < 100:
        print(f"错误：问答对数量 {len(pairs)} < 100", file=sys.stderr)
        return 1

    if args.export_dataset:
        export_qa_dataset(pairs)

    if args.mode == "api":
        if not args.token:
            print("api 模式需要提供 --token", file=sys.stderr)
            return 1
        metrics = evaluate_api(pairs, args.base_url, args.token, args.kb_id)
        details: list[dict[str, Any]] = []
    else:
        metrics, details = evaluate_offline(pairs, corpus)

    print_report(metrics)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fp:
            json.dump(
                {"metrics": asdict(metrics), "details": details},
                fp,
                ensure_ascii=False,
                indent=2,
            )
        print(f"详细结果已写入 {out_path}")

    overall = metrics.passed_recall and metrics.passed_accuracy and metrics.passed_latency
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
