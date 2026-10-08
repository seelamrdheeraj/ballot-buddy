#!/usr/bin/env python3
"""Merge researcher JSON -> data/ballot-2026.json + data/reps.json, inject CA seed into the app HTML.
Robust to missing inputs: run again as more research lands."""
import json, os, re, sys, datetime, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import counties as CO

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_IN = os.path.join(ROOT, 'research')                       # ../research  (researcher outputs)
OUT = os.path.join(ROOT, 'data'); os.makedirs(OUT, exist_ok=True)
TODAY = datetime.date.today().isoformat()

def load(name):
    p = os.path.join(DATA_IN, name)
    if not os.path.exists(p): print(f'  (missing) {name}'); return None
    try:
        with open(p, encoding='utf-8') as f: txt = f.read()
        # tolerate agents that wrapped JSON in ``` fences
        m = re.search(r'\{.*\}', txt, re.S); return json.loads(m.group(0) if m else txt)
    except Exception as e: print(f'  (bad json) {name}: {e}'); return None

# ---------- topic normalization ----------
TOPIC_KEYS = [
 ('housing', r'hous|rent|homeown|afford.*home|starter home'),
 ('cost', r'cost of living|afford|price|inflation|grocer|utility bill'),
 ('health', r'health|medic|insul|drug|clinic|abortion|reproduct'),
 ('taxes', r'\btax'),
 ('energy', r'gas|energy|oil|electric|utilit|fuel'),
 ('education', r'educat|school|student|teacher|college|tuition|university'),
 ('safety', r'safety|police|law enforce|fire|crime|public safety|border|traffick'),
 ('immigration', r'immigra|border'),
 ('economy', r'econom|business|job|wage|worker|manufactur|trade'),
 ('environment', r'environ|climate|water|wildfire|conserv|clean'),
 ('elections', r'elect|voting|democracy|redistrict'),
 ('budget', r'budget|spending|deficit|debt|fiscal'),
 ('veterans', r'veteran'),
 ('agriculture', r'agricult|farm'),
 ('homeless', r'homeless'),
 ('childcare', r'child ?care|family'),
]
def topic_key(raw):
    s = (raw or '').lower()
    if re.search(r'abortion|reproduct', s): return 'abortion'
    if re.search(r'\bgun|firearm|second amendment', s): return 'guns'
    for k, rx in TOPIC_KEYS:
        if re.search(rx, s): return k
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_') or 'other'

def slug(s): return re.sub(r'[^a-z0-9]+', '', (s or '').lower())
CLS = ['', 'b', 'c', 'd']

def norm_candidate(c, race_id, i):
    pos = []
    for p in (c.get('positions') or []):
        if not p or not p.get('statement'): continue
        pos.append({'topic': topic_key(p.get('topic')), 'statement': p['statement'].strip(), 'url': p.get('url') or c.get('site') or ''})
    out = {
        'id': f"{race_id}:{slug(c.get('name'))}",
        'name': (c.get('name') or '').strip(),
        'party': (c.get('party') or '').strip() or 'Unknown',
        'cls': CLS[i % 4],
        'background': (c.get('background') or '').strip(),
        'summary': (c.get('summary') or '').strip(),
        'site': c.get('site') if c.get('site') and c['site'].lower() not in ('no site found', 'none', '') else '',
        'src': c.get('site') or c.get('background_url') or '',
        'positions': pos,
    }
    if c.get('social'): out['social'] = c['social']
    if c.get('incumbent') in (True,'true','True','yes'): out['inc'] = 'Incumbent'
    if not pos: out['nopos'] = True
    return out

# Curated California content (bios, positions, verified sites) now lives in research/local_curated.json;
# candidates and contests come from the SoS certified list and the county registrar lists (research/).
SJC = 'https://www.sjgov.org/department/rov/election-information/current_election'

