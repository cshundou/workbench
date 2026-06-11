import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useAgentStore } from '@/stores/agent';

vi.mock('@/api/agent', () => ({
  getAgents: vi.fn().mockResolvedValue({ items: [{ id: 1, name: 'Agent1' }], total: 1 }),
  getAgentById: vi.fn().mockResolvedValue({ id: 1, name: 'Agent1', tools: [] }),
  getAgentHistory: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}));

describe('useAgentStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('fetchAgents 加载智能体列表', async () => {
    const store = useAgentStore();
    await store.fetchAgents();
    expect(store.agents.length).toBe(1);
  });

  it('fetchAgent 设置当前智能体', async () => {
    const store = useAgentStore();
    await store.fetchAgent(1);
    expect(store.currentAgent?.name).toBe('Agent1');
  });
});
