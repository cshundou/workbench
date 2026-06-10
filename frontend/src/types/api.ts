/** 统一 API 响应格式（文档 8.1） */
export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
  error?: string;
}

/** 登录请求参数 */
export interface LoginParams {
  username: string;
  password: string;
}

/** 登录响应数据 */
export interface LoginResult {
  token: string;
  expiresIn: number;
}

/** 用户信息 */
export interface UserInfo {
  id: number;
  username: string;
  email: string;
  role: {
    id: number;
    name: string;
    code: string;
  };
  permissions: string[];
}

/** 获取用户信息响应 */
export interface UserInfoResult {
  user: UserInfo;
  permissions: string[];
}

/** 分页查询参数 */
export interface PageParams {
  page?: number;
  page_size?: number;
  keyword?: string;
}

/** 分页响应 */
export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** 角色信息 */
export interface RoleInfo {
  id: number;
  name: string;
  description?: string | null;
  permissions: string[];
  created_at?: string;
  updated_at?: string;
}

/** 用户列表项 */
export interface UserListItem {
  id: number;
  username: string;
  email: string;
  role_id: number | null;
  role?: {
    id: number;
    name: string;
  } | null;
  status: number;
  last_login_at?: string | null;
  created_at?: string;
}

/** 创建用户参数 */
export interface CreateUserParams {
  username: string;
  email: string;
  password: string;
  role_id: number | null;
}

/** 更新用户参数 */
export interface UpdateUserParams {
  username?: string;
  email?: string;
  password?: string;
  role_id?: number | null;
  status?: number;
}

/** 创建角色参数 */
export interface CreateRoleParams {
  name: string;
  description?: string;
  permissions: string[];
}

/** 更新角色参数 */
export interface UpdateRoleParams {
  name?: string;
  description?: string;
  permissions?: string[];
}
