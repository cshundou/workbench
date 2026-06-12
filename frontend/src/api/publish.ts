import request from './request';

export function createPublishToken(data: {
  resource_type: string;
  resource_id: number;
  publish_mode?: string;
}): Promise<{ token: string; embed_url: string; api_url: string }> {
  return request.post('/publish/tokens', data) as Promise<{
    token: string;
    embed_url: string;
    api_url: string;
  }>;
}

export function getPublishInfo(token: string): Promise<{
  resource_type: string;
  resource_id: number;
  publish_mode: string;
}> {
  return request.get(`/publish/${token}/info`) as Promise<{
    resource_type: string;
    resource_id: number;
    publish_mode: string;
  }>;
}
