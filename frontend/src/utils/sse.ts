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
  private onMessage?: (data: unknown) => void;
  private onError?: (error: Event) => void;
  private onOpen?: () => void;
  private onClose?: () => void;
  private isConnected: Ref<boolean> = ref(false);
  private data: Ref<string> = ref('');
  private error: Ref<Event | null> = ref(null);

  constructor(options: SSEOptions) {
    this.url = options.url;
    this.headers = options.headers || {};
    this.onMessage = options.onMessage;
    this.onError = options.onError;
    this.onOpen = options.onOpen;
    this.onClose = options.onClose;
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
      this.onOpen?.();
    };

    this.eventSource.onmessage = (event) => {
      try {
        const parsedData = JSON.parse(event.data) as { content?: string };
        if (parsedData.content) {
          this.data.value += parsedData.content;
        }
        this.onMessage?.(parsedData);
      } catch {
        this.data.value += event.data;
        this.onMessage?.(event.data);
      }
    };

    this.eventSource.onerror = (error) => {
      this.isConnected.value = false;
      this.error.value = error;
      this.onError?.(error);
    };
  }

  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      this.isConnected.value = false;
      this.onClose?.();
    }
  }

  /** 重置已累积的流式文本 */
  resetData(): void {
    this.data.value = '';
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
export function useSSE(url: string, options?: Omit<SSEOptions, 'url'>) {
  const client = new SSEClient({ url, ...options });

  onUnmounted(() => {
    client.disconnect();
  });

  return {
    connect: client.connect.bind(client),
    disconnect: client.disconnect.bind(client),
    resetData: client.resetData.bind(client),
    data: client.getData(),
    error: client.getError(),
    isConnected: client.getConnectionStatus(),
  };
}
