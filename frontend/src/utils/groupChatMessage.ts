import type { AgentMessage } from '@/api/groupChat';

/** 消息视觉类型 */
export type MessageVisualType =
  | 'system'
  | 'user'
  | 'deliverable'
  | 'review_pass'
  | 'review_reject'
  | 'normal';

/** 执行阶段分区 */
export type ExecutionPhase = 'startup' | 'execution' | 'review' | 'delivery' | 'other';

export interface PhaseDivider {
  phase: ExecutionPhase;
  label: string;
}

const PHASE_LABELS: Record<ExecutionPhase, string> = {
  startup: '任务启动',
  execution: '执行过程',
  review: '审核阶段',
  delivery: '最终交付',
  other: '其他',
};

const SYSTEM_TYPES = new Set(['system', 'team_formation', 'error']);
const DELIVERABLE_TYPES = new Set(['result_delivery', 'task_complete']);
const REVIEW_TYPES = new Set(['review_result', 'review_request']);

/** 根据消息 type 推断执行阶段 */
export function getMessagePhase(msg: AgentMessage): ExecutionPhase {
  const t = msg.type;
  if (msg.metadata?.ppt_pipeline) return 'review';
  if (t === 'task_start' || t === 'phase_start') return 'startup';
  if (t === 'phase_summary') return 'execution';
  if (REVIEW_TYPES.has(t)) return 'review';
  if (t === 'task_complete') return 'delivery';
  if (
    [
      'task_assignment',
      'phase_start',
      'phase_summary',
      'progress_update',
      'answer',
      'result_delivery',
      'question',
    ].includes(t)
  ) {
    return 'execution';
  }
  return 'other';
}

/** 判断消息视觉样式类型 */
export function getMessageVisualType(msg: AgentMessage): MessageVisualType {
  if (msg.sender.role === 'user') return 'user';
  if (msg.sender.role === 'system' || SYSTEM_TYPES.has(msg.type)) return 'system';
  if (DELIVERABLE_TYPES.has(msg.type)) return 'deliverable';
  if (msg.type === 'review_result') {
    const passed =
      msg.content.includes('✅') ||
      msg.content.includes('审核通过') ||
      (msg.metadata?.review as { passed?: boolean } | undefined)?.passed === true;
    return passed ? 'review_pass' : 'review_reject';
  }
  return 'normal';
}

/** 是否为交付物类消息 */
export function isDeliverableMessage(msg: AgentMessage): boolean {
  return DELIVERABLE_TYPES.has(msg.type) || Boolean(msg.attachments?.length);
}

/** 获取交付物主内容（优先附件文本/Markdown） */
export function getDeliverableContent(msg: AgentMessage): string {
  const textAtt = msg.attachments?.find(
    (a) => a.type === 'text' && typeof a.content === 'string',
  );
  if (textAtt && typeof textAtt.content === 'string') {
    return textAtt.content;
  }
  return msg.content;
}

/** 获取交付物显示名称 */
export function getDeliverableTitle(msg: AgentMessage): string {
  const named = msg.attachments?.find((a) => a.name);
  if (named?.name) return named.name;
  if (msg.type === 'task_complete') return '最终报告';
  return '交付物';
}

/** 构建带阶段分割线的消息列表 */
export interface StreamItem {
  kind: 'phase' | 'message';
  phase?: PhaseDivider;
  message?: AgentMessage;
}

export function buildStreamItems(messages: AgentMessage[]): StreamItem[] {
  const items: StreamItem[] = [];
  let lastPhase: ExecutionPhase | null = null;

  for (const msg of messages) {
    // PPT 流水线阶段分割线（系统消息 metadata.ppt_pipeline）
    if (msg.metadata?.ppt_pipeline && msg.type === 'phase_start') {
      items.push({
        kind: 'phase',
        phase: { phase: 'review', label: msg.content.replace(/^[✅❌📑]\s*/, '') },
      });
      continue;
    }

    const phase = getMessagePhase(msg);
    if (phase !== lastPhase && phase !== 'other') {
      items.push({
        kind: 'phase',
        phase: { phase, label: PHASE_LABELS[phase] },
      });
      lastPhase = phase;
    }
    items.push({ kind: 'message', message: msg });
  }
  return items;
}

/** 长内容阈值（字符数） */
export const LONG_CONTENT_THRESHOLD = 300;

export function isLongContent(content: string): boolean {
  return content.length > LONG_CONTENT_THRESHOLD;
}
