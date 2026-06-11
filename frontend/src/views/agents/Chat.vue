<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import {
  ArrowLeft,
  Delete,
  Loading,
  Plus,
  Position,
  Setting,
  VideoPause,
} from '@element-plus/icons-vue';
import StreamingText from '@/components/chat/StreamingText.vue';
import ToolCallPanel from '@/components/agent/ToolCallPanel.vue';
import ApiKeyHintBanner from '@/components/settings/ApiKeyHintBanner.vue';
import {
  chatAgentStream,
  deleteAgentSession,
  getAgentHistory,
  getAgentSessions,
} from '@/api/agent';
import type { AgentChatStreamMessage, ChatHistoryItem, ToolCallStep } from '@/api/agent';
import { useAgentStore } from '@/stores/agent';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolSteps?: ToolCallStep[];
}

const route = useRoute();
const router = useRouter();
const agentStore = useAgentStore();

const agentId = computed(() => Number(route.params.id));
const sessionId = ref('');
const messages = ref<ChatMessage[]>([]);
const inputQuery = ref('');
const isStreaming = ref(false);
const thinkingText = ref('');
const currentToolSteps = ref<ToolCallStep[]>([]);
const activeToolSteps = ref<ToolCallStep[]>([]);

const sessions = ref<{ session_id: string; last_message: string; updated_at?: string }[]>([]);

let abortController: AbortController | null = null;

async function loadSessions(): Promise<void> {
  sessions.value = await getAgentSessions(agentId.value);
}

async function loadSessionHistory(targetSessionId: string): Promise<void> {
  sessionId.value = targetSessionId;
  const { items } = await getAgentHistory(agentId.value, {
    session_id: targetSessionId,
    limit: 200,
  });
  messages.value = items.map((item: ChatHistoryItem) => ({
    id: `history-${item.id}`,
    role: item.message_type === 'user' ? 'user' : 'assistant',
    content: item.content,
    toolSteps: (item.metadata?.intermediate_steps as ToolCallStep[]) || [],
  }));
}

function handleNewSession(): void {
  sessionId.value = `agent-${agentId.value}-${Date.now()}`;
  messages.value = [];
  activeToolSteps.value = [];
}

async function handleDeleteSession(targetSessionId: string): Promise<void> {
  await deleteAgentSession(agentId.value, targetSessionId);
  if (sessionId.value === targetSessionId) {
    handleNewSession();
  }
  await loadSessions();
}

function handleStreamMessage(msg: AgentChatStreamMessage): void {
  if (msg.type === 'model_fallback') {
    ElMessage.warning(msg.content || '已自动切换模型');
    return;
  }

  if (msg.type === 'thinking') {
    thinkingText.value = msg.content || '正在分析问题...';
    return;
  }

  if (msg.type === 'tool_start') {
    thinkingText.value = msg.content || `正在调用 ${msg.tool_label || msg.tool_name}...`;
    return;
  }

  if (msg.type === 'tool_end' && msg.intermediate_step) {
    const step: ToolCallStep = {
      ...msg.intermediate_step,
      tool_label: msg.tool_label || msg.tool_name,
    };
    currentToolSteps.value.push(step);
    activeToolSteps.value = [...currentToolSteps.value];

    const lastAssistant = [...messages.value].reverse().find((m) => m.role === 'assistant');
    if (lastAssistant) {
      lastAssistant.toolSteps = [...currentToolSteps.value];
    }
    thinkingText.value = '';
    return;
  }

  if (msg.type === 'done') {
    isStreaming.value = false;
    thinkingText.value = '';
    if (msg.session_id) {
      sessionId.value = msg.session_id;
      void loadSessions();
    }
    if (msg.intermediate_steps) {
      activeToolSteps.value = msg.intermediate_steps;
    }
    return;
  }

  if (msg.type === 'error') {
    const errorText = msg.message || '对话出错，请稍后重试';
    const lastAssistant = [...messages.value].reverse().find((m) => m.role === 'assistant');
    if (lastAssistant) {
      lastAssistant.content = errorText;
    }
    ElMessage.error(errorText);
    isStreaming.value = false;
    thinkingText.value = '';
    return;
  }

  if (msg.content) {
    thinkingText.value = '';
    const lastAssistant = [...messages.value].reverse().find((m) => m.role === 'assistant');
    if (lastAssistant) {
      lastAssistant.content += msg.content;
    }
  }
}

async function loadAgent(): Promise<void> {
  await agentStore.fetchAgent(agentId.value);
  handleNewSession();
  await loadSessions();
}

onMounted(() => {
  loadAgent();
});

async function handleSend(): Promise<void> {
  const query = inputQuery.value.trim();
  if (!query || isStreaming.value) {
    return;
  }

  messages.value.push({
    id: `user-${Date.now()}`,
    role: 'user',
    content: query,
  });

  messages.value.push({
    id: `assistant-${Date.now()}`,
    role: 'assistant',
    content: '',
    toolSteps: [],
  });

  inputQuery.value = '';
  isStreaming.value = true;
  currentToolSteps.value = [];
  activeToolSteps.value = [];
  thinkingText.value = '正在分析问题...';

  abortController?.abort();
  abortController = new AbortController();

  try {
    await chatAgentStream(
      agentId.value,
      { query, session_id: sessionId.value },
      handleStreamMessage,
      abortController.signal,
    );
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      ElMessage.error('对话请求失败');
      console.error('[Agent Chat Error]', error);
    }
  } finally {
    isStreaming.value = false;
    thinkingText.value = '';
  }
}

