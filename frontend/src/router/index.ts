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
