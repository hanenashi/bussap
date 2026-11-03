# Progress

## 2026-11-03 — First phone stop view

Goal: search real stops, select an exact source boarding position or JR route pattern, and show scheduled departures for today, tomorrow, or a chosen date on the existing Beechan HTTPS origin. Use the generated visual concept at `docs/design/stop-screen-concept.png` for the layout and typography; real API data replaces the sample text.

Checks: verify the API and static shell through Tailscale Serve, exercise stop search → selection → departures in a rendered mobile browser, check operator/date controls and JR warning, and compare the rendered view with the concept. The map and offline cache remain later slices.

Results: `web/` is a dependency-free first stop screen served from the API's existing origin. Search returns source-specific boarding points for Chuo and Jotetsu, and JR station selection leads to route, direction, and boarding-number selection. Today, tomorrow, custom date, refresh, source link, feed retrieval time, and clear coverage/connection states are present. JR candidate departures display the owner's exact warning. The visual concept's bold BUSSAP header, search tabs, stop heading, date controls, open departure rows, and highlighted next bus are reflected in the rendered screen; live data and browser chrome differ from the sample art.

Verification: Chromium Playwright at 393×852 exercised Jotetsu `札幌駅` 25番のりば, tomorrow, JR `新札幌駅` → 新１２, and Chuo `地下鉄麻生駅`; there were no page errors. A 320×720 pass found no horizontal overflow and the calendar control opened without a page error. A 1000×800 screenshot confirmed the centered desktop layout. Beechan's Tailscale HTTPS origin returned the page and JavaScript with 200; `/health` remained ready. `node --check`, the four Python unit tests, and `git diff --check` passed. Actual Android browser interaction and offline behavior are still to be checked in later slices.


## 2026-11-03 — Beechan read-only service and feed refresh

Goal: let phone browsers query Beechan's normalized departure results through a small read-only HTTPS service. Refresh the Chuo and Jotetsu feeds on Beechan without making phones fetch upstream data.

Sources: the existing three-operator CLI, HODA GTFS ZIPs, and Ekibus JR local timetable requests. Tailscale Serve already runs on Beechan for other localhost services; use a separate port and preserve existing mappings.

Assumptions: this two-person service needs only bounded GET endpoints, local cache and tailnet access. JR remains category-based with the exact warning `cant promise correct times now`; a changed revision must withhold its times.

Checks: local HTTP health, stop search, pattern discovery, three-operator departures, invalid parameters, feed refresh timer, and a phone-side HTTPS read if Tailscale access is available. Keep the service bound to loopback.

Results: `scripts/server.py` serves only bounded GET endpoints on `127.0.0.1:8788`. The three-operator queries preserve the existing GTFS coverage and JR candidate statuses; POST returns 405. Systemd user units `bussap-api.service` and `bussap-refresh.timer` are enabled on Beechan. The daily refresh uses HTTP conditional requests; a manual systemd refresh completed with both feeds unchanged.

Network: added tailnet-only `https://beechan.tail8d9f69.ts.net:10002` → `127.0.0.1:8788`, leaving pre-existing Serve mappings intact. Local health returned `ready`; the Pixel fetched `/health` and a Chuo departure through HTTPS over Tailscale. No phone UI was built in this slice.

Checks: local health, stop search, JR pattern discovery, three-operator departures, missing JR pattern (400), POST (405), feed timer execution, and Pixel-to-Beechan HTTPS query all passed. Existing four unit tests and three JR source probes also passed. The user systemd manager reports `degraded` because of other units, but both BUSSAP units were active/successful at setup.

Next step: build the first phone UI on the same Beechan origin, starting with stop search and departures. The map and broader network overview can follow after the stop view is usable on a Pixel.

## 2026-11-03 — JR warning and launch scope

The owner chose to use the normal JR weekday/Saturday/Sunday-holiday categories and not hold up the personal app for exceptional-service verification. User-facing JR warning: `cant promise correct times now`. The CLI now emits that exact warning with candidate JR times. A changed source revision still withholds times until reviewed. Next step: Beechan read-only service and refresh job, then phone UI.

## 2026-11-03 — JR date and season audit

Goal: test more ordinary JR local patterns, find any first/third/fifth versus second/fourth Saturday difference, and determine whether operator notices establish a trustworthy season or exception rule.

Sources: Sapporo Ekibus local timetable endpoint and JR Hokkaido Bus's own timetable PDFs and service notices. Use bounded requests and compact observations.

Assumptions: the April 2026 timetable revision may remain current in November, but the API's four day tabs alone do not prove it. Special service and winter changes may need an operator notice or explicit coverage period.

Checks: compare selected patterns with the current official PDFs, inspect revision/holiday notices, and try the documented Ekibus holiday endpoint. Record mismatches and unknowns. No phone service or UI in this slice.

Findings: seven more ordinary 札幌駅前 patterns all returned revision 20260401. All seven had the same first/third/fifth and second/fourth Saturday lists; one 快速６４ pattern had weekday departures but no weekend departures. The current operator PDF index also points to April 2026 timetables. The city's `get_holiday` endpoint returned false for 2027-01-01 and 2027-03-22, despite both being national holidays in the Cabinet Office calendar. See [source-inventory.md](source-inventory.md) for scope and examples.

Change: the JR CLI now withholds departures if Ekibus reports a revision other than the reviewed `20260401`. A test simulating a changed revision passes. The existing `day_category_candidate_unverified_for_date` status remains for the reviewed revision.

Known limitation, accepted for v1: neither Ekibus timetable response nor the operator index gives an end date or future exception schedule. The app may show JR day-category times with the owner's short warning. Recheck Busdia or operator notices when the source revision changes. No phone service was started in this audit.

