#!/usr/bin/env python3
"""Build data/match-questions.json from the reviewed question drafts in .frugal-fable/match/out/*.json.

Each contest is keyed by the sorted set of its candidates' name slugs, so the app finds the same
bank whether the race comes from the state seed or a county file. Every candidate mapping is
re-checked here against the live data: the cited statement must exist and the quote must be a
verbatim substring of it. Anything that fails is dropped and reported, never shipped.
Optional wording fixes live in .frugal-fable/match/fixes.json: [{"contest","id","q_en","q_es","t_en","t_es"}] (null = keep).
Optional review drops live in .frugal-fable/match/drops.json: [{"contest": "<substring of header>",
"id": "<question id>", "slug": "<candidate slug or omit to drop the whole question>", "why": "..."}].
"""
import glob, json, os, re, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, '.frugal-fable', 'match', 'out')
TOPICS = set('housing cost health taxes energy safety homeless emerg education streets water roads growth community immigration economy environment abortion guns crime jobs agriculture veterans elections budget finance childcare other'.split())
slug = lambda s: re.sub(r'[^a-z]', '', (s or '').lower())
en = lambda x: x.get('en', '') if isinstance(x, dict) else (x or '')

def races():
    d = json.load(open(os.path.join(ROOT, 'data', 'ballot-2026.json')))
    for k, v in d['races'].items():
        for kk, r in (v or {}).items():
            if isinstance(r, dict) and r.get('candidates'): yield f'{k}/{kk}', r
            elif isinstance(r, list):
                for c in r:
                    if isinstance(c, dict) and c.get('candidates'): yield f'{k}/{kk}/{c.get("id")}', c
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'local', '*.json'))):
        for c in json.load(open(f)).get('contests', []):
            if c.get('candidates'): yield f'{os.path.basename(f)}/{c.get("id")}', c

by_sig = {}
for key, r in races():
    cands = {slug(c.get('name')): [en(p.get('statement')) for p in (c.get('positions') or [])] for c in r['candidates']}
    sig = '|'.join(sorted(cands))
    e = by_sig.setdefault(sig, {'office': '', 'cands': cands, 'keys': []})
    e['keys'].append(key)
    if not e['office'] and en(r.get('office')): e['office'] = en(r.get('office'))
for e in by_sig.values():
    if not e['office']: e['office'] = e['keys'][0]

# header line -> sig, written by the batching step
HEADER_SIG = {}
ip = os.path.join(ROOT, '.frugal-fable', 'match', 'in', 'index.json')
if os.path.exists(ip):
    for sig_, v in json.load(open(ip)).items():
        for h in v.get('keys', []): HEADER_SIG[h.strip()] = sig_
drops = []
dp = os.path.join(ROOT, '.frugal-fable', 'match', 'drops.json')
if os.path.exists(dp): drops = json.load(open(dp))
def dropped(header, qid, s=None):
    for d in drops:
        if (d['contest'] in header or d['contest'] in CUR_SIG[0]) and d['id'] == qid and (d.get('slug') in (None, '', s) if s else not d.get('slug')): d['_used'] = True; return d
    return None

fixes = []
fp = os.path.join(ROOT, '.frugal-fable', 'match', 'fixes.json')
if os.path.exists(fp): fixes = json.load(open(fp))
def fix(header, q):
    for f in fixes:
        if (f['contest'] in header or f['contest'] in CUR_SIG[0]) and f['id'] == q.get('id'):
            if f.get('q_en'): q['q']['en'] = f['q_en']
            if f.get('q_es'): q['q']['es'] = f['q_es']
            if f.get('t_en') or f.get('t_es'):
                q['tradeoff'] = q.get('tradeoff') or {}
                if f.get('t_en'): q['tradeoff']['en'] = f['t_en']
                if f.get('t_es'): q['tradeoff']['es'] = f['t_es']
            f['_used'] = True
CUR_SIG = ['']   # sig of the contest being merged; drop/fix "contest" may name a header fragment or a candidate slug
problems, contests, nq, nm, ndrop = [], [], 0, 0, 0
for f in sorted(glob.glob(os.path.join(OUT_DIR, 'batch-*.json'))):
    for c in json.load(open(f)).get('contests', []):
        header = c.get('contest', '')
        sig = HEADER_SIG.get(header.strip())
        if not sig:   # fall back to the contest id or seed key named in the header
            m = re.search(r'\| id=(.+?) \| status', header) or re.search(r'\| id=(\S+)', header)
            hk = header[3:].split(' | ')[0].strip()
            for s_, e in by_sig.items():
                if any(k == hk or (m and k.endswith('/' + m.group(1))) for k in e['keys']): sig = s_; break
        if not sig: problems.append(f'contest not found: {header[:90]}'); continue
        e = by_sig[sig]; qs = []; CUR_SIG[0] = sig
        for q in c.get('questions', []):
            qid = q.get('id'); d = dropped(header, qid)
            if d: ndrop += 1; continue
            if not qid or not isinstance(q.get('q'), dict) or not q['q'].get('en'): problems.append(f'{header[:60]}: bad question {qid}'); continue
            fix(header, q)
            if q.get('topic') not in TOPICS: q['topic'] = 'other'
            if len(q['q']['en']) > 120: problems.append(f'{header[:60]}/{qid}: q.en too long ({len(q["q"]["en"])})')
            sides = {}
            for s, sd in (q.get('sides') or {}).items():
                if dropped(header, qid, s): ndrop += 1; continue
                if s not in e['cands']: problems.append(f'{header[:60]}/{qid}: unknown candidate {s}'); continue
                try: idx = int(sd.get('idx')); stmt = e['cands'][s][idx]
                except Exception: problems.append(f'{header[:60]}/{qid}/{s}: bad idx {sd.get("idx")}'); continue
                quote = (sd.get('quote') or '').strip()
                if not quote or quote not in stmt: problems.append(f'{header[:60]}/{qid}/{s}: quote not in statement'); continue
                if sd.get('side') not in (1, -1): problems.append(f'{header[:60]}/{qid}/{s}: bad side'); continue
                sides[s] = {'side': sd['side'], 'idx': idx, 'quote': quote[:140]}
            if not sides: continue
            qs.append({'id': qid, 'topic': q['topic'], 'q': q['q'], 'tradeoff': q.get('tradeoff') or None, 'sides': sides}); nm += len(sides)
        if qs:
            contests.append({'sig': sig, 'office': e['office'], 'questions': qs}); nq += len(qs)

out = {'generated': datetime.date.today().isoformat(), 'note': 'Curated voter-match questions. Each candidate is mapped only where a documented statement (cited by index and verbatim quote) supports that side; unmapped candidates are not scored on that question.', 'contests': contests}
json.dump(out, open(os.path.join(ROOT, 'data', 'match-questions.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print(f'{len(contests)} contests, {nq} questions, {nm} mappings written; {ndrop} review drops applied; {len(problems)} problems')
for p in problems: print('  !', p)
for f in fixes:
    if not f.get('_used'): print('  ! fix not applied (no match):', f['contest'], f['id'])
for d in drops:
    if not d.get('_used'): print('  ! drop not applied (no match):', d['contest'], d['id'], d.get('slug'))
