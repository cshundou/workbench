"""
知识库业务服务：CRUD、文档管理、解析任务调度。
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.knowledge_base import (
    DocumentListResponse,
    DocumentResponse,
    ImportUrlRequest,
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    ParseProgressResponse,
)
from app.services.rag.document_loader import DocumentLoader
from app.services.rag.rag_service import rag_service
from app.services.rag.url_fetcher import UrlFetcher
from app.services.user_key_context import UserKeyContext
from app.services.audit_service import audit_service

logger = get_logger(__name__)

DOCUMENT_STATUS_PENDING = 0
DOCUMENT_STATUS_DONE = 1
DOCUMENT_STATUS_FAILED = 2

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".xlsx", ".html", ".ppt", ".pptx"}


class KnowledgeBaseService:
    """知识库 CRUD 与文档管理业务逻辑。"""

    def __init__(self) -> None:
        self.document_loader = DocumentLoader()
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    async def _get_kb_or_raise(
        self,
        db: AsyncSession,
        kb_id: int,
        tenant_id: int,
    ) -> KnowledgeBase:
        """按 ID 查询知识库，不存在则抛出异常。"""
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        kb = result.scalar_one_or_none()
        if kb is None:
            raise NotFoundError(message="知识库不存在")
        return kb

    async def _check_kb_access(
        self,
        kb: KnowledgeBase,
        user: User,
        require_owner: bool = False,
    ) -> None:
        """校验用户对知识库的访问权限。"""
        if kb.is_public and not require_owner:
            return
        if kb.owner_id == user.id:
            return
        if require_owner:
            raise ValidationError(message="仅知识库所有者可执行此操作")
        raise ValidationError(message="无权访问该知识库")

    def _to_kb_response(self, kb: KnowledgeBase, document_count: int = 0) -> KnowledgeBaseResponse:
        """ORM 转响应模式。"""
        return KnowledgeBaseResponse(
            id=kb.id,
            tenant_id=kb.tenant_id,
            name=kb.name,
            description=kb.description,
            owner_id=kb.owner_id,
            is_public=kb.is_public,
            embedding_model=kb.embedding_model,
            chunk_size=kb.chunk_size,
            chunk_overlap=kb.chunk_overlap,
            status=kb.status,
            document_count=document_count,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        )

    def _to_document_response(
        self,
        document: Document,
        parse_task_id: Optional[str] = None,
    ) -> DocumentResponse:
        """文档 ORM 转响应模式。"""
        return DocumentResponse(
            id=document.id,
            tenant_id=document.tenant_id,
            kb_id=document.kb_id,
            name=document.name,
            file_type=document.file_type,
            file_size=document.file_size,
            uploader_id=document.uploader_id,
            status=document.status,
            total_chunks=document.total_chunks,
            parse_task_id=parse_task_id,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    async def list_knowledge_bases(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> KnowledgeBaseListResponse:
        """分页列出当前用户可访问的知识库。"""
        access_filter = or_(
            KnowledgeBase.is_public.is_(True),
            KnowledgeBase.owner_id == user.id,
        )
        count_stmt = (
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.tenant_id == tenant_id, access_filter)
        )
        total = (await db.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.tenant_id == tenant_id, access_filter)
            .order_by(KnowledgeBase.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        kbs = (await db.execute(stmt)).scalars().all()

        items: list[KnowledgeBaseResponse] = []
        for kb in kbs:
            doc_count_stmt = select(func.count()).select_from(Document).where(
                Document.kb_id == kb.id
            )
            doc_count = (await db.execute(doc_count_stmt)).scalar_one()
            items.append(self._to_kb_response(kb, doc_count))

        return KnowledgeBaseListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_knowledge_base(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        data: KnowledgeBaseCreate,
    ) -> KnowledgeBaseResponse:
        """创建知识库。"""
        kb = KnowledgeBase(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
            owner_id=user.id,
            is_public=data.is_public,
            embedding_model=data.embedding_model,
            status=1,
        )
        db.add(kb)
        try:
            await db.flush()
        except IntegrityError as exc:
            logger.warning("知识库名称冲突 tenant_id=%s name=%s", tenant_id, data.name)
            raise ConflictError(message="知识库名称已存在") from exc

        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="knowledge_base.create",
            resource_type="knowledge_base",
            resource_id=kb.id,
            detail={"name": kb.name, "is_public": kb.is_public},
        )
        logger.info("创建知识库 id=%s name=%s", kb.id, kb.name)
        return self._to_kb_response(kb, 0)

    async def get_knowledge_base(
        self,
        db: AsyncSession,
        kb_id: int,
        tenant_id: int,
        user: User,
    ) -> KnowledgeBaseResponse:
        """获取知识库详情。"""
        kb = await self._get_kb_or_raise(db, kb_id, tenant_id)
        await self._check_kb_access(kb, user)

        doc_count = (
            await db.execute(
                select(func.count()).select_from(Document).where(Document.kb_id == kb_id)
            )
        ).scalar_one()
        return self._to_kb_response(kb, doc_count)

    async def update_knowledge_base(
        self,
        db: AsyncSession,
        kb_id: int,
        tenant_id: int,
        user: User,
        data: KnowledgeBaseUpdate,
    ) -> KnowledgeBaseResponse:
        """更新知识库。"""
        kb = await self._get_kb_or_raise(db, kb_id, tenant_id)
        await self._check_kb_access(kb, user, require_owner=True)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(kb, field, value)

        try:
            await db.flush()
        except IntegrityError as exc:
            raise ConflictError(message="知识库名称已存在") from exc

        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="knowledge_base.update",
            resource_type="knowledge_base",
            resource_id=kb.id,
            detail=update_data,
        )
        doc_count = (
            await db.execute(
                select(func.count()).select_from(Document).where(Document.kb_id == kb_id)
            )
        ).scalar_one()
        logger.info("更新知识库 id=%s", kb_id)
        return self._to_kb_response(kb, doc_count)

    async def delete_knowledge_base(
        self,
        db: AsyncSession,
        kb_id: int,
        tenant_id: int,
        user: User,
        user_ctx: UserKeyContext,
    ) -> None:
        """删除知识库及其文档文件与向量集合。"""
        kb = await self._get_kb_or_raise(db, kb_id, tenant_id)
        await self._check_kb_access(kb, user, require_owner=True)

        await rag_service.delete_kb_vectors(kb_id, kb.embedding_model, user_ctx)

        docs_stmt = select(Document).where(Document.kb_id == kb_id)
        documents = (await db.execute(docs_stmt)).scalars().all()
        for document in documents:
            if os.path.isfile(document.file_path):
                try:
                    os.remove(document.file_path)
                except OSError as exc:
                    logger.warning("删除文件失败 path=%s: %s", document.file_path, exc)

        upload_dir = Path(settings.upload_dir) / str(tenant_id) / str(kb_id)
        if upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)

        await db.delete(kb)
        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="knowledge_base.delete",
            resource_type="knowledge_base",
            resource_id=kb_id,
            detail={"name": kb.name},
        )
        logger.info("删除知识库 id=%s", kb_id)

    async def list_documents(
        self,
        db: AsyncSession,
        kb_id: int,
        tenant_id: int,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> DocumentListResponse:
        """分页列出知识库文档。"""
        kb = await self._get_kb_or_raise(db, kb_id, tenant_id)
        await self._check_kb_access(kb, user)

        count_stmt = (
            select(func.count())
            .select_from(Document)
            .where(Document.kb_id == kb_id, Document.tenant_id == tenant_id)
        )
        total = (await db.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(Document)
            .where(Document.kb_id == kb_id, Document.tenant_id == tenant_id)
            .order_by(Document.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        documents = (await db.execute(stmt)).scalars().all()

        return DocumentListResponse(
            items=[self._to_document_response(doc) for doc in documents],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def upload_document(
        self,
        db: AsyncSession,
        kb_id: int,
        tenant_id: int,
        user: User,
        file: UploadFile,
        tags: Optional[str] = None,
    ) -> DocumentResponse:
        """
        上传文档并调度后台解析任务。

        Args:
            db: 数据库会话。
            kb_id: 知识库 ID。
            tenant_id: 租户 ID。
            user: 当前用户。
            file: 上传文件。
            tags: 逗号分隔标签。

        Returns:
            文档响应。
        """
        kb = await self._get_kb_or_raise(db, kb_id, tenant_id)
        await self._check_kb_access(kb, user)

        if not file.filename:
            raise ValidationError(message="文件名不能为空")

        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                message=f"不支持的文件格式，允许: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        upload_dir = Path(settings.upload_dir) / str(tenant_id) / str(kb_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
        file_path = upload_dir / safe_name

        content = await file.read()
        if not content:
            raise ValidationError(message="上传文件为空")

        with open(file_path, "wb") as output:
            output.write(content)

        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []

        document = Document(
            tenant_id=tenant_id,
            kb_id=kb_id,
            name=file.filename,
            file_type=file_ext,
            file_size=len(content),
            file_path=str(file_path),
            uploader_id=user.id,
            status=DOCUMENT_STATUS_PENDING,
            total_chunks=0,
        )
        db.add(document)
        await db.flush()

        await rag_service.set_parse_progress(document.id, 0, "等待解析", status="pending")
        parse_task_id = await rag_service.schedule_parse_document(
            document.id,
            user.id,
            tenant_id,
            tags=tag_list,
        )
        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="document.create",
            resource_type="document",
            resource_id=document.id,
            detail={
                "kb_id": kb_id,
                "name": document.name,
                "file_type": document.file_type,
                "task_id": parse_task_id,
            },
        )

        logger.info(
            "文档上传成功 document_id=%s kb_id=%s name=%s",
            document.id,
            kb_id,
            file.filename,
        )
        return self._to_document_response(document, parse_task_id=parse_task_id)

    async def get_document(
        self,
        db: AsyncSession,
        kb_id: int,
        doc_id: int,
        tenant_id: int,
        user: User,
    ) -> DocumentResponse:
        """获取文档详情。"""
        kb = await self._get_kb_or_raise(db, kb_id, tenant_id)
        await self._check_kb_access(kb, user)

        stmt = select(Document).where(
            Document.id == doc_id,
            Document.kb_id == kb_id,
            Document.tenant_id == tenant_id,
        )
        document = (await db.execute(stmt)).scalar_one_or_none()
        if document is None:
            raise NotFoundError(message="文档不存在")
        return self._to_document_response(document)

    async def get_document_file_path(
        self,
        db: AsyncSession,
        kb_id: int,
        doc_id: int,
        tenant_id: int,
        user: User,
    ) -> tuple[str, str]:
        """获取文档下载路径与原始文件名。"""
        document_response = await self.get_document(db, kb_id, doc_id, tenant_id, user)
        stmt = select(Document).where(Document.id == doc_id)
        document = (await db.execute(stmt)).scalar_one()
        if not os.path.isfile(document.file_path):
            raise NotFoundError(message="文档文件不存在")
        return document.file_path, document_response.name

    async def delete_document(
        self,
        db: AsyncSession,
        kb_id: int,
        doc_id: int,
        tenant_id: int,
        user: User,
    ) -> None:
        """删除文档及其向量（增量更新）。"""
        kb = await self._get_kb_or_raise(db, kb_id, tenant_id)
        await self._check_kb_access(kb, user)

        stmt = select(Document).where(
            Document.id == doc_id,
            Document.kb_id == kb_id,
            Document.tenant_id == tenant_id,
        )
        document = (await db.execute(stmt)).scalar_one_or_none()
        if document is None:
            raise NotFoundError(message="文档不存在")

        from app.services.user_key_context import user_key_resolver

        user_ctx = await user_key_resolver.load_context(db, user.id, tenant_id)
        await rag_service.delete_document_vectors(db, document, user_ctx)

        if os.path.isfile(document.file_path):
            try:
                os.remove(document.file_path)
            except OSError as exc:
                logger.warning("删除文件失败: %s", exc)

        await rag_service.clear_parse_progress(doc_id)
        await db.delete(document)
        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="document.delete",
            resource_type="document",
            resource_id=doc_id,
            detail={"kb_id": kb_id, "name": document.name},
        )
        logger.info("删除文档 document_id=%s kb_id=%s", doc_id, kb_id)

    async def get_parse_progress(
        self,
        db: AsyncSession,
        kb_id: int,
        doc_id: int,
        tenant_id: int,
        user: User,
    ) -> ParseProgressResponse:
        """查询文档解析进度。"""
        document = await self.get_document(db, kb_id, doc_id, tenant_id, user)
        progress_info = await rag_service.get_parse_progress(doc_id)

        if progress_info:
            return ParseProgressResponse(
                document_id=doc_id,
                status=document.status,
                progress=progress_info.get("progress", 0),
                message=progress_info.get("message", ""),
                parse_status=progress_info.get("status", "pending"),
            )

        status_map = {
            DOCUMENT_STATUS_PENDING: ("pending", 0, "等待解析"),
            DOCUMENT_STATUS_DONE: ("completed", 100, "解析完成"),
            DOCUMENT_STATUS_FAILED: ("failed", 0, "解析失败"),
        }
        parse_status, progress, message = status_map.get(
            document.status,
            ("pending", 0, "未知状态"),
        )
        return ParseProgressResponse(
            document_id=doc_id,
            status=document.status,
            progress=progress,
            message=message,
            parse_status=parse_status,
        )

    async def import_url(
        self,
        db: AsyncSession,
        kb_id: int,
        tenant_id: int,
        user: User,
        data: ImportUrlRequest,
    ) -> DocumentResponse:
        """从 URL 抓取网页正文并入库。"""
        kb = await self._get_kb_or_raise(db, kb_id, tenant_id)
        await self._check_kb_access(kb, user, require_owner=True)

        fetcher = UrlFetcher()
        page_title, content = await fetcher.fetch(data.url)
        if not content.strip():
            raise ValidationError(message="未能从 URL 提取有效内容")

        doc_title = data.title or page_title or "Imported Web Page"
        safe_filename = f"{uuid.uuid4().hex}_{doc_title[:50]}.html"
        upload_dir = Path(settings.upload_dir) / str(tenant_id) / str(kb_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / safe_filename

        with open(file_path, "w", encoding="utf-8") as output:
            output.write(content)

        encoded = content.encode("utf-8")
        document = Document(
            tenant_id=tenant_id,
            kb_id=kb_id,
            name=doc_title,
            file_type=".html",
            file_size=len(encoded),
            file_path=str(file_path),
            uploader_id=user.id,
            status=DOCUMENT_STATUS_PENDING,
            total_chunks=0,
        )
        db.add(document)
        await db.flush()

        await rag_service.set_parse_progress(document.id, 0, "等待解析", status="pending")
        parse_task_id = await rag_service.schedule_parse_document(
            document.id,
            user.id,
            tenant_id,
            tags=["url-import"],
        )
        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="document.import_url",
            resource_type="document",
            resource_id=document.id,
            detail={"kb_id": kb_id, "url": data.url, "task_id": parse_task_id},
        )
        logger.info("URL 导入成功 document_id=%s url=%s", document.id, data.url)
        return self._to_document_response(document, parse_task_id=parse_task_id)


knowledge_base_service = KnowledgeBaseService()
