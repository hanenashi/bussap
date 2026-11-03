# Progress

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
