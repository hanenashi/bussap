# BUSSAP

Personal Sapporo bus map and timetable project. Beechan serves a street map, stop search, and scheduled departures for Hokkaido Chuo Bus, Jotetsu, and JR Hokkaido Bus local routes. See [battleplan.md](battleplan.md) and [docs/source-inventory.md](docs/source-inventory.md).

## Source query on Beechan

Python 3 with the standard library is sufficient. The owner has completed HODA's use-purpose form. Run from the repository root:

```sh
python3 scripts/departures.py refresh all
python3 scripts/departures.py find-stops jotetsu --name 札幌駅
python3 scripts/departures.py query jotetsu --stop S010800000100100 --date 2026-11-07 --route 南５４ --destination 南町四丁目 --limit 3
python3 scripts/departures.py find-stops jr --name 新札幌駅
python3 scripts/departures.py jr-patterns --stop 340238 --limit 5
python3 scripts/departures.py query jr --stop 340238 --pattern 340044:340100-0 --date 2026-11-03 --limit 3
```

`refresh` validates and atomically replaces the two GTFS ZIPs in ignored `.local-data/`, retaining a `.previous.zip` backup. `BUSSAP_DATA_DIR` can point to another local cache directory. `find-stops` returns source-specific boarding IDs; shared names can refer to several different curbside positions. JR patterns include line, course, direction and boarding number.

GTFS queries apply `calendar.txt` plus `calendar_dates.txt`, reject dates outside feed coverage, and return `scheduled_at` in Asia/Tokyo. The `--date` is the **service date**: a GTFS time such as `25:15:00` belongs to that service day and gets a next-calendar-day timestamp. `--after` uses the same service-day clock and accepts times beyond 24:00.

JR queries infer one of Ekibus's four day categories using the [Cabinet Office 2026–2027 holiday list](https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html), or `--jr-category` can select one explicitly. The result is labeled `day_category_candidate_unverified_for_date` and shows the source timetable revision date (currently 2026/04/01) with a note that operation on the selected date is unverified. The API also returns when Beechan fetched that timetable; the phone's offline copy has its own cache time. The API does not establish seasonal validity or exceptional operations for a requested date. The bounded `python3 scripts/probe_jr.py` checks three known local patterns against the audit fixture; a changed revision causes the query to withhold departures until reviewed.

Run the small local tests with:

```sh
python3 -m unittest discover -s tests -v
```

## Beechan phone-facing service

Beechan runs a read-only API bound to `127.0.0.1:8788`. Tailscale Serve exposes it only to the tailnet at:

```text
https://beechan.tail8d9f69.ts.net:10002
```

Open that URL in a phone browser for the street map and stop search. Tap a point (or a cluster, then an exact boarding point) to preview departures and open the full timetable. Tap a Chuo or Jotetsu departure row to show only that line, then tap **すべて見る** to clear the filter. The current-location button requests permission only when tapped. JR points with numbers filter the route list to that boarding position. Choose today, tomorrow, or another date in the full timetable. The map uses OpenStreetMap tiles for the visible viewport; it does not download offline maps or draw unverified route lines. The map's **参考路線図** link opens the supplied 2016 PDF as a historical reference in a separate tab in a browser, or in the same window in the installed app. Drag it with one finger, pinch or double tap to zoom as far as 32×, and use its back button to return. At close zoom, the visible section redraws sharply after movement stops. See [PDF assessment](docs/pdf-assessment.md).

On a departure screen, tap **☆ この乗り場を保存** to add a shortcut above the map. A selected Chuo/Jotetsu line is saved with the exact boarding stop; JR saves its chosen route pattern and boarding number. Tap **★ 保存済み** on the same screen to remove it. Favorites live only in that browser's localStorage and do not sync between phones. A shortcut requests the current timetable when online and can reopen a previously viewed response when offline.

BUSSAP now has a web app manifest and a service worker, so Chrome can add it to the home screen from its browser menu. After an online visit, the app shell opens without Beechan. Full timetable views already opened on that browser are saved for offline fallback by exact stop, date, and line/pattern; up to 30 recent views are retained. A saved favorite is the quickest way to reach one offline. The screen labels cached results with their retrieval time and says they cover only the previously viewed range. Dates that were never viewed show a clear message. Stop search, new timetables, OpenStreetMap tiles, and the PDF still need a connection. The icon source is `web/icons/icon.svg`; the manifest uses 192 and 512 px PNGs generated from it.

