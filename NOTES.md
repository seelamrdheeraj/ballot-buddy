# Ballot Buddy — website + app prototype

Built from the SkillsUSA Entrepreneurship business plan (contestant 2738) and regional presentation (5904).
Target competition: Northeastern NextUp Founders Prize 2026 (entry deadline Sept 30, 2026, 11:59 PM EDT; written app ~900 words + 2–3 min video).

## Live links (private artifacts — share from the page's share menu)
- App prototype: https://claude.ai/code/artifact/6416bd27-1b34-4c78-927f-a15ac130d932
- Website:       https://claude.ai/code/artifact/f524a251-a993-43f2-b467-d4dffc7f7043

## Files
- ballot-buddy-site.html — marketing website (single file, no build step; open in any browser)
- ballot-buddy-app.html  — interactive phone-framed app prototype (single file)
  - BallotBot uses Claude only when opened at the artifact link; opened locally it falls back to built-in answers.

## Ballot data (v3, verified 2026-09-18)
Enter ZIP 95391 (Mountain House, CA) for the full Nov 3, 2026 ballot.
- Candidates: CA Secretary of State certified list (Aug 27, 2026) + June 2 primary results.
  Governor (Becerra / Hilton), U.S. House CD-9 under the Prop 50 map (Harder / McBride), Assembly AD-13 (Ransom / Patti),
  Mountain House City Council (6 candidates, 2 seats), Lammersville USD Trustee Area 4 (Daniel / Olsen).
- Positions: each candidate's own website or official county candidate statement; source link on every candidate screen.
  Four council candidates and both school-board candidates have no published statement yet (county guide mails by Oct 5) — shown as such, not invented.
- Propositions: all 14 statewide (1–5, 37–45) from the official Voter Information Guide (Aug 10, 2026) + LAO fiscal estimates.
  No local measures apply to Mountain House.
- Deadlines: SoS + San Joaquin County Registrar (non-VCA county): mail ballots Oct 5, register by Oct 19 (same-day in person Oct 20–Nov 3),
  request mail ballot by Oct 27, polls 7am–8pm Nov 3, mail ballots received by Nov 10.
- Not yet loaded: Lt. Governor, AG, SoS, Controller, Treasurer, Insurance Commissioner, Board of Equalization, judicial retention (noted in-app).
- Other ZIPs: Tracy (953xx) gets the district races; other CA ZIPs get Governor + propositions; other states get a notice.

## Brand
Navy #0F4A6B · Ballot red #D8454F · Coral #D9737D · Cream #F6F1E7 · Marigold #F2A65A
Type: Archivo (display) + Public Sans (body), loaded from Google Fonts.

## Version history
- v1   — full build from the plan
- v2   — simplified: site cut from ~1,240 to ~400 words; app sample data halved
- v2.1 — reader-panel fixes + 7 code fixes
- v3   — real, sourced Nov 3, 2026 ballot for Mountain House replaces fictional sample data
- v4   — any-ZIP architecture: data moved to `data/`, live FEC House lookup, Match/Follow/Record added
- v5   — research finished (all 36 governor + 35 senate races, measures for all 50 states); repo layout, validator, heading and honesty fixes
- v6   — registration: Get started opens register.html; server.py (stdlib + SQLite) stores sign-ups; private admin.html lists them; demo copy and external demo links removed
- v6.1 — API moved into bb_core.py and exposed as Vercel Functions (api/) with a private Vercel Blob store, so registration works on the public Vercel URL
- v6.2 — app page is a plain full-height app shell (phone bezel, fake status bar and side copy removed); registered visitors open straight on ZIP setup, no welcome/Get started screen
- v6.3 — Premium removed: BallotBot and candidate comparison open directly, no paywall sheet or Profile toggle; site pricing section, Premium tags and $7.99 copy gone

## Test on your phone (same Wi-Fi as the Mac)
1. In Terminal on the Mac:  cd ~/Downloads/"Ballot Buddy" && python3 -m http.server 8765 --bind 0.0.0.0
   (click Allow if macOS asks about incoming connections)
2. On the phone, open Safari (iPhone) or Chrome (Android) and go to:  http://<Mac IP>:8765  (index.html redirects to the app; type the http:// part)
   Find the Mac's IP with:  ipconfig getifaddr en0
