# Architecture — current small deployment

The current deployment is a Python standard-library data engine and read-only HTTP service on Beechan, with a vanilla JavaScript phone UI. Leaflet renders the street map using visible-viewport OpenStreetMap tiles. The service remains tailnet-only through Tailscale Serve.

```text
HODA GTFS + Sapporo Ekibus JR sources
              |
       Beechan scheduled fetch + validation
              |
      versioned local snapshot + source health
              |
     small read-only HTTPS web app and API
              |
    Pixel browsers via Tailscale Serve initially
```

Beechan owns fetching, parsing, validation, and scheduled refresh. Phones receive compact stop, map and departure data; they do not scrape the upstream transit sites. Snapshot replacement is atomic after validation, retaining the last good version. Chuo/Jotetsu GTFS and a compact JR map marker snapshot are refreshed daily. JR timetable lookups remain on demand with a bounded cache.

Favorites are a small browser-local list keyed by source stop ID, optional GTFS line filter, and JR pattern ID. They contain only public stop/route metadata and are not sent to Beechan as a write or synchronized between phones. Opening one still queries the current timetable; a removed upstream stop or pattern is reported as unavailable.

Initial record keys should namespace the source and distinguish `stop`, boarding position, route, pattern/direction and service-day category. A departure has a scheduled time and optional live time; they are separate fields. Coordinates and route shapes retain provenance and uncertainty. JR's day-category times can be shown with the user-approved warning `cant promise correct times now`; exceptional-date validation is not a launch gate for this personal app.

`scripts/departures.py` currently returns these source-specific records as JSON. Chuo/Jotetsu results include date-specific `scheduled_at` only within GTFS coverage. JR results carry a category and a warning, with `scheduled_at: null`. `scripts/server.py` exposes the same data through loopback HTTP and a separate tailnet-only Tailscale Serve port. The phone UI can use same-origin requests from this service; no browser CORS access to upstream sites is required.

Beechan's `bussap-refresh.timer` conditionally checks HODA feeds and refreshes validated JR marker coordinates daily. JR timetable lookups remain bounded by exact stop/pattern endpoints and a short in-memory cache; phones never call Ekibus directly. A future snapshot job may prefetch favorite JR patterns if actual usage warrants it.

Tailscale Serve is the first HTTPS route for two phones already on the tailnet. A browser-only remote option can be evaluated later. The map loads only currently visible OpenStreetMap raster tiles, shows attribution, and does not prefetch or cache tiles for offline use. A bounded `bbox` API groups dense stops. GTFS coordinates identify individual boarding points; JR's `Get_marker_data` identifies numbered boarding locations when available. The map does not turn stop sequences into unverified street paths. The supplied 2016 PDF is served through a minimal, private reference viewer; see [pdf-assessment.md](pdf-assessment.md).
