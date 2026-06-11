import axios from 'axios';
import { ElMessage } from 'element-plus';
import request from './request';
import type { PageParams, PageResult } from '@/types/api';

/** 知识库信息 */
export interface KnowledgeBaseInfo {
  id: number;
  name: string;
  description?: string | null;
  owner_id?: number | null;
  is_public: boolean;
  embedding_model: string;
  chunk_size?: number;
  chunk_overlap?: number;
  status: number;
  document_count?: number;
  created_at?: string;
  updated_at?: string;
}

/** 创建知识库参数 */
export interface CreateKnowledgeBaseParams {
  name: string;
  description?: string;
  is_public?: boolean;
  embedding_model?: string;
}

/** 更新知识库参数 */
export interface UpdateKnowledgeBaseParams {
  name?: string;
  description?: string;
  is_public?: boolean;
  embedding_model?: string;
  status?: number;
}

/** 文档信息 */
export interface DocumentInfo {
  id: number;
  kb_id: number;
  name: string;
  file_type: string;
  file_size: number;
  status: number;
  total_chunks: number;
  uploader_id?: number | null;
  created_at?: string;
  updated_at?: string;
}

/** 文档解析进度 */
export interface DocumentProgress {
  document_id: number;
  status: number;
  progress: number;
  message?: string;
  total_chunks?: number;
}

/** 检索请求参数 */
export interface SearchKnowledgeParams {
  query: string;
  top_k?: number;
  filters?: Record<string, unknown>;
}

/** 检索结果项 */
export interface SearchResultItem {
  id: number;
  content: string;
  score: number;
  metadata: {
    document_id?: number;
    document_name?: string;
    page_number?: number | string;
    chunk_index?: number;
    [key: string]: unknown;
  };
}

/** 引用来源 */
export interface CitationSource {
  id: number;
  document_id: number;
  document_name: string;
  page_number?: number | string;
  chunk_index?: number;
  content?: string;
}

/** 流式问答 SSE 消息 */
export interface ChatStreamMessage {
  type?: 'token' | 'content' | 'citation' | 'done' | 'error';
  content?: string;
  sources?: CitationSource[];
  message?: string;
  session_id?: string;
}

/** RAG 对话历史条目 */
export interface RagChatHistoryItem {
  id: number;
  session_id: string;
  message_type: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  metadata?: {
    sources?: CitationSource[];
    use_rag?: boolean;
    [key: string]: unknown;
  };
  created_at?: string;
}

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/** 获取知识库列表 */
export function getKnowledgeBases(
  params?: PageParams,
): Promise<PageResult<KnowledgeBaseInfo>> {
  return request.get('/knowledge-bases', { params }) as Promise<
    PageResult<KnowledgeBaseInfo>
  >;
}

/** 获取知识库详情 */
export function getKnowledgeBaseById(id: number): Promise<KnowledgeBaseInfo> {
  return request.get(`/knowledge-bases/${id}`) as Promise<KnowledgeBaseInfo>;
}

/** 创建知识库 */
export function createKnowledgeBase(
  data: CreateKnowledgeBaseParams,
): Promise<KnowledgeBaseInfo> {
  return request.post('/knowledge-bases', data) as Promise<KnowledgeBaseInfo>;
}

/** 更新知识库 */
export function updateKnowledgeBase(
  id: number,
  data: UpdateKnowledgeBaseParams,
): Promise<KnowledgeBaseInfo> {
  return request.put(`/knowledge-bases/${id}`, data) as Promise<KnowledgeBaseInfo>;
}

/** 删除知识库 */
export function deleteKnowledgeBase(id: number): Promise<void> {
  return request.delete(`/knowledge-bases/${id}`) as Promise<void>;
}

/** 获取文档列表 */
export function getDocuments(kbId: number): Promise<DocumentInfo[]> {
  return request.get(`/knowledge-bases/${kbId}/documents`) as Promise<DocumentInfo[]>;
}

/** 上传文档（支持进度回调） */
export async function uploadDocument(
  kbId: number,
  file: File,
  tags?: string,
  onProgress?: (percent: number) => void,
): Promise<DocumentInfo> {
  const formData = new FormData();
  formData.append('file', file);
  if (tags) {
    formData.append('tags', tags);
  }

  const token = localStorage.getItem('token');

  try {
    const response = await axios.post(
      `${baseURL}/knowledge-bases/${kbId}/documents`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        onUploadProgress: (event) => {
          if (event.total && onProgress) {
            onProgress(Math.round((event.loaded / event.total) * 100));
          }
        },
      },
    );

    const res = response.data;
    if (res.code === 200) {
      return res.data as DocumentInfo;
    }

    const errorMessage = res.message || '上传失败';
    ElMessage.error(errorMessage);
    throw new Error(errorMessage);
  } catch (error) {
    console.error('[Upload Document Error]', error);
    throw error;
  }
}

/** 删除文档 */
export function deleteDocument(kbId: number, docId: number): Promise<void> {
  return request.delete(`/knowledge-bases/${kbId}/documents/${docId}`) as Promise<void>;
}

