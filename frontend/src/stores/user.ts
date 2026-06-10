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

  function logout(): void {
    apiLogout().catch((error) => {
      console.error('[Logout Error]', error);
    });
    token.value = null;
    userInfo.value = null;
    permissions.value = [];
    localStorage.removeItem('token');
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
    logout,
    hasPermission,
  };
});
