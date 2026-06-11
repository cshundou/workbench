# 企业智能协作工作台开发文档

## 基于增强 RAG + 多 Agent + LangGraph 工作流

**文档版本**：v1.0

**最后更新**：2026-06-10

**适用对象**：前端开发者、后端 / AI 开发者、全栈开发者、运维工程师、求职者

------

## 文档导读

本文档为企业级可直接交付的完整开发指南，不同角色重点阅读章节如下：

- **前端开发者**：重点阅读第 2 章前端技术栈、第 7 章 Vue 前端关键技术落地要点、第 8 章 API 接口文档、第 9 章分阶段开发计划
- **后端 / AI 开发者**：重点阅读第 2 章后端技术栈、第 3 章系统架构设计、第 4 章数据库设计、第 5 章三大核心技术强化设计、第 8 章 API 接口文档
- **全栈开发者**：完整阅读所有章节，按第 9 章开发计划逐步推进
- **运维工程师**：重点阅读第 2 章部署运维技术栈、第 11 章部署指南
- **求职者**：重点阅读第 12 章简历标准写法、第 13 章面试高频问题 & 应答思路

------

## 目录

### 一、项目总览

1.1 项目名称

1.2 项目定位

1.3 核心适配调整

1.4 项目竞争力分析

### 二、完整技术栈

2.1 前端技术栈（Vue 生态）

2.2 后端技术栈（Python+AI 核心）

2.3 部署 & 运维技术栈

### 三、系统架构设计

3.1 整体架构图

3.2 模块划分

3.3 数据流图

3.4 安全架构

### 四、数据库设计

4.1 数据库选型说明

4.2 表结构设计（含 SQL 语句）

4.3 索引设计

4.4 关联关系图

### 五、三大核心技术强化设计

5.1 增强版 RAG 系统

 5.1.1 全链路架构（7 层优化）

 5.1.2 RAG 功能落地实现

5.2 Agent 智能体系统

 5.2.1 智能体能力设计

 5.2.2 前端交互实现

5.3 LangGraph 多智能体工作流

 5.3.1 多智能体角色划分

 5.3.2 LangGraph 工作流拓扑

 5.3.3 核心技术特性实现

 5.3.4 前端可视化展示

### 六、完整功能模块实现

6.1 账户 & 权限系统

6.2 增强 RAG 知识库

6.3 单 Agent 智能体中心

6.4 LangGraph 多智能体工作流

6.5 全局流式交互体验

6.6 系统监控与运维

### 七、Vue 前端关键技术落地要点

7.1 流式输出 SSE 封装

7.2 Pinia 模块化状态设计

7.3 组件拆分规范

7.4 路由设计

7.5 性能优化方案

### 八、API 接口文档

8.1 接口规范

8.2 用户认证接口

8.3 知识库管理接口

8.4 智能体管理接口

8.5 工作流管理接口

8.6 流式对话接口

8.7 系统监控接口

8.8 错误码说明

### 九、分阶段开发计划

9.1 第 1 周：项目脚手架搭建 & 基础框架

9.2 第 2 周：用户体系 + 基础文档上传

9.3 第 3~4 周：增强 RAG 全功能落地

9.4 第 5~6 周：单 Agent 智能体 + 工具调用

9.5 第 7~8 周：LangGraph 多智能体工作流

9.6 第 9~10 周：优化、工程化、部署、文档

### 十、测试指南

10.1 单元测试

10.2 集成测试

10.3 性能测试

10.4 AI 能力评估

### 十一、部署指南

11.1 环境准备

11.2 依赖安装

11.3 配置文件说明

11.4 分步部署命令

11.5 启动验证方法

11.6 常见部署问题排查

### 十二、简历标准写法

12.1 项目名称

12.2 项目描述

12.3 技术栈

12.4 核心职责 & 技术亮点

### 十三、面试高频问题 & 应答思路

13.1 RAG 相关问题

13.2 Agent 相关问题

13.3 LangGraph 相关问题

13.4 前端技术相关问题

13.5 架构设计相关问题

### 十四、补充建议与最佳实践

14.1 开发落地提速建议

14.2 代码规范与最佳实践

14.3 性能优化建议

14.4 常见问题排查

### 十五、版本历史记录

15.1 版本号说明

15.2 更新记录模板

------

## 一、项目总览

### 1.1 项目名称

**企业智能协作工作台 —— 基于增强 RAG + 多 Agent + LangGraph 工作流**

### 1.2 项目定位

面向企业内部的**知识问答 + 任务自动化 + 多角色 AI 团队协同**平台。

依托**增强版 RAG** 沉淀企业私有知识库，结合**单 / 多智能体**完成工具调用、任务拆解，最终通过 **LangGraph** 编排复杂串行 / 并行 / 分支工作流，完全贴合当前企业 AI 团队主流技术选型与招聘要求。

### 1.3 核心适配调整

- 前端：全面切换 **Vue 3 + Vite + Pinia** 技术栈（主力技术）
- 后端：Python + FastAPI + LangChain + LangGraph（延续已有 Python 基础）
- 核心技术强化：**高阶 RAG 全链路优化、Agent 工具系统、LangGraph 状态化多智能体工作流**
- 附加企业能力：权限、多租户、流式通信、日志追踪、容器化部署

### 1.4 项目竞争力分析

1. **企业主流方向**：当前中大厂 AI 应用、企业知识库、AI 自动化流程、客服 / 办公智能体全部基于 `RAG + Agent + LangGraph` 技术栈
2. **全覆盖招聘考点**：Vue 工程化、流式交互、SSE/WebSocket、高阶 RAG、智能体工具调用、多智能体编排、状态管理、向量库、异步后端
3. **技术深度足够**：不是简单调 API，包含**架构设计、性能优化、问题兜底、工程化落地**，面试可深挖
4. **差异化明显**：区别于普通聊天机器人、简易笔记，主打**复杂业务工作流 + 企业私有知识结合**

------

## 二、完整技术栈

### 2.1 前端技术栈（Vue 生态）

表格







| 分类          | 技术选型                                   | 作用                               |
| ------------- | ------------------------------------------ | ---------------------------------- |
| 核心框架      | Vue 3 + Composition API + `<script setup>` | 主流企业写法，类型友好             |
| 构建工具      | Vite 5.x                                   | 极速构建、插件扩展                 |
| 类型系统      | TypeScript 5.x                             | 全项目类型约束，企业强制要求       |
| 状态管理      | Pinia 2.x                                  | 替代 Vuex，轻量化、模块化状态      |
| 路由          | Vue Router 4.x                             | 页面路由、权限路由                 |
| UI 组件库     | Element Plus 2.x                           | 企业级后台 UI，适配管理端场景      |
| 样式方案      | SCSS + UnoCSS                              | 统一样式规范                       |
| 代码编辑器    | Monaco Editor 0.47.x                       | 代码片段、提示词编辑、文档预览     |
| 流式通信      | 原生 SSE + WebSocket                       | 大模型流式输出、智能体状态实时推送 |
| 图表 / 可视化 | ECharts 5.x                                | 检索统计、Token 消耗、任务报表     |
| 文件处理      | XLSX + PDF.js + mammoth                    | 前端解析 PDF/Excel/Word 预览       |
| 工程化        | ESLint 8.x + Prettier 3.x + Husky 9.x      | 代码规范、提交校验                 |

