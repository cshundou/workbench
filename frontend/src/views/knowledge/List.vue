<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import { Plus, Search, Edit, Delete, ChatDotRound, FolderOpened } from '@element-plus/icons-vue';
import { createKnowledgeBase, updateKnowledgeBase, deleteKnowledgeBase } from '@/api/rag';
import type { KnowledgeBaseInfo } from '@/api/rag';
import {
  getAvailableModels,
  formatEmbeddingOptionLabel,
  PROVIDER_LABELS,
  type AIModelEntity,
} from '@/api/models';
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
const embeddingModelsLoading = ref(false);
const embeddingModelsWarning = ref('');
const embeddingModels = ref<AIModelEntity[]>([]);
const originalEmbeddingModel = ref('');

const EMBEDDING_PROVIDER_ORDER = ['openai', 'tongyi', 'doubao', 'minimax'] as const;

const embeddingsByProvider = computed(() => {
  const grouped: Record<string, AIModelEntity[]> = {};
  for (const provider of EMBEDDING_PROVIDER_ORDER) {
    grouped[provider] = embeddingModels.value.filter((item) => item.provider === provider);
  }
  return grouped;
});

const kbForm = reactive({
  name: '',
  description: '',
  is_public: false,
  embedding_model: 'text-embedding-3-small',
});

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入知识库名称', trigger: 'blur' },
    { min: 2, max: 100, message: '名称长度为 2-100 个字符', trigger: 'blur' },
  ],
};

const canWrite = computed(() => userStore.hasPermission('kb:write'));
const canDelete = computed(() => userStore.hasPermission('kb:delete'));

/** 加载可用 Embedding 模型 */
async function loadEmbeddingModels(refresh = false): Promise<void> {
  embeddingModelsLoading.value = true;
  embeddingModelsWarning.value = '';
  try {
    const response = await getAvailableModels('text-embedding', refresh);
    embeddingModels.value = response.models.filter((item) => item.status !== 'deprecated');
    if (response.warning) {
      embeddingModelsWarning.value = response.warning;
    }
    if (
      embeddingModels.value.length &&
      !embeddingModels.value.some((item) => item.model === kbForm.embedding_model)
    ) {
      kbForm.embedding_model = embeddingModels.value[0].model;
    }
  } catch (error) {
    console.error('[Load Embedding Models Error]', error);
    embeddingModelsWarning.value = '加载 Embedding 模型失败，请检查 API 密钥配置';
  } finally {
    embeddingModelsLoading.value = false;
  }
}

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
async function openCreateDialog(): Promise<void> {
  isEdit.value = false;
  editingId.value = null;
  dialogTitle.value = '新建知识库';
  kbForm.name = '';
  kbForm.description = '';
  kbForm.is_public = false;
  kbForm.embedding_model =
    embeddingModels.value[0]?.model || 'text-embedding-3-small';
  originalEmbeddingModel.value = '';
  await loadEmbeddingModels();
  dialogVisible.value = true;
}

/** 打开编辑对话框 */
async function openEditDialog(kb: KnowledgeBaseInfo): Promise<void> {
  isEdit.value = true;
  editingId.value = kb.id;
  dialogTitle.value = '编辑知识库';
  kbForm.name = kb.name;
  kbForm.description = kb.description || '';
  kbForm.is_public = kb.is_public;
  kbForm.embedding_model = kb.embedding_model;
  originalEmbeddingModel.value = kb.embedding_model;
  await loadEmbeddingModels();
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
    if (
      isEdit.value &&
      originalEmbeddingModel.value &&
      kbForm.embedding_model !== originalEmbeddingModel.value
    ) {
      await ElMessageBox.confirm(
        '切换 Embedding 模型后，已有文档需要重新解析才能使用新向量，是否继续？',
        '切换模型确认',
        { confirmButtonText: '继续保存', cancelButtonText: '取消', type: 'warning' },
      );
    }

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
  loadEmbeddingModels();
});
</script>

<template>
  <div class="knowledge-list">
    <ApiKeyHintBanner scene="rag" />

    <SectionHeader title="知识库" description="企业私有知识沉淀，支持增强 RAG 检索与引用溯源">
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
      <el-empty
        v-if="!ragStore.isLoading && ragStore.knowledgeBases.length === 0"
        description="暂无知识库"
      />

      <el-card v-for="kb in ragStore.knowledgeBases" :key="kb.id" shadow="never" class="kb-card">
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
          <el-button text type="primary" :icon="ChatDotRound" @click="goChat(kb)"> 问答 </el-button>
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
          <div class="embedding-model-row">
            <el-select
              v-model="kbForm.embedding_model"
              :loading="embeddingModelsLoading"
              placeholder="选择 Embedding 模型"
              style="width: 100%"
            >
              <el-option-group
                v-for="provider in EMBEDDING_PROVIDER_ORDER"
                :key="provider"
                :label="PROVIDER_LABELS[provider]"
              >
                <el-option
                  v-for="item in embeddingsByProvider[provider]"
                  :key="item.model"
                  :label="formatEmbeddingOptionLabel(item)"
                  :value="item.model"
                />
              </el-option-group>
            </el-select>
            <el-button
              :loading="embeddingModelsLoading"
              @click="loadEmbeddingModels(true)"
            >
              刷新
            </el-button>
          </div>
          <p v-if="embeddingModelsWarning" class="embedding-hint warning">
            {{ embeddingModelsWarning }}
          </p>
          <p v-else class="embedding-hint">
            仅显示已配置 API 密钥对应的向量模型；切换模型后需重新解析文档。
          </p>
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
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;

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

.embedding-model-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.embedding-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: $text-secondary;
  line-height: 1.5;

  &.warning {
    color: $warning-color;
  }
}
</style>
