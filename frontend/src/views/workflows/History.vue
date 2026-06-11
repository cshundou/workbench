<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, VideoPlay } from '@element-plus/icons-vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import { getExecutionHistory, executeWorkflow, getExecutionReplay } from '@/api/workflow';
import type { WorkflowExecution } from '@/api/workflow';

const route = useRoute();
const router = useRouter();
const workflowId = computed(() => Number(route.params.id));

const loading = ref(false);
const executions = ref<WorkflowExecution[]>([]);
const total = ref(0);
const queryParams = reactive({ page: 1, page_size: 10 });

const statusMap: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  interrupted: '等待人工',
};

async function fetchHistory(): Promise<void> {
  loading.value = true;
  try {
    const result = await getExecutionHistory(workflowId.value, queryParams);
    executions.value = result.items;
    total.value = result.total;
  } finally {
    loading.value = false;
  }
}

async function handleReplay(row: WorkflowExecution): Promise<void> {
  try {
    const replay = await getExecutionReplay(workflowId.value, row.id);
    const input = replay.input_params || row.input_params || {};
    const execution = await executeWorkflow(workflowId.value, {
      task: String(input.task || ''),
      require_human_approval: Boolean(input.require_human_approval),
      kb_id: input.kb_id as number | undefined,
      extra_params: (input.extra_params as Record<string, unknown>) || {},
    });
    ElMessage.success('已重新启动执行');
    router.push({
      name: 'WorkflowExecute',
      params: { id: workflowId.value },
      query: { executionId: execution.id },
    });
  } catch {
    ElMessage.error('重跑失败');
  }
}

function goExecuteDetail(row: WorkflowExecution): void {
  router.push({
    name: 'WorkflowExecute',
    params: { id: workflowId.value },
    query: { executionId: row.id },
  });
}

onMounted(() => {
  fetchHistory();
});
</script>

<template>
  <div class="workflow-history">
    <SectionHeader title="执行历史" description="查看历史执行记录并支持重跑">
      <template #actions>
        <el-button text :icon="ArrowLeft" @click="router.push({ name: 'WorkflowList' })">
          返回列表
        </el-button>
      </template>
    </SectionHeader>

    <el-table v-loading="loading" :data="executions" stripe>
      <el-table-column prop="id" label="执行 ID" width="100" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ statusMap[row.status] || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="任务摘要" min-width="240">
        <template #default="{ row }">
          {{ String(row.input_params?.task || '').slice(0, 80) }}
        </template>
      </el-table-column>
      <el-table-column prop="started_at" label="开始时间" width="180" />
      <el-table-column prop="completed_at" label="完成时间" width="180" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click="goExecuteDetail(row)">详情</el-button>
          <el-button text type="success" :icon="VideoPlay" @click="handleReplay(row)"
            >重跑</el-button
          >
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="queryParams.page"
        :page-size="queryParams.page_size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchHistory"
      />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
