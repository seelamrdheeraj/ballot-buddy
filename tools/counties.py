#!/usr/bin/env python3
"""Normalize county registrar lists, the SoS certified list, office descriptions and the
ZIP table (research/) into the shapes the app reads. Imported by build.py.

Every candidate keeps `src` (the official list it came from). `site` is set ONLY when an
official list printed a campaign website or research/local_curated.json carries a verified
one — the app shows a "Candidate website" link only when `site` exists."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, 'research')

def load_json(rel):
    p = os.path.join(RES, rel)
    if not os.path.exists(p):
        print(f'  (missing) research/{rel}'); return None
    with open(p, encoding='utf-8') as f: return json.load(f)

def slug(s): return re.sub(r'[^a-z0-9]', '', (s or '').lower())
SITE_STATUS = {}
try:
    SITE_STATUS = json.load(open(os.path.join(RES, 'site_status.json'), encoding='utf-8'))
except Exception: pass

SMALL = {'de', 'la', 'del', 'van', 'von', 'der', 'y', 'e'}
def nice_name(n):
    """County lists print names in capitals; present them in normal case without touching mixed-case input."""
    n = (n or '').strip()
    if n != n.upper() or not n: return n
    def word(w):
        if not w: return w
        if re.fullmatch(r'[A-Z]\.?', w): return w.upper()               # initials: R. G.
        if w.lower() in SMALL: return w.lower()
        core = w.lower()
        core = re.sub(r"^(mc|mac|o')(\w)", lambda m: m.group(1).capitalize() + m.group(2).upper(), core)
        core = re.sub(r"(^|[-'\u2019\"(])(\w)", lambda m: m.group(1) + m.group(2).upper(), core)
        return core
    out = ' '.join(word(w) for w in n.split(' '))
    out = re.sub(r'\b(Ii|Iii|Iv|Jr|Sr)\b\.?', lambda m: m.group(0).upper(), out)
    return out

# ---------- office keys (for plain-language descriptions) ----------
OFFICE_KEY_RULES = [
 ('governor', r'^governor$'), ('lt_governor', r'lieutenant governor'), ('secretary_of_state', r'secretary of state'),
 ('controller', r'controller'), ('treasurer', r'^(state )?treasurer$'), ('attorney_general', r'attorney general'),
 ('insurance_commissioner', r'insurance commissioner'), ('superintendent_public_instruction', r'superintendent of public instruction'),
 ('board_of_equalization', r'equalization'), ('us_house', r'united states representative|u\.?s\.? (house|representative)|congress'),
 ('state_senate', r'state senat'), ('assembly', r'assembly'), ('supreme_court_retention', r'supreme court'),
 ('appeals_court_retention', r'court of appeal'), ('county_supervisor', r'supervisor'), ('county_assessor', r'assessor'),
 ('county_auditor_controller', r'auditor'), ('county_clerk_recorder', r'clerk|recorder'), ('district_attorney', r'district attorney'),
 ('sheriff', r'sheriff'), ('county_treasurer_tax_collector', r'tax collector'), ('county_superintendent_schools', r'superintendent of schools'),
 ('county_board_of_education', r'board of education'), ('mayor', r'^mayor'), ('city_attorney', r'city attorney'), ('city_auditor', r'city auditor|^auditor'),
 ('city_clerk', r'city clerk'), ('city_treasurer', r'city treasurer'), ('city_council', r'council'),
 ('bart_director', r'bay area rapid transit|bart'), ('ac_transit_director', r'ac transit|alameda-contra costa transit'),
 ('east_bay_mud_director', r'municipal utility'), ('east_bay_regional_park_director', r'regional park'),
 ('community_college_trustee', r'community college|college district'), ('school_board', r'school|unified|union elementary|governing board|trustee'),
 ('special_district_director', r'director|district'),
]
def office_key(contest):
    txt = ' '.join([contest.get('office') or '', contest.get('jurisdiction') or '']).lower()
    jt = contest.get('jurisdiction_type') or ''
    if jt == 'us_house': return 'us_house'
    if jt == 'state_senate': return 'state_senate'
    if jt == 'assembly': return 'assembly'
    if jt == 'county_supervisor': return 'county_supervisor'
    if jt == 'college': return 'community_college_trustee'
    if jt == 'school': return 'school_board'
    if jt == 'transit':
        for k, rx in OFFICE_KEY_RULES:
            if k in ('bart_director', 'ac_transit_director') and re.search(rx, txt): return k
        return 'special_district_director'
    for k, rx in OFFICE_KEY_RULES:
        if re.search(rx, (contest.get('office') or '').lower()): return k
    for k, rx in OFFICE_KEY_RULES:
        if re.search(rx, txt): return k
    return 'special_district_director'

LEVEL = {
 'us_house': {'en': 'Federal', 'es': 'Federal'}, 'statewide': {'en': 'Statewide', 'es': 'Estatal'},
 'state_senate': {'en': 'State', 'es': 'Estatal'}, 'assembly': {'en': 'State', 'es': 'Estatal'},
 'judicial': {'en': 'Courts', 'es': 'Tribunales'},
 'county_supervisor': {'en': 'County', 'es': 'Condado'}, 'county_office': {'en': 'County', 'es': 'Condado'},
 'city': {'en': 'City', 'es': 'Ciudad'}, 'school': {'en': 'Schools', 'es': 'Escuelas'}, 'college': {'en': 'Schools', 'es': 'Escuelas'},
 'special': {'en': 'Special district', 'es': 'Distrito especial'}, 'transit': {'en': 'Transit & utilities', 'es': 'Transporte y servicios'},
}

# ---------- Spanish for office titles and jurisdiction names ----------
ES_OFFICE = [
 (r'(?i)^board member,? trustee area (\d+)$', r'Miembro de la junta, Área \1'),
 (r'(?i)^member,? state board of equalization,? district (\d+)$', r'Junta de Igualación, Distrito \1'),
 (r'(?i)^member,? state board of equalization,? (\d+)(st|nd|rd|th) district$', r'Junta de Igualación, Distrito \1'),
 (r'(?i)^(.*) \(short term\)$', lambda m: es_of(m.group(1), ES_OFFICE) + ' (mandato corto)'),
 (r'(?i)^(.*) \(full term\)$', lambda m: es_of(m.group(1), ES_OFFICE) + ' (mandato completo)'),
 (r'^Governor$', 'Gobernador'), (r'^Lieutenant Governor$', 'Vicegobernador'), (r'^Secretary of State$', 'Secretario de Estado'),
 (r'^(State )?Controller$', 'Contralor estatal'), (r'^(State )?Treasurer$', 'Tesorero estatal'), (r'^Attorney General$', 'Fiscal General'),
 (r'^Insurance Commissioner$', 'Comisionado de Seguros'), (r'^Superintendent of Public Instruction$', 'Superintendente de Instrucción Pública'),
 (r'(?i)board of equalization,? (member,? )?district (\d+)', r'Junta de Igualación, Distrito \2'),
 (r'(?i)united states representative,? (\d+)(st|nd|rd|th)? district', r'Representante de EE. UU., Distrito \1'),
 (r'(?i)u\.?s\.? (house|representative),? district (\d+)', r'Representante de EE. UU., Distrito \2'),
 (r'(?i)state senator,? (\d+)(st|nd|rd|th)? district', r'Senador estatal, Distrito \1'),
 (r'(?i)state senat\w*,? district (\d+)', r'Senador estatal, Distrito \1'),
 (r'(?i)member of the state assembly,? (\d+)(st|nd|rd|th)? district', r'Asambleísta estatal, Distrito \1'),
 (r'(?i)(state )?assembly\w*,? district (\d+)', r'Asambleísta estatal, Distrito \2'), (r'(?i)member of the state assembly,? (\d+)(st|nd|rd|th) assembly district', r'Asambleísta estatal, Distrito \1'), (r'(?i)^u\.s\. representative,? (\d+)(st|nd|rd|th) congressional district', r'Representante de EE. UU., Distrito \1'), (r'(?i)^state senator,? (\d+)(st|nd|rd|th) state senate district', r'Senador estatal, Distrito \1'), (r'(?i)equalization,? (\d+)(st|nd|rd|th) district', r'Junta de Igualación, Distrito \1'),
 (r'(?i)^mayor$', 'Alcalde'), (r'(?i)^(city )?council ?member,? district (\d+)$', r'Concejal, Distrito \2'), (r'(?i)^(city )?council ?member,? district (\d+)( \(short term\))?$', r'Concejal, Distrito \2'),
 (r'(?i)^(city )?council ?member$', 'Concejal'), (r'(?i)^city attorney$', 'Abogado de la ciudad'), (r'(?i)^(city )?auditor$', 'Auditor'), (r'(?i)^member,? state board of equalization,? district (\d+)$', r'Junta de Igualación, Distrito \1'),
 (r'(?i)^city clerk$', 'Secretario municipal'), (r'(?i)^city treasurer$', 'Tesorero municipal'),
 (r'(?i)supervisor,? district (\d+)', r'Supervisor del condado, Distrito \1'), (r'(?i)^district attorney$', 'Fiscal de distrito'),
 (r'(?i)^sheriff(-coroner)?$', 'Alguacil'), (r'(?i)assessor', 'Tasador del condado'), (r'(?i)auditor-controller', 'Auditor-Contralor'),
 (r'(?i)treasurer-tax collector', 'Tesorero-Recaudador'), (r'(?i)superintendent of schools', 'Superintendente de escuelas del condado'),
 (r'(?i)board of education,? (trustee )?area (\d+)', r'Junta de Educación, Área \2'),
 (r'(?i)governing board member,? trustee area (\d+)', r'Miembro de la junta directiva, Área \1'),
 (r'(?i)governing board member', 'Miembro de la junta directiva'), (r'(?i)trustee area (\d+)', r'Área \1'),
 (r'(?i)^board member,? trustee area (\d+)$', r'Miembro de la junta, Área \1'), (r'(?i)^school board member,? area (\d+)( \(short term\))?$', r'Miembro de la junta escolar, Área \1\2'),
 (r'(?i)^school board member( \(full term\))?$', 'Miembro de la junta escolar'), (r'(?i)^school director,? district (\d+)$', r'Director escolar, Distrito \1'), (r'(?i)^school director$', 'Director escolar'),
 (r'(?i)^board of education member$', 'Miembro de la Junta de Educación'), (r'(?i)^community college district trustee,? area (\d+)( \(short term\))?$', r'Miembro de la junta del colegio comunitario, Área \1\2'),
 (r'(?i)^member,? city council,? district (\d+)$', r'Concejal, Distrito \1'), (r'(?i)^member,? city council$', 'Concejal'), (r'(?i)^city council member,? district (\d+)$', r'Concejal, Distrito \1'), (r'(?i)^city council member$', 'Concejal'),
 (r'(?i)^board member,? division (\d+)( short term)?$', r'Miembro de la junta, División \1'), (r'(?i)^director,? (division|ward|district|area|dist #)\s?(\d+)$', r'Director, Distrito \2'), (r'(?i)^director$', 'Director'),
 (r'(?i)^rent stabilization board commissioner$', 'Comisionado de la Junta de Estabilización de Rentas'),
]
ES_JURIS = [(r'^City of (.+)$', r'Ciudad de \1'), (r'^County of (.+)$', r'Condado de \1'), (r'^(.+) County$', r'Condado de \1'),
            (r'^Town of (.+)$', r'Pueblo de \1'), (r'(?i)^(.+?) joint unified school district$', r'Distrito Escolar Unificado Conjunto \1'),
            (r'(?i)^(.+?) unified school district$', r'Distrito Escolar Unificado \1'), (r'(?i)^(.+?) elementary school district$', r'Distrito Escolar Primario \1'),
            (r'(?i)^(.+?) (joint )?union high school district$', r'Distrito de Preparatorias \1'), (r'(?i)^(.+?) community college district$', r'Distrito de Colegios Comunitarios \1'),
            (r'(?i)^(.+?) irrigation district$', r'Distrito de Riego \1'), (r'(?i)^(.+?) water district$', r'Distrito de Agua \1'), (r'(?i)^(.+?) sanitary district$', r'Distrito Sanitario \1'),
            (r'(?i)^(.+?) healthcare district$', r'Distrito de Salud \1'), (r'(?i)^(.+?) fire protection district$', r'Distrito de Protección contra Incendios \1'),
            (r'(?i)^(.+?) recreation & park district$', r'Distrito de Recreación y Parques \1'), (r'(?i)^(.+?) regional park district$', r'Distrito de Parques Regionales \1'),
            (r'(?i)^(.+?) municipal utility district( \(EBMUD\))?$', r'Distrito Municipal de Servicios \1'), (r'(?i)^AC Transit District$', 'Distrito AC Transit'),
            (r'(?i)^California State Assembly$', 'Asamblea Estatal de California'), (r'(?i)^California State Senate$', 'Senado Estatal de California'),
            (r'(?i)^(United States|U\.S\.) House of Representatives$', 'Cámara de Representantes de EE. UU.'), (r'(?i)^State of California$', 'Estado de California')]
def es_of(text, rules):
    t = text or ''
    for rx, rep in rules:
        if re.search(rx, t): return re.sub(rx, rep, t)
    return t
def bi(en, rules): return {'en': en or '', 'es': es_of(en, rules)}

# ---------- candidates ----------
def norm_candidate(c, cid_prefix, src, curated=None):
    name = nice_name(c.get('name'))
    cid = f'{cid_prefix}:{slug(name)}'
    party = c.get('party')
    out = {'id': cid, 'name': name, 'party': party if party else 'nonp',
           'desig': {'en': c.get('ballot_designation') or '', 'es': c.get('ballot_designation_es') or c.get('ballot_designation') or ''},
           'src': c.get('src') or src, 'review': 'unreviewed'}
    if c.get('incumbent'): out['inc'] = 'Incumbent'
    if c.get('website'):
        w = c['website'].strip()
        if w and not re.match(r'^https?://', w, re.I): w = 'https://' + w   # printed without a scheme; the address itself is as printed
        st = SITE_STATUS.get(w) or SITE_STATUS.get(w.rstrip('/')) or SITE_STATUS.get(w + '/')
        if st and st.get('status') == 0:   # domain did not resolve / refused when probed: say so instead of linking to nothing
            out['site_note'] = {'en': f"The official list prints {w.replace('https://', '')}, which did not respond when checked on {st.get('checked')}.", 'es': f"La lista oficial indica {w.replace('https://', '')}, que no respondía al verificarlo el {st.get('checked')}."}
        else:
            out['site'] = w; out['site_src'] = 'official_list'
    cur = (curated or {}).get(slug(name)) or (curated or {}).get(cid)
    if cur:
        for k in ('bio', 'summary', 'cls', 'background'):
            if cur.get(k) is not None: out[k] = cur[k]
        if cur.get('party'): out['party'] = cur['party']
        if cur.get('inc'): out['inc'] = cur['inc']
        if cur.get('desig'): out['desig'] = cur['desig']
        if cur.get('site'): out['site'] = cur['site']; out['site_src'] = cur.get('site_src') or 'verified'
        if cur.get('site') is None and 'site' in cur: out.pop('site', None); out.pop('site_src', None)
        if cur.get('positions'): out['positions'] = cur['positions']
        if cur.get('record'): out['record'] = cur['record']
        if cur.get('review'): out['review'] = cur['review']
        if cur.get('sources_reviewed'): out['sources_reviewed'] = cur['sources_reviewed']
        if cur.get('social'): out['social'] = cur['social']
        if cur.get('site_note'): out['site_note'] = cur['site_note']
        if cur.get('src'): out['src'] = cur['src']
    return out

SCHOOL_CITY = {'City of Oakland': 'Oakland Unified School District', 'City of Berkeley': 'Berkeley Unified School District', 'City of Albany': 'Albany Unified School District'}
def norm_contest(c, county_key, src, curated):
    jt = c.get('jurisdiction_type') or 'special'
    office = c.get('office') or ''
    if c.get('office_clean'):   # Alameda prints ballot headings ("For Mayor, Alameda"); the extraction also carries a clean title
        office = c['office_clean']
        dl = c.get('district_label')
        if dl and dl.lower() not in office.lower(): office += ', ' + dl
        if c.get('term') in ('Short Term', 'Full Term') and c['term'].lower() not in office.lower(): office += f" ({c['term'].lower()})"
    district = c.get('district')
    if jt == 'school' and (c.get('jurisdiction') or '') in SCHOOL_CITY: c = dict(c, jurisdiction=SCHOOL_CITY[c['jurisdiction']])
    cid = f'{county_key}:{jt}:{slug(c.get("jurisdiction"))}:{slug(office)}'
    out = {'id': cid, 'type': jt, 'level': LEVEL.get(jt, LEVEL['special']),
           'juris': bi(c.get('jurisdiction'), ES_JURIS), 'office': bi(office, ES_OFFICE),
           'district': str(district) if district not in (None, '') else None,
           'seats': int(c.get('seats') or 1), 'term': c.get('term') or '', 'rcv': bool(c.get('rcv')),
           'office_key': c.get('office_key_override') or office_key(c), 'src': c.get('src') or src,
           'election': {'en': 'November 3, 2026 General Election', 'es': 'Elección general del 3 de noviembre de 2026'},
           'candidates': [norm_candidate(x, cid, c.get('src') or src, curated) for x in (c.get('candidates') or []) if x.get('name')]}
    n_c = len(out['candidates'])
    out['on_ballot'] = True if c.get('on_ballot') is None else bool(c.get('on_ballot'))
    if c.get('status'): out['status'] = c['status']
    elif not out['on_ballot']: out['status'] = 'not_on_ballot'
    elif n_c == 0: out['status'] = 'no_candidate'
    elif jt == 'judicial': out['status'] = 'retention'
    elif n_c <= out['seats']: out['status'] = 'unopposed'
    else: out['status'] = 'contested'
    if c.get('status_note'): out['status_note'] = c['status_note'] if isinstance(c['status_note'], dict) else {'en': c['status_note'], 'es': c.get('status_note_es') or c['status_note']}
    if c.get('notes'):   # county extraction notes are for maintainers; show voters only the short, relevant sentences
        note = c['notes']
        m = re.search(r'not "Filing Completed" \(excluded from candidates\):\s*(.*)', note)
        if m:
            names = re.sub(r'\s+', ' ', m.group(1)).strip().rstrip('.')
            names = re.sub(r"\b([A-Z][A-Z'\-\.]+(?: [A-Z][A-Z'\-\.]+)+)\b", lambda x: nice_name(x.group(1)), names)
            out['note'] = {'en': 'Not on the candidate list (withdrawn or incomplete filing, per the county): ' + names + '.', 'es': 'No está en la lista de candidatos (retiro o solicitud incompleta, según el condado): ' + names + '.'}
        else:
            sents = [x.strip() for x in re.split(r'(?<=[.;])\s+', note) if x.strip()]
            keep = [x for x in sents if not re.search(r'write-in|ballot order|ballot type|roster|extract|parsed|footer|line-wrap|whitespace|sample ballot shows|VIG|county (lists|groups)|candidate list returns|not printed in the county|what\'s on the ballot', x, re.I)][:2]
            if keep: out['note'] = {'en': ' '.join(keep), 'es': c.get('notes_es') or ' '.join(keep)}
        if c.get('rcv'):   # replace extraction fragments with one plain-language line (the county's RCV page explains the rules)
            out['note'] = {'en': 'Ranked-choice voting: rank up to 5 candidates in order of preference. Your first choice counts first; later choices count only if your earlier choices are eliminated.',
                           'es': 'Votación por orden de preferencia: clasifica hasta 5 candidatos. Tu primera opción cuenta primero; las siguientes solo cuentan si tus opciones anteriores quedan eliminadas.'}
        if out.get('note') and re.search(r'seats not stated', out['note']['en'], re.I): out.pop('note')
    cid_county = c.get('id') or c.get('county_race_id')
    if cid_county is not None: out['county_id'] = str(cid_county)
    if c.get('term') in ('Short Term', 'Full Term'): out['term'] = ''
    return out

def norm_measure(m, county_key, src):
    return {'id': m.get('letter') or '', 'juris': bi(m.get('jurisdiction'), ES_JURIS), 'type': m.get('jurisdiction_type') or 'special',
            'title': m.get('title') or '', 'question': m.get('question') or '', 'threshold': m.get('threshold') or '', 'src': m.get('src') or src}

DATE_TITLES = {
 'mail': {'en': 'Mail ballots go out', 'es': 'Se envían las boletas por correo'},
 'reg': {'en': 'Register to vote', 'es': 'Regístrate para votar'},
 'sameday': {'en': 'Same-day registration begins', 'es': 'Comienza el registro el mismo día'},
 'req': {'en': 'Last day to request a mail ballot', 'es': 'Último día para pedir boleta por correo'},
 'early': {'en': 'Early voting begins', 'es': 'Comienza la votación anticipada'},
 'vc11': {'en': 'First vote centers open', 'es': 'Abren los primeros centros de votación'},
 'vc4': {'en': 'All vote centers open', 'es': 'Abren todos los centros de votación'},
 'eday': {'en': 'Election Day', 'es': 'Día de la elección'},
 'recv': {'en': 'Mailed ballots must arrive', 'es': 'Deben llegar las boletas por correo'},
 'drop': {'en': 'Ballot drop boxes open', 'es': 'Abren los buzones para boletas'},
}

def load_county(rel, county_key, curated):
    j = load_json(rel)
    if not j: return None
    src = ''
    for s in (j.get('sources') or []):
        if s.get('status') == 'ok' and s.get('url'): src = s['url']; break
    reg = j.get('registrar') or {}
    county = {'name': j.get('county') or county_key, 'fips': j.get('fips'), 'state': 'CA',
              'election': j.get('election') or {'date': '2026-11-03', 'name': 'November 3, 2026 General Election'},
              'registrar': {'name': reg.get('name') or '', 'url': reg.get('url') or '', 'phone': reg.get('phone') or '', 'address': reg.get('address') or ''},
              'vca': (str(reg.get('vca')).lower() == 'true') if reg.get('vca') is not None else None, 'vca_src': reg.get('vca_src') or '',
              'dates': [], 'official': [], 'lookup': [], 'sources': j.get('sources') or [], 'gaps': j.get('gaps') or []}
    VOTER_DATES = {'mail', 'reg', 'sameday', 'req', 'early', 'vc11', 'vc4', 'eday', 'recv'}
    for d in (j.get('dates') or []):
        if not d.get('date'): continue
        did = d.get('id') or 'other'
        if did == 'other' and re.search(r'drop box|drop stop', d.get('label') or '', re.I): did = 'drop'
        if did not in VOTER_DATES and did != 'drop': continue   # canvass, nomination period, testing: administrative, not voter deadlines
        county['dates'].append({'id': did if did != 'other' else 'x' + slug(d.get('label'))[:12], 'date': d['date'],
                                'title': {'en': d.get('label') or DATE_TITLES.get(did, {}).get('en', ''), 'es': d.get('label_es') or DATE_TITLES.get(did, {}).get('es', d.get('label') or '')},
                                'sub': {'en': d.get('detail') or '', 'es': d.get('detail_es') or d.get('detail') or ''}, 'src': d.get('src') or ''})
    SKIP_LINK = re.compile(r'precinct association|camera|media tool kit|drive up|write-in|statements? of vote|campaign finance|logic|canvass|facsimile|election results', re.I)
    for l in (j.get('official_links') or []):
        if l.get('url') and not SKIP_LINK.search(l.get('name') or ''): county['official'].append({'name': {'en': l.get('name') or '', 'es': l.get('name_es') or l.get('name') or ''}, 'url': l['url'], 'what': l.get('what') or ''})
    for l in (j.get('lookup_tools') or []):
        if l.get('url'): county['lookup'].append({'name': {'en': l.get('name') or '', 'es': l.get('name_es') or l.get('name') or ''}, 'url': l['url']})
    rows = [c for c in (j.get('contests') or []) if c.get('office') and c.get('jurisdiction_type') != 'judicial'] + extra_contests(j, county_key)   # retention questions come from the SoS list (with question text)
    contests = [norm_contest(c, county_key, src, curated) for c in rows]
    seen = {}
    for c in contests:
        if c['id'] in seen:
            c['id'] = c['id'] + ':' + (c.get('county_id') or str(seen[c['id']]))
        seen[c['id']] = seen.get(c['id'], 0) + 1
    # Ballot styles: which contests share a ballot (from the county's sample-ballot types). Lets the app hide districts that never appear with the voter's city.
    bs = load_json(rel.replace('.json', '_ballot_styles.json'))
    if bs:
        known = {x['county_id'] for x in contests if x.get('county_id')}
        styles = []
        raw = bs.get('ballot_styles') or []
        for b in (raw.values() if isinstance(raw, dict) else raw):
            if not isinstance(b, dict): continue
            ids = [str(i) for i in (b.get('contest_ids') or []) if str(i) in known]
            ms = [str(m) for m in (b.get('measures') or b.get('measure_letters') or [])]
            if ids: styles.append({'c': ids, 'm': ms, 'a': b.get('areas') or []})
        county['styles'] = styles; county['styles_src'] = bs.get('src') or ''
    measures = [norm_measure(m, county_key, src) for m in (j.get('measures') or []) if m.get('letter') or m.get('title')]
    return county, contests, measures

# ---------- San Joaquin roster names ("Lodi USD Trustee Area 4", "Woodbridge Irrigation District, Division 3") ----------
ABBR = [(r'\bUSD\b', 'Unified School District'), (r'\bESD\b', 'Elementary School District'), (r'\bHSD\b', 'High School District'),
        (r'\bJoint SD\b', 'Joint School District'), (r'\bSD\b', 'School District'), (r'\bCCD\b', 'Community College District'),
        (r'\bBOE\b', 'County Board of Education'), (r'\bS\.J\.(?=\s|$)', 'San Joaquin'), (r'\bSJ\b', 'San Joaquin'), (r'\bCSD\b', 'Community Services District')]
def expand(name):
    for rx, rep in ABBR: name = re.sub(rx, rep, name)
    return name
def parse_roster_name(rn, seats):
    name = rn.strip(); term = ''
    m = re.search(r'\s+(Unexpired Term|Unexpired)$', name, re.I)
    if m: term = 'Unexpired term'; name = name[:m.start()]
    m = re.match(r'^(.*?),?\s+(?:Trustee )?Area\s+(\d+)$', name)
    if m:
        juris = expand(m.group(1)); d = m.group(2); office = f'Board Member Trustee Area {d}'
    else:
        m = re.match(r'^(.*?),?\s+Division\s+([\dIVX]+)$', name)
        if m: juris = expand(m.group(1)); d = m.group(2); office = f'Board Member Division {d}'
        else: juris = expand(name); d = None; office = 'Board Member'
    low = juris.lower()
    if 'community college' in low: jt = 'college'
    elif 'board of education' in low: jt = 'school'
    elif 'school district' in low: jt = 'school'
    else: jt = 'special'
    if term: office += ' (unexpired term)'
    return {'jurisdiction_type': jt, 'jurisdiction': juris, 'office': office, 'district': d, 'seats': seats, 'term': term or '4 years'}

SJ_AIL_NOTE_SCHOOL = {'en': 'Not on the ballot. The county roster marks this contest “On Ballot: No”: the number of qualified candidates did not exceed the seats. Under the Education Code (§5328) the nominee is seated at the board’s organizational meeting in December without an election. Confirm with the district.',
                      'es': 'No está en la boleta. La lista del condado marca esta contienda como “On Ballot: No”: el número de candidatos calificados no superó los escaños. Según el Código de Educación (§5328), la persona nominada toma posesión en la reunión de organización de la junta en diciembre, sin elección. Confírmalo con el distrito.'}
SJ_AIL_NOTE = {'en': 'Not on the ballot. The county roster marks this contest “On Ballot: No”: the number of qualified candidates did not exceed the seats, so under the Elections Code the governing board appoints the nominee in lieu of an election. Confirm with the district.',
               'es': 'No está en la boleta. La lista del condado marca esta contienda como “On Ballot: No”: el número de candidatos calificados no superó los escaños, así que según el Código Electoral la junta nombra a la persona nominada en lugar de una elección. Confírmalo con el distrito.'}
SJ_NOCAND_NOTE = {'en': 'Listed in the county Notice of Election, but no qualified candidate filed by the Aug 20, 2026 roster. The governing body fills the seat by appointment.',
                  'es': 'Aparece en el Aviso de Elección del condado, pero ningún candidato calificado se registró al 20 de agosto de 2026. El órgano de gobierno cubre el escaño por nombramiento.'}
ALA_NOB_NOTE = {'en': 'Not on the ballot. The county candidate list marks this race “Not On Ballot” because qualified candidates did not exceed the open seats. School-district nominees are seated at the board’s December organizational meeting (Education Code §5328); city and special-district boards appoint the nominee in lieu of an election (Elections Code). Confirm with the district or city.',
                'es': 'No está en la boleta. La lista de candidatos del condado marca esta contienda como “Not On Ballot” porque los candidatos calificados no superaron los escaños. En los distritos escolares la persona nominada toma posesión en la reunión de organización de diciembre (Código de Educación §5328); los concejos y distritos especiales la nombran en lugar de una elección (Código Electoral). Confírmalo con el distrito o la ciudad.'}
def extra_contests(j, county_key):
    """Contests the county keeps off the ballot (appointment in lieu, no candidate): the directory shows them, the personal ballot does not."""
    out = []
    for c in (j.get('appointed_in_lieu') or []):
        base = parse_roster_name(c.get('roster_name') or '', int(c.get('seats') or 1))
        note = SJ_AIL_NOTE_SCHOOL if base['jurisdiction_type'] in ('school', 'college') else SJ_AIL_NOTE
        base.update({'src': c.get('src'), 'candidates': c.get('candidates') or [], 'on_ballot': False, 'status': 'appointed_in_lieu', 'status_note': note, 'id': 'ail-' + str(c.get('county_contest_id') or slug(c.get('roster_name')))})
        out.append(base)
    for c in (j.get('no_candidate_contests') or []):
        if re.search(r'superior court', c.get('contest') or '', re.I):
            out.append({'jurisdiction_type': 'county_office', 'jurisdiction': f'{county_key} County Superior Court', 'office': f"Judge of the Superior Court ({c.get('seats') or 7} seats)", 'district': None, 'seats': int(c.get('seats') or 7), 'term': '6 years',
                        'src': c.get('src'), 'candidates': [], 'on_ballot': False, 'status': 'judicial_uncontested', 'id': 'superior-court', 'office_key_override': 'superior_court_judge',
                        'status_note': {'en': 'Not on the ballot. The county Notice of Election lists these judgeships subject to Elections Code §8203: no one filed to run against the incumbent judges, so the seats do not appear on the ballot and the incumbents are declared elected. The county notice does not print their names.',
                                        'es': 'No está en la boleta. El Aviso de Elección del condado lista estas judicaturas sujetas al Código Electoral §8203: nadie se postuló contra los jueces titulares, así que los escaños no aparecen en la boleta y los titulares se declaran electos. El aviso del condado no imprime sus nombres.'}})
            continue
        base = parse_roster_name(c.get('contest') or '', int(c.get('seats') or 1))
        base.update({'src': c.get('src'), 'candidates': [], 'on_ballot': False, 'status': 'no_candidate', 'status_note': SJ_NOCAND_NOTE, 'id': 'nocand-' + slug(c.get('contest'))})
        out.append(base)
    for c in (j.get('not_on_ballot_contests') or []):
        base = dict(c); base.update({'on_ballot': False, 'status': 'not_on_ballot', 'status_note': ALA_NOB_NOTE})
        out.append(base)
    return out

# ---------- SoS certified list → statewide / house / senate / assembly races ----------
def load_sos(curated):
    j = load_json('sos_certified.json')
    if not j: return {}, {}, {}, {}, []
    src = j.get('source_url') or ''
    statewide, house, senate, assembly, boe = [], {}, {}, {}, {}
    for c in (j.get('contests') or []):
        office = (c.get('office') or '').strip(); dist = c.get('district')
        cands_raw = c.get('candidates') or []
        key_prefix = slug(office) + (':' + str(dist) if dist else '')
        cands = [norm_candidate(x, key_prefix, src, curated) for x in cands_raw if x.get('name')]
        if not cands: continue
        low = office.lower()
        if re.search(r'house|representative|congress', low) and dist:
            house['CA%02d' % int(dist)] = {'source_url': src, 'candidates': cands}
        elif 'senat' in low and dist:
            senate['CA%02d' % int(dist)] = {'source_url': src, 'candidates': cands, 'office': bi(f'State Senator, District {int(dist)}', ES_OFFICE), 'office_key': 'state_senate'}
        elif 'assembly' in low and dist:
            assembly['CA%02d' % int(dist)] = {'source_url': src, 'candidates': cands, 'office': bi(f'State Assembly, District {int(dist)}', ES_OFFICE), 'office_key': 'assembly'}
        elif 'governor' == low:
            continue  # the governor record is built in build.py from these names plus curated positions
        elif 'equalization' in low and dist:
            boe[str(int(dist))] = {'source_url': src, 'candidates': cands, 'covers': c.get('covers_counties') or []}
        else:
            ck = office_key({'office': office, 'jurisdiction_type': 'statewide'})
            statewide.append({'id': 'sw:' + slug(office) + (':' + str(dist) if dist else ''), 'type': 'statewide', 'level': LEVEL['statewide'],
                              'juris': {'en': 'State of California', 'es': 'Estado de California'}, 'office': bi(office + (f', District {dist}' if dist else ''), ES_OFFICE),
                              'district': str(dist) if dist else None, 'seats': 1, 'term': '4 years', 'office_key': ck, 'src': src,
                              'election': {'en': 'November 3, 2026 General Election', 'es': 'Elección general del 3 de noviembre de 2026'}, 'candidates': cands})
    return statewide, house, senate, assembly, boe, (j.get('retention_justices') or []), j

def retention_contests(retention, county_key, src):
    """Judicial retention (yes/no) questions that appear on this county's ballot: Supreme Court for everyone,
    Court of Appeal for the county's appellate district. Rendered as a contest so the office description shows."""
    groups = {}
    for r in retention:
        if county_key not in (r.get('applies_to_counties') or []): continue
        court = r.get('court') or ''
        key = 'supreme' if 'Supreme' in court else 'appeal'
        g = groups.setdefault(key, [])
        g.append({'id': f'{county_key}:judicial:{key}:{slug(r.get("name"))}', 'name': r.get('name') or '', 'party': 'nonp',
                  'desig': {'en': (r.get('title_in_question') or 'Justice') + (f', {r["appellate_district"]}' if r.get('appellate_district') else '') + (f', Division {r["division"]}' if r.get('division') else ''), 'es': ''},
                  'src': src, 'review': 'reviewed', 'retention': True, 'question': r.get('question_as_printed') or ''})
    out = []
    for key, cands in groups.items():
        dist = next((r.get('appellate_district') for r in retention if county_key in (r.get('applies_to_counties') or []) and (('Supreme' in (r.get('court') or '')) == (key == 'supreme'))), None)
        dist_lbl = (dist or '') if not dist or 'district' in dist.lower() else f'{dist} Appellate District'
        office = 'Supreme Court of California — retention' if key == 'supreme' else f'Court of Appeal, {dist_lbl} — retention'
        out.append({'id': f'{county_key}:judicial:{key}', 'type': 'judicial', 'level': LEVEL['judicial'],
                    'juris': {'en': 'State of California', 'es': 'Estado de California'},
                    'office': {'en': office, 'es': ('Corte Suprema de California — retención' if key == 'supreme' else f'Corte de Apelaciones, {dist_lbl} — retención')},
                    'district': None, 'seats': len(cands), 'term': '12 years', 'rcv': False, 'status': 'retention', 'on_ballot': True,
                    'office_key': 'supreme_court_retention' if key == 'supreme' else 'appeals_court_retention', 'src': src,
                    'election': {'en': 'November 3, 2026 General Election', 'es': 'Elección general del 3 de noviembre de 2026'},
                    'note': {'en': 'Retention question: a YES vote keeps the justice for another term; a NO vote removes them. There is no opponent.', 'es': 'Pregunta de retención: un voto SÍ mantiene al juez por otro mandato; un voto NO lo remueve. No hay oponente.'},
                    'candidates': cands})
    return out

