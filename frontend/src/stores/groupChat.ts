import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import {
  buildGroupChatWsUrl,
  cancelGroupChatSession,
  createGroupChatSession,
  getGroupChatMessages,
  getGroupChatSession,
  resolveGroupChatReview,
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
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectAttempts = 0;
  const MAX_RECONNECT = 3;
  let activeSessionId: number | null = null;

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

  /** 同步消息列表（断线重连后） */
  async function syncMessages(sessionId: number): Promise<void> {
    const records = await getGroupChatMessages(sessionId);
    messages.value = records.map((m) => m.payload);
  }

  /** 连接 WebSocket */
  function connectWebSocket(sessionId: number): void {
    disconnectWebSocket(false);
    activeSessionId = sessionId;
    reconnectAttempts = 0;
    startPolling(sessionId);
    openWebSocket(sessionId);
  }

  function openWebSocket(sessionId: number): void {
    const url = buildGroupChatWsUrl(sessionId);
    ws = new WebSocket(url);

    ws.onopen = () => {
      reconnectAttempts = 0;
    };

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
      if (
        activeSessionId === sessionId &&
        !['completed', 'failed', 'cancelled', 'human_review'].includes(sessionStatus.value)
      ) {
        scheduleReconnect(sessionId);
      }
    };
  }

  function scheduleReconnect(sessionId: number): void {
    if (reconnectAttempts >= MAX_RECONNECT) return;
    const delay = 1000 * 2 ** reconnectAttempts;
    reconnectAttempts += 1;
    reconnectTimer = setTimeout(async () => {
      try {
        await syncMessages(sessionId);
        openWebSocket(sessionId);
      } catch (err) {
        console.error('[GroupChat WS] 重连失败', err);
        scheduleReconnect(sessionId);
      }
    }, delay);
  }

  function disconnectWebSocket(clearSession = true): void {
    stopPolling();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (clearSession) {
      activeSessionId = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
  }

  async function cancelSession(): Promise<void> {
    if (!currentSession.value) return;
    await cancelGroupChatSession(currentSession.value.id);
    currentSession.value = {
      ...currentSession.value,
      status: 'cancelled',
    };
    stopPolling();
  }

  async function resolveReview(action: 'approve' | 'reject', comment?: string): Promise<void> {
    if (!currentSession.value) return;
    const session = await resolveGroupChatReview(currentSession.value.id, action, comment);
    currentSession.value = session;
    stopPolling();
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
    cancelSession,
    resolveReview,
    reset,
  };
});
