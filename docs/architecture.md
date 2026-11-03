# Architecture sketch — provisional

No app stack or deployment has been chosen. This sketch keeps the first implementation small while source checks continue.

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

Initial record keys should namespace the source and distinguish `stop`, boarding position, route, pattern/direction and service-day category. A departure has a scheduled time and optional live time; they are separate fields. Coordinates and route shapes retain provenance and uncertainty. For JR's day-category source, the app must not claim a specific-date schedule without separate exception and seasonal verification.

Tailscale Serve is the easiest first HTTPS route for two phones already on the tailnet. A browser-only remote option can be evaluated later with Cloudflare Tunnel plus Access, which would add identity configuration but no router port forwarding. Neither network choice blocks the source audit or data model. The map base layer and viewer library can be selected after a unified stop/date query works.
