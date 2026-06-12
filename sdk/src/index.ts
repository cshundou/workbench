/**
 * Agent Platform Plugin SDK - core exports.
 */

export const PERMISSIONS = {
  NETWORK_OUTBOUND: 'network:outbound',
  NETWORK_INBOUND: 'network:inbound',
  STORAGE_READ: 'storage:read',
  STORAGE_WRITE: 'storage:write',
  SYSTEM_ENV: 'system:env',
  AGENT_MESSAGE: 'agent:message',
  USER_INFO: 'user:info',
  FILESYSTEM_READ: 'filesystem:read',
  FILESYSTEM_WRITE: 'filesystem:write',
  PROCESS_SPAWN: 'process:spawn',
  DATABASE_QUERY: 'database:query',
  MCP_INVOKE: 'mcp:invoke',
} as const;

export type SkillPermission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

export interface SkillDefinition<TParams = Record<string, unknown>, TResult = unknown> {
  name: string;
  description: string;
  permissions: SkillPermission[];
  parameters: Record<string, unknown>;
  execute: (params: TParams) => Promise<TResult> | TResult;
}

export interface PluginManifest {
  plugin_id: string;
  name: string;
  description: string;
  author: string;
  version: string;
  category: string;
  permissions: SkillPermission[];
  skills: string[];
  signature?: string;
}

/** 定义 Skill 处理器 */
export function defineSkill<TParams = Record<string, unknown>, TResult = unknown>(
  definition: SkillDefinition<TParams, TResult>,
): SkillDefinition<TParams, TResult> {
  return definition;
}

/** 插件私有存储（运行时由平台注入） */
export const storage = {
  async get(_key: string): Promise<unknown> {
    throw new Error('storage.get must be called within platform runtime');
  },
  async set(_key: string, _value: unknown): Promise<void> {
    throw new Error('storage.set must be called within platform runtime');
  },
};

/** 权限常量别名 */
export const permissions = PERMISSIONS;
