# BUSSAP — battleplan

Status: planning baseline, 2026-11-03
Repository: https://github.com/hanenashi/bussap
Owner workflow: ChatGPT for product/architecture decisions; Codex CLI on Beechan for bounded investigation and implementation.

## 0. Mission

Build a fast, inexpensive, installable **Sapporo bus map and timetable app** for two people, primarily on Android phones. One glance should answer:

- Where are the nearby stops?
- Which buses serve this stop, in which direction?
- When are the next departures today (and tomorrow / another day)?
- Where does a chosen route go?
- What does the *whole bus network* look like?

**All three are mandatory:** Hokkaido Chuo Bus (北海道中央バス), JR Hokkaido Bus (ジェイ・アール北海道バス, including **regular local Sapporo services**), and Jotetsu (じょうてつ). Do not call an MVP complete if JR local buses are missing.

Two complementary views:
1. **Street map:** OpenStreetMap-based map with approximate stop positions, route shapes, tappable stops, and departures.
2. **Network overview:** zoomable existing root PDF (currently named " sapporobus.pdf" with a leading space), reusing its whole-network schematic where useful. It need not be georeferenced or interactive in v1.

Focus: reliable scheduled departures, pleasant mobile UX, offline-friendly caching, minimal maintenance and running cost. Live location/delay predictions are welcome later, but not needed to ship a useful first version.

### Non-goals for initial release

- No user accounts, social features, payments, route optimisation engine, native APK, elaborate admin dashboard, or perfect cartographic accuracy.
- No attempt to replicate all of Google Maps or full multimodal journey planning.
- No invented "live" estimates when only scheduled times are available.

## 1. Ground truth and candidates

Treat all unofficial endpoints as **candidates requiring verification**, not stable contracts. Record actual behavior, representative responses, date of observation, restrictions, source freshness and fallback.

| Operator | Preferred schedule source | Fallback | Live-data candidate |
|---|---|---|---|
| Chuo Bus | HODA GTFS static ZIP | City Ekibus timetable interface | City Ekibus / operator |
| Jotetsu | HODA GTFS static ZIP | City Ekibus timetable interface | City Ekibus / operator |
| JR Hokkaido Bus local routes | Sapporo City Ekibus system: inspect JSON calls and test coverage | JR-linked Busdia HTML timetables; operator PDFs as last resort | City Ekibus and new Buskita |

Important sources:
- HODA GTFS directory: https://ckan.hoda.jp/dataset/gtfs-data
- Chuo GTFS: https://ckan.hoda.jp/dataset/gtfs-data/resource/dbadfccc-670e-49b9-be77-c3f346ee3160
- Jotetsu GTFS: https://www.transit.land/data/feeds/f-joutetsu~jp
- Sapporo Ekibus: https://ekibus.city.sapporo.jp/
- Ekibus mobile search: https://ekibus.city.sapporo.jp/m
- Reverse-engineering reference, **not official API documentation**: https://qiita.com/hextomino/items/c9ecbd9fd961119fa88e
- JR local routes: https://www.jrhokkaidobus.com/timetable/routebus_sapporo/
- Busdia: https://www.busdia.com/
- JR Buskita: https://jhb.buskita.com/
- OSM: https://www.openstreetmap.org/
- MapLibre: https://maplibre.org/
- PDF.js: https://mozilla.github.io/pdf.js/

HODA lists an attribution license; honor dataset attribution and its platform-use instructions. Record licenses and source URLs in the app's About/Data section. For unofficial sources, avoid hammering servers, bypassing authentication, distributing unrestricted raw copies, or hard-coding secrets in the public repository. This is a personal project, but "private use" does not magically remove website terms or copyright concerns.

### First JR investigation: prove a normal Sapporo route

