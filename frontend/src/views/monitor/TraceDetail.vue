<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ArrowLeft } from '@element-plus/icons-vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import { getTraceTree, type TraceSpanItem } from '@/api/trace';

const route = useRoute();
const router = useRouter();

const loading = ref(false);
const traceId = computed(() => String(route.query.trace_id || ''));
const trace = ref<Awaited<ReturnType<typeof getTraceTree>> | null>(null);

const spans = computed<TraceSpanItem[]>(() => trace.value?.spans || []);

async function loadTrace(): Promise<void> {
  if (!traceId.value) return;
  loading.value = true;
  try {
    trace.value = await getTraceTree(traceId.value);
  } catch (err) {
    console.error('[TraceDetail] 加载失败', err);
    trace.value = null;
  } finally {
    loading.value = false;
  }
}

function goBack(): void {
  router.back();
}

onMounted(loadTrace);
</script>

<template>
  <div class="trace-detail-page">
    <SectionHeader
      :title="traceId ? `链路追踪 ${traceId}` : '链路追踪'"
      description="工作流执行全链路 Span 明细"
    >
      <template #actions>
        <el-button :icon="ArrowLeft" text @click="goBack">返回</el-button>
      </template>
    </SectionHeader>

    <el-alert v-if="!traceId" type="warning" show-icon :closable="false" class="mb-4">
      缺少 trace_id 参数
    </el-alert>

    <el-card v-else v-loading="loading" shadow="never">
      <template v-if="trace">
        <el-descriptions :column="3" border class="mb-4">
          <el-descriptions-item label="Trace ID">{{ trace.trace_id }}</el-descriptions-item>
          <el-descriptions-item label="资源类型">{{ trace.resource_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="资源 ID">{{ trace.resource_id ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ trace.status || '-' }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ trace.started_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ trace.completed_at || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-table :data="spans" stripe empty-text="暂无 Span 记录">
          <el-table-column prop="name" label="Span 名称" min-width="160" />
          <el-table-column prop="kind" label="类型" width="100" />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column prop="duration_ms" label="耗时 (ms)" width="110" />
          <el-table-column prop="error" label="错误" min-width="180" show-overflow-tooltip />
        </el-table>
      </template>

      <el-empty v-else-if="!loading" description="未找到 Trace 记录或无权访问" />
    </el-card>
  </div>
</template>

<style scoped>
.trace-detail-page {
  min-height: 400px;
}

.mb-4 {
  margin-bottom: 16px;
}
</style>
