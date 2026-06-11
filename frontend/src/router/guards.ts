import type { RouteLocationNormalized, NavigationGuardNext } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useUserStore } from '@/stores/user';
import { useAppConfigStore } from '@/stores/appConfig';
import type { AccessLevel } from '@/constants/auth';

/** 从 matched 记录解析访问级别 */
export function resolveAccessLevel(route: RouteLocationNormalized): AccessLevel {
  const matched = [...route.matched].reverse();
  for (const record of matched) {
    const level = record.meta.accessLevel as AccessLevel | undefined;
    if (level) {
      return level;
    }
  }
  if (route.meta.requiresAuth === false) {
    return 'public';
  }
  if (route.meta.permission) {
    return 'permission';
  }
  return 'auth';
}

/** 检查路由及其父级所需的权限 */
export function getRequiredPermission(route: RouteLocationNormalized): string | undefined {
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

/** 认证与权限路由守卫 */
export async function authGuard(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext,
): Promise<void> {
  const userStore = useUserStore();
  const appConfig = useAppConfigStore();

  if (!appConfig.loaded) {
    await appConfig.fetchAuthConfig();
  }

  const authMode = appConfig.authMode;
  const level = resolveAccessLevel(to);

  if (authMode === 'required' && to.meta.requiresAuth !== false && !userStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } });
    return;
  }

  if (
    authMode === 'optional' &&
    (level === 'auth' || level === 'permission') &&
    !userStore.isLoggedIn
  ) {
    next({ name: 'Login', query: { redirect: to.fullPath } });
    return;
  }

  if (to.name === 'Login' && userStore.isLoggedIn) {
    next({ name: 'Dashboard' });
    return;
  }

  if (userStore.isLoggedIn && !userStore.userInfo) {
    try {
      await userStore.fetchUserInfo();
    } catch {
      userStore.logout();
      next({ name: 'Login' });
      return;
    }
  }

  const requiredPermission = getRequiredPermission(to);
  if (requiredPermission && userStore.isLoggedIn && !userStore.hasPermission(requiredPermission)) {
    ElMessage.warning('权限不足');
    next({ name: 'Dashboard' });
    return;
  }

  next();
}

/** 401 时是否应跳转登录页 */
export function shouldRedirectOn401(route: RouteLocationNormalized): boolean {
  const appConfig = useAppConfigStore();
  const level = resolveAccessLevel(route);
  return appConfig.authMode === 'required' || level === 'auth' || level === 'permission';
}
