<script setup lang="ts">
import { computed } from 'vue';
import type { MessageAttachment, ProgressStep } from '@/api/groupChat';

const props = defineProps<{
  progress: number;
  steps: ProgressStep[];
  deliverables: Record<string, unknown>[];
}>();

const allAttachments = computed<MessageAttachment[]>(() => {
  const items: MessageAttachment[] = [];
  for (const d of props.deliverables) {
    const atts = (d.attachments as MessageAttachment[]) || [];
    items.push(...atts);
    if (d.content && !atts.length) {
      items.push({
        type: 'text',
        name: String(d.role || '交付物'),
        content: d.content,
      });
    }
  }
  return items;
});

function stepIcon(status: string): string {
  if (status === 'completed') return '✓';
  if (status === 'running') return '●';
  if (status === 'skipped') return '–';
  return '○';
}
</script>

<template>
  <aside class="side-panel">
    <section class="progress-section">
      <h3 class="panel-title">任务进度</h3>
      <el-progress :percentage="Math.round(progress)" :stroke-width="8" />
      <ul class="step-list">
        <li
          v-for="step in steps"
          :key="step.key"
          class="step-item"
          :class="`step-item--${step.status}`"
        >
          <span class="step-icon">{{ stepIcon(step.status) }}</span>
          <span class="step-label">{{ step.label }}</span>
        </li>
      </ul>
    </section>

    <section class="attachment-section">
      <h3 class="panel-title">附件列表</h3>
      <ul v-if="allAttachments.length" class="file-list">
        <li v-for="(att, idx) in allAttachments" :key="idx" class="file-item">
          <span class="file-icon">📎</span>
          <span class="file-name">{{ att.name }}</span>
          <span class="file-type">{{ att.type }}</span>
        </li>
      </ul>
      <p v-else class="empty-hint">暂无附件</p>
    </section>
  </aside>
</template>

<style lang="scss" scoped>
.side-panel {
  height: 100%;
  padding: 20px 16px;
  border-left: 1px solid $border-color;
  background: $bg-white;
  overflow-y: auto;
}

.panel-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: $text-primary;
}

.progress-section {
  margin-bottom: 24px;
}

.step-list {
  list-style: none;
  margin: 16px 0 0;
  padding: 0;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
  color: $text-secondary;

  &--completed {
    color: $success-color;
  }

  &--running {
    color: $primary-color;
    font-weight: 500;
  }
}

.step-icon {
  width: 16px;
  text-align: center;
  font-size: 12px;
}

.file-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  font-size: 12px;
  transition: background 0.2s;

  &:hover {
    background: #f7f8fa;
  }
}

.file-name {
  flex: 1;
  color: $text-primary;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-type {
  color: $text-secondary;
  font-size: 10px;
  text-transform: uppercase;
}

.empty-hint {
  font-size: 12px;
  color: $text-secondary;
  margin: 0;
}
</style>
