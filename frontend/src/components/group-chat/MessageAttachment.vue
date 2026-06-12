<script setup lang="ts">
import { ref } from 'vue';
import type { MessageAttachment } from '@/api/groupChat';

defineProps<{
  attachments: MessageAttachment[];
}>();

const expanded = ref<Record<number, boolean>>({});

function toggle(idx: number): void {
  expanded.value[idx] = !expanded.value[idx];
}

function contentPreview(att: MessageAttachment): string {
  const c = att.content;
  if (typeof c === 'string') {
    return c.length > 120 ? `${c.slice(0, 120)}...` : c;
  }
  return JSON.stringify(c).slice(0, 120);
}
</script>

<template>
  <div class="attachments">
    <div
      v-for="(att, idx) in attachments"
      :key="idx"
      class="attachment-item"
      @click="toggle(idx)"
    >
      <div class="attachment-header">
        <span class="attachment-type">{{ att.type }}</span>
        <span class="attachment-name">{{ att.name }}</span>
        <span class="attachment-toggle">{{ expanded[idx] ? '收起' : '展开' }}</span>
      </div>
      <div v-if="expanded[idx]" class="attachment-body">
        <pre v-if="att.type === 'code'" class="code-block"><code>{{ att.content }}</code></pre>
        <div v-else-if="att.type === 'table'" class="table-preview">{{ contentPreview(att) }}</div>
        <div v-else-if="att.type === 'chart'" class="chart-preview">
          📊 {{ att.name }}
          <pre>{{ JSON.stringify(att.content, null, 2) }}</pre>
        </div>
        <div v-else class="text-preview">{{ contentPreview(att) }}</div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.attachments {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.attachment-item {
  border: 1px solid $border-color;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
}

.attachment-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: #fafafa;
  font-size: 12px;
}

.attachment-type {
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba($primary-color, 0.1);
  color: $primary-color;
  text-transform: uppercase;
  font-size: 10px;
}

.attachment-name {
  flex: 1;
  color: $text-primary;
  font-weight: 500;
}

.attachment-toggle {
  color: $text-secondary;
}

.attachment-body {
  padding: 10px;
  font-size: 12px;
  color: $text-secondary;
  border-top: 1px solid $border-color;
}

.code-block {
  margin: 0;
  padding: 8px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
}

.text-preview,
.table-preview {
  white-space: pre-wrap;
  word-break: break-word;
}

.chart-preview pre {
  margin-top: 6px;
  font-size: 11px;
}
</style>