3. iPhone: Share → Add to Home Screen. Android: menu → Add to Home screen / Install app.
   The icon (icon.png) and manifest.json make it launch full-screen like an app.
Note: this works only while the Mac server is running and both devices are on the same network.
For a permanent link, upload the folder to Netlify or GitHub Pages and use that URL instead.

## v4 (2026-09-22) — any-ZIP architecture + feature list from the founders' notes
Data now lives in `data/` and is fetched at load; the HTML carries an inline CA seed so 95391 works even if the fetch fails.
- `data/zip-cd.json`: built from the Census 2020 ZCTA → 118th-Congress relationship file; districts covering ≥5% of a ZIP's land, largest first; ZIPs spanning districts prompt the user to pick. Verified overrides for the Prop 50 map: 95391, 95376, 95377, 95304 → CA-09. `_meta.redistricted_for_2026` lists CA, TX, MO, NC, OH, UT; the app shows a warning there.
- U.S. House for any district: OpenFEC `/v1/candidates/` (office=H, cycle=2026, candidate_status=C, election_years includes 2026). At-large states retry district `00`. Names + party only; FEC doesn't know primary results, and the app says so. Cached 24h in localStorage. `FEC_KEY` = DEMO_KEY (30/hr); free key at api.data.gov/signup.
- Curated data merged by `tools/build.py`: governor/senate/measures JSON from researchers + hardcoded verified CA data (governor, CD-9, AD-13, MH council, LUSD, deadlines, official links). Rerun after dropping new research JSON into `research/`. (v5 moved the script and its inputs into the repo; see below.)
- Features added: Match (swipe on real positions, names hidden, overlap % per candidate, interests saved to Profile and fed to BallotBot), Follow (candidates + officials), Record screen (promises next to votes), calendar export (.ics with day-before alarm) + in-app reminder check, Learn without quiz (three reads + official-source links), BallotBot prompt tailored to ZIP/district/interests/follows, richer Home.
- Removed: quiz and badges; fictional sample data is gone entirely.
- The research that was pending here on 2026-09-22 (governor and senate matchups outside CA, measures outside CA, recorded votes) was finished the same day — see v5 below.
- Not possible on a static site: push notifications (calendar export instead), live social feeds for followed candidates (links instead).

## v5 (2026-09-22) — research finished, repo-shaped
The research that v4 left pending is done. Coverage is now: Governor in all 36 states holding a 2026 race,
U.S. Senate in all 35 races (33 Class 2 seats + the FL and OH specials), and statewide measures for all 50 states —
145 measures in 39 states, with 11 states (CT, DE, IL, ME, MS, NJ, NY, OR, PA, SC, TX) confirmed to have none.
Recorded votes for Harder and Ransom (8 each) were already loaded in the interrupted v4 session.

### Layout
Researcher JSON now lives in `research/`; `tools/build.py` merges it into `data/`. The paths in build.py were
pointing the wrong way (it read `../data` and wrote `tools/data`) — fixed, and the rebuild is byte-identical.
`tools/validate.py` is new: it checks every measure for a source link, both vote effects, and a fiscal line,
and exits non-zero on error so a deploy can gate on it. Run `python3 tools/build.py && python3 tools/validate.py`.

### App fixes this round
- **Honesty bug.** `myMeasures()` returns `[]` both for a state we checked and for one we never researched, so
  unresearched states were telling voters "No statewide measures on your ballot this year." Now an absent key
  and an empty list say different things (`measuresChecked()` / `meas_notloaded`).
