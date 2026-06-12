<script setup lang="ts">
import { computed, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { CircleCheck, CircleClose } from '@element-plus/icons-vue';
import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue';
import MessageAttachmentView from '@/components/group-chat/MessageAttachment.vue';
import ChartRenderer from '@/components/group-chat/ChartRenderer.vue';
import { ROLE_BUBBLE_COLORS, type AgentMessage } from '@/api/groupChat';
import {
  buildStreamItems,
  getDeliverableContent,
  getDeliverableTitle,
  getMessageVisualType,
  isLongContent,
  type MessageVisualType,
} from '@/utils/groupChatMessage';
import type { Deliverable } from '@/utils/deliverables';

const props = defineProps<{
  messages: AgentMessage[];
  typingRole?: string | null;
  filterRole?: string | null;
  highlightMessageId?: string | null;
}>();

const emit = defineEmits<{
  viewReport: [deliverable: Partial<Deliverable> & { content: string; name: string }];
}>();

const displayMessages = computed(() => {
  if (!props.filterRole) return props.messages;
  return props.messages.filter(
    (m) => m.sender.role === props.filterRole || m.sender.role === 'user',
  );
});

const streamItems = computed(() => buildStreamItems(displayMessages.value));

const expandedIds = ref<Set<string>>(new Set());
const collapsedLongIds = ref<Set<string>>(new Set());

const roleLabels: Record<string, string> = {
  project_manager: '项目经理',
  researcher: '研究员',
  engineer: '工程师',
  analyst: '分析师',
  auditor: '审核员',
  user: '用户',
  system: '系统',
};

function bubbleColor(role: string): string {
  return ROLE_BUBBLE_COLORS[role] || ROLE_BUBBLE_COLORS.system;
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function toggleThought(id: string): void {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id);
  } else {
    expandedIds.value.add(id);
  }
}

function isThoughtExpanded(id: string): boolean {
  return expandedIds.value.has(id);
}

function visualType(msg: AgentMessage): MessageVisualType {
  return getMessageVisualType(msg);
}

function displayContent(msg: AgentMessage): string {
  const vt = visualType(msg);
  if (vt === 'deliverable') {
    return getDeliverableContent(msg);
  }
  return msg.content;
}

function shouldCollapse(msg: AgentMessage): boolean {
  const content = displayContent(msg);
  return visualType(msg) === 'deliverable' && isLongContent(content) && !collapsedLongIds.value.has(msg.id);
}

function expandFull(msg: AgentMessage): void {
  openReport(msg);
}

function openReport(msg: AgentMessage, content?: string, name?: string): void {
  const body = content || displayContent(msg);
  emit('viewReport', {
    id: msg.id,
    messageId: msg.id,
    name: name || getDeliverableTitle(msg),
    content: body,
    category: msg.type === 'task_complete' ? 'final' : 'intermediate',
    type: 'text',
    fileType: 'md',
    createdBy: msg.sender.name || msg.sender.role,
    createdAt: msg.timestamp,
    size: new Blob([body]).size,
  });
}

async function copyContent(content: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(content);
    ElMessage.success('已复制');
  } catch {
    ElMessage.error('复制失败');
  }
}

