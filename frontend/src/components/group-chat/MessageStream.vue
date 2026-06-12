<script setup lang="ts">
import { computed, ref } from 'vue';
import StreamingText from '@/components/chat/StreamingText.vue';
import MessageAttachmentView from '@/components/group-chat/MessageAttachment.vue';
import { ROLE_BUBBLE_COLORS, type AgentMessage } from '@/api/groupChat';

const props = defineProps<{
  messages: AgentMessage[];
  typingRole?: string | null;
  filterRole?: string | null;
}>();

const displayMessages = computed(() => {
  if (!props.filterRole) return props.messages;
  return props.messages.filter(
    (m) => m.sender.role === props.filterRole || m.sender.role === 'user',
  );
});

const expandedIds = ref<Set<string>>(new Set());

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

function toggleExpand(id: string): void {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id);
  } else {
    expandedIds.value.add(id);
  }
}

function isExpanded(id: string): boolean {
  return expandedIds.value.has(id);
}

const roleLabels: Record<string, string> = {
  project_manager: '项目经理',
  researcher: '研究员',
  engineer: '工程师',
  analyst: '分析师',
  auditor: '审核员',
  user: '用户',
};
</script>

<template>
  <div class="message-stream">
    <div v-if="filterRole" class="filter-hint">仅显示 {{ filterRole }} 相关消息</div>
    <div
      v-for="msg in displayMessages"
      :key="msg.id"
      class="message-row"
      :class="{ 'message-row--user': msg.sender.role === 'user' }"
    >
      <div v-if="msg.sender.role !== 'user'" class="msg-avatar">
        {{ msg.sender.avatar }}
      </div>
      <div class="msg-body">
        <div class="msg-header">
          <span class="msg-sender">{{ msg.sender.name || roleLabels[msg.sender.role] }}</span>
          <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
        </div>
        <div
          class="msg-bubble"
          :style="{ '--bubble-color': bubbleColor(msg.sender.role) }"
        >
          <StreamingText :content="msg.content" />
          <MessageAttachmentView
            v-if="msg.attachments?.length"
            :attachments="msg.attachments"
          />
          <button
            v-if="msg.metadata?.thought || msg.metadata?.toolCalls"
            type="button"
            class="expand-btn"
            @click="toggleExpand(msg.id)"
          >
            {{ isExpanded(msg.id) ? '收起' : '查看' }}思考过程
          </button>
          <div v-if="isExpanded(msg.id)" class="thought-panel">
            <p v-if="msg.metadata?.thought">{{ msg.metadata.thought }}</p>
            <pre v-if="msg.metadata?.toolCalls">{{
              JSON.stringify(msg.metadata.toolCalls, null, 2)
            }}</pre>
          </div>
        </div>
      </div>
    </div>

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
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;

  &--user {
    flex-direction: row-reverse;

    .msg-body {
      align-items: flex-end;
    }

    .msg-bubble {
      background: #f2f3f5;
      border-color: transparent;
    }
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
  max-width: 75%;
  gap: 4px;
}

.msg-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
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
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  font-size: 14px;
  line-height: 1.6;
  color: $text-primary;
}

.expand-btn {
  margin-top: 8px;
  padding: 0;
  border: none;
  background: none;
  color: $primary-color;
  font-size: 12px;
  cursor: pointer;
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
