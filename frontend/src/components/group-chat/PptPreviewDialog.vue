<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { Close, Download, Minus, Plus, Printer } from '@element-plus/icons-vue';
import { downloadGroupChatDeliverable } from '@/api/groupChat';
import type { Deliverable } from '@/utils/deliverables';

const props = defineProps<{
  visible: boolean;
  deliverable: Deliverable | null;
  sessionId?: number;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
}>();

const previewRef = ref<HTMLElement | null>(null);
const previewer = ref<{ preview: (data: ArrayBuffer) => Promise<unknown> } | null>(null);
const loading = ref(false);
const scale = ref(1);
const currentSlide = ref(1);
const totalSlides = ref(0);

const title = computed(() => props.deliverable?.name || 'PPT 预览');
const filename = computed(() => {
  const name = props.deliverable?.name || 'presentation.pptx';
  return name.toLowerCase().endsWith('.pptx') ? name : `${name}.pptx`;
});

function close(): void {
  emit('update:visible', false);
}

async function initPreviewer(): Promise<void> {
  if (!previewRef.value) return;
  previewRef.value.innerHTML = '';
  const mod = await import('pptx-preview');
  previewer.value = mod.init(previewRef.value, {
    width: Math.round(960 * scale.value),
    height: Math.round(540 * scale.value),
  });
}

async function loadPptx(): Promise<void> {
  if (!props.visible || !props.deliverable || props.deliverable.fileType !== 'pptx') return;
  if (!props.sessionId) {
    ElMessage.warning('缺少会话 ID，无法加载 PPT');
    return;
  }
  loading.value = true;
  try {
    await initPreviewer();
    const blob = await downloadGroupChatDeliverable(props.sessionId, filename.value);
    const buffer = await blob.arrayBuffer();
    await previewer.value?.preview(buffer);
    await nextTick();
    const slides = previewRef.value?.querySelectorAll('.pptx-preview-slide');
    totalSlides.value = slides?.length || props.deliverable.slideCount || 1;
    currentSlide.value = 1;
    scrollToSlide(1);
  } catch (err) {
    console.error('[PptPreview] 加载失败', err);
    ElMessage.error('PPT 预览加载失败');
  } finally {
    loading.value = false;
  }
}

function scrollToSlide(index: number): void {
  const slides = previewRef.value?.querySelectorAll('.pptx-preview-slide');
  if (!slides?.length) return;
  const target = Math.min(Math.max(index, 1), slides.length);
  currentSlide.value = target;
  slides[target - 1]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function prevSlide(): void {
  scrollToSlide(currentSlide.value - 1);
}

function nextSlide(): void {
  scrollToSlide(currentSlide.value + 1);
}

function zoomIn(): void {
  scale.value = Math.min(scale.value + 0.1, 2);
  void reloadWithScale();
}

function zoomOut(): void {
  scale.value = Math.max(scale.value - 0.1, 0.5);
  void reloadWithScale();
}

async function reloadWithScale(): Promise<void> {
  if (!props.visible) return;
  await loadPptx();
}

async function handleDownloadPptx(): Promise<void> {
  if (!props.sessionId) return;
  try {
    const blob = await downloadGroupChatDeliverable(props.sessionId, filename.value);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename.value;
    link.click();
    URL.revokeObjectURL(url);
    ElMessage.success('PPT 已下载');
  } catch {
    ElMessage.error('下载失败');
  }
}

function handleExportPdf(): void {
  window.print();
  ElMessage.info('请在打印对话框中选择「另存为 PDF」');
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      scale.value = 1;
      void loadPptx();
    }
  },
);

onBeforeUnmount(() => {
  previewRef.value = null;
});
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="920px"
    top="4vh"
    destroy-on-close
    class="ppt-preview-dialog"
    @update:model-value="emit('update:visible', $event)"
  >
    <div v-loading="loading" class="preview-toolbar">
      <div class="toolbar-group">
        <el-button :icon="Minus" circle size="small" @click="zoomOut" />
        <span class="scale-label">{{ Math.round(scale * 100) }}%</span>
        <el-button :icon="Plus" circle size="small" @click="zoomIn" />
      </div>
      <div class="toolbar-group">
        <el-button size="small" :disabled="currentSlide <= 1" @click="prevSlide">上一页</el-button>
        <span class="page-label">{{ currentSlide }} / {{ totalSlides || '?' }}</span>
        <el-button size="small" :disabled="currentSlide >= totalSlides" @click="nextSlide">
          下一页
        </el-button>
      </div>
      <div class="toolbar-group">
        <el-button :icon="Download" size="small" @click="handleDownloadPptx">下载 PPT</el-button>
        <el-button :icon="Printer" size="small" @click="handleExportPdf">导出 PDF</el-button>
      </div>
    </div>

    <div ref="previewRef" class="preview-container" />

    <template #footer>
      <el-button :icon="Close" @click="close">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.preview-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.scale-label,
.page-label {
  font-size: 12px;
  color: $text-secondary;
  min-width: 48px;
  text-align: center;
}

.preview-container {
  max-height: 62vh;
  overflow: auto;
  border: 1px solid $border-color;
  border-radius: 8px;
  background: #f5f6f8;
  padding: 12px;
}

@media print {
  .preview-toolbar,
  :deep(.el-dialog__header),
  :deep(.el-dialog__footer) {
    display: none !important;
  }

  .preview-container {
    max-height: none;
    border: none;
  }
}
</style>
