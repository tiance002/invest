import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import type { TaskDetail } from './types';

const fixture = (status: TaskDetail['status']): TaskDetail => ({
  id: 'task-1', status, mode: 'mock', request: { symbol: '600519', market: 'CN_A', horizon_days: 3, research_question: '验证模拟流程', scenario: 'fail_once' },
  run_version: 'mock-v1', attempt_count: 1, created_at: '2026-10-28T00:00:00Z', updated_at: '2026-10-28T00:00:00Z',
  error: status === 'failed' ? { code: 'MOCK_FAILURE', message: '模拟首次执行失败' } : null, result: null, runs: [],
});
const response = (value: unknown) => Promise.resolve(new Response(JSON.stringify(value), { status: 200 }));
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('research workbench', () => {
  it('starts empty and rejects invalid forms without a POST', async () => {
    const fetchMock = vi.fn().mockImplementation(() => response({ items: [] }));
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    expect(await screen.findByText('一个论点，两种视角。')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '开始模拟研究' }));
    expect(screen.getByText('请输入 6 位 A 股证券代码。')).toBeInTheDocument();
    expect(screen.getByText('请写下至少 2 字的研究问题。')).toBeInTheDocument();
    expect(fetchMock.mock.calls.every(call => !call[1]?.method)).toBe(true);
  });

  it('recovers saved task and does not poll succeeded task', async () => {
    localStorage.setItem('arena.selected', JSON.stringify('task-1'));
    const fetchMock = vi.fn().mockImplementation((url: string) => response(url === '/api/tasks' ? { items: [] } : fixture('succeeded')));
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    await screen.findByText('研究完成');
    vi.useFakeTimers();
    await act(() => vi.advanceTimersByTimeAsync(6000));
    expect(fetchMock.mock.calls.filter(call => call[0] === '/api/tasks/task-1')).toHaveLength(1);
    fireEvent.keyDown(screen.getByRole('tab', { name: '研究结果' }), { key: 'ArrowRight' });
    expect(screen.getByRole('tab', { name: /执行轨迹/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('执行记录')).toBeInTheDocument();
  });

  it('polls running tasks until terminal status, then stops', async () => {
    localStorage.setItem('arena.selected', JSON.stringify('task-1'));
    let reads = 0;
    const fetchMock = vi.fn().mockImplementation((url: string) => response(url === '/api/tasks' ? { items: [] } : fixture(++reads === 1 ? 'running' : 'succeeded')));
    vi.stubGlobal('fetch', fetchMock);
    vi.useFakeTimers();
    await act(async () => { render(<App />); });
    expect(screen.getByText('研究进行中')).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(screen.getByText('研究完成')).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(reads).toBe(2);
  });

  it('explains uncertain submission and reuses its key on user retry', async () => {
    let writes = 0;
    const fetchMock = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
      if (options?.method === 'POST' && ++writes === 1) return Promise.reject(new TypeError('Failed to fetch'));
      return response(url === '/api/tasks' && !options?.method ? { items: [] } : fixture('succeeded'));
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    fireEvent.change(screen.getByLabelText('证券代码'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('研究问题'), { target: { value: '验证模拟流程' } });
    fireEvent.click(screen.getByRole('button', { name: '开始模拟研究' }));
    expect(await screen.findByText('操作未确认')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '开始模拟研究' }));
    await screen.findByText('研究完成');
    const posts = fetchMock.mock.calls.filter(call => call[1]?.method === 'POST');
    expect(posts).toHaveLength(2);
    expect(posts[0][1].headers['Idempotency-Key']).toBe(posts[1][1].headers['Idempotency-Key']);
  });

  it('shows failure and retries with the same task id and an idempotency header', async () => {
    localStorage.setItem('arena.selected', JSON.stringify('task-1'));
    let retried = false;
    const fetchMock = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
      if (url.endsWith('/retry')) { retried = true; expect(options?.headers).toHaveProperty('Idempotency-Key'); return response(fixture('queued')); }
      return response(url === '/api/tasks' ? { items: [] } : fixture(retried ? 'succeeded' : 'failed'));
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    expect(await screen.findByText('模拟首次执行失败')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试此任务' }));
    await waitFor(() => expect(screen.getByText('研究完成')).toBeInTheDocument());
    expect(fetchMock.mock.calls.some(call => call[0] === '/api/tasks/task-1/retry')).toBe(true);
    expect(JSON.parse(localStorage.getItem('arena.selected')!)).toBe('task-1');
  });
});
