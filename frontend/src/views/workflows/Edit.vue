<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, Plus } from '@element-plus/icons-vue';
import { VueFlow } from '@vue-flow/core';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import WorkflowNode from '@/components/workflow/WorkflowNode.vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import { getWorkflow, updateWorkflow, validateWorkflowGraph } from '@/api/workflow';
import type { GraphDefinition, WorkflowEdgeDef, WorkflowNodeDef } from '@/api/workflow';

const route = useRoute();
const router = useRouter();
const workflowId = computed(() => Number(route.params.id));

const loading = ref(false);
const saving = ref(false);
const workflowName = ref('');
const nodes = ref<WorkflowNodeDef[]>([]);
const edges = ref<WorkflowEdgeDef[]>([]);

const nodeTypes = [
  { type: 'scheduler', label: '调度中心' },
  { type: 'knowledge', label: '知识库 Agent' },
  { type: 'search', label: '搜索 Agent' },
  { type: 'execution', label: '执行 Agent' },
  { type: 'human', label: '人工介入' },
  { type: 'reviewer', label: '审核 Agent' },
  { type: 'loop', label: '循环节点' },
];

function addNode(type: string, label: string): void {
  const id = `${type}_${Date.now()}`;
  const config =
    type === 'loop'
      ? { loop_condition: '满足退出条件', max_iterations: 10 }
      : {};
  nodes.value.push({
    id,
    type,
    label,
    position: { x: 120 + nodes.value.length * 40, y: 120 + nodes.value.length * 30 },
    config,
  });
}

function onConnect(params: { source?: string; target?: string }): void {
  if (!params.source || !params.target) {
    return;
  }
  edges.value.push({
    id: `e-${params.source}-${params.target}-${Date.now()}`,
    source: params.source,
    target: params.target,
  });
}

const flowNodes = computed(() =>
  nodes.value.map((node) => ({
    id: node.id,
    type: 'workflow',
    position: node.position,
    data: { label: node.label, type: node.type, status: 'waiting' },
  })),
);

const flowEdges = computed(() =>
  edges.value.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
  })),
);

async function loadWorkflow(): Promise<void> {
  loading.value = true;
  try {
    const wf = await getWorkflow(workflowId.value);
    workflowName.value = wf.name;
    nodes.value = JSON.parse(JSON.stringify(wf.graph_definition.nodes || []));
    edges.value = JSON.parse(JSON.stringify(wf.graph_definition.edges || []));
  } finally {
    loading.value = false;
  }
}

function removeSelected(nodeId: string): void {
  nodes.value = nodes.value.filter((node) => node.id !== nodeId);
  edges.value = edges.value.filter((edge) => edge.source !== nodeId && edge.target !== nodeId);
}

async function handleSave(): Promise<void> {
  saving.value = true;
  try {
    const graphDefinition: GraphDefinition = { nodes: nodes.value, edges: edges.value };
    const validation = await validateWorkflowGraph(workflowId.value, graphDefinition);
    if (!validation.valid) {
      ElMessage.error(validation.errors.join('；') || '图定义校验失败');
      return;
    }
    if (validation.warnings.length > 0) {
      ElMessage.warning(validation.warnings.join('；'));
    }
    await updateWorkflow(workflowId.value, { graph_definition: graphDefinition });
    ElMessage.success('工作流拓扑已保存');
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  loadWorkflow();
});
</script>

<template>
  <div v-loading="loading" class="workflow-edit">
    <SectionHeader :title="`${workflowName} - 可视化编辑`" description="拖拽连线定义工作流拓扑">
      <template #actions>
        <el-button text :icon="ArrowLeft" @click="router.back()">返回</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存拓扑</el-button>
      </template>
    </SectionHeader>

    <div class="edit-layout">
      <div class="palette">
        <h4>添加节点</h4>
        <el-button
          v-for="item in nodeTypes"
          :key="item.type"
          class="palette-btn"
          :icon="Plus"
          @click="addNode(item.type, item.label)"
        >
          {{ item.label }}
        </el-button>
      </div>
      <div class="canvas-wrap">
        <VueFlow
          :nodes="flowNodes"
          :edges="flowEdges"
          :nodes-draggable="true"
          :nodes-connectable="true"
          fit-view-on-init
          @connect="onConnect"
          @node-double-click="({ node }) => removeSelected(node.id)"
        >
          <template #node-workflow="nodeProps">
            <WorkflowNode
              :id="nodeProps.id"
              :label="nodeProps.data.label"
              :type="nodeProps.data.type"
              status="waiting"
            />
          </template>
        </VueFlow>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.workflow-edit {
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
}

.edit-layout {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
}

.palette {
  width: 180px;
  padding: 12px;
  background: #fff;
  border-radius: $border-radius-md;
  box-shadow: $shadow-soft;

  h4 {
    margin: 0 0 12px;
    font-size: 14px;
  }
}

.palette-btn {
  width: 100%;
  margin-bottom: 8px;
  justify-content: flex-start;
}

.canvas-wrap {
  flex: 1;
  background: #fff;
  border-radius: $border-radius-md;
  box-shadow: $shadow-soft;
}
</style>
