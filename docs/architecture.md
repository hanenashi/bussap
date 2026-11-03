# Architecture sketch — provisional

The first source-validation implementation is a Python standard-library CLI. No app stack or deployment has been chosen. This sketch keeps the first implementation small while source checks continue.

```text
HODA GTFS + JR timetable source
              |
       Beechan scheduled fetch + validation
              |
      versioned local snapshot + source health
              |
     small read-only HTTPS web app and API
              |
    Pixel browsers via Tailscale Serve initially
```

Beechan owns fetching, parsing, validation, and scheduled refresh. Phones receive compact stop, route and departure data; they do not scrape the upstream sites. Snapshot replacement should be atomic after validation, retaining the last good version. Each response should carry source, revision/coverage date, fetched time and stale status.

Initial record keys should namespace the source and distinguish `stop`, boarding position, route, pattern/direction and service-day category. A departure has a scheduled time and optional live time; they are separate fields. Coordinates and route shapes retain provenance and uncertainty. JR's day-category times can be shown with the user-approved warning `cant promise correct times now`; exceptional-date validation is not a launch gate for this personal app.

`scripts/departures.py` currently returns these source-specific records as JSON. Chuo/Jotetsu results include date-specific `scheduled_at` only within GTFS coverage. JR results carry a category and a warning, with `scheduled_at: null`. `scripts/server.py` exposes the same data through loopback HTTP and a separate tailnet-only Tailscale Serve port. The phone UI can use same-origin requests from this service; no browser CORS access to upstream sites is required.

Beechan's `bussap-refresh.timer` conditionally checks HODA feeds daily and validates replacements. JR timetable lookups remain on demand, bounded by exact stop/pattern endpoints and a short in-memory cache; phones never call Ekibus directly. A future snapshot job may prefetch favorite JR patterns if actual usage warrants it.

Tailscale Serve is the easiest first HTTPS route for two phones already on the tailnet. A browser-only remote option can be evaluated later with Cloudflare Tunnel plus Access, which would add identity configuration but no router port forwarding. Neither network choice blocks the source audit or data model. The map base layer and viewer library can be selected after a unified stop/date query works.
