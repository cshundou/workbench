# RAG 评估报告（基于 `rag_eval.py`）

**评估日期**：2026-06-11  
**评估脚本**：`tests/eval/rag_eval.py`  
**结果文件**：`tests/eval/results.json`  
**对照标准**：《企业智能协作工作台交付标准文档 v1.0》第 3.2 节

---

## 1. 评估目标与阈值

`rag_eval.py` 里定义的核心门禁如下：

| 指标 | 阈值 | 脚本判定字段 |
| ---- | ---- | ------------ |
| Recall@5 | ≥ 90% | `passed_recall` |
| Accuracy@1 | ≥ 85% | `passed_accuracy` |
| 平均检索延迟 | ≤ 100 ms | `passed_latency` |

---

## 2. 评估方法

### 2.1 离线标准集评估（默认）

```bash
python3 tests/eval/rag_eval.py --export-dataset --output tests/eval/results.json
```

- 数据源：`tests/eval/data/corpus.json`
- 问答对：由脚本生成并导出 `qa_pairs.json`（≥100 组）
- 输出：终端汇总 + `results.json`（`metrics` 与 `details`）

### 2.2 API 抽样评估（可选）

```bash
python3 tests/eval/rag_eval.py --mode api \
  --base-url http://localhost \
  --token <JWT> \
  --kb-id 1
```

- 用于校验线上接口 `POST /api/v1/knowledge-bases/{kb_id}/search`
- 默认抽样 20 条，控制线上调用成本

---

## 3. 本次结果（来自 `tests/eval/results.json`）

| 指标 | 实测值 | 阈值 | 结论 |
| ---- | ------ | ---- | ---- |
| Recall@5 | **100.0%** | ≥ 90% | ✅ |
| Accuracy@1 | **96.8%** | ≥ 85% | ✅ |
| 平均检索延迟 | **0.35 ms** | ≤ 100 ms | ✅ |
| P95 检索延迟 | **0.44 ms** | 参考项 | ✅ |
| 最大检索延迟 | **1.04 ms** | 参考项 | ✅ |

脚本布尔判定：

- `passed_recall = true`
- `passed_accuracy = true`
- `passed_latency = true`

---

## 4. 结论

基于 `tests/eval/rag_eval.py` 的离线标准集评估，本项目在召回率、准确率和检索延迟三项指标均达标。  
当前结果满足交付标准第 3.2 节要求。

**验收结论**：✅ **通过**

---

## 5. 复现清单

1. 进入项目根目录。
2. 执行 `python3 tests/eval/rag_eval.py --export-dataset --output tests/eval/results.json`。
3. 核对终端输出与 `tests/eval/results.json` 中 `metrics` 字段。
4. 将本次指标同步更新到本报告第 3 节。
