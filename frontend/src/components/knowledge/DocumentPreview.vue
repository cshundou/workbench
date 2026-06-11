<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import * as mammoth from 'mammoth';
import * as XLSX from 'xlsx';
import axios from 'axios';
import * as pdfjsLib from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;

const props = defineProps<{
  kbId: number;
  docId: number;
  fileName: string;
  fileType: string;
  visible: boolean;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
}>();

const loading = ref(false);
const previewHtml = ref('');
const sheetRows = ref<string[][]>([]);
const pdfPages = ref<string[]>([]);

const dialogVisible = computed({
  get: () => props.visible,
  set: (val: boolean) => emit('update:visible', val),
});

const isPdf = computed(() => ['pdf'].includes(props.fileType.toLowerCase()));
const isWord = computed(() => ['docx', 'doc'].includes(props.fileType.toLowerCase()));
const isExcel = computed(() => ['xlsx', 'xls'].includes(props.fileType.toLowerCase()));

async function fetchFileBlob(): Promise<Blob> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1';
  const token = localStorage.getItem('token');
  const response = await axios.get(
    `${baseURL}/knowledge-bases/${props.kbId}/documents/${props.docId}/download`,
    {
      responseType: 'blob',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  );
  return response.data as Blob;
}

async function loadPreview(): Promise<void> {
  loading.value = true;
  previewHtml.value = '';
  sheetRows.value = [];
  pdfPages.value = [];
  try {
    const blob = await fetchFileBlob();
    const ext = props.fileType.toLowerCase();

    if (ext === 'pdf') {
      const buffer = await blob.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: buffer }).promise;
      const pages: string[] = [];
      for (let i = 1; i <= pdf.numPages; i += 1) {
        const page = await pdf.getPage(i);
        const viewport = page.getViewport({ scale: 1.2 });
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        if (!context) {
          continue;
        }
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await page.render({ canvasContext: context, viewport }).promise;
        pages.push(canvas.toDataURL());
      }
      pdfPages.value = pages;
    } else if (['docx', 'doc'].includes(ext)) {
      const buffer = await blob.arrayBuffer();
      const result = await mammoth.convertToHtml({ arrayBuffer: buffer });
      previewHtml.value = result.value;
    } else if (['xlsx', 'xls'].includes(ext)) {
      const buffer = await blob.arrayBuffer();
      const workbook = XLSX.read(buffer, { type: 'array' });
      const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
      sheetRows.value = XLSX.utils.sheet_to_json<string[]>(firstSheet, { header: 1 });
    } else {
      previewHtml.value = '<p>暂不支持该格式在线预览</p>';
    }
  } catch (error) {
    console.error('[DocumentPreview]', error);
    ElMessage.error('文档预览加载失败');
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      loadPreview();
    }
  },
);

onMounted(() => {
  if (props.visible) {
    loadPreview();
  }
});
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="`预览：${fileName}`"
    width="80%"
    top="5vh"
    destroy-on-close
  >
    <div v-loading="loading" class="preview-body">
      <div v-if="isPdf" class="pdf-pages">
        <img v-for="(page, index) in pdfPages" :key="index" :src="page" alt="PDF 页面" />
      </div>
      <div v-else-if="isWord" class="word-preview" v-html="previewHtml" />
      <div v-else-if="isExcel" class="excel-preview">
        <el-table :data="sheetRows.slice(1)" stripe max-height="520">
          <el-table-column
            v-for="(col, colIndex) in sheetRows[0] || []"
            :key="colIndex"
            :label="String(col)"
            min-width="120"
          >
            <template #default="{ row }">
              {{ row[colIndex] }}
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-empty v-else description="不支持预览此格式" />
    </div>
  </el-dialog>
</template>

<style lang="scss" scoped>
.preview-body {
  min-height: 320px;
  max-height: 70vh;
  overflow: auto;
}

.pdf-pages img {
  display: block;
  width: 100%;
  margin-bottom: 12px;
  border: 1px solid $border-color;
}

.word-preview {
  padding: 12px;
  line-height: 1.7;
}
</style>
