import request from '@/api/request';
import type { PageResult } from '@/types/api';

/** Token 消耗汇总 */
export interface TokenUsageSummary {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  record_count: number;
}

/** Token 消耗按日统计项 */
export interface TokenUsageByDay {
  date: string;
  total_tokens: number;
  record_count: number;
}

/** Token 消耗按用户统计项 */
export interface TokenUsageByUser {
  user_id: number | null;
  username: string;
  total_tokens: number;
  record_count: number;
}

/** Token 消耗按模型统计项 */
export interface TokenUsageByModel {
  model_name: string;
  total_tokens: number;
  record_count: number;
}

/** Token 消耗统计响应 */
export interface TokenUsageStats {
  summary: TokenUsageSummary;
  breakdown: TokenUsageByDay[] | TokenUsageByUser[] | TokenUsageByModel[];
  filters: {
    start_date: string;
    end_date: string;
    user_id?: number | null;
    model_name?: string | null;
    group_by: string;
  };
}

/** API 调用汇总 */
export interface ApiStatsSummary {
  total_count: number;
  error_count: number;
  avg_response_ms: number;
}

/** API 按端点统计项 */
export interface ApiEndpointStat {
  endpoint: string;
  count: number;
  avg_response_ms: number;
}

/** API 按日统计项 */
export interface ApiDailyStat {
  date: string;
  count: number;
  error_count: number;
  avg_response_ms: number;
}

/** API 调用统计响应 */
export interface ApiStats {
  summary: ApiStatsSummary;
  endpoints: ApiEndpointStat[];
  daily_series: ApiDailyStat[];
}

/** 错误日志条目 */
export interface ErrorLogItem {
  timestamp: string;
  method: string;
  path: string;
  status_code: number;
  message: string;
  error?: string | null;
}

/** 健康检查组件状态 */
export interface HealthComponent {
  status: string;
  message: string;
}

/** 系统健康检查响应 */
export interface SystemHealth {
  status: string;
  timestamp: string;
  components: Record<string, HealthComponent>;
}

export interface TokenUsageQuery {
  start_date?: string;
  end_date?: string;
  user_id?: number;
  model_name?: string;
  group_by?: 'day' | 'user' | 'model';
}

/** 查询 Token 消耗统计 */
export function getTokenUsage(params?: TokenUsageQuery): Promise<TokenUsageStats> {
  return request.get('/monitor/token-usage', { params });
}

/** 查询 API 调用统计 */
export function getApiStats(days = 7): Promise<ApiStats> {
  return request.get('/monitor/api-stats', { params: { days } });
}

/** 分页查询错误日志 */
export function getErrorLogs(params?: {
  page?: number;
  page_size?: number;
  status_code?: number;
}): Promise<PageResult<ErrorLogItem>> {
  return request.get('/monitor/error-logs', { params });
}

/** 系统健康检查 */
export function getMonitorHealth(): Promise<SystemHealth> {
  return request.get('/monitor/health');
}

export interface UserActivityStats {
  dau: number;
  wau: number;
  mau: number;
  top_users: { user_id: number; username: string; count: number }[];
  module_usage: { module: string; count: number; ratio: number }[];
}

/** 用户活跃度统计 */
export function getUserActivity(): Promise<UserActivityStats> {
  return request.get('/monitor/user-activity');
}
