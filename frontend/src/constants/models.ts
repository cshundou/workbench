/** 大模型定义（与后端 core/constants.py 对齐） */
export interface ModelDefinition {
  name: string;
  label: string;
  provider: string;
  providerLabel: string;
  maxTokens: number;
  defaultTemperature: number;
  defaultTopP: number;
}

/** 按厂商分组的大模型列表 */
export const LLM_MODEL_DEFINITIONS: ModelDefinition[] = [
  { name: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo', provider: 'openai', providerLabel: 'OpenAI', maxTokens: 16385, defaultTemperature: 0.7, defaultTopP: 1.0 },
  { name: 'gpt-4o', label: 'GPT-4o', provider: 'openai', providerLabel: 'OpenAI', maxTokens: 128000, defaultTemperature: 0.7, defaultTopP: 1.0 },
  { name: 'gpt-4-turbo', label: 'GPT-4 Turbo', provider: 'openai', providerLabel: 'OpenAI', maxTokens: 128000, defaultTemperature: 0.7, defaultTopP: 1.0 },
  { name: 'qwen-turbo', label: '通义千问 Turbo', provider: 'tongyi', providerLabel: '通义千问', maxTokens: 8192, defaultTemperature: 0.7, defaultTopP: 1.0 },
  { name: 'qwen-plus', label: '通义千问 Plus', provider: 'tongyi', providerLabel: '通义千问', maxTokens: 32768, defaultTemperature: 0.7, defaultTopP: 1.0 },
  { name: 'qwen-max', label: '通义千问 Max', provider: 'tongyi', providerLabel: '通义千问', maxTokens: 32768, defaultTemperature: 0.7, defaultTopP: 1.0 },
  { name: 'doubao-pro-4k', label: '豆包 Pro 4K', provider: 'doubao', providerLabel: '豆包', maxTokens: 4096, defaultTemperature: 0.7, defaultTopP: 1.0 },
  { name: 'doubao-pro-32k', label: '豆包 Pro 32K', provider: 'doubao', providerLabel: '豆包', maxTokens: 32768, defaultTemperature: 0.7, defaultTopP: 1.0 },
  { name: 'doubao-4', label: '豆包 4', provider: 'doubao', providerLabel: '豆包', maxTokens: 128000, defaultTemperature: 0.7, defaultTopP: 1.0 },
  { name: 'abab6.5s-chat', label: 'abab6.5s-chat', provider: 'minimax', providerLabel: 'MiniMax', maxTokens: 8192, defaultTemperature: 0.7, defaultTopP: 1.0 },
  { name: 'minimax-m3', label: 'MiniMax M3', provider: 'minimax', providerLabel: 'MiniMax', maxTokens: 128000, defaultTemperature: 0.7, defaultTopP: 1.0 },
];

export const LLM_MODEL_MAP = new Map(LLM_MODEL_DEFINITIONS.map((m) => [m.name, m]));

export const LLM_PROVIDER_ORDER = ['openai', 'tongyi', 'doubao', 'minimax'] as const;

export const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  tongyi: '通义千问',
  doubao: '豆包',
  minimax: 'MiniMax',
};

/** 获取模型 max_tokens 上限 */
export function getModelMaxTokens(modelName: string): number {
  return LLM_MODEL_MAP.get(modelName)?.maxTokens ?? 128000;
}

/** 校验智能体模型参数 */
export function validateAgentModelParams(
  modelName: string,
  temperature: number,
  topP: number,
  maxTokens: number,
): string | null {
  if (!LLM_MODEL_MAP.has(modelName)) {
    return `不支持的模型: ${modelName}`;
  }
  if (temperature < 0 || temperature > 2) {
    return '温度必须在 0-2 范围内';
  }
  if (topP < 0 || topP > 1) {
    return 'Top P 必须在 0-1 范围内';
  }
  const limit = getModelMaxTokens(modelName);
  if (maxTokens < 1 || maxTokens > limit) {
    return `最大 Token 必须在 1-${limit} 范围内`;
  }
  return null;
}

/** 按厂商分组 */
export function getModelsByProvider(): Record<string, ModelDefinition[]> {
  const grouped: Record<string, ModelDefinition[]> = {};
  for (const provider of LLM_PROVIDER_ORDER) {
    grouped[provider] = LLM_MODEL_DEFINITIONS.filter((m) => m.provider === provider);
  }
  return grouped;
}
