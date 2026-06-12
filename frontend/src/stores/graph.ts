import { defineStore } from 'pinia';
import { ref } from 'vue';
import {
  getWorkflows,
  getWorkflow,
  createWorkflow,
  updateWorkflow,
  deleteWorkflow,
  executeWorkflow,
  getExecutionStatus,
  submitHumanIntervention,
  cancelWorkflowExecution,
  buildWorkflowWsUrl,
  type WorkflowInfo,
  type WorkflowExecution,
  type NodeExecutionLog,
  type WorkflowWsMessage,
  type CreateWorkflowParams,
  type UpdateWorkflowParams,
  type ExecuteWorkflowParams,
} from '@/api/workflow';
import type { AgentMessage } from '@/api/groupChat';
import type { PageParams } from '@/types/api';

/** 节点状态颜色映射 */
export const NODE_STATUS_COLORS: Record<string, string> = {
  waiting: '#86909C',
  running: '#FF5A1F',
  completed: '#00B42A',
  failed: '#F53F3F',
  waiting_for_human: '#FF7D00',
};

export const useGraphStore = defineStore('graph', () => {
  const workflows = ref<WorkflowInfo[]>([]);
  const currentWorkflow = ref<WorkflowInfo | null>(null);
  const currentExecution = ref<WorkflowExecution | null>(null);
  const nodeStatuses = ref<Record<string, string>>({});
  const executionLogs = ref<NodeExecutionLog[]>([]);
  const streamingFinalAnswer = ref('');
  const groupChatMessages = ref<AgentMessage[]>([]);
  const isLoading = ref(false);
  const total = ref(0);

  let ws: WebSocket | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  /** 加载工作流列表 */
  async function fetchWorkflows(params?: PageParams): Promise<void> {
    isLoading.value = true;
    try {
      const res = await getWorkflows(params);
      workflows.value = res.items;
      total.value = res.total;
    } finally {
      isLoading.value = false;
    }
  }

  /** 加载工作流详情 */
  async function fetchWorkflow(id: number): Promise<void> {
    isLoading.value = true;
    try {
      currentWorkflow.value = await getWorkflow(id);
    } finally {
      isLoading.value = false;
    }
  }

  /** 创建工作流 */
  async function addWorkflow(data: CreateWorkflowParams): Promise<WorkflowInfo> {
    const result = await createWorkflow(data);
    await fetchWorkflows();
    return result;
  }

  /** 更新工作流 */
  async function editWorkflow(id: number, data: UpdateWorkflowParams): Promise<void> {
    await updateWorkflow(id, data);
    await fetchWorkflows();
  }

  /** 删除工作流 */
  async function removeWorkflow(id: number): Promise<void> {
    await deleteWorkflow(id);
    await fetchWorkflows();
  }

  /** 执行工作流 */
  async function runWorkflow(
    workflowId: number,
    data: ExecuteWorkflowParams,
  ): Promise<WorkflowExecution> {
    const execution = await executeWorkflow(workflowId, data);
    currentExecution.value = execution;
    nodeStatuses.value = execution.node_statuses || {};
    executionLogs.value = execution.logs || [];
    return execution;
  }

  /** 刷新执行状态 */
  async function refreshExecution(executionId: number): Promise<void> {
    const execution = await getExecutionStatus(executionId);
    currentExecution.value = execution;
    nodeStatuses.value = execution.node_statuses || {};
    executionLogs.value = execution.logs || [];
  }

  /** 终止工作流执行 */
  async function cancelExecution(executionId: number): Promise<void> {
    const execution = await cancelWorkflowExecution(executionId);
    currentExecution.value = execution;
    nodeStatuses.value = execution.node_statuses || {};
    executionLogs.value = execution.logs || [];
    disconnectWebSocket();
  }

  /** 人工介入 */
  async function intervene(
    executionId: number,
    approved: boolean,
    comment?: string,
    rejectTarget?: string,
  ): Promise<void> {
    const execution = await submitHumanIntervention(executionId, {
      approved,
      comment,
      reject_target: rejectTarget,
    });
    currentExecution.value = execution;
    nodeStatuses.value = execution.node_statuses || {};
    executionLogs.value = execution.logs || [];
  }

  /** 轮询执行状态（WebSocket 不可用时的兜底） */
  function startExecutionPolling(executionId: number, intervalMs = 2000): void {
    stopExecutionPolling();
    pollTimer = setInterval(async () => {
      try {
        await refreshExecution(executionId);
        const status = currentExecution.value?.status;
        if (status && ['completed', 'failed', 'interrupted'].includes(status)) {
          stopExecutionPolling();
        }
      } catch (err) {
        console.error('[Workflow Poll] 刷新失败', err);
      }
    }, intervalMs);
  }

  function stopExecutionPolling(): void {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  /** 连接 WebSocket 实时推送 */
  function connectWebSocket(executionId: number): void {
    disconnectWebSocket();
    startExecutionPolling(executionId);

    const url = buildWorkflowWsUrl(executionId);
    ws = new WebSocket(url);

    ws.onopen = () => {
      console.info('[Workflow WS] 已连接 execution_id=%s', executionId);
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const message: WorkflowWsMessage = JSON.parse(event.data as string);
        handleWsMessage(message);
      } catch (err) {
        console.error('[Workflow WS] 消息解析失败', err);
      }
    };

    ws.onerror = (err) => {
      console.error('[Workflow WS] 连接错误', err);
    };

    ws.onclose = () => {
      ws = null;
    };
  }

  /** 断开 WebSocket */
  function disconnectWebSocket(): void {
    stopExecutionPolling();
    if (ws) {
      ws.close();
      ws = null;
    }
  }

  /** 处理 WebSocket 消息 */
  function handleWsMessage(message: WorkflowWsMessage): void {
    if (message.type === 'node_status' && message.node_id && message.status) {
      nodeStatuses.value = {
        ...nodeStatuses.value,
        [message.node_id]: message.status,
      };
      if (message.log) {
        executionLogs.value = [...executionLogs.value, message.log];
      }
    }

    if (message.type === 'connected') {
      console.info('[Workflow WS] 服务端确认连接', message);
    }

    if (message.type === 'execution_status' && message.status) {
      if (currentExecution.value) {
        currentExecution.value = {
          ...currentExecution.value,
          status: message.status,
          output_result: message.data || currentExecution.value.output_result,
        };
      }
      if (['completed', 'failed', 'interrupted'].includes(message.status)) {
        stopExecutionPolling();
      }
    }

    if (message.type === 'node_stream' && message.chunk) {
      streamingFinalAnswer.value += message.chunk;
    }

    if (message.type === 'group_chat_message' && message.message) {
      const payload = message.message as AgentMessage;
      groupChatMessages.value = [...groupChatMessages.value, payload];
    }
  }

  /** 重置执行状态 */
  function resetExecution(): void {
    disconnectWebSocket();
    currentExecution.value = null;
    nodeStatuses.value = {};
    executionLogs.value = [];
    streamingFinalAnswer.value = '';
    groupChatMessages.value = [];
  }

  return {
    workflows,
    currentWorkflow,
    currentExecution,
    nodeStatuses,
    executionLogs,
    streamingFinalAnswer,
    groupChatMessages,
    isLoading,
    total,
    fetchWorkflows,
    fetchWorkflow,
    addWorkflow,
    editWorkflow,
    removeWorkflow,
    runWorkflow,
    refreshExecution,
    intervene,
    cancelExecution,
    connectWebSocket,
    disconnectWebSocket,
    startExecutionPolling,
    stopExecutionPolling,
    resetExecution,
  };
});
