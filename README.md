# Ballot Buddy

**Use your buddy to cast your ballot.**

A free, nonpartisan voter-education app for voters 18+. Enter any U.S. ZIP code and see your ballot: candidates and measures explained in plain English, the deadlines that matter in your county, and a swipe-to-compare that matches your views to what candidates actually said.

Only 23% of voters aged 18–29 turned out in the 2022 midterms. The reason usually isn't apathy. It's confusing ballot language, missed deadlines, and not knowing which sources to trust. Ballot Buddy is built to remove all three.

---

## Try it

**Live demo:** https://seelamrdheeraj.github.io/ballot-buddy/

Enter any ZIP in **San Joaquin County or Alameda County, California** (for example **95391**, Mountain House, or **94601**, Oakland) to see every contest on the November 3, 2026 ballot there, from Governor down to school boards and special districts, with the county's own dates and official links. Any other U.S. ZIP shows the statewide races and the U.S. House race pulled live from the Federal Election Commission.

On a phone, open that link and tap **Share → Add to Home Screen** (iPhone) or **menu → Install app** (Android). It runs full screen, like a native app.

---

## What it does

- **Your ballot by ZIP.** Any ZIP in the U.S. Your congressional district is looked up from Census data; House candidates load live from the FEC.
- **Match.** Swipe agree or disagree on real statements from candidates on your ballot, with names hidden. At the end you see how often you overlapped with each candidate. Overlap is shown as a number, never as a recommendation.
- **Follow.** Follow your representatives and see their recorded votes next to what they promised in their own words. We show both; you decide.
- **County directory.** Every contest and candidate the county lists, searchable, each labeled *Contested*, *Running unopposed*, *Not on the ballot · appointment in lieu of election*, *Not on the ballot* or *No candidate filed*, with the county's own wording for why. A candidate is never dropped for lacking an opponent, a website, or a statement.
- **Plain-English measures.** Every measure in three bullets, plus what a YES and a NO vote each mean and what it costs. The official text is one tap away.
- **Deadlines that actually remind you.** One tap adds any deadline to your phone's calendar with a day-before alert.
- **Learn.** Two-minute reads, then direct links to your state and county election offices, your school district, and your FEC district page.
- **English and Spanish**, plus text-to-speech on every summary.
- **BallotBot.** An AI assistant that knows your ZIP, your ballot, and your swiped interests, and answers in plain language. It explains; it never tells you how to vote.

---

## Coverage

Every state on the November 3, 2026 ballot, verified against official sources as of September 22, 2026.

| | Covered |
|---|---|
| **Governor** | All **36** states holding a 2026 race |
| **U.S. Senate** | All **35** races — the 33 Class 2 seats plus the Florida and Ohio specials |
| **U.S. House** | Any district, live from the FEC |
| **Statewide measures** | All **50** states checked: **145 measures across 39 states**, and 11 states confirmed to have none |
| **California statewide** | Governor plus Lieutenant Governor, Secretary of State, Controller, Treasurer, Attorney General, Insurance Commissioner, Superintendent of Public Instruction, Board of Equalization, and the Supreme Court and Court of Appeal retention questions, from the Secretary of State's certified list |
| **Local races** | **San Joaquin County** (144 contests, 229 candidates, 4 local measures) and **Alameda County** (136 contests, 314 candidates, 28 local measures): every contest the county Registrars list for November 3, 2026, including seats that are unopposed, filled by appointment in lieu of election, or have no candidate. Your personal ballot shows only the races you can vote in; the **County directory** shows everything. |

The 11 states with no statewide measures this year are Connecticut, Delaware, Illinois, Maine, Mississippi, New Jersey, New York, Oregon, Pennsylvania, South Carolina, and Texas. The app says "no statewide measures on your ballot" there — and says something different, on purpose, if a state were ever left unverified.

---

## Where the data comes from

Every candidate, measure, and date traces back to a source. Nothing is invented.

