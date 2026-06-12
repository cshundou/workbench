import request from './request';
import type { GraphDefinition } from './workflow';

export interface MarketplaceTemplateItem {
  id: string;
  name: string;
  description: string;
  category?: string;
  industry?: string;
  is_official?: boolean;
  node_count?: number;
}

export function listMarketplaceTemplates(params?: {
  category?: string;
  industry?: string;
  keyword?: string;
}): Promise<{ items: MarketplaceTemplateItem[]; total: number }> {
  return request.get('/marketplace/templates', { params }) as Promise<{
    items: MarketplaceTemplateItem[];
    total: number;
  }>;
}

export function getMarketplaceTemplate(id: string): Promise<{
  id: string;
  name: string;
  graph_definition: GraphDefinition;
}> {
  return request.get(`/marketplace/templates/${id}`) as Promise<{
    id: string;
    name: string;
    graph_definition: GraphDefinition;
  }>;
}
