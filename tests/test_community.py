from playwright.sync_api import sync_playwright
import json

import os
URL = 'file://' + os.path.abspath('dist/valos-explorer.html')
errs = []

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1280, 'height': 950})
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and '403' not in m.text else None)
    pg.on('pageerror', lambda e: errs.append('PAGEERROR: ' + str(e)))

    pg.goto(URL); pg.wait_for_timeout(400)
    pg.evaluate("location.hash='#/community'"); pg.wait_for_timeout(500)
    pg.screenshot(path='tests/c-dashboard.png', full_page=True)

    # profile save
    pg.fill('#pf-handle', 'testuser')
    pg.select_option('#pf-role', 'Solo home staker')
    pg.select_option('#pf-scale', '1–5 validators')
    pg.select_option('#pf-infra', 'Home bare metal')
    pg.select_option('#pf-custody', 'Local keystores')
    pg.click('#pf-save'); pg.wait_for_timeout(300)
    print('profile saved:', pg.evaluate("ws.community.profile.handle"))

    # rate flow
    pg.evaluate("location.hash='#/community/rate:SLS1'"); pg.wait_for_timeout(400)
    pg.screenshot(path='tests/c-rate.png', full_page=True)
    for d in ['freq', 'fin', 'net', 'det']:
        pg.check(f"input[name=\"rate-{d}\"][value=\"3\"]", force=True)
    pg.click('#saverate'); pg.wait_for_timeout(300)
    pg.screenshot(path='tests/c-rate-result.png', full_page=True)
    print('my estimates:', pg.evaluate("myClaims().filter(c=>c.type==='estimate').length"))

    # pairwise
    pg.evaluate("location.hash='#/community/pair'"); pg.wait_for_timeout(400)
    pg.screenshot(path='tests/c-pair.png')
    pg.click('.paircard >> nth=0'); pg.wait_for_timeout(200)
    print('pair result shown:', pg.locator('#pairresult .card').count())
    pg.wait_for_timeout(800)  # auto-advance

    # incident
    pg.evaluate("location.hash='#/community/incident:DOW4'"); pg.wait_for_timeout(400)
    pg.fill('#inc-text', 'Power outage during storm, 6h offline, added UPS and LTE failover afterwards.')
    pg.fill('#inc-setup', 'home staker, 2 validators')
    pg.click('#inc-save'); pg.wait_for_timeout(400)
    print('after incident, hash:', pg.evaluate("location.hash"))
    pg.screenshot(path='tests/c-riskpage-community.png', full_page=True)

    # new risk submit with similarity
    pg.evaluate("location.hash='#/community/submit'"); pg.wait_for_timeout(400)
    pg.fill('#nr-vector', 'Validator signs two different blocks because anti-slashing database deleted')
    pg.wait_for_timeout(200)
    sim = pg.locator('#nr-sim .simwarn').count()
    print('similarity warning fired:', sim)
    pg.screenshot(path='tests/c-submit-sim.png', full_page=True)
    pg.fill('#nr-vector', 'Expired cloud spending budget auto-suspends VM hosting the beacon node')
    pg.fill('#nr-desc', 'Cloud accounts with budget caps or expired payment methods silently suspend instances; the beacon node disappears without any infra alert because the provider considers it intentional, leading to missed duties until a human checks billing.')
    pg.click('#nr-save'); pg.wait_for_timeout(400)
    print('draft hash:', pg.evaluate("location.hash"))
    pg.screenshot(path='tests/c-draft-detail.png', full_page=True)

    # queue + vote
    pg.evaluate("location.hash='#/community/queue'"); pg.wait_for_timeout(400)
    pg.locator('[data-cr="CR-1"] [data-vote="confirm"]').click(); pg.wait_for_timeout(300)
    print('CR-1 confirms now:', pg.evaluate("crVotes('CR-1').confirms.length"))
    pg.screenshot(path='tests/c-queue.png', full_page=True)

    # drafts overlay in register
    pg.evaluate("location.hash='#/risks'"); pg.wait_for_timeout(300)
    pg.check('#draftsw'); pg.wait_for_timeout(300)
    print('draft rows in register:', pg.locator('.draftrow').count())
    pg.screenshot(path='tests/c-register-drafts.png', full_page=True)

    # seed toggle off → aggregates shrink
    pg.evaluate("location.hash='#/community'"); pg.wait_for_timeout(300)
    pg.uncheck('#seedtoggle'); pg.wait_for_timeout(400)
    print('claims visible w/o seed:', pg.evaluate("allClaims().length"), 'mine:', pg.evaluate("myClaims().length"))
    pg.screenshot(path='tests/c-dashboard-noseed.png', full_page=True)
    pg.check('#seedtoggle'); pg.wait_for_timeout(200)

    # persistence across reload (localStorage in real browser)
    pg.reload(); pg.wait_for_timeout(500)
    print('claims after reload:', pg.evaluate("myClaims().length"),
          'profile:', pg.evaluate("ws.community.profile && ws.community.profile.handle"))

    # mobile
    m = b.new_page(viewport={'width': 390, 'height': 800})
    m.on('pageerror', lambda e: errs.append('MOBILE: ' + str(e)))
    m.goto(URL + '#/community'); m.wait_for_timeout(400)
    m.screenshot(path='tests/c-mobile.png', full_page=True)
    m.goto(URL + '#/community/rate:DOW2'); m.wait_for_timeout(400)
    m.screenshot(path='tests/c-mobile-rate.png')
    b.close()

print('errors:', json.dumps(errs, indent=1) if errs else 'none')
