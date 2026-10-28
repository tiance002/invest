"""Real browser acceptance; the API, worker and dependencies must already run."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:5173')
    parser.add_argument('--browser-channel', default=None, help='Use msedge for installed Edge, or omit for Playwright Chromium')
    parser.add_argument('--inspect-only', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    evidence: dict = {'started_at': datetime.now(timezone.utc).isoformat(), 'checks': [], 'tasks': {}}
    page_errors: list[str] = []
    console_errors: list[str] = []

    def check(name: str, condition: bool):
        assert condition, name
        evidence['checks'].append({'name': name, 'passed': True})
        print(f'PASS {name}', flush=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=args.browser_channel, headless=True)
        evidence['browser_version'] = browser.version
        context = browser.new_context(viewport={'width': 1440, 'height': 1040}, locale='zh-CN', timezone_id='Asia/Shanghai', reduced_motion='reduce')
        page = context.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
        try:
            page.goto(args.url)
            page.wait_for_load_state('networkidle')
            # Inspect the rendered UI before exercising the known semantic controls.
            evidence['initial_controls'] = {
                'buttons': page.get_by_role('button').all_text_contents(),
                'field_ids': page.locator('input,select,textarea').evaluate_all('(items) => items.map(item => item.id)'),
            }
            (OUT / 'demo-initial-dom.html').write_text(page.content(), encoding='utf-8')
            page.screenshot(path=str(OUT / 'demo-initial.png'), full_page=True)
            if args.inspect_only:
                print(json.dumps(evidence['initial_controls'], ensure_ascii=False))
                return

            def submit(scenario: str, question: str):
                page.get_by_role('button', name='新任务', exact=True).click()
                page.locator('#market').select_option('CN_A')
                page.locator('#symbol').fill('600519')
                page.locator('#horizon').fill('3')
                page.locator('#question').fill(question)
                page.locator('#scenario').select_option(scenario)
                with page.expect_response(lambda response: response.url.endswith('/api/tasks') and response.request.method == 'POST') as capture:
                    page.get_by_role('button', name='开始模拟研究', exact=True).click()
                response = capture.value
                assert response.status == 202
                task = response.json()
                expect(page.locator('#task-select')).to_have_value(task['id'])
                return task

            def get_task(task_id: str):
                response = page.request.get(f'{args.url}/api/tasks/{task_id}')
                assert response.status == 200
                return response.json()

            normal = submit('normal', '浏览器演示：哪些模拟证据支持论点，反方会如何质疑？')
            expect(page.locator('.status-badge.succeeded')).to_be_visible(timeout=45000)
            expect(page.get_by_role('heading', name='研究员', exact=True)).to_be_visible()
            expect(page.get_by_role('heading', name='反方质询', exact=True)).to_be_visible()
            check('browser submission completes real worker workflow', get_task(normal['id'])['status'] == 'succeeded')
            check('mock labels visible', page.get_by_text('模拟数据', exact=True).count() >= 1)
            page.screenshot(path=str(OUT / 'demo-result.png'), full_page=True)

            page.get_by_role('tab', name=re.compile('执行轨迹')).click()
            expect(page.locator('.agent-record')).to_have_count(2)
            page.locator('.agent-record summary').first.click()
            expect(page.locator('.agent-record-body').first).to_contain_text('mock-evidence-v1')
            page.screenshot(path=str(OUT / 'demo-trace.png'), full_page=True)
            check('agent input output and evidence inspectable', page.locator('.agent-record-body pre').count() >= 2)

            page.reload()
            page.wait_for_load_state('networkidle')
            expect(page.locator('#task-select')).to_have_value(normal['id'])
            expect(page.locator('.status-badge.succeeded')).to_be_visible()
            check('task selection survives page reload', normal['id'] in page.locator('.task-meta').inner_text())
            with page.expect_response(lambda response: response.url.endswith('/api/tasks') and response.request.method == 'POST') as replay:
                page.get_by_role('button', name='开始模拟研究', exact=True).click()
            check('browser duplicate submit reuses durable task', replay.value.json()['id'] == normal['id'])
            evidence['tasks']['normal'] = get_task(normal['id'])

            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path=str(OUT / 'demo-mobile.png'), full_page=True)
            check('mobile viewport has no horizontal overflow', page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
            page.set_viewport_size({'width': 1440, 'height': 1040})

            failed = submit('fail_once', '浏览器演示：首次模拟失败后，在同一任务中重试并保留历史。')
            expect(page.locator('.status-badge.failed')).to_be_visible(timeout=45000)
            page.screenshot(path=str(OUT / 'demo-failure.png'), full_page=True)
            with page.expect_response(lambda response: response.url.endswith(f"/api/tasks/{failed['id']}/retry") and response.request.method == 'POST') as retried:
                page.get_by_role('button', name='重试此任务', exact=True).click()
            check('browser retry retains task identity', retried.value.status == 202 and retried.value.json()['id'] == failed['id'])
            expect(page.locator('.status-badge.succeeded')).to_be_visible(timeout=45000)
            page.get_by_role('tab', name=re.compile('执行轨迹')).click()
            expect(page.locator('.run-record')).to_have_count(2)
            page.screenshot(path=str(OUT / 'demo-retry.png'), full_page=True)
            recovered = get_task(failed['id'])
            check('failed and successful attempts both remain visible', recovered['attempt_count'] == 2 and recovered['runs'][0]['status'] == 'failed' and recovered['runs'][1]['status'] == 'succeeded')
            evidence['tasks']['retry'] = recovered

            timeout = submit('timeout', '浏览器演示：模拟模型超时，核对结构化错误与部分输出。')
            expect(page.locator('.status-badge.failed')).to_be_visible(timeout=45000)
            timeout = get_task(timeout['id'])
            check('timeout visible with persisted error', bool(timeout['error']) and timeout['result'] is None)
            evidence['tasks']['timeout'] = timeout
            page.screenshot(path=str(OUT / 'demo-timeout.png'), full_page=True)

            # Leave the recorded demo context on the successful normal research result.
            page.locator('#task-select').select_option(normal['id'])
            expect(page.locator('.status-badge.succeeded')).to_be_visible()
            check('no uncaught browser errors', not page_errors)
            check('no browser console errors', not console_errors)
            evidence['passed'] = True
        except Exception as error:
            evidence['passed'] = False
            evidence['failure'] = f'{type(error).__name__}: {error}'
            page.screenshot(path=str(OUT / 'demo-error.png'), full_page=True)
            raise
        finally:
            evidence['page_errors'] = page_errors
            evidence['console_errors'] = console_errors
            evidence['finished_at'] = datetime.now(timezone.utc).isoformat()
            (OUT / ('browser-inspection.json' if args.inspect_only else 'browser-verification.json')).write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
            context.close()
            browser.close()


if __name__ == '__main__':
    main()