### 2.2 后端技术栈（Python + AI 核心）

表格







| 分类        | 技术选型                                 | 作用                                    |
| ----------- | ---------------------------------------- | --------------------------------------- |
| Web 框架    | FastAPI 0.110.x                          | 异步高性能接口，自动接口文档            |
| AI 框架     | LangChain 0.1.x + LangGraph 0.0.x        | Agent 能力 + 多智能体工作流编排（核心） |
| 大模型      | 通义千问 4 / 豆包 4 + GPT-4o             | 多模型兼容、降级兜底                    |
| 向量数据库  | Chroma 0.4.x (本地) + Pinecone (线上)    | RAG 向量存储、语义检索                  |
| 关系数据库  | PostgreSQL 16                            | 用户、知识库、任务、权限数据持久化      |
| ORM         | SQLAlchemy 2.x                           | 数据库操作                              |
| 缓存 / 状态 | Redis 7.x                                | 对话上下文、Agent 状态、限流、会话缓存  |
| 文档解析    | Unstructured 0.12.x + PyPDF2             | 多格式文档解析、清洗                    |
| 工具集      | Tavily 搜索、PythonREPL、SQLDatabaseTool | Agent 外部工具调用                      |
| 可观测      | LangSmith                                | 追踪 Agent/RAG 链路、调试、评估         |

### 2.3 部署 & 运维技术栈

- Docker 25.x + Docker Compose 2.x：一键编排前后端、数据库、Redis
- 服务部署：阿里云 ECS / 腾讯云 CVM / Render
- 反向代理：Nginx 1.25.x
- 日志收集：ELK Stack（可选）
- 监控告警：Prometheus + Grafana（可选）

------

## 三、系统架构设计

### 3.1 整体架构图

plaintext









```
┌─────────────────────────────────────────────────────────┐
│                    前端层 (Vue 3 生态)                   │
├─────────┬─────────┬─────────┬─────────┬─────────┬─────────┤
│  登录页 │ 知识库  │ 智能体  │ 工作流  │  控制台 │ 监控面板│
└─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    网关层 (FastAPI)                      │
├─────────┬─────────┬─────────┬─────────┬─────────┬─────────┤
│ 认证鉴权│ 路由分发│ 限流控制│ 异常处理│ 日志记录│ SSE/WS  │
└─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    业务服务层                            │
├─────────┬─────────┬─────────┬─────────┬─────────┬─────────┤
│用户服务│知识库服务│智能体服务│工作流服务│工具服务│统计服务│
└─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    AI 核心层                             │
├─────────────────────┬─────────────────────┬─────────────┤
│   增强 RAG 引擎     │   Agent 执行引擎    │ LangGraph   │
│ (文档处理/检索/重排)│ (工具调用/规划)     │ 工作流引擎  │
└─────────────────────┴─────────────────────┴─────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    数据持久层                            │
├─────────┬─────────┬─────────┬─────────┬─────────────────┤
│PostgreSQL│  Redis  │ Chroma  │ Pinecone│ 外部大模型API  │
└─────────┴─────────┴─────────┴─────────┴─────────────────┘
```

### 3.2 模块划分

1. **用户认证模块**：负责用户登录、注册、权限管理、多租户隔离
2. **知识库模块**：文档上传、解析、向量化、检索、管理
3. **智能体模块**：单智能体创建、配置、对话、工具调用
4. **工作流模块**：多智能体工作流定义、执行、监控、人工介入
5. **工具服务模块**：统一管理所有外部工具，提供标准调用接口
6. **流式通信模块**：处理 SSE 和 WebSocket 连接，实现实时消息推送
7. **系统监控模块**：Token 消耗统计、接口调用量、错误日志收集

### 3.3 数据流图

**知识库问答数据流**：

1. 用户上传文档 → 文档解析 → 智能分块 → 元数据增强 → 向量化 → 存储到向量库
2. 用户提问 → 意图识别 → 双路检索 → 重排序 → 上下文拼接 → 大模型生成回答 → 标注引用 → 返回前端

**单 Agent 任务数据流**：

1. 用户提问 → Agent 意图识别 → 判断是否需要工具 → 选择工具 → 调用工具服务
2. 工具执行 → 返回结果 → Agent 汇总 → 生成最终回答 → 返回前端

**多智能体工作流数据流**：

1. 用户提交任务 → 调度中心 Agent 拆解任务 → 分配给对应专业 Agent
2. 各 Agent 并行 / 串行执行 → 中间结果存入全局 State
3. 审核 Agent 汇总结果 → 生成最终输出 → 返回前端

### 3.4 安全架构

- **接口安全**：JWT 令牌认证、接口限流、IP 白名单、请求签名
- **数据安全**：多租户数据隔离、敏感数据加密存储、文档权限控制
- **AI 安全**：提示词注入防护、敏感内容过滤、Token 用量限制
- **日志审计**：所有操作记录日志、工具调用审计、异常行为告警

------

## 四、数据库设计

### 4.1 数据库选型说明

- **PostgreSQL 16**：支持 JSONB 类型、全文检索、事务性强，适合存储结构化业务数据
- **Redis 7.x**：高性能缓存，用于存储会话状态、Agent 执行状态、限流数据
- **Chroma/Pinecone**：专用向量数据库，用于存储文档向量和元数据

### 4.2 表结构设计（含 SQL 语句）

sql









