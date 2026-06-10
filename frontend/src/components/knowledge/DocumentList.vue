<script setup lang="ts">
import { computed } from 'vue';
import { Delete, Download, Refresh } from '@element-plus/icons-vue';
import type { DocumentInfo } from '@/api/rag';

const props = defineProps<{
  documents: DocumentInfo[];
  progressMap: Record<number, number>;
  loading?: boolean;
  canWrite?: boolean;
}>();

const emit = defineEmits<{
  delete: [doc: DocumentInfo];
  download: [doc: DocumentInfo];
  refresh: [];
}>();

/** 文档状态映射 */
const statusMap: Record<number, { label: string; type: 'info' | 'success' | 'danger' | 'warning' }> = {
  0: { label: '解析中', type: 'warning' },
  1: { label: '已完成', type: 'success' },
  2: { label: '解析失败', type: 'danger' },
};

/** 格式化文件大小 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** 获取文档解析进度 */
function getProgress(doc: DocumentInfo): number {
  if (doc.status === 1) {
    return 100;
  }
  return props.progressMap[doc.id] ?? 0;
}

const hasPendingDocs = computed(() =>
  props.documents.some((doc) => doc.status === 0),
);
</script>

<template>
  <div class="document-list">
    <div class="list-header flex-between">
      <span class="list-title">文档列表 ({{ documents.length }})</span>
      <el-button
        v-if="hasPendingDocs"
        text
        type="primary"
        :icon="Refresh"
        @click="emit('refresh')"
      >
        刷新进度
      </el-button>
    </div>

    <el-table v-loading="loading" :data="documents" stripe style="width: 100%">
      <el-table-column prop="name" label="文档名称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="file_type" label="类型" width="100" />
      <el-table-column label="大小" width="100">
        <template #default="{ row }">
          {{ formatFileSize(row.file_size) }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusMap[row.status]?.type || 'info'" size="small">
            {{ statusMap[row.status]?.label || '未知' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="解析进度" min-width="180">
        <template #default="{ row }">
          <el-progress
            :percentage="getProgress(row)"
            :status="row.status === 2 ? 'exception' : row.status === 1 ? 'success' : undefined"
            :stroke-width="8"
          />
        </template>
      </el-table-column>
      <el-table-column prop="total_chunks" label="分块数" width="80" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button
            text
            type="primary"
            :icon="Download"
            :disabled="row.status !== 1"
            @click="emit('download', row)"
          />
          <el-button
            v-if="canWrite"
            text
            type="danger"
            :icon="Delete"
            @click="emit('delete', row)"
          />
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style lang="scss" scoped>
.document-list {
  margin-top: 20px;
}

.list-header {
  margin-bottom: 12px;
}

.list-title {
  font-size: 15px;
  font-weight: 600;
  color: $text-primary;
}
</style>
