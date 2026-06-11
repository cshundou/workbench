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
    scheduler: '⚙',
    knowledge: '知',
    search: '搜',
    execution: '执',
    human: '人',
    reviewer: '审',
  };
  return icons[props.type] || '·';
});
</script>

<template>
  <div
    class="workflow-node"
    :class="{ 'is-selected': selected }"
    :style="{ borderColor: selected ? statusColor : undefined }"
  >
    <Handle type="target" :position="Position.Top" />
    <div class="node-header">
      <span class="node-icon">{{ typeIcon }}</span>
      <span class="node-label">{{ label }}</span>
    </div>
    <div class="node-status" :style="{ color: statusColor, borderColor: statusColor }">
      {{ status || 'waiting' }}
    </div>
    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style lang="scss" scoped>
.workflow-node {
  min-width: 140px;
  padding: 10px 14px;
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: $border-radius;
  box-shadow: none;
  cursor: pointer;
  transition: border-color 0.2s ease;

  &:hover {
    border-color: $primary-color;
  }

  &.is-selected {
    border-color: $primary-color;
    border-width: 2px;
  }
}

.node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.node-icon {
  font-size: 12px;
  color: $text-secondary;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid $border-color;
  border-radius: $border-radius;
}

.node-label {
  font-size: 13px;
  font-weight: 600;
  color: $text-primary;
}

.node-status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: $border-radius;
  font-size: 11px;
  background: $bg-white;
  border: 1px solid $border-color;
  text-transform: capitalize;
}
</style>