1. In a regular browser, choose several ordinary **JR Hokkaido Bus** routes/stops in Ekibus (not railway journeys and not only express buses), including stops in different areas. Record the exact route, stop, direction, date and the visible official timetable.
2. Inspect the network activity in browser devtools: endpoint, method, JSON request/response, IDs, date/weekday behavior, pagination, stop metadata and CORS. The Qiita article mentions the *Get_busstop_timetable_list*, *Get_busstop_lastdata* and *Get_busstop_list* family; names and schemas must be revalidated, not assumed.
3. Write a small reproducible probe that retrieves a **JR local** departure list; compare times/directions and validity against visible Ekibus results for at least one weekday, weekend, and relevant holiday/service exception. Never confuse current-day approaching-bus data with future-date timetables.
4. Try Busdia's HTML as a second adapter if it is more suitable for complete JR static timetables. Identify how to discover stops and route directions without manual IDs. Investigate official PDFs only if the first two paths fail.
5. Assess whether coordinate coverage is provided by Ekibus; if not, match by name/location to OSM with conservative confidence rules.
6. Save tiny **redacted fixtures** and reproducible tests, not enormous raw responses. Document precisely what is verified vs speculative, including rate limits and limitations.
7. Prove **three representative JR stops** from different routes before declaring the JR adapter viable. Prioritize common local journeys, not airport/express-only coverage.

If JR remains blocked, **stop and report the obstacle + next practical candidate**. Do not silently drop JR, substitute train results, or manufacture a schedule.

## 2. Product behavior

### Map screen (primary home screen)

- Open on Sapporo by default; optionally center near user **only after requesting location permission**. Keep the last viewed area when appropriate.
- Show operator-distinguishable stops, optionally clustered at low zoom; don't flood the whole city with labels.
- Tap a stop to open a **bottom sheet** with stop name, operator, direction/platform information, current date and upcoming departures. Route number, destination, time and scheduled/live status must be readable at a glance.
- Tap route to highlight its approximate path and ordered stops; provide destination and opposite-direction context.
- Search Japanese stop names, route numbers and major landmarks; show nearby and favorites.
- Favorite an actual boarding position/direction, not only a shared stop name.
- Allow choosing today / tomorrow / date, and manually refreshing when network is available.
- For a provisional coordinate, label it approximate. For a real bus trip, indicate the side of the street/platform when known; prioritize correct boarding over marker prettiness.
- Fast on Pixel-sized Android screens, large touch targets, calm and uncluttered. Japanese place names are primary; English interface labels optional.

### Network overview tab

- Preserve and **inspect root " sapporobus.pdf"** locally first (PDF size, page count, resolution, vector/raster characteristics, authorship/source, readability on phones).
- Initially make it a **pinch-zoom/pan viewer** (PDF.js or another light reliable viewer). Offer full-screen; do not redraw by hand unless necessary.
- Consider a later overlay of clickable major hubs/routes only if alignment is reliable and effort is justified.
- If the PDF is unsuitable, prefer a generated schematic from known route/stop sequences rather than inventing geometry. The street map and schematic must remain separate mental models.
- Check redistribution rights before publishing the PDF as a public web asset. A repository being public is not by itself proof of reuse permission.
- When cleaning file structure, fix the **leading space in its filename** using git mv; maintain Git history and references.

### Schedules and honesty

- Display **scheduled** vs **real-time** distinctly; show last updated timestamp and source.
- Handle weekends, Japanese national holidays, GTFS calendar_dates exceptions, winter/summer service changes, and year-end special service. Dates/times use Asia/Tokyo and GTFS service-day semantics (including times past 24:00).
- Show "no verified timetable for this date" when a feed's coverage expires, not fake future predictions.
- If realtime is absent, stale, or failing, show valid cached scheduled times with a clear label.
- Offer an official-source link from each stop/route for checking exceptional disruptions.
- Geometry may be approximate; **departure times should not be approximated**.

## 3. Technical design (prefer the simplest viable implementation)

### Recommended stack

- **PWA:** React + TypeScript + Vite (or similarly lightweight familiar stack); mobile-first layout; manifest and service worker.
- **Map:** MapLibre GL JS with an OSM-derived style/provider that permits the intended usage. Display required OSM/style/dataset attribution. Do not bulk-download the public OSM tile server for offline maps.
- **Schedule ingestion:** small command-line source adapters run on Beechan. TypeScript or Python are both acceptable; choose one that offers straightforward GTFS/HTML/JSON parsing and tests.
- **Storage/build:** keep a canonical normalized intermediate database or files; export compact, versioned, static chunks/indexes for the client. Avoid shipping huge raw GTFS ZIPs to each phone on every launch.
- **Hosting:** start with HTTPS static hosting (e.g., GitHub Pages or Cloudflare Pages) for the PWA and data snapshots. Device-local favorites; no login required for public transit data. Beechan can build/refresh snapshots, but the app should still work if Beechan is offline.
- **Optional live bridge:** if source APIs cannot be called from the browser due to CORS/headers, use a tiny read-only proxy/worker with source-specific allowlists, caching and rate limits. Avoid a generic open proxy. Do not make live requests a dependency for browsing cached timetables.
- **Privacy:** geolocation and favorites stay on device unless explicitly needed otherwise; avoid analytics by default; never commit cookies, user positions or credentials.