DEADLINES_CA = [
 {'id':'mail','date':'2026-10-05','title':{'en':'Mail ballots go out','es':'Se envían las boletas por correo'},'sub':{'en':'Every registered voter is mailed one. Ballot drop boxes and early voting at the county Registrar’s office open the same day.','es':'Cada votante registrado recibe una. Los buzones y la votación anticipada en la oficina del Registro abren el mismo día.'}},
 {'id':'reg','date':'2026-10-19','title':{'en':'Register to vote','es':'Regístrate para votar'},'sub':{'en':'Missed it? From Oct 20 through Election Day you can register and vote in person at any polling place.','es':'¿Se te pasó? Del 20 de octubre al día de la elección puedes registrarte y votar en persona en cualquier lugar de votación.'}},
 {'id':'req','date':'2026-10-27','title':{'en':'Last day to request a mail ballot','es':'Último día para pedir boleta por correo'},'sub':{'en':'If yours never arrived, ask the county Registrar by today.','es':'Si la tuya no llegó, pídela al Registro del condado hoy.'}},
 {'id':'eday','date':'2026-11-03','title':{'en':'Election Day','es':'Día de la elección'},'sub':{'en':'Polls open 7 a.m. to 8 p.m. Mail ballots must be postmarked today, or dropped in a box by 8 p.m.','es':'Las urnas abren de 7 a.m. a 8 p.m. Las boletas por correo deben tener matasellos de hoy o ir al buzón antes de las 8 p.m.'}},
 {'id':'recv','date':'2026-11-10','title':{'en':'Mailed ballots must arrive','es':'Deben llegar las boletas por correo'},'sub':{'en':'A ballot postmarked by Nov 3 counts if the county receives it by today.','es':'Una boleta con matasellos del 3 de nov cuenta si el condado la recibe hoy.'}},
]
DEADLINES_DEFAULT = [
 {'id':'reg','date':None,'approx':{'en':'Usually 15–30 days before Election Day','es':'Usualmente 15–30 días antes de la elección'},'title':{'en':'Register to vote','es':'Regístrate para votar'},'sub':{'en':'Deadlines vary by state. Many states allow same-day registration. Check vote.gov for yours.','es':'Las fechas varían por estado. Muchos permiten registrarse el mismo día. Revisa vote.gov.'}},
 {'id':'mail','date':None,'approx':{'en':'Usually early to mid-October','es':'Usualmente a principios o mediados de octubre'},'title':{'en':'Request a mail ballot','es':'Solicita tu boleta por correo'},'sub':{'en':'Some states mail every voter a ballot; others require a request. Check vote.gov.','es':'Algunos estados envían boleta a todos; otros requieren solicitud. Revisa vote.gov.'}},
 {'id':'eday','date':'2026-11-03','title':{'en':'Election Day','es':'Día de la elección'},'sub':{'en':'Polls are open all day. Mailing your ballot? Send it early; some states must receive it by today.','es':'Las urnas abren todo el día. ¿Por correo? Envíala temprano; algunos estados deben recibirla hoy.'}},
]
OFFICIAL = {
 'CA': [{'name':{'en':'CA Secretary of State · Elections','es':'Secretario de Estado de CA · Elecciones'},'url':'https://www.sos.ca.gov/elections'},{'name':{'en':'Check registration','es':'Verificar registro'},'url':'https://voterstatus.sos.ca.gov/'},{'name':{'en':'Official Voter Guide','es':'Guía oficial del votante'},'url':'https://voterguide.sos.ca.gov/'},{'name':{'en':'Track my ballot','es':'Rastrear mi boleta'},'url':'https://california.ballottrax.net/'}],
 '95391': [{'name':{'en':'San Joaquin County Registrar','es':'Registro del condado de San Joaquin'},'url':SJC},{'name':{'en':'City of Mountain House','es':'Ciudad de Mountain House'},'url':'https://www.mountainhouseca.gov/436/Elections'},{'name':{'en':'Lammersville Unified School District','es':'Distrito Escolar de Lammersville'},'url':'https://www.lammersvilleschooldistrict.net/'},{'name':{'en':'Ballot drop box locations','es':'Buzones para boletas'},'url':'https://www.sjgov.org/department/rov/election-information/current_election/ballot-drop-box-locations'}],
}
UPDATES = {
 'CA': [{'date':'Aug 27','hot':True,'title':{'en':'Your candidates are final','es':'Tus candidatos son definitivos'},'body':{'en':'The Secretary of State certified the Nov 3 candidate list.','es':'El Secretario de Estado certificó la lista de candidatos del 3 de nov.'},'url':'https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf'},
        {'date':'Aug 10','title':{'en':'Official Voter Guide published','es':'Guía oficial del votante publicada'},'body':{'en':'14 statewide propositions, explained in Measures.','es':'14 propuestas estatales, explicadas en Medidas.'},'url':'https://voterguide.sos.ca.gov/'}],
 'all': [{'date':'Nov 3','title':{'en':'Election Day is Tuesday, November 3','es':'La elección es el martes 3 de noviembre'},'body':{'en':'Check your registration and deadlines in this app.','es':'Revisa tu registro y fechas límite en esta app.'},'url':'https://vote.gov'}],
}


