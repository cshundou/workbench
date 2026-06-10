import { defineStore } from 'pinia';
import { ref } from 'vue';
import {
  getAgents,
  getAgentById,
  getAvailableTools,
  getAgentHistory,
  type AgentInfo,
  type ToolDefinition,
  type ChatHistoryItem,
} from '@/api/agent';
import type { PageParams } from '@/types/api';

export const useAgentStore = defineStore('agent', () => {
  const agents = ref<AgentInfo[]>([]);
  const currentAgent = ref<AgentInfo | null>(null);
  const availableTools = ref<ToolDefinition[]>([]);
  const chatHistory = ref<ChatHistoryItem[]>([]);
  const isLoading = ref(false);
  const total = ref(0);

  /** 加载智能体列表 */
  async function fetchAgents(params?: PageParams & { keyword?: string }): Promise<void> {
    isLoading.value = true;
    try {
      const res = await getAgents(params);
      agents.value = res.items;
      total.value = res.total;
    } catch (error) {
      console.error('[Fetch Agents Error]', error);
    } finally {
      isLoading.value = false;
    }
  }

  /** 加载智能体详情 */
  async function fetchAgent(id: number): Promise<void> {
    isLoading.value = true;
    try {
      currentAgent.value = await getAgentById(id);
    } catch (error) {
      console.error('[Fetch Agent Error]', error);
      currentAgent.value = null;
    } finally {
      isLoading.value = false;
    }
  }

  /** 加载可用工具 */
  async function fetchAvailableTools(): Promise<void> {
    try {
      availableTools.value = await getAvailableTools();
    } catch (error) {
      console.error('[Fetch Tools Error]', error);
    }
  }

  /** 加载对话历史 */
  async function fetchChatHistory(
    agentId: number,
    sessionId?: string,
  ): Promise<void> {
    isLoading.value = true;
    try {
      const res = await getAgentHistory(agentId, { session_id: sessionId });
      chatHistory.value = res.items;
    } catch (error) {
      console.error('[Fetch Chat History Error]', error);
    } finally {
      isLoading.value = false;
    }
  }

  /** 清空当前智能体上下文 */
  function clearCurrentAgent(): void {
    currentAgent.value = null;
    chatHistory.value = [];
  }

  return {
    agents,
    currentAgent,
    availableTools,
    chatHistory,
    isLoading,
    total,
    fetchAgents,
    fetchAgent,
    fetchAvailableTools,
    fetchChatHistory,
    clearCurrentAgent,
  };
});
