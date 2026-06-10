<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { ArrowLeft, ChatDotRound } from '@element-plus/icons-vue';
import DocumentUploader from '@/components/knowledge/DocumentUploader.vue';
import DocumentList from '@/components/knowledge/DocumentList.vue';
import { deleteDocument, downloadDocument, getDocumentProgress } from '@/api/rag';
import type { DocumentInfo } from '@/api/rag';
import { useRagStore } from '@/stores/rag';
import { useUserStore } from '@/stores/user';

const route = useRoute();
const router = useRouter();
const ragStore = useRagStore();
const userStore = useUserStore();

const kbId = computed(() => Number(route.params.id));
const canWrite = computed(() => userStore.hasPermission('knowledge:write'));

/** 文档解析进度映射 */
const progressMap = ref<Record<number, number>>({});
let progressTimer: ReturnType<typeof setInterval> | null = null;

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
});

onUnmounted(() => {
  stopProgressPolling();
});
</script>

<template>
  <div class="knowledge-detail">
    <div class="detail-header flex-between">
      <div class="header-left flex-center">
        <el-button text :icon="ArrowLeft" @click="goBack">返回列表</el-button>
        <h2 class="kb-title">{{ ragStore.currentKb?.name || '知识库详情' }}</h2>
      </div>
      <el-button type="primary" :icon="ChatDotRound" @click="goChat">进入问答</el-button>
    </div>

    <p v-if="ragStore.currentKb?.description" class="kb-description">
      {{ ragStore.currentKb.description }}
    </p>

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
        @refresh="refreshProgress"
      />
    </el-card>
  </div>
</template>

<style lang="scss" scoped>
.knowledge-detail {
  min-height: 400px;
}

.detail-header {
  margin-bottom: 12px;
}

.header-left {
  gap: 8px;
}

.kb-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: $text-primary;
}

.kb-description {
  margin: 0 0 20px;
  font-size: 14px;
  color: $text-secondary;
}

.upload-card {
  margin-bottom: 20px;
}
</style>