The map follows the [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/): visible attribution, browser caching, and no bulk prefetch. The public tile service is best-effort; BUSSAP's timetable API still works if the background map tiles fail. The reference viewer uses vendored [PDF.js](https://mozilla.github.io/pdf.js/) 5.4.624 under its Apache 2.0 license.

The API supports `GET /health`, `GET /api/stops?operator=...&name=...`, `GET /api/jr-patterns?stop=...`, and `GET /api/departures?operator=...&stop=...&date=...`. Departure query parameters match the CLI (`after`, `limit`, `route`, `destination`, `pattern`, `jr_category`). It accepts no writes. JR responses include the source revision date, a selected-date validity note, and Beechan's retrieval time; they withhold times after an unreviewed source revision change. The server caches small JR lookups briefly to avoid repeated upstream calls; Chuo and Jotetsu queries read Beechan's local feed files.

Versioned systemd user units live in `ops/systemd/`. On Beechan they are symlinked into `~/.config/systemd/user/` and enabled:

```sh
systemctl --user status bussap-api.service bussap-refresh.timer
systemctl --user start bussap-refresh.service
curl -fsS http://127.0.0.1:8788/health
tailscale serve status
```

The timer checks the two HODA ZIPs daily around 04:20 JST, with up to 20 minutes of jitter. Conditional requests leave unchanged feeds in place; a valid replacement keeps a `.previous.zip` backup in ignored `.local-data/`. To stop access, disable only BUSSAP's mapping with `tailscale serve --https=10002 off`. Other Serve mappings belong to other projects.

The same timer now refreshes a compact JR boarding-point map snapshot from Sapporo Ekibus's `/Get_marker_data`. It validates operator IDs, names, Hokkaido coordinates, and a minimum record count before atomic replacement. The previous snapshot stays available if a refresh fails. Inspect it with `python3 scripts/map_data.py refresh-jr`. The map API is `GET /api/map-stops?bbox=south,west,north,east&zoom=15&operator=all`; it returns bounded clusters and exact stop IDs. Leaflet 1.9.4 is vendored under `web/vendor/` with its MIT license.

## Credential-gated public gateway

`scripts/public_gateway.py` is a separate localhost service at `127.0.0.1:8790`. A dedicated userspace Tailscale node named `bussap-gate` exposes it through Funnel at `https://bussap-gate.tail8d9f69.ts.net/`. The original private BUSSAP app remains at port 10002 on Beechan's existing Tailscale node. The gateway returns only its sign-in page and public branding files to visitors without a valid session; it requires a registered WebAuthn credential and device unlock for app data and the historical PDF. It accepts at most two single-device credentials. Enrollment uses a one-use, seven-day code; login sessions last 14 days. The dependency is pinned in `requirements-gateway.txt` and runs from ignored `.venv/`; rebuild it with `python3 -m venv .venv && .venv/bin/pip install -r requirements-gateway.txt`.

The manifest and 192/512 px icon files are reachable without an app session so Android can fetch or refresh the installed icon. Their URLs are versioned in the manifest. The PDF viewer is linked in the signed-in app and remains online-only; unauthenticated requests to its viewer, script, and PDF receive 404. No source timetable API or app JavaScript is public without a session.

The dedicated node also has a tailnet-only staging URL at `https://bussap-gate.tail8d9f69.ts.net:10003/`. Its state is in ignored `.local-data/tailnode/` and its socket is `%t/bussap-tailnode.sock`; `ops/systemd/bussap-tailnode.service` keeps it separate from Beechan's existing Tailscale daemon. Both gateway and tailnode user services are enabled, and the user manager has linger enabled. No existing Serve mapping was converted to Funnel. The public hostname is now the WebAuthn RP ID, so registration on either gateway URL works for the public app. Both intended phones have enrolled one credential each; the two-phone limit is full.

To create an enrollment code, run `.venv/bin/python scripts/public_gateway.py invite phone-label`. The command writes the code to a mode-0600 file in ignored `.local-data/`; it does not print the code. Enter it on the gateway sign-in page on that phone, then delete the code file. Use `.venv/bin/python scripts/public_gateway.py list` to see enrolled labels and `revoke phone-label` to invalidate a lost phone's credential and sessions. To close the public gateway without changing the original BUSSAP service, run `tailscale --socket=/run/user/1000/bussap-tailnode.sock funnel --https=443 off`.
