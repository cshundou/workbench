/** 路由访问级别 */
export type AccessLevel = 'public' | 'auth' | 'permission';

/** 认证模式 */
export type AuthMode = 'required' | 'optional';

/** 默认认证模式（与环境变量一致） */
export const DEFAULT_AUTH_MODE: AuthMode =
  (import.meta.env.VITE_AUTH_MODE as AuthMode) || 'required';