| What | Source |
|---|---|
| ZIP → congressional district | U.S. Census Bureau, ZCTA-to-Congressional-District relationship file |
| U.S. House candidates (any district) | Federal Election Commission public API, live |
| California Governor and CA-9 House candidates | CA Secretary of State certified list (Aug 27, 2026) |
| Governor and U.S. Senate candidates in every other state | Each state's Secretary of State or election-division certified candidate list |
| San Joaquin and Alameda County contests and measures | San Joaquin County Registrar of Voters (Local Candidate Roster, Aug 20, 2026; County Voter Information Guide sample ballots) and Alameda County Registrar of Voters (Candidate List, Measures list, County Voter Information Guide) |
| Candidate websites | Only as printed on the Secretary of State's Official Candidate Contact List or the county's candidate list, or verified by us as belonging to that candidate for that race. Otherwise the app says no verified website was found. It never guesses an address. |
| Candidate positions | Each candidate's own campaign website or official candidate statement, with a link, date and context on every position, labelled "Candidate's stated position". Board and roll-call votes are labelled "Public record" and link to the minutes or roll call. |
| What each office does | Plain-language descriptions, each citing an official or civic source (state, county, city, school-board association) |
| ZIP → county, city, Assembly and Senate districts | U.S. Census Bureau 2020 ZCTA relationship files (county, place, 2021 legislative districts); ZIPs that span districts ask the voter to pick |
| Statewide ballot measures | Each state's official ballot-measure page, voter guide, and legislative fiscal note |
| California propositions | Official Voter Information Guide (certified Aug 10, 2026) and the Legislative Analyst's Office |
| Deadlines | CA Secretary of State and the San Joaquin County Registrar of Voters |
| Mountain House local races | City candidate log and county qualified-candidate roster |
| Representatives' promises | Their own campaign and official sites |

A **Sources** button inside the app lists these, and every candidate and measure screen links out to its original source.

**Nonpartisan by design.** Ballot Buddy does not endorse candidates or measures. Positions are quoted or closely paraphrased from what each candidate published themselves, with no characterization added.

---

## Known limits

Stated honestly here, and flagged inside the app too.

- **FEC data lists everyone who filed**, including candidates who lost their primary. The app says so. Your state's certified list is the final word.
- **Six states redrew districts for 2026** (CA, TX, MO, NC, OH, UT). The Census table reflects the older map, so the app shows a warning in those states. Mountain House and Tracy are verified against the new California map.
- **Positions are loaded for a small set of candidates.** Governor, U.S. House CA-9, Assembly District 13, Mountain House City Council and Lammersville USD (Trustee Areas 4 and 5) have sourced positions; the Lammersville candidates also carry county campaign-finance filings, organization-published endorsements, board attendance and vote records, and paraphrased statements from Mountain House Matters interviews and its Sept 30, 2026 forum. Every other candidate in both counties shows name, party where the office is partisan, ballot designation, incumbency where the county printed it, and a website only where an official list printed one. Those candidates are marked **Not yet reviewed**, with a link to the official list. Nothing is inferred from social media.
- **Unopposed seats are explained, not hidden.** San Joaquin's roster marks 75 contests "On Ballot: No" (appointment in lieu of election) and its Notice of Election lists 13 seats with no qualified candidate; Alameda's list marks 30 races "Not On Ballot" and 9 on-ballot races have one candidate per seat. The directory shows all of them with the county's wording. Whether a given board has actually made its appointment is not tracked.
- **Your exact districts need your address.** A ZIP can span several Assembly, Senate, supervisor, school or special districts. The app shows the ones your ZIP touches, asks you to pick where it can, and puts the rest under **Districts to confirm** with a link to your county's own lookup tool. In San Joaquin County, the county's ballot-style table is used to hide districts that never share a ballot with your city.
- **Mountain House (95391) is placed in San Joaquin County by rule.** The Census ZIP area is mostly unpopulated Alameda County hills; the community itself is in San Joaquin County, so the app uses that.
- **Vote records** are loaded for Josh Harder and Rhodesia Ransom, the two officials Mountain House voters can follow today. Other officials show promises and links until their records are compiled.
- **Spanish covers the app itself and the California ballot.** Buttons, labels, and every California candidate and proposition are translated. Candidate and measure text for other states is currently English only, so in Spanish mode you'll see Spanish around English content there.
- **Two candidate websites printed on official lists did not resolve when checked on October 8, 2026** (Stephanie Olsen's olsen4area4.com and Tom Patti's TomPatti13.com), and Vanitha Daniel's vanithadaniel4lusd.com, which appears in search results, does not resolve either. The app says so rather than linking to a dead or unrelated page.
- **Assembly District 13 candidate Tom Patti's positions come from his official candidate statement in the June 2026 primary guide**, because no live campaign site could be verified.
- **A few measure details are still unconfirmed**, and each says so where it appears. Ohio's Secretary of State blocked automated reading, so Issue 3 carries a notice that its exact certified wording wasn't verified. Rhode Island's five bond questions aren't numbered yet, so they're listed by name. Louisiana's amendment numbering comes from two news listings that agree, not from the state. Every one of these is recorded in `research/` with the reason.
- **Notifications** on a static site can't push to a locked phone. Calendar export gives you a real alert instead.
- **BallotBot** answers from built-in responses unless the app is opened through Claude, which supplies live AI answers.

