import request from './request';

/** Trace Span 节点 */
export interface TraceSpanItem {
  span_id: string;
  parent_span_id?: string | null;
  name: string;
  kind: string;
  status: string;
  duration_ms?: number | null;
  input?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
  error?: string | null;
}

/** Trace 调用树 */
export interface TraceTree {
  trace_id: string;
  resource_type?: string;
  resource_id?: number | null;
  status?: string;
  started_at?: string | null;
  completed_at?: string | null;
  spans: TraceSpanItem[];
}

/** 获取 Trace 调用树 */
export function getTraceTree(traceId: string): Promise<TraceTree> {
  return request.get(`/traces/${encodeURIComponent(traceId)}`) as Promise<TraceTree>;
}
