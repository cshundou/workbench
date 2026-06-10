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

/** 将图定义转换为 vue-flow 边 */
const edges = computed(() =>
  props.graphDefinition.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    animated: props.nodeStatuses[edge.source] === 'running',
    style: { stroke: '#b1b1b7', strokeWidth: 2 },
  })),
);

</script>

<template>
  <div class="workflow-canvas">
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
  </div>
</template>

<style lang="scss" scoped>
.workflow-canvas {
  width: 100%;
  height: 100%;
  min-height: 400px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid $border-color;
}
</style>
