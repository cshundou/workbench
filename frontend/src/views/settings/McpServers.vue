<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import {
  createMcpServer,
  enableBuiltinMcp,
  listMcpServers,
  syncMcpTools,
  testMcpServer,
  type McpServerInfo,
} from '@/api/mcp';

const loading = ref(false);
const servers = ref<McpServerInfo[]>([]);
const dialogVisible = ref(false);
const form = ref({ name: '', endpoint: '', transport: 'http' });

async function fetchServers(): Promise<void> {
  loading.value = true;
  try {
    servers.value = await listMcpServers();
  } finally {
    loading.value = false;
  }
}

async function handleCreate(): Promise<void> {
  await createMcpServer(form.value);
  dialogVisible.value = false;
  ElMessage.success('MCP 服务器已添加');
  fetchServers();
}

async function handleEnableBuiltin(): Promise<void> {
  const result = await enableBuiltinMcp();
  ElMessage.success(`已启用 ${result.created_count} 个内置 MCP`);
  fetchServers();
}

onMounted(fetchServers);
</script>

<template>
  <div>
    <SectionHeader title="MCP 服务器" description="连接行业标准 MCP 工具生态" />
    <div class="toolbar">
      <el-button type="primary" @click="dialogVisible = true">添加服务器</el-button>
      <el-button @click="handleEnableBuiltin">启用内置 MCP</el-button>
    </div>
    <el-table v-loading="loading" :data="servers" stripe>
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="transport" label="传输" width="80" />
      <el-table-column prop="endpoint" label="端点" show-overflow-tooltip />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button link type="primary" @click="testMcpServer(row.id)">测试</el-button>
          <el-button link @click="syncMcpTools(row.id)">同步工具</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dialogVisible" title="添加 MCP 服务器" width="480px">
      <el-form label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="端点"><el-input v-model="form.endpoint" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; }
</style>
