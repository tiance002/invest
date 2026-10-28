# Phase-one API contract

All outputs use `mode: "mock"`. There is no live data or trading endpoint.

## Endpoints

- `POST /api/tasks`, required `Idempotency-Key` header (8–128 chars), response HTTP 202 TaskDetail. Same key + canonical request replays the existing task; different request with same key returns 409. DB commit precedes Redis notification.
- `GET /api/tasks` returns `{items: TaskDetail[]}` (latest 50).
- `GET /api/tasks/{id}` returns TaskDetail or 404.
- `POST /api/tasks/{id}/retry`, required `Idempotency-Key`, HTTP 202 TaskDetail. Failed task only; durable replay of same retry key; queued/running/succeeded cannot create new runs through retry. Max attempts bounded.
- `GET /healthz` liveness.
- `GET /readyz` dependency status; PostgreSQL required, Redis degraded allowed because DB polling is durable fallback.

## Request

```json
{
  "symbol": "600519",
  "market": "CN_A",
  "horizon_days": 3,
  "research_question": "验证模拟证据与反方质询流程",
  "scenario": "normal"
}
```

Markets `CN_A|US`. Horizon 1–20 trading days (default 3). Symbols validated by market. Scenario `normal|fail_once|timeout` is explicitly simulated fault injection. No real thresholds or investment advice.

## TaskDetail

```typescript
type TaskDetail = {
  id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  mode: 'mock';
  request: {symbol: string; market: 'CN_A' | 'US'; horizon_days: number; research_question: string; scenario: 'normal' | 'fail_once' | 'timeout'};
  run_version: string;
  attempt_count: number;
  created_at: string;
  updated_at: string;
  error: {code: string; message: string} | null;
  result: {
    mode: 'mock';
    summary: string;
    agreements: string[];
    disagreements: string[];
    open_questions: string[];
    evidence_refs: string[];
    agent_outputs: AgentOutput[];
  } | null;
  runs: Array<{
    id: string; attempt: number; run_version: string; status: string;
    started_at: string; finished_at: string | null; duration_ms: number | null;
    error: {code: string; message: string} | null;
    agent_runs: Array<{
      id: string; role: string; status: string; input: unknown;
      output: AgentOutput | null; evidence_refs: string[];
      duration_ms: number | null; error: {code: string; message: string} | null;
      model_provider: string; model_name: string;
      input_tokens: number | null; output_tokens: number | null; cost_usd: number | null;
    }>;
  }>;
};
type AgentOutput = {
  mode: 'mock'; role: 'researcher' | 'challenger';
  basis: string[]; doubts: string[]; conclusion: string; evidence_refs: string[];
};
```

FastAPI validation errors use standard `detail`; application errors use readable `detail` strings. Display human Chinese labels in the UI; retain raw JSON inspection. Poll running/queued tasks, stop polling terminal tasks, preserve key on uncertain network failure, persist task ID for reload recovery.