### Normalized concepts

Implement source adapters behind an explicit interface, rather than mixing scraping with components:

- **Operator**: stable internal key, Japanese name, attribution.
- **Stop/boarding point**: internal ID, source ID, source, lat/lon (optional), uncertainty, aliases, operator/platform/direction. Opposite-side stops must not be blindly merged.
- **Route and pattern**: operator, public line number, direction/headsign, ordered stop IDs, shape if available.
- **Trip and service**: departure sequence, service calendar/exceptions, validity dates, timezone, source/version.
- **Departure**: stop, route/pattern, destination, scheduled timestamp, optional observed/predicted timestamp, reliability/status.
- **Source health**: fetched at, coverage dates, parser status, validation counts, age/staleness, last successful version.

Keep original source IDs namespaced by provider; never assume IDs are globally unique or stable. When joining JR stops to OSM coordinates, use cautious name normalization + geographic bounds and manual overrides; retain match confidence and provenance. Prefer GTFS shapes.txt; fall back to OSM transit relations; otherwise draw clearly approximate stop-to-stop lines.

### Offline and update strategy

- Offline **favorites, loaded stop catalog and the schedules already cached on device**; map tiles are online initially.
- Versioned static data, atomic replacement on successful validation, rollback to last known-good snapshots.
- Probe sources and refresh on a conservative schedule (e.g., daily checks with conditional downloads; adapt to actual publisher update cadence). Don't continually scrape.
- Make stale/missing JR data visible and link to the official timetable; one bad source must not blank the other operators.
- Distinguish optional future "fully offline map" from the first release; it requires an appropriate tile provider/package and licensing.

## 4. Delivery phases and gates

### Phase 0 — Repository reconnaissance and source audit

Deliverables:
- Read README and inspect the root PDF locally; record findings and provenance.
- Make **docs/source-inventory.md**: sources, format, access, license, coverage, validity, confidence, update frequency, failure modes, examples.
- Make **docs/architecture.md**: minimal proposed stack, data contracts, and topology; mark assumptions.
- Check HODA GTFS files and representative coverage; validate they contain real stop/trip/service data for Sapporo.
- Prove or disprove JR Ekibus/Busdia approach with repeatable requests and fixture tests.

**Gate:** reliable path to *real, regular JR Bus scheduled times* identified and demonstrated, plus viable GTFS for Chuo and Jotetsu. No UI implementation before the JR approach is reasonably understood. If blocked, report honestly.

### Phase 1 — Data engine / one unified query

Deliverables:
- One command to fetch/parse each operator and build normalized local data.
- Tiny sample corpus and source-adapter tests; schema validation and diagnostic logs.
- Search stop by name and query next N departures for a stop/date/direction from all three providers, initially via CLI or minimal HTTP route.
- Check timezone, overnight departures, weekends/holidays and route-direction identity.
- Store source timestamps and surface stale-data warnings.

**Gate:** produce a reproducible **3-operator comparison report** with actual stop names, dates, times, source URLs and pass/fail against official visible schedules. Include JR. Don't proceed on fabricated placeholder data.

### Phase 2 — Useful Android PWA

Deliverables:
- HTTPS installable PWA, map with stop markers, location permission and stop bottom sheet.
- Today/another-date next departures; operator/route filtering, search, route highlights and favorite boarding points.
- Quick loading and reasonable mobile performance; cache static schedules.
- Test on Android Chrome and a second phone-size viewport, plus offline/stale scenario.

**Gate:** user can open a bus stop on the map and see accurate upcoming schedules for each of the three operators, without another subscription.

### Phase 3 — Complete network plan

