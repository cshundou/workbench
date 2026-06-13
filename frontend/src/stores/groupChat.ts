import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import {
  buildGroupChatWsUrl,
  cancelGroupChatSession,
  createGroupChatSession,
  getGroupChatMessages,
  getGroupChatSession,
  interveneGroupChatSession,
  restartGroupChatSession,
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
  const selectedRole = ref<string | null>(null);
  const teamConfig = ref<Record<string, unknown> | null>(null);
  const isFormingTeam = ref(false);
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
  const isCompleted = computed(() => sessionStatus.value === 'completed');

  const canIntervene = computed(() =>
    ['failed', 'cancelled', 'human_review'].includes(sessionStatus.value),
  );

  const canSendMessage = computed(() => {
    const status = sessionStatus.value;
    if (status === 'completed') return false;
    if (status === 'human_review') return false;
    return ['running', 'pending', 'reviewing', 'failed', 'cancelled'].includes(status);
  });

  /** 创建并启动群聊会话 */
  async function startSession(params: CreateGroupChatParams): Promise<GroupChatSession> {
    isLoading.value = true;
    try {
      const session = await createGroupChatSession(params);
      currentSession.value = session;
      members.value = session.members;
      progressSteps.value = session.progress_steps;
      teamConfig.value = session.team_config || null;
      isFormingTeam.value = true;
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

  /** 用户发言（失败态走人工介入通道） */
  async function sendUserMessage(content: string, restartAfter = false): Promise<void> {
    if (!currentSession.value) return;
    if (sessionStatus.value === 'failed' || sessionStatus.value === 'cancelled') {
      const session = await interveneGroupChatSession(
        currentSession.value.id,
        restartAfter ? 'restart' : 'supplement',
        content,
      );
      currentSession.value = session;
      members.value = session.members;
      progressSteps.value = session.progress_steps;
      if (restartAfter) {
        connectWebSocket(session.id);
      }
      return;
    }
    const record = await sendGroupChatMessage(currentSession.value.id, content);
    messages.value.push(record.payload);
  }

  /** 重新执行会话 */
  async function restartSession(): Promise<void> {
    if (!currentSession.value) return;
    const session = await restartGroupChatSession(currentSession.value.id);
    currentSession.value = session;
    members.value = session.members;
    progressSteps.value = session.progress_steps;
    connectWebSocket(session.id);
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

    if (msg.type === 'team_formation' && msg.team_config) {
      teamConfig.value = msg.team_config;
      isFormingTeam.value = true;
    }

    if (msg.type === 'team_adjusted') {
      if (msg.team_config) teamConfig.value = msg.team_config;
      if (msg.members) members.value = msg.members;
    }

    if (msg.type === 'member_status') {
      if (msg.members) {
        members.value = msg.members;
        isFormingTeam.value = false;
      }
      if (msg.role && (msg.status === 'working' || msg.status === 'thinking')) {
        typingRole.value = msg.role;
      } else if (
        msg.role &&
        ['completed', 'pending', 'idle'].includes(msg.status || '') &&
        typingRole.value === msg.role
      ) {
        typingRole.value = null;
      }
    }

    if (msg.type === 'session_update' && currentSession.value) {
      currentSession.value = {
        ...currentSession.value,
        status: msg.status || currentSession.value.status,
        progress: msg.progress ?? currentSession.value.progress,
        error_message: msg.error ?? currentSession.value.error_message,
        error_code: msg.error_code ?? currentSession.value.error_code,
        error_suggestions: msg.error_suggestions ?? currentSession.value.error_suggestions,
        raw_error: msg.raw_error ?? currentSession.value.raw_error,
      };
      if (msg.final_answer) {
        finalAnswer.value = msg.final_answer;
      }
      if (msg.status === 'pending' && msg.status) {
        startPolling(currentSession.value.id);
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
    selectedRole.value = null;
    teamConfig.value = null;
    isFormingTeam.value = false;
    finalAnswer.value = '';
  }

  function selectMember(role: string): void {
    selectedRole.value = selectedRole.value === role ? null : role;
  }

  return {
    currentSession,
    messages,
    members,
    progressSteps,
    typingRole,
    selectedRole,
    teamConfig,
    isFormingTeam,
    isLoading,
    finalAnswer,
    sessionStatus,
    progress,
    isCompleted,
    canIntervene,
    canSendMessage,
    startSession,
    loadSession,
    sendUserMessage,
    restartSession,
    connectWebSocket,
    disconnectWebSocket,
    cancelSession,
    resolveReview,
    selectMember,
    reset,
  };
});
