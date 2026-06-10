<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    content: string;
    streaming?: boolean;
  }>(),
  {
    streaming: false,
  },
);

/** 简易 Markdown 渲染：标题、粗体、行内代码、代码块、表格、链接 */
function renderMarkdown(text: string): string {
  if (!text) {
    return '';
  }

  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // 代码块
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_match, lang, code) => {
    const langClass = lang ? ` class="language-${lang}"` : '';
    return `<pre class="code-block"><code${langClass}>${code.trim()}</code></pre>`;
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

  return html;
}

const renderedHtml = computed(() => renderMarkdown(props.content));
</script>

<template>
  <div class="streaming-text">
    <div class="markdown-body" v-html="renderedHtml" />
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

  :deep(.code-block) {
    margin: 12px 0;
    padding: 12px 16px;
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
