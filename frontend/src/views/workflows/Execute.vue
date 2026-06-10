<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, VideoPlay, Check, Close } from '@element-plus/icons-vue';
import WorkflowCanvas from '@/components/workflow/WorkflowCanvas.vue';
import ExecutionLogPanel from '@/components/workflow/ExecutionLogPanel.vue';
import { useGraphStore } from '@/stores/graph';
import type { NodeExecutionLog } from '@/api/workflow';

const route = useRoute();
const router = useRouter();
const graphStore = useGraphStore();

const workflowId = computed(() => Number(route.params.id));
const taskInput = ref('');
const requireHuman = ref(false);
const isExecuting = ref(false);
const selectedNodeId = ref<string | null>(null);
const selectedLog = ref<NodeExecutionLog | null>(null);
const interventionComment = ref('');

const graphDefinition = computed(
  () =>
    graphStore.currentWorkflow?.graph_definition || { nodes: [], edges: [] },
);

const executionStatus = computed(() => graphStore.currentExecution?.status || 'idle');

const isWaitingHuman = computed(() => executionStatus.value === 'interrupted');

const statusTagType = computed(() => {
  const map: Record<string, string> = {
    pending: 'info',
    running: 'primary',
    completed: 'success',
    failed: 'danger',
    interrupted: 'warning',
    idle: 'info',
  };
  return map[executionStatus.value] || 'info';
});

async function loadWorkflow(): Promise<void> {
  await graphStore.fetchWorkflow(workflowId.value);
}

async function handleExecute(): Promise<void> {
  if (!taskInput.value.trim()) {
    ElMessage.warning('请输入任务描述');
    return;
  }

  isExecuting.value = true;
  graphStore.resetExecution();

  try {
    const execution = await graphStore.runWorkflow(workflowId.value, {
      task: taskInput.value.trim(),
      require_human_approval: requireHuman.value,
    });
    graphStore.connectWebSocket(execution.id);
    ElMessage.success('工作流已启动');
  } catch {
    ElMessage.error('启动失败');
  } finally {
    isExecuting.value = false;
  }
}

async function handleApprove(): Promise<void> {
  if (!graphStore.currentExecution) return;
  await graphStore.intervene(
    graphStore.currentExecution.id,
    true,
    interventionComment.value || undefined,
  );
  graphStore.connectWebSocket(graphStore.currentExecution.id);
  ElMessage.success('已批准，工作流继续执行');
  interventionComment.value = '';
}

async function handleReject(): Promise<void> {
  if (!graphStore.currentExecution) return;
  await graphStore.intervene(graphStore.currentExecution.id, false, interventionComment.value);
  ElMessage.warning('已拒绝，工作流已终止');
  interventionComment.value = '';
}

function handleNodeClick(nodeId: string): void {
  selectedNodeId.value = nodeId;
  const logs = graphStore.executionLogs.filter((l) => l.node_id === nodeId);
  selectedLog.value = logs.length > 0 ? logs[logs.length - 1] : null;
}

function goBack(): void {
  router.push({ name: 'WorkflowList' });
}

onMounted(() => {
  loadWorkflow();
});

onUnmounted(() => {
  graphStore.disconnectWebSocket();
});
</script>

