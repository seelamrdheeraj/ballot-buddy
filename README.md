# Ballot Buddy

**Use your buddy to cast your ballot.**

A free, nonpartisan voter-education app for voters aged 18–29. Enter any U.S. ZIP code and see your ballot: candidates and measures explained in plain English, the deadlines that matter in your county, and a swipe-to-compare that matches your views to what candidates actually said.

Only 23% of voters aged 18–29 turned out in the 2022 midterms. The reason usually isn't apathy. It's confusing ballot language, missed deadlines, and not knowing which sources to trust. Ballot Buddy is built to remove all three.

---

## Try it

**Live demo:** https://seelamrdheeraj.github.io/ballot-buddy/

Enter ZIP **95391** (Mountain House, California) to see a complete November 3, 2026 ballot, or try any ZIP to see your U.S. House race pulled live from the Federal Election Commission.

On a phone, open that link and tap **Share → Add to Home Screen** (iPhone) or **menu → Install app** (Android). It runs full screen, like a native app.

---

## What it does

- **Your ballot by ZIP.** Any ZIP in the U.S. Your congressional district is looked up from Census data; House candidates load live from the FEC.
- **Match.** Swipe agree or disagree on real statements from candidates on your ballot, with names hidden. At the end you see how often you overlapped with each candidate. Overlap is shown as a number, never as a recommendation.
- **Follow.** Follow your representatives and see their recorded votes next to what they promised in their own words. We show both; you decide.
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
| **Local races** | Mountain House and Tracy, California |

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
| Candidate positions | Each candidate's own campaign website or official county statement, with a link on every position |
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
- **Six Mountain House candidates have no published positions yet.** Their official statements arrive with the county Voter Guide mailed by October 5, 2026.
- **Vote records** are loaded for Josh Harder and Rhodesia Ransom, the two officials Mountain House voters can follow today. Other officials show promises and links until their records are compiled.
- **Spanish covers the app itself and the California ballot.** Buttons, labels, and every California candidate and proposition are translated. Candidate and measure text for other states is currently English only, so in Spanish mode you'll see Spanish around English content there.
- **California's down-ballot statewide offices aren't loaded** — Lieutenant Governor, Attorney General, Secretary of State, Controller, Treasurer, Insurance Commissioner, Board of Equalization, and judicial retention. The app says so on the Candidates screen.
- **A few measure details are still unconfirmed**, and each says so where it appears. Ohio's Secretary of State blocked automated reading, so Issue 3 carries a notice that its exact certified wording wasn't verified. Rhode Island's five bond questions aren't numbered yet, so they're listed by name. Louisiana's amendment numbering comes from two news listings that agree, not from the state. Every one of these is recorded in `research/` with the reason.
- **Notifications** on a static site can't push to a locked phone. Calendar export gives you a real alert instead.
- **BallotBot** answers from built-in responses unless the app is opened through Claude, which supplies live AI answers.

Always confirm deadlines with your state or county election office. This is voter education, not legal advice.

---

## Run it yourself

No build step, no framework. One HTML file plus a `data/` folder.

**Simplest:** download the repo, then serve the folder (the app fetches its data files, so opening the HTML directly from disk won't load them):

```bash
cd ballot-buddy
python3 -m http.server 8765 --bind 0.0.0.0
```

Then open `http://localhost:8765`. On a phone on the same Wi-Fi, use your computer's address instead of `localhost`, including the `http://`.

**Optional:** the FEC lookup uses the shared `DEMO_KEY`, which allows only about 10 requests an hour. For a free key with a higher limit, sign up at api.data.gov/signup and paste it into `FEC_KEY` near the top of the script in `ballot-buddy-app.html`.

### Files

| File | What it is |
|---|---|
| `ballot-buddy-app.html` | The app. Single file, vanilla JavaScript. |
| `data/ballot-2026.json` | Verified candidates, measures, deadlines, and official links. |
| `data/zip-cd.json` | ZIP code to congressional district table (33,000 ZIPs). |
| `data/reps.json` | Followed officials: promises, links, vote records. |
| `ballot-buddy-site.html` | Marketing website for the venture. |
| `index.html` | Redirects to the app so a bare URL opens it. |
| `icon.png`, `manifest.json` | Home-screen icon and install settings. |
| `research/` | The raw, sourced research each data file was built from. |
| `tools/build.py` | Merges `research/` into `data/`. Run it after adding research. |
| `tools/validate.py` | Checks the merged data for missing sources, empty fields, and bad dates. |
| `NOTES.md` | Build notes, data pipeline, version history. |

### Updating the data

```bash
python3 tools/build.py && python3 tools/validate.py
```

`build.py` rebuilds `data/ballot-2026.json` and `data/reps.json` from everything in `research/`, and refreshes the California seed embedded in the app so ZIP 95391 works even if the data fetch fails. `validate.py` exits non-zero if anything is broken, so it can gate a deploy.

---

## Publish it on GitHub Pages

This is a static site, so no build step is needed.

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

*Ballot data verified September 18–22, 2026.*
