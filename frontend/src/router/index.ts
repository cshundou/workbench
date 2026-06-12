import { createRouter, createWebHistory } from 'vue-router';
import type { RouteRecordRaw } from 'vue-router';
import { ROUTE_PERMISSIONS } from '@/constants/permissions';
import { authGuard } from '@/router/guards';

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false, title: '登录' },
  },
  {
    path: '/agents/share/:token',
    name: 'AgentShare',
    component: () => import('@/views/agents/Share.vue'),
    meta: { requiresAuth: false, title: '智能体分享' },
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/views/Layout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true, accessLevel: 'public' },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '控制台', icon: 'Odometer', accessLevel: 'public' },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/knowledge/Index.vue'),
        meta: {
          title: '知识库',
          icon: 'Collection',
          accessLevel: 'public',
        },
        children: [
          {
            path: '',
            name: 'KnowledgeList',
            component: () => import('@/views/knowledge/List.vue'),
            meta: { title: '知识库' },
          },
          {
            path: ':id/chat',
            name: 'KnowledgeChat',
            component: () => import('@/views/knowledge/Chat.vue'),
            meta: { title: '知识库问答' },
          },
          {
            path: ':id',
            name: 'KnowledgeDetail',
            component: () => import('@/views/knowledge/Detail.vue'),
            meta: { title: '知识库详情' },
          },
        ],
      },
      {
        path: 'agents',
        name: 'Agents',
        component: () => import('@/views/agents/Index.vue'),
        meta: {
          title: '智能体',
          icon: 'Cpu',
          accessLevel: 'public',
        },
        children: [
          {
            path: '',
            name: 'AgentList',
            component: () => import('@/views/agents/List.vue'),
            meta: { title: '智能体' },
          },
          {
            path: ':id/config',
            name: 'AgentConfig',
            component: () => import('@/views/agents/Config.vue'),
            meta: { title: '智能体配置' },
          },
          {
            path: ':id/chat',
            name: 'AgentChat',
            component: () => import('@/views/agents/Chat.vue'),
            meta: { title: '智能体对话' },
          },
        ],
      },
      {
        path: 'workflows',
        name: 'Workflows',
        component: () => import('@/views/workflows/Index.vue'),
        meta: {
          title: '工作流',
          icon: 'Share',
          accessLevel: 'public',
        },
        children: [
          {
            path: '',
            name: 'WorkflowList',
            component: () => import('@/views/workflows/List.vue'),
            meta: { title: '工作流' },
          },
          {
            path: ':id/execute',
            name: 'WorkflowExecute',
            component: () => import('@/views/workflows/Execute.vue'),
            meta: { title: '执行工作流' },
          },
          {
            path: ':id/edit',
            name: 'WorkflowEdit',
            component: () => import('@/views/workflows/Edit.vue'),
            meta: { title: '编辑工作流', permission: 'workflow:write' },
          },
          {
            path: ':id/history',
            name: 'WorkflowHistory',
            component: () => import('@/views/workflows/History.vue'),
            meta: { title: '执行历史' },
          },
          {
            path: ':id/group-chat',
            name: 'WorkflowGroupChat',
            component: () => import('@/views/workflows/GroupChatView.vue'),
            meta: { title: '群聊协同' },
          },
          {
            path: 'agent-roles',
            name: 'AgentRoles',
            component: () => import('@/views/workflows/AgentRoles.vue'),
            meta: { title: '专业角色库', permission: 'workflow:write' },
          },
          {
            path: 'marketplace',
            name: 'WorkflowMarketplace',
            component: () => import('@/views/marketplace/Index.vue'),
            meta: { title: '模板市场' },
          },
        ],
      },
      {
        path: 'monitor',
        name: 'Monitor',
        component: () => import('@/views/monitor/Dashboard.vue'),
        meta: {
          title: '监控面板',
          icon: 'DataAnalysis',
          accessLevel: 'public',
        },
      },
      {
        path: 'monitor/traces',
        name: 'MonitorTraces',
        component: () => import('@/views/monitor/TraceDetail.vue'),
        meta: { title: '链路追踪', accessLevel: 'public' },
      },
      {
        path: 'plugins',
        name: 'Plugins',
        redirect: '/plugins/marketplace',
        meta: {
          title: '插件市场',
          icon: 'Connection',
          accessLevel: 'permission',
          permission: 'agent:write',
        },
        children: [
          {
            path: 'marketplace',
            name: 'PluginMarketplace',
            component: () => import('@/views/plugins/Marketplace.vue'),
            meta: { title: '插件市场' },
          },
          {
            path: 'installed',
            name: 'PluginsInstalled',
            component: () => import('@/views/plugins/Installed.vue'),
            meta: { title: '已安装插件' },
          },
          {
            path: 'skills',
            name: 'SkillsConfig',
            component: () => import('@/views/plugins/SkillsConfig.vue'),
            meta: { title: '技能配置' },
          },
          {
            path: ':pluginId',
            name: 'PluginDetail',
            component: () => import('@/views/plugins/Detail.vue'),
            meta: { title: '插件详情' },
          },
        ],
      },
      {
        path: 'settings',
        name: 'Settings',
        redirect: '/settings/users',
        meta: { title: '系统设置', icon: 'Setting' },
        children: [
          {
            path: 'users',
            name: 'UserManagement',
            component: () => import('@/views/settings/UserManagement.vue'),
            meta: {
              title: '用户管理',
              accessLevel: 'permission',
              permission: ROUTE_PERMISSIONS.userManagement,
            },
          },
          {
            path: 'roles',
            name: 'RoleManagement',
            component: () => import('@/views/settings/RoleManagement.vue'),
            meta: {
              title: '角色管理',
              accessLevel: 'permission',
              permission: ROUTE_PERMISSIONS.roleManagement,
            },
          },
          {
            path: 'api-keys',
            name: 'ApiKeys',
            component: () => import('@/views/settings/ApiKeys.vue'),
            meta: { title: 'API 密钥管理', accessLevel: 'auth' },
          },
          {
            path: 'tools',
            name: 'ToolsManagement',
            component: () => import('@/views/settings/ToolsManagement.vue'),
            meta: {
              title: '工具管理',
              accessLevel: 'permission',
              permission: 'agent:write',
            },
          },
          {
            path: 'mcp',
            name: 'McpServers',
            component: () => import('@/views/settings/McpServers.vue'),
            meta: {
              title: 'MCP 服务器',
              accessLevel: 'permission',
              permission: 'agent:write',
            },
          },
          {
            path: 'tenants',
            name: 'TenantManagement',
            component: () => import('@/views/settings/TenantManagement.vue'),
            meta: { title: '租户管理', accessLevel: 'permission', permission: 'tenant:read' },
          },
          {
            path: 'audit-logs',
            name: 'AuditLogs',
            component: () => import('@/views/settings/AuditLogs.vue'),
            meta: { title: '审计日志', accessLevel: 'permission', permission: 'audit:read' },
          },
        ],
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

router.beforeEach(authGuard);

export default router;
