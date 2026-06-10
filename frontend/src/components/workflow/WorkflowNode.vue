<script setup lang="ts">
import { computed } from 'vue';
import { Handle, Position } from '@vue-flow/core';
import { NODE_STATUS_COLORS } from '@/stores/graph';

const props = defineProps<{
  id: string;
  label: string;
  type: string;
  status?: string;
  selected?: boolean;
}>();

const statusColor = computed(() => {
  const status = props.status || 'waiting';
  return NODE_STATUS_COLORS[status] || NODE_STATUS_COLORS.waiting;
});

const typeIcon = computed(() => {
  const icons: Record<string, string> = {
    scheduler: '⚙️',
    knowledge: '📚',
    search: '🔍',
    execution: '⚡',
    human: '👤',
    reviewer: '✅',
  };
  return icons[props.type] || '📦';
});
</script>

<template>
  <div
    class="workflow-node"
    :class="{ 'is-selected': selected }"
    :style="{ borderColor: statusColor, '--status-color': statusColor }"
  >
    <Handle type="target" :position="Position.Top" />
    <div class="node-header">
      <span class="node-icon">{{ typeIcon }}</span>
      <span class="node-label">{{ label }}</span>
    </div>
    <div class="node-status" :style="{ backgroundColor: statusColor }">
      {{ status || 'waiting' }}
    </div>
    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style lang="scss" scoped>
.workflow-node {
  min-width: 140px;
  padding: 10px 14px;
  background: #fff;
  border: 2px solid #909399;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  }

  &.is-selected {
    box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.3);
  }
}

.node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.node-icon {
  font-size: 16px;
}

.node-label {
  font-size: 13px;
  font-weight: 600;
  color: $text-primary;
}

.node-status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  color: #fff;
  text-transform: capitalize;
}
</style>
