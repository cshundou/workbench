import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useRagStore } from '@/stores/rag';

vi.mock('@/api/rag', () => ({
  getKnowledgeBases: vi.fn().mockResolvedValue({ items: [{ id: 1, name: 'KB1' }], total: 1 }),
  getKnowledgeBaseById: vi.fn().mockResolvedValue({ id: 1, name: 'KB1', document_count: 0 }),
  getDocuments: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}));

describe('useRagStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('fetchKnowledgeBases 加载列表', async () => {
    const store = useRagStore();
    await store.fetchKnowledgeBases();
    expect(store.knowledgeBases.length).toBe(1);
    expect(store.knowledgeBases[0].name).toBe('KB1');
  });

  it('fetchKnowledgeBase 设置当前知识库', async () => {
    const store = useRagStore();
    await store.fetchKnowledgeBase(1);
    expect(store.currentKb?.id).toBe(1);
  });

  it('fetchDocuments 解析分页 items 为数组', async () => {
    const store = useRagStore();
    const ok = await store.fetchDocuments(1);
    expect(ok).toBe(true);
    expect(Array.isArray(store.documents)).toBe(true);
    expect(store.documents).toEqual([]);
    expect(store.documentsTotal).toBe(0);
    expect(store.documentsLoading).toBe(false);
  });
});
