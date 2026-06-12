import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';

/** markdown-it 实例：启用表格、链接识别 */
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
});

/** DOMPurify 白名单配置，防止 XSS */
const PURIFY_CONFIG = {
  ALLOWED_TAGS: [
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'p',
    'br',
    'hr',
    'ul',
    'ol',
    'li',
    'blockquote',
    'pre',
    'code',
    'table',
    'thead',
    'tbody',
    'tr',
    'th',
    'td',
    'strong',
    'em',
    'del',
    's',
    'a',
    'sup',
    'sub',
    'span',
    'div',
  ],
  ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'data-code', 'id', 'title'],
  ALLOW_DATA_ATTR: true,
};

/** 自定义代码块渲染：包裹复制按钮容器 */
const defaultFence =
  md.renderer.rules.fence ||
  function fence(tokens, idx, options, _env, slf) {
    return slf.renderToken(tokens, idx, options);
  };

md.renderer.rules.fence = (tokens, idx, options, env, slf) => {
  const token = tokens[idx];
  const lang = token.info.trim().split(/\s+/g)[0] || '';
  const code = token.content;
  const encoded = encodeURIComponent(code);
  const langClass = lang ? ` class="language-${lang}"` : '';
  const raw = defaultFence(tokens, idx, options, env, slf);
  if (raw.startsWith('<pre')) {
    return (
      `<div class="code-block-wrapper">` +
      `<button type="button" class="copy-btn" data-code="${encoded}" title="复制代码">复制</button>` +
      `<pre class="code-block"><code${langClass}>${md.utils.escapeHtml(code)}</code></pre>` +
      `</div>`
    );
  }
  return raw;
};

/** 为标题注入 id，供目录导航锚点使用 */
md.renderer.rules.heading_open = (tokens, idx) => {
  const token = tokens[idx];
  const level = token.tag;
  const nextToken = tokens[idx + 1];
  if (nextToken?.type === 'inline' && nextToken.content) {
    const id = nextToken.content
      .toLowerCase()
      .replace(/[^\w\u4e00-\u9fa5]+/g, '-')
      .replace(/^-|-$/g, '');
    return `<${level} id="${id}">`;
  }
  return `<${level}>`;
};

/**
 * 将 Markdown 文本渲染为安全 HTML
 */
export function renderMarkdownToHtml(content: string): string {
  if (!content) {
    return '';
  }
  const raw = md.render(content);
  return String(DOMPurify.sanitize(raw, PURIFY_CONFIG));
}

/**
 * 从 Markdown 提取标题目录
 */
export interface TocItem {
  id: string;
  text: string;
  level: number;
}

export function extractTocFromMarkdown(content: string): TocItem[] {
  const items: TocItem[] = [];
  const lines = content.split('\n');
  for (const line of lines) {
    const match = /^(#{1,6})\s+(.+)$/.exec(line.trim());
    if (match) {
      const level = match[1].length;
      const text = match[2].replace(/\*\*|__/g, '').trim();
      const id = text
        .toLowerCase()
        .replace(/[^\w\u4e00-\u9fa5]+/g, '-')
        .replace(/^-|-$/g, '');
      items.push({ id, text, level });
    }
  }
  return items;
}
