import { describe, it, expect } from 'vitest';
import { buildWorkflowWsUrl } from '@/api/workflow';

describe('buildWorkflowWsUrl', () => {
  it('构建 WebSocket URL 并附带 token', () => {
    localStorage.setItem('token', 'abc123');
    const url = buildWorkflowWsUrl(42);
    expect(url).toContain('ws');
    expect(url).toContain('42');
    expect(url).toContain('token=abc123');
  });
});
