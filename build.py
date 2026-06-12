#!/usr/bin/env python3
import json, re

d = json.load(open('data.json'))

risk_by_code = {r['code']: r for r in d['risks']}
active = [r for r in d['risks'] if r['status'] == 'active']

# redirect map for retired codes -> active replacement codes
redirect = {}
for r in d['risks']:
    if r['status'] == 'replaced':
        repl = []
        for rid in r.get('replacedBy', []):
            t = next((x for x in d['risks'] if x['id'] == rid), None)
            if t: repl.append(t['code'])
        redirect[r['code']] = repl
    elif r['status'] == 'removed':
        redirect[r['code']] = []

def resolve(codes):
    out = []
    for c in codes:
        if c in redirect:
            out += redirect[c]
        else:
            out.append(c)
    seen, res = set(), []
    for c in out:
        if c not in seen and c in risk_by_code and risk_by_code[c]['status'] == 'active':
            seen.add(c); res.append(c)
    return sorted(res)

for m in d['mitigations']:
    m['risks'] = resolve(m['risks'])
for g in d['mitGroups']:
    g['risks'] = resolve(g['risks'])
for c in d['controls']:
    c['risks'] = resolve(c['risks'])
for g in d['ctlGroups']:
    g['risks'] = resolve(g.get('risks', []))

# reverse links
for r in d['risks']:
    r['mits'] = []
    r['ctls'] = []
    r['groupMits'] = []
for m in d['mitigations']:
    for c in m['risks']:
        risk_by_code[c]['mits'].append(m['id'])
for g in d['mitGroups']:
    for c in g['risks']:
        risk_by_code[c]['groupMits'].append(g['id'])
for c in d['controls']:
    for code in c['risks']:
        risk_by_code[code]['ctls'].append(c['id'])

d['foundationalMits'] = [m['id'] for m in d['mitigations'] if m.get('all')]
d['foundationalCtls'] = [c['id'] for c in d['controls'] if c.get('all')]

# related controls for each mitigation (risk overlap)
ctl_by_id = {c['id']: c for c in d['controls']}
for m in d['mitigations']:
    rs = set(m['risks'])
    scored = []
    for c in d['controls']:
        ov = len(rs & set(c['risks']))
        if ov: scored.append((ov, c['id']))
    scored.sort(key=lambda x: (-x[0], x[1]))
    m['relatedCtls'] = [cid for _, cid in scored[:6]]
    # related mits for each control
for c in d['controls']:
    rs = set(c['risks'])
    scored = []
    for m in d['mitigations']:
        ov = len(rs & set(m['risks']))
        if ov: scored.append((ov, m['id']))
    scored.sort(key=lambda x: (-x[0], x[1]))
    c['relatedMits'] = [mid for _, mid in scored[:6]]

# stats
d['stats'] = {
    'categories': len(d['categories']),
    'activeRisks': len(active),
    'mitigations': len(d['mitigations']),
    'controls': len(d['controls']),
    'reqs': sum(len(c['reqs']) for c in d['controls']),
    'frameworks': 3,
}

import shutil, os
tpl = open('template.html', encoding='utf-8').read()
payload = json.dumps(d, separators=(',', ':')).replace('</', '<\\/')
out = tpl.replace('"__DATA__"', payload)
open('dist/valos-explorer.html', 'w', encoding='utf-8').write(out)
shutil.copy('favicon.ico', 'dist/favicon.ico')
print('written', len(out), 'bytes')
