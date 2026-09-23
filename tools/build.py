#!/usr/bin/env python3
"""Merge researcher JSON -> data/ballot-2026.json + data/reps.json, inject CA seed into the app HTML.
Robust to missing inputs: run again as more research lands."""
import json, os, re, sys, datetime, glob

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

# ---------- Mountain House local ballot (verified 2026-09-18; see NOTES.md) ----------
SJC = 'https://www.sjgov.org/department/rov/election-information/current_election'
LOCAL_95391 = [
 {'id':'council','level':{'en':'Local','es':'Local'},'office':{'en':'Mountain House City Council (At-Large)','es':'Concejo de Mountain House (general)'},'seats':2,'src':'https://www.mountainhouseca.gov/445/November-3-2026-Candidate-Log','candidates':[
  {'id':'council:ronnagreen','name':'Ronna Green','party':'nonp','cls':'','desig':{'en':'City of Mountain House Council Member','es':'Concejal de Mountain House'},'bio':{'en':'Current council member and Vice Mayor; business owner; resident since 2005.','es':'Concejal actual y vicealcaldesa; empresaria; residente desde 2005.'},'summary':{'en':'Streets, public safety, housing costs, downtown, water.','es':'Calles, seguridad, costo de vivienda, centro, agua.'},'site':'https://ronnagreen.org/','src':'https://ronnagreen.org/',
   'pos':{'streets':{'en':'Improve streets, strengthen public safety, address housing affordability, reimagine downtown.','es':'Mejorar calles, reforzar la seguridad, atender el costo de la vivienda, renovar el centro.'},'water':{'en':'Bring investment for reliable water infrastructure.','es':'Atraer inversión para una infraestructura de agua confiable.'},'roads':{'en':'Advocate in Washington for safer roads and better connectivity.','es':'Gestionar en Washington carreteras más seguras y mejor conectividad.'}}},
  {'id':'council:happygrewal','name':'Happy Grewal','party':'nonp','cls':'b','desig':{'en':'Business Owner/Farmer','es':'Empresario/Agricultor'},'bio':{'en':'Small business owner and farmer; resident for over a decade.','es':'Dueño de pequeño negocio y agricultor; residente por más de una década.'},'summary':{'en':'Safe neighborhoods, smart growth, parks and local commerce.','es':'Vecindarios seguros, crecimiento inteligente, parques y comercio local.'},'site':'https://happygrewal.pages.dev/','src':'https://happygrewal.pages.dev/',
   'pos':{'safety':{'en':'Support first responders, safe school corridors, neighborhood safety partnerships.','es':'Apoyar a los socorristas, corredores escolares seguros, alianzas vecinales de seguridad.'},'growth':{'en':'Thoughtful planning, balanced budgets, modern infrastructure.','es':'Planificación cuidadosa, presupuestos equilibrados, infraestructura moderna.'},'community':{'en':'Family parks, local commerce, recreation, and events.','es':'Parques familiares, comercio local, recreación y eventos.'}}},
  {'id':'council:arjunjuturu','name':'Arjun Juturu','party':'nonp','cls':'c','desig':{'en':'Engineer/Business Owner','es':'Ingeniero/Empresario'},'bio':{'en':'Challenger. Filed a county candidate statement (July 2026).','es':'Aspirante. Presentó declaración de candidato al condado (julio 2026).'},'nopos':True,'src':SJC},
  {'id':'council:nadershareghi','name':'Nader Shareghi','party':'nonp','cls':'d','desig':{'en':'Engineer/Assistant Manager','es':'Ingeniero/Subgerente'},'bio':{'en':'Former Mountain House CSD public works director; 16 years as a Stockton city engineer.','es':'Ex director de obras públicas del CSD de Mountain House; 16 años como ingeniero de la ciudad de Stockton.'},'nopos':True,'src':SJC},
  {'id':'council:bernicekingtingle','name':'Bernice King Tingle','party':'nonp','cls':'','desig':{'en':'City of Mountain House Council Member','es':'Concejal de Mountain House'},'bio':{'en':'Current council member; original CSD board member (2008); the city’s first Vice Mayor.','es':'Concejal actual; miembro original de la junta del CSD (2008); primera vicealcaldesa de la ciudad.'},'nopos':True,'src':SJC},
  {'id':'council:sureshvuyyuru','name':'Suresh Vuyyuru','party':'nonp','cls':'b','desig':{'en':'Parent/Engineer/Farmer','es':'Padre/Ingeniero/Agricultor'},'bio':{'en':'Software engineer and farmer; ran for CSD board (2022) and council (2024).','es':'Ingeniero de software y agricultor; candidato a la junta del CSD (2022) y al concejo (2024).'},'nopos':True,'src':SJC}]},
 {'id':'lusd','level':{'en':'Local','es':'Local'},'office':{'en':'Lammersville Unified School Board, Trustee Area 4','es':'Junta Escolar de Lammersville, Área 4'},'seats':1,'src':SJC,'note':{'en':'Only voters living in Trustee Area 4 (northern Mountain House) see this race.','es':'Solo los votantes del Área 4 (norte de Mountain House) ven esta contienda.'},'candidates':[
  {'id':'lusd:vanithadaniel','name':'Vanitha Daniel','party':'nonp','cls':'c','desig':{'en':'Mother/Educator/Entrepreneur','es':'Madre/Educadora/Emprendedora'},'bio':{'en':'Current school board trustee (since 2022); educator.','es':'Miembro actual de la junta escolar (desde 2022); educadora.'},'nopos':True,'src':SJC},
  {'id':'lusd:stephanieolsen','name':'Stephanie Olsen','party':'nonp','cls':'d','desig':{'en':'Education Attorney/Parent','es':'Abogada de educación/Madre'},'bio':{'en':'Current trustee (appointed 2024); board clerk; education attorney.','es':'Miembro actual (nombrada en 2024); secretaria de la junta; abogada de educación.'},'nopos':True,'src':SJC}]}
]
# Mountain House-specific CD-9 curated matchup (SoS certified list, Aug 27 2026) — overrides FEC for this district
HOUSE_CA09 = {'source_url':'https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf','candidates':[
 {'id':'house:joshharder','name':'Josh Harder','party':'Democratic','cls':'c','inc':'Incumbent','desig':{'en':'Father/Representative','es':'Padre/Representante'},'background':{'en':'Current U.S. Representative (since 2019); former venture-capital executive.','es':'Representante actual (desde 2019); ex ejecutivo de capital de riesgo.'},'summary':{'en':'Cheaper prescriptions, repeal gas taxes, homelessness as an emergency.','es':'Medicinas más baratas, eliminar impuestos a la gasolina, emergencia por personas sin hogar.'},'site':'https://harderforcongress.com/','src':'https://harderforcongress.com/issues/',
  'positions':[{'topic':'cost','statement':{'en':'Cut prescription drug costs, repeal gas taxes, get housing costs under control.','es':'Bajar el costo de las medicinas, eliminar impuestos a la gasolina, controlar el costo de la vivienda.'},'url':'https://harderforcongress.com/issues/'},{'topic':'health','statement':{'en':'A $35 monthly cap on insulin; bring more doctors to the Valley.','es':'Tope de $35 al mes para la insulina; más médicos para el Valle.'},'url':'https://harderforcongress.com/issues/'},{'topic':'homeless','statement':{'en':'Treat homelessness as an emergency: mental health, addiction services, job training.','es':'Tratar la falta de vivienda como emergencia: salud mental, adicciones, capacitación laboral.'},'url':'https://harderforcongress.com/issues/'}]},
 {'id':'house:johnmcbride','name':'John McBride','party':'Republican','cls':'','desig':{'en':'Athletic Performance Coach','es':'Entrenador de rendimiento deportivo'},'background':{'en':'Strength and conditioning coach; ran in the 2024 primary.','es':'Entrenador de fuerza y acondicionamiento; candidato en la primaria de 2024.'},'summary':{'en':'Lower taxes, smaller government, no tax on Social Security.','es':'Menos impuestos, gobierno más pequeño, sin impuesto al Seguro Social.'},'site':'https://www.johnmcbrideforcongress.com/','src':'https://www.johnmcbrideforcongress.com/',
  'positions':[{'topic':'taxes','statement':{'en':'Reduce taxes, shrink government spending, no tax on Social Security.','es':'Reducir impuestos, recortar el gasto público, sin impuesto al Seguro Social.'},'url':'https://www.johnmcbrideforcongress.com/'},{'topic':'health','statement':{'en':'Remove dangerous chemicals from food and water.','es':'Eliminar químicos peligrosos de los alimentos y el agua.'},'url':'https://www.johnmcbrideforcongress.com/'},{'topic':'safety','statement':{'en':'Support local police, a stronger border, water rights, less regulation on small farms.','es':'Apoyar a la policía local, frontera más fuerte, derechos de agua, menos regulación a granjas pequeñas.'},'url':'https://www.johnmcbrideforcongress.com/'}]}]}
