<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import {
  ArrowLeft,
  CopyDocument,
  Delete,
  Plus,
  Position,
  RefreshRight,
  VideoPause,
} from '@element-plus/icons-vue';
import StreamingText from '@/components/chat/StreamingText.vue';
import CitationPanel from '@/components/knowledge/CitationPanel.vue';
import {
  chatKnowledgeStream,
  deleteRagChatSession,
  getRagChatHistory,
  getRagChatSessions,
} from '@/api/rag';
import type { ChatStreamMessage, CitationSource, RagChatHistoryItem } from '@/api/rag';
import { useRagStore } from '@/stores/rag';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: CitationSource[];
}

const route = useRoute();
const router = useRouter();
const ragStore = useRagStore();

const kbId = computed(() => Number(route.params.id));

const sessionId = ref('');
const sessions = ref<{ session_id: string; last_message: string; updated_at?: string }[]>([]);
const messages = ref<ChatMessage[]>([]);
const inputQuery = ref('');
const isStreaming = ref(false);
const activeCitationId = ref<number | null>(null);
const currentSources = ref<CitationSource[]>([]);

const useRag = ref(true);
const showFilters = ref(false);
const filterDepartment = ref('');
const filterFileType = ref('');
const filterDateRange = ref<[string, string] | null>(null);
const abortController = ref<AbortController | null>(null);

const fileTypeOptions = ['.pdf', '.docx', '.doc', '.md', '.txt', '.html', '.xlsx', '.pptx', '.csv'];

function buildSearchFilters(): Record<string, unknown> | undefined {
  const filters: Record<string, unknown> = {};
  if (filterDepartment.value.trim()) {
    filters.department = filterDepartment.value.trim();
  }
  if (filterFileType.value) {
    filters.file_type = filterFileType.value;
  }
  if (filterDateRange.value) {
    const [start, end] = filterDateRange.value;
    filters.time_start = `${start}T00:00:00`;
    filters.time_end = `${end}T23:59:59`;
  }
  return Object.keys(filters).length > 0 ? filters : undefined;
}

function clearFilters(): void {
  filterDepartment.value = '';
  filterFileType.value = '';
  filterDateRange.value = null;
}

/** 加载知识库信息 */
async function loadKbInfo(): Promise<void> {
  await ragStore.fetchKnowledgeBase(kbId.value);
}

async function loadSessions(): Promise<void> {
  sessions.value = await getRagChatSessions(kbId.value);
}

function handleNewSession(): void {
  sessionId.value = `kb-${kbId.value}-${Date.now()}`;
  messages.value = [];
  currentSources.value = [];
}

async function loadSessionHistory(targetSessionId: string): Promise<void> {
  sessionId.value = targetSessionId;
  const { items } = await getRagChatHistory(kbId.value, {
    session_id: targetSessionId,
    limit: 200,
  });
  messages.value = items.map((item: RagChatHistoryItem) => ({
    id: `history-${item.id}`,
    role: item.message_type === 'user' ? 'user' : 'assistant',
    content: item.content,
    sources: (item.metadata?.sources as CitationSource[]) || [],
  }));
  const lastAssistant = [...messages.value].reverse().find((m) => m.role === 'assistant');
  currentSources.value = lastAssistant?.sources || [];
}

async function handleDeleteSession(targetSessionId: string): Promise<void> {
  await deleteRagChatSession(kbId.value, targetSessionId);
  if (sessionId.value === targetSessionId) {
    handleNewSession();
  }
  await loadSessions();
}

onMounted(async () => {
  await loadKbInfo();
  handleNewSession();
  await loadSessions();
});

/** 处理 SSE 消息 */
function handleStreamMessage(data: unknown): void {
  const msg = data as ChatStreamMessage;

  if (msg.type === 'citation' && msg.sources) {
    currentSources.value = msg.sources;
    const lastAssistant = [...messages.value].reverse().find((m) => m.role === 'assistant');
    if (lastAssistant) {
      lastAssistant.sources = msg.sources;
    }
    return;
  }

  if (msg.type === 'done') {
    isStreaming.value = false;
    if (msg.session_id) {
      sessionId.value = msg.session_id;
      void loadSessions();
    }
    return;
  }

  if (msg.type === 'error') {
    ElMessage.error(msg.message || '问答出错');
    isStreaming.value = false;
    return;
  }

  const tokenContent = msg.type === 'token' ? msg.content : msg.content;
  if (tokenContent) {
    const lastAssistant = [...messages.value].reverse().find((m) => m.role === 'assistant');
    if (lastAssistant) {
      lastAssistant.content += tokenContent;
    }
  }
}

/** 发送问题 */
async function streamQuery(query: string, appendUserMessage: boolean): Promise<void> {
  if (!query || isStreaming.value) {
    return;
  }

  if (!sessionId.value) {
    handleNewSession();
  }

  if (appendUserMessage) {
    messages.value.push({
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
    });
  }

  const assistantMsg: ChatMessage = {
    id: `assistant-${Date.now()}`,
    role: 'assistant',
    content: '',
    sources: [],
  };
  messages.value.push(assistantMsg);

  inputQuery.value = '';
  isStreaming.value = true;
  currentSources.value = [];
  activeCitationId.value = null;

  abortController.value?.abort();
  abortController.value = new AbortController();

  try {
    await chatKnowledgeStream(
      kbId.value,
      {
        query,
        use_rag: useRag.value,
        session_id: sessionId.value,
        filters: buildSearchFilters(),
      },
      handleStreamMessage,
      abortController.value.signal,
    );
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      ElMessage.error('问答请求失败');
    }
  } finally {
    isStreaming.value = false;
  }
}

