/**
 * 大模型定义（已迁移至统一模型中心 API）。
 * 本文件保留类型与工具函数 re-export，供尚未迁移的模块使用。
 */
export type {
  AIModelEntity as ModelDefinition,
  LegacyModelDefinition,
  ParameterRule,
} from '@/api/models';

export {
  getAvailableModels,
  getModelLabel,
  getModelMaxTokensFromEntity as getModelMaxTokens,
  PROVIDER_LABELS,
  toAgentModelDefinition,
  validateAgentModelParamsFromEntity as validateAgentModelParams,
} from '@/api/models';

/** @deprecated 请使用 getAvailableModels() 动态获取 */
export const LLM_MODEL_DEFINITIONS: never[] = [];
export const LLM_MODEL_MAP = new Map<string, never>();
export const LLM_PROVIDER_ORDER = ['openai', 'tongyi', 'doubao', 'minimax'] as const;

/** @deprecated */
export function getModelsByProvider(): Record<string, never[]> {
  return {};
}
