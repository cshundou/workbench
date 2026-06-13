<script setup lang="ts">
import DeliverablesPanel from '@/components/group-chat/DeliverablesPanel.vue';
import type { ProgressStep, AgentMessage } from '@/api/groupChat';
import type { Deliverable } from '@/utils/deliverables';

defineProps<{
  progress: number;
  steps: ProgressStep[];
  messages: AgentMessage[];
  deliverables: Record<string, unknown>[];
  sessionId?: number;
}>();

const emit = defineEmits<{
  viewDeliverable: [deliverable: Deliverable];
  locateMessage: [messageId: string];
  jumpPhase: [stepKey: string];
}>();

function stepIcon(status: string): string {
  if (status === 'completed') return '✓';
  if (status === 'running') return '●';
  if (status === 'skipped') return '–';
  return '○';
}

function handleStepClick(step: ProgressStep): void {
  emit('jumpPhase', step.key);
}
</script>

<template>
  <aside class="side-panel">
    <section class="progress-section">
      <h3 class="panel-title">任务进度</h3>
      <el-progress :percentage="Math.round(progress)" :stroke-width="8" color="#ff5a1f" />
      <ul class="step-list">
        <li
          v-for="step in steps"
          :key="step.key"
          class="step-item"
          :class="`step-item--${step.status}`"
          @click="handleStepClick(step)"
        >
          <span class="step-icon">{{ stepIcon(step.status) }}</span>
          <span class="step-label">{{ step.label }}</span>
        </li>
      </ul>
    </section>

    <DeliverablesPanel
      :messages="messages"
      :session-deliverables="deliverables"
      :session-id="sessionId"
      @view="emit('viewDeliverable', $event)"
      @locate="emit('locateMessage', $event)"
    />
  </aside>
</template>

<style lang="scss" scoped>
.side-panel {
  height: 100%;
  padding: 20px 16px;
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
  padding-bottom: 20px;
  border-bottom: 1px solid $border-color;
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
  padding: 6px 8px;
  font-size: 13px;
  color: $text-secondary;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: rgba($primary-color, 0.04);
  }

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
</style>
