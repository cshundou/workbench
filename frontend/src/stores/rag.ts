import { defineStore } from 'pinia';
import { ref } from 'vue';
import {
  getKnowledgeBases,
  getKnowledgeBaseById,
  getDocuments,
  searchKnowledgeBase,
  type KnowledgeBaseInfo,
  type DocumentInfo,
  type SearchResultItem,
  type SearchKnowledgeParams,
} from '@/api/rag';
import type { PageParams } from '@/types/api';

export const useRagStore = defineStore('rag', () => {
  const knowledgeBases = ref<KnowledgeBaseInfo[]>([]);
  const currentKb = ref<KnowledgeBaseInfo | null>(null);
  const documents = ref<DocumentInfo[]>([]);
  const searchResults = ref<SearchResultItem[]>([]);
  const isLoading = ref(false);
  const total = ref(0);

  /** 加载知识库列表 */
  async function fetchKnowledgeBases(params?: PageParams): Promise<void> {
    isLoading.value = true;
    try {
      const res = await getKnowledgeBases(params);
      knowledgeBases.value = res.items;
      total.value = res.total;
    } catch (error) {
      console.error('[Fetch Knowledge Bases Error]', error);
    } finally {
      isLoading.value = false;
    }
  }

  /** 加载知识库详情 */
  async function fetchKnowledgeBase(id: number): Promise<void> {
    isLoading.value = true;
    try {
      currentKb.value = await getKnowledgeBaseById(id);
    } catch (error) {
      console.error('[Fetch Knowledge Base Error]', error);
      currentKb.value = null;
    } finally {
      isLoading.value = false;
    }
  }

  /** 加载文档列表 */
  async function fetchDocuments(kbId: number): Promise<void> {
    isLoading.value = true;
    try {
      documents.value = await getDocuments(kbId);
    } catch (error) {
      console.error('[Fetch Documents Error]', error);
    } finally {
      isLoading.value = false;
    }
  }

  /** 检索知识库 */
  async function search(kbId: number, params: SearchKnowledgeParams): Promise<void> {
    isLoading.value = true;
    try {
      searchResults.value = await searchKnowledgeBase(kbId, params);
    } catch (error) {
      console.error('[Search Knowledge Base Error]', error);
    } finally {
      isLoading.value = false;
    }
  }

  /** 清空当前知识库上下文 */
  function clearCurrentKb(): void {
    currentKb.value = null;
    documents.value = [];
    searchResults.value = [];
  }

  return {
    knowledgeBases,
    currentKb,
    documents,
    searchResults,
    isLoading,
    total,
    fetchKnowledgeBases,
    fetchKnowledgeBase,
    fetchDocuments,
    search,
    clearCurrentKb,
  };
});
