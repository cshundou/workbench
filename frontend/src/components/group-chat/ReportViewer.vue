<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { Close, Download, CopyDocument, Printer } from '@element-plus/icons-vue';
import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue';
import ChartRenderer from '@/components/group-chat/ChartRenderer.vue';
import { extractTocFromMarkdown } from '@/utils/markdown';
import type { Deliverable } from '@/utils/deliverables';

const props = defineProps<{
  visible: boolean;
  deliverable: Deliverable | null;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
}>();

const fontSize = ref(15);
const activeTocId = ref('');

const content = computed(() => props.deliverable?.content || '');
const title = computed(() => props.deliverable?.name || '报告详情');
const toc = computed(() => extractTocFromMarkdown(content.value));
const showChart = computed(
  () => props.deliverable?.category === 'chart' && props.deliverable?.chartConfig,
);

function close(): void {
  emit('update:visible', false);
}

function scrollToHeading(id: string): void {
  activeTocId.value = id;
  const el = document.getElementById(id);
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function copyFullText(): Promise<void> {
  try {
    await navigator.clipboard.writeText(content.value);
    ElMessage.success('全文已复制');
  } catch {
    ElMessage.error('复制失败');
  }
}

function exportMarkdown(): void {
  const blob = new Blob([content.value], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${title.value.replace(/[/\\?%*:|"<>]/g, '_')}.md`;
  link.click();
  URL.revokeObjectURL(url);
  ElMessage.success('Markdown 已导出');
}

function handlePrint(): void {
  window.print();
}

function increaseFont(): void {
  fontSize.value = Math.min(fontSize.value + 1, 20);
}

function decreaseFont(): void {
  fontSize.value = Math.max(fontSize.value - 1, 12);
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      fontSize.value = 15;
      activeTocId.value = '';
    }
  },
);
</script>

<template>
  <Teleport to="body">
    <Transition name="report-fade">
      <div v-if="visible && deliverable" class="report-viewer-overlay" @click.self="close">
        <div class="report-viewer">
          <header class="report-toolbar">
            <h2 class="report-title">{{ title }}</h2>
            <div class="toolbar-actions">
              <el-button :icon="Download" size="small" @click="exportMarkdown">导出 MD</el-button>
              <el-button :icon="CopyDocument" size="small" @click="copyFullText">复制全文</el-button>
              <el-button :icon="Printer" size="small" @click="handlePrint">打印</el-button>
              <el-button-group size="small">
                <el-button @click="decreaseFont">A-</el-button>
                <el-button @click="increaseFont">A+</el-button>
              </el-button-group>
              <el-button :icon="Close" circle size="small" @click="close" />
            </div>
          </header>

          <div class="report-body">
            <aside v-if="toc.length && !showChart" class="report-toc">
              <h3>目录</h3>
              <ul>
                <li
                  v-for="item in toc"
                  :key="item.id"
                  :class="[
                    `toc-level-${item.level}`,
                    { 'toc-item--active': activeTocId === item.id },
                  ]"
                >
                  <button type="button" @click="scrollToHeading(item.id)">{{ item.text }}</button>
                </li>
              </ul>
            </aside>

            <main class="report-content">
              <ChartRenderer
                v-if="showChart && deliverable.chartConfig"
                :config="deliverable.chartConfig"
                :title="deliverable.name"
                :height="360"
                :show-toolbar="true"
              />
              <MarkdownRenderer v-else :content="content" :font-size="fontSize" />
            </main>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style lang="scss" scoped>
.report-viewer-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: stretch;
  justify-content: center;
}

.report-viewer {
  width: 100%;
  max-width: 1100px;
  margin: 24px;
  background: $bg-white;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.report-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid $border-color;
  flex-shrink: 0;
}

.report-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.report-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.report-toc {
  width: 200px;
  flex-shrink: 0;
  padding: 16px;
  border-right: 1px solid $border-color;
  overflow-y: auto;

  h3 {
    margin: 0 0 12px;
    font-size: 13px;
    font-weight: 600;
    color: $text-secondary;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  li button {
    display: block;
    width: 100%;
    text-align: left;
    padding: 4px 0;
    border: none;
    background: none;
    font-size: 13px;
    color: $text-regular;
    cursor: pointer;

    &:hover {
      color: $primary-color;
    }
  }

  .toc-item--active button {
    color: $primary-color;
    font-weight: 500;
  }

  .toc-level-2 {
    padding-left: 12px;
  }

  .toc-level-3 {
    padding-left: 24px;
  }

  .toc-level-4,
  .toc-level-5,
  .toc-level-6 {
    padding-left: 36px;
  }
}

.report-content {
  flex: 1;
  overflow-y: auto;
  padding: 32px 48px;
  max-width: 800px;
  margin: 0 auto;
}

.report-fade-enter-active,
.report-fade-leave-active {
  transition: opacity 0.2s ease;
}

.report-fade-enter-from,
.report-fade-leave-to {
  opacity: 0;
}

@media print {
  .report-viewer-overlay {
    position: static;
    background: none;
  }

  .report-toolbar,
  .report-toc {
    display: none;
  }

  .report-viewer {
    margin: 0;
    max-width: none;
  }
}

@media (max-width: 768px) {
  .report-toc {
    display: none;
  }

  .report-content {
    padding: 20px 16px;
  }
}
</style>