# State Assembly 13 stays as a local race for 95391/Tracy ZIPs (not statewide)
ASSEMBLY_13 = {'id':'assembly','level':{'en':'State','es':'Estatal'},'office':{'en':'State Assembly, District 13','es':'Asamblea Estatal, Distrito 13'},'seats':1,'src':'https://elections.cdn.sos.ca.gov/sov/2026-primary/sov/95-state-assembly.pdf','candidates':[
 {'id':'assembly:rhodesiaransom','name':'Rhodesia Ransom','party':'Democratic','cls':'d','inc':'Incumbent','desig':{'en':'State Assemblymember','es':'Asambleísta estatal'},'bio':{'en':'Current Assemblymember (since 2024); former Tracy City Councilmember.','es':'Asambleísta actual (desde 2024); ex concejal de Tracy.'},'summary':{'en':'Local jobs, renters’ internet costs, Family Justice Centers.','es':'Empleos locales, internet para inquilinos, Centros de Justicia Familiar.'},'site':'https://voteransom.com/','src':'https://voteransom.com/results',
  'pos':{'cost':{'en':'Protected 1,000+ local manufacturing jobs; ended forced high-cost internet contracts for renters.','es':'Protegió más de 1,000 empleos de manufactura; eliminó contratos de internet caros y obligatorios para inquilinos.'},'safety':{'en':'$10 million for Family Justice Centers; tougher penalties for trafficking and drunk driving.','es':'$10 millones para Centros de Justicia Familiar; penas más duras por trata y conducir ebrio.'},'emerg':{'en':'Improved wildfire response; $20 million to protect the Delta from invasive species.','es':'Mejoró la respuesta a incendios; $20 millones para proteger el Delta de especies invasoras.'}}},
 {'id':'assembly:tompatti','name':'Tom Patti','party':'Republican','cls':'b','desig':{'en':'Businessman/Father','es':'Empresario/Padre'},'bio':{'en':'Former San Joaquin County Supervisor (2017–2025); business owner.','es':'Ex supervisor del condado de San Joaquin (2017–2025); empresario.'},'summary':{'en':'Suspend gas taxes, parents’ rights, backed Prop 36.','es':'Suspender impuestos a la gasolina, derechos de los padres, apoyó la Prop 36.'},'src':'https://www.sjgov.org/docs/default-source/registrar-of-voters-documents/candidates/historical-county-voter-information-guides/2026-primary-composite-civg-(english).pdf',
  'pos':{'energy':{'en':'Lower energy costs and suspend gas taxes.','es':'Bajar los costos de energía y suspender los impuestos a la gasolina.'},'education':{'en':'Protect parents’ rights in schools; girls’ sports for girls only.','es':'Proteger los derechos de los padres en las escuelas; deportes femeninos solo para niñas.'},'housing':{'en':'Smart growth for affordable housing without government overreach; backed Prop 36 on retail theft.','es':'Crecimiento inteligente para vivienda asequible sin exceso de gobierno; apoyó la Prop 36 contra el robo en tiendas.'}}}]}

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