# ---------- merge ----------
D = {'generated': TODAY, 'election': '2026-11-03', 'races': {'governor': {}, 'senate': {}, 'house': {}, 'statewide': {}, 'ssenate': {}, 'assembly': {}}, 'measures': {}, 'measures_meta': {}, 'local': {}, 'deadlines': {}, 'official': OFFICIAL, 'updates': UPDATES, 'sources': {}, 'coverage': {}, 'counties': {}, 'contests': {}, 'local_measures': {}, 'zips': {}, 'offices': {}, 'concepts': {}}
print('merging:')
for f in sorted(glob.glob(os.path.join(DATA_IN, 'gov_*.json'))):
    j = load(os.path.basename(f))
    if not j: continue
    for st, race in (j.get('states') or {}).items():
        cands = [norm_candidate(c, f'gov:{st}', i) for i, c in enumerate(race.get('candidates') or []) if c.get('name')]
        if not cands: continue
        D['races']['governor'][st] = {'source_url': race.get('certified_source_url') or race.get('source_url') or '', 'primary_held': race.get('primary_held'), 'notes': race.get('notes',''), 'candidates': cands}
    print(f'  {os.path.basename(f)}: {len(j.get("states") or {})} states')
for f in sorted(glob.glob(os.path.join(DATA_IN, 'senate*.json'))):
    sen = load(os.path.basename(f))
    if not sen: continue
    for st, race in (sen.get('states') or {}).items():
        cands = [norm_candidate(c, f'sen:{st}', i) for i, c in enumerate(race.get('candidates') or []) if c.get('name')]
        if not cands: continue
        D['races']['senate'][st] = {'source_url': race.get('source_url') or '', 'special': bool(race.get('special')), 'primary_held': race.get('primary_held'), 'notes': race.get('notes',''), 'candidates': cands}
    print(f'  {os.path.basename(f)}: {len(sen.get("states") or {})} states')
for f in sorted(glob.glob(os.path.join(DATA_IN, 'measures_*.json'))):
    j = load(os.path.basename(f))
    if not j: continue
    n = 0
    for st, block in (j.get('states') or {}).items():
        ms = []
        for m in (block.get('measures') or []):
            if not m.get('number'): continue
            plain = m.get('plain') or []
            ms.append({'number': m['number'], 'title': m.get('title',''), 'ballot_label': m.get('ballot_label',''), 'plain': (plain[:3] if isinstance(plain, list) else (plain if isinstance(plain, dict) else [str(plain)])), 'yes': m.get('yes',''), 'no': m.get('no',''), 'fiscal': m.get('fiscal',''), 'urls': m.get('urls') or ([m['url']] if m.get('url') else [])})
        if ms: D['measures'][st] = ms; n += len(ms)
        # Keep the researcher's state-level caveats (pending litigation, a source that
        # could only be read secondhand) rather than dropping them at the merge.
        meta = {k: block[k] for k in ('source_url', 'official_guide_published', 'notes') if block.get(k)}
        if meta: D['measures_meta'][st] = meta
    for st in (j.get('states_with_no_measures') or []): D['measures'].setdefault(st, [])
    print(f'  {os.path.basename(f)}: {n} measures')

# ---------- California: SoS certified list + county registrar lists + curated enrichment ----------
if not D['measures'].get('CA'):
    print('  WARNING: no California propositions found in research/ — the CA seed will ship empty.')
