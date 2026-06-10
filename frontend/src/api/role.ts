import request from './request';
import type {
  CreateRoleParams,
  PageParams,
  PageResult,
  RoleInfo,
  UpdateRoleParams,
} from '@/types/api';

/** 获取角色列表 */
export function getRoles(params?: PageParams): Promise<PageResult<RoleInfo>> {
  return request.get('/roles', { params }) as Promise<PageResult<RoleInfo>>;
}

/** 获取角色详情 */
export function getRoleById(id: number): Promise<RoleInfo> {
  return request.get(`/roles/${id}`) as Promise<RoleInfo>;
}

/** 创建角色 */
export function createRole(data: CreateRoleParams): Promise<RoleInfo> {
  return request.post('/roles', data) as Promise<RoleInfo>;
}

/** 更新角色 */
export function updateRole(id: number, data: UpdateRoleParams): Promise<RoleInfo> {
  return request.put(`/roles/${id}`, data) as Promise<RoleInfo>;
}

/** 删除角色 */
export function deleteRole(id: number): Promise<void> {
  return request.delete(`/roles/${id}`) as Promise<void>;
}
