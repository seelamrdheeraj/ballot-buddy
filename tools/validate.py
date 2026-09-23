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
      f'local {len(D["local"])} ZIPs')
for w in warnings: print(f'  WARN  {w}')
for e in errors:  print(f'  ERROR {e}')
print(f'\n{len(errors)} errors, {len(warnings)} warnings')
sys.exit(1 if errors else 0)