async function handleSend(): Promise<void> {
  const query = inputQuery.value.trim();
  if (!query) {
    return;
  }
  inputQuery.value = '';
  await streamQuery(query, true);
}

async function handleRegenerateLast(): Promise<void> {
  if (isStreaming.value) {
    return;
  }
  const lastUser = [...messages.value].reverse().find((msg) => msg.role === 'user');
  if (!lastUser) {
    ElMessage.warning('暂无可重新生成的问题');
    return;
  }

  const lastMessage = messages.value[messages.value.length - 1];
  if (lastMessage && lastMessage.role === 'assistant') {
    messages.value.pop();
  }

  await streamQuery(lastUser.content, false);
}

async function handleCopyAnswer(content: string): Promise<void> {
  if (!content.trim()) {
    ElMessage.warning('暂无可复制内容');
    return;
  }
  try {
    await navigator.clipboard.writeText(content);
    ElMessage.success('已复制完整回答');
  } catch (error) {
    console.error('[Copy Answer Error]', error);
    ElMessage.error('复制失败');
  }
}

/** 中断当前回答 */
function handleAbort(): void {
  abortController.value?.abort();
  isStreaming.value = false;
  ElMessage.info('已停止生成');
}

/** 点击引用来源，跳转到文档详情并打开预览 */
function handleCitationSelect(source: CitationSource): void {
  activeCitationId.value = source.id;
  if (!source.document_id) {
    ElMessage.warning('无法定位原文档');
    return;
  }
  router.push({
    name: 'KnowledgeDetail',
    params: { id: kbId.value },
    query: {
      docId: String(source.document_id),
      chunkIndex: source.chunk_index !== undefined ? String(source.chunk_index) : undefined,
      highlight: '1',
    },
  });
}

/** 回车发送 */
function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleSend();
  }
}

function goBack(): void {
  router.push({ name: 'KnowledgeDetail', params: { id: kbId.value } });
}

onUnmounted(() => {
  abortController.value?.abort();
});
</script>

<template>
  <div class="knowledge-chat">
    <div class="chat-header flex-between">
      <div class="header-left flex-center">
        <el-button text :icon="ArrowLeft" @click="goBack">返回文档</el-button>
        <h2 class="chat-title">{{ ragStore.currentKb?.name || '知识库问答' }}</h2>
      </div>
      <div class="header-right flex-center">
        <span class="mode-label">知识库增强</span>
        <el-switch v-model="useRag" :disabled="isStreaming" />
        <el-button v-if="isStreaming" type="danger" plain :icon="VideoPause" @click="handleAbort">
          停止生成
        </el-button>
      </div>
    </div>

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
        <div v-if="useRag" class="filter-panel">
          <div class="filter-header flex-between">
            <span>检索过滤</span>
            <el-button text size="small" @click="showFilters = !showFilters">
              {{ showFilters ? '收起' : '展开' }}
            </el-button>
          </div>
          <div v-show="showFilters" class="filter-body">
            <el-input
              v-model="filterDepartment"
              placeholder="部门（角色名）"
              clearable
              size="small"
            />
            <el-select v-model="filterFileType" placeholder="文档类型" clearable size="small">
              <el-option v-for="type in fileTypeOptions" :key="type" :label="type" :value="type" />
            </el-select>
            <el-date-picker
              v-model="filterDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              value-format="YYYY-MM-DD"
            />
            <el-button size="small" @click="clearFilters">重置</el-button>
          </div>
        </div>

        <div class="message-list">
          <el-empty v-if="messages.length === 0" description="输入问题开始与知识库对话" />

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
                <div class="assistant-actions">
                  <el-button
                    text
                    size="small"
                    :icon="CopyDocument"
                    @click="handleCopyAnswer(msg.content)"
                  >
                    复制完整回答
                  </el-button>
                  <el-button
                    v-if="msg === messages[messages.length - 1] && !isStreaming"
                    text
                    size="small"
                    :icon="RefreshRight"
                    @click="handleRegenerateLast"
                  >
                    重新生成
                  </el-button>
                </div>
              </template>
            </div>
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
              :icon="RefreshRight"
              :disabled="isStreaming || !messages.some((msg) => msg.role === 'user')"
              @click="handleRegenerateLast"
            >
              重新生成上次回答
            </el-button>
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
        <CitationPanel
          :sources="
            currentSources.length > 0
              ? currentSources
              : messages.filter((m) => m.role === 'assistant').at(-1)?.sources || []
          "
          :active-id="activeCitationId"
          @select="handleCitationSelect"
        />
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.knowledge-chat {
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
}

.chat-header {
  margin-bottom: 16px;
  flex-shrink: 0;
}

.header-left {
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
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid $border-color;
  display: flex;
  flex-direction: column;
  background: $bg-color;
}

.sidebar-header {
  padding: 12px 16px;
  border-bottom: 1px solid $border-color;

  h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: $text-primary;
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
  margin-bottom: 4px;

  &:hover {
    background: rgba($primary-color, 0.06);
  }

  &.active {
    background: rgba($primary-color, 0.12);
  }
}

.session-text {
  flex: 1;
  font-size: 13px;
  color: $text-secondary;
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

.filter-panel {
  padding: 12px 16px 0;
  border-bottom: 1px solid $border-color;
}

.filter-header {
  font-size: 13px;
  font-weight: 500;
  color: $text-primary;
  margin-bottom: 8px;
}

.filter-body {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding-bottom: 12px;
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

.chat-input-area {
  padding: 16px;
  flex-shrink: 0;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.chat-sidebar {
  width: 320px;
  flex-shrink: 0;
  background: $bg-color;
}

.assistant-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
</style>
