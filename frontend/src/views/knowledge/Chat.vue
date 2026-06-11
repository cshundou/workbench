<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, Position, VideoPause } from '@element-plus/icons-vue';
import StreamingText from '@/components/chat/StreamingText.vue';
import CitationPanel from '@/components/knowledge/CitationPanel.vue';
import { chatKnowledgeStream } from '@/api/rag';
import type { ChatStreamMessage, CitationSource } from '@/api/rag';
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

const messages = ref<ChatMessage[]>([]);
const inputQuery = ref('');
const isStreaming = ref(false);
const activeCitationId = ref<number | null>(null);
const currentSources = ref<CitationSource[]>([]);

const useRag = ref(true);
const abortController = ref<AbortController | null>(null);

/** 加载知识库信息 */
async function loadKbInfo(): Promise<void> {
  await ragStore.fetchKnowledgeBase(kbId.value);
}

loadKbInfo();

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
    return;
  }

  if (msg.type === 'error') {
    ElMessage.error(msg.message || '问答出错');
    isStreaming.value = false;
    return;
  }

  if (msg.content) {
    const lastAssistant = [...messages.value].reverse().find((m) => m.role === 'assistant');
    if (lastAssistant) {
      lastAssistant.content += msg.content;
    }
  }
}

/** 发送问题 */
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
      { query, use_rag: useRag.value },
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

/** 中断当前回答 */
function handleAbort(): void {
  abortController.value?.abort();
  isStreaming.value = false;
  ElMessage.info('已停止生成');
}

/** 点击引用来源 */
function handleCitationSelect(source: CitationSource): void {
  activeCitationId.value = source.id;
  ElMessage.info(`查看引用 [${source.id}]：${source.document_name}`);
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
        <el-button
          v-if="isStreaming"
          type="danger"
          plain
          :icon="VideoPause"
          @click="handleAbort"
        >
          停止生成
        </el-button>
      </div>
    </div>

    <div class="chat-layout">
      <div class="chat-main">
        <div class="message-list">
          <el-empty
            v-if="messages.length === 0"
            description="输入问题开始与知识库对话"
          />

          <div
            v-for="msg in messages"
            :key="msg.id"
            class="message-item"
            :class="msg.role"
          >
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
        <CitationPanel
          :sources="currentSources.length > 0 ? currentSources : (messages.filter(m => m.role === 'assistant').at(-1)?.sources || [])"
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
  width: 320px;
  flex-shrink: 0;
  background: $bg-color;
}
</style>
