import { beforeEach, describe, expect, it, vi } from 'vitest';
import { clearSubmission, createTask, isTerminal, keyForRequest, keyForRetry, request, validateRequest } from './api';
import type { ResearchRequest, TaskDetail } from './types';

const input: ResearchRequest = { symbol: '600519', market: 'CN_A', horizon_days: 3, research_question: '测试研究问题', scenario: 'normal' };
beforeEach(() => localStorage.clear());

describe('request validation', () => {
  it('validates market-specific symbols and trading horizon', () => {
    expect(validateRequest(input)).toEqual({});
    expect(validateRequest({ ...input, symbol: 'AAPL' })).toHaveProperty('symbol');
    expect(validateRequest({ ...input, market: 'US', symbol: 'BRK.B' })).toEqual({});
    expect(validateRequest({ ...input, horizon_days: 21 })).toHaveProperty('horizon_days');
    expect(validateRequest({ ...input, horizon_days: 1.5 })).toHaveProperty('horizon_days');
    expect(validateRequest({ ...input, research_question: '   ' })).toHaveProperty('research_question');
  });
});

describe('idempotency and uncertain failures', () => {
  it('keeps the same key across resubmission and rotates for changed or explicit new requests', () => {
    const first = keyForRequest(input);
    expect(keyForRequest(input)).toBe(first);
    expect(keyForRequest({ ...input, symbol: '000001' })).not.toBe(first);
    clearSubmission();
    expect(keyForRequest(input)).not.toBe(first);
  });
  it('retains key after network uncertainty and sends required header', async () => {
    const mock = vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValueOnce(new Response(JSON.stringify({ id: 'same-task' }), { status: 202 }));
    vi.stubGlobal('fetch', mock);
    const key = keyForRequest(input);
    await expect(createTask(input, key)).rejects.toThrow('提交结果可能尚未确认');
    await createTask(input, keyForRequest(input));
    expect(mock.mock.calls[1][1].headers['Idempotency-Key']).toBe(key);
  });
  it('scopes retry keys to task and attempt and preserves uncertain retries', () => {
    const task = { id: 'test-task', attempt_count: 1 } as TaskDetail;
    const first = keyForRetry(task);
    expect(keyForRetry(task)).toBe(first);
    expect(keyForRetry({ ...task, attempt_count: 2 })).not.toBe(first);
  });
  it('retains submission key in memory when browser storage is unavailable', () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Unavailable'); });
    const first = keyForRequest(input);
    expect(keyForRequest(input)).toBe(first);
    clearSubmission(); storage.mockRestore();
  });
});

it('preserves application error detail', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Task cannot be retried' }), { status: 409 })));
  await expect(request('/api/test')).rejects.toThrow('Task cannot be retried');
});

it('stops polling for both terminal statuses', () => {
  expect(isTerminal('succeeded')).toBe(true);
  expect(isTerminal('failed')).toBe(true);
  expect(isTerminal('running')).toBe(false);
  expect(isTerminal('queued')).toBe(false);
});