GOV_CA = {'source_url':'https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf','primary_held':True,'notes':'Top two from the June 2, 2026 primary.','candidates':[
 {'id':'gov:xavierbecerra','name':'Xavier Becerra','party':'Democratic','cls':'','desig':{'en':'Voting Rights Attorney','es':'Abogado de derechos electorales'},'background':{'en':'Former U.S. Secretary of Health and Human Services; former California Attorney General.','es':'Ex secretario de Salud de EE. UU.; ex fiscal general de California.'},'summary':{'en':'Housing emergency, price-gouging crackdown, lower drug prices.','es':'Emergencia de vivienda, freno a precios abusivos, medicinas más baratas.'},'site':'https://www.xavierbecerra2026.com/','src':'https://www.xavierbecerra2026.com/',
  'positions':[{'topic':'housing','statement':{'en':'Declare the housing shortage a state emergency; reform building fees statewide.','es':'Declarar emergencia estatal por la escasez de vivienda; reformar las tarifas de construcción.'},'url':'https://www.xavierbecerra2026.com/priorities/housing/'},{'topic':'cost','statement':{'en':'Stand up to price gouging and unjustified rate hikes; expand child-care help.','es':'Enfrentar precios abusivos y alzas injustificadas; ampliar ayuda para cuidado infantil.'},'url':'https://www.xavierbecerra2026.com/priorities/economy-and-affordability/'},{'topic':'health','statement':{'en':'Protect everyone’s coverage; negotiate lower drug prices for state programs.','es':'Proteger la cobertura de todos; negociar medicinas más baratas en programas estatales.'},'url':'https://www.xavierbecerra2026.com/priorities/health-care/'}]},
 {'id':'gov:stevehilton','name':'Steve Hilton','party':'Republican','cls':'b','desig':{'en':'Small Business Owner','es':'Dueño de pequeño negocio'},'background':{'en':'Former senior adviser to a British prime minister; former Fox News host.','es':'Ex asesor de un primer ministro británico; ex presentador de Fox News.'},'summary':{'en':'No income tax on first $150K, $3 gas, starter homes.','es':'Sin impuesto sobre los primeros $150K, gasolina a $3, casas iniciales.'},'site':'https://stevehiltonforgovernor.com/','src':'https://stevehiltonforgovernor.com/plan',
  'positions':[{'topic':'taxes','statement':{'en':'No state income tax on the first $150,000 you earn.','es':'Sin impuesto estatal sobre los primeros $150,000 que ganes.'},'url':'https://stevehiltonforgovernor.com/plan'},{'topic':'energy','statement':{'en':'End the rules and fees behind high gas prices; cut utility bills in half.','es':'Eliminar las reglas y tarifas que encarecen la gasolina; reducir a la mitad las facturas de servicios.'},'url':'https://stevehiltonforgovernor.com/plan'},{'topic':'housing','statement':{'en':'Clear red tape and fees so starter homes for young families get built.','es':'Eliminar trabas y tarifas para que se construyan casas iniciales para familias jóvenes.'},'url':'https://stevehiltonforgovernor.com/plan'}]}]}