CURATED = CO.load_json('local_curated.json') or {}
CERT = 'https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf'
statewide, house_sos, ssenate, assembly, boe, retention, SOSJ = CO.load_sos(CURATED)
D['races']['statewide']['CA'] = statewide
for k, v in house_sos.items(): D['races']['house'][k] = v
D['races']['ssenate'] = ssenate; D['races']['assembly'] = assembly
gov = next((c for c in (SOSJ.get('contests') or []) if (c.get('office') or '').strip() == 'Governor'), None)
if gov:
    D['races']['governor']['CA'] = {'source_url': CERT, 'primary_held': True, 'notes': 'Top two from the June 2, 2026 primary.',
                                    'candidates': [CO.norm_candidate(x, 'gov', CERT, CURATED) for x in gov['candidates']]}
else:
    print('  WARNING: research/sos_certified.json has no Governor contest; CA governor will be missing.')

def enrich_from_sos(contest):
    """County lists print names and designations; the SoS list adds party, incumbency and the printed website."""
    t = contest['type']; d = contest.get('district')
    ref = None
    if t == 'us_house' and d: ref = house_sos.get('CA%02d' % int(d))
    elif t == 'state_senate' and d: ref = ssenate.get('CA%02d' % int(d))
    elif t == 'assembly' and d: ref = assembly.get('CA%02d' % int(d))
    elif t == 'statewide' and re.search(r'equaliz', contest['office']['en'], re.I) and d: ref = boe.get(str(int(d)))
    elif t == 'statewide':
        ref = next((c for c in statewide if c['office_key'] == contest['office_key']), None)
        if contest['office_key'] == 'governor': ref = D['races']['governor'].get('CA')
    if not ref: return
    by = {CO.slug(c['name']): c for c in ref['candidates']}
    if not contest['candidates']:
        contest['candidates'] = [dict(c) for c in ref['candidates']]; contest['src'] = ref.get('source_url') or contest['src']; return
    for c in contest['candidates']:
        m = by.get(CO.slug(c['name']))
        if not m: contest.setdefault('gaps', []).append(f"{c['name']} not on the SoS certified list"); continue
        for k in ('party', 'inc', 'site', 'site_src', 'bio', 'background', 'summary', 'cls', 'positions', 'review', 'sources_reviewed', 'social', 'record'):
            if m.get(k) is not None and (k in ('party', 'inc', 'positions', 'review', 'sources_reviewed', 'bio', 'background', 'summary', 'cls', 'social', 'record') or not c.get(k)): c[k] = m[k]
        if not c['desig'].get('en') and m.get('desig'): c['desig'] = m['desig']
    missing = [c for s_, c in by.items() if s_ not in {CO.slug(x['name']) for x in contest['candidates']}]
    for c in missing: contest.setdefault('gaps', []).append(f"{c['name']} is on the SoS list but not the county list")

for key, rel in [('San Joaquin', 'counties/sjc.json'), ('Alameda', 'counties/alameda.json')]:
    res = CO.load_county(rel, key, CURATED)
    if not res: print(f'  WARNING: no county file for {key}; its local races will be missing.'); continue
    county, contests, measures = res
    for c in contests: enrich_from_sos(c)
    contests += CO.retention_contests(retention, key, CERT)
    # ballot styles → contest indexes (small, and the app joins on index)
    for i, c in enumerate(contests): c['ix'] = i
    if county.get('styles'):
        byid = {c['county_id']: c['ix'] for c in contests if c.get('county_id')}
        county['styles'] = [{'c': sorted({byid[x] for x in st['c'] if x in byid}), 'm': st['m'], 'a': st['a']} for st in county['styles']]
    D['counties'][key] = county; D['contests'][key] = contests; D['local_measures'][key] = measures
    print(f'  {rel}: {len(contests)} contests, {sum(len(c["candidates"]) for c in contests)} candidates, {len(measures)} measures')
D['offices'], D['concepts'] = CO.load_offices()
D['zips'] = CO.load_zips()
D['deadlines'] = {'CA': DEADLINES_CA, 'default': DEADLINES_DEFAULT}
D['local'] = {}   # legacy ZIP-keyed races replaced by D.contests (kept so older app code finds the key)