<template>
  <div class="workflow-execute-page">
    <div class="page-header">
      <el-button :icon="ArrowLeft" text @click="goBack">返回列表</el-button>
      <div class="header-info">
        <h2>{{ graphStore.currentWorkflow?.name || '工作流执行' }}</h2>
        <el-tag v-if="executionStatus !== 'idle'" :type="statusTagType as any" size="small">
          {{ executionStatus }}
        </el-tag>
      </div>
    </div>

    <el-row :gutter="16" class="main-content">
      <el-col :span="16">
        <el-card shadow="never" class="canvas-card">
          <template #header>
            <span>工作流拓扑</span>
            <div class="legend">
              <span class="legend-item"><i class="dot waiting" />等待</span>
              <span class="legend-item"><i class="dot running" />执行中</span>
              <span class="legend-item"><i class="dot completed" />完成</span>
              <span class="legend-item"><i class="dot failed" />失败</span>
            </div>
          </template>
          <WorkflowCanvas
            :graph-definition="graphDefinition"
            :node-statuses="graphStore.nodeStatuses"
            :selected-node-id="selectedNodeId"
            @node-click="handleNodeClick"
          />
        </el-card>

        <!-- 节点详情 -->
        <el-card v-if="selectedLog" shadow="never" class="node-detail-card">
          <template #header>节点详情：{{ selectedLog.node_label }}</template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="状态">{{ selectedLog.status }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedLog.input_data" label="输入">
              <pre class="json-pre">{{ JSON.stringify(selectedLog.input_data, null, 2) }}</pre>
            </el-descriptions-item>
            <el-descriptions-item v-if="selectedLog.output_data" label="输出">
              <pre class="json-pre">{{ JSON.stringify(selectedLog.output_data, null, 2) }}</pre>
            </el-descriptions-item>
            <el-descriptions-item v-if="selectedLog.error" label="错误">
              <span class="error-text">{{ selectedLog.error }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="8">
        <!-- 执行控制 -->
        <el-card shadow="never" class="control-card">
          <template #header>执行控制</template>
          <el-form label-position="top">
            <el-form-item label="任务描述">
              <el-input
                v-model="taskInput"
                type="textarea"
                :rows="4"
                placeholder="描述需要多智能体协同完成的复杂任务..."
                :disabled="executionStatus === 'running'"
              />
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="requireHuman" :disabled="executionStatus === 'running'">
                启用人工介入（审核前需人工确认）
              </el-checkbox>
            </el-form-item>
            <el-button
              type="primary"
              :icon="VideoPlay"
              :loading="isExecuting"
              :disabled="executionStatus === 'running'"
              block
              @click="handleExecute"
            >
              {{ executionStatus === 'running' ? '执行中...' : '开始执行' }}
            </el-button>
          </el-form>
        </el-card>

        <!-- 人工介入 -->
        <el-card v-if="isWaitingHuman" shadow="never" class="intervention-card">
          <template #header>
            <span class="intervention-title">⚠️ 等待人工确认</span>
          </template>
          <p class="intervention-desc">工作流已暂停，请审核子任务结果后决定是否继续执行。</p>
          <el-input
            v-model="interventionComment"
            type="textarea"
            :rows="2"
            placeholder="审批备注（可选）"
            class="mb-3"
          />
          <div class="intervention-actions">
            <el-button type="success" :icon="Check" @click="handleApprove">批准继续</el-button>
            <el-button type="danger" :icon="Close" @click="handleReject">拒绝终止</el-button>
          </div>
        </el-card>

        <!-- 最终结果 -->
        <el-card
          v-if="graphStore.currentExecution?.output_result?.final"
          shadow="never"
          class="result-card"
        >
          <template #header>最终回答</template>
          <div class="final-answer">
            {{ graphStore.currentExecution?.output_result?.final }}
          </div>
        </el-card>

        <!-- 执行日志 -->
        <el-card shadow="never" class="log-card">
          <ExecutionLogPanel
            :logs="graphStore.executionLogs"
            :selected-node-id="selectedNodeId"
            @select="handleNodeClick"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style lang="scss" scoped>
.workflow-execute-page {
  padding: 4px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;

  .header-info {
    display: flex;
    align-items: center;
    gap: 10px;

    h2 {
      margin: 0;
      font-size: 18px;
    }
  }
}

.canvas-card {
  margin-bottom: 16px;

  :deep(.el-card__header) {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
}

.legend {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: $text-secondary;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;

  &.waiting { background: #909399; }
  &.running { background: #409eff; }
  &.completed { background: #67c23a; }
  &.failed { background: #f56c6c; }
}

.control-card,
.intervention-card,
.result-card,
.log-card {
  margin-bottom: 16px;
}

.log-card {
  :deep(.el-card__body) {
    padding: 0;
    height: 360px;
  }
}

.intervention-title {
  color: #e6a23c;
  font-weight: 600;
}

.intervention-desc {
  font-size: 13px;
  color: $text-secondary;
  margin: 0 0 12px;
}

.intervention-actions {
  display: flex;
  gap: 8px;
}

.mb-3 {
  margin-bottom: 12px;
}

.json-pre {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.error-text {
  color: #f56c6c;
}

.final-answer {
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.node-detail-card {
  margin-bottom: 16px;
}
</style>
