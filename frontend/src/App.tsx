import { useEffect, useState } from 'react';
import { Activity, ArrowUpRight, BookOpen, Check, ChevronDown, Circle, FileJson, FlaskConical, Layers3, LoaderCircle, Plus, RefreshCw, Scale, Search, ShieldCheck, TriangleAlert } from 'lucide-react';
import { clearSubmission, createTask, getTask, isTerminal, keyForRequest, keyForRetry, listTasks, readStored, retryTask, statusLabels, validateRequest, writeStored } from './api';
import type { AgentOutput, ResearchRequest, TaskDetail } from './types';

const defaultRequest: ResearchRequest = { symbol: '', market: 'CN_A', horizon_days: 3, research_question: '', scenario: 'normal' };
const scenarioLabels = { normal: '正常研究流程', fail_once: '首次失败，重试恢复', timeout: '执行超时' };
const shortDate = (value: string) => new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
const messageOf = (error: unknown) => error instanceof Error ? error.message : '请求失败，请稍后重试。';
const mergeTask = (items: TaskDetail[], next: TaskDetail) => [next, ...items.filter(item => item.id !== next.id)].sort((a, b) => b.created_at.localeCompare(a.created_at));

export default function App() {
  const [draft, setDraft] = useState<ResearchRequest>(() => readStored<ResearchRequest>('arena.draft') || defaultRequest);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [tasks, setTasks] = useState<TaskDetail[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(() => readStored<string>('arena.selected'));
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [listError, setListError] = useState('');
  const [detailError, setDetailError] = useState('');
  const [actionError, setActionError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [refreshList, setRefreshList] = useState(0);
  const [activeTab, setActiveTab] = useState<'result' | 'trace' | 'raw'>('result');

  useEffect(() => { writeStored('arena.draft', draft); }, [draft]);
  useEffect(() => { writeStored('arena.selected', selectedId); }, [selectedId]);
  useEffect(() => {
    let alive = true;
    setInitialLoading(true);
    listTasks().then(data => {
      if (!alive) return;
      setTasks(data.items); setListError('');
      setSelectedId(previous => previous || data.items[0]?.id || null);
    }).catch(error => { if (alive) setListError(messageOf(error)); })
      .finally(() => { if (alive) setInitialLoading(false); });
    return () => { alive = false; };
  }, [refreshList]);

  useEffect(() => {
    if (!selectedId) { setTask(null); setDetailError(''); return; }
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    setTask(previous => previous?.id === selectedId ? previous : null);
    async function poll() {
      try {
        const next = await getTask(selectedId!);
        if (!alive) return;
        setTask(next); setTasks(items => mergeTask(items, next)); setDetailError('');
        if (!isTerminal(next.status)) timer = setTimeout(poll, 1000);
      } catch (error) {
        if (!alive) return;
        setDetailError(messageOf(error));
        // Keep transient read failures recoverable without losing the selected task.
        timer = setTimeout(poll, 5000);
      }
    }
    void poll();
    return () => { alive = false; clearTimeout(timer); };
  }, [selectedId, refresh]);

  function edit<K extends keyof ResearchRequest>(field: K, value: ResearchRequest[K]) {
    setDraft(previous => ({ ...previous, [field]: value }));
    setErrors(previous => ({ ...previous, [field]: '' }));
    setActionError(''); clearSubmission();
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const input = { ...draft, symbol: draft.symbol.trim().toUpperCase(), research_question: draft.research_question.trim() };
    const issues = validateRequest(input);
    setErrors(issues);
    if (Object.keys(issues).length) return;
    setBusy(true); setActionError('');
    try {
      const next = await createTask(input, keyForRequest(input));
      setTask(next); setTasks(items => mergeTask(items, next)); setSelectedId(next.id);
      setRefresh(value => value + 1); setActiveTab('result');
    } catch (error) { setActionError(messageOf(error)); }
    finally { setBusy(false); }
  }

  async function retry() {
    if (!task || busy) return;
    setBusy(true); setActionError('');
    try {
      const next = await retryTask(task.id, keyForRetry(task));
      setTask(next); setTasks(items => mergeTask(items, next));
      setRefresh(value => value + 1); setActiveTab('result');
    } catch (error) { setActionError(messageOf(error)); }
    finally { setBusy(false); }
  }

  function newRequest() {
    clearSubmission(); setActionError(''); setErrors({});
    setSelectedId(null); setActiveTab('result');
    document.getElementById('symbol')?.focus();
  }

  return <div className="app-shell">
    <header className="masthead">
      <a className="brand" href="#main" aria-label="论点研究室，跳至主内容"><span className="brand-mark"><Layers3 size={22} strokeWidth={1.5} /></span><span>论点研究室<small>Investment Thesis Arena</small></span></a>
      <div className="environment"><span className="mock-tag"><FlaskConical size={13} /> 模拟数据</span><span className="header-note">第一阶段 / 研究工作流验证</span></div>
    </header>
    <main id="main">
      <section className="intro">
        <div><div className="section-kicker">研究，从一个值得质疑的论点开始</div><h1>让证据与质疑，同席而谈。</h1><p>提出研究问题，观察研究员与反方的独立判断，沿着证据回看每一步。</p></div>
        <div className="scope-note"><ShieldCheck size={20} /><div><strong>非投资建议</strong><span>所有论点与证据均为模拟生成<br />不接入实时行情，不提供交易操作</span></div></div>
      </section>
      <div className="workspace">
        <aside className="request-panel" aria-labelledby="request-heading">
          <div className="panel-heading"><h2 id="request-heading"><Search size={17} /> 发起研究</h2><button className="text-button new-button" onClick={newRequest} disabled={busy}><Plus size={14} /> 新任务</button></div>
          <form noValidate onSubmit={submit}>
            <fieldset disabled={busy}>
              <div className="field"><label htmlFor="market">研究市场</label><div className="select-wrap"><select id="market" value={draft.market} onChange={event => edit('market', event.target.value as ResearchRequest['market'])}><option value="CN_A">A 股 / CN_A</option><option value="US">美股 / US</option></select><ChevronDown size={15} /></div></div>
              <div className="form-row"><div className="field"><label htmlFor="symbol">证券代码</label><input id="symbol" placeholder={draft.market === 'CN_A' ? '例如 600519' : '例如 AAPL'} value={draft.symbol} onChange={event => edit('symbol', event.target.value.toUpperCase())} aria-invalid={!!errors.symbol} aria-describedby={errors.symbol ? 'symbol-error' : undefined} autoComplete="off" />{errors.symbol && <span id="symbol-error" className="field-error">{errors.symbol}</span>}</div><div className="field horizon-field"><label htmlFor="horizon">研究周期<span>交易日</span></label><input id="horizon" type="number" min="1" max="20" value={Number.isNaN(draft.horizon_days) ? '' : draft.horizon_days} onChange={event => edit('horizon_days', event.target.value === '' ? NaN : Number(event.target.value))} aria-invalid={!!errors.horizon_days} /></div></div>
              {errors.horizon_days && <p className="field-error">{errors.horizon_days}</p>}
              <div className="field"><label htmlFor="question">研究问题</label><textarea id="question" rows={4} maxLength={1000} placeholder="例如：哪些模拟证据支持当前论点？反方会如何质疑其假设？" value={draft.research_question} onChange={event => edit('research_question', event.target.value)} aria-invalid={!!errors.research_question} aria-describedby={errors.research_question ? 'question-error' : undefined} />{errors.research_question && <span className="field-error" id="question-error">{errors.research_question}</span>}<span className="field-hint">描述希望验证的假设或尚未解答的问题。</span></div>
              <div className="field scenario-field"><label htmlFor="scenario">模拟场景<span>流程验证</span></label><div className="select-wrap"><select id="scenario" value={draft.scenario} onChange={event => edit('scenario', event.target.value as ResearchRequest['scenario'])}>{Object.entries(scenarioLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><ChevronDown size={15} /></div><span className="field-hint">失败与超时仅用于模拟故障及重试。</span></div>
              <button className="primary-button submit-button" type="submit">{busy ? <LoaderCircle size={16} className="spin" /> : <Plus size={16} />}{busy ? '正在提交…' : '开始模拟研究'}</button>
            </fieldset>
          </form>
          {actionError && <div role="alert" className="error-box"><TriangleAlert size={16} /><div><strong>操作未确认</strong><p>{actionError}</p><span>重试会复用本次请求标识，避免重复创建。</span></div></div>}
          <div className="request-footnote"><FlaskConical size={14} /><span>模拟工作流仅验证研究编排与可追溯性。</span></div>
        </aside>
        <section className="research-panel" aria-label="研究任务工作区">
          <div className="task-toolbar"><div className="task-picker"><label htmlFor="task-select">最近任务</label><div className="select-wrap"><select id="task-select" value={selectedId || ''} onChange={event => { setSelectedId(event.target.value || null); setActiveTab('result'); setActionError(''); }}><option value="">选择研究任务</option>{tasks.map(item => <option key={item.id} value={item.id}>{item.request.symbol} / {statusLabels[item.status]} / {shortDate(item.created_at)} / {item.id.slice(0, 8)}</option>)}</select><ChevronDown size={15} /></div></div><button className="icon-button" aria-label="刷新任务列表" title="刷新任务列表" onClick={() => { setRefreshList(value => value + 1); setRefresh(value => value + 1); }}><RefreshCw size={16} className={initialLoading ? 'spin' : ''} /></button></div>
          {listError && <div className="inline-error" role="alert">任务列表读取失败：{listError}<button className="text-button" onClick={() => setRefreshList(value => value + 1)}>重新读取</button></div>}
          {detailError && <div className="inline-error" role="alert">任务状态读取失败：{detailError}<button className="text-button" onClick={() => setRefresh(value => value + 1)}>立即重连</button></div>}
          {selectedId ? task ? <>
            <div className="task-heading"><div><div className="task-context">{task.request.market === 'CN_A' ? 'A 股' : '美股'}<span>{task.request.horizon_days} 个交易日</span><span>{scenarioLabels[task.request.scenario]}</span></div><h2>{task.request.symbol}<StatusBadge status={task.status} /></h2><p>{task.request.research_question}</p></div><div className="task-time">{shortDate(task.created_at)}<span>创建时间</span></div></div>
            <div className="progress-track" aria-label="研究进度">{['queued', 'running', 'succeeded'].map((status, index) => {
              const current = task.status === status;
              const passed = task.status === 'succeeded' || (task.status === 'running' && index === 0) || (task.status === 'failed' && index === 0);
              return <div key={status} className={`${current ? 'current' : ''} ${passed ? 'passed' : ''}`}><span className="step-dot">{passed ? <Check size={12} /> : current && !isTerminal(task.status) ? <LoaderCircle size={12} className="spin" /> : <Circle size={8} />}</span><span>{['请求入队', '双向研究', '汇总结果'][index]}</span></div>;
            })}</div>
            <div className="tabs" onKeyDown={tabKeys} role="tablist" aria-label="任务内容"><button id="tab-result" role="tab" tabIndex={activeTab === 'result' ? 0 : -1} aria-selected={activeTab === 'result'} aria-controls="task-content" onClick={() => setActiveTab('result')}><BookOpen size={16} /> 研究结果</button><button id="tab-trace" role="tab" tabIndex={activeTab === 'trace' ? 0 : -1} aria-selected={activeTab === 'trace'} aria-controls="task-content" onClick={() => setActiveTab('trace')}><Activity size={16} /> 执行轨迹<span>{task.runs.length}</span></button><button id="tab-raw" role="tab" tabIndex={activeTab === 'raw' ? 0 : -1} aria-selected={activeTab === 'raw'} aria-controls="task-content" onClick={() => setActiveTab('raw')}><FileJson size={16} /> 原始数据</button></div>
            <div id="task-content" className="task-content" role="tabpanel" aria-labelledby={`tab-${activeTab}`}>
              {activeTab === 'raw' ? <><div className="content-heading"><h3>任务原始 JSON</h3><span>保留接口原始字段</span></div><pre className="raw-json" tabIndex={0}>{JSON.stringify(task, null, 2)}</pre></> : activeTab === 'trace' ? <Trace task={task} /> : <>
                {task.status === 'failed' && <div className="failure-panel" role="alert"><TriangleAlert size={24} /><div><h3>这次研究未能完成</h3><p>{task.error?.message || '执行过程中发生错误，可重试此任务。'}</p><code>{task.error?.code || 'UNKNOWN_ERROR'}</code><p className="muted">重试将保留本任务并新增一次执行记录，历史轨迹仍可查看。</p><button className="primary-button" onClick={retry} disabled={busy}><RefreshCw size={15} />{busy ? '正在重试…' : '重试此任务'}</button></div></div>}
                {!isTerminal(task.status) && <div className="working-state" role="status"><span className="working-icon"><Scale size={28} strokeWidth={1.3} /></span><h3>{task.status === 'queued' ? '研究请求已入队' : '研究与质询正在进行'}</h3><p>{task.status === 'queued' ? '等待工作进程领取任务，页面将自动更新。' : '研究员梳理依据，反方检验假设。完成后将在这里展示双方结论。'}</p><span className="live-text"><span />每秒同步任务状态</span></div>}
                {task.result && <Results task={task} />}
              </>}
            </div>
            <div className="task-meta"><span>任务 <code>{task.id}</code></span><span>版本 <code>{task.run_version}</code></span><span>第 {task.attempt_count} 次执行</span></div>
          </> : <div className="empty-state" role="status"><LoaderCircle className="spin" size={26} /><h2>正在恢复任务</h2><p>读取已保存的研究记录与执行状态。</p></div> : <div className="empty-state"><div className="empty-art"><BookOpen size={37} strokeWidth={1.1} /><span><Scale size={22} strokeWidth={1.3} /></span></div><h2>一个论点，两种视角。</h2><p>从左侧提出研究问题。研究完成后，<br />在这里对照依据、质疑与尚待验证的事项。</p><div className="empty-flow"><span><Search size={14} /> 提出问题</span><span className="flow-line" /><span><Scale size={14} /> 独立质询</span><span className="flow-line" /><span><BookOpen size={14} /> 回溯证据</span></div><span className="empty-note">当前没有选中的研究任务</span></div>}
        </section>
      </div>
      <footer><span>Investment Thesis Arena <span className="footer-separator">/</span> 第一阶段</span><span>模拟数据，非投资建议。研究结论不构成买卖依据。</span></footer>
    </main>
  </div>;
}

function tabKeys(event: React.KeyboardEvent<HTMLDivElement>) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
  const index = buttons.indexOf(event.target as HTMLButtonElement);
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
    : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
  event.preventDefault(); buttons[next]?.focus(); buttons[next]?.click();
}

function StatusBadge({ status }: { status: TaskDetail['status'] }) {
  return <span className={`status-badge ${status}`} role="status"><span />{statusLabels[status]}</span>;
}

function ItemList({ items, empty = '暂无记录' }: { items: string[]; empty?: string }) {
  return items.length ? <ul className="item-list">{items.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="muted small">{empty}</p>;
}

function AgentCard({ output }: { output: AgentOutput }) {
  const researcher = output.role === 'researcher';
  return <article className={`agent-card ${researcher ? 'researcher' : 'challenger'}`}><div className="agent-title"><span className="role-icon">{researcher ? <BookOpen size={18} /> : <Scale size={18} />}</span><div><h3>{researcher ? '研究员' : '反方质询'}</h3><span>{researcher ? '建立论点，陈述依据' : '检验假设，识别缺口'}</span></div><span className="tiny-mock">模拟</span></div><div className="agent-body"><h4>研究依据</h4><ItemList items={output.basis} /><h4>疑点与局限</h4><ItemList items={output.doubts} /><div className="agent-conclusion"><h4>独立结论</h4><p>{output.conclusion}</p></div><div className="evidence-tags" aria-label="引用证据">{output.evidence_refs.map(ref => <a href={`#evidence-${encodeURIComponent(ref)}`} key={ref}>{ref}<ArrowUpRight size={10} /></a>)}</div></div></article>;
}

function Results({ task }: { task: TaskDetail }) {
  const result = task.result!;
  const refs = [...new Set([...result.evidence_refs, ...result.agent_outputs.flatMap(output => output.evidence_refs)])];
  return <><section className="summary-panel"><div className="summary-title"><Check size={16} /><h3>研究综述</h3><span>模拟结论</span></div><p>{result.summary}</p></section><div className="agent-grid">{result.agent_outputs.map(output => <AgentCard output={output} key={output.role} />)}</div><section className="synthesis"><div><h3><span className="list-marker agreed" />双方共识</h3><ItemList items={result.agreements} /></div><div><h3><span className="list-marker disputed" />主要分歧</h3><ItemList items={result.disagreements} /></div><div><h3><span className="list-marker open" />待验证问题</h3><ItemList items={result.open_questions} /></div></section><section className="evidence-section"><div className="content-heading"><h3>证据索引</h3><span>模拟引用 / {refs.length} 项</span></div><p className="muted small">以下为模拟证据标识；具体引用及版本可在执行轨迹和原始数据中核对。</p><div className="evidence-index">{refs.map(ref => <div id={`evidence-${ref}`} key={ref}><FileJson size={14} /><code>{ref}</code><span>模拟证据</span></div>)}</div></section></>;
}

function Trace({ task }: { task: TaskDetail }) {
  return <><div className="content-heading"><h3>执行记录</h3><span>完整保留每次执行</span></div>{!task.runs.length && <p className="muted">工作进程尚未开始执行，领取后将生成轨迹。</p>}<div className="trace-list">{task.runs.map(run => <details className="run-record" key={run.id} open><summary><span className="run-number">第 {run.attempt} 次</span><span>{statusLabels[run.status] || run.status}</span><code>{run.run_version}</code><span>{run.duration_ms === null ? '执行中' : `${run.duration_ms} ms`}</span><ChevronDown size={15} /></summary><div className="run-body"><dl className="run-info"><div><dt>执行 ID</dt><dd>{run.id}</dd></div><div><dt>开始时间</dt><dd>{shortDate(run.started_at)}</dd></div><div><dt>结束时间</dt><dd>{run.finished_at ? shortDate(run.finished_at) : '尚未结束'}</dd></div></dl>{run.error && <p className="trace-error">{run.error.code}: {run.error.message}</p>}{run.agent_runs.map(agent => <details className="agent-record" key={agent.id}><summary><span>{agent.role === 'researcher' ? '研究员' : agent.role === 'challenger' ? '反方质询' : agent.role}</span><span>{statusLabels[agent.status] || agent.status}</span><span>{agent.duration_ms === null ? '耗时待记录' : `${agent.duration_ms} ms`}</span><ChevronDown size={14} /></summary><div className="agent-record-body"><p>提供方 <code>{agent.model_provider}</code> / 模型 <code>{agent.model_name}</code></p><p>输入 Token：{agent.input_tokens ?? '未记录'} / 输出 Token：{agent.output_tokens ?? '未记录'} / 成本：{agent.cost_usd === null ? '未记录' : `$${agent.cost_usd}`}</p><h4>引用证据</h4><ItemList items={agent.evidence_refs} /><h4>输入</h4><pre className="raw-json">{JSON.stringify(agent.input, null, 2)}</pre><h4>输出</h4><pre className="raw-json">{JSON.stringify(agent.output, null, 2)}</pre>{agent.error && <p className="trace-error">{agent.error.code}: {agent.error.message}</p>}</div></details>)}</div></details>)}</div></>;
}
