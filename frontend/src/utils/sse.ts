// frontend/src/utils/sse.ts
import { ref, Ref, onUnmounted } from 'vue';

interface SSEOptions {
  url: string;
  headers?: Record<string, string>;
  onMessage?: (data: unknown) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private url: string;
  private headers: Record<string, string>;
  private isConnected: Ref<boolean> = ref(false);
  private data: Ref<string> = ref('');
  private error: Ref<Event | null> = ref(null);

  constructor(options: SSEOptions) {
    this.url = options.url;
    this.headers = options.headers || {};
  }

  connect(): void {
    if (this.eventSource) {
      this.disconnect();
    }

    // 原生 EventSource 不支持自定义 headers，配置保留供后续 fetch-stream 方案扩展
    if (import.meta.env.DEV && Object.keys(this.headers).length > 0) {
      console.info('[SSE] Custom headers stored:', this.headers);
    }

    // 构建带参数的URL
    const urlWithParams = new URL(this.url, window.location.origin);
    // 添加认证token
    const token = localStorage.getItem('token');
    if (token) {
      urlWithParams.searchParams.append('token', token);
    }

    this.eventSource = new EventSource(urlWithParams.toString());

    this.eventSource.onopen = () => {
      this.isConnected.value = true;
      this.error.value = null;
    };

    this.eventSource.onmessage = (event) => {
      try {
        const parsedData = JSON.parse(event.data);
        this.data.value += parsedData.content || '';
      } catch {
        // 处理纯文本数据
        this.data.value += event.data;
      }
    };

    this.eventSource.onerror = (error) => {
      this.isConnected.value = false;
      this.error.value = error;
      // 自动重连（最多3次）
      setTimeout(() => {
        if (!this.isConnected.value) {
          this.connect();
        }
      }, 3000);
    };
  }

  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      this.isConnected.value = false;
    }
  }

  getData(): Ref<string> {
    return this.data;
  }

  getError(): Ref<Event | null> {
    return this.error;
  }

  getConnectionStatus(): Ref<boolean> {
    return this.isConnected;
  }
}

// 组合式API封装
export function useSSE(url: string, headers?: Record<string, string>) {
  const client = new SSEClient({ url, headers });

  onUnmounted(() => {
    client.disconnect();
  });

  return {
    connect: client.connect.bind(client),
    disconnect: client.disconnect.bind(client),
    data: client.getData(),
    error: client.getError(),
    isConnected: client.getConnectionStatus(),
  };
}
