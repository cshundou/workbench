"""PPT 多 Agent 交付能力单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.delivery.ppt_generator_service import PptGeneratorService
from app.services.delivery.ppt_outline_builder import build_ppt_outline
from app.services.delivery.task_intent import detect_delivery_format


class TestTaskIntent:
    def test_detect_ppt_keywords(self) -> None:
        assert detect_delivery_format("帮我做一份竞品分析 PPT") == "ppt"
        assert detect_delivery_format("制作10页幻灯片汇报") == "ppt"
        assert detect_delivery_format("写一份调研报告") == "report"


    def test_detect_ppt_page_pattern(self) -> None:
        assert detect_delivery_format("做8页演示文稿") == "ppt"


class TestPptOutlineBuilder:
    def test_build_from_markdown_sections(self) -> None:
        deliverables = [
            {
                "role": "copywriter",
                "content": "## 市场概况\n- 规模增长\n- 竞争加剧\n\n## 趋势\n- AI 渗透",
            }
        ]
        outline = build_ppt_outline("AI 趋势 PPT", deliverables)
        assert outline["title"]
        assert len(outline["slides"]) >= 2

    def test_build_from_json_slides(self) -> None:
        payload = json.dumps(
            {
                "slides": [
                    {"title": "封面", "bullets": ["副标题"]},
                    {"title": "结论", "bullets": ["要点A", "要点B"]},
                ]
            }
        )
        outline = build_ppt_outline("测试", [{"role": "analyst", "content": payload}])
        assert len(outline["slides"]) == 2
        assert outline["slides"][0]["title"] == "封面"


class TestPptGeneratorService:
    def test_generate_pptx_file(self, tmp_path: Path) -> None:
        service = PptGeneratorService(base_dir=str(tmp_path))
        outline = {
            "title": "测试演示",
            "slides": [
                {"title": "背景", "bullets": ["要点1", "要点2"]},
                {"title": "结论", "bullets": ["建议A"]},
            ],
        }
        result = service.generate_pptx(1, 99, outline, filename="test.pptx")
        assert result["filename"] == "test.pptx"
        assert Path(result["file_path"]).is_file()
        assert result["slide_count"] >= 3
        assert result["size"] > 0

    def test_get_file_path_rejects_traversal(self, tmp_path: Path) -> None:
        service = PptGeneratorService(base_dir=str(tmp_path))
        service.generate_pptx(1, 1, {"title": "T", "slides": []}, filename="ok.pptx")
        assert service.get_file_path(1, 1, "../secret.pptx") is None
        assert service.get_file_path(1, 1, "ok.pptx") is not None
