"""Black-box acceptance against running API/worker/PostgreSQL/Redis.

Uses only the standard library. Writes repeatable evidence; never deletes jobs.
Optional Redis outage touches only this repository's Compose redis service.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', default='http://127.0.0.1:8000')
    parser.add_argument('--redis-outage', action='store_true')
    parser.add_argument('--postgres-restart', action='store_true')
    args = parser.parse_args()
    evidence: dict = {'started_at': datetime.now(timezone.utc).isoformat(), 'checks': [], 'tasks': {}}

    def request(method: str, path: str, payload: dict | None = None, key: str | None = None):
        headers = {'Content-Type': 'application/json'}
        if key:
            headers['Idempotency-Key'] = key
        body = json.dumps(payload).encode() if payload is not None else None
        req = Request(args.api + path, body, headers, method=method)
        try:
            with urlopen(req, timeout=12) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def check(name: str, condition: bool):
        assert condition, name
        evidence['checks'].append({'name': name, 'passed': True})
        print(f'PASS {name}', flush=True)

    def submit(scenario='normal', key=None, **overrides):
        payload = {
            'symbol': '600519', 'market': 'CN_A', 'horizon_days': 3,
            'research_question': '模拟运行验收：仅验证证据、反方质询及持久化流程。',
            'scenario': scenario,
        } | overrides
        status, task = request('POST', '/api/tasks', payload, key or str(uuid4()))
        assert status == 202, (status, task)
        return task, payload

    def terminal(task_id: str):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            status, task = request('GET', f'/api/tasks/{task_id}')
            assert status == 200, (status, task)
            if task['status'] in ('succeeded', 'failed'):
                return task
            time.sleep(0.25)
        raise AssertionError(f'Task did not reach terminal state: {task_id}')

    try:
        check('API liveness', request('GET', '/healthz')[0] == 200)
        ready_status, ready = request('GET', '/readyz')
        evidence['readiness_before'] = ready
        check('API readiness', ready_status == 200)

        code, _ = request('POST', '/api/tasks', {'symbol': 'invalid'}, str(uuid4()))
        check('invalid request rejected', code == 422)
        code, _ = request('GET', f'/api/tasks/{uuid4()}')
        check('unknown task is 404', code == 404)

        key = str(uuid4())
        task, payload = submit(key=key)
        with ThreadPoolExecutor(max_workers=8) as pool:
            replays = list(pool.map(lambda _: request('POST', '/api/tasks', payload, key), range(8)))
        check('concurrent duplicate requests return same task', all(s == 202 and t['id'] == task['id'] for s, t in replays))
        code, _ = request('POST', '/api/tasks', payload | {'horizon_days': 4}, key)
        check('idempotency key payload conflict is 409', code == 409)
        done = terminal(task['id'])
        evidence['tasks']['normal'] = done
        check('normal task succeeds once', done['status'] == 'succeeded' and done['attempt_count'] == 1 and len(done['runs']) == 1)
        result = done['result']
        check('task and result marked mock', done['mode'] == result['mode'] == 'mock')
        check('two distinct structured agents', {a['role'] for a in result['agent_outputs']} == {'researcher', 'challenger'} and all(a['mode'] == 'mock' and a['basis'] and a['doubts'] and a['conclusion'] and a['evidence_refs'] for a in result['agent_outputs']))
        traces = done['runs'][0]['agent_runs']
        check('raw outputs and evidence durably readable', len(traces) == 2 and all(a['status'] == 'succeeded' and a['input'] and a['output'] in result['agent_outputs'] and a['duration_ms'] is not None for a in traces))
        check('retry successful task rejected', request('POST', f"/api/tasks/{task['id']}/retry", key=str(uuid4()))[0] == 409)

        failed, _ = submit('fail_once')
        failed = terminal(failed['id'])
        check('simulated failure durably recorded', failed['status'] == 'failed' and bool(failed['error']) and failed['runs'][0]['status'] == 'failed')
        retry_key = str(uuid4())
        code, retried = request('POST', f"/api/tasks/{failed['id']}/retry", key=retry_key)
        check('failed task retry accepted with same task ID', code == 202 and retried['id'] == failed['id'])
        recovered = terminal(failed['id'])
        code, replay = request('POST', f"/api/tasks/{failed['id']}/retry", key=retry_key)
        check('retry idempotent after completion', code == 202 and replay['attempt_count'] == 2)
        check('retry keeps previous attempt and succeeds', recovered['status'] == 'succeeded' and len(recovered['runs']) == 2 and recovered['attempt_count'] == 2 and recovered['runs'][0]['error'])
        evidence['tasks']['retry'] = recovered

        timeout, _ = submit('timeout')
        timeout = terminal(timeout['id'])
        check('adapter timeout recorded as failure', timeout['status'] == 'failed' and bool(timeout['error']) and any(a['status'] == 'failed' and a['error'] for a in timeout['runs'][0]['agent_runs']))
        evidence['tasks']['timeout'] = timeout

        if args.redis_outage:
            try:
                subprocess.run(['docker', 'compose', 'stop', 'redis'], cwd=ROOT, check=True, capture_output=True)
                outage_status, outage_ready = request('GET', '/readyz')
                evidence['readiness_redis_outage'] = outage_ready
                check('readiness remains available in Redis degraded mode', outage_status == 200)
                outage, _ = submit(research_question='模拟 Redis 中断验收，确认数据库任务不会丢失。')
                outage = terminal(outage['id'])
                check('database fallback completes job during Redis outage', outage['status'] == 'succeeded' and outage['attempt_count'] == 1)
                evidence['tasks']['redis_outage'] = outage
            finally:
                subprocess.run(['docker', 'compose', 'start', 'redis'], cwd=ROOT, check=True, capture_output=True)

        check('task history readable', request('GET', '/api/tasks')[0] == 200)
        if args.postgres_restart:
            # Only run this mode on the isolated project during acceptance testing.
            _, history = request('GET', '/api/tasks')
            check('no active task before database restart', not any(t['status'] in ('queued', 'running') for t in history['items']))
            try:
                subprocess.run(['docker', 'compose', 'stop', 'postgres'], cwd=ROOT, check=True, capture_output=True)
                code, unavailable = request('GET', '/readyz')
                check('database outage readiness is 503', code == 503)
                evidence['readiness_postgres_outage'] = unavailable
                code, unavailable = request('GET', f"/api/tasks/{done['id']}")
                check('database outage API error is safe', code == 503 and 'arena_local' not in json.dumps(unavailable))
            finally:
                subprocess.run(['docker', 'compose', 'start', 'postgres'], cwd=ROOT, check=True, capture_output=True)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if request('GET', '/readyz')[0] == 200:
                    break
                time.sleep(0.5)
            code, restored = request('GET', f"/api/tasks/{done['id']}")
            check('task result and traces survive PostgreSQL restart', code == 200 and restored == done)
            code, replay = request('POST', '/api/tasks', payload, key)
            check('idempotency survives PostgreSQL restart', code == 202 and replay['id'] == done['id'] and replay['attempt_count'] == 1)
            evidence['postgres_restart_preserved_task_id'] = done['id']
        evidence['passed'] = True
    except Exception as error:
        evidence['passed'] = False
        evidence['failure'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        evidence['finished_at'] = datetime.now(timezone.utc).isoformat()
        (ROOT / 'artifacts').mkdir(exist_ok=True)
        (ROOT / 'artifacts' / 'runtime-verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
