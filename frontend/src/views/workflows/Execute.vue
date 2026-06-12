<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { ArrowLeft, VideoPlay, Check, Close, CircleClose, Download } from '@element-plus/icons-vue';
import WorkflowCanvas from '@/components/workflow/WorkflowCanvas.vue';
import ExecutionLogPanel from '@/components/workflow/ExecutionLogPanel.vue';
import StreamingText from '@/components/chat/StreamingText.vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import { useGraphStore } from '@/stores/graph';
import { getKnowledgeBases } from '@/api/rag';
import { exportExecutionLogs } from '@/api/workflow';
import type { NodeExecutionLog } from '@/api/workflow';

const route = useRoute();
const router = useRouter();
const graphStore = useGraphStore();

const workflowId = computed(() => Number(route.params.id));
const taskInput = ref('');
const requireHuman = ref(false);
const selectedKbId = ref<number | undefined>(undefined);
const kbOptions = ref<{ id: number; name: string }[]>([]);
const isExecuting = ref(false);
const selectedNodeId = ref<string | null>(null);
const selectedLog = ref<NodeExecutionLog | null>(null);
const interventionComment = ref('');

const graphDefinition = computed(
  () => graphStore.currentWorkflow?.graph_definition || { nodes: [], edges: [] },
);

const executionStatus = computed(() => graphStore.currentExecution?.status || 'idle');

const isWaitingHuman = computed(() => executionStatus.value === 'interrupted');

const canTerminate = computed(() => ['pending', 'running'].includes(executionStatus.value));

const isTerminating = ref(false);

const finalAnswer = computed(() => {
  if (graphStore.streamingFinalAnswer) {
    return graphStore.streamingFinalAnswer;
  }
  const final = graphStore.currentExecution?.output_result?.final;
  return typeof final === 'string' ? final : '';
});

const parallelDurationMs = computed(() => {
  const logs = graphStore.executionLogs;
  for (let i = logs.length - 1; i >= 0; i -= 1) {
    const duration = (logs[i] as NodeExecutionLog & { branch_duration_ms?: number })
      .branch_duration_ms;
    if (duration) return duration;
  }
  return null;
});

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
  const kbRes = await getKnowledgeBases({ page: 1, page_size: 100 });
  kbOptions.value = kbRes.items.map((kb) => ({ id: kb.id, name: kb.name }));
}

async function handleExecute(): Promise<void> {
  if (!taskInput.value.trim()) {
    ElMessage.warning('请输入任务描述');
    return;
  }

  const hasKnowledgeNode = graphDefinition.value.nodes.some((n) => n.type === 'knowledge');
  if (hasKnowledgeNode && !selectedKbId.value) {
    ElMessage.warning('请选择知识库后再执行（知识库 Agent 需要绑定数据源）');
    return;
  }

  isExecuting.value = true;
  graphStore.resetExecution();

  try {
    const execution = await graphStore.runWorkflow(workflowId.value, {
      task: taskInput.value.trim(),
      require_human_approval: requireHuman.value,
      kb_id: selectedKbId.value,
    });
    graphStore.connectWebSocket(execution.id);
    ElMessage.success(`工作流已启动（执行 ID: ${execution.id}）`);
  } catch (err) {
    console.error('[Workflow Execute] 启动失败', err);
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

async function handleTerminate(): Promise<void> {
  if (!graphStore.currentExecution) return;
  try {
    await ElMessageBox.confirm('确定要终止当前工作流吗？', '终止确认', {
      type: 'warning',
      confirmButtonText: '确定终止',
      cancelButtonText: '取消',
    });
  } catch {
    return;
  }

  isTerminating.value = true;
  try {
    await graphStore.cancelExecution(graphStore.currentExecution.id);
    ElMessage.warning('工作流已终止');
  } catch {
    ElMessage.error('终止失败');
  } finally {
    isTerminating.value = false;
  }
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

async function handleExportLogs(): Promise<void> {
  if (!graphStore.currentExecution) return;
  const data = await exportExecutionLogs(graphStore.currentExecution.id);
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `workflow-logs-${graphStore.currentExecution.id}.json`;
  link.click();
  URL.revokeObjectURL(url);
  ElMessage.success('日志已导出');
}

onMounted(async () => {
  await loadWorkflow();
  const executionId = Number(route.query.executionId);
  if (executionId) {
    await graphStore.refreshExecution(executionId);
    graphStore.connectWebSocket(executionId);
  }
});

onUnmounted(() => {
  graphStore.disconnectWebSocket();
});
</script>

<template>
  <div class="workflow-execute-page">
    <SectionHeader
      :title="graphStore.currentWorkflow?.name || '工作流执行'"
      description="LangGraph 多智能体协同执行与状态追踪"
    >
      <template #actions>
        <el-button :icon="ArrowLeft" text @click="goBack">返回列表</el-button>
        <el-tag v-if="executionStatus !== 'idle'" :type="statusTagType as any" size="small">
          {{ executionStatus }}
        </el-tag>
      </template>
    </SectionHeader>

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
            <el-form-item label="知识库">
              <el-select
                v-model="selectedKbId"
                clearable
                filterable
                placeholder="选择知识库（知识库 Agent 必填）"
                style="width: 100%"
                :disabled="executionStatus === 'running'"
              >
                <el-option
                  v-for="kb in kbOptions"
                  :key="kb.id"
                  :label="kb.name"
                  :value="kb.id"
                />
              </el-select>
            </el-form-item>
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
            <p v-if="parallelDurationMs" class="parallel-hint">
              并行执行总耗时：{{ parallelDurationMs }} ms
            </p>
            <div class="execute-actions">
              <el-button
                type="primary"
                :icon="VideoPlay"
                :loading="isExecuting"
                :disabled="executionStatus === 'running'"
                @click="handleExecute"
              >
                {{ executionStatus === 'running' ? '执行中...' : '开始执行' }}
              </el-button>
              <el-button
                v-if="canTerminate"
                type="danger"
                :icon="CircleClose"
                :loading="isTerminating"
                plain
                @click="handleTerminate"
              >
                终止执行
              </el-button>
            </div>
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
        <el-card v-if="finalAnswer" shadow="never" class="result-card">
          <template #header>最终回答</template>
          <StreamingText :content="finalAnswer" :streaming="executionStatus === 'running'" />
        </el-card>

        <!-- 执行日志 -->
        <el-card shadow="never" class="log-card">
          <template #header>
            <div class="log-header">
              <span>执行日志</span>
              <el-button
                v-if="graphStore.currentExecution"
                size="small"
                :icon="Download"
                @click="handleExportLogs"
              >
                导出 JSON
              </el-button>
            </div>
          </template>
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
  padding: 0;
}

.canvas-card {
  margin-bottom: 16px;
  border-radius: $border-radius-lg;

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

  &.waiting {
    background: #86909c;
  }
  &.running {
    background: #ff5a1f;
  }
  &.completed {
    background: #00b42a;
  }
  &.failed {
    background: #f53f3f;
  }
}

.control-card,
.intervention-card,
.result-card,
.log-card {
  margin-bottom: 16px;
  border-radius: $border-radius-lg;
}

.log-card {
  :deep(.el-card__body) {
    padding: 0;
    height: 360px;
  }
}

.intervention-title {
  color: $warning-color;
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

.execute-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
