<script setup lang="ts">
import { computed, ref } from 'vue';
import { ElMessage } from 'element-plus';
import {
  type Deliverable,
  type DeliverableCategory,
  extractDeliverables,
  formatFileSize,
  getCategoryLabel,
  getCategoryOrder,
  groupDeliverablesByCategory,
} from '@/utils/deliverables';
import type { AgentMessage } from '@/api/groupChat';

const props = defineProps<{
  messages: AgentMessage[];
  sessionDeliverables: Record<string, unknown>[];
}>();

const emit = defineEmits<{
  view: [deliverable: Deliverable];
  locate: [messageId: string];
}>();

const expandedCategories = ref<Set<DeliverableCategory>>(
  new Set(['final', 'chart', 'intermediate', 'reference']),
);

const deliverables = computed(() =>
  extractDeliverables(props.messages, props.sessionDeliverables),
);

const grouped = computed(() => groupDeliverablesByCategory(deliverables.value));

const totalCount = computed(() => deliverables.value.length);

function toggleCategory(cat: DeliverableCategory): void {
  if (expandedCategories.value.has(cat)) {
    expandedCategories.value.delete(cat);
  } else {
    expandedCategories.value.add(cat);
  }
}

function isExpanded(cat: DeliverableCategory): boolean {
  return expandedCategories.value.has(cat);
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function handleView(d: Deliverable): void {
  emit('view', d);
}

function handleLocate(d: Deliverable): void {
  emit('locate', d.messageId);
}

async function handleDownload(d: Deliverable): Promise<void> {
  const ext = d.fileType === 'md' ? 'md' : d.fileType === 'code' ? 'txt' : 'txt';
  const blob = new Blob([d.content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${d.name.replace(/[/\\?%*:|"<>]/g, '_')}.${ext}`;
  link.click();
  URL.revokeObjectURL(url);
  ElMessage.success('文件已下载');
}

async function handleCopyLink(d: Deliverable): Promise<void> {
  const text = `# ${d.name}\n\n${d.content.slice(0, 200)}...`;
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('内容摘要已复制');
  } catch {
    ElMessage.error('复制失败');
  }
}

const categoryIcons: Record<DeliverableCategory, string> = {
  final: '📑',
  chart: '📊',
  intermediate: '📄',
  reference: '📎',
};
</script>

<template>
  <section class="deliverables-panel">
    <div class="panel-header">
      <h3 class="panel-title">📎 交付物面板</h3>
      <span class="panel-count">共 {{ totalCount }} 个交付物</span>
    </div>

    <div v-if="totalCount === 0" class="empty-hint">暂无交付物，Agent 产出后将自动归集</div>

    <div v-for="cat in getCategoryOrder()" :key="cat" class="category-block">
      <template v-if="grouped[cat].length">
        <button type="button" class="category-header" @click="toggleCategory(cat)">
          <span>{{ categoryIcons[cat] }} {{ getCategoryLabel(cat) }}</span>
          <span class="category-count">{{ grouped[cat].length }}</span>
          <span class="category-toggle">{{ isExpanded(cat) ? '▼' : '▶' }}</span>
        </button>

        <div v-show="isExpanded(cat)" class="category-items">
          <div v-for="item in grouped[cat]" :key="item.id" class="deliverable-card">
            <div class="card-main" @click="handleLocate(item)">
              <span class="card-name">{{ item.name }}</span>
              <span class="card-meta">
                {{ item.createdBy }} · {{ formatTime(item.createdAt) }} ·
                {{ formatFileSize(item.size) }}
              </span>
            </div>
            <div class="card-actions">
              <button type="button" class="action-btn" @click.stop="handleView(item)">查看</button>
              <button type="button" class="action-btn" @click.stop="handleDownload(item)">
                下载
              </button>
              <button type="button" class="action-btn" @click.stop="handleCopyLink(item)">
                复制
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </section>
</template>

<style lang="scss" scoped>
.deliverables-panel {
  margin-top: 8px;
}

.panel-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: $text-primary;
}

.panel-count {
  font-size: 11px;
  color: $text-secondary;
}

.empty-hint {
  font-size: 12px;
  color: $text-secondary;
  padding: 12px 0;
}

.category-block {
  margin-bottom: 12px;
}

.category-header {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 0;
  border: none;
  background: none;
  font-size: 13px;
  font-weight: 500;
  color: $text-primary;
  cursor: pointer;
  text-align: left;

  &:hover {
    color: $primary-color;
  }
}

.category-count {
  font-size: 11px;
  color: $text-secondary;
  background: #f2f3f5;
  padding: 1px 6px;
  border-radius: 10px;
}

.category-toggle {
  margin-left: auto;
  font-size: 10px;
  color: $text-secondary;
}

.deliverable-card {
  padding: 10px;
  margin-bottom: 8px;
  border: 1px solid $border-color;
  border-radius: 8px;
  background: #fafbfc;
  transition: border-color 0.2s;

  &:hover {
    border-color: rgba($primary-color, 0.4);
  }
}

.card-main {
  cursor: pointer;
}

.card-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: $text-primary;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  font-size: 11px;
  color: $text-secondary;
}

.card-actions {
  display: flex;
  gap: 6px;
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
