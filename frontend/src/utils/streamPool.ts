/**
 * 全局 SSE / 流式连接池，避免同一资源重复创建连接。
 */
import { fetchSSEStream, type FetchSSEStreamOptions } from './sse';

interface PoolEntry {
  key: string;
  abortController: AbortController;
  promise: Promise<void>;
}

const pool = new Map<string, PoolEntry>();

function buildPoolKey(url: string, method: string, body?: string): string {
  return `${method}:${url}:${body || ''}`;
}

/** 从连接池获取或创建流式连接 */
export function acquireStream<T>(options: FetchSSEStreamOptions<T>): {
  key: string;
  promise: Promise<void>;
  abort: () => void;
} {
  const method = options.method || 'POST';
  const key = buildPoolKey(options.url, method, options.body);

  const existing = pool.get(key);
  if (existing) {
    return {
      key,
      promise: existing.promise,
      abort: () => releaseStream(key),
    };
  }

  const abortController = new AbortController();
  let mergedSignal: AbortSignal = abortController.signal;
  if (options.signal) {
    if (options.signal.aborted) {
      abortController.abort();
    } else {
      options.signal.addEventListener('abort', () => abortController.abort(), {
        once: true,
      });
    }
  }

  const promise = fetchSSEStream<T>({
    ...options,
    signal: mergedSignal,
  }).finally(() => {
    pool.delete(key);
  });

  pool.set(key, { key, abortController, promise });
  return {
    key,
    promise,
    abort: () => releaseStream(key),
  };
}

/** 释放连接池中的流式连接 */
export function releaseStream(key: string): void {
  const entry = pool.get(key);
  if (!entry) {
    return;
  }
  entry.abortController.abort();
  pool.delete(key);
}

/** 释放全部连接（如页面卸载时） */
export function releaseAllStreams(): void {
  for (const key of [...pool.keys()]) {
    releaseStream(key);
  }
}
