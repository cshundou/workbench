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
  success_count?: number;
  success_rate?: number;
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

/** 工具调用统计 */
export interface ToolStatsSummary {
  total_count: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
}

export interface ToolDailyStat {
  date: string;
  total_count: number;
  success_count: number;
  success_rate: number;
}

export interface ToolStats {
  summary: ToolStatsSummary;
  tools: Array<{
    tool_name: string;
    total_count: number;
    success_count: number;
    failure_count: number;
    success_rate: number;
  }>;
  daily_series: ToolDailyStat[];
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

/** 工具调用成功率统计 */
export function getToolStats(days = 7): Promise<ToolStats> {
  return request.get('/monitor/tool-stats', { params: { days } });
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

export interface AlertConfig {
  enabled: boolean;
  slow_api_threshold_ms: number;
  error_rate_threshold: number;
  cooldown_seconds: number;
  email_configured: boolean;
  dingtalk_configured: boolean;
}

export interface AlertHistoryItem {
  timestamp: string;
  type: string;
  message: string;
}

/** 查询告警配置 */
export function getAlertConfig(): Promise<AlertConfig> {
  return request.get('/monitor/alerts/config');
}

/** 查询告警历史 */
export function getAlertHistory(limit = 20): Promise<{ items: AlertHistoryItem[]; total: number }> {
  return request.get('/monitor/alerts/history', { params: { limit } });
}

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/** 导出 Token 消耗报表 */
export async function exportTokenUsage(
  format: 'csv' | 'excel',
  params?: TokenUsageQuery,
): Promise<void> {
  const token = localStorage.getItem('token');
  const query = new URLSearchParams();
  if (params?.start_date) query.set('start_date', params.start_date);
  if (params?.end_date) query.set('end_date', params.end_date);
  if (params?.group_by) query.set('group_by', params.group_by);

  const suffix = query.toString() ? `?${query.toString()}` : '';
  const response = await fetch(`${baseURL}/monitor/token-usage/export/${format}${suffix}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    throw new Error('导出失败');
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = format === 'csv' ? 'token_usage.csv' : 'token_usage.xlsx';
  link.click();
  window.URL.revokeObjectURL(url);
}
