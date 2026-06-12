import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import {
  buildGroupChatWsUrl,
  createGroupChatSession,
  getGroupChatSession,
  sendGroupChatMessage,
  type AgentMessage,
  type CreateGroupChatParams,
  type GroupChatMember,
  type GroupChatSession,
  type GroupChatWsMessage,
  type ProgressStep,
} from '@/api/groupChat';

export const useGroupChatStore = defineStore('groupChat', () => {
  const currentSession = ref<GroupChatSession | null>(null);
  const messages = ref<AgentMessage[]>([]);
  const members = ref<GroupChatMember[]>([]);
  const progressSteps = ref<ProgressStep[]>([]);
  const typingRole = ref<string | null>(null);
  const isLoading = ref(false);
  const finalAnswer = ref('');

  let ws: WebSocket | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  const sessionStatus = computed(() => currentSession.value?.status || 'idle');
  const progress = computed(() => currentSession.value?.progress ?? 0);
  const isCompleted = computed(() =>
    ['completed', 'failed', 'human_review'].includes(sessionStatus.value),
  );

  /** 创建并启动群聊会话 */
  async function startSession(params: CreateGroupChatParams): Promise<GroupChatSession> {
    isLoading.value = true;
    try {
      const session = await createGroupChatSession(params);
      currentSession.value = session;
      members.value = session.members;
      progressSteps.value = session.progress_steps;
      messages.value = [];
      connectWebSocket(session.id);
      return session;
    } finally {
      isLoading.value = false;
    }
  }

  /** 加载已有会话 */
  async function loadSession(sessionId: number): Promise<void> {
    isLoading.value = true;
    try {
      const session = await getGroupChatSession(sessionId, true);
      currentSession.value = session;
      members.value = session.members;
      progressSteps.value = session.progress_steps;
      messages.value = (session.messages || []).map((m) => m.payload);
      connectWebSocket(sessionId);
    } finally {
      isLoading.value = false;
    }
  }

  /** 用户发言 */
  async function sendUserMessage(content: string): Promise<void> {
    if (!currentSession.value) return;
    const record = await sendGroupChatMessage(currentSession.value.id, content);
    messages.value.push(record.payload);
  }

  /** 连接 WebSocket */
  function connectWebSocket(sessionId: number): void {
    disconnectWebSocket();
    startPolling(sessionId);

    const url = buildGroupChatWsUrl(sessionId);
    ws = new WebSocket(url);

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: GroupChatWsMessage = JSON.parse(event.data as string);
        handleWsMessage(msg);
      } catch (err) {
        console.error('[GroupChat WS] 消息解析失败', err);
      }
    };

    ws.onerror = (err) => {
      console.error('[GroupChat WS] 连接错误', err);
    };

    ws.onclose = () => {
      ws = null;
    };
  }

  function disconnectWebSocket(): void {
    stopPolling();
    if (ws) {
      ws.close();
      ws = null;
    }
  }

  function startPolling(sessionId: number): void {
    stopPolling();
    pollTimer = setInterval(async () => {
      try {
        const session = await getGroupChatSession(sessionId, true);
        currentSession.value = session;
        members.value = session.members;
        progressSteps.value = session.progress_steps;
        if (['completed', 'failed', 'human_review'].includes(session.status)) {
          stopPolling();
        }
      } catch (err) {
        console.error('[GroupChat Poll] 刷新失败', err);
      }
    }, 3000);
  }

  function stopPolling(): void {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function handleWsMessage(msg: GroupChatWsMessage): void {
    if (msg.type === 'group_chat_message' && msg.message) {
      appendMessage(msg.message);
      if (msg.message.sender.role !== 'user') {
        typingRole.value = null;
      }
    }

    if (msg.type === 'member_status') {
      if (msg.members) {
        members.value = msg.members;
      }
      if (msg.role && msg.status === 'working') {
        typingRole.value = msg.role;
      } else if (msg.role && msg.status === 'idle' && typingRole.value === msg.role) {
        typingRole.value = null;
      }
    }

    if (msg.type === 'session_update' && currentSession.value) {
      currentSession.value = {
        ...currentSession.value,
        status: msg.status || currentSession.value.status,
        progress: msg.progress ?? currentSession.value.progress,
      };
      if (msg.final_answer) {
        finalAnswer.value = msg.final_answer;
      }
      if (msg.status && ['completed', 'failed', 'human_review'].includes(msg.status)) {
        stopPolling();
      }
    }
  }

  function appendMessage(message: AgentMessage): void {
    const exists = messages.value.some((m) => m.id === message.id);
    if (!exists) {
      messages.value.push(message);
    }
  }

  function reset(): void {
    disconnectWebSocket();
    currentSession.value = null;
    messages.value = [];
    members.value = [];
    progressSteps.value = [];
    typingRole.value = null;
    finalAnswer.value = '';
  }

  return {
    currentSession,
    messages,
    members,
    progressSteps,
    typingRole,
    isLoading,
    finalAnswer,
    sessionStatus,
    progress,
    isCompleted,
    startSession,
    loadSession,
    sendUserMessage,
    connectWebSocket,
    disconnectWebSocket,
    reset,
  };
});