```
-- 创建数据库
CREATE DATABASE ai_workbench;
\c ai_workbench;

-- 租户表
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    domain VARCHAR(100) UNIQUE NOT NULL,
    status SMALLINT DEFAULT 1 CHECK (status IN (0, 1)), -- 0:禁用, 1:启用
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 角色表
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    description TEXT,
    permissions JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name)
);

-- 用户表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id INTEGER REFERENCES roles(id) ON DELETE SET NULL,
    status SMALLINT DEFAULT 1 CHECK (status IN (0, 1)), -- 0:禁用, 1:启用
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, username),
    UNIQUE(tenant_id, email)
);

-- 知识库表
CREATE TABLE knowledge_bases (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    is_public BOOLEAN DEFAULT FALSE,
    embedding_model VARCHAR(50) NOT NULL DEFAULT 'text-embedding-ada-002',
    chunk_size INTEGER NOT NULL DEFAULT 512,
    chunk_overlap INTEGER NOT NULL DEFAULT 100,
    status SMALLINT DEFAULT 1 CHECK (status IN (0, 1)), -- 0:禁用, 1:启用
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name)
);

-- 文档表
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    kb_id INTEGER REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size BIGINT NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    uploader_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status SMALLINT DEFAULT 0 CHECK (status IN (0, 1, 2)), -- 0:待处理, 1:已处理, 2:处理失败
    total_chunks INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 文档分块表
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    parent_chunk_id INTEGER REFERENCES document_chunks(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    vector_id VARCHAR(100) NOT NULL, -- 向量数据库中的ID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, chunk_index)
);

-- 智能体表
CREATE TABLE agents (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    system_prompt TEXT NOT NULL,
    model_name VARCHAR(50) NOT NULL DEFAULT 'gpt-3.5-turbo',
    temperature FLOAT NOT NULL DEFAULT 0.7,
    max_tokens INTEGER NOT NULL DEFAULT 2048,
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    is_public BOOLEAN DEFAULT FALSE,
    tools JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name)
);

-- 工作流表
CREATE TABLE workflows (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    graph_definition JSONB NOT NULL,
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name)
);

-- 工作流执行记录
CREATE TABLE workflow_executions (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER REFERENCES workflows(id) ON DELETE CASCADE,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'interrupted')),
    input_params JSONB NOT NULL DEFAULT '{}'::JSONB,
    output_result JSONB,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- 对话历史表
CREATE TABLE chat_histories (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(100) NOT NULL,
    message_type VARCHAR(20) NOT NULL CHECK (message_type IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Token 消耗记录表
CREATE TABLE token_usage (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    model_name VARCHAR(50) NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 4.3 索引设计

sql









```
-- 用户表索引
CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_role_id ON users(role_id);

-- 知识库索引
CREATE INDEX idx_knowledge_bases_tenant_id ON knowledge_bases(tenant_id);
CREATE INDEX idx_knowledge_bases_owner_id ON knowledge_bases(owner_id);

-- 文档索引
CREATE INDEX idx_documents_tenant_id ON documents(tenant_id);
CREATE INDEX idx_documents_kb_id ON documents(kb_id);
CREATE INDEX idx_documents_uploader_id ON documents(uploader_id);
CREATE INDEX idx_documents_status ON documents(status);

-- 文档分块索引
CREATE INDEX idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_document_chunks_vector_id ON document_chunks(vector_id);

-- 智能体索引
CREATE INDEX idx_agents_tenant_id ON agents(tenant_id);
CREATE INDEX idx_agents_owner_id ON agents(owner_id);

-- 工作流索引
CREATE INDEX idx_workflows_tenant_id ON workflows(tenant_id);
CREATE INDEX idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);

-- 对话历史索引
CREATE INDEX idx_chat_histories_tenant_id ON chat_histories(tenant_id);
CREATE INDEX idx_chat_histories_user_id ON chat_histories(user_id);
CREATE INDEX idx_chat_histories_session_id ON chat_histories(session_id);
CREATE INDEX idx_chat_histories_created_at ON chat_histories(created_at);

-- Token 消耗索引
CREATE INDEX idx_token_usage_tenant_id ON token_usage(tenant_id);
CREATE INDEX idx_token_usage_user_id ON token_usage(user_id);
CREATE INDEX idx_token_usage_created_at ON token_usage(created_at);
```

### 4.4 关联关系图

- **租户** 1:N **用户** 1:N **知识库** 1:N **文档** 1:N **文档分块**
- **租户** 1:N **角色** 1:N **用户**
- **租户** 1:N **智能体**
- **租户** 1:N **工作流** 1:N **工作流执行记录**
- **用户** 1:N **对话历史**
- **用户** 1:N **Token 消耗记录**

------

## 五、三大核心技术强化设计

### 5.1 增强版 RAG 系统

#### 5.1.1 全链路架构（7 层优化）

**1. 文档接入层**

支持格式：PDF、MD、TXT、Excel、Word、PowerPoint、网页链接

处理流程：

python



运行







```
# backend/app/services/rag/document_loader.py
from unstructured.partition.auto import partition
from unstructured.cleaners.core import clean_extra_whitespace, remove_punctuation
import PyPDF2
import io

