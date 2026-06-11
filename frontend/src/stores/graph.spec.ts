import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { NODE_STATUS_COLORS, useGraphStore } from '@/stores/graph';

describe('useGraphStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('初始节点状态为空', () => {
    const store = useGraphStore();
    expect(Object.keys(store.nodeStatuses).length).toBe(0);
  });

  it('NODE_STATUS_COLORS 包含关键状态', () => {
    expect(NODE_STATUS_COLORS.running).toBeDefined();
    expect(NODE_STATUS_COLORS.completed).toBeDefined();
  });

  it('resetExecution 清空状态', () => {
    const store = useGraphStore();
    store.nodeStatuses = { scheduler: 'completed' };
    store.resetExecution();
    expect(Object.keys(store.nodeStatuses).length).toBe(0);
  });
});
