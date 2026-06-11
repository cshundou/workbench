<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import { Plus, VideoPlay, Edit, Delete, Share } from '@element-plus/icons-vue';
import type { WorkflowInfo } from '@/api/workflow';
import { useGraphStore } from '@/stores/graph';
import { useUserStore } from '@/stores/user';
import ApiKeyHintBanner from '@/components/settings/ApiKeyHintBanner.vue';

const router = useRouter();
const graphStore = useGraphStore();
const userStore = useUserStore();

const queryParams = reactive({
  page: 1,
  page_size: 12,
});

const dialogVisible = ref(false);
const dialogTitle = ref('新建工作流');
const isEdit = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref<FormInstance>();
const submitLoading = ref(false);

const wfForm = reactive({
  name: '',
  description: '',
  is_public: false,
});

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入工作流名称', trigger: 'blur' },
    { min: 2, max: 100, message: '名称长度为 2-100 个字符', trigger: 'blur' },
  ],
};

const canWrite = computed(() => userStore.hasPermission('workflow:write'));

async function fetchList(): Promise<void> {
  await graphStore.fetchWorkflows(queryParams);
}

function handlePageChange(page: number): void {
  queryParams.page = page;
  fetchList();
}

function openCreateDialog(): void {
  isEdit.value = false;
  editingId.value = null;
  dialogTitle.value = '新建工作流';
  wfForm.name = '';
  wfForm.description = '';
  wfForm.is_public = false;
  dialogVisible.value = true;
}

function openEditDialog(wf: WorkflowInfo): void {
  isEdit.value = true;
  editingId.value = wf.id;
  dialogTitle.value = '编辑工作流';
  wfForm.name = wf.name;
  wfForm.description = wf.description || '';
  wfForm.is_public = wf.is_public;
  dialogVisible.value = true;
}

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  submitLoading.value = true;
  try {
    if (isEdit.value && editingId.value) {
      await graphStore.editWorkflow(editingId.value, { ...wfForm });
      ElMessage.success('更新成功');
    } else {
      await graphStore.addWorkflow({ ...wfForm });
      ElMessage.success('创建成功');
    }
    dialogVisible.value = false;
    fetchList();
  } finally {
    submitLoading.value = false;
  }
}

async function handleDelete(wf: WorkflowInfo): Promise<void> {
  await ElMessageBox.confirm(`确定删除工作流「${wf.name}」？`, '删除确认', {
    type: 'warning',
  });
  await graphStore.removeWorkflow(wf.id);
  ElMessage.success('删除成功');
}

function goExecute(wf: WorkflowInfo): void {
  router.push({ name: 'WorkflowExecute', params: { id: wf.id } });
}

onMounted(() => {
  fetchList();
});
</script>

<template>
  <div class="workflow-list-page">
    <ApiKeyHintBanner scene="workflow" />
    <div class="page-header">
      <div>
        <h2 class="page-title">工作流模板</h2>
        <p class="page-desc">LangGraph 多智能体协同工作流，支持任务拆解、并行执行与人工介入</p>
      </div>
      <el-button v-if="canWrite" type="primary" :icon="Plus" @click="openCreateDialog">
        新建工作流
      </el-button>
    </div>

    <el-row v-loading="graphStore.isLoading" :gutter="16">
      <el-col
        v-for="wf in graphStore.workflows"
        :key="wf.id"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
      >
        <el-card shadow="never" class="wf-card">
          <div class="wf-card-header">
            <el-icon :size="28" class="wf-icon"><Share /></el-icon>
            <el-tag v-if="wf.is_public" size="small" type="success">公开</el-tag>
          </div>
          <h3 class="wf-name">{{ wf.name }}</h3>
          <p class="wf-desc">{{ wf.description || '暂无描述' }}</p>
          <div class="wf-meta">
            <span>{{ wf.graph_definition?.nodes?.length || 0 }} 个节点</span>
          </div>
          <div class="wf-actions">
            <el-button type="primary" size="small" :icon="VideoPlay" @click="goExecute(wf)">
              执行
            </el-button>
            <template v-if="canWrite">
              <el-button size="small" :icon="Edit" @click="openEditDialog(wf)" />
              <el-button size="small" type="danger" :icon="Delete" @click="handleDelete(wf)" />
            </template>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty
      v-if="!graphStore.isLoading && graphStore.workflows.length === 0"
      description="暂无工作流，点击新建创建第一个模板"
    />

    <div v-if="graphStore.total > queryParams.page_size" class="pagination-wrap">
      <el-pagination
        v-model:current-page="queryParams.page"
        :page-size="queryParams.page_size"
        :total="graphStore.total"
        layout="prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="wfForm" :rules="formRules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="wfForm.name" placeholder="请输入工作流名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="wfForm.description"
            type="textarea"
            :rows="3"
            placeholder="工作流描述（可选）"
          />
        </el-form-item>
        <el-form-item label="公开">
          <el-switch v-model="wfForm.is_public" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.workflow-list-page {
  padding: 4px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-title {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 600;
}

.page-desc {
  margin: 0;
  font-size: 13px;
  color: $text-secondary;
}

.wf-card {
  margin-bottom: 16px;
  transition: border-color 0.2s ease;

  &:hover {
    border-color: $primary-color;
  }
}

.wf-icon {
  color: $primary-color;
}

.wf-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.wf-name {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 600;
}

.wf-desc {
  margin: 0 0 8px;
  font-size: 13px;
  color: $text-secondary;
  min-height: 36px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.wf-meta {
  font-size: 12px;
  color: $text-secondary;
  margin-bottom: 12px;
}

.wf-actions {
  display: flex;
  gap: 8px;
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