# ---------- merge ----------
D = {'generated': TODAY, 'election': '2026-11-03', 'races': {'governor': {}, 'senate': {}, 'house': {}}, 'measures': {}, 'measures_meta': {}, 'local': {}, 'deadlines': {}, 'official': OFFICIAL, 'updates': UPDATES, 'sources': {}, 'coverage': {}}
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

# California overrides from the verified v3 build (official guide) if the agent file lacks them
if not D['measures'].get('CA'):
    print('  WARNING: no California propositions found in research/ — the CA seed will ship empty.')
D['races']['governor'].setdefault('CA', GOV_CA)
D['races']['house']['CA09'] = HOUSE_CA09
D['local']['95391'] = LOCAL_95391 + [ASSEMBLY_13]
for z in ['95376','95377','95304']:  # Tracy ZIPs share AD-13 (not the MH council race)
    D['local'].setdefault(z, [ASSEMBLY_13])
D['deadlines'] = {'CA': DEADLINES_CA, 'default': DEADLINES_DEFAULT}

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
D['coverage'] = {'governor_states': sorted(D['races']['governor']), 'senate_states': sorted(D['races']['senate']), 'measure_states': sorted(k for k, v in D['measures'].items() if v), 'local_zips': sorted(D['local'])}

with open(os.path.join(OUT, 'ballot-2026.json'), 'w', encoding='utf-8') as f: json.dump(D, f, ensure_ascii=False, separators=(',', ':'))
with open(os.path.join(OUT, 'reps.json'), 'w', encoding='utf-8') as f: json.dump(reps, f, ensure_ascii=False, separators=(',', ':'))

# ---------- inject CA seed into HTML ----------
seed = {'generated': TODAY, 'election': D['election'], 'races': {'governor': {'CA': D['races']['governor']['CA']}, 'senate': {}, 'house': {'CA09': HOUSE_CA09}}, 'measures': {'CA': D['measures'].get('CA', [])}, 'local': {'95391': D['local']['95391']}, 'deadlines': D['deadlines'], 'official': OFFICIAL, 'updates': UPDATES, 'sources': D['sources'], 'coverage': D['coverage']}
html_path = os.path.join(ROOT, 'ballot-buddy-app.html')
html = open(html_path, encoding='utf-8').read()
seed_txt = json.dumps(seed, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
html = re.sub(r'<script type="application/json" id="seed">.*?</script>', lambda m: '<script type="application/json" id="seed">' + seed_txt + '</script>', html, flags=re.S)
open(html_path, 'w', encoding='utf-8').write(html)

sizes = {n: os.path.getsize(os.path.join(OUT, n)) for n in ['ballot-2026.json', 'reps.json']}
print('\ncoverage:', json.dumps({k: len(v) for k, v in D['coverage'].items()}))
print('sizes:', sizes, '| html:', os.path.getsize(html_path))
