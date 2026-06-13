import request from './request';

/** API 密钥提供商 */
export type ApiKeyProvider =
  | 'openai'
  | 'tongyi'
  | 'doubao'
  | 'minimax'
  | 'tavily'
  | 'cohere'
  | 'pinecone';

/** 掩码后的 API 密钥信息 */
export interface UserApiKeyInfo {
  id: number;
  provider: ApiKeyProvider;
  api_key_masked: string;
  base_url: string | null;
  model_name: string | null;
  is_default: boolean;
  is_valid: boolean;
  last_validated_at: string | null;
  created_at: string;
  updated_at: string;
}

/** 保存 API 密钥请求 */
export interface UserApiKeyUpsertPayload {
  provider: ApiKeyProvider;
  api_key: string;
  base_url?: string;
  model_name?: string;
  is_default?: boolean;
}

/** 验证结果 */
export interface UserApiKeyValidateResult {
  provider: string;
  is_valid: boolean;
  message: string;
}

/** 密钥配置状态摘要 */
export interface UserApiKeyStatus {
  configured_providers: string[];
  has_llm_key: boolean;
  has_embedding_key: boolean;
  has_cohere_key: boolean;
  has_tavily_key: boolean;
  has_pinecone_key: boolean;
  default_llm_provider: string | null;
  missing_for_rag: string[];
  missing_for_agent: string[];
  rerank_mode: string;
  available_rerank_providers: string[];
}

/** RAG 重排序偏好 */
export interface RerankPreference {
  mode: string;
  available_llm_providers: string[];
  has_cohere_key: boolean;
}

/** 重排序模式 */
export type RerankMode =
  | 'auto'
  | 'cohere'
  | 'off'
  | 'openai'
  | 'tongyi'
  | 'doubao'
  | 'minimax';

/** 可用于 Embedding 重排序的大模型提供商 */
export type RerankLlmProvider = Extract<
  ApiKeyProvider,
  'openai' | 'tongyi' | 'doubao' | 'minimax'
>;

/** 获取当前用户的 API 密钥列表 */
export function listApiKeys(): Promise<UserApiKeyInfo[]> {
  return request.get('/user/api-keys');
}

/** 获取 API 密钥配置状态 */
export function getApiKeyStatus(): Promise<UserApiKeyStatus> {
  return request.get('/user/api-keys/status');
}

/** 保存或更新 API 密钥 */
export function upsertApiKey(data: UserApiKeyUpsertPayload): Promise<UserApiKeyInfo> {
  return request.post('/user/api-keys', data);
}

/** 删除 API 密钥 */
export function deleteApiKey(provider: ApiKeyProvider): Promise<void> {
  return request.delete(`/user/api-keys/${provider}`);
}

/** 验证 API 密钥 */
export function validateApiKey(
  provider: ApiKeyProvider,
  apiKey?: string,
): Promise<UserApiKeyValidateResult> {
  return request.post(`/user/api-keys/${provider}/validate`, apiKey ? { api_key: apiKey } : {});
}

/** 获取 RAG 重排序偏好 */
export function getRerankPreference(): Promise<RerankPreference> {
  return request.get('/user/api-keys/rerank-preference');
}

/** 保存 RAG 重排序偏好 */
export function saveRerankPreference(mode: RerankMode): Promise<RerankPreference> {
  return request.put('/user/api-keys/rerank-preference', { mode });
}
