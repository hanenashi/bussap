# Progress

## 2026-11-12 — JR source outage shown clearly

The owner reported that 琴似１条３丁目 showed a generic route loading error. Beechan's JR lookup returned 502 because the Sapporo Ekibus API refused connections; the stop is present in the local JR marker snapshot as station 340598. [Sapporo City says it temporarily stopped Ekibus](https://www.city.sapporo.jp/st/trouble/r081109_homepageteijshi.html) after an unauthorized access incident on November 9, pending safety checks. BUSSAP now names the unavailable JR data source on stop search, route selection, departure loading, and route details, and links to JR Hokkaido Bus's official timetable page. Chuo and Jotetsu still use their local GTFS feeds.

The current JR marker snapshot can locate a stop on the map, but it cannot supply route patterns or departures while Ekibus is unavailable. BUSSAP does not invent times from that snapshot.

## 2026-11-03 — Departure route details

Each departure now opens its ordered stop list. Chuo and Jotetsu use the exact GTFS trip and boarding sequence; JR uses the selected Ekibus course and joins station IDs to the JR marker snapshot. The route map connects adjacent stop coordinates with straight dashed segments and explicitly labels the line as approximate. Stops without JR marker coordinates remain in the list and leave gaps in the line. The existing tap-to-filter behavior on Chuo and Jotetsu departure rows remains separate from the new **経路を見る** action. Route details need a connection; the service worker still caches only previously viewed timetables.

Checks: eleven Python tests pass in the gateway environment, including route stop order and JR marker matching. The restarted API returned a route with exactly one boarding stop for live Chuo, Jotetsu, and JR departures. Chromium at 390 and 360 px opened Chuo and JR route details, drew their maps, and returned to the timetable without page errors or horizontal overflow. The public gateway still requires a session for the new API endpoint.

## 2026-11-03 — Signed-in PDF and public app icons

The owner asked to restore the historical PDF for the two enrolled users and reported that the installed app icon had disappeared. The Pixel screenshot inbox contained only an unrelated May screenshot, so diagnosis used the gateway response: unauthenticated requests for the manifest and both icon PNGs returned 401. The gateway now serves only those branding files without a session, and the login page links the same manifest and icon. Versioned icon URLs in the manifest prompt a fresh Android fetch. App JavaScript, APIs, and the PDF still require a valid session; the PDF viewer and bytes return 404 to unauthenticated visitors.

Checks: nine Python tests passed in the gateway virtual environment, including signed-in PDF access and unauthenticated PDF denial. After the gateway restart, the public manifest and both PNGs returned 200 without cookies, while the API still returned 401 and PDF 404. Chromium parsed the public manifest and fetched both versioned icons without credentials. A temporary signed-in browser session rendered the PDF canvas at 3572 × 3465 px through the live Funnel, and its back button closed the tab with no page errors; the temporary session was deleted. Actual launcher-icon refresh on either Pixel has not yet been observed.

## 2026-11-03 — Both phones enrolled

The wife completed enrollment through the public gateway. The production database now lists exactly two credentials, `owner` and `wife`. Her one-use code file was removed. The public sign-in page still responds, and an API request without a session still receives 401. The owner confirmed that she is in; installation on her Pixel has not been independently observed.

## 2026-11-03 — Dedicated BUSSAP Funnel node

The owner chose a separate Tailscale node so Beechan's five existing private Serve URLs would stay intact. A userspace `tailscaled` instance with its own mode-0700 state and socket is now registered as `bussap-gate.tail8d9f69.ts.net`; the `bussap-tailnode.service` user unit keeps it running. The gateway's WebAuthn RP ID and allowed origins were changed to that hostname. The previous staging mapping on Beechan was removed, and the new node has private staging on port 10003 and public Funnel on port 443. The original BUSSAP at Beechan port 10002 remains private.

Checks: the new node reports Running; its private HTTPS stage returned 200 for the sign-in page, 401 for an unauthenticated API request, and 404 for the PDF. Chromium over that HTTPS origin enrolled and signed in with a virtual authenticator, loaded the gated app with an active service worker and install manifest, cleared cookies, and signed in again without page errors. The test credential was revoked. Public Funnel status reports on; both published relay IPs returned 200 for the gate, and a direct relay request returned 401 for the API, 404 for the PDF, and 401 for app JavaScript. The owner's Pixel successfully enrolled a production credential through the public URL; its used code file was removed. A second one-use code for the wife's phone was placed on the owner's Pixel clipboard for private sharing. Her enrollment and install remain pending. No test credentials remain in the production database.

