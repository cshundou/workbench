import axios, {
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';
import { ElMessage } from 'element-plus';
import type { ApiResponse } from '@/types/api';
import router from '@/router';

/** Axios 实例：统一 baseURL、超时与拦截器 */
const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/** 请求拦截：自动附加 Bearer Token（登录接口不携带旧 token，避免干扰） */
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const isLoginRequest = config.url?.includes('/auth/login');
    const token = localStorage.getItem('token');
    if (token && config.headers && !isLoginRequest) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    console.error('[Request Error]', error);
    return Promise.reject(error);
  },
);

/** 响应拦截：统一处理业务 code 与 HTTP 错误 */
request.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const res = response.data;

    if (res.code === 200) {
      return res.data as never;
    }

    const errorMessage = res.message || '请求失败';
    ElMessage.error(errorMessage);
    return Promise.reject(new Error(errorMessage));
  },
  (error) => {
    const status = error.response?.status;
    const responseData = error.response?.data as ApiResponse | undefined;
    const errorMessage = responseData?.message || error.message || '网络错误';

    if (status === 401) {
      localStorage.removeItem('token');
      if (router.currentRoute.value.name !== 'Login') {
        router.push({
          name: 'Login',
          query: { redirect: router.currentRoute.value.fullPath },
        });
      }
      ElMessage.error('登录已过期，请重新登录');
    } else if (status === 428) {
      ElMessage.warning(errorMessage || '请先配置 API 密钥');
      if (router.currentRoute.value.path !== '/settings/api-keys') {
        router.push('/settings/api-keys');
      }
    } else {
      ElMessage.error(errorMessage);
    }

    console.error('[Response Error]', error);
    return Promise.reject(error);
  },
);

export default request;