/** 查询文档解析进度 */
export function getDocumentProgress(
  kbId: number,
  docId: number,
): Promise<DocumentProgress> {
  return request.get(
    `/knowledge-bases/${kbId}/documents/${docId}/progress`,
  ) as Promise<DocumentProgress>;
}

/** 下载文档 */
export async function downloadDocument(kbId: number, docId: number, filename: string): Promise<void> {
  const token = localStorage.getItem('token');

  try {
    const response = await axios.get(
      `${baseURL}/knowledge-bases/${kbId}/documents/${docId}/download`,
      {
        responseType: 'blob',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      },
    );

    const blob = new Blob([response.data]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('[Download Document Error]', error);
    ElMessage.error('文档下载失败');
    throw error;
  }
}

/** 检索知识库 */
export function searchKnowledgeBase(
  kbId: number,
  data: SearchKnowledgeParams,
): Promise<SearchResultItem[]> {
  return request.post(`/knowledge-bases/${kbId}/search`, data) as Promise<
    SearchResultItem[]
  >;
}

/** 构建流式问答 SSE URL（兼容旧 EventSource 调用，推荐使用 chatKnowledgeStream） */
export function buildChatStreamUrl(
  kbId: number,
  query: string,
  sessionId?: string,
  useRag = true,
): string {
  const url = new URL(`${baseURL}/knowledge-bases/${kbId}/chat/stream`, window.location.origin);
  url.searchParams.set('query', query);
  url.searchParams.set('use_rag', String(useRag));
  if (sessionId) {
    url.searchParams.set('session_id', sessionId);
  }
  const token = localStorage.getItem('token');
  if (token) {
    url.searchParams.set('token', token);
  }
  return url.pathname + url.search;
}

/** 获取 RAG 对话历史 */
export function getRagChatHistory(
  kbId: number,
  params?: { session_id?: string; limit?: number },
): Promise<{ items: RagChatHistoryItem[]; total: number }> {
  return request.get(`/knowledge-bases/${kbId}/history`, { params }) as Promise<{
    items: RagChatHistoryItem[];
    total: number;
  }>;
}

/** 删除 RAG 对话会话 */
export function deleteRagChatSession(kbId: number, sessionId: string): Promise<void> {
  return request.delete(`/knowledge-bases/${kbId}/history/${sessionId}`) as Promise<void>;
}

/** 获取 RAG 会话列表（从历史聚合） */
export async function getRagChatSessions(
  kbId: number,
): Promise<{ session_id: string; last_message: string; updated_at?: string }[]> {
  const { items } = await getRagChatHistory(kbId, { limit: 200 });
  const sessionMap = new Map<string, { session_id: string; last_message: string; updated_at?: string }>();
  for (const item of items) {
    const existing = sessionMap.get(item.session_id);
    if (!existing || (item.created_at && item.created_at > (existing.updated_at || ''))) {
      sessionMap.set(item.session_id, {
        session_id: item.session_id,
        last_message: item.content.slice(0, 80),
        updated_at: item.created_at,
      });
    }
  }
  return Array.from(sessionMap.values()).sort(
    (a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''),
  );
}

/** POST 流式问答（支持 use_rag 模式切换） */
export async function chatKnowledgeStream(
  kbId: number,
  data: {
    query: string;
    use_rag?: boolean;
    top_k?: number;
    session_id?: string;
    filters?: Record<string, unknown>;
  },
  onMessage: (msg: ChatStreamMessage) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = localStorage.getItem('token');
  const response = await fetch(`${baseURL}/knowledge-bases/${kbId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      query: data.query,
      use_rag: data.use_rag ?? true,
      top_k: data.top_k ?? 5,
      session_id: data.session_id,
      filters: data.filters,
    }),
    signal,
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('无法读取流式响应');
  }

  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data:')) {
        continue;
      }
      const payload = trimmed.slice(5).trim();
      if (!payload) {
        continue;
      }
      try {
        onMessage(JSON.parse(payload) as ChatStreamMessage);
      } catch {
        // ignore
      }
    }
  }
}

export interface SearchStats {
  total_queries: number;
  hit_queries: number;
  hit_rate: number;
  avg_latency_ms: number;
  top_documents: { document_id: number; hit_count: number }[];
}

export interface OptimizationHint {
  level: 'info' | 'warning';
  title: string;
  description: string;
}

export function getSearchStats(kbId: number): Promise<SearchStats> {
  return request.get(`/knowledge-bases/${kbId}/search-stats`) as Promise<SearchStats>;
}

/** 从 URL 导入文档 */
export function importUrlDocument(
  kbId: number,
  data: { url: string; title?: string },
): Promise<DocumentInfo> {
  return request.post(`/knowledge-bases/${kbId}/import-url`, data) as Promise<DocumentInfo>;
}

export function getOptimizationHints(
  kbId: number,
): Promise<{ hints: OptimizationHint[]; chunk_size: number; chunk_overlap: number }> {
  return request.get(`/knowledge-bases/${kbId}/optimization-hints`) as Promise<{
    hints: OptimizationHint[];
    chunk_size: number;
    chunk_overlap: number;
  }>;
}