## 2026-11-03 — Device credential gate staged for a future Funnel

Goal: prepare an HTTPS entry point that can authenticate only the owner's and wife's enrolled phones without asking either phone to run Tailscale. Preserve the current private BUSSAP URL and keep the 2016 PDF off any public endpoint.

Implementation: a separate Python gateway on loopback port 8790 uses Yubico's pinned `fido2` library, one-use enrollment codes, single-device WebAuthn credentials with device verification, and revocable 14-day sessions. It gates the app shell, static files, service worker, and APIs; its public-facing variant removes and blocks the historical PDF. A private Tailscale Serve mapping on HTTPS port 10003 stages the gateway. The existing private BUSSAP service on port 10002 is unchanged.

Checks: eight Python tests passed in the gateway virtual environment, including unauthenticated API/PDF denial and cross-origin POST rejection. Chromium's virtual authenticator enrolled once, reached the gated app, lost its session after cookies were cleared, and signed in again; the app had no page errors. A second browser pass confirmed the gated app served its install manifest and activated its service worker after enrollment. The production gateway serves the sign-in page over tailnet HTTPS, returns 401 for an unauthenticated API request, and returns 404 for the PDF. The test credentials were revoked or kept in temporary databases; the production database has none. The six existing tests and syntax checks passed. Real Pixel credential enrollment and public Funnel routing are outstanding.

Routing limit: Beechan's only Funnel-capable ports (443, 8443, 10000) are already used by unrelated private Serve mappings. The owner must choose between a separate Tailscale node/hostname and moving one existing service before a public Funnel can be enabled; the final WebAuthn RP ID depends on that choice. No public mapping or production enrollment code has been created.

## 2026-11-03 — JR source date and one PDF exit control

Goal: replace the generic JR `cant promise correct times now` text with the actual timetable revision date and a short validity caveat, while showing when Beechan fetched that source. In the installed standalone app, open the PDF viewer in the same app window so the viewer's back button is the only visible exit control. Keep new-tab behavior in ordinary browser mode.

Source and assumptions: Ekibus returns `date_of_revision` (currently `20260401`); this is a timetable revision, not the date the phone cached a response. The existing `offline_cached_at` remains a separate phone cache timestamp. The PWA manifest requests `standalone`, which can be detected with `matchMedia('(display-mode: standalone)')`.

Implementation: JR responses now say `JR時刻表: 2026/04/01改正データ。選択日の運行は未確認です。` and include Beechan's `source_fetched_at`; the source note shows its retrieval time. Older offline responses with the former English warning are relabeled from their saved `source_revision`. The PDF link uses the same app window in standalone mode, leaving the page's back button as the sole exit control; browser mode still opens a tab.

Checks: six Python tests, Python and JavaScript syntax, and `git diff --check` passed. The live API returned the 2026/04/01 revision and a separate 2026-11-03 fetch time. Mobile Chromium showed the JR notice and retrieval time with four departures and no page errors; it also translated an older cached warning correctly. An offline reload showed the dated notice alongside a separate phone cache time at 320 px with no horizontal overflow. Browser mode rendered the PDF in a tab and closed it with the in-page back button; simulated standalone mode rendered it in the same window with one button and returned to the map. Physical Pixel standalone behavior remains unverified while ADB is deferred.

## 2026-11-03 — Installable shell and viewed-timetable cache

Goal: make BUSSAP installable on a phone and let a saved boarding point reopen the timetable for a date this browser already viewed when Beechan or the network is unavailable.

Sources and assumptions: use a same-origin service worker, browser Cache Storage, the existing read-only API, and a web app manifest. Only successful full departure queries are cached; static app files are precached. OpenStreetMap tiles, the historical PDF, and unseen stop searches remain online-only. Offline responses must show retrieval time and may contain only the previously fetched range, so they must not imply that an absent bus never runs.

Implementation: a manifest with 192/512 px icons, a same-origin service worker, and a bounded Cache Storage list of 30 previously viewed full timetables. Successful live responses refresh the cache; an unreviewed JR source revision clears all JR cache entries. Offline results show retrieval time, preserve JR's `cant promise correct times now` warning, filter past times, and explicitly say they cover only the previously displayed range. An unseen date reports that no saved timetable exists. The app shell works offline; OSM tiles, the PDF, and new stop searches remain online-only.

