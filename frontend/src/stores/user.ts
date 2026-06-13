import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { login as apiLogin, logout as apiLogout, getUserInfo } from '@/api/user';
import type { UserInfo } from '@/types/api';

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('token'));
  const userInfo = ref<UserInfo | null>(null);
  const permissions = ref<string[]>([]);

  const isLoggedIn = computed(() => !!token.value);

  async function login(username: string, password: string): Promise<void> {
    const res = await apiLogin({ username, password });
    token.value = res.token;
    localStorage.setItem('token', res.token);
    await fetchUserInfo();
  }

  async function fetchUserInfo(): Promise<void> {
    const res = await getUserInfo();
    userInfo.value = res.user;
    permissions.value = res.permissions;
  }

  /** 清除本地登录态（不调用后端 logout，供 401 拦截器使用） */
  function clearSession(): void {
    token.value = null;
    userInfo.value = null;
    permissions.value = [];
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
  }

  /** 用户主动登出：尽力通知服务端，失败时仍清除本地态 */
  function logout(): void {
    const refreshToken = localStorage.getItem('refresh_token');
    apiLogout(refreshToken)
      .catch((error) => {
        console.error('[Logout Error]', error);
      })
      .finally(() => {
        clearSession();
      });
  }

  function hasPermission(permission: string): boolean {
    return permissions.value.includes(permission) || permissions.value.includes('*');
  }

  return {
    token,
    userInfo,
    permissions,
    isLoggedIn,
    login,
    fetchUserInfo,
    clearSession,
    logout,
    hasPermission,
  };
});
