import type { ResearchRequest, TaskDetail } from './types';

export const isTerminal = (status: TaskDetail['status']) => status === 'succeeded' || status === 'failed';
export const statusLabels: Record<string, string> = {
  queued: '等待执行', running: '研究进行中', succeeded: '研究完成', failed: '执行失败',
};

export class ApiError extends Error {
  constructor(message: string, public status?: number) { super(message); }
}

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal });
    let body: unknown;
    try { body = await response.json(); } catch { throw new ApiError('服务返回了无法读取的数据，请稍后重试。', response.status); }
    if (!response.ok) {
      const detail = (body as { detail?: unknown })?.detail;
      const message = typeof detail === 'string' ? detail : Array.isArray(detail)
        ? detail.map(item => `${item.loc?.slice(1).join('.') || '参数'}: ${item.msg}`).join('；')
        : `请求失败（HTTP ${response.status}）`;
      throw new ApiError(message, response.status);
    }
    return body as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('暂时无法连接服务，提交结果可能尚未确认。请使用相同请求重试。');
  } finally { clearTimeout(timer); }
}

export const getTask = (id: string) => request<TaskDetail>(`/api/tasks/${encodeURIComponent(id)}`);
export const listTasks = () => request<{ items: TaskDetail[] }>('/api/tasks');
export const createTask = (input: ResearchRequest, key: string) => request<TaskDetail>('/api/tasks', {
  method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key }, body: JSON.stringify(input),
});
export const retryTask = (id: string, key: string) => request<TaskDetail>(`/api/tasks/${encodeURIComponent(id)}/retry`, {
  method: 'POST', headers: { 'Idempotency-Key': key },
});

export function validateRequest(input: ResearchRequest): Record<string, string> {
  const errors: Record<string, string> = {};
  if (input.market === 'CN_A' ? !/^\d{6}$/.test(input.symbol) : !/^[A-Z][A-Z0-9.-]{0,9}$/.test(input.symbol)) {
    errors.symbol = input.market === 'CN_A' ? '请输入 6 位 A 股证券代码。' : '请输入有效的美股代码，如 AAPL 或 BRK.B。';
  }
  if (!Number.isInteger(input.horizon_days) || input.horizon_days < 1 || input.horizon_days > 20) errors.horizon_days = '研究周期须为 1–20 个交易日的整数。';
  if (input.research_question.trim().length < 2) errors.research_question = '请写下至少 2 字的研究问题。';
  if (input.research_question.length > 1000) errors.research_question = '研究问题请控制在 1000 字以内。';
  return errors;
}

type Submission = { key: string; fingerprint: string };
const volatileStore = new Map<string, unknown>();
export function keyForRequest(input: ResearchRequest): string {
  const fingerprint = JSON.stringify(input);
  const saved = readStored<Submission>('arena.submission');
  if (saved?.fingerprint === fingerprint && typeof saved.key === 'string') return saved.key;
  const key = crypto.randomUUID();
  writeStored('arena.submission', { key, fingerprint });
  return key;
}
export function keyForRetry(task: TaskDetail): string {
  const storageKey = `arena.retry.${task.id}.${task.attempt_count}`;
  const saved = readStored<string>(storageKey);
  if (typeof saved === 'string') return saved;
  const key = crypto.randomUUID();
  writeStored(storageKey, key);
  return key;
}
export function readStored<T>(key: string): T | null {
  if (volatileStore.has(key)) return volatileStore.get(key) as T;
  try { return JSON.parse(localStorage.getItem(key) || 'null') as T | null; } catch { return null; }
}
export function writeStored(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); volatileStore.delete(key); }
  catch { volatileStore.set(key, value); }
}
export function clearSubmission() {
  volatileStore.delete('arena.submission');
  try { localStorage.removeItem('arena.submission'); } catch { /* Nonessential browser persistence. */ }
}