Always confirm deadlines with your state or county election office. This is voter education, not legal advice.

---

## Run it yourself

No build step, no framework, no dependencies. Locally, one Python file serves the site, the app, and the registration API, and registrations are stored in a SQLite file next to it. Python 3.9 or newer is the only requirement. The same API code runs on Vercel for the public site (see below).

**1. Start the server.**

```bash
python3 server.py
```

**2. Open it.**

| Page | URL |
|---|---|
| App | `http://localhost:8765/` |
| Marketing site | `http://localhost:8765/ballot-buddy-site.html` |
| Create account / sign in | `http://localhost:8765/register.html` (add `#signin` for the sign-in form) |
| Admin (private) | `http://localhost:8765/admin.html` |

**Get started** on the site or in the app opens the account page: first name, last initial, age, email and a password (8+ characters), validated in the browser and again on the server. Signing in sets a 30-day HttpOnly cookie that renews on every visit, so the app stays signed in until **Sign out** in Profile. Your ZIP, district picks, language, text size, reminders, swipes, follows and the screen you were on are saved to your account after every change and restored when you open the app again, on the same phone or a new one. Profile lets you edit name, age, email and password (email and password changes ask for the current password) and change location without redoing setup. The admin page asks you to create a password the first time you open it, then lists sign-ups newest first; the list is never sent to anyone who hasn't signed in. To fix the admin password in advance instead, copy `.env.example` to `.env` and set `ADMIN_PASSWORD` (it overrides the stored one).

On a phone on the same Wi-Fi, use your computer's address instead of `localhost`, including the `http://`.

Options, as environment variables or lines in `.env`: `PORT` (default 8765), `BIND` (default 0.0.0.0), `BB_DB` (database path, default `registrations.db`), `BB_SECURE_COOKIE=1` when serving over HTTPS, `SESSION_SECRET` to pin the key that signs voter sessions (otherwise one is generated once and kept in the store). Admin sign-ins last 12 hours. `python3 tools/test_accounts.py http://localhost:8765` exercises every account route against a running server.

**Optional:** the FEC lookup uses the shared `DEMO_KEY`, which allows only about 10 requests an hour. For a free key with a higher limit, sign up at api.data.gov/signup and paste it into `FEC_KEY` near the top of the script in `ballot-buddy-app.html`.

### Files

