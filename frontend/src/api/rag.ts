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
  type?: 'content' | 'citation' | 'done' | 'error';
  content?: string;
  sources?: CitationSource[];
  message?: string;
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

/** 构建流式问答 SSE URL（文档 7.1 EventSource） */
export function buildChatStreamUrl(
  kbId: number,
  query: string,
  sessionId?: string,
): string {
  const url = new URL(`${baseURL}/knowledge-bases/${kbId}/chat/stream`, window.location.origin);
  url.searchParams.set('query', query);
  if (sessionId) {
    url.searchParams.set('session_id', sessionId);
  }
  const token = localStorage.getItem('token');
  if (token) {
    url.searchParams.set('token', token);
  }
  return url.pathname + url.search;
}
