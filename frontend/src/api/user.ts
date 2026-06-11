import request from './request';
import type {
  CreateUserParams,
  LoginParams,
  LoginResult,
  PageParams,
  PageResult,
  UpdateUserParams,
  UserInfo,
  UserInfoResult,
  UserListItem,
} from '@/types/api';

/** 后端登录响应（蛇形命名） */
interface LoginApiData {
  token: string;
  refresh_token?: string;
  expires_in: number;
}

/** 后端 /auth/me 响应（嵌套 user 对象） */
interface MeApiData {
  user: {
    id: number;
    username: string;
    email: string;
    role: UserInfo['role'];
    permissions: string[];
  };
  permissions: string[];
}

/** 用户登录 */
export async function login(data: LoginParams): Promise<LoginResult> {
  const res = (await request.post('/auth/login', data)) as LoginApiData;
  if (res.refresh_token) {
    localStorage.setItem('refresh_token', res.refresh_token);
  }
  return {
    token: res.token,
    expiresIn: res.expires_in,
  };
}

/** 获取当前用户信息 */
export async function getUserInfo(): Promise<UserInfoResult> {
  const res = (await request.get('/auth/me')) as MeApiData;
  return {
    user: res.user,
    permissions: res.permissions,
  };
}

/** 刷新访问令牌 */
export function refreshAccessToken(refreshToken: string): Promise<{ token: string; expires_in: number }> {
  return request.post('/auth/refresh', { refresh_token: refreshToken }) as Promise<{
    token: string;
    expires_in: number;
  }>;
}

/** 用户登出 */
export function logout(): Promise<void> {
  const refreshToken = localStorage.getItem('refresh_token');
  localStorage.removeItem('refresh_token');
  return request.post('/auth/logout', refreshToken ? { refresh_token: refreshToken } : {});
}

/** 获取用户列表 */
export function getUsers(params?: PageParams): Promise<PageResult<UserListItem>> {
  return request.get('/users', { params }) as Promise<PageResult<UserListItem>>;
}

/** 获取用户详情 */
export function getUserById(id: number): Promise<UserListItem> {
  return request.get(`/users/${id}`) as Promise<UserListItem>;
}

/** 创建用户 */
export function createUser(data: CreateUserParams): Promise<UserListItem> {
  return request.post('/users', data) as Promise<UserListItem>;
}

/** 更新用户 */
export function updateUser(id: number, data: UpdateUserParams): Promise<UserListItem> {
  return request.put(`/users/${id}`, data) as Promise<UserListItem>;
}

/** 删除用户 */
export function deleteUser(id: number): Promise<void> {
  return request.delete(`/users/${id}`) as Promise<void>;
}