def load_offices():
    j = load_json('offices.json') or {}
    return j.get('offices') or {}, j.get('concepts') or {}

CITY_COUNTY = {'San Joaquin': ['Stockton', 'Lodi', 'Manteca', 'Tracy', 'Lathrop', 'Ripon', 'Escalon', 'Mountain House'],
               'Alameda': ['Alameda', 'Albany', 'Berkeley', 'Dublin', 'Emeryville', 'Fremont', 'Hayward', 'Livermore', 'Newark', 'Oakland', 'Piedmont', 'Pleasanton', 'San Leandro', 'Union City']}
ZIP_OVERRIDES = {
 # ZCTA 95391 is mostly unpopulated Alameda County hills by land area; the community of Mountain House is in San Joaquin County (city site, county roster).
 '95391': {'county': 'San Joaquin', 'assembly': ['13', '16'], 'note': 'County set from the City of Mountain House; land-area share would say Alameda.'},
}
def load_zips():
    j = load_json('zips_local.json') or {}
    zips = j.get('zips') or {}
    # research/district_hints.json: for a ZIP that crosses a district line, which part of the ZIP each district covers (en/es), so the picker can say more than a number.
    hints = (load_json('district_hints.json') or {}).get('hints') or {}
    out = {}
    for z, v in zips.items():
        places = [p for p in (v.get('places') or []) if p.get('name')]
        places.sort(key=lambda p: (p.get('type') != 'city', -(p.get('share') or 0)))   # the incorporated city is where the voters are
        county = v.get('county') or ''
        for p in places:   # county rule: a ZIP that contains one of a county's cities belongs to that county for ballot purposes
            if p.get('type') == 'city':
                hit = next((c for c, cities in CITY_COUNTY.items() if p['name'] in cities), None)
                if hit: county = hit
                break
        o = {'county': county, 'places': [{'name': p['name'], 'type': p.get('type') or 'cdp'} for p in places],
             'ad': [str(x) for x in (v.get('assembly') or [])], 'sd': [str(x) for x in (v.get('senate') or [])]}
        if v.get('other_county'): o['other_county'] = v['other_county']
        ov = ZIP_OVERRIDES.get(z)
        if ov:
            o['county'] = ov.get('county', o['county']); o['ad'] = ov.get('assembly', o['ad']); o['note'] = ov.get('note', '')
        h = hints.get(z) or {}
        hz = {}
        for kind in ('cd', 'ad', 'sd'):
            kept = {d: {'en': t['en'], 'es': t.get('es') or t['en']} for d, t in (h.get(kind) or {}).items() if t.get('en')}
            if kept: hz[kind] = kept
        if hz: o['hints'] = hz
        if o['county'] in CITY_COUNTY: out[z] = o   # only ZIPs whose ballot county is covered
    return out
