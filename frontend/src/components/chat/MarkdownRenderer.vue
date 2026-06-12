<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import hljs from 'highlight.js/lib/core';
import javascript from 'highlight.js/lib/languages/javascript';
import python from 'highlight.js/lib/languages/python';
import sql from 'highlight.js/lib/languages/sql';
import json from 'highlight.js/lib/languages/json';
import bash from 'highlight.js/lib/languages/bash';
import markdown from 'highlight.js/lib/languages/markdown';
import 'highlight.js/styles/github.css';
import { renderMarkdownToHtml } from '@/utils/markdown';

hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('js', javascript);
hljs.registerLanguage('typescript', javascript);
hljs.registerLanguage('ts', javascript);
hljs.registerLanguage('python', python);
hljs.registerLanguage('py', python);
hljs.registerLanguage('sql', sql);
hljs.registerLanguage('json', json);
hljs.registerLanguage('bash', bash);
hljs.registerLanguage('shell', bash);
hljs.registerLanguage('markdown', markdown);
hljs.registerLanguage('md', markdown);

const props = withDefaults(
  defineProps<{
    content: string;
    streaming?: boolean;
    fontSize?: number;
    compact?: boolean;
  }>(),
  {
    streaming: false,
    fontSize: 14,
    compact: false,
  },
);

const markdownRef = ref<HTMLElement | null>(null);

const renderedHtml = computed(() => renderMarkdownToHtml(props.content));

/** 对代码块应用 highlight.js 语法高亮 */
function applyCodeHighlight(): void {
  const root = markdownRef.value;
  if (!root) return;
  root.querySelectorAll('pre code').forEach((block) => {
    hljs.highlightElement(block as HTMLElement);
  });
}

/** 复制代码块内容 */
async function handleCopyClick(event: MouseEvent): Promise<void> {
  const target = event.target as HTMLElement;
  if (!target.classList.contains('copy-btn')) return;
  const encoded = target.getAttribute('data-code') || '';
  try {
    await navigator.clipboard.writeText(decodeURIComponent(encoded));
    ElMessage.success('代码已复制');
  } catch {
    ElMessage.error('复制失败');
  }
}

watch(
  () => props.content,
  async () => {
    await nextTick();
    applyCodeHighlight();
  },
);

onMounted(async () => {
  await nextTick();
  applyCodeHighlight();
});
</script>

<template>
  <div
    class="markdown-renderer"
    :class="{ 'markdown-renderer--compact': compact }"
    :style="{ fontSize: `${fontSize}px` }"
  >
    <div
      ref="markdownRef"
      class="markdown-body"
      @click="handleCopyClick"
      v-html="renderedHtml"
    />
    <span v-if="streaming" class="cursor-blink">|</span>
  </div>
</template>

<style lang="scss" scoped>
.markdown-renderer {
  line-height: 1.7;
  color: $text-primary;
  word-break: break-word;
}

.markdown-body {
  :deep(h1) {
    margin: 20px 0 12px;
    font-size: 1.6em;
    font-weight: 700;
    color: $text-primary;
    border-bottom: 1px solid $border-color;
    padding-bottom: 8px;
  }

  :deep(h2) {
    margin: 18px 0 10px;
    font-size: 1.35em;
    font-weight: 600;
  }

  :deep(h3) {
    margin: 14px 0 8px;
    font-size: 1.15em;
    font-weight: 600;
  }

  :deep(h4),
  :deep(h5),
  :deep(h6) {
    margin: 12px 0 6px;
    font-weight: 600;
  }

  :deep(p) {
    margin: 8px 0;
  }

  :deep(ul),
  :deep(ol) {
    margin: 8px 0;
    padding-left: 1.5em;
  }

  :deep(li) {
    margin: 4px 0;
  }

  :deep(blockquote) {
    margin: 12px 0;
    padding: 8px 16px;
    border-left: 3px solid $primary-color;
    background: #f7f8fa;
    color: $text-regular;
  }

  :deep(hr) {
    margin: 16px 0;
    border: none;
    border-top: 1px solid $border-color;
  }

  :deep(.code-block-wrapper) {
    position: relative;
    margin: 12px 0;
  }

  :deep(.copy-btn) {
    position: absolute;
    top: 8px;
    right: 8px;
    z-index: 1;
    padding: 2px 8px;
    font-size: 12px;
    color: $text-secondary;
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid $border-color;
    border-radius: 4px;
    cursor: pointer;

    &:hover {
      color: $primary-color;
      border-color: $primary-color;
    }
  }

  :deep(.code-block),
  :deep(pre) {
    margin: 0;
    padding: 12px 16px;
    padding-top: 32px;
    background: #f5f7fa;
    border-radius: 6px;
    overflow-x: auto;
    font-family: 'Menlo', 'Monaco', 'Consolas', monospace;
    font-size: 0.9em;
    line-height: 1.5;
  }

  :deep(code) {
    font-family: 'Menlo', 'Monaco', 'Consolas', monospace;
  }

  :deep(p code),
  :deep(li code) {
    padding: 2px 6px;
    background: #f0f2f5;
    border-radius: 4px;
    font-size: 0.9em;
    color: #c7254e;
  }

  :deep(table) {
    width: 100%;
    margin: 12px 0;
    border-collapse: collapse;
    font-size: 0.95em;

    th,
    td {
      border: 1px solid $border-color;
      padding: 8px 12px;
      text-align: left;
    }

    th {
      background: #fafafa;
      font-weight: 600;
    }

    tr:nth-child(even) td {
      background: #fafbfc;
    }
  }

  :deep(a) {
    color: $primary-color;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }

  :deep(strong) {
    font-weight: 600;
    color: $text-primary;
  }
}

.markdown-renderer--compact {
  .markdown-body :deep(h1) {
    font-size: 1.3em;
    margin-top: 12px;
  }
}

.cursor-blink {
  display: inline-block;
  color: $primary-color;
  animation: blink 1s step-end infinite;
  margin-left: 2px;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
