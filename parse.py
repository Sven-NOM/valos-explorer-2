#!/usr/bin/env python3
import re, json, html

src = open("spec/valos-spec.html", encoding="utf-8").read()
lines = src.split('\n')

# ---------- helpers ----------
def clean_text(t):
    # [[[?REF]]] -> REF ; [[?REF]] -> REF ; [[[REF]]] -> REF
    t = re.sub(r'\[\[\[\??([A-Za-z0-9_]+)\]\]\]', r'\1', t)
    t = re.sub(r'\[\[\??([A-Za-z0-9_]+)\]\]', r'\1', t)
    # markdown links [text](url) -> text
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)
    # respec defs [=x=], <dfn>, <abbr> etc
    t = re.sub(r'\[=([^=]+)=\]', r'\1', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = html.unescape(t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def heading(line):
    m = re.match(r'^(#{2,5})\s+(.*?)\s*(?:\{#([a-zA-Z0-9_-]+)\})?\s*$', line)
    if m:
        return len(m.group(1)), m.group(2).strip(), m.group(3)
    return None

RISK_LINK = re.compile(r'\[([A-Z]{3}\d+)\]\(#risk-[a-z]+-\d+\)')
EXT_REF = re.compile(r'\[\[\?([A-Za-z0-9_]+)\]\]\s*([^\n<*]*)')

def parse_info_block(text):
    """Return (risk_codes, all_flag, externals[]) from an info-div-ish text."""
    risks = RISK_LINK.findall(text)
    allflag = bool(re.search(r'all risks', text, re.I))
    externals = []
    for m in EXT_REF.finditer(text):
        fw, ref = m.group(1), m.group(2).strip().rstrip(':').strip()
        externals.append({'fw': fw, 'ref': ref})
    return risks, allflag, externals

# ---------- locate top-level sections ----------
def find_line(pred):
    for i, l in enumerate(lines):
        if pred(l): return i
    return -1

i_risks = find_line(lambda l: l.startswith('## Risks {#sec-risks}'))
i_mit   = find_line(lambda l: l.startswith('## Risk Mitigation Strategies'))
i_ctl   = find_line(lambda l: l.startswith('## Controls Catalog'))
i_app   = find_line(lambda l: l.startswith('<section id="sec-sotd"'))

# ---------- 1. risks ----------
categories = []
risks = []
cur_cat = None
i = i_risks
risks_intro_lines = []
while i < i_mit:
    l = lines[i]
    h = heading(l)
    if h and h[0] == 3:
        cur_cat = {'id': h[2], 'name': h[1], 'intro': [], 'code': None}
        categories.append(cur_cat)
        i += 1; continue
    if cur_cat and '<table>' not in l and '<tr' not in l and not l.startswith('<'):
        if l.strip() and not l.strip().startswith('|'):
            cur_cat['intro'].append(l.strip())
    if l.strip().startswith('<tr id="risk-'):
        rid = re.search(r'id="(risk-[a-z]+-\d+)"', l).group(1)
        # gather until </tr>
        block = []
        j = i
        while ('</tr>' not in lines[j] and '</tbody>' not in lines[j]
               and '</table>' not in lines[j]):
            block.append(lines[j]); j += 1
        block.append(lines[j])
        blob = '\n'.join(block)
        tds = re.findall(r'<td[^>]*>(.*?)</td>', blob, re.S)
        code_raw = clean_text(tds[0]) if tds else rid
        code = code_raw.split()[0].split('(')[0]
        replaces = re.findall(r'[A-Z]{3}\d+', code_raw[len(code):])
        if 'colspan' in blob:
            rest = clean_text(tds[1]) if len(tds) > 1 else ''
            status = 'removed' if 'Removed' in rest else 'replaced'
            repl = re.findall(r'href="#(risk-[a-z]+-\d+)"', blob)
            risks.append({'id': rid, 'code': code, 'cat': cur_cat['id'], 'status': status,
                          'replacedBy': repl, 'group': '', 'vector': '', 'desc': rest})
        else:
            risks.append({'id': rid, 'code': code, 'cat': cur_cat['id'], 'status': 'active',
                          'replaces': replaces,
                          'group': clean_text(tds[1]), 'vector': clean_text(tds[2]),
                          'desc': clean_text(tds[3]) if len(tds)>3 else ''})
        if cur_cat['code'] is None:
            cur_cat['code'] = re.match(r'[A-Z]+', code).group(0)
        i = j + 1; continue
    if cur_cat is None and l.strip() and not l.startswith('##'):
        risks_intro_lines.append(l.strip())
    i += 1

for c in categories:
    c['intro'] = clean_text(' '.join(c['intro']))

# ---------- 2 & 3. generic section walker for mitigations and controls ----------
def walk(start, end):
    """Yield events: ('h3', name, id, body) blocks split at h3/h4 honoring info divs."""
    blocks = []  # list of dicts {level, name, id, lines}
    cur = None
    depth_info = 0
    i = start + 1
    # capture intro of the ## section
    top_intro = {'level': 2, 'name': None, 'id': None, 'lines': []}
    cur = top_intro
    blocks.append(cur)
    while i < end:
        l = lines[i]
        opens = l.count('<div class="info"') + l.count('<details')
        closes = l.count('</div>') + l.count('</details>')
        h = heading(l)
        if h and h[0] in (3, 4) and depth_info == 0:
            cur = {'level': h[0], 'name': h[1], 'id': h[2], 'lines': []}
            blocks.append(cur)
        else:
            cur['lines'].append(l)
        depth_info += opens - closes
        if depth_info < 0: depth_info = 0
        i += 1
    return blocks

def extract_tools(text):
    tools = []
    for m in re.finditer(r'<details class="tools">(.*?)</details>', text, re.S):
        for t in re.finditer(r'<a href="([^"]+)">([^<]+)</a>', m.group(1)):
            tools.append({'url': t.group(1), 'name': t.group(2)})
    return tools

def extract_infos(text):
    out = []
    for m in re.finditer(r'<div class="info">(.*?)</div>', text, re.S):
        out.append(m.group(1))
    return out

def body_paragraphs(text):
    # remove details and info divs, then clean remaining prose
    text = re.sub(r'<details class="tools">.*?</details>', '', text, flags=re.S)
    text = re.sub(r'<div class="info">.*?</div>', '', text, flags=re.S)
    paras = []
    bullets = []
    cur_bullet_head = None
    for raw in text.split('\n'):
        s = raw.strip()
        if not s: 
            paras.append('') ; continue
        if s.startswith('#####'):
            cur_bullet_head = clean_text(s.lstrip('#').strip())
            paras.append('@@H:' + cur_bullet_head)
            continue
        if s.startswith(('*', '-')) and not s.startswith('---'):
            paras.append('@@B:' + clean_text(s[1:].strip()))
            continue
        paras.append(clean_text(s))
    # merge consecutive prose lines into paragraphs
    out = []
    buf = []
    for p in paras:
        if p == '':
            if buf: out.append({'t': 'p', 'x': ' '.join(buf)}); buf = []
        elif p.startswith('@@H:'):
            if buf: out.append({'t': 'p', 'x': ' '.join(buf)}); buf = []
            out.append({'t': 'h', 'x': p[4:]})
        elif p.startswith('@@B:'):
            if buf: out.append({'t': 'p', 'x': ' '.join(buf)}); buf = []
            out.append({'t': 'b', 'x': p[4:]})
        else:
            buf.append(p)
    if buf: out.append({'t': 'p', 'x': ' '.join(buf)})
    return [o for o in out if o['x']]

# ---- mitigations ----
mit_groups = []
mitigations = []
blocks = walk(i_mit, i_ctl)
mit_top_intro = clean_text(' '.join([l for l in blocks[0]['lines'] if l.strip() and not l.startswith('#')]))
gcur = None
for b in blocks[1:]:
    text = '\n'.join(b['lines'])
    infos = extract_infos(text)
    rks, allf, ext = set(), False, []
    for inf in infos:
        r, a, e = parse_info_block(inf)
        rks.update(r); allf = allf or a; ext += e
    if b['level'] == 3:
        gcur = {'id': b['id'], 'name': b['name'],
                'intro': body_paragraphs(text),
                'risks': sorted(rks), 'all': allf,
                'tools': extract_tools(text)}
        mit_groups.append(gcur)
    else:
        mitigations.append({'id': b['id'] or ('mit-' + re.sub(r'[^a-z0-9]+', '-', b['name'].lower())),
                            'name': b['name'], 'group': gcur['id'],
                            'body': body_paragraphs(text),
                            'tools': extract_tools(text),
                            'risks': sorted(rks), 'all': allf})

# ---- controls ----
ctl_groups = []
controls = []
blocks = walk(i_ctl, i_app)
ctl_top_intro = clean_text(' '.join([l for l in blocks[0]['lines'] if l.strip() and not l.startswith('#')]))
gcur = None
pending_group_ext = []
for b in blocks[1:]:
    text = '\n'.join(b['lines'])
    infos = extract_infos(text)
    rks, allf, ext = set(), False, []
    for inf in infos:
        r, a, e = parse_info_block(inf)
        rks.update(r); allf = allf or a; ext += e
    # also catch external refs and risk links outside divs (defensive)
    if not infos:
        r, a, e = parse_info_block(text)
        rks.update(r); allf = allf or a; ext += e
    reqs = [{'id': m.group(1), 'text': clean_text(m.group(2)),
             'level': ('MUST NOT' if 'MUST NOT' in m.group(2) else
                       'MUST' if 'MUST' in m.group(2) else
                       'SHOULD' if 'SHOULD' in m.group(2) else
                       'MAY' if 'MAY' in m.group(2) else 'REQ')}
            for m in re.finditer(r'<b id="(req-[a-z0-9-]+)">(.*?)</b>', text, re.S)]
    if b['level'] == 3:
        gcur = {'id': b['id'], 'name': b['name'], 'externals': ext, 'risks': sorted(rks)}
        ctl_groups.append(gcur)
    else:
        # strip req <b> lines and 🔗 anchors from body
        btext = re.sub(r'<a href="#req-[a-z0-9-]+">🔗</a>\s*<b id="req-[a-z0-9-]+">.*?</b>', '', text, flags=re.S)
        body = body_paragraphs(btext)
        if not reqs:
            # info-only stray h4 -> merge into previous control
            if controls:
                controls[-1]['risks'] = sorted(set(controls[-1]['risks']) | rks)
                controls[-1]['all'] = controls[-1]['all'] or allf
                controls[-1]['externals'] += ext
            continue
        controls.append({'id': reqs[0]['id'], 'name': b['name'], 'group': gcur['id'],
                         'reqs': reqs, 'body': body, 'externals': ext,
                         'risks': sorted(rks), 'all': allf})

data = {
    'meta': {'title': 'ValOS — Validator Operations Standard',
             'org': 'Lido Labs Foundation', 'license': 'Apache 2',
             'mitIntro': mit_top_intro, 'ctlIntro': ctl_top_intro},
    'categories': categories,
    'risks': risks,
    'mitGroups': mit_groups,
    'mitigations': mitigations,
    'ctlGroups': ctl_groups,
    'controls': controls,
}

json.dump(data, open('data.json', 'w'), indent=1)

active = [r for r in risks if r['status'] == 'active']
print('categories', len(categories), [c['code'] for c in categories])
print('risks', len(risks), 'active', len(active))
print('mit groups', len(mit_groups), 'mitigations', len(mitigations))
print('ctl groups', len(ctl_groups), 'controls', len(controls),
      'reqs', sum(len(c['reqs']) for c in controls))
# sanity: risks referenced that don't exist
known = {r['code'] for r in risks}
refd = set()
for m in mitigations: refd.update(m['risks'])
for c in controls: refd.update(c['risks'])
print('unknown refs:', sorted(refd - known))
print('retired refs used:', sorted(refd & {r['code'] for r in risks if r['status'] != 'active'}))
