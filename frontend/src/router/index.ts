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