function handleAbort(): void {
  abortController?.abort();
  abortController = null;
  isStreaming.value = false;
  thinkingText.value = '';
  ElMessage.info('已停止生成');
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleSend();
  }
}

function goBack(): void {
  router.push({ name: 'AgentList' });
}

function goConfig(): void {
  router.push({ name: 'AgentConfig', params: { id: agentId.value } });
}

onUnmounted(() => {
  abortController?.abort();
});
</script>

<template>
  <div class="agent-chat">
    <div class="chat-header flex-between">
      <div class="header-left flex-center">
        <el-button text :icon="ArrowLeft" @click="goBack">返回列表</el-button>
        <h2 class="chat-title">{{ agentStore.currentAgent?.name || '智能体对话' }}</h2>
      </div>
      <div class="header-actions">
        <el-button text :icon="Setting" @click="goConfig">配置</el-button>
        <el-button v-if="isStreaming" type="danger" plain :icon="VideoPause" @click="handleAbort">
          停止生成
        </el-button>
      </div>
    </div>

    <ApiKeyHintBanner scene="agent" class="chat-api-key-hint" />

    <div class="chat-layout">
      <div class="session-sidebar">
        <div class="sidebar-header flex-between">
          <h3>会话</h3>
          <el-button text :icon="Plus" @click="handleNewSession">新建</el-button>
        </div>
        <div class="session-list">
          <div
            v-for="session in sessions"
            :key="session.session_id"
            class="session-item"
            :class="{ active: session.session_id === sessionId }"
            @click="loadSessionHistory(session.session_id)"
          >
            <div class="session-text">{{ session.last_message || '新会话' }}</div>
            <el-button
              text
              type="danger"
              :icon="Delete"
              @click.stop="handleDeleteSession(session.session_id)"
            />
          </div>
        </div>
      </div>

      <div class="chat-main">
        <div class="message-list">
          <el-empty v-if="messages.length === 0" description="输入问题开始与智能体对话" />

          <div v-for="msg in messages" :key="msg.id" class="message-item" :class="msg.role">
            <div class="message-bubble">
              <template v-if="msg.role === 'user'">
                <p class="user-text">{{ msg.content }}</p>
              </template>
              <template v-else>
                <StreamingText
                  :content="msg.content"
                  :streaming="isStreaming && msg === messages[messages.length - 1]"
                />
              </template>
            </div>
          </div>

          <div v-if="thinkingText && isStreaming" class="thinking-banner">
            <el-icon class="is-loading"><Loading /></el-icon>
            {{ thinkingText }}
          </div>
        </div>

        <div class="chat-input-area">
          <el-input
            v-model="inputQuery"
            type="textarea"
            :rows="3"
            placeholder="输入您的问题，Enter 发送，Shift+Enter 换行"
            :disabled="isStreaming"
            @keydown="handleKeydown"
          />
          <div class="input-actions">
            <el-button
              type="primary"
              :icon="Position"
              :loading="isStreaming"
              :disabled="!inputQuery.trim()"
              @click="handleSend"
            >
              {{ isStreaming ? '生成中...' : '发送' }}
            </el-button>
          </div>
        </div>
      </div>

      <div class="chat-sidebar">
        <div class="sidebar-header">
          <h3>工具调用</h3>
        </div>
        <ToolCallPanel
          :steps="activeToolSteps"
          :thinking-text="thinkingText"
          :is-active="isStreaming"
        />
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.agent-chat {
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
}

.chat-header {
  margin-bottom: 12px;
  flex-shrink: 0;
}

.chat-api-key-hint {
  margin-bottom: 12px;
  flex-shrink: 0;
}

.header-left {
  gap: 8px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.chat-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: $text-primary;
}

.chat-layout {
  flex: 1;
  display: flex;
  gap: 0;
  min-height: 0;
  border: none;
  border-radius: $border-radius-lg;
  box-shadow: $shadow-card;
  overflow: hidden;
  background: #fff;
}

.session-sidebar {
  width: 260px;
  border-right: 1px solid $border-color;
  display: flex;
  flex-direction: column;
  background: $bg-color;

  .sidebar-header {
    padding: 12px 16px;

    h3 {
      margin: 0;
      font-size: 15px;
    }
  }
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 10px;
  border-radius: $border-radius-md;
  cursor: pointer;
  margin-bottom: 6px;

  &.active {
    background: rgba($primary-color, 0.12);
  }

  &:hover {
    background: rgba($primary-color, 0.08);
  }
}

.session-text {
  flex: 1;
  font-size: 13px;
  color: $text-regular;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message-item {
  margin-bottom: 16px;
  display: flex;

  &.user {
    justify-content: flex-end;

    .message-bubble {
      background: $primary-color;
      color: #fff;
      border-radius: $border-radius-lg $border-radius-lg $border-radius-sm $border-radius-lg;
      max-width: 70%;
    }
  }

  &.assistant {
    justify-content: flex-start;

    .message-bubble {
      background: $bg-white;
      color: $text-primary;
      border-radius: $border-radius-lg $border-radius-lg $border-radius-lg $border-radius-sm;
      max-width: 85%;
      box-shadow: $shadow-soft;
    }
  }
}

.message-bubble {
  padding: 12px 16px;
}

.user-text {
  margin: 0;
  line-height: 1.6;
  white-space: pre-wrap;
}

.thinking-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba($primary-color, 0.08);
  border-radius: $border-radius-pill;
  color: $text-regular;
  font-size: 14px;
  margin-top: 8px;
}

.chat-input-area {
  padding: 16px;
  flex-shrink: 0;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.chat-sidebar {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: $bg-color;
}

.sidebar-header {
  padding: 12px 16px;

  h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
  }
}
</style>
