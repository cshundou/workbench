<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { ArrowLeft, ChatDotRound } from '@element-plus/icons-vue';
import DocumentUploader from '@/components/knowledge/DocumentUploader.vue';
import DocumentList from '@/components/knowledge/DocumentList.vue';
import DocumentPreview from '@/components/knowledge/DocumentPreview.vue';
import { deleteDocument, downloadDocument, getDocumentProgress, getOptimizationHints, getSearchStats } from '@/api/rag';
import type { DocumentInfo, OptimizationHint, SearchStats } from '@/api/rag';
import { useRagStore } from '@/stores/rag';
import { useUserStore } from '@/stores/user';
import SectionHeader from '@/components/layout/SectionHeader.vue';

const route = useRoute();
const router = useRouter();
const ragStore = useRagStore();
const userStore = useUserStore();

const kbId = computed(() => Number(route.params.id));
const canWrite = computed(() => userStore.hasPermission('knowledge:write'));

const activeTab = ref('documents');
const previewVisible = ref(false);
const previewDoc = ref<DocumentInfo | null>(null);
const searchStats = ref<SearchStats | null>(null);
const optimizationHints = ref<OptimizationHint[]>([]);
/** 文档解析进度映射 */
const progressMap = ref<Record<number, number>>({});
let progressTimer: ReturnType<typeof setInterval> | null = null;

async function loadSearchAnalysis(): Promise<void> {
  try {
    searchStats.value = await getSearchStats(kbId.value);
    const hintsResult = await getOptimizationHints(kbId.value);
    optimizationHints.value = hintsResult.hints;
  } catch (error) {
    console.error('[Search Analysis Error]', error);
  }
}

function handlePreview(doc: DocumentInfo): void {
  previewDoc.value = doc;
  previewVisible.value = true;
}

/** 加载知识库与文档 */
async function loadData(): Promise<void> {
  await ragStore.fetchKnowledgeBase(kbId.value);
  await ragStore.fetchDocuments(kbId.value);
  await refreshProgress();
}

/** 刷新所有待处理文档的解析进度 */
async function refreshProgress(): Promise<void> {
  const pendingDocs = ragStore.documents.filter((doc) => doc.status === 0);
  if (pendingDocs.length === 0) {
    return;
  }

  await Promise.all(
    pendingDocs.map(async (doc) => {
      try {
        const progress = await getDocumentProgress(kbId.value, doc.id);
        progressMap.value[doc.id] = progress.progress;
        if (progress.status !== 0) {
          doc.status = progress.status;
          doc.total_chunks = progress.total_chunks ?? doc.total_chunks;
        }
      } catch (error) {
        console.error(`[Progress Error] doc ${doc.id}`, error);
      }
    }),
  );
}

/** 启动进度轮询 */
function startProgressPolling(): void {
  stopProgressPolling();
  progressTimer = setInterval(() => {
    const hasPending = ragStore.documents.some((doc) => doc.status === 0);
    if (hasPending) {
      refreshProgress();
    } else {
      stopProgressPolling();
    }
  }, 3000);
}

function stopProgressPolling(): void {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
}

/** 文档上传完成 */
function handleUploaded(doc: DocumentInfo): void {
  const exists = ragStore.documents.find((item) => item.id === doc.id);
  if (!exists) {
    ragStore.documents.unshift(doc);
  }
  progressMap.value[doc.id] = 0;
  startProgressPolling();
}

/** 全部上传完成 */
async function handleAllDone(): Promise<void> {
  await ragStore.fetchDocuments(kbId.value);
  startProgressPolling();
}

/** 删除文档 */
async function handleDelete(doc: DocumentInfo): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除文档「${doc.name}」吗？`, '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    });
    await deleteDocument(kbId.value, doc.id);
    ElMessage.success('删除成功');
    await ragStore.fetchDocuments(kbId.value);
  } catch (error) {
    if (error !== 'cancel') {
      console.error('[Delete Document Error]', error);
    }
  }
}

/** 下载文档 */
async function handleDownload(doc: DocumentInfo): Promise<void> {
  try {
    await downloadDocument(kbId.value, doc.id, doc.name);
  } catch (error) {
    console.error('[Download Document Error]', error);
  }
}

function goBack(): void {
  router.push({ name: 'KnowledgeList' });
}

function goChat(): void {
  router.push({ name: 'KnowledgeChat', params: { id: kbId.value } });
}

onMounted(() => {
  loadData().then(() => startProgressPolling());
  loadSearchAnalysis();
});

onUnmounted(() => {
  stopProgressPolling();
});
</script>

<template>
  <div class="knowledge-detail">
    <SectionHeader
      :title="ragStore.currentKb?.name || '知识库详情'"
      :description="ragStore.currentKb?.description || '管理文档上传与解析进度'"
    >
      <template #actions>
        <el-button text :icon="ArrowLeft" @click="goBack">返回列表</el-button>
        <el-button type="primary" :icon="ChatDotRound" round @click="goChat">进入问答</el-button>
      </template>
    </SectionHeader>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="文档管理" name="documents">
        <el-card shadow="never" class="upload-card">
          <template #header>
            <span>上传文档</span>
          </template>
          <DocumentUploader
            :kb-id="kbId"
            :disabled="!canWrite"
            @uploaded="handleUploaded"
            @all-done="handleAllDone"
          />
        </el-card>

        <el-card shadow="never">
          <DocumentList
            :documents="ragStore.documents"
            :progress-map="progressMap"
            :loading="ragStore.isLoading"
            :can-write="canWrite"
            @delete="handleDelete"
            @download="handleDownload"
            @preview="handlePreview"
            @refresh="refreshProgress"
          />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="检索分析" name="analysis">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-statistic title="检索次数" :value="searchStats?.total_queries || 0" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="命中率" :value="((searchStats?.hit_rate || 0) * 100).toFixed(1)" suffix="%" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="平均延迟(ms)" :value="searchStats?.avg_latency_ms || 0" />
          </el-col>
        </el-row>
        <el-divider />
        <h4>优化建议</h4>
        <el-empty v-if="!optimizationHints.length" description="暂无优化建议" />
        <el-alert
          v-for="(hint, index) in optimizationHints"
          :key="index"
          :title="hint.title"
          :description="hint.description"
          :type="hint.level === 'warning' ? 'warning' : 'info'"
          show-icon
          class="hint-item"
        />
      </el-tab-pane>
    </el-tabs>

    <DocumentPreview
      v-if="previewDoc"
      v-model:visible="previewVisible"
      :kb-id="kbId"
      :doc-id="previewDoc.id"
      :file-name="previewDoc.name"
      :file-type="previewDoc.file_type"
    />
  </div>
</template>

<style lang="scss" scoped>
.knowledge-detail {
  min-height: 400px;
}

.upload-card {
  margin-bottom: 20px;
}

.hint-item {
  margin-bottom: 12px;
}
</style>
