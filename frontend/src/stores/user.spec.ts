import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useUserStore } from '@/stores/user';

vi.mock('@/api/user', () => ({
  login: vi.fn().mockResolvedValue({ token: 'test-token', refresh_token: 'rt', expires_in: 3600 }),
  logout: vi.fn().mockResolvedValue(undefined),
  getUserInfo: vi.fn().mockResolvedValue({
    user: { id: 1, username: 'admin', email: 'a@b.com', role: null, permissions: [] },
    permissions: ['*'],
  }),
}));

describe('useUserStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('初始未登录', () => {
    const store = useUserStore();
    expect(store.isLoggedIn).toBe(false);
  });

  it('login 后设置 token', async () => {
    const store = useUserStore();
    await store.login('admin', 'password');
    expect(store.isLoggedIn).toBe(true);
    expect(localStorage.getItem('token')).toBe('test-token');
  });

  it('hasPermission 支持通配符', async () => {
    const store = useUserStore();
    await store.login('admin', 'password');
    expect(store.hasPermission('kb:read')).toBe(true);
  });

  it('logout 清除状态', async () => {
    const store = useUserStore();
    await store.login('admin', 'password');
    store.clearSession();
    expect(store.isLoggedIn).toBe(false);
    expect(localStorage.getItem('token')).toBeNull();
  });
});
