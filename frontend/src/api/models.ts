import request from './request';

/** 参数规则 */
export interface ParameterRule {
  min: number;
  max: number;
  default: number;
}

/** 标准化模型实体 */
export interface AIModelEntity {
  model: string;
  provider: string;
  label: Record<string, string>;
  model_type: 'llm' | 'text-embedding' | 'rerank';
  context_size: number;
  features: string[];
  parameter_rules: Record<string, ParameterRule>;
  status: 'active' | 'deprecated';
  fetch_from: 'predefined' | 'remote';
  provider_label?: string;
}

/** 厂商信息 */
export interface ModelProviderInfo {
  provider: string;
  label: Record<string, string>;
  default_base_url: string;
  base_url_placeholder: string;
  category: 'llm' | 'tool';
  description: string;
}

/** 拉取厂商模型响应 */
export interface ProviderModelListResponse {
  provider: string;
  fetch_from: string;
  models: AIModelEntity[];
  warning?: string | null;
  is_valid?: boolean | null;
  validate_message?: string | null;
}

/** 可用模型汇总响应 */
export interface AvailableModelsResponse {
  models: AIModelEntity[];
  providers: string[];
  fetch_from: string;
  warning?: string | null;
}

/** 兼容旧 Agent 模型定义 */
export interface LegacyModelDefinition {
  name: string;
  label: string;
  provider: string;
  provider_label: string;
  max_tokens: number;
  default_temperature: number;
  default_top_p: number;
  features?: string[];
  parameter_rules?: Record<string, ParameterRule>;
}

export const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  tongyi: '通义千问',
  doubao: '豆包',
  minimax: 'MiniMax',
};

/** 获取支持的模型厂商列表 */
export function listModelProviders(category?: string): Promise<ModelProviderInfo[]> {
  return request.get('/model-providers', { params: category ? { category } : undefined });
}

/** 拉取指定厂商可用模型 */
export function fetchProviderModels(
  provider: string,
  payload: {
    api_key?: string;
    base_url?: string;
    model_type?: string;
  },
): Promise<ProviderModelListResponse> {
  return request.post(`/model-providers/${provider}/models`, payload);
}

/** 获取当前用户可用模型 */
export function getAvailableModels(modelType = 'llm'): Promise<AvailableModelsResponse> {
  return request.get('/models/available', { params: { model_type: modelType } });
}

/** 从 AIModelEntity 获取显示名 */
export function getModelLabel(entity: AIModelEntity): string {
  return entity.label?.zh_Hans || entity.label?.en_US || entity.model;
}

/** 获取模型 max_tokens 上限 */
export function getModelMaxTokensFromEntity(entity: AIModelEntity): number {
  const rule = entity.parameter_rules?.max_tokens;
  return rule ? rule.max : entity.context_size;
}

/** 校验智能体模型参数 */
export function validateAgentModelParamsFromEntity(
  entity: AIModelEntity,
  temperature: number,
  topP: number,
  maxTokens: number,
): string | null {
  const tempRule = entity.parameter_rules?.temperature ?? { min: 0, max: 2, default: 0.7 };
  const topPRule = entity.parameter_rules?.top_p ?? { min: 0, max: 1, default: 1 };
  const maxRule = entity.parameter_rules?.max_tokens ?? {
    min: 1,
    max: entity.context_size,
    default: 2048,
  };

  if (temperature < tempRule.min || temperature > tempRule.max) {
    return `温度必须在 ${tempRule.min}-${tempRule.max} 范围内`;
  }
  if (topP < topPRule.min || topP > topPRule.max) {
    return `Top P 必须在 ${topPRule.min}-${topPRule.max} 范围内`;
  }
  if (maxTokens < maxRule.min || maxTokens > maxRule.max) {
    return `最大 Token 必须在 ${maxRule.min}-${maxRule.max} 范围内`;
  }
  return null;
}

/** 将 AIModelEntity 转为 Agent 表单使用的结构 */
export function toAgentModelDefinition(entity: AIModelEntity): LegacyModelDefinition {
  const rules = entity.parameter_rules ?? {};
  return {
    name: entity.model,
    label: getModelLabel(entity),
    provider: entity.provider,
    provider_label: entity.provider_label || PROVIDER_LABELS[entity.provider] || entity.provider,
    max_tokens: getModelMaxTokensFromEntity(entity),
    default_temperature: rules.temperature?.default ?? 0.7,
    default_top_p: rules.top_p?.default ?? 1,
    features: entity.features,
    parameter_rules: entity.parameter_rules,
  };
}
