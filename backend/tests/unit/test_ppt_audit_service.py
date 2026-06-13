"""PPT 五维专项审核服务单元测试。"""

from app.services.delivery.ppt_audit_service import ppt_audit_service


def test_audit_outline_passes_rich_structure() -> None:
    outline = {
        "title": "测试汇报",
        "slides": [
            {"slide_type": "cover", "title": "封面"},
            {"slide_type": "toc", "title": "目录", "bullets": ["一", "二"]},
            {"slide_type": "content", "title": "背景与现状", "bullets": ["2024年行业规模达500亿（来源：公开报告）", "核心冲突：增长放缓"]},
            {"slide_type": "content", "title": "核心问题", "bullets": ["如何提升研发效率20%", "本次汇报目标明确"]},
            {"slide_type": "content", "title": "分析与方案", "bullets": ["方案A：自动化工具链", "方案B：流程重构"]},
            {"slide_type": "content", "title": "关键数据", "bullets": ["效率提升15%（来源：内部测算）"], "chart": {"chart_type": "bar"}},
            {"slide_type": "content", "title": "总结与建议", "bullets": ["结论：双轨并行最可行", "建议：Q3启动试点"]},
            {"slide_type": "content", "title": "补充分析一", "bullets": ["竞品对比显示差距在交付周期"]},
            {"slide_type": "content", "title": "补充分析二", "bullets": ["用户调研反馈优先级排序"]},
            {"slide_type": "content", "title": "补充分析三", "bullets": ["成本测算与ROI预估说明"]},
            {"slide_type": "content", "title": "补充分析四", "bullets": ["风险清单与缓释措施"]},
            {"slide_type": "ending", "title": "谢谢聆听"},
        ],
    }
    report = ppt_audit_service.audit_outline(outline, complexity="medium")
    assert report["audit_type"] == "outline"
    assert report["total_score"] >= 80
    assert report["passed"] is True


def test_audit_outline_fails_when_empty() -> None:
    report = ppt_audit_service.audit_outline(None)
    assert report["passed"] is False
    assert report["assignee"] == "copywriter"


def test_audit_final_requires_ppt_file() -> None:
    report = ppt_audit_service.audit_final(
        task="测试",
        deliverables=[],
        results={},
        outline={"slides": [{"slide_type": "cover", "title": "封面"}]},
        ppt_file=None,
        complexity="simple",
    )
    assert report["passed"] is False
    assert any("PPTX" in str(i) for i in report.get("issues", []))
