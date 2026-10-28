export type ResearchRequest = {
  symbol: string;
  market: 'CN_A' | 'US';
  horizon_days: number;
  research_question: string;
  scenario: 'normal' | 'fail_once' | 'timeout';
};
export type AgentOutput = {
  mode: 'mock'; role: 'researcher' | 'challenger';
  basis: string[]; doubts: string[]; conclusion: string; evidence_refs: string[];
};
export type TaskError = { code: string; message: string };
export type TaskDetail = {
  id: string; status: 'queued' | 'running' | 'succeeded' | 'failed'; mode: 'mock';
  request: ResearchRequest; run_version: string; attempt_count: number;
  created_at: string; updated_at: string; error: TaskError | null;
  result: {
    mode: 'mock'; summary: string; agreements: string[]; disagreements: string[];
    open_questions: string[]; evidence_refs: string[]; agent_outputs: AgentOutput[];
  } | null;
  runs: Array<{
    id: string; attempt: number; run_version: string; status: string;
    started_at: string; finished_at: string | null; duration_ms: number | null;
    error: TaskError | null;
    agent_runs: Array<{
      id: string; role: string; status: string; input: unknown; output: AgentOutput | null;
      evidence_refs: string[]; duration_ms: number | null; error: TaskError | null;
      model_provider: string; model_name: string; input_tokens: number | null;
      output_tokens: number | null; cost_usd: number | null;
    }>;
  }>;
};