Checks: local Chromium showed an active service worker and 10 static shell cache entries. A separate test service was stopped after saving 札幌駅 25番; the browser then reloaded the shell, reopened cached departures with an offline timestamp, showed a clear message for an unseen date, and returned to live data after the test service restarted. The same stopped-service test reopened JR 新１２ at 320 px with its exact warning plus offline timestamp. Both views had no page errors or horizontal overflow. The icons were checked at 192 and 512 px. On the tailnet HTTPS origin, Chromium reported a secure context, a manifest with no parse errors, and an active service worker. Existing tests and static checks passed. Physical Pixel install/airplane-mode QA remains deferred until device access is available.

Next: field-test install and offline use on the Pixel when ADB/Wi-Fi is available; then consider a compact offline stop catalog if daily use shows a need.

## 2026-11-03 — Saved boarding points

Goal: let one phone save and reopen its usual exact boarding points without searching again. Chuo/Jotetsu favorites may include a selected line filter; JR favorites must include the chosen route pattern and boarding position.

Source and assumptions: use the app's existing source-specific stop IDs and JR pattern IDs. Store a small validated list in that browser's localStorage only; no account, server write, or cross-phone sync is needed for this personal first slice. A saved item is a shortcut to a fresh departure query, not a cached timetable.

Implementation: a save/remove button on the full departure screen and compact shortcuts above the home map. A GTFS favorite keeps the exact stop ID and optional chosen line; a JR favorite keeps the station/boarding point and pattern. The list is bounded to 12 and validated on read. Storage failure displays a plain message, and a source ID that later disappears displays a reselect message.

Checks: mobile Chromium at 393 × 852 saved 真駒内駅 6番 and 9番 as distinct items, reopened 6番 after reload, and removed it without affecting 9番. A 南５５ favorite reopened with only that line; a JR 新１２ favorite reopened its exact route at 320 × 720 with `cant promise correct times now` and no horizontal overflow. Blocking localStorage writes gave a clear message without adding a card or page error. The five Python tests, JavaScript syntax, `git diff --check`, and live HTTPS page check passed. A 320 px departure screenshot and the home favorites screenshot were visually inspected. Physical Pixel QA remains deferred while the phone is on cellular.

Next: after this slice, make the app installable and cache already fetched timetables for offline use.

## 2026-11-03 — Sharper PDF close-ups

The owner found that the 8× PDF limit still left labels hard to read. The viewer now allows 32× zoom. At close zoom it redraws the visible phone-sized section directly from the vector PDF after movement settles, rather than stretching the overview canvas. The overview remains visible during a drag. No new controls or source data were added.

Mobile Chromium at 393 × 852 with touch emulation reached a 12,576 CSS px page width at 32×, produced a sharp 786 × 1600 px detail canvas, and redrew after a one-finger drag. The screen retained one visible button, had no horizontal overflow, and logged no page errors. The 24× and 32× screenshots were visually inspected; stop names were legible. Physical Pixel QA remains deferred as requested.

## 2026-11-03 — PDF reference pan and closer zoom

The owner reported that the PDF loaded but one-finger dragging did nothing and the map needed closer zoom. The viewer now starts at 2.3× fit width, pans with one finger, pinches between 1× and 8×, and double taps for a quick closer view. It keeps the back button as the only visible control. PDF.js renders the same source page at 1.5× resolution; route data is still not extracted from the historical PDF.

Mobile-sized Chromium touch emulation at 393 × 852 confirmed one-finger drag changed the map position, pinch increased width from 904 px to 1738 px, and double tap reached the 3144 px maximum. The page had one button, no horizontal overflow, and no JavaScript errors. Real Pixel QA remains pending while the phone is on cellular and Wireless debugging has no listener.

## 2026-11-03 — Route label layout and line filtering

The owner reported that `真駒内駅` appeared one character per line beside the long `南９８真駒内駅～道路管理事務所` route name. Departure rows now show the short route code while retaining the full route name as a title. Chuo and Jotetsu rows are tappable: a tap filters by the chosen line code, date and refresh keep that filter, and **すべて見る** clears it. JR remains on its existing pattern selection flow.

Chromium at 393 × 852 showed `南９８` beside a horizontal `真駒内駅` destination with 191 px available; tapping narrowed 22 visible rows to `南９８` only. A separate `南５５` check returned 49 departures from both GTFS variants of that line, with no other line codes; clearing restored the mixed list. No page errors or horizontal overflow. The Pixel Wireless ADB listener was unavailable when checked through Termux.

## 2026-11-03 — Private PDF reference viewer

