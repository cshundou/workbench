<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import { Plus, Search, Edit, Delete, ChatDotRound, FolderOpened } from '@element-plus/icons-vue';
import {
  createKnowledgeBase,
  updateKnowledgeBase,
  deleteKnowledgeBase,
} from '@/api/rag';
import type { KnowledgeBaseInfo } from '@/api/rag';
import { useRagStore } from '@/stores/rag';
import { useUserStore } from '@/stores/user';
import ApiKeyHintBanner from '@/components/settings/ApiKeyHintBanner.vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';

const router = useRouter();
const ragStore = useRagStore();
const userStore = useUserStore();

const queryParams = reactive({
  page: 1,
  page_size: 12,
  keyword: '',
});

const dialogVisible = ref(false);
const dialogTitle = ref('新建知识库');
const isEdit = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref<FormInstance>();
const submitLoading = ref(false);

const kbForm = reactive({
  name: '',
  description: '',
  is_public: false,
  embedding_model: 'text-embedding-ada-002',
});

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入知识库名称', trigger: 'blur' },
    { min: 2, max: 100, message: '名称长度为 2-100 个字符', trigger: 'blur' },
  ],
};

const canWrite = computed(() => userStore.hasPermission('knowledge:write'));

/** 加载知识库列表 */
async function fetchList(): Promise<void> {
  await ragStore.fetchKnowledgeBases(queryParams);
}

/** 搜索 */
function handleSearch(): void {
  queryParams.page = 1;
  fetchList();
}

/** 分页切换 */
function handlePageChange(page: number): void {
  queryParams.page = page;
  fetchList();
}

/** 打开新建对话框 */
function openCreateDialog(): void {
  isEdit.value = false;
  editingId.value = null;
  dialogTitle.value = '新建知识库';
  kbForm.name = '';
  kbForm.description = '';
  kbForm.is_public = false;
  kbForm.embedding_model = 'text-embedding-ada-002';
  dialogVisible.value = true;
}

/** 打开编辑对话框 */
function openEditDialog(kb: KnowledgeBaseInfo): void {
  isEdit.value = true;
  editingId.value = kb.id;
  dialogTitle.value = '编辑知识库';
  kbForm.name = kb.name;
  kbForm.description = kb.description || '';
  kbForm.is_public = kb.is_public;
  kbForm.embedding_model = kb.embedding_model;
  dialogVisible.value = true;
}

/** 提交表单 */
async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }

  submitLoading.value = true;
  try {
    if (isEdit.value && editingId.value) {
      await updateKnowledgeBase(editingId.value, {
        name: kbForm.name,
        description: kbForm.description || undefined,
        is_public: kbForm.is_public,
        embedding_model: kbForm.embedding_model,
      });
      ElMessage.success('知识库更新成功');
    } else {
      await createKnowledgeBase({
        name: kbForm.name,
        description: kbForm.description || undefined,
        is_public: kbForm.is_public,
        embedding_model: kbForm.embedding_model,
      });
      ElMessage.success('知识库创建成功');
    }
    dialogVisible.value = false;
    await fetchList();
  } catch (error) {
    console.error('[Submit Knowledge Base Error]', error);
  } finally {
    submitLoading.value = false;
  }
}