- **Headings.** Several states print a paragraph as the official measure title (Missouri's run to 576 chars),
  and some repeat the measure number inside it. `shortT()` / `mHead()` trim the boilerplate opener, drop a
  duplicated number, and cap the heading; the full official wording still shows under More detail.
- **Montana** ships titles that are pure designation ("A Constitutional Amendment Proposed by Initiative
  Petition"), so the three MT measures were given short subject lines taken from their own ballot language.
- **Ohio Issue 3**: ohiosos.gov returned 403 to every fetch, so its ballot text is prefixed with a plain-language
  notice that the certified wording is unverified, with the official PDF linked. Verify before publication.

### Data caveats carried forward
`build.py` now keeps each state's researcher `notes` in `data/ballot-2026.json` under `measures_meta` rather than
dropping them at the merge. These are developer-facing (they name blocked sites and pending litigation) and are
deliberately not rendered in the app. Live items: Rhode Island's bond questions are unnumbered pending the SoS,
Louisiana's 1–10 ordering is from agreeing news listings, Missouri Amendment 6 was reinstated by the state
Supreme Court on Sept 3, and Florida Amendment 3 carries the court-revised ballot language.

### Still open
California's down-ballot statewide offices (Lt. Gov, AG, SoS, Controller, Treasurer, Insurance Commissioner,
Board of Equalization, judicial retention) are still not loaded. Spanish covers the app chrome and the California
ballot only — other states' candidate and measure text is English.

## v6 (2026-10-06) — registration app
- `server.py` replaces `python3 -m http.server`: same static serving, plus `/api/register`, `/api/registrations` and the admin session routes. SQLite file `registrations.db`, created on first run. No dependencies.
- `register.html`: first name, last initial, age (13–120; `MIN_AGE`/`MAX_AGE` in both server.py and the page). Validated client- and server-side. Draft is kept in localStorage across refreshes; success is kept under `bb-registration` so the app knows who signed up.
- `admin.html`: password sign-in (`ADMIN_PASSWORD` from `.env`), HttpOnly cookie, 12-hour sessions, 8 failed attempts per 10 minutes per IP. The page is public; the data is not.
- App: welcome "Get started" sends unregistered visitors to register.html, then on to ZIP setup; Profile shows the account; "Reset" clears the registration too. "Free in this demo" copy is now "free during launch" (there is still no payment flow).
- Site: viewport meta added; every CTA now points at local pages (register.html / ballot-buddy-app.html) instead of the GitHub Pages demo.

## v6.1 (2026-10-06) — hosted registration on Vercel
- `bb_core.py` now holds the whole API (validation, sessions, storage, HTTP adapter). `server.py` is a thin static-file wrapper around it; `api/*.py` are five-line Vercel Functions around it.
- Storage backends: SQLite locally; on Vercel a private Blob store, one JSON blob per registration under `registrations/`. The record is also base64url-encoded into the blob pathname so the admin list needs one `list` call, never a download per blob. Talks the same HTTP as the official SDK (`https://vercel.com/api/blob`, `x-api-version: 11`, `x-vercel-blob-access: private`).
- Admin sessions are now stateless signed cookies (HMAC over an expiry, keyed by the password) so they survive cold starts; logout only clears the cookie. Login throttling is per process, so on serverless it is best effort.
- `register.html` shows the server's own error message when the API answers with one (e.g. "not set up yet"), instead of blaming the connection.
- Setup on Vercel: create a private Blob store and connect it (adds `BLOB_READ_WRITE_TOKEN`), add `ADMIN_PASSWORD`, redeploy. See README.
- First-run admin setup: when no `ADMIN_PASSWORD` is set, the admin page offers "Create the admin password" and stores a PBKDF2-SHA256 hash (200k iterations, random salt) as the `admin_password` setting (SQLite `settings` table locally, `settings/admin_password.json` private blob on Vercel). `/api/admin/setup` refuses once a password exists; the env var always overrides. This removed the only credential the owner had to type into Vercel.

## v6.2 (2026-10-07) — app shell, no demo framing
- `ballot-buddy-app.html` no longer renders inside a fake phone (bezel, notch, "9:41" status bar) on a navy stage with "Tap around" copy. The app is one full-height column: edge-to-edge on phones, centered at 520px with a hairline border on wider screens. The `fit()` scaler and `tick()` clock are gone with it.
- Boot picks the first screen from state: set up → last screen; registered but not set up → ZIP setup; not registered → welcome ("Get started" → register.html). So after registering and tapping "Open the app" the first thing shown is "Where do you vote?". The ZIP step has no Back button during first-time setup (there is nothing to go back to); it still has one when reached from Profile → Change.

## v6.3 (2026-10-07) — everything is free
- App: `requirePremium()` and the $7.99 sheet are gone. The mascot opens BallotBot directly, Compare opens directly (no lock icon), and the Profile no longer has a Premium card. `S.premium` is no longer read; the strings `premium`, `premium_s`, `price`, `on_demo`, `try`, `later` were dropped in both languages. The marigold pill style the Match result uses is now `.pill.marigold`.
- Site: the Pricing section and nav link are removed, the BallotBot feature has no Premium tag, the campus-ambassador line no longer promises "Free Premium", and the "Is it free?" answer lists everything as free.