function downloadContent(msg: AgentMessage): void {
  const content = displayContent(msg);
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${getDeliverableTitle(msg)}.md`;
  link.click();
  URL.revokeObjectURL(url);
  ElMessage.success('已下载');
}

function handleAttachmentDetail(content: string, name: string, msg: AgentMessage): void {
  openReport(msg, content, name);
}

function handleChartEnlarge(config: Record<string, unknown>, name: string, msg: AgentMessage): void {
  emit('viewReport', {
    id: `${msg.id}-chart`,
    messageId: msg.id,
    name,
    content: JSON.stringify(config, null, 2),
    category: 'chart',
    type: 'chart',
    fileType: 'chart',
    chartConfig: config,
    createdBy: msg.sender.name || msg.sender.role,
    createdAt: msg.timestamp,
    size: 0,
  });
}

/** 识别消息级图表配置（附件内图表由 MessageAttachment 渲染） */
function detectChartConfig(msg: AgentMessage): Record<string, unknown> | null {
  if (msg.contentType === 'chart' && msg.chartConfig) {
    return msg.chartConfig as Record<string, unknown>;
  }
  return null;
}
</script>

<template>
  <div class="message-stream">
    <div v-if="filterRole" class="filter-hint">仅显示 {{ filterRole }} 相关消息</div>

    <template v-for="(item, idx) in streamItems" :key="item.kind === 'phase' ? `phase-${idx}` : item.message!.id">
      <!-- 阶段分割线 -->
      <div v-if="item.kind === 'phase' && item.phase" class="phase-divider">
        <span class="phase-line" />
        <span class="phase-label">{{ item.phase.label }}</span>
        <span class="phase-line" />
      </div>

      <!-- 系统通知 -->
      <div
        v-else-if="item.message && visualType(item.message) === 'system'"
        :id="`msg-${item.message.id}`"
        class="system-notice"
        :class="{ 'message-highlight': highlightMessageId === item.message.id }"
      >
        {{ item.message.content }}
      </div>

      <!-- 普通/交付/审核/用户消息 -->
      <div
        v-else-if="item.message"
        :id="`msg-${item.message.id}`"
        class="message-row"
        :class="{
          'message-row--user': item.message.sender.role === 'user',
          'message-row--deliverable': visualType(item.message) === 'deliverable',
          'message-row--review-pass': visualType(item.message) === 'review_pass',
          'message-row--review-reject': visualType(item.message) === 'review_reject',
          'message-highlight': highlightMessageId === item.message.id,
        }"
      >
        <div v-if="item.message.sender.role !== 'user'" class="msg-avatar">
          {{ item.message.sender.avatar }}
        </div>
        <div class="msg-body">
          <div class="msg-header">
            <span v-if="visualType(item.message) === 'deliverable'" class="msg-tag msg-tag--deliverable">
              交付物
            </span>
            <span
              v-if="visualType(item.message) === 'review_pass' || visualType(item.message) === 'review_reject'"
              class="msg-tag"
              :class="visualType(item.message) === 'review_pass' ? 'msg-tag--pass' : 'msg-tag--reject'"
            >
              审核
            </span>
            <span class="msg-sender">{{
              item.message.sender.name || roleLabels[item.message.sender.role]
            }}</span>
            <span class="msg-time">{{ formatTime(item.message.timestamp) }}</span>
          </div>

          <div
            class="msg-bubble"
            :style="{ '--bubble-color': bubbleColor(item.message.sender.role) }"
          >
            <!-- 审核通过/打回图标 -->
            <div
              v-if="visualType(item.message) === 'review_pass'"
              class="review-badge review-badge--pass"
            >
              <el-icon><CircleCheck /></el-icon>
              审核通过
            </div>
            <div
              v-if="visualType(item.message) === 'review_reject'"
              class="review-badge review-badge--reject"
            >
              <el-icon><CircleClose /></el-icon>
              审核不通过
            </div>

            <!-- 图表内嵌渲染 -->
            <ChartRenderer
              v-if="detectChartConfig(item.message)"
              :config="detectChartConfig(item.message)!"
              :title="getDeliverableTitle(item.message)"
              :show-toolbar="true"
              @enlarge="handleChartEnlarge(detectChartConfig(item.message)!, getDeliverableTitle(item.message), item.message)"
            />

            <!-- Markdown 正文 -->
            <template v-else-if="shouldCollapse(item.message)">
              <MarkdownRenderer :content="displayContent(item.message).slice(0, 300) + '...'" compact />
              <button type="button" class="expand-full-btn" @click="expandFull(item.message)">
                展开查看全文
              </button>
            </template>
            <MarkdownRenderer v-else :content="displayContent(item.message)" compact />

            <MessageAttachmentView
              v-if="item.message.attachments?.length"
              :attachments="item.message.attachments"
              @view-detail="(c, n) => handleAttachmentDetail(c, n, item.message!)"
              @view-chart="(c, n) => handleChartEnlarge(c, n, item.message!)"
            />

            <!-- 交付物操作栏 -->
            <div v-if="visualType(item.message) === 'deliverable'" class="deliverable-actions">
              <button type="button" class="action-btn" @click="openReport(item.message)">
                查看详情
              </button>
              <button type="button" class="action-btn" @click="downloadContent(item.message)">
                下载
              </button>
              <button
                type="button"
                class="action-btn"
                @click="copyContent(displayContent(item.message))"
              >
                复制
              </button>
            </div>

            <button
              v-if="item.message.metadata?.thought || item.message.metadata?.toolCalls"
              type="button"
              class="expand-btn"
              @click="toggleThought(item.message.id)"
            >
              {{ isThoughtExpanded(item.message.id) ? '收起' : '查看' }}思考过程
            </button>
            <div v-if="isThoughtExpanded(item.message.id)" class="thought-panel">
              <p v-if="item.message.metadata?.thought">{{ item.message.metadata.thought }}</p>
              <pre v-if="item.message.metadata?.toolCalls">{{
                JSON.stringify(item.message.metadata.toolCalls, null, 2)
              }}</pre>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-if="typingRole" class="typing-indicator">
      <span class="typing-avatar">{{ typingRole === 'auditor' ? '✅' : '💬' }}</span>
      <span class="typing-text">正在输入...</span>
      <span class="typing-dots"><span /><span /><span /></span>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.message-stream {
  flex: 1;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.phase-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0;
}

.phase-line {
  flex: 1;
  height: 1px;
  background: $border-color;
}

.phase-label {
  font-size: 12px;
  color: $text-secondary;
  white-space: nowrap;
  padding: 2px 10px;
  background: #f7f8fa;
  border-radius: 12px;
}

.system-notice {
  text-align: center;
  font-size: 12px;
  color: $text-secondary;
  padding: 4px 0;
}

.message-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  transition: background 0.3s;

  &--user {
    flex-direction: row-reverse;

    .msg-body {
      align-items: flex-end;
    }

    .msg-bubble {
      background: $primary-color;
      color: #fff;
      border-left-color: transparent;
      border-radius: 12px 12px 4px 12px;

      :deep(.markdown-body) {
        color: #fff;

        a {
          color: #ffe8dc;
        }

        code {
          background: rgba(255, 255, 255, 0.15);
          color: #fff;
        }
      }
    }
  }

  &--deliverable .msg-bubble {
    background: $bg-white;
    border-left-width: 4px;
    max-width: 100%;
  }

  &--review-pass .msg-bubble {
    border-left-color: $success-color;
    border: 1px solid rgba($success-color, 0.3);
    border-left-width: 4px;
  }

  &--review-reject .msg-bubble {
    border-left-color: $danger-color;
    border: 1px solid rgba($danger-color, 0.3);
    border-left-width: 4px;
  }
}

.message-highlight {
  animation: highlight-pulse 1.5s ease;
}

@keyframes highlight-pulse {
  0%,
  100% {
    background: transparent;
  }
  30% {
    background: rgba($primary-color, 0.08);
    border-radius: 8px;
  }
}

.msg-avatar {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.msg-body {
  display: flex;
  flex-direction: column;
  max-width: 85%;
  gap: 4px;
}

.msg-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  flex-wrap: wrap;
}

.msg-tag {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;

  &--deliverable {
    background: rgba($primary-color, 0.1);
    color: $primary-color;
  }

  &--pass {
    background: rgba($success-color, 0.1);
    color: $success-color;
  }

  &--reject {
    background: rgba($danger-color, 0.1);
    color: $danger-color;
  }
}

.msg-sender {
  font-weight: 500;
  color: $text-primary;
}

.msg-time {
  color: $text-secondary;
}

.msg-bubble {
  padding: 12px 14px;
  border-radius: 12px;
  border-left: 3px solid var(--bubble-color, #1677ff);
  background: $bg-white;
  font-size: 14px;
  line-height: 1.6;
  color: $text-primary;
}

.review-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;

  &--pass {
    color: $success-color;
  }

  &--reject {
    color: $danger-color;
  }
}

.deliverable-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid $border-color;
}

.action-btn,
.expand-btn,
.expand-full-btn {
  padding: 4px 10px;
  font-size: 12px;
  color: $primary-color;
  background: transparent;
  border: 1px solid rgba($primary-color, 0.35);
  border-radius: 4px;
  cursor: pointer;

  &:hover {
    background: rgba($primary-color, 0.06);
  }
}

.expand-btn,
.expand-full-btn {
  margin-top: 8px;
  border: none;
  padding: 0;
  background: none;
}

.thought-panel {
  margin-top: 8px;
  padding: 8px;
  background: #f7f8fa;
  border-radius: 6px;
  font-size: 12px;
  color: $text-secondary;

  pre {
    margin: 4px 0 0;
    white-space: pre-wrap;
    word-break: break-all;
  }
}

.filter-hint {
  padding: 6px 12px;
  font-size: 12px;
  color: $primary-color;
  background: rgba($primary-color, 0.06);
  border-radius: 6px;
  margin-bottom: 8px;
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  color: $text-secondary;
  font-size: 13px;
}

.typing-dots {
  display: flex;
  gap: 3px;

  span {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: $text-secondary;
    animation: blink 1.2s infinite;

    &:nth-child(2) {
      animation-delay: 0.2s;
    }

    &:nth-child(3) {
      animation-delay: 0.4s;
    }
  }
}

@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.3;
  }
  40% {
    opacity: 1;
  }
}
</style>