Deliverables:
- Working PDF viewer tab for the supplied schematic (or an explained replacement if necessary).
- Smooth touch zoom/pan and simple return to geographic map.
- Optional major-hub links only after the plain PDF view works.

**Gate:** schematic is readable and usable on phone; no need to hand-create a perfectly aligned interactive diagram.

### Phase 4 — Practical polish and optional live departures

Deliverables:
- Live city Ekibus/Buskita adapter where useful and feasible, with appropriate cache/failover.
- Clearly labeled realtime vs schedule; test delays, missing vehicle data and outages.
- Better place search, manual mapping overrides, route traces and small UX refinements based on real daily use.
- Health/update dashboard only if actual maintenance pain warrants it.

**Gate:** app remains useful when live source is broken, offline, or slow.

## 5. Testing and field verification

- Test **all three operators** on realistic stops and routes, with opposite directions where relevant.
- Check weekday, Saturday, Sunday/holiday, late evening, service-date boundary and winter timetable changes.
- Verify sources with visible official timetables at the same stop, direction and date. Save screenshots/URLs in investigation notes where permitted.
- Test parsing against small saved fixtures and an intentionally changed/invalid upstream response.
- Validate map markers in the real world: correct vicinity and curbside are more important than sub-meter precision. Mark uncertain pins.
- Android: GPS permission denied, slow network, airplane mode after a successful sync, screen rotation, install prompt, big finger-friendly tap targets.
- Track coverage and issues: stop count, routes, trips, coverage by agency, mismatches, unknown coordinates, feed date span, last successful fetch.
- Never equate "the scraper returned 200 OK" with "these are today's correct departures."

## 6. Work discipline for Beechan / Codex

- Start by reading this battleplan and inspecting the repository; do **not** presume app code already exists.
- Before each meaningful implementation step, write a small scoped task in **docs/progress.md** with goal, source, assumptions, tests and next step.
- Work in small verifiable slices; commit logical milestones with useful messages. Do not silently change scope or initiate a large app rewrite.
- Keep **evidence separate from assumptions**. Link primary sources and preserve representative reproducible examples; avoid speculation presented as fact.
- Prefer practical tests over elaborate speculative architecture. Avoid spending tokens on ornamental UI before JR data is proven.
- Preserve user's PDF and unrelated files; do not delete or regenerate it without inspection.
- Never commit credentials, session cookies, personal location data or giant scraped datasets; keep private fixtures and build outputs gitignored as appropriate.
- When a source fails, implement a sensible fallback, bounded retries/backoff, and honest UI degradation. No bypass of sign-in, paywalls, or anti-bot controls.
- Report at each gate: **what works, exact evidence, what doesn't, commit SHA, and recommended next task**.
- Reserve significant product decisions for discussion with the user in ChatGPT when several reasonable designs exist; Beechan should choose routine implementation details autonomously.
- Keep the system runnable on Debian Beechan with short setup commands and a simple README.

## 7. First assignment for Codex CLI (do this now, then report)

**Objective:** establish the trustworthy three-operator source path, with **JR local bus as the hard constraint**. Do not build the UI yet.

1. Inspect the current repo, the oddly spaced root PDF, and available tooling.
2. Create docs/source-inventory.md and docs/progress.md; investigate HODA Chuo/Jotetsu GTFS and validate the date coverage and number of relevant Sapporo routes/stops.
3. Probe Sapporo Ekibus for **JR Hokkaido Bus local** timetables on multiple routes. Capture only compact non-sensitive sample request/response fixtures, compare a weekday and a weekend timetable against the official interface, and record how stop IDs and directions are found.
4. Investigate Busdia as an HTML/stop-list fallback and JR operator PDFs if needed. Establish the best order of fallback and coordinate sources.
5. Sketch the minimal data schema/interfaces and a 3-operator CLI query test plan (implement a small probe if it helps prove the source).
6. Update docs/progress.md with findings, exact working commands, limitations, confidence, next implementation steps and commit SHA.
7. **Stop after this investigation gate**. Summarize findings for discussion before building the PWA.

**Definition of done:** We can point to repeatable evidence that regular JR local bus departures can be obtained, explain how each of the three operators will be kept current, and know whether the supplied PDF can be reused as a zoomable reference. If JR cannot yet be proven, provide a concrete blocker and the next best test rather than pretending phase 0 passed.
