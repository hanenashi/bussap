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

JR queries infer one of Ekibus's four day categories using the [Cabinet Office 2026–2027 holiday list](https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html), or `--jr-category` can select one explicitly. The result is labeled `day_category_candidate_unverified_for_date` and carries the user-facing warning `cant promise correct times now`. The API does not establish seasonal validity or exceptional operations for a requested date. The bounded `python3 scripts/probe_jr.py` checks three known local patterns against the audit fixture; a changed revision causes the query to withhold departures until reviewed.

Run the small local tests with:

```sh
python3 -m unittest discover -s tests -v
```

## Beechan phone-facing service

Beechan runs a read-only API bound to `127.0.0.1:8788`. Tailscale Serve exposes it only to the tailnet at:

```text
https://beechan.tail8d9f69.ts.net:10002
```

Open that URL in a phone browser for the street map and stop search. Tap a point (or a cluster, then an exact boarding point) to preview departures and open the full timetable. The current-location button requests permission only when tapped. JR points with numbers filter the route list to that boarding position. Choose today, tomorrow, or another date in the full timetable. The map uses OpenStreetMap tiles for the visible viewport; it does not download offline maps or draw unverified route lines. The map's **参考路線図** link opens the supplied 2016 PDF as a historical reference in a separate, nearly full-screen tab with a back button. The installable/offline PWA and a current network diagram are later slices; see [PDF assessment](docs/pdf-assessment.md).

The map follows the [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/): visible attribution, browser caching, and no bulk prefetch. The public tile service is best-effort; BUSSAP's timetable API still works if the background map tiles fail. The reference viewer uses vendored [PDF.js](https://mozilla.github.io/pdf.js/) 5.4.624 under its Apache 2.0 license.

The API supports `GET /health`, `GET /api/stops?operator=...&name=...`, `GET /api/jr-patterns?stop=...`, and `GET /api/departures?operator=...&stop=...&date=...`. Departure query parameters match the CLI (`after`, `limit`, `route`, `destination`, `pattern`, `jr_category`). It accepts no writes. JR responses include the exact user warning `cant promise correct times now` and withhold times after an unreviewed source revision change. The server caches small JR lookups briefly to avoid repeated upstream calls; Chuo and Jotetsu queries read Beechan's local feed files.

Versioned systemd user units live in `ops/systemd/`. On Beechan they are symlinked into `~/.config/systemd/user/` and enabled:

```sh
systemctl --user status bussap-api.service bussap-refresh.timer
systemctl --user start bussap-refresh.service
curl -fsS http://127.0.0.1:8788/health
tailscale serve status
```

The timer checks the two HODA ZIPs daily around 04:20 JST, with up to 20 minutes of jitter. Conditional requests leave unchanged feeds in place; a valid replacement keeps a `.previous.zip` backup in ignored `.local-data/`. To stop access, disable only BUSSAP's mapping with `tailscale serve --https=10002 off`. Other Serve mappings belong to other projects.

The same timer now refreshes a compact JR boarding-point map snapshot from Sapporo Ekibus's `/Get_marker_data`. It validates operator IDs, names, Hokkaido coordinates, and a minimum record count before atomic replacement. The previous snapshot stays available if a refresh fails. Inspect it with `python3 scripts/map_data.py refresh-jr`. The map API is `GET /api/map-stops?bbox=south,west,north,east&zoom=15&operator=all`; it returns bounded clusters and exact stop IDs. Leaflet 1.9.4 is vendored under `web/vendor/` with its MIT license.
