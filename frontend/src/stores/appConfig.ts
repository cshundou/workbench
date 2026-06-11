import { defineStore } from 'pinia';
import { ref } from 'vue';
import request from '@/api/request';
import { DEFAULT_AUTH_MODE, type AuthMode } from '@/constants/auth';

interface AuthConfigResponse {
  auth_mode: AuthMode;
  anonymous_enabled: boolean;
}

/** 应用运行时配置（认证模式等） */
export const useAppConfigStore = defineStore('appConfig', () => {
  const authMode = ref<AuthMode>(DEFAULT_AUTH_MODE);
  const loaded = ref(false);

  async function fetchAuthConfig(): Promise<void> {
    try {
      const data = (await request.get('/config/auth')) as AuthConfigResponse;
      authMode.value = data.auth_mode || DEFAULT_AUTH_MODE;
    } catch {
      authMode.value = DEFAULT_AUTH_MODE;
    } finally {
      loaded.value = true;
    }
  }

  return { authMode, loaded, fetchAuthConfig };
});