class DocumentLoader:
    def __init__(self):
        self.supported_formats = {
            '.pdf': self.load_pdf,
            '.txt': self.load_text,
            '.md': self.load_markdown,
            '.docx': self.load_docx,
            '.xlsx': self.load_excel,
            '.html': self.load_html
        }
    
    def load_document(self, file_path: str, file_type: str) -> str:
        """加载并清洗文档"""
        if file_type not in self.supported_formats:
            raise ValueError(f"不支持的文件格式: {file_type}")
        
        content = self.supported_formats[file_type](file_path)
        # 基础清洗
        content = clean_extra_whitespace(content)
        content = content.replace('\x00', '')  # 移除空字符
        return content
    
    def load_pdf(self, file_path: str) -> str:
        """加载PDF文档，处理水印和乱码"""
        elements = partition(filename=file_path, strategy="fast")
        return "\n\n".join([str(el) for el in elements if len(str(el).strip()) > 0])
    
    def load_text(self, file_path: str) -> str:
        """加载纯文本文档"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def load_markdown(self, file_path: str) -> str:
        """加载Markdown文档"""
        return self.load_text(file_path)
    
    def load_docx(self, file_path: str) -> str:
        """加载Word文档"""
        from docx import Document
        doc = Document(file_path)
        return "\n\n".join([para.text for para in doc.paragraphs])
    
    def load_excel(self, file_path: str) -> str:
        """加载Excel文档"""
        import pandas as pd
        df = pd.read_excel(file_path)
        return df.to_string(index=False)
    
    def load_html(self, file_path: str) -> str:
        """加载HTML文档"""
        from bs4 import BeautifulSoup
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        return soup.get_text()
```

**2. 智能分块层**

实现混合分块策略：固定分块 + 语义分块 + 重叠分片 + 标题锚定

python



运行







```
# backend/app/services/rag/chunker.py
from langchain.text_splitter import RecursiveCharacterTextSplitter, SemanticChunker
from langchain_community.embeddings import OpenAIEmbeddings
import re

class IntelligentChunker:
    def __init__(self, embedding_model: str = "text-embedding-ada-002"):
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        self.semantic_chunker = SemanticChunker(
            self.embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=95
        )
        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=100,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def split_document(self, content: str, metadata: dict) -> list[dict]:
        """智能分块，返回带元数据的块列表"""
        # 提取标题结构
        headings = self._extract_headings(content)
        
        # 先进行语义分块
        semantic_chunks = self.semantic_chunker.split_text(content)
        
        # 对过大的语义块进行递归分块
        final_chunks = []
        for i, chunk in enumerate(semantic_chunks):
            if len(chunk) > 1024:
                sub_chunks = self.recursive_splitter.split_text(chunk)
                for j, sub_chunk in enumerate(sub_chunks):
                    final_chunks.append({
                        "content": sub_chunk,
                        "metadata": {
                            **metadata,
                            "chunk_index": f"{i}.{j}",
                            "parent_chunk_id": i,
                            "heading": self._get_current_heading(chunk, headings)
                        }
                    })
            else:
                final_chunks.append({
                    "content": chunk,
                    "metadata": {
                        **metadata,
                        "chunk_index": str(i),
                        "heading": self._get_current_heading(chunk, headings)
                    }
                })
        
        return final_chunks
    
    def _extract_headings(self, content: str) -> list[tuple[int, int, str]]:
        """提取文档中的标题结构"""
        heading_pattern = r'^(#{1,6})\s+(.+)$|^(.+)\n[=-]+$'
        headings = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            match = re.match(heading_pattern, line, re.MULTILINE)
            if match:
                level = len(match.group(1)) if match.group(1) else 1
                text = match.group(2) if match.group(2) else match.group(3)
                headings.append((i, level, text.strip()))
        
        return headings
    
    def _get_current_heading(self, chunk: str, headings: list[tuple[int, int, str]]) -> str:
        """获取当前块所属的标题"""
        if not headings:
            return ""
        
        # 找到chunk中出现的最后一个标题
        chunk_start = 0
        for line_num, level, text in reversed(headings):
            if text in chunk:
                return text
        
        # 如果没有找到，返回最接近的前一个标题
        return headings[-1][2] if headings else ""
```

**3. 元数据增强层**

每条向量附加完整元数据，支持多条件过滤检索

python



运行







```
# 元数据结构示例
{
    "document_id": 123,
    "document_name": "公司员工手册.pdf",
    "kb_id": 45,
    "kb_name": "人力资源知识库",
    "uploader_id": 789,
    "uploader_name": "张三",
    "department": "人力资源部",
    "tags": ["员工福利", "考勤制度"],
    "created_at": "2024-05-20T10:30:00Z",
    "page_number": 15,
    "heading": "第三章 考勤管理",
    "chunk_index": "3.2",
    "file_type": "pdf"
}
```

**4. 双路检索层**

实现向量检索 + BM25 关键词检索，结果融合加权排序

python



运行







```
# backend/app/services/rag/retriever.py
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain.retrievers import EnsembleRetriever
from langchain_community.embeddings import OpenAIEmbeddings

class HybridRetriever:
    def __init__(self, vector_store: Chroma):
        self.vector_store = vector_store
        
        # 初始化向量检索器
        self.vector_retriever = vector_store.as_retriever(
            search_kwargs={"k": 10}
        )
        
        # 注意：BM25Retriever需要预先加载所有文档
        # 实际项目中应在服务启动时或文档更新时重新初始化
    
    def initialize_bm25(self, documents: list[dict]):
        """初始化BM25检索器"""
        self.bm25_retriever = BM25Retriever.from_documents(
            [doc["content"] for doc in documents]
        )
        self.bm25_retriever.k = 10
        
        # 初始化混合检索器
        self.ensemble_retriever = EnsembleRetriever(
            retrievers=[self.bm25_retriever, self.vector_retriever],
            weights=[0.3, 0.7]  # BM25权重0.3，向量权重0.7
        )
    
    def retrieve(self, query: str, filters: dict = None, top_k: int = 5) -> list[dict]:
        """执行混合检索，返回前top_k个结果"""
        # 应用过滤条件
        if filters:
            self.vector_retriever.search_kwargs["filter"] = filters
        
        # 执行检索
        results = self.ensemble_retriever.get_relevant_documents(query)
        
        # 去重
        seen_ids = set()
        unique_results = []
        for doc in results:
            if doc.metadata.get("vector_id") not in seen_ids:
                seen_ids.add(doc.metadata.get("vector_id"))
                unique_results.append(doc)
                if len(unique_results) >= top_k:
                    break
        
        return unique_results
```

**5. 重排序 Rerank 层**

使用 Cohere Rerank 或 BGE Rerank 模型进行二次排序

python



运行







```
# backend/app/services/rag/reranker.py
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CohereRerank
import os

class Reranker:
    def __init__(self, base_retriever):
        self.compressor = CohereRerank(
            cohere_api_key=os.getenv("COHERE_API_KEY"),
            model="rerank-english-v3.0",
            top_n=5
        )
        self.compression_retriever = ContextualCompressionRetriever(
            base_compressor=self.compressor,
            base_retriever=base_retriever
        )
    
    def rerank(self, query: str, documents: list[dict]) -> list[dict]:
        """对检索结果进行重排序"""
        return self.compression_retriever.get_relevant_documents(query)
```

**6. 上下文拼接层**

实现父子块检索机制，保证上下文完整性

python



运行







```
# backend/app/services/rag/context_builder.py
from sqlalchemy.orm import Session
from backend.app.models import DocumentChunk

class ContextBuilder:
    def __init__(self, db: Session):
        self.db = db
    
    def build_context(self, retrieved_chunks: list[dict]) -> tuple[str, list[dict]]:
        """构建完整上下文，包含父子块信息和引用来源"""
        context_parts = []
        sources = []
        
        for i, chunk in enumerate(retrieved_chunks):
            chunk_metadata = chunk.metadata
            parent_chunk_id = chunk_metadata.get("parent_chunk_id")
            
            # 如果有父块，获取父块内容作为上下文
            if parent_chunk_id is not None:
                parent_chunk = self.db.query(DocumentChunk).filter(
                    DocumentChunk.id == parent_chunk_id
                ).first()
                
                if parent_chunk:
                    context_parts.append(f"【上下文：{parent_chunk.content[:200]}...】")
            
            # 添加当前块内容和引用编号
            context_parts.append(f"[{i+1}] {chunk.page_content}")
            
            # 记录来源信息
            sources.append({
                "id": i+1,
                "document_name": chunk_metadata.get("document_name", "未知文档"),
                "page_number": chunk_metadata.get("page_number", "未知"),
                "chunk_index": chunk_metadata.get("chunk_index", "未知"),
                "document_id": chunk_metadata.get("document_id")
            })
            
            context_parts.append("---")
        
        return "\n\n".join(context_parts), sources
```

**7. 引用溯源层**

自动标注引用来源，支持点击跳转

python



运行







```
# backend/app/services/rag/answer_generator.py
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate

class AnswerGenerator:
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        self.llm = ChatOpenAI(model_name=model_name, temperature=0)
        
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""
            基于以下上下文回答用户的问题。如果上下文没有相关信息，请明确说明不知道。
            回答时请在引用的内容后面标注对应的来源编号，例如：[1]
            
            上下文：
            {context}
            
            问题：{question}
            
            回答：
            """
        )
    
    def generate_answer(self, query: str, context: str, sources: list[dict]) -> dict:
        """生成带引用的回答"""
        # 生成回答
        chain = self.prompt_template | self.llm
        answer = chain.invoke({"context": context, "question": query})
        
        return {
            "answer": answer.content,
            "sources": sources
        }
