<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, Plus } from '@element-plus/icons-vue';
import { VueFlow } from '@vue-flow/core';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import WorkflowNode from '@/components/workflow/WorkflowNode.vue';
import NodeConfigDrawer from '@/components/workflow/NodeConfigDrawer.vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import {
  getWorkflow,
  updateWorkflow,
  validateWorkflowGraph,
  getWorkflowVersions,
  rollbackWorkflowVersion,
  publishWorkflow,
} from '@/api/workflow';
import type {
  GraphDefinition,
  WorkflowEdgeDef,
  WorkflowNodeDef,
  WorkflowVersionInfo,
} from '@/api/workflow';

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
  { type: 'supervisor', label: '监督节点' },
  { type: 'reviewer', label: '审核 Agent' },
  { type: 'condition', label: '条件分支' },
  { type: 'custom_agent', label: '自定义 Agent' },
  { type: 'loop', label: '循环节点' },
];

const configDrawerVisible = ref(false);
const editingNode = ref<WorkflowNodeDef | null>(null);
const versions = ref<WorkflowVersionInfo[]>([]);
const workflowStatus = ref('draft');
const currentVersion = ref<string | null>(null);

function addNode(type: string, label: string): void {
  const id = `${type}_${Date.now()}`;
  const config =
    type === 'loop'
      ? { loop_condition: '满足退出条件', max_iterations: 10 }
      : type === 'condition'
        ? {
            branches: [
              {
                label: '知识库无结果',
                condition: 'knowledge 为空',
                target: '',
              },
            ],
            default_target: '',
          }
        : type === 'custom_agent'
          ? { agent_id: null }
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
    workflowStatus.value = wf.status || 'draft';
    currentVersion.value = wf.current_version || null;
    nodes.value = JSON.parse(JSON.stringify(wf.graph_definition.nodes || []));
    edges.value = JSON.parse(JSON.stringify(wf.graph_definition.edges || []));
    versions.value = await getWorkflowVersions(workflowId.value);
  } finally {
    loading.value = false;
  }
}

function openNodeConfig(nodeId: string): void {
  const node = nodes.value.find((item) => item.id === nodeId);
  if (!node) return;
  editingNode.value = node;
  configDrawerVisible.value = true;
}

function handleNodeConfigSave(updated: WorkflowNodeDef): void {
  const index = nodes.value.findIndex((item) => item.id === updated.id);
  if (index >= 0) {
    nodes.value[index] = updated;
  }
}

function removeSelected(nodeId: string): void {
  nodes.value = nodes.value.filter((node) => node.id !== nodeId);
  edges.value = edges.value.filter((edge) => edge.source !== nodeId && edge.target !== nodeId);
}

async function handleRollback(versionId: number): Promise<void> {
  await rollbackWorkflowVersion(workflowId.value, versionId);
  ElMessage.success('已回滚并生成新版本');
  await loadWorkflow();
}

async function handlePublish(): Promise<void> {
  await publishWorkflow(workflowId.value);
  ElMessage.success('发布成功');
  await loadWorkflow();
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
      <div class="version-panel">
        <h4>版本历史</h4>
        <p class="version-meta">
          状态：{{ workflowStatus === 'published' ? '已发布' : '草稿' }}
          <span v-if="currentVersion"> · {{ currentVersion }}</span>
        </p>
        <el-button
          v-if="workflowStatus !== 'published'"
          type="success"
          size="small"
          class="mb-2"
          @click="handlePublish"
        >
          发布
        </el-button>
        <el-scrollbar max-height="320px">
          <div v-for="ver in versions" :key="ver.id" class="version-item">
            <div class="ver-title">{{ ver.version }}</div>
            <div class="ver-time">{{ ver.published_at }}</div>
            <el-button link size="small" type="primary" @click="handleRollback(ver.id)">
              回滚
            </el-button>
          </div>
        </el-scrollbar>
      </div>
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
          @node-double-click="({ node }) => openNodeConfig(node.id)"
          @node-contextmenu="({ node, event }) => { event.preventDefault(); removeSelected(node.id); }"
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

    <NodeConfigDrawer
      v-model:visible="configDrawerVisible"
      :node="editingNode"
      @save="handleNodeConfigSave"
    />
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

.version-panel {
  width: 200px;
  padding: 12px;
  background: #fff;
  border-radius: $border-radius-md;
  box-shadow: $shadow-soft;

  h4 {
    margin: 0 0 8px;
    font-size: 14px;
  }
}

.version-meta {
  font-size: 12px;
  color: $text-secondary;
  margin: 0 0 8px;
}

.version-item {
  padding: 8px 0;
  border-bottom: 1px solid $border-color;
}

.ver-title {
  font-weight: 600;
  font-size: 13px;
}

.ver-time {
  font-size: 11px;
  color: $text-secondary;
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
