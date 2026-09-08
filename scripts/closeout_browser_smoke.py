#!/usr/bin/env python3
"""Small real-browser release smoke for an isolated Visembler instance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--only', type=int, default=-1, help='run one zero-based viewport case')
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    report = {'checks': [], 'console_errors': [], 'page_errors': [], 'request_errors': []}
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        cases=[(1440,900,'light'),(1024,768,'dark'),(768,900,'light'),(480,820,'dark'),(390,844,'light'),(360,740,'light')]
        if args.only >= 0: cases=[cases[args.only]]
        for width, height, theme in cases:
            page = browser.new_page(viewport={'width':width,'height':height})
            page.on('console', lambda message: report['console_errors'].append(message.text) if message.type == 'error' else None)
            page.on('pageerror', lambda error: report['page_errors'].append(str(error)))
            page.on('requestfailed', lambda request: report['request_errors'].append(request.url))
            page.goto(args.url, wait_until='domcontentloaded'); page.locator('.cui-visualizer-root[data-editor-ready="true"]').wait_for(timeout=15_000)
            page.evaluate("theme=>document.documentElement.setAttribute('data-theme',theme)", theme)
            root = page.locator('.cui-visualizer-root'); box = root.bounding_box()
            assert box and box['width'] > 0
            assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')
            for selector in ('#libraryToggle','#inspectorToggle'):
                control = page.locator(selector)
                if control.get_attribute('aria-pressed') == 'true': control.click()
                control.click(); control.click()
            page.locator('#zoomFit').click()
            page.screenshot(path=str(args.output / f'{width}x{height}-{theme}.png'))
            report['checks'].append({'viewport':[width,height], 'theme':theme, 'status':'PASS'})
            page.close()
        browser.close()
    report['status'] = 'PASS' if not report['console_errors'] and not report['page_errors'] and not report['request_errors'] else 'FAIL'
    (args.output / 'browser-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
