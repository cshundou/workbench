import type { AgentMessage, MessageAttachment } from '@/api/groupChat';

/** 交付物分类 */
export type DeliverableCategory = 'final' | 'chart' | 'intermediate' | 'reference';

/** 标准化交付物模型 */
export interface Deliverable {
  id: string;
  messageId: string;
  name: string;
  category: DeliverableCategory;
  type: string;
  fileType: string;
  content: string;
  createdBy: string;
  createdAt: string;
  size: number;
  chartConfig?: Record<string, unknown>;
}

const CATEGORY_ORDER: DeliverableCategory[] = ['final', 'chart', 'intermediate', 'reference'];

const CATEGORY_LABELS: Record<DeliverableCategory, string> = {
  final: '最终交付',
  chart: '图表数据',
  intermediate: '中间产物',
  reference: '参考资料',
};

export function getCategoryLabel(category: DeliverableCategory): string {
  return CATEGORY_LABELS[category];
}

export function getCategoryOrder(): DeliverableCategory[] {
  return CATEGORY_ORDER;
}

function inferCategory(msg: AgentMessage, att?: MessageAttachment): DeliverableCategory {
  if (msg.type === 'task_complete') return 'final';
  if (att?.type === 'chart') return 'chart';
  if (att?.type === 'text' && msg.type === 'result_delivery') return 'intermediate';
  if (att?.type === 'code') return 'intermediate';
  if (msg.type === 'result_delivery') return 'intermediate';
  return 'reference';
}

function inferFileType(att?: MessageAttachment, content?: string): string {
  if (att?.type === 'chart') return 'chart';
  if (att?.type === 'code') return 'code';
  if (att?.type === 'image') return 'png';
  if (content && content.startsWith('#')) return 'md';
  return 'txt';
}

function buildDeliverableFromAttachment(
  msg: AgentMessage,
  att: MessageAttachment,
  index: number,
): Deliverable {
  const content =
    typeof att.content === 'string' ? att.content : JSON.stringify(att.content, null, 2);
  const category = inferCategory(msg, att);
  return {
    id: `${msg.id}-att-${index}`,
    messageId: msg.id,
    name: att.name || '未命名交付物',
    category,
    type: att.type,
    fileType: inferFileType(att, content),
    content,
    createdBy: msg.sender.name || msg.sender.role,
    createdAt: msg.timestamp,
    size: new Blob([content]).size,
    chartConfig:
      att.type === 'chart' && att.content && typeof att.content === 'object'
        ? (att.content as Record<string, unknown>)
        : undefined,
  };
}

/** 从消息流与会话 deliverables 汇总交付物列表 */
export function extractDeliverables(
  messages: AgentMessage[],
  sessionDeliverables: Record<string, unknown>[] = [],
): Deliverable[] {
  const map = new Map<string, Deliverable>();

  for (const msg of messages) {
    if (msg.attachments?.length) {
      msg.attachments.forEach((att, idx) => {
        const d = buildDeliverableFromAttachment(msg, att, idx);
        map.set(d.id, d);
      });
    } else if (['result_delivery', 'task_complete'].includes(msg.type) && msg.content) {
      const content =
        msg.metadata?.final_answer && typeof msg.metadata.final_answer === 'string'
          ? msg.metadata.final_answer
          : msg.content;
      const d: Deliverable = {
        id: `${msg.id}-content`,
        messageId: msg.id,
        name: msg.type === 'task_complete' ? '最终报告' : `${msg.sender.name}交付`,
        category: msg.type === 'task_complete' ? 'final' : 'intermediate',
        type: 'text',
        fileType: 'md',
        content,
        createdBy: msg.sender.name || msg.sender.role,
        createdAt: msg.timestamp,
        size: new Blob([content]).size,
      };
      map.set(d.id, d);
    }
  }

  for (const [idx, item] of sessionDeliverables.entries()) {
    const role = String(item.role || '成员');
    const content = String(item.content || '');
    const atts = (item.attachments as MessageAttachment[]) || [];
    if (atts.length) {
      atts.forEach((att, attIdx) => {
        const syntheticMsg: AgentMessage = {
          id: `session-${idx}`,
          timestamp: new Date().toISOString(),
          sender: { id: role, name: role, role, avatar: '📄' },
          type: 'result_delivery',
          content,
        };
        const d = buildDeliverableFromAttachment(syntheticMsg, att, attIdx);
        d.id = `session-${idx}-att-${attIdx}`;
        if (!map.has(d.id)) map.set(d.id, d);
      });
    } else if (content) {
      const id = `session-${idx}`;
      if (!map.has(id)) {
        map.set(id, {
          id,
          messageId: id,
          name: `${role}交付`,
          category: 'intermediate',
          type: 'text',
          fileType: 'md',
          content,
          createdBy: role,
          createdAt: new Date().toISOString(),
          size: new Blob([content]).size,
        });
      }
    }
  }

  return Array.from(map.values()).sort(
    (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
  );
}

export function groupDeliverablesByCategory(
  deliverables: Deliverable[],
): Record<DeliverableCategory, Deliverable[]> {
  const grouped: Record<DeliverableCategory, Deliverable[]> = {
    final: [],
    chart: [],
    intermediate: [],
    reference: [],
  };
  for (const d of deliverables) {
    grouped[d.category].push(d);
  }
  return grouped;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
