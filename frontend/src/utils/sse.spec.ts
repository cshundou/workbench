import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { parseSSELine, fetchSSEStream } from '@/utils/sse';

describe('parseSSELine', () => {
  it('解析 data 行', () => {
    const result = parseSSELine('data: {"type":"token","content":"hi"}');
    expect(result).toEqual({ type: 'token', content: 'hi' });
  });

  it('忽略空行', () => {
    expect(parseSSELine('')).toBeNull();
    expect(parseSSELine('event: ping')).toBeNull();
  });

  it('无效 JSON 返回 null', () => {
    expect(parseSSELine('data: not-json')).toBeNull();
  });
});

describe('fetchSSEStream', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('流正常结束时不再重连', async () => {
    const encoder = new TextEncoder();
    const reader = {
      read: vi
        .fn()
        .mockResolvedValueOnce({
          done: false,
          value: encoder.encode('data: {"type":"done"}\n'),
        })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => reader },
    });

    const messages: unknown[] = [];
    await fetchSSEStream({
      url: '/api/v1/test',
      onMessage: (msg) => messages.push(msg),
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(messages).toHaveLength(1);
  });

  it('失败后最多重连 3 次', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));

    const onError = vi.fn();
    let caught: Error | null = null;
    const run = fetchSSEStream({
      url: '/api/v1/test',
      onMessage: () => undefined,
      onError,
      maxReconnectAttempts: 3,
    }).catch((error: Error) => {
      caught = error;
    });

    await vi.runAllTimersAsync();
    await run;

    expect(caught?.message).toBe('network');
    expect(global.fetch).toHaveBeenCalledTimes(4);
    expect(onError).toHaveBeenCalledTimes(1);
  });
});
