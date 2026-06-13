<script setup lang="ts">
import { computed } from 'vue';
import { VueFlow } from '@vue-flow/core';
import type { NodeMouseEvent } from '@vue-flow/core';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import WorkflowNode from './WorkflowNode.vue';
import type { GraphDefinition } from '@/api/workflow';

const props = defineProps<{
  graphDefinition: GraphDefinition;
  nodeStatuses: Record<string, string>;
  selectedNodeId?: string | null;
}>();

const emit = defineEmits<{
  'node-click': [nodeId: string];
}>();

function handleNodeClick(event: NodeMouseEvent): void {
  emit('node-click', event.node.id);
}

/** 将图定义转换为 vue-flow 节点 */
const nodes = computed(() =>
  props.graphDefinition.nodes.map((node) => ({
    id: node.id,
    type: 'workflow',
    position: node.position,
    data: {
      label: node.label,
      type: node.type,
      status: props.nodeStatuses[node.id] || 'waiting',
      selected: props.selectedNodeId === node.id,
    },
  })),
);

/** 当前并行执行中的节点 */
const parallelRunningNodes = computed(() =>
  Object.entries(props.nodeStatuses)
    .filter(([, status]) => status === 'running')
    .map(([nodeId]) => nodeId),
);

const isParallelActive = computed(() => parallelRunningNodes.value.length > 1);

/** 将图定义转换为 vue-flow 边 */
const edges = computed(() =>
  props.graphDefinition.edges.map((edge) => {
    const sourceRunning = props.nodeStatuses[edge.source] === 'running';
    const targetRunning = props.nodeStatuses[edge.target] === 'running';
    const isParallelEdge =
      isParallelActive.value &&
      (parallelRunningNodes.value.includes(edge.source) ||
        parallelRunningNodes.value.includes(edge.target));

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      animated: sourceRunning || targetRunning,
      style: {
        stroke: isParallelEdge ? '#ff5a1f' : '#b1b1b7',
        strokeWidth: isParallelEdge ? 3 : 2,
        strokeDasharray: isParallelEdge ? '6 3' : undefined,
      },
    };
  }),
);
</script>

<template>
  <div class="workflow-canvas">
    <el-empty
      v-if="!nodes.length"
      description="拓扑未配置，已使用标准六节点模板执行"
      class="empty-canvas"
    />
    <template v-else>
    <div v-if="isParallelActive" class="parallel-badge">
      并行执行中（{{ parallelRunningNodes.length }} 个节点）
    </div>
    <VueFlow
      :nodes="nodes"
      :edges="edges"
      :default-viewport="{ zoom: 0.85 }"
      :min-zoom="0.3"
      :max-zoom="2"
      fit-view-on-init
      @node-click="handleNodeClick"
    >
      <template #node-workflow="nodeProps">
        <WorkflowNode
          :id="nodeProps.id"
          :label="nodeProps.data.label"
          :type="nodeProps.data.type"
          :status="nodeProps.data.status"
          :selected="nodeProps.data.selected"
        />
      </template>
    </VueFlow>
    </template>
  </div>
</template>

<style lang="scss" scoped>
.workflow-canvas {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 400px;
  background: $bg-white;
  border-radius: $border-radius;
  border: 1px solid $border-color;
}

.empty-canvas {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.parallel-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  padding: 4px 10px;
  font-size: 12px;
  color: #ff5a1f;
  background: rgba(255, 90, 31, 0.1);
  border: 1px solid rgba(255, 90, 31, 0.35);
  border-radius: $border-radius;
}
</style>