The owner chose to use the supplied 2016 PDF as a reference only. The map now links to a separate tab at `/network-map` with a single back button. The page renders the original PDF using vendored PDF.js 5.4.624; the PDF bytes are served unchanged from `/network-map.pdf` on the same tailnet-only service. It is not parsed into current route data or linked from a public host. The copyright notice and public redistribution question remain recorded in [pdf-assessment.md](pdf-assessment.md).

Checks: mobile-sized Chromium at 393 × 852 rendered the full PDF on canvas with no page errors or horizontal overflow; the back button closed the viewer tab and preserved the original map tab. The HTTPS viewer and PDF returned 200, and the served PDF matched the root file byte-for-byte. Five Python tests, JavaScript syntax, and `git diff --check` passed. Physical Pixel QA was unavailable because ADB had no connected device.

## 2026-11-03 — Street map and PDF preflight

Goal: add a Sapporo street map that opens the existing departure view for all three operators, while assessing the supplied PDF before using it. The map design reference is `docs/design/map-screen-concept.png`.

Sources: Chuo/Jotetsu exact boarding coordinates from the cached HODA GTFS ZIPs; JR numbered boarding coordinates from Sapporo Ekibus `/Get_marker_data`. Leaflet 1.9.4 is vendored with its MIT license; visible-viewport raster tiles use OpenStreetMap with attribution and no prefetch/offline tile download. [bus-routes.net](https://bus-routes.net/) is a linked comparison source, not copied data; its [terms](https://yuru-to.net/policy/) disallow unauthorized republication. See [pdf-assessment.md](pdf-assessment.md) for the 2016 vector PDF's structure and rights warning.

Implementation: a validated, atomic JR marker snapshot in ignored `.local-data/` is refreshed by Beechan's daily systemd job. It contains 1,360 JR boarding records; the full catalog has 5,571 points across the three operators. `/api/map-stops` takes a bounded viewport and zoom, groups dense points, and preserves individual IDs in small clusters. The phone map starts at Sapporo Station; a tap selects an exact boarding point, previews the next two GTFS buses, or leads to JR route selection filtered by the chosen bay. Location is requested only when the user taps the location control.

Verification: the local 393×852 Chromium path completed Jotetsu 札幌駅 25番のりば → two-bus preview → full departures, JR 札幌駅前 11番のりば → two matching route choices → candidate departures with `cant promise correct times now`, and Chuo 札幌駅北口 → full departures. No page errors. 320×720 and 1000×800 screenshots had no horizontal overflow. Mocked geolocation moved the viewport only after the location button was tapped. The five Python tests, JavaScript syntax checks, systemd unit verification, manual refresh job, local map API and tailnet HTTPS checks passed. The Pixel reached the HTTPS page through Termux SSH; Wireless ADB was unavailable, so this slice has not yet had a fresh physical Pixel render.

Visual comparison: header/search/operator tabs, blue/coral/teal markers, right-side location control, visible map attribution, and the date/departure/action anatomy in the stop sheet follow the concept. Intentional differences are real OSM tiles instead of illustrative map art, and a truthful initial "tap a stop" sheet instead of sample departures. The selected sheet scrolls into view on small screens. The PDF viewer was added in the subsequent slice above.


## 2026-11-03 — Pixel Chrome empty-state diagnosis

The owner reported that the current Chrome tab seemed broken. ADB and Chrome DevTools showed the selected Chuo stop was `北３条西１０丁目` (`S010200097400100`) at 43.20428, 141.75217, roughly 36 km straight-line distance from Sapporo Station. Its 2026-11-03 departures were 08:47 and 12:02; at 12:20 the old generic “no buses” message was technically correct but gave no useful explanation. Chrome had also automatically translated the Japanese stop name and app labels into English. The Pixel screenshot inbox contained no recent BUSSAP screenshot; diagnosis used a fresh ADB screen capture and the live Chrome tab.

The UI now labels a stop's straight-line distance from Sapporo Station and, when today's departures have finished, shows the day's last scheduled bus if the full result fits within the API's 50-row bound. GTFS stop search ranks exact names and then stops near Sapporo before applying the API result limit. Japanese transit names are marked `notranslate`. A live Pixel Chrome reload showed the Japanese text, 36 km label, and 12:02 last-bus message; tapping 明日 showed three departures starting at 09:02. The physical 1080 px screenshot showed the page fitting the 411 CSS px viewport. The stale translated BUSSAP tab was replaced with the verified one.


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
