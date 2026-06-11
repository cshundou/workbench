<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import hljs from 'highlight.js/lib/core';
import javascript from 'highlight.js/lib/languages/javascript';
import python from 'highlight.js/lib/languages/python';
import sql from 'highlight.js/lib/languages/sql';
import json from 'highlight.js/lib/languages/json';
import bash from 'highlight.js/lib/languages/bash';
import 'highlight.js/styles/github.css';

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

const props = withDefaults(
  defineProps<{
    content: string;
    streaming?: boolean;
  }>(),
  {
    streaming: false,
  },
);

const markdownRef = ref<HTMLElement | null>(null);

/** 过滤 XSS 危险标签与事件属性 */
function sanitizeHtml(html: string): string {
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
    .replace(/\s+on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
    .replace(/javascript:/gi, '');
}

/** 简易 Markdown 渲染：标题、粗体、行内代码、代码块、表格、链接 */
function renderMarkdown(text: string): string {
  if (!text) {
    return '';
  }

  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // 代码块（含复制按钮容器）
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_match, lang, code) => {
    const trimmed = code.trim();
    const langClass = lang ? ` class="language-${lang}"` : '';
    const encoded = encodeURIComponent(trimmed);
    return (
      `<div class="code-block-wrapper">` +
      `<button type="button" class="copy-btn" data-code="${encoded}" title="复制代码">复制</button>` +
      `<pre class="code-block"><code${langClass}>${trimmed}</code></pre>` +
      `</div>`
    );
  });

  // 行内代码
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

  // 标题
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // 粗体 / 斜体
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // 链接
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  );

  // 表格（简单管道表格）
  html = html.replace(/((?:\|.+\|\n)+)/g, (tableBlock) => {
    const rows = tableBlock.trim().split('\n').filter((row) => !row.match(/^\|[\s-:|]+\|$/));
    if (rows.length === 0) {
      return tableBlock;
    }
    const tableRows = rows
      .map((row, index) => {
        const cells = row
          .split('|')
          .filter((cell) => cell.trim() !== '')
          .map((cell) => `<${index === 0 ? 'th' : 'td'}>${cell.trim()}</${index === 0 ? 'th' : 'td'}>`)
          .join('');
        return `<tr>${cells}</tr>`;
      })
      .join('');
    return `<table class="md-table"><tbody>${tableRows}</tbody></table>`;
  });

  // 引用标注 [1] 高亮
  html = html.replace(/\[(\d+)\]/g, '<sup class="citation-ref">[$1]</sup>');

  // 换行
  html = html.replace(/\n/g, '<br />');

  return sanitizeHtml(html);
}

const renderedHtml = computed(() => renderMarkdown(props.content));

/** 对代码块应用 highlight.js 语法高亮 */
function applyCodeHighlight(): void {
  const root = markdownRef.value;
  if (!root) {
    return;
  }
  root.querySelectorAll('pre code').forEach((block) => {
    hljs.highlightElement(block as HTMLElement);
  });
}

/** 复制代码块内容 */
async function handleCopyClick(event: MouseEvent): Promise<void> {
  const target = event.target as HTMLElement;
  if (!target.classList.contains('copy-btn')) {
    return;
  }
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
  <div class="streaming-text">
    <div
      ref="markdownRef"
      class="markdown-body"
      v-html="renderedHtml"
      @click="handleCopyClick"
    />
    <span v-if="streaming" class="cursor-blink">|</span>
  </div>
</template>

<style lang="scss" scoped>
.streaming-text {
  line-height: 1.7;
  color: $text-primary;
  word-break: break-word;
}

.markdown-body {
  :deep(h1),
  :deep(h2),
  :deep(h3) {
    margin: 12px 0 8px;
    font-weight: 600;
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
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid $border-color;
    border-radius: 4px;
    cursor: pointer;

    &:hover {
      color: $primary-color;
      border-color: $primary-color;
    }
  }

  :deep(.code-block) {
    margin: 0;
    padding: 12px 16px;
    padding-top: 32px;
    background: #f5f7fa;
    border-radius: 6px;
    overflow-x: auto;
    font-family: 'Menlo', 'Monaco', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.5;
  }

  :deep(.inline-code) {
    padding: 2px 6px;
    background: #f0f2f5;
    border-radius: 4px;
    font-family: 'Menlo', 'Monaco', 'Consolas', monospace;
    font-size: 0.9em;
    color: #c7254e;
  }

  :deep(.md-table) {
    width: 100%;
    margin: 12px 0;
    border-collapse: collapse;
    font-size: 14px;

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
  }

  :deep(.citation-ref) {
    color: $primary-color;
    cursor: pointer;
    font-weight: 600;
  }

  :deep(a) {
    color: $primary-color;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
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