/** 删除知识库 */
async function handleDelete(kb: KnowledgeBaseInfo): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除知识库「${kb.name}」吗？此操作不可恢复。`, '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    });
    await deleteKnowledgeBase(kb.id);
    ElMessage.success('删除成功');
    await fetchList();
  } catch (error) {
    if (error !== 'cancel') {
      console.error('[Delete Knowledge Base Error]', error);
    }
  }
}

/** 进入详情 */
function goDetail(kb: KnowledgeBaseInfo): void {
  router.push({ name: 'KnowledgeDetail', params: { id: kb.id } });
}

/** 进入问答 */
function goChat(kb: KnowledgeBaseInfo): void {
  router.push({ name: 'KnowledgeChat', params: { id: kb.id } });
}

onMounted(() => {
  fetchList();
});
</script>

<template>
  <div class="knowledge-list">
    <ApiKeyHintBanner scene="rag" />

    <SectionHeader
      title="知识库"
      description="企业私有知识沉淀，支持增强 RAG 检索与引用溯源"
    >
      <template #actions>
        <el-button v-if="canWrite" type="primary" :icon="Plus" round @click="openCreateDialog">
          新建知识库
        </el-button>
      </template>
    </SectionHeader>

    <div class="search-bar">
      <el-input
        v-model="queryParams.keyword"
        placeholder="搜索知识库名称"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-button type="primary" :icon="Search" round @click="handleSearch">搜索</el-button>
    </div>

    <div v-loading="ragStore.isLoading" class="kb-grid">
      <el-empty v-if="!ragStore.isLoading && ragStore.knowledgeBases.length === 0" description="暂无知识库" />

      <el-card
        v-for="kb in ragStore.knowledgeBases"
        :key="kb.id"
        shadow="never"
        class="kb-card"
      >
        <div class="kb-card-header">
          <el-icon :size="24" class="kb-icon"><FolderOpened /></el-icon>
          <div class="kb-info">
            <h3 class="kb-name" @click="goDetail(kb)">{{ kb.name }}</h3>
            <p class="kb-desc">{{ kb.description || '暂无描述' }}</p>
          </div>
        </div>

        <div class="kb-meta">
          <el-tag v-if="kb.is_public" size="small" type="success">公开</el-tag>
          <el-tag v-else size="small" type="info">私有</el-tag>
          <span class="doc-count">{{ kb.document_count ?? 0 }} 篇文档</span>
        </div>

        <div class="kb-actions">
          <el-button text type="primary" :icon="FolderOpened" @click="goDetail(kb)">
            管理文档
          </el-button>
          <el-button text type="primary" :icon="ChatDotRound" @click="goChat(kb)">
            问答
          </el-button>
          <template v-if="canWrite">
            <el-button text type="primary" :icon="Edit" @click="openEditDialog(kb)" />
            <el-button text type="danger" :icon="Delete" @click="handleDelete(kb)" />
          </template>
        </div>
      </el-card>
    </div>

    <div v-if="ragStore.total > queryParams.page_size" class="pagination-wrap">
      <el-pagination
        v-model:current-page="queryParams.page"
        :page-size="queryParams.page_size"
        :total="ragStore.total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" destroy-on-close>
      <el-form ref="formRef" :model="kbForm" :rules="formRules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="kbForm.name" placeholder="请输入知识库名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="kbForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入知识库描述"
          />
        </el-form-item>
        <el-form-item label="嵌入模型">
          <el-select v-model="kbForm.embedding_model" style="width: 100%">
            <el-option label="text-embedding-ada-002" value="text-embedding-ada-002" />
            <el-option label="text-embedding-3-small" value="text-embedding-3-small" />
            <el-option label="text-embedding-3-large" value="text-embedding-3-large" />
          </el-select>
        </el-form-item>
        <el-form-item label="是否公开">
          <el-switch v-model="kbForm.is_public" />
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
.knowledge-list {
  min-height: 400px;
}

.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.search-input {
  width: 280px;
}

.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  min-height: 200px;
}

.kb-card {
  border-radius: $border-radius-lg;
  transition: box-shadow 0.2s ease, transform 0.2s ease;

  &:hover {
    box-shadow: $shadow-card-hover;
    transform: translateY(-2px);
  }
}

.kb-icon {
  color: $primary-color;
  flex-shrink: 0;
}

.kb-card-header {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.kb-name {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
  cursor: pointer;

  &:hover {
    color: $primary-color;
  }
}

.kb-desc {
  margin: 0;
  font-size: 13px;
  color: $text-secondary;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.kb-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.doc-count {
  font-size: 13px;
  color: $text-secondary;
}

.kb-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-top: 12px;
}

.pagination-wrap {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}
</style>
