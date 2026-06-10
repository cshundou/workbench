import request from './request';
import type { PageParams, PageResult } from '@/types/api';

/** 工作流拓扑节点 */
export interface WorkflowNodeDef {
  id: string;
  type: string;
  label: string;
  position: { x: number; y: number };
}

/** 工作流拓扑边 */
export interface WorkflowEdgeDef {
  id: string;
  source: string;
  target: string;
}

/** 工作流图定义 */
export interface GraphDefinition {
  nodes: WorkflowNodeDef[];
  edges: WorkflowEdgeDef[];
}

/** 工作流信息 */
export interface WorkflowInfo {
  id: number;
  tenant_id: number;
  name: string;
  description?: string | null;
  graph_definition: GraphDefinition;
  owner_id?: number | null;
  is_public: boolean;
  created_at?: string;
  updated_at?: string;
}

/** 创建工作流参数 */
export interface CreateWorkflowParams {
  name: string;
  description?: string;
  graph_definition?: GraphDefinition;
  is_public?: boolean;
}

/** 更新工作流参数 */
export interface UpdateWorkflowParams {
  name?: string;
  description?: string;
  graph_definition?: GraphDefinition;
  is_public?: boolean;
}

/** 执行工作流参数 */
export interface ExecuteWorkflowParams {
  task: string;
  require_human_approval?: boolean;
  kb_id?: number;
  extra_params?: Record<string, unknown>;
}

/** 节点执行日志 */
export interface NodeExecutionLog {
  node_id: string;
  node_label: string;
  status: string;
  input_data?: Record<string, unknown> | null;
  output_data?: Record<string, unknown> | null;
  error?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

/** 工作流执行记录 */
export interface WorkflowExecution {
  id: number;
  workflow_id: number;
  tenant_id: number;
  status: string;
  input_params: Record<string, unknown>;
  output_result?: Record<string, unknown> | null;
  error_message?: string | null;
  started_at?: string;
  completed_at?: string | null;
  created_by?: number | null;
  thread_id?: string | null;
  node_statuses?: Record<string, string>;
  logs?: NodeExecutionLog[];
}

/** 人工介入参数 */
export interface HumanInterventionParams {
  approved: boolean;
  comment?: string;
}

/** WebSocket 消息 */
export interface WorkflowWsMessage {
  type: 'connected' | 'node_status' | 'execution_status';
  execution_id?: number;
  node_id?: string;
  status?: string;
  log?: NodeExecutionLog;
  data?: Record<string, unknown>;
  message?: string;
}

/** 获取工作流列表 */
export function getWorkflows(params?: PageParams): Promise<PageResult<WorkflowInfo>> {
  return request.get('/workflows', { params });
}

/** 获取工作流详情 */
export function getWorkflow(id: number): Promise<WorkflowInfo> {
  return request.get(`/workflows/${id}`);
}

/** 创建工作流 */
export function createWorkflow(data: CreateWorkflowParams): Promise<WorkflowInfo> {
  return request.post('/workflows', data);
}

/** 更新工作流 */
export function updateWorkflow(id: number, data: UpdateWorkflowParams): Promise<WorkflowInfo> {
  return request.put(`/workflows/${id}`, data);
}

/** 删除工作流 */
export function deleteWorkflow(id: number): Promise<void> {
  return request.delete(`/workflows/${id}`);
}

/** 执行工作流 */
export function executeWorkflow(
  workflowId: number,
  data: ExecuteWorkflowParams,
): Promise<WorkflowExecution> {
  return request.post(`/workflows/${workflowId}/execute`, data);
}

/** 获取执行状态 */
export function getExecutionStatus(executionId: number): Promise<WorkflowExecution> {
  return request.get(`/workflows/executions/${executionId}`);
}

/** 获取执行历史 */
export function getExecutionHistory(
  workflowId: number,
  params?: PageParams,
): Promise<PageResult<WorkflowExecution>> {
  return request.get(`/workflows/${workflowId}/executions`, { params });
}

/** 人工介入确认 */
export function submitHumanIntervention(
  executionId: number,
  data: HumanInterventionParams,
): Promise<WorkflowExecution> {
  return request.post(`/workflows/executions/${executionId}/intervene`, data);
}

/** 构建工作流 WebSocket URL */
export function buildWorkflowWsUrl(executionId: number): string {
  const base = import.meta.env.VITE_API_BASE_URL || '/api/v1';
  const wsBase = base.replace(/^http/, 'ws');
  const token = localStorage.getItem('token') || '';
  return `${wsBase}/workflows/ws/${executionId}?token=${encodeURIComponent(token)}`;
}