# reps
rt = load('reptracking.json')
reps = {'generated': TODAY, 'officials': []}
if rt:
    for o in rt.get('officials') or []:
        oid = 'rep:' + slug(o.get('name'))
        reps['officials'].append({'id': oid, 'name': o.get('name'), 'office': o.get('office'), 'party': o.get('party'), 'official_site': o.get('official_site'), 'campaign_site': o.get('campaign_site'), 'social': o.get('social') or {}, 'contact': o.get('contact'), 'upcoming_events': o.get('upcoming_events') or [],
            'promises': [{'topic': topic_key(p.get('topic')), 'statement': p.get('statement'), 'url': p.get('url')} for p in (o.get('promises') or [])],
            'votes': [dict(v, related_topic=topic_key(v.get('related_topic')) if v.get('related_topic') else '') for v in (o.get('votes') or [])]})
    print(f'  reptracking.json: {len(reps["officials"])} officials')
# link followed-candidate ids to rep ids where the same person (e.g., Harder is both a candidate and an official)
D['sources'] = {'zip_cd': 'U.S. Census Bureau ZCTA-to-Congressional-District relationship file (see NOTES.md)', 'fec': 'https://api.open.fec.gov/'}
D['coverage'] = {'governor_states': sorted(D['races']['governor']), 'senate_states': sorted(D['races']['senate']), 'measure_states': sorted(k for k, v in D['measures'].items() if v), 'local_counties': sorted(D['contests']), 'local_zips': sorted(D['zips'])}

# County data ships as its own file per county (fetched when a voter's ZIP is in that county); the main file carries only the index.
os.makedirs(os.path.join(OUT, 'local'), exist_ok=True)
D['local_index'] = {}
for key in D['counties']:
    fname = 'local/' + re.sub(r'[^a-z]+', '-', key.lower()).strip('-') + '.json'
    blob = {'generated': TODAY, 'county': D['counties'][key], 'contests': D['contests'][key], 'local_measures': D['local_measures'][key]}
    with open(os.path.join(OUT, fname), 'w', encoding='utf-8') as f: json.dump(blob, f, ensure_ascii=False, separators=(',', ':'))
    D['local_index'][key] = {'file': 'data/' + fname, 'name': D['counties'][key]['name'], 'contests': len(D['contests'][key]), 'measures': len(D['local_measures'][key]), 'generated': TODAY}
MAIN = {k: v for k, v in D.items() if k not in ('counties', 'contests', 'local_measures')}
with open(os.path.join(OUT, 'ballot-2026.json'), 'w', encoding='utf-8') as f: json.dump(MAIN, f, ensure_ascii=False, separators=(',', ':'))
with open(os.path.join(OUT, 'reps.json'), 'w', encoding='utf-8') as f: json.dump(reps, f, ensure_ascii=False, separators=(',', ':'))

# ---------- inject CA seed into HTML ----------
seed = {'generated': TODAY, 'election': D['election'], 'races': {'governor': {'CA': D['races']['governor'].get('CA')}, 'senate': {}, 'house': {k: v for k, v in D['races']['house'].items() if k.startswith('CA')}, 'statewide': D['races']['statewide'], 'ssenate': D['races']['ssenate'], 'assembly': D['races']['assembly']}, 'measures': {'CA': D['measures'].get('CA', [])}, 'local': {}, 'deadlines': D['deadlines'], 'official': OFFICIAL, 'updates': UPDATES, 'sources': D['sources'], 'coverage': D['coverage'], 'local_index': D['local_index'], 'zips': D['zips'], 'offices': D['offices'], 'concepts': D['concepts']}
html_path = os.path.join(ROOT, 'ballot-buddy-app.html')
html = open(html_path, encoding='utf-8').read()
seed_txt = json.dumps(seed, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
html = re.sub(r'<script type="application/json" id="seed">.*?</script>', lambda m: '<script type="application/json" id="seed">' + seed_txt + '</script>', html, flags=re.S)
open(html_path, 'w', encoding='utf-8').write(html)

sizes = {n: os.path.getsize(os.path.join(OUT, n)) for n in ['ballot-2026.json', 'reps.json'] + [v['file'].replace('data/', '') for v in D['local_index'].values()]}
print('\ncoverage:', json.dumps({k: len(v) for k, v in D['coverage'].items()}))
print('sizes:', sizes, '| html:', os.path.getsize(html_path))
