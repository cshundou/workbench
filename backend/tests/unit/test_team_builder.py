"""智能团队组建引擎单元测试。"""

import pytest

from app.services.workflow.role_catalog import PRESET_PROFESSIONAL_ROLES
from app.services.workflow.team_builder import TeamBuilder
from app.services.workflow.team_template_catalog import OFFICIAL_TEAM_TEMPLATES


class TestRoleCatalog:
    """专业角色库。"""

    def test_preset_roles_count(self) -> None:
        assert len(PRESET_PROFESSIONAL_ROLES) >= 12

    def test_each_role_has_required_fields(self) -> None:
        for role in PRESET_PROFESSIONAL_ROLES:
            assert role.get("role_id")
            assert role.get("name")
            assert role.get("avatar")
            assert role.get("system_prompt")
            assert role.get("tools")
            assert role.get("responsibility")

    def test_auditor_in_presets(self) -> None:
        role_ids = [r["role_id"] for r in PRESET_PROFESSIONAL_ROLES]
        assert "auditor" in role_ids


class TestTeamBuilder:
    """团队组建器四步逻辑。"""

    @pytest.fixture
    def builder(self) -> TeamBuilder:
        return TeamBuilder()

    def test_identify_domain_tech(self, builder: TeamBuilder) -> None:
        assert builder.identify_domain("帮我写一个 Python API 接口") == "tech"

    def test_identify_domain_finance(self, builder: TeamBuilder) -> None:
        assert builder.identify_domain("计算 Q2 ROI 和成本分析") == "finance"

    def test_assess_complexity_simple(self, builder: TeamBuilder) -> None:
        assert builder.assess_complexity("简单概述一下") == "simple"

    def test_team_size_range(self, builder: TeamBuilder) -> None:
        config = builder.build("全面分析市场竞争格局并撰写深度报告")
        assert TeamBuilder.MIN_TEAM_SIZE <= config["team_size"] <= TeamBuilder.MAX_TEAM_SIZE

    def test_always_has_auditor(self, builder: TeamBuilder) -> None:
        config = builder.build("快速调研")
        role_ids = [m["role_id"] for m in config["members"]]
        assert "auditor" in role_ids

    def test_classic_five_template(self, builder: TeamBuilder) -> None:
        config = builder.build_classic_five("测试任务")
        assert config["team_size"] == 5
        assert config["template_id"] == "classic_five"
        role_ids = [m["role_id"] for m in config["members"]]
        assert role_ids == [
            "project_manager",
            "researcher",
            "engineer",
            "analyst",
            "auditor",
        ]

    def test_output_structure(self, builder: TeamBuilder) -> None:
        config = builder.build("生成广告投放分析报告")
        assert "team_id" in config
        assert "members" in config
        assert "workflow" in config
        assert config["max_review_rounds"] == 3
        for member in config["members"]:
            assert "role_id" in member
            assert "subtasks" in member

    def test_official_template(self, builder: TeamBuilder) -> None:
        config = builder.build("数据分析任务", template_id="data_analysis")
        assert config["template_id"] == "data_analysis"
        assert config["team_size"] >= 2


class TestOfficialTemplates:
    """官方场景模板。"""

    def test_official_template_count(self) -> None:
        assert len(OFFICIAL_TEAM_TEMPLATES) >= 10

    def test_each_template_has_auditor(self) -> None:
        for tpl in OFFICIAL_TEAM_TEMPLATES:
            members = tpl["team_config"]["members"]
            role_ids = [m["role_id"] for m in members]
            assert "auditor" in role_ids, f"模板 {tpl['id']} 缺少审核员"
