import type { GraphDefinition } from '@/api/workflow';

/** 标准六节点工作流拓扑（与后端 STANDARD_GRAPH_DEFINITION 对齐） */
export const STANDARD_GRAPH_DEFINITION: GraphDefinition = {
  nodes: [
    { id: 'scheduler', type: 'scheduler', label: '调度中心', position: { x: 400, y: 0 } },
    {
      id: 'knowledge_agent',
      type: 'knowledge',
      label: '知识库 Agent',
      position: { x: 100, y: 160 },
    },
    { id: 'search_agent', type: 'search', label: '搜索 Agent', position: { x: 300, y: 160 } },
    {
      id: 'execution_agent',
      type: 'execution',
      label: '执行 Agent',
      position: { x: 500, y: 160 },
    },
    {
      id: 'human_intervention',
      type: 'human',
      label: '人工介入',
      position: { x: 400, y: 320 },
    },
    { id: 'reviewer', type: 'reviewer', label: '审核 Agent', position: { x: 400, y: 480 } },
  ],
  edges: [
    { id: 'e1', source: 'scheduler', target: 'knowledge_agent' },
    { id: 'e2', source: 'scheduler', target: 'search_agent' },
    { id: 'e3', source: 'scheduler', target: 'execution_agent' },
    { id: 'e4', source: 'knowledge_agent', target: 'human_intervention' },
    { id: 'e5', source: 'search_agent', target: 'human_intervention' },
    { id: 'e6', source: 'execution_agent', target: 'human_intervention' },
    { id: 'e7', source: 'human_intervention', target: 'reviewer' },
  ],
};

/** 解析有效拓扑：优先 execution 快照，其次 workflow 定义，最后标准模板 */
export function resolveEffectiveGraph(
  fromExecution?: GraphDefinition | null,
  fromWorkflow?: GraphDefinition | null,
): GraphDefinition {
  if (fromExecution?.nodes?.length) return fromExecution;
  if (fromWorkflow?.nodes?.length) return fromWorkflow;
  return STANDARD_GRAPH_DEFINITION;
}
