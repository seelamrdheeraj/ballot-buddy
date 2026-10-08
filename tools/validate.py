#!/usr/bin/env python3
"""Check data/ballot-2026.json for the mistakes that would show a voter something wrong.

Errors are things that would render badly or mislead; warnings are gaps worth knowing about.
Exit code is 1 if there are errors, so CI can gate on it.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO "
             "MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
# Offices actually on a Nov 3, 2026 ballot, so "missing" means missing rather than nonexistent.
GOV_2026 = set("AL AK AZ AR CA CO CT FL GA HI ID IL IA KS ME MD MA MI MN NE NV NH NM NY OH "
               "OK OR PA RI SC SD TN TX VT WI WY".split())
# The 33 Class 2 seats, plus the Florida and Ohio special elections for appointed senators.
SEN_2026 = set("AL AK AR CO DE FL GA ID IL IA KS KY LA ME MA MI MN MS MT NE NH NJ NM NC "
               "OH OK OR RI SC SD TN TX VA WV WY".split())

errors, warnings = [], []
def err(m): errors.append(m)
def warn(m): warnings.append(m)

path = os.path.join(ROOT, 'data', 'ballot-2026.json')
D = json.load(open(path, encoding='utf-8'))

def text_of(v):
    """Fields are either a plain string or an {en, es} pair."""
    if isinstance(v, dict): return v.get('en') or ''
    return v or ''

# ---------- races ----------
for office, expected in (('governor', GOV_2026), ('senate', SEN_2026)):
    got = set(D['races'][office])
    for st in sorted(got - STATES): err(f'{office}: "{st}" is not a state code')
    for st in sorted(expected - got): warn(f'{office}: no data for {st}, which holds this race in 2026')
    for st in sorted(got - expected): warn(f'{office}: {st} has data but was not expected to hold this race')
    for st, race in D['races'][office].items():
        if not race.get('candidates'): err(f'{office} {st}: no candidates')
        if not race.get('source_url'): warn(f'{office} {st}: no source_url')
        seen = set()
        for c in race['candidates']:
            if not c.get('name'): err(f'{office} {st}: a candidate has no name')
            if c.get('id') in seen: err(f'{office} {st}: duplicate candidate id {c.get("id")}')
            seen.add(c.get('id'))
            if not c.get('positions') and not c.get('nopos'):
                err(f'{office} {st}: {c.get("name")} has no positions and is not flagged nopos')
            for p in c.get('positions') or []:
                if not text_of(p.get('statement')): err(f'{office} {st}: {c.get("name")} has an empty position')
                if not p.get('url'): warn(f'{office} {st}: {c.get("name")} position has no source url')

# ---------- measures ----------
total = 0
for st, ms in D['measures'].items():
    if st not in STATES: err(f'measures: "{st}" is not a state code'); continue
    numbers = set()
    for m in ms:
        total += 1
        where = f'measure {st} {m.get("number")}'
        if not m.get('number'): err(f'measures {st}: a measure has no number')
        if m.get('number') in numbers: err(f'measures {st}: duplicate number {m.get("number")}')
        numbers.add(m.get('number'))
        if not m.get('title'): warn(f'{where}: no title')
        plain = m.get('plain') or []
        if isinstance(plain, dict): plain = plain.get('en') or []
        if not plain: err(f'{where}: no plain-English bullets')
        elif len(plain) != 3: warn(f'{where}: {len(plain)} plain bullets (3 expected)')
        for b in plain:
            if isinstance(b, str) and len(b) > 260: warn(f'{where}: a plain bullet is {len(b)} chars, long for a phone')
        if not text_of(m.get('yes')): err(f'{where}: missing what a YES vote does')
        if not text_of(m.get('no')): err(f'{where}: missing what a NO vote does')
        if not text_of(m.get('fiscal')): warn(f'{where}: no fiscal line')
        if not m.get('urls'): err(f'{where}: no source url')
        for u in m.get('urls') or []:
            if not str(u).startswith('http'): err(f'{where}: bad url {u!r}')

missing_states = sorted(STATES - set(D['measures']))
if missing_states:
    warn(f'measures: {len(missing_states)} states not researched at all: {" ".join(missing_states)}')

# ---------- deadlines, local, official ----------
for scope, ds in D['deadlines'].items():
    for d in ds:
        if not d.get('date') and not d.get('approx'):
            err(f'deadline {scope}/{d.get("id")}: neither a date nor an approximate window')
        if d.get('date') and not re.fullmatch(r'2026-\d\d-\d\d', d['date']):
            err(f'deadline {scope}/{d.get("id")}: bad date {d["date"]}')
for zipc, races in D['local'].items():
    if not re.fullmatch(r'\d{5}', zipc): err(f'local: "{zipc}" is not a ZIP')
    for r in races:
        if not r.get('candidates'): err(f'local {zipc}/{r.get("id")}: no candidates')

# ---------- report ----------
print(f'{path}')
print(f'  governor {len(D["races"]["governor"])} states · senate {len(D["races"]["senate"])} states · '
      f'measures {total} in {len([k for k,v in D["measures"].items() if v])} states · '
      f'local {len(D.get("local_index") or {})} counties, {len(D.get("zips") or {})} ZIPs')
for w in warnings: print(f'  WARN  {w}')
# ---------- county files (San Joaquin, Alameda): what a local voter would see ----------
for key, idx in (D.get('local_index') or {}).items():
    lp = os.path.join(ROOT, idx['file'])
    if not os.path.exists(lp): err(f'{key}: county file {idx["file"]} missing'); continue
    LJ = json.load(open(lp, encoding='utf-8'))
    C, contests, measures = LJ.get('county') or {}, LJ.get('contests') or [], LJ.get('local_measures') or []
    if not C.get('registrar', {}).get('url'): err(f'{key}: registrar URL missing')
    if not any(d.get('id') == 'eday' for d in C.get('dates', [])): warn(f'{key}: no Election Day row in county dates (state row will be used)')
    if C.get('vca') is None: warn(f'{key}: Voter\'s Choice Act status unknown')
    if not C.get('lookup'): warn(f'{key}: no district/sample-ballot lookup tool link')
    seen_ids = set()
    for c in contests:
        cid = c.get('id', '?')
        if cid in seen_ids: err(f'{key}: duplicate contest id {cid}')
        seen_ids.add(cid)
        if not text_of(c.get('office')): err(f'{key}: contest {cid} has no office title')
        if not text_of(c.get('juris')): err(f'{key}: contest {cid} has no jurisdiction')
        if not c.get('src'): err(f'{key}: contest {cid} has no source link')
        if not c.get('office_key'): warn(f'{key}: contest {cid} has no office description key')
        if not c.get('candidates'): warn(f'{key}: contest {cid} lists no candidates')
        for cand in c.get('candidates') or []:
            n = cand.get('name') or '?'
            if not cand.get('src'): err(f'{key}: {n} ({cid}) has no official source link')
            if cand.get('site'):
                if not re.match(r'^https?://', cand['site']): err(f'{key}: {n} website lacks a scheme: {cand["site"]}')
                if cand.get('site_src') not in ('official_list', 'verified'): err(f'{key}: {n} website is not from an official list or verified research')
            if cand.get('review') not in ('reviewed', 'unreviewed', 'none_found'): err(f'{key}: {n} has an unknown review status {cand.get("review")!r}')
            for pos in cand.get('positions') or []:
                if not pos.get('url'): err(f'{key}: {n} position "{text_of(pos.get("statement"))[:40]}" has no source URL')
                if pos.get('kind') not in ('stated', 'record', 'reporting'): err(f'{key}: {n} position kind {pos.get("kind")!r} is not stated/record/reporting')
            if cand.get('nopos'): err(f'{key}: {n} still carries the retired nopos flag')
    for m in measures:
        if not m.get('id') or not m.get('src'): err(f'{key}: local measure {m.get("id")!r} lacks a letter or a source link')
        if not m.get('question') and not m.get('title'): warn(f'{key}: measure {m.get("id")} has no question text')
    print(f'  {key}: {len(contests)} contests, {sum(len(c.get("candidates") or []) for c in contests)} candidates, {len(measures)} local measures')
for z, v in (D.get('zips') or {}).items():
    if v.get('county') not in (D.get('local_index') or {}): err(f'ZIP {z} maps to uncovered county {v.get("county")!r}')

for e in errors:  print(f'  ERROR {e}')
print(f'\n{len(errors)} errors, {len(warnings)} warnings')
sys.exit(1 if errors else 0)
