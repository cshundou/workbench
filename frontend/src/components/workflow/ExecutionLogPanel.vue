<script setup lang="ts">
import { computed, ref } from 'vue';
import type { NodeExecutionLog } from '@/api/workflow';
import { NODE_STATUS_COLORS } from '@/stores/graph';

const props = defineProps<{
  logs: NodeExecutionLog[];
  selectedNodeId?: string | null;
  traceId?: string | null;
}>();

const emit = defineEmits<{
  select: [nodeId: string];
}>();

const keyword = ref('');
const expandedKeys = ref<Set<string>>(new Set());

const sortedLogs = computed(() => {
  const filtered = [...props.logs]
    .filter((log) => {
      if (!keyword.value.trim()) return true;
      const text = JSON.stringify(log).toLowerCase();
      return text.includes(keyword.value.trim().toLowerCase());
    })
    .sort((a, b) => {
      const ta = a.started_at || a.completed_at || '';
      const tb = b.started_at || b.completed_at || '';
      return ta.localeCompare(tb);
    });
  return filtered;
});

const loopGroups = computed(() => {
  const groups: Record<string, NodeExecutionLog[]> = {};
  for (const log of sortedLogs.value) {
    const iteration = (log as NodeExecutionLog & { loop_iteration?: number }).loop_iteration;
    if (iteration != null) {
      const key = `loop-${iteration}`;
      groups[key] = groups[key] || [];
      groups[key].push(log);
    }
  }
  return groups;
});

function toggleExpand(key: string): void {
  if (expandedKeys.value.has(key)) {
    expandedKeys.value.delete(key);
  } else {
    expandedKeys.value.add(key);
  }
}

function isExpanded(key: string): boolean {
  return expandedKeys.value.has(key);
}

function statusColor(status: string): string {
  return NODE_STATUS_COLORS[status] || NODE_STATUS_COLORS.waiting;
}

function formatTime(iso?: string | null): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleTimeString();
}
</script>

<template>
  <div class="execution-log-panel">
    <div class="panel-header">
      <h4>执行日志</h4>
      <span class="log-count">{{ logs.length }} 条（含持久化记录）</span>
      <router-link
        v-if="traceId"
        :to="`/monitor/traces?trace_id=${traceId}`"
        class="trace-link"
      >
        查看链路 TraceID
      </router-link>
    </div>
    <div class="panel-toolbar">
      <el-input v-model="keyword" size="small" placeholder="搜索日志内容" clearable />
    </div>

    <el-scrollbar v-if="sortedLogs.length" class="log-list">
      <div
        v-for="(log, index) in sortedLogs"
        :key="`${log.node_id}-${index}`"
        class="log-item"
        :class="{ active: selectedNodeId === log.node_id }"
        @click="emit('select', log.node_id)"
      >
        <div class="log-item-header">
          <span class="status-dot" :style="{ backgroundColor: statusColor(log.status) }" />
          <span class="node-name">{{ log.node_label }}</span>
          <el-tag size="small" :color="statusColor(log.status)" effect="dark">
            {{ log.status }}
          </el-tag>
        </div>
        <div class="log-time">
          {{ formatTime(log.started_at || log.completed_at) }}
          <span v-if="(log as any).branch_duration_ms" class="branch-time">
            分支耗时 {{ (log as any).branch_duration_ms }}ms
          </span>
          <span v-if="(log as any).loop_iteration != null" class="loop-badge">
            循环 {{ (log as any).loop_iteration }}/{{ (log as any).max_iterations ?? '?' }}
          </span>
        </div>
        <div v-if="log.error" class="log-error">{{ log.error }}</div>
        <div v-if="log.input_data" class="log-io">
          <el-button link size="small" @click.stop="toggleExpand(`${log.node_id}-in`)">
            {{ isExpanded(`${log.node_id}-in`) ? '收起输入' : '展开输入' }}
          </el-button>
          <pre v-if="isExpanded(`${log.node_id}-in`)">{{ JSON.stringify(log.input_data, null, 2) }}</pre>
        </div>
        <div v-if="log.output_data" class="log-io">
          <el-button link size="small" @click.stop="toggleExpand(`${log.node_id}-out`)">
            {{ isExpanded(`${log.node_id}-out`) ? '收起输出' : '展开输出' }}
          </el-button>
          <pre v-if="isExpanded(`${log.node_id}-out`)">{{ JSON.stringify(log.output_data, null, 2) }}</pre>
        </div>
      </div>
    </el-scrollbar>

    <el-empty v-else description="暂无执行日志" :image-size="60" />
  </div>
</template>

<style lang="scss" scoped>
.execution-log-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: $border-radius;
  border: 1px solid $border-color;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid $border-color;

  h4 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }

  .log-count {
    font-size: 12px;
    color: $text-secondary;
  }
}

.log-list {
  flex: 1;
  padding: 8px;
}

.log-item {
  padding: 10px 12px;
  margin-bottom: 8px;
  border-radius: $border-radius;
  border: 1px solid $border-color;
  cursor: pointer;
  transition: background 0.15s;

  &:hover,
  &.active {
    background: rgba($primary-color, 0.06);
    border-color: $primary-color;
  }
}

.log-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.node-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
}

.log-time {
  font-size: 11px;
  color: $text-secondary;
  margin-bottom: 4px;
}

.log-error {
  font-size: 12px;
  color: #f56c6c;
  margin-top: 4px;
}

.log-output {
  margin-top: 6px;

  pre {
    margin: 0;
    padding: 6px 8px;
    background: #f5f7fa;
    border-radius: 4px;
    font-size: 11px;
    overflow-x: auto;
    max-height: 120px;
  }
}
</style>
