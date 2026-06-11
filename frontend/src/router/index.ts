import { createRouter, createWebHistory } from 'vue-router';
import type { RouteRecordRaw } from 'vue-router';
import { useUserStore } from '@/stores/user';
import { ROUTE_PERMISSIONS } from '@/constants/permissions';

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
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '控制台', icon: 'Odometer' },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/knowledge/Index.vue'),
        meta: {
          title: '知识库',
          icon: 'Collection',
          permission: ROUTE_PERMISSIONS.knowledge,
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
          permission: ROUTE_PERMISSIONS.agents,
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
          permission: ROUTE_PERMISSIONS.workflows,
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
        ],
      },
      {
        path: 'monitor',
        name: 'Monitor',
        component: () => import('@/views/monitor/Dashboard.vue'),
        meta: {
          title: '监控面板',
          icon: 'DataAnalysis',
          permission: ROUTE_PERMISSIONS.monitor,
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
              permission: ROUTE_PERMISSIONS.userManagement,
            },
          },
          {
            path: 'roles',
            name: 'RoleManagement',
            component: () => import('@/views/settings/RoleManagement.vue'),
            meta: {
              title: '角色管理',
              permission: ROUTE_PERMISSIONS.roleManagement,
            },
          },
          {
            path: 'api-keys',
            name: 'ApiKeys',
            component: () => import('@/views/settings/ApiKeys.vue'),
            meta: { title: 'API 密钥管理' },
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

/** 检查路由及其父级所需的权限 */
function getRequiredPermission(route: {
  meta: Record<string, unknown>;
  matched: { meta: Record<string, unknown> }[];
}): string | undefined {
  if (route.meta.permission) {
    return route.meta.permission as string;
  }
  const matched = [...route.matched].reverse();
  for (const record of matched) {
    if (record.meta.permission) {
      return record.meta.permission as string;
    }
  }
  return undefined;
}

// 路由守卫：认证 + 动态权限校验
router.beforeEach(async (to, _from, next) => {
  const userStore = useUserStore();

  if (to.meta.requiresAuth !== false && !userStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } });
    return;
  }

  if (to.name === 'Login' && userStore.isLoggedIn) {
    next({ name: 'Dashboard' });
    return;
  }

  // 加载用户信息
  if (userStore.isLoggedIn && !userStore.userInfo) {
    try {
      await userStore.fetchUserInfo();
    } catch {
      userStore.logout();
      next({ name: 'Login' });
      return;
    }
  }

  // 动态权限路由校验
  const requiredPermission = getRequiredPermission(to);
  if (requiredPermission && !userStore.hasPermission(requiredPermission)) {
    next({ name: 'Dashboard' });
    return;
  }

  next();
});

export default router;
