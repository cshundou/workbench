"""
自定义工具 Schema 单元测试。
"""

from app.schemas.custom_tool import CustomToolCreate


class TestCustomToolSchema:
    """自定义工具请求校验。"""

    def test_create_schema(self) -> None:
        data = CustomToolCreate(
            name="weather",
            description="查询天气",
            invoke_url="https://api.example.com/weather",
            auth_type="bearer",
            auth_token="secret",
        )
        assert data.name == "weather"
        assert str(data.invoke_url) == "https://api.example.com/weather"