```

#### 5.1.2 RAG 功能落地实现

- **私有知识库管理**：支持创建、编辑、删除知识库，设置访问权限
- **批量文档导入**：支持多文件同时上传，后台异步处理
- **增量更新**：新增 / 修改文档时只更新对应向量，无需全量重建
- **检索效果评估**：记录检索日志，统计召回率和准确率
- **RAG 开关**：前端可切换 "纯大模型" 和 "知识库增强" 模式

### 5.2 Agent 智能体系统

#### 5.2.1 智能体能力设计

**1. 角色自定义**

支持配置智能体身份、系统提示词、模型参数和可用工具

python



运行







```
# backend/app/models/agent.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class AgentConfig(BaseModel):
    name: str = Field(..., description="智能体名称")
    description: Optional[str] = Field(None, description="智能体描述")
    system_prompt: str = Field(..., description="系统提示词")
    model_name: str = Field(default="gpt-3.5-turbo", description="模型名称")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=2048, description="最大Token数")
    tools: List[str] = Field(default_factory=list, description="可用工具列表")
```

**2. 工具市场**

内置企业高频工具，支持自定义扩展

python



运行







```
# backend/app/services/agent/tools/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

class ToolResult(BaseModel):
    success: bool = Field(..., description="是否执行成功")
    content: Any = Field(..., description="执行结果内容")
    error: Optional[str] = Field(None, description="错误信息")

