<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue';
import ChartRenderer from '@/components/group-chat/ChartRenderer.vue';
import type { MessageAttachment } from '@/api/groupChat';

defineProps<{
  attachments: MessageAttachment[];
  sessionId?: number;
}>();

const emit = defineEmits<{
  viewChart: [config: Record<string, unknown>, name: string];
  viewDetail: [content: string, name: string];
  downloadPptx: [filename: string, slideCount?: number];
  previewPptx: [filename: string, slideCount?: number];
}>();

const expanded = ref<Record<number, boolean>>({});

function toggle(idx: number): void {
  expanded.value[idx] = !expanded.value[idx];
}

function isChartContent(content: unknown): content is Record<string, unknown> {
  return Boolean(content && typeof content === 'object' && !Array.isArray(content));
}

async function copyContent(content: unknown): Promise<void> {
  const text = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('已复制');
  } catch {
    ElMessage.error('复制失败');
  }
}

function openDetail(att: MessageAttachment): void {
  const content =
    typeof att.content === 'string' ? att.content : JSON.stringify(att.content, null, 2);
  emit('viewDetail', content, att.name);
}

function openChart(att: MessageAttachment): void {
  if (isChartContent(att.content)) {
    emit('viewChart', att.content, att.name);
  }
}

function isPptxAttachment(att: MessageAttachment): boolean {
  const attAny = att as MessageAttachment & { file_type?: string };
  return (
    attAny.file_type === 'pptx' ||
    (att.type === 'file' && String(att.name || '').toLowerCase().endsWith('.pptx'))
  );
}

function getSlideCount(att: MessageAttachment): number | undefined {
  const attAny = att as MessageAttachment & { slide_count?: number };
  return attAny.slide_count;
}

function handlePptxDownload(att: MessageAttachment): void {
  emit('downloadPptx', att.name, getSlideCount(att));
}

function handlePptxPreview(att: MessageAttachment): void {
  emit('previewPptx', att.name, getSlideCount(att));
}
</script>

<template>
  <div class="attachments">
    <div
      v-for="(att, idx) in attachments"
      :key="idx"
      class="attachment-item"
      :class="{ 'attachment-item--pptx': isPptxAttachment(att) }"
    >
      <div v-if="isPptxAttachment(att)" class="pptx-card">
        <div class="pptx-thumb">PPT</div>
        <div class="pptx-info">
          <span class="attachment-name">{{ att.name }}</span>
          <span class="pptx-meta">
            {{ getSlideCount(att) ? `${getSlideCount(att)} 页 · ` : '' }}演示文稿
          </span>
        </div>
        <div class="pptx-actions">
          <button type="button" class="action-btn" @click.stop="handlePptxPreview(att)">
            预览
          </button>
          <button type="button" class="action-btn" @click.stop="handlePptxDownload(att)">
            下载
          </button>
        </div>
      </div>

      <template v-else>
        <div class="attachment-header" @click="toggle(idx)">
          <span class="attachment-type">{{ att.type }}</span>
          <span class="attachment-name">{{ att.name }}</span>
          <span class="attachment-toggle">{{ expanded[idx] ? '收起' : '展开' }}</span>
        </div>
        <div v-if="expanded[idx] !== false" class="attachment-body">
          <ChartRenderer
            v-if="att.type === 'chart' && isChartContent(att.content)"
            :config="att.content"
            :title="att.name"
            @enlarge="openChart(att)"
          />
          <MarkdownRenderer
            v-else-if="att.type === 'text' && typeof att.content === 'string'"
            :content="att.content"
            compact
          />
          <pre v-else-if="att.type === 'code'" class="code-block"><code>{{ att.content }}</code></pre>
          <div v-else class="text-preview">{{ att.content }}</div>
          <div class="attachment-actions">
            <button type="button" class="action-btn" @click.stop="openDetail(att)">
              查看详情
            </button>
            <button type="button" class="action-btn" @click.stop="copyContent(att.content)">
              复制
            </button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.attachments {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attachment-item {
  border: 1px solid $border-color;
  border-radius: 8px;
  overflow: hidden;

  &--pptx {
    border-color: rgba(#5856d6, 0.35);
    background: linear-gradient(135deg, #fafbff 0%, #f3f4ff 100%);
  }
}

.pptx-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
}

.pptx-thumb {
  width: 48px;
  height: 36px;
  border-radius: 6px;
  background: linear-gradient(135deg, #5856d6, #7b79ff);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pptx-info {
  flex: 1;
  min-width: 0;
}

.pptx-meta {
  display: block;
  font-size: 11px;
  color: $text-secondary;
  margin-top: 2px;
}

.pptx-actions {
  display: flex;
  gap: 6px;
}

.attachment-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: #fafafa;
  font-size: 12px;
  cursor: pointer;
}

.attachment-type {
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba($primary-color, 0.1);
  color: $primary-color;
  text-transform: uppercase;
  font-size: 10px;
}

.attachment-name {
  flex: 1;
  color: $text-primary;
  font-weight: 500;
}

.attachment-toggle {
  color: $text-secondary;
}

.attachment-body {
  padding: 10px;
  font-size: 12px;
  color: $text-secondary;
  border-top: 1px solid $border-color;
}

.code-block {
  margin: 0;
  padding: 8px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
}

.text-preview {
  white-space: pre-wrap;
  word-break: break-word;
}

.attachment-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.action-btn {
  padding: 2px 8px;
  font-size: 11px;
  color: $primary-color;
  background: transparent;
  border: 1px solid rgba($primary-color, 0.35);
  border-radius: 4px;
  cursor: pointer;

  &:hover {
    background: rgba($primary-color, 0.06);
  }
}
</style>
