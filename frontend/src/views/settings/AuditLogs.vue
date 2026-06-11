<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import { ElMessage } from 'element-plus';
import { exportAuditLogs, getAuditLogs, type AuditLogItem } from '@/api/audit';

const loading = ref(false);
const exportLoading = ref(false);
const logs = ref<AuditLogItem[]>([]);
const total = ref(0);
const queryParams = reactive({ page: 1, page_size: 20, action: '', resource_type: '' });

async function fetchLogs(): Promise<void> {
  loading.value = true;
  try {
    const result = await getAuditLogs({
      page: queryParams.page,
      page_size: queryParams.page_size,
      action: queryParams.action || undefined,
      resource_type: queryParams.resource_type || undefined,
    });
    logs.value = result.items;
    total.value = result.total;
  } finally {
    loading.value = false;
  }
}

async function handleExport(format: 'csv' | 'excel'): Promise<void> {
  exportLoading.value = true;
  try {
    await exportAuditLogs(format, {
      action: queryParams.action || undefined,
      resource_type: queryParams.resource_type || undefined,
    });
    ElMessage.success('导出成功');
  } catch (error) {
    console.error('[Audit Export]', error);
    ElMessage.error('导出失败');
  } finally {
    exportLoading.value = false;
  }
}

onMounted(() => {
  fetchLogs();
});
</script>

<template>
  <div>
    <SectionHeader title="审计日志" description="记录登录、CRUD 与关键业务操作" />

    <div class="filters">
      <el-input
        v-model="queryParams.action"
        placeholder="操作类型"
        clearable
        style="width: 180px"
      />
      <el-input
        v-model="queryParams.resource_type"
        placeholder="资源类型"
        clearable
        style="width: 180px"
      />
      <el-button type="primary" @click="fetchLogs">查询</el-button>
      <el-button :loading="exportLoading" @click="handleExport('csv')">导出 CSV</el-button>
      <el-button :loading="exportLoading" @click="handleExport('excel')">导出 Excel</el-button>
    </div>

    <el-table v-loading="loading" :data="logs" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="action" label="操作" width="140" />
      <el-table-column prop="resource_type" label="资源类型" width="120" />
      <el-table-column prop="resource_id" label="资源 ID" width="100" />
      <el-table-column prop="user_id" label="用户 ID" width="100" />
      <el-table-column prop="ip_address" label="IP" width="140" />
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column label="结果" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.detail?.success === true" size="small" type="success"> 成功 </el-tag>
          <el-tag v-else-if="row.detail?.success === false" size="small" type="danger">
            失败
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="详情" min-width="200">
        <template #default="{ row }">
          {{ JSON.stringify(row.detail || {}) }}
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="queryParams.page"
        :page-size="queryParams.page_size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchLogs"
      />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