class BaseTool(ABC):
    name: str
    description: str
    parameters: Dict[str, Any]
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行工具"""
        pass

# backend/app/services/agent/tools/knowledge_base.py
class KnowledgeBaseTool(BaseTool):
    name = "knowledge_base_search"
    description = "搜索企业私有知识库中的信息"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "要搜索的问题"
            },
            "kb_id": {
                "type": "integer",
                "description": "知识库ID，可选，不指定则搜索所有有权限的知识库"
            }
        },
        "required": ["query"]
    }
    
    def __init__(self, rag_service):
        self.rag_service = rag_service
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        try:
            query = parameters["query"]
            kb_id = parameters.get("kb_id")
            
            results = await self.rag_service.retrieve(query, kb_id=kb_id)
            
            return ToolResult(
                success=True,
                content={
                    "results": [
                        {
                            "content": r.page_content,
                            "source": r.metadata.get("document_name")
                        } for r in results
                    ]
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content=None,
                error=str(e)
            )
```

**3. 自主规划 & 工具调用链路**

python



运行







```
# backend/app/services/agent/agent_service.py
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import List, Dict, Any
from .tools.base import BaseTool

class AgentService:
    def __init__(self):
        self.tool_registry = {}
    
    def register_tool(self, tool: BaseTool):
        """注册工具"""
        self.tool_registry[tool.name] = tool
    
    async def run_agent(
        self,
        agent_config: Dict[str, Any],
        user_query: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """运行智能体"""
        # 初始化LLM
        llm = ChatOpenAI(
            model=agent_config["model_name"],
            temperature=agent_config["temperature"],
            max_tokens=agent_config["max_tokens"]
        )
        
        # 获取可用工具
        tools = [self.tool_registry[name] for name in agent_config["tools"] if name in self.tool_registry]
        
        # 创建提示模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", agent_config["system_prompt"]),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # 创建Agent
        agent = create_openai_tools_agent(llm, tools, prompt)
        
        # 创建Agent执行器
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
            max_iterations=5  # 防止无限循环
        )
        
        # 执行Agent
        result = await agent_executor.ainvoke({
            "input": user_query,
            "chat_history": chat_history or []
        })
        
        return {
            "answer": result["output"],
            "intermediate_steps": [
                {
                    "tool_name": step[0].tool,
                    "tool_input": step[0].tool_input,
                    "tool_output": step[1]
                } for step in result["intermediate_steps"]
            ]
        }
```

**4. 异常兜底**

- 工具调用失败自动重试（最多 3 次）
- 工具权限拦截（检查用户是否有权限使用该工具）
- Token 超限保护（自动截断上下文）
- 超时处理（单工具调用超时时间 30 秒）

#### 5.2.2 前端交互实现

- **思考过程可视化**：实时展示 "正在分析问题"、"调用知识库检索" 等状态
- **工具调用记录**：展开 / 折叠查看每一步工具的入参和返回结果
- **任务中断**：支持随时终止当前 Agent 执行
- **历史对话**：保存完整的对话历史，包括工具调用过程

### 5.3 LangGraph 多智能体工作流

#### 5.3.1 多智能体角色划分

**1. 调度中心 Agent（总指挥）**

- 职责：接收用户总任务，拆解为多个子任务，分配给对应专业智能体
- 系统提示词："你是一个任务调度专家。请将用户的复杂任务拆解为多个明确的子任务，并分配给对应的专业智能体。可用智能体：知识库专家 (负责查询内部资料)、搜索专家 (负责联网查询)、执行专家 (负责代码和数据计算)、审核专家 (负责最终结果审核)。"

**2. 知识库 Agent**

- 职责：专门负责调用增强 RAG 系统，查询企业内部资料
- 工具：私有知识库检索工具

**3. 检索 / 外部信息 Agent**

- 职责：负责联网搜索、获取外部数据
- 工具：Tavily 搜索工具

**4. 执行 Agent**

- 职责：负责代码运行、数据计算、SQL 查询等落地执行
- 工具：Python 代码解释器、SQL 查询工具、计算器工具

**5. 审核 Agent**

- 职责：汇总所有子智能体结果，校对、润色、格式统一，输出最终答案
- 系统提示词："你是一个结果审核专家。请汇总所有子任务的结果，检查准确性和完整性，统一格式，生成清晰易懂的最终回答。"

#### 5.3.2 LangGraph 工作流拓扑

python



运行







```
# backend/app/services/workflow/graph_builder.py
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
import redis

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    task: str
    subtasks: list[dict]
    results: dict
    current_step: str
    status: str
    error: str

class WorkflowBuilder:
    def __init__(self, redis_url: str):
        self.redis = redis.Redis.from_url(redis_url)
        self.checkpointer = RedisSaver(self.redis)
    
    def build_standard_workflow(self):
        """构建标准多智能体工作流"""
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("scheduler", self.scheduler_node)
        workflow.add_node("knowledge_agent", self.knowledge_agent_node)
        workflow.add_node("search_agent", self.search_agent_node)
        workflow.add_node("execution_agent", self.execution_agent_node)
        workflow.add_node("reviewer", self.reviewer_node)
        
        # 设置入口点
        workflow.set_entry_point("scheduler")
        
        # 添加条件边
        workflow.add_conditional_edges(
            "scheduler",
            self.route_after_scheduler,
            {
                "knowledge": "knowledge_agent",
                "search": "search_agent",
                "execution": "execution_agent",
                "review": "reviewer",
                "end": END
            }
        )
        
        # 添加普通边
        workflow.add_edge("knowledge_agent", "reviewer")
        workflow.add_edge("search_agent", "reviewer")
        workflow.add_edge("execution_agent", "reviewer")
        workflow.add_edge("reviewer", END)
        
        # 编译工作流
        return workflow.compile(checkpointer=self.checkpointer)
    
    def scheduler_node(self, state: AgentState) -> AgentState:
        """调度中心节点"""
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        
        prompt = f"""
        请将以下任务拆解为子任务，并分配给对应的智能体：
        任务：{state['task']}
        
        可用智能体：
        - knowledge：查询企业内部知识库
        - search：联网搜索外部信息
        - execution：执行代码、计算或SQL查询
        - review：汇总和审核结果
        
        请输出JSON格式的子任务列表，例如：
        [
            {{"agent": "knowledge", "task": "查询公司员工年假政策"}},
            {{"agent": "search", "task": "查询2024年法定年假天数"}}
        ]
        """
        
        response = llm.invoke(prompt)
        
        import json
        try:
            subtasks = json.loads(response.content)
            state["subtasks"] = subtasks
            state["current_step"] = "scheduler_completed"
            state["status"] = "running"
        except Exception as e:
            state["error"] = f"任务拆解失败: {str(e)}"
            state["status"] = "failed"
        
        return state
    
    def knowledge_agent_node(self, state: AgentState) -> AgentState:
        """知识库Agent节点"""
        # 实现知识库查询逻辑
        knowledge_task = next((t for t in state["subtasks"] if t["agent"] == "knowledge"), None)
        if knowledge_task:
            # 调用RAG服务查询
            # results = await rag_service.retrieve(knowledge_task["task"])
            state["results"]["knowledge"] = "知识库查询结果"
        
        return state
    
    def search_agent_node(self, state: AgentState) -> AgentState:
        """搜索Agent节点"""
        # 实现联网搜索逻辑
        search_task = next((t for t in state["subtasks"] if t["agent"] == "search"), None)
        if search_task:
            # 调用Tavily搜索
            # results = tavily.search(search_task["task"])
            state["results"]["search"] = "联网搜索结果"
        
        return state
    
    def execution_agent_node(self, state: AgentState) -> AgentState:
        """执行Agent节点"""
        # 实现代码执行逻辑
        execution_task = next((t for t in state["subtasks"] if t["agent"] == "execution"), None)
        if execution_task:
            # 调用PythonREPL执行
            # results = python_repl.run(execution_task["task"])
            state["results"]["execution"] = "代码执行结果"
        
        return state
    
    def reviewer_node(self, state: AgentState) -> AgentState:
        """审核节点"""
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        
        prompt = f"""
        请汇总以下所有子任务的结果，生成最终回答：
        
        原始任务：{state['task']}
        
        子任务结果：
        {state['results']}
        
        请生成清晰、准确、格式统一的最终回答。
        """
        
        response = llm.invoke(prompt)
        
        state["results"]["final"] = response.content
        state["status"] = "completed"
        
        return state
    
    def route_after_scheduler(self, state: AgentState) -> str:
        """调度后的路由逻辑"""
        if state["status"] == "failed":
            return "end"
        
        # 根据拆解的子任务决定下一步
        if any(t["agent"] == "knowledge" for t in state["subtasks"]):
            return "knowledge"
        elif any(t["agent"] == "search" for t in state["subtasks"]):
            return "search"
        elif any(t["agent"] == "execution" for t in state["subtasks"]):
            return "execution"
        else:
            return "review"
```

#### 5.3.3 核心技术特性实现

**1. 全局状态 State 管理**

- 整个工作流共享同一个状态对象
- 状态包含：消息历史、任务信息、子任务列表、中间结果、当前步骤、状态
- 所有节点只能读取和修改自己负责的状态字段

**2. 持久化状态**

- 使用 RedisSaver 将工作流状态持久化到 Redis
- 支持服务重启后恢复未完成的工作流
- 每个工作流执行实例有唯一的 thread_id

**3. 流程追踪**

- 记录每个节点的执行时间、输入输出、状态变化
- 支持全链路日志查询
- 集成 LangSmith 进行可视化追踪

**4. 人工介入节点**

python



运行







```
def human_intervention_node(state: AgentState) -> AgentState:
    """人工介入节点"""
    # 将工作流状态设置为等待人工确认
    state["status"] = "waiting_for_human"
    # 暂停工作流执行
    return state

# 在工作流中添加条件边，支持人工确认后继续
workflow.add_conditional_edges(
    "human_intervention",
    lambda state: "continue" if state.get("human_approved") else "end",
    {
        "continue": "next_node",
        "end": END
    }
)
```

#### 5.3.4 前端可视化展示

- 使用 `vue-flow` 库实现工作流拓扑图可视化
- 节点状态用不同颜色标识：灰色 (等待)、蓝色 (执行中)、绿色 (完成)、红色 (失败)
- 点击节点可查看详细执行日志和输入输出
- 支持放大、缩小、拖拽拓扑图

------

## 六、完整功能模块实现

### 6.1 账户 & 权限系统

**核心功能**：

- 基于 JWT 的登录认证
- RBAC 角色权限管理
- 多租户数据隔离
- 细粒度资源权限控制（知识库、智能体、工作流）

**权限设计**：

- 超级管理员：拥有所有权限
- 租户管理员：管理本租户的用户、角色和资源
- 普通用户：使用有权限的资源
- 只读用户：只能查看资源，不能修改

### 6.2 增强 RAG 知识库

**核心功能**：

- 知识库创建、编辑、删除、权限设置
- 多格式文档上传、预览、下载
- 文档解析进度实时显示
- 向量库全量 / 增量更新
- 检索效果统计和优化建议

### 6.3 单 Agent 智能体中心

**核心功能**：

- 智能体创建、编辑、删除、复制
- 系统提示词在线编辑（Monaco Editor）
- 工具启用 / 禁用配置
- 模型参数调整（温度、最大 Token 等）
- 智能体对话测试和历史记录

### 6.4 LangGraph 多智能体工作流

**核心功能**：

- 工作流模板管理（创建、编辑、删除、发布）
- 工作流参数配置
- 手动执行工作流并传入参数
- 工作流执行状态实时监控
- 执行历史记录和结果查看
- 人工介入节点处理

### 6.5 全局流式交互体验

**核心功能**：

- 大模型回答逐字流式输出
- Markdown、代码块、表格自动渲染
- 工具调用过程实时推送
- 工作流节点状态实时更新
- 支持中断和重新执行

### 6.6 系统监控与运维

**核心功能**：

- Token 消耗统计（按用户、按模型、按时间）
- 接口调用量和响应时间统计
- 错误日志收集和查询
- 系统健康状态监控
- 用户活跃度统计

------

## 七、Vue 前端关键技术落地要点

### 7.1 流式输出 SSE 封装

typescript



运行







```
// frontend/src/utils/sse.ts
import { ref, Ref, onUnmounted } from 'vue';

interface SSEOptions {
  url: string;
  headers?: Record<string, string>;
  onMessage?: (data: any) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private url: string;
  private headers: Record<string, string>;
  private isConnected: Ref<boolean> = ref(false);
  private data: Ref<string> = ref('');
  private error: Ref<Event | null> = ref(null);
  
  constructor(options: SSEOptions) {
    this.url = options.url;
    this.headers = options.headers || {};
  }
  
  connect(): void {
    if (this.eventSource) {
      this.disconnect();
    }
    
    // 构建带参数的URL
    const urlWithParams = new URL(this.url, window.location.origin);
    // 添加认证token
    const token = localStorage.getItem('token');
    if (token) {
      urlWithParams.searchParams.append('token', token);
    }
    
    this.eventSource = new EventSource(urlWithParams.toString());
    
    this.eventSource.onopen = () => {
      this.isConnected.value = true;
      this.error.value = null;
    };
    
    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.data.value += data.content || '';
      } catch (e) {
        // 处理纯文本数据
        this.data.value += event.data;
      }
    };
    
    this.eventSource.onerror = (error) => {
      this.isConnected.value = false;
      this.error.value = error;
      // 自动重连（最多3次）
      setTimeout(() => {
        if (!this.isConnected.value) {
          this.connect();
        }
      }, 3000);
    };
  }
  
  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      this.isConnected.value = false;
    }
  }
  
  getData(): Ref<string> {
    return this.data;
  }
  
  getError(): Ref<Event | null> {
    return this.error;
  }
  
  getConnectionStatus(): Ref<boolean> {
    return this.isConnected;
  }
}

// 组合式API封装
export function useSSE(url: string, headers?: Record<string, string>) {
  const client = new SSEClient({ url, headers });
  
  onUnmounted(() => {
    client.disconnect();
  });
  
  return {
    connect: client.connect.bind(client),
    disconnect: client.disconnect.bind(client),
    data: client.getData(),
    error: client.getError(),
    isConnected: client.getConnectionStatus()
  };
}
```

### 7.2 Pinia 模块化状态设计

typescript



运行







```
// frontend/src/stores/user.ts
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { login as apiLogin, logout as apiLogout, getUserInfo } from '@/api/user';

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('token'));
  const userInfo = ref<any>(null);
  const permissions = ref<string[]>([]);
  
  const isLoggedIn = computed(() => !!token.value);
  
  async function login(username: string, password: string) {
    const res = await apiLogin({ username, password });
    token.value = res.token;
    localStorage.setItem('token', res.token);
    await fetchUserInfo();
  }
  
  async function fetchUserInfo() {
    const res = await getUserInfo();
    userInfo.value = res.user;
    permissions.value = res.permissions;
  }
  
  function logout() {
    apiLogout();
    token.value = null;
    userInfo.value = null;
    permissions.value = [];
    localStorage.removeItem('token');
  }
  
  function hasPermission(permission: string): boolean {
    return permissions.value.includes(permission) || permissions.value.includes('*');
  }
  
  return {
    token,
    userInfo,
    permissions,
    isLoggedIn,
    login,
    fetchUserInfo,
    logout,
    hasPermission
  };
});

// frontend/src/stores/rag.ts
import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getKnowledgeBases, getDocuments, searchKnowledgeBase } from '@/api/rag';

export const useRagStore = defineStore('rag', () => {
  const knowledgeBases = ref<any[]>([]);
  const currentKb = ref<any>(null);
  const documents = ref<any[]>([]);
  const searchResults = ref<any[]>([]);
  const isLoading = ref(false);
  
  async function fetchKnowledgeBases() {
    isLoading.value = true;
    try {
      const res = await getKnowledgeBases();
      knowledgeBases.value = res.data;
    } finally {
      isLoading.value = false;
    }
  }
  
  async function fetchDocuments(kbId: number) {
    isLoading.value = true;
    try {
      const res = await getDocuments(kbId);
      documents.value = res.data;
    } finally {
      isLoading.value = false;
    }
  }
  
  async function search(kbId: number, query: string) {
    isLoading.value = true;
    try {
      const res = await searchKnowledgeBase(kbId, query);
      searchResults.value = res.data;
    } finally {
      isLoading.value = false;
    }
  }
  
  return {
    knowledgeBases,
    currentKb,
    documents,
    searchResults,
    isLoading,
    fetchKnowledgeBases,
    fetchDocuments,
    search
  };
});

// 其他Store同理：agentStore.ts, graphStore.ts
```

### 7.3 组件拆分规范

**通用组件目录结构**：

plaintext









```
src/components/
├── common/
│   ├── BaseButton.vue
│   ├── BaseCard.vue
│   ├── BaseDialog.vue
│   ├── BaseDrawer.vue
│   ├── BaseTable.vue
│   └── BaseUpload.vue
├── chat/
│   ├── ChatMessage.vue
│   ├── ChatInput.vue
│   ├── ChatList.vue
│   ├── StreamingText.vue
│   └── ToolCallPanel.vue
├── knowledge/
│   ├── DocumentUploader.vue
│   ├── DocumentList.vue
│   ├── DocumentPreview.vue
│   └── KnowledgeBaseCard.vue
├── agent/
│   ├── AgentCard.vue
│   ├── AgentConfigForm.vue
│   ├── AgentChat.vue
│   └── ToolSelector.vue
└── workflow/
    ├── WorkflowCanvas.vue
    ├── WorkflowNode.vue
    ├── WorkflowEdge.vue
    └── ExecutionLogPanel.vue
```

### 7.4 路由设计

typescript



运行







```
// frontend/src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router';
import { useUserStore } from '@/stores/user';

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/views/Layout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue')
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/knowledge/Index.vue'),
        children: [
          {
            path: '',
            name: 'KnowledgeList',
            component: () => import('@/views/knowledge/List.vue')
          },
          {
            path: ':id',
            name: 'KnowledgeDetail',
            component: () => import('@/views/knowledge/Detail.vue')
          }
        ]
      },
      {
        path: 'agents',
        name: 'Agents',
        component: () => import('@/views/agents/Index.vue')
      },
      {
        path: 'workflows',
        name: 'Workflows',
        component: () => import('@/views/workflows/Index.vue')
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Settings.vue')
      }
    ]
  }
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
});

// 路由守卫
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore();
  
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } });
    return;
  }
  
  if (to.name === 'Login' && userStore.isLoggedIn) {
    next({ name: 'Dashboard' });
    return;
  }
  
  // 加载用户信息
  if (userStore.isLoggedIn && !userStore.userInfo) {
    try {
      await userStore.fetchUserInfo();
    } catch (e) {
      userStore.logout();
      next({ name: 'Login' });
      return;
    }
  }
  
  next();
});

export default router;
```

### 7.5 性能优化方案

**1. 虚拟滚动**

- 使用 `vue-virtual-scroller` 实现大文档和聊天记录虚拟滚动
- 只渲染可视区域内的元素，大幅提升性能

**2. 懒加载**

- 路由懒加载：使用 `import()` 动态导入组件
- 组件懒加载：使用 `defineAsyncComponent` 延迟加载非关键组件
- 图片懒加载：使用 `v-lazy` 指令

**3. SSE 连接管理**

- 页面销毁时自动关闭 SSE 连接
- 全局连接池管理，避免重复创建连接
- 连接超时自动重连

**4. 状态优化**

- 避免在 Pinia 中存储大量非必要数据
- 使用 `shallowRef` 和 `shallowReactive` 减少响应式开销
- 及时清理过期状态

------

## 八、API 接口文档

### 8.1 接口规范

- 基础 URL：`/api/v1`
- 请求方法：GET、POST、PUT、DELETE
- 请求格式：JSON
- 响应格式：JSON
- 认证方式：Bearer Token（在请求头中添加 `Authorization: Bearer {token}`）

**统一响应格式**：

json









```
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

**错误响应格式**：

json









```
{
  "code": 400,
  "message": "参数错误",
  "data": null,
  "error": "详细错误信息"
}
```

### 8.2 用户认证接口

#### 登录

- **请求路径**：`/auth/login`

- **请求方法**：POST

- **请求参数**：

  表格

  

  

  

  |  参数名  |  类型  | 是否必填 |  说明  |
  | :------: | :----: | :------: | :----: |
  | username | string |    是    | 用户名 |
  | password | string |    是    |  密码  |

- **响应参数**：

  表格

  

  

  

  |   参数名   |  类型   |     说明      |
  | :--------: | :-----: | :-----------: |
  |   token    | string  |   JWT 令牌    |
  | expires_in | integer | 过期时间 (秒) |

- **成功示例**：

json









```
{
  "code": 200,
  "message": "success",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 86400
  }
}
```

- **失败示例**：

json









```
{
  "code": 401,
  "message": "用户名或密码错误",
  "data": null
}
```

#### 获取用户信息

- **请求路径**：`/auth/me`

- **请求方法**：GET

- **请求头**：`Authorization: Bearer {token}`

- 响应参数

  ：

  表格

  

  

  

  |   参数名    |  类型   |   说明   |
  | :---------: | :-----: | :------: |
  |     id      | integer | 用户 ID  |
  |  username   | string  |  用户名  |
  |    email    | string  |   邮箱   |
  |    role     | object  | 角色信息 |
  | permissions |  array  | 权限列表 |

### 8.3 知识库管理接口

#### 创建知识库

- **请求路径**：`/knowledge-bases`

- **请求方法**：POST

- 请求参数

  ：

  表格

  

  

  

  |     参数名      |  类型   | 是否必填 |    说明    |
  | :-------------: | :-----: | :------: | :--------: |
  |      name       | string  |    是    | 知识库名称 |
  |   description   | string  |    否    | 知识库描述 |
  |    is_public    | boolean |    否    |  是否公开  |
  | embedding_model | string  |    否    |  嵌入模型  |

#### 上传文档

- **请求路径**：`/knowledge-bases/{kb_id}/documents`

- **请求方法**：POST

- **请求头**：`Content-Type: multipart/form-data`

- 请求参数

  ：

  表格

  

  

  

  | 参数名 |  类型  | 是否必填 |      说明      |
  | :----: | :----: | :------: | :------------: |
  |  file  |  file  |    是    |    文档文件    |
  |  tags  | string |    否    | 标签，逗号分隔 |

#### 检索知识库

- **请求路径**：`/knowledge-bases/{kb_id}/search`

- **请求方法**：POST

- 请求参数

  ：

  表格

  

  

  

  | 参数名  |  类型   | 是否必填 |     说明     |
  | :-----: | :-----: | :------: | :----------: |
  |  query  | string  |    是    |   检索问题   |
  |  top_k  | integer |    否    | 返回结果数量 |
  | filters | object  |    否    |   过滤条件   |

### 8.4 智能体管理接口

#### 创建智能体

- **请求路径**：`/agents`
- **请求方法**：POST

### 8.5 工作流管理接口

- `GET /workflows`：工作流列表
- `POST /workflows/{id}/execute`：执行工作流
- `GET /workflows/{id}/executions`：执行历史

### 8.6 流式交互接口

- `POST /knowledge-bases/{kb_id}/chat`：SSE 流式问答（use_rag 切换）
- `POST /agents/{id}/chat`：Agent 流式对话

### 8.7 系统监控接口

- `GET /monitor/user-activity`：DAU/WAU/MAU

### 8.8 租户与审计接口

- `CRUD /tenants`：租户管理
- `GET /audit-logs`：审计日志

## 九、分阶段开发计划

一期 MVP 已完成；二期 P0/P1/P2 已全部落地（测试、Monaco、预览、工作流编辑、租户、审计、CI）。

## 十、测试指南

```bash
cd backend && pytest tests/ -q
cd frontend && npm run lint && npm run build
```

## 十一、部署指南

```bash
docker compose up -d
cd backend && alembic upgrade head && arq app.worker.WorkerSettings
```