## 2026-11-03 — Unified departure CLI

Goal: query scheduled departures for an exact boarding stop and service date through one CLI for all three operators.

Sources: the two HODA GTFS ZIPs and Sapporo Ekibus's JR local timetable endpoint. Existing sample fixtures and operator PDF comparisons are the reference checks.

Assumptions: GTFS coverage is authoritative only inside `feed_info.txt` dates; JR's day category can be selected explicitly, but its API does not prove a particular date or special-service exception. The first CLI can use exact source IDs to avoid unsafe stop-name merging.

Checks: weekday, Saturday, calendar exception, feed expiry, boarding position, and GTFS times beyond 24:00; repeat the three JR samples. Report missing or stale data plainly.

Results: added `scripts/departures.py` with `refresh`, `find-stops`, `jr-patterns`, and `query`. The GTFS path applies calendar exceptions, uses exact boarding IDs, preserves platform codes, handles after-midnight times and returns explicit `outside_feed_coverage`. The JR path discovers route patterns and boarding numbers from Ekibus; it infers a day category from the official 2026–2027 holiday list, but returns `day_category_candidate_unverified_for_date` with no claimed date-specific timestamp. The three JR audit patterns still pass.

Verification: three synthetic date/overnight tests pass. Live queries returned Chuo 麻０５ 07:40/08:45/09:47 on 2026-11-04, Jotetsu 南５４ 06:55/07:40/08:10 on 2026-11-07 after destination filtering, and JR 新１２ 07:50/08:20/09:00 in the Sunday/holiday category for 2026-11-03. On the 2026-11-03 national holiday, Chuo returned 08:06/09:06/10:06 and Jotetsu returned 06:55/07:40/08:10, matching their published Sunday/holiday sample columns. Out-of-coverage Chuo query on 2027-04-01 returned an explicit coverage status.

Limits: this CLI is a source-validation engine, not a live phone service. JR's date-specific validity and seasonal transitions are unresolved; GTFS sample comparisons are narrow. Full route/stop coverage and snapshot scheduling remain future work.

Next step: widen source validation and decide a reliable JR exception/season rule before exposing date-specific JR times to phones. A Beechan read-only service and scheduler can follow; the map and phone UI still wait.

## 2026-11-03 — JR probe and two GTFS comparisons

Goal: make the three JR local samples repeatable, then check one Chuo and one Jotetsu scheduled departure against visible operator sources.

Sources: Sapporo Ekibus timetable interface and JR's 2026-04 PDFs; HODA Chuo/Jotetsu ZIPs and operator timetable pages.

Assumptions: upstream IDs and day-category meanings may change; a successful HTTP response alone does not prove a valid schedule. No account or location data is needed.

Checks: run the probe on Beechan with bounded requests; verify route identity, revision, category and selected departure times; compare GTFS stop/direction/date/time with independent operator output. Record a mismatch as a finding.

Results: `python3 scripts/probe_jr.py` passed 3/3 JR local samples against the recorded 2026-04 revision and all four day categories. Chuo 麻０５ from 地下鉄麻生駅 and Jotetsu 南５４ from 札幌駅 matched the first three weekday and Saturday departures in current operator PDFs; exact stops, dates and links are in [source-inventory.md](source-inventory.md). No mismatch found in these narrow samples.

Limits: the JR endpoint lacks an arbitrary-date query, so service exceptions and seasonal changes are still unproven. The JR probe fixture will deliberately fail when the source revision changes, requiring review. Chuo's winter timetable transition needs a recheck. Busdia did not respond from Beechan; operator PDFs remain a manual fallback.

Next step: implement a unified stop/date CLI query with source validity and boarding-position identity, then check broader route coverage and exceptional dates. No map or phone UI in this slice.

## 2026-11-03 — Phase 0 source audit started

Goal: establish trustworthy scheduled data for Chuo, Jotetsu, and regular JR Hokkaido Bus routes before building the app.

Verified so far:

- The repository has a battleplan, README, and one root PDF; no app implementation exists yet.
- After the owner confirmed completion of HODA's form, both GTFS ZIPs were downloaded outside the repository and inspected. Both contain stops, routes, trips, stop times, calendars and calendar exceptions, with declared feed coverage 2026-10-01 through 2027-03-31. Neither has `shapes.txt`; both leave `route_short_name` blank.
- Sapporo Ekibus lists JR Hokkaido Bus, Chuo, and Jotetsu. Its site warns that cross-season time searches can show the current seasonal timetable, and that some special-service results can differ from actual operation. Three ordinary JR local routes returned departure lists through its own timetable API. The first three weekday and weekend departures for each matched JR's 2026-04 operator PDFs; details and commands are in [source-inventory.md](source-inventory.md).
- The root PDF is a one-page, 1.8 MB, text-extractable network map marked 2016-12-01 and `禁無断転載`. It is useful as historical reference; current accuracy and redistribution permission are unverified.

Assumptions to test:

- Beechan can collect and validate snapshots on a conservative schedule, and serve a small phone-facing web app.
- Tailscale Serve is the simplest first HTTPS access path for two phones. An access-controlled public URL could be added later if the second phone should work without Tailscale.

Next steps:

1. Build a small repeatable JR probe with representative fixtures and wider route coverage. Validate first/third/fifth vs second/fourth Saturday and special dates explicitly.
2. Compare representative Chuo and Jotetsu GTFS departures with visible operator timetables.
3. Explore Busdia as a fallback; the homepage timed out from Beechan during this audit. The operator PDFs are an available manual fallback.
4. Implement a unified stop/date CLI query once source rules are pinned down; decide the phone access path after it works. Do not build the map yet.

This audit is a documentation milestone; its commit is recorded in git history.
