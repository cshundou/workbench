import { describe, it, expect } from 'vitest';
import { parseSSELine } from '@/utils/sse';

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
