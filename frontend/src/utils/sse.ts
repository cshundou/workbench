// frontend/src/utils/sse.ts
import { ref, Ref, onUnmounted } from 'vue';

const MAX_RECONNECT_ATTEMPTS = 3;
const RECONNECT_DELAY_MS = 3000;

/** 解析单行 SSE data 负载 */
export function parseSSELine(line: string): Record<string, unknown> | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith('data:')) {
    return null;
  }
  const payload = trimmed.slice(5).trim();
  if (!payload) {
    return null;
  }
  try {
    return JSON.parse(payload) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** 从 ReadableStream 解析 SSE 行并回调 */
async function consumeSSEStream<T>(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onMessage: (msg: T) => void,
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const parsed = parseSSELine(line);
      if (parsed) {
        onMessage(parsed as T);
      }
    }
  }
}

export interface FetchSSEStreamOptions<T> {
  url: string;
  method?: 'GET' | 'POST';
  headers?: Record<string, string>;
  body?: string;
  signal?: AbortSignal;
  onMessage: (msg: T) => void;
  onError?: (error: Error) => void;
  maxReconnectAttempts?: number;
}

/**
 * 统一 Fetch SSE 流式客户端，支持断线自动重连（默认最多 3 次）。
 */
export async function fetchSSEStream<T>(
  options: FetchSSEStreamOptions<T>,
): Promise<void> {
  const {
    url,
    method = 'POST',
    headers = {},
    body,
    signal,
    onMessage,
    onError,
    maxReconnectAttempts = MAX_RECONNECT_ATTEMPTS,
  } = options;

  const token = localStorage.getItem('token');
  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...headers,
  };

  let attempt = 0;

  while (attempt <= maxReconnectAttempts) {
    if (signal?.aborted) {
      return;
    }

    try {
      const response = await fetch(url, {
        method,
        headers: requestHeaders,
        body,
        signal,
      });

      if (!response.ok) {
        throw new Error(await response.text().catch(() => `请求失败: ${response.status}`));
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('无法读取流式响应');
      }

      await consumeSSEStream(reader, onMessage);
      return;
    } catch (error) {
      if (signal?.aborted || (error as Error).name === 'AbortError') {
        return;
      }

      attempt += 1;
      if (attempt > maxReconnectAttempts) {
        const finalError =
          error instanceof Error ? error : new Error('SSE 流式连接失败');
        onError?.(finalError);
        throw finalError;
      }

      await new Promise<void>((resolve) => {
        setTimeout(resolve, RECONNECT_DELAY_MS);
      });
    }
  }
}

interface SSEOptions {
  url: string;
  headers?: Record<string, string>;
  onMessage?: (data: unknown) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  onClose?: () => void;
  maxReconnectAttempts?: number;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private url: string;
  private headers: Record<string, string>;
  private onMessage?: (data: unknown) => void;
  private onError?: (error: Event) => void;
  private onOpen?: () => void;
  private onClose?: () => void;
  private maxReconnectAttempts: number;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private manualDisconnect = false;
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
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? MAX_RECONNECT_ATTEMPTS;
  }

  connect(): void {
    this.manualDisconnect = false;
    this.openConnection();
  }

  private openConnection(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    if (import.meta.env.DEV && Object.keys(this.headers).length > 0) {
      console.info('[SSE] Custom headers stored:', this.headers);
    }

    const urlWithParams = new URL(this.url, window.location.origin);
    const token = localStorage.getItem('token');
    if (token) {
      urlWithParams.searchParams.append('token', token);
    }

    this.eventSource = new EventSource(urlWithParams.toString());

    this.eventSource.onopen = () => {
      this.isConnected.value = true;
      this.error.value = null;
      this.reconnectAttempts = 0;
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

      if (this.manualDisconnect) {
        return;
      }

      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        return;
      }

      this.reconnectAttempts += 1;
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
      }
      this.reconnectTimer = setTimeout(() => {
        if (!this.manualDisconnect && !this.isConnected.value) {
          this.openConnection();
        }
      }, RECONNECT_DELAY_MS);
    };
  }

  disconnect(): void {
    this.manualDisconnect = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
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
