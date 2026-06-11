import request from './request';
import type { PageParams, PageResult } from '@/types/api';

/** 智能体信息 */
export interface AgentInfo {
  id: number;
  tenant_id: number;
  name: string;
  description?: string | null;
  system_prompt: string;
  model_name: string;
  temperature: number;
  top_p: number;
  max_tokens: number;
  owner_id?: number | null;
  is_public: boolean;
  tools: string[];
  created_at?: string;
  updated_at?: string;
}

/** 创建智能体参数 */
export interface CreateAgentParams {
  name: string;
  description?: string;
  system_prompt: string;
  model_name?: string;
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  is_public?: boolean;
  tools?: string[];
}

/** 更新智能体参数 */
export interface UpdateAgentParams {
  name?: string;
  description?: string;
  system_prompt?: string;
  model_name?: string;
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  is_public?: boolean;
  tools?: string[];
}

/** 内置工具定义 */
export interface ToolDefinition {
  name: string;
  label: string;
  description: string;
}

/** 工具调用步骤 */
export interface ToolCallStep {
  tool_name: string;
  tool_label?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: unknown;
}

/** 流式对话 SSE 消息 */
export interface AgentChatStreamMessage {
  type?: 'thinking' | 'tool_start' | 'tool_end' | 'content' | 'done' | 'error';
  content?: string;
  tool_name?: string;
  tool_label?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: unknown;
  intermediate_step?: ToolCallStep;
  intermediate_steps?: ToolCallStep[];
  session_id?: string;
  message?: string;
}

/** 对话历史条目 */
export interface ChatHistoryItem {
  id: number;
  session_id: string;
  message_type: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
}

/** 智能体对话请求 */
export interface AgentChatRequest {
  query: string;
  session_id?: string;
}

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/** 获取智能体列表 */
export function getAgents(params?: PageParams & { keyword?: string }): Promise<PageResult<AgentInfo>> {
  return request.get('/agents', { params }) as Promise<PageResult<AgentInfo>>;
}

/** 获取智能体详情 */
export function getAgentById(id: number): Promise<AgentInfo> {
  return request.get(`/agents/${id}`) as Promise<AgentInfo>;
}

/** 创建智能体 */
export function createAgent(data: CreateAgentParams): Promise<AgentInfo> {
  return request.post('/agents', data) as Promise<AgentInfo>;
}

/** 更新智能体 */
export function updateAgent(id: number, data: UpdateAgentParams): Promise<AgentInfo> {
  return request.put(`/agents/${id}`, data) as Promise<AgentInfo>;
}

/** 删除智能体 */
export function deleteAgent(id: number): Promise<void> {
  return request.delete(`/agents/${id}`) as Promise<void>;
}

/** 复制智能体 */
export function copyAgent(id: number): Promise<AgentInfo> {
  return request.post(`/agents/${id}/copy`) as Promise<AgentInfo>;
}

/** 获取可用工具列表 */
export function getAvailableTools(): Promise<ToolDefinition[]> {
  return request.get('/agents/tools') as Promise<ToolDefinition[]>;
}

/** 获取对话历史 */
export function getAgentHistory(
  agentId: number,
  params?: { session_id?: string; limit?: number },
): Promise<{ items: ChatHistoryItem[]; total: number }> {
  return request.get(`/agents/${agentId}/history`, { params }) as Promise<{
    items: ChatHistoryItem[];
    total: number;
  }>;
}

/** 删除会话历史 */
export function deleteAgentSession(agentId: number, sessionId: string): Promise<void> {
  return request.delete(`/agents/${agentId}/history/${sessionId}`) as Promise<void>;
}

/** 获取会话列表（从 history 聚合） */
export async function getAgentSessions(
  agentId: number,
): Promise<{ session_id: string; last_message: string; updated_at?: string }[]> {
  const { items } = await getAgentHistory(agentId, { limit: 200 });
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

/** POST 流式对话（fetch + ReadableStream） */
export async function chatAgentStream(
  agentId: number,
  data: AgentChatRequest,
  onMessage: (msg: AgentChatStreamMessage) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = localStorage.getItem('token');

  const response = await fetch(`${baseURL}/agents/${agentId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `请求失败: ${response.status}`);
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
        onMessage(JSON.parse(payload) as AgentChatStreamMessage);
      } catch {
        // 忽略非 JSON 行
      }
    }
  }
}
