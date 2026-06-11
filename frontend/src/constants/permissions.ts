/** 系统权限选项（角色配置用） */
export const PERMISSION_OPTIONS = [
  { label: '全部权限', value: '*' },
  { label: '用户查看', value: 'user:read' },
  { label: '用户管理', value: 'user:write' },
  { label: '角色查看', value: 'role:read' },
  { label: '角色管理', value: 'role:write' },
  { label: '知识库查看', value: 'knowledge:read' },
  { label: '知识库管理', value: 'knowledge:write' },
  { label: '智能体查看', value: 'agent:read' },
  { label: '智能体管理', value: 'agent:write' },
  { label: '智能体删除', value: 'agent:delete' },
  { label: '工作流查看', value: 'workflow:read' },
  { label: '工作流管理', value: 'workflow:write' },
  { label: '监控查看', value: 'monitor:read' },
  { label: '审计日志', value: 'audit:read' },
  { label: '租户查看', value: 'tenant:read' },
  { label: '租户管理', value: 'tenant:write' },
] as const;

/** 路由权限映射 */
export const ROUTE_PERMISSIONS = {
  knowledge: 'knowledge:read',
  agents: 'agent:read',
  workflows: 'workflow:read',
  userManagement: 'user:read',
  roleManagement: 'role:read',
  monitor: 'monitor:read',
  tenants: 'tenant:read',
  auditLogs: 'audit:read',
} as const;
