from playwright.sync_api import sync_playwright
import json

import os
URL = 'file://' + os.path.abspath('dist/valos-explorer.html')
errs = []

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errs.append('PAGEERROR: ' + str(e)))

    pg.goto(URL); pg.wait_for_timeout(400)
    pg.screenshot(path='tests/shot-overview.png', full_page=True)

    # fabric hover + legend filter
    pg.hover('.fcell >> nth=3'); pg.wait_for_timeout(100)
    pg.click('#flegend button >> nth=1'); pg.wait_for_timeout(100)

    for h, name in [('#/risks', 'risks'), ('#/risks/SLS1', 'risk-detail'),
                    ('#/mitigations', 'mitigations'),
                    ('#/mitigations/sec-mit-antislash-db', 'mit-detail'),
                    ('#/controls', 'controls'), ('#/planner', 'planner')]:
        pg.evaluate(f"location.hash='{h}'"); pg.wait_for_timeout(350)
        pg.screenshot(path=f'tests/shot-{name}.png', full_page=(name != 'controls'))

    # controls interactions: set a status, type a note
    pg.evaluate("location.hash='#/controls'"); pg.wait_for_timeout(300)
    pg.select_option('[data-req] >> nth=0', 'pass')
    pg.select_option('[data-req] >> nth=1', 'partial')
    pg.fill('[data-note] >> nth=0', 'See runbook RB-12')
    pg.wait_for_timeout(150)
    pg.screenshot(path='tests/shot-controls-assessed.png')

    # search risks
    pg.evaluate("location.hash='#/risks'"); pg.wait_for_timeout(300)
    pg.fill('#rq', 'double'); pg.wait_for_timeout(250)
    n = pg.locator('.riskrow').count()
    print('risk search "double" rows:', n)
    pg.screenshot(path='tests/shot-risk-search.png')

    # planner: change status, check coverage updates, seed
    pg.evaluate("location.hash='#/planner'"); pg.wait_for_timeout(300)
    pg.select_option('select[data-p=status] >> nth=0', 'done'); pg.wait_for_timeout(250)
    cov = pg.locator('.covercard .mono').inner_text()
    print('coverage after 1 done:', cov)
    pg.click('#seed'); pg.wait_for_timeout(250)
    cov2 = pg.locator('.covercard .mono').inner_text()
    print('coverage after seed:', cov2)
    pg.screenshot(path='tests/shot-planner-active.png', full_page=False)

    # mobile
    pg2 = b.new_page(viewport={'width': 390, 'height': 800})
    pg2.on('pageerror', lambda e: errs.append('MOBILE PAGEERROR: ' + str(e)))
    pg2.goto(URL); pg2.wait_for_timeout(300)
    pg2.screenshot(path='tests/shot-mobile-overview.png', full_page=True)
    pg2.evaluate("location.hash='#/risks/SLS1'"); pg2.wait_for_timeout(300)
    pg2.screenshot(path='tests/shot-mobile-risk.png', full_page=True)
    pg2.evaluate("location.hash='#/controls'"); pg2.wait_for_timeout(300)
    pg2.screenshot(path='tests/shot-mobile-controls.png')

    b.close()

print('console errors:', json.dumps(errs, indent=1) if errs else 'none')
