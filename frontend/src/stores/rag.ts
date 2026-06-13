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
  /** 列表页等通用加载态 */
  const isLoading = ref(false);
  /** 知识库详情加载态 */
  const kbLoading = ref(false);
  /** 文档列表加载态 */
  const documentsLoading = ref(false);
  /** 文档列表加载错误信息 */
  const documentsError = ref<string | null>(null);
  const total = ref(0);
  const documentsTotal = ref(0);

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
    kbLoading.value = true;
    try {
      currentKb.value = await getKnowledgeBaseById(id);
    } catch (error) {
      console.error('[Fetch Knowledge Base Error]', error);
      currentKb.value = null;
    } finally {
      kbLoading.value = false;
    }
  }

  /** 加载文档列表 */
  async function fetchDocuments(kbId: number, params?: PageParams): Promise<boolean> {
    documentsLoading.value = true;
    documentsError.value = null;
    try {
      const res = await getDocuments(kbId, params);
      documents.value = Array.isArray(res.items) ? res.items : [];
      documentsTotal.value = res.total ?? documents.value.length;
      return true;
    } catch (error) {
      console.error('[Fetch Documents Error]', error);
      documents.value = [];
      documentsError.value = '文档列表加载失败，请检查网络后重试';
      return false;
    } finally {
      documentsLoading.value = false;
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
    documentsTotal.value = 0;
    documentsError.value = null;
    searchResults.value = [];
  }

  return {
    knowledgeBases,
    currentKb,
    documents,
    searchResults,
    isLoading,
    kbLoading,
    documentsLoading,
    documentsError,
    total,
    documentsTotal,
    fetchKnowledgeBases,
    fetchKnowledgeBase,
    fetchDocuments,
    search,
    clearCurrentKb,
  };
});
