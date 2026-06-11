<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus } from '@element-plus/icons-vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import {
  deleteCustomTool,
  listCustomTools,
  registerCustomTool,
  testCustomTool,
  type CustomToolInfo,
} from '@/api/tools';

const loading = ref(false);
const tools = ref<CustomToolInfo[]>([]);
const dialogVisible = ref(false);
const testDialogVisible = ref(false);
const testResult = ref('');
const testingId = ref<number | null>(null);

const form = reactive({
  name: '',
  description: '',
  invoke_url: '',
  auth_type: 'none' as 'none' | 'bearer' | 'api_key',
  auth_token: '',
  parameters_schema: '{\n  "type": "object",\n  "properties": {},\n  "required": []\n}',
});

async function fetchTools(): Promise<void> {
  loading.value = true;
  try {
    tools.value = await listCustomTools();
  } finally {
    loading.value = false;
  }
}

function openCreate(): void {
  form.name = '';
  form.description = '';
  form.invoke_url = '';
  form.auth_type = 'none';
  form.auth_token = '';
  dialogVisible.value = true;
}

async function handleCreate(): Promise<void> {
  try {
    const parameters_schema = JSON.parse(form.parameters_schema);
    await registerCustomTool({
      name: form.name,
      description: form.description,
      invoke_url: form.invoke_url,
      auth_type: form.auth_type,
      auth_token: form.auth_token || undefined,
      parameters_schema,
    });
    ElMessage.success('工具注册成功');
    dialogVisible.value = false;
    await fetchTools();
  } catch (error) {
    ElMessage.error('注册失败，请检查参数 JSON 格式');
    console.error(error);
  }
}

async function handleDelete(tool: CustomToolInfo): Promise<void> {
  await ElMessageBox.confirm(`确定删除工具「${tool.name}」吗？`, '删除确认', { type: 'warning' });
  await deleteCustomTool(tool.id);
  ElMessage.success('已删除');
  await fetchTools();
}

async function handleTest(tool: CustomToolInfo): Promise<void> {
  testingId.value = tool.id;
  testResult.value = '';
  testDialogVisible.value = true;
  const result = await testCustomTool(tool.id, {});
  testResult.value = JSON.stringify(result, null, 2);
}

onMounted(() => {
  void fetchTools();
});
</script>

<template>
  <div v-loading="loading" class="tools-management">
    <SectionHeader title="工具管理" description="注册和管理自定义 REST 工具">
      <template #actions>
        <el-button type="primary" :icon="Plus" @click="openCreate">注册工具</el-button>
      </template>
    </SectionHeader>

    <el-table :data="tools" stripe>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
      <el-table-column prop="invoke_url" label="调用 URL" min-width="220" show-overflow-tooltip />
      <el-table-column prop="auth_type" label="认证" width="100" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="handleTest(row)">测试</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="注册自定义工具" width="640px">
      <el-form label-width="110px">
        <el-form-item label="工具名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
        <el-form-item label="调用 URL"><el-input v-model="form.invoke_url" /></el-form-item>
        <el-form-item label="认证方式">
          <el-select v-model="form.auth_type" style="width: 100%">
            <el-option label="无" value="none" />
            <el-option label="Bearer Token" value="bearer" />
            <el-option label="API Key" value="api_key" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.auth_type !== 'none'" label="凭证">
          <el-input v-model="form.auth_token" type="password" show-password />
        </el-form-item>
        <el-form-item label="参数 Schema">
          <el-input v-model="form.parameters_schema" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">注册</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="testDialogVisible" title="测试结果" width="560px">
      <pre class="test-result">{{ testResult }}</pre>
    </el-dialog>
  </div>
</template>

<style scoped>
.test-result {
  max-height: 360px;
  overflow: auto;
  background: #f7f8fa;
  padding: 12px;
  border-radius: 8px;
}
</style>