| File | What it is |
|---|---|
| `ballot-buddy-app.html` | The app. Single file, vanilla JavaScript. |
| `data/ballot-2026.json` | Verified candidates, measures, deadlines, official links, office descriptions and the ZIP table for the two covered counties. |
| `data/local/*.json` | One file per covered county (contests, candidates, local measures, dates, links, ballot styles), fetched when a voter's ZIP is in that county. |
| `data/zip-cd.json` | ZIP code to congressional district table (33,000 ZIPs). |
| `data/reps.json` | Followed officials: promises, links, vote records. |
| `ballot-buddy-site.html` | Marketing website for the venture. |
| `register.html` | Create account / sign in: first name, last initial, age, email, password. |
| `admin.html` | Private admin page listing sign-ups, newest first. |
| `server.py` | Local server: static files plus the account API. Standard library only. |
| `bb_core.py` | The account API itself: validation, password hashing, voter and admin sessions, saved app state, SQLite and Vercel Blob storage. Shared by `server.py` and `api/`. |
| `api/` | Vercel Functions, one tiny file per route, all delegating to `bb_core.py`. |
| `vercel.json` | Keeps data and research files out of the function bundles. |
| `registrations.db` | SQLite database the server creates on first run: accounts, saved state, sign-up log (gitignored). |
| `.env.example` | Template for `.env`, which holds the admin password. |
| `index.html` | Redirects to the app so a bare URL opens it. |
| `icon.png`, `manifest.json` | Home-screen icon and install settings. |
| `research/` | The raw, sourced research each data file was built from. `counties/` holds each county Registrar's lists, `sos_certified.json` the state certified list, `offices.json` the office descriptions, `zips_local.json` the ZIP table, and `local_curated.json` the sourced bios, positions and verified websites. |
| `tools/counties.py` | Normalizes the county and state lists into the app's shape (used by `build.py`). |
| `tools/build.py` | Merges `research/` into `data/`. Run it after adding research. |
| `tools/validate.py` | Checks the merged data for missing sources, empty fields, and bad dates. |
| `NOTES.md` | Build notes, data pipeline, version history. |

### Updating the data

```bash
python3 tools/build.py && python3 tools/validate.py
```

`build.py` rebuilds `data/ballot-2026.json`, `data/local/*.json` and `data/reps.json` from everything in `research/`, and refreshes the California seed embedded in the app (statewide races, ZIP table, office descriptions) so the app renders even if a data fetch fails; county contests load from `data/local/`. `validate.py` checks every candidate for an official source, every website for a scheme and an official or verified origin, and every position for a source link, and exits non-zero if anything is broken, so it can gate a deploy.

---

## Deploy on Vercel (the public site)

The project is deployed on Vercel from the `main` branch, and Vercel runs the files in `api/` as Python functions, so accounts work on the public URL. Accounts, saved state and the sign-up log are stored in a **private Vercel Blob store** (included on the free plan). One-time setup:

1. **Connect storage.** Open the project in Vercel, go to **Storage**, choose **Create Database → Blob**, set access to **Private**, and connect it to the project. Vercel adds the store's variables to the project. Then **Redeploy** once (Deployments → ⋯ → Redeploy) so the functions see them.
2. **Create the admin password.** Open `/admin.html` on the live site. The first visit shows "Create the admin password"; set it and you are in. The password is stored as a salted hash in the same store, and nobody can set it again afterwards. Do this right after step 1, before sharing the link.

Until step 1 is done, the registration page says registration isn't set up yet, and the admin page says storage isn't connected. Setting an `ADMIN_PASSWORD` environment variable overrides the stored password (useful locally, or to recover if you forget it). Admin sign-ins last 12 hours and are tied to the password, so changing it signs everyone out.

## Publish it on GitHub Pages

GitHub Pages can host the site and the app, but not the registration API: on Pages, `register.html` and `admin.html` show a "not set up" message. Use the Vercel deployment above for the full app. The steps below publish the static part only.

1. Create a repository and push this folder to it.
2. In the repository, open **Settings → Pages**.
3. Under **Source**, choose **Deploy from a branch**, pick `main` and the `/ (root)` folder, and save.

The site goes live at `https://<your-username>.github.io/<repo-name>/` within a minute or two. `index.html` redirects to the app, so the bare URL opens it.

---

## The team

Ballot Buddy LLC, four student co-founders in Mountain House, California.

| Name | Role |
|---|---|
| Sudhanva Sudheendra | Operations |
| Dheeraj Seelam | Marketing |
| Ansh Sharma | HR & PR |
| Udeep Hebbar | Finance |

Contact: contact@ballotbuddyapp.com · Instagram: @BallotBuddy

---

*Statewide data verified September 18–22, 2026; San Joaquin and Alameda County data verified against the county Registrars' lists on October 8, 2026.*
