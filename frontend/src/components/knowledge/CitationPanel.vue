<script setup lang="ts">
import { Document } from '@element-plus/icons-vue';
import type { CitationSource } from '@/api/rag';

defineProps<{
  sources: CitationSource[];
  activeId?: number | null;
}>();

const emit = defineEmits<{
  select: [source: CitationSource];
}>();

/** 点击引用来源 */
function handleSelect(source: CitationSource): void {
  emit('select', source);
}
</script>

<template>
  <div class="citation-panel">
    <div class="panel-header">
      <el-icon><Document /></el-icon>
      <span>引用来源 ({{ sources.length }})</span>
    </div>

    <el-empty v-if="sources.length === 0" description="暂无引用" :image-size="60" />

    <div v-else class="citation-list">
      <div
        v-for="source in sources"
        :key="source.id"
        class="citation-item"
        :class="{ active: activeId === source.id }"
        @click="handleSelect(source)"
      >
        <div class="citation-title">
          <sup class="ref-num">[{{ source.id }}]</sup>
          {{ source.document_name }}
        </div>
        <div class="citation-meta">
          <span v-if="source.page_number !== undefined">第 {{ source.page_number }} 页</span>
          <span v-if="source.chunk_index !== undefined">片段 #{{ source.chunk_index }}</span>
        </div>
        <p v-if="source.content" class="citation-snippet">
          {{ source.content }}
        </p>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.citation-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-left: 1px solid $border-color;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  font-size: 14px;
  font-weight: 600;
  color: $text-primary;
  border-bottom: 1px solid $border-color;
}

.citation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.citation-item {
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  border: 1px solid $border-color;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover,
  &.active {
    border-color: $primary-color;
    background: rgba(64, 158, 255, 0.06);
  }
}

.citation-title {
  font-size: 14px;
  font-weight: 500;
  color: $text-primary;
  margin-bottom: 4px;
}

.ref-num {
  color: $primary-color;
  margin-right: 4px;
}

.citation-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: $text-secondary;
  margin-bottom: 6px;
}

.citation-snippet {
  margin: 0;
  font-size: 13px;
  color: $text-secondary;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
