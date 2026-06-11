"""
知识库相关 Pydantic 模式。
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求。"""

    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    description: Optional[str] = Field(default=None, description="知识库描述")
    is_public: bool = Field(default=False, description="是否公开")
    embedding_model: str = Field(
        default="text-embedding-ada-002",
        max_length=50,
        description="嵌入模型",
    )


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_public: Optional[bool] = None
    embedding_model: Optional[str] = Field(default=None, max_length=50)
    chunk_size: Optional[int] = Field(default=None, ge=128, le=4096)
    chunk_overlap: Optional[int] = Field(default=None, ge=0, le=512)
    status: Optional[int] = Field(default=None, ge=0, le=1)


class KnowledgeBaseResponse(BaseModel):
    """知识库响应数据。"""

    id: int
    tenant_id: int
    name: str
    description: Optional[str] = None
    owner_id: Optional[int] = None
    is_public: bool
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    status: int
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeBaseListResponse(BaseModel):
    """知识库列表分页响应。"""

    items: List[KnowledgeBaseResponse]
    total: int
    page: int
    page_size: int


class DocumentResponse(BaseModel):
    """文档响应数据。"""

    id: int
    tenant_id: int
    kb_id: int
    name: str
    file_type: str
    file_size: int
    uploader_id: Optional[int] = None
    status: int
    total_chunks: int
    parse_task_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """文档列表分页响应。"""

    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class ParseProgressResponse(BaseModel):
    """文档解析进度响应。"""

    document_id: int
    status: int
    progress: int = Field(description="解析进度 0-100")
    message: str = ""
    parse_status: str = Field(
        default="pending",
        description="processing / completed / failed / pending",
    )


class SearchRequest(BaseModel):
    """知识库检索请求。"""

    query: str = Field(..., min_length=1, description="检索问题")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")
    use_rag: bool = Field(default=True, description="是否启用知识库增强检索")
    filters: Optional[dict[str, Any]] = Field(
        default=None,
        description="过滤条件：department、file_type、document_id、tags",
    )


class SearchResultItem(BaseModel):
    """单条检索结果。"""

    content: str
    metadata: dict[str, Any]
    score: Optional[float] = None


class SearchResponse(BaseModel):
    """检索响应。"""

    query: str
    results: List[SearchResultItem]
    total: int


class ChatRequest(BaseModel):
    """流式问答请求。"""

    query: str = Field(..., min_length=1, description="用户问题")
    top_k: int = Field(default=5, ge=1, le=20, description="检索数量")
    use_rag: bool = Field(default=True, description="是否启用知识库增强检索")
    filters: Optional[dict[str, Any]] = Field(default=None, description="过滤条件")


class ChatAnswerResponse(BaseModel):
    """非流式问答响应。"""

    answer: str
    sources: List[dict[str, Any]]
