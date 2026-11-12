#!/usr/bin/env python3
"""Read-only localhost API for the BUSSAP source-validation data engine."""

import argparse
import json
import math
import threading
import time
import zipfile
from collections import OrderedDict
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import departures
import map_data
import buskita


class BoundedCache:
    def __init__(self, max_entries=128):
        self.entries = OrderedDict()
        self.max_entries = max_entries
        self.lock = threading.Lock()

    def get_or_make(self, key, ttl_seconds, make):
        now = time.monotonic()
        with self.lock:
            entry = self.entries.get(key)
            if entry and entry[0] > now:
                self.entries.move_to_end(key)
                return entry[1]
        value = make()
        with self.lock:
            self.entries[key] = (time.monotonic() + ttl_seconds, value)
            self.entries.move_to_end(key)
            while len(self.entries) > self.max_entries:
                self.entries.popitem(last=False)
        return value


CACHE = BoundedCache()
WEB_DIR = Path(__file__).resolve().parents[1] / "web"
NETWORK_PDF = WEB_DIR.parent / " sapporobus.pdf"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json; charset=utf-8"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/icons/icon-192.png": ("icons/icon-192.png", "image/png"),
    "/icons/icon-512.png": ("icons/icon-512.png", "image/png"),
    "/network-map": ("network-map.html", "text/html; charset=utf-8"),
    "/network-map.js": ("network-map.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/map.css": ("map.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/map.js": ("map.js", "text/javascript; charset=utf-8"),
    "/vendor/leaflet.js": ("vendor/leaflet.js", "text/javascript; charset=utf-8"),
    "/vendor/leaflet.css": ("vendor/leaflet.css", "text/css; charset=utf-8"),
    "/vendor/pdf.mjs": ("vendor/pdf.mjs", "text/javascript; charset=utf-8"),
    "/vendor/pdf.worker.mjs": ("vendor/pdf.worker.mjs", "text/javascript; charset=utf-8"),
}


def one(params, name, required=False, default=None):
    values = params.get(name, [])
    if len(values) > 1:
        raise ValueError(f"repeat parameter: {name}")
    if not values or not values[0]:
        if required:
            raise ValueError(f"missing parameter: {name}")
        return default
    return values[0]


def bounded_int(value, name, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name}") from exc
    if not low <= number <= high:
        raise ValueError(f"{name} must be {low}–{high}")
    return number


def feed_health():
    feeds = {}
    for operator in departures.FEEDS:
        path = departures.DATA_DIR / f"{operator}.zip"
        if not path.exists():
            feeds[operator] = {"status": "missing"}
            continue
        try:
            with zipfile.ZipFile(path) as archive:
                info = next(departures.rows(archive, "feed_info.txt"))
            feeds[operator] = {
                "status": "ready",
                "coverage_from": info["feed_start_date"],
                "coverage_through": info["feed_end_date"],
                "fetched_at": datetime.fromtimestamp(path.stat().st_mtime, departures.TOKYO).isoformat(),
            }
        except (OSError, KeyError, StopIteration, zipfile.BadZipFile):
            feeds[operator] = {"status": "invalid"}
    return {"status": "ready" if all(r["status"] == "ready" for r in feeds.values()) else "degraded", "feeds": feeds, "jr_reviewed_revision": departures.JR_REVIEWED_REVISION}


def dispatch(path, params):
    if path == "/health":
        return feed_health()
    if path == "/api/stops":
        operator = one(params, "operator", required=True)
        if operator not in (*departures.FEEDS, "jr"):
            raise ValueError("unknown operator")
        name = one(params, "name", required=True)
        if len(name) > 80:
            raise ValueError("name too long")
        limit = bounded_int(one(params, "limit", default="20"), "limit", 1, 50)
        key = ("stops", operator, name, limit)
        def find():
            try:
                return departures.find_stops(operator, name, limit)
            except OSError:
                if operator != "jr":
                    raise
                stops, _, fetched_at = map_data.catalog()
                needle = buskita.norm(name).casefold()
                matches = [stop for stop in stops if stop["operator"] == "jr" and needle in buskita.norm(stop["name"]).casefold()]
                matches.sort(key=lambda stop: (buskita.norm(stop["name"]).casefold() != needle, stop["name"], stop["id"]))
                return {"operator": "jr", "query": name, "total_matches": len(matches),
                        "stops": matches[:limit], "source": "cached_jr_markers", "fetched_at": fetched_at}
        return CACHE.get_or_make(key, 3600 if operator == "jr" else 300, find)
    if path == "/api/map-stops":
        bbox_text = one(params, "bbox", required=True)
        try:
            bbox = tuple(float(value) for value in bbox_text.split(","))
        except ValueError as exc:
            raise ValueError("invalid bbox") from exc
        if len(bbox) != 4 or not all(math.isfinite(value) for value in bbox):
            raise ValueError("invalid bbox")
        south, west, north, east = bbox
        if not (40 <= south < north <= 46 and 138 <= west < east <= 146 and north - south <= 2 and east - west <= 2):
            raise ValueError("bbox outside supported area")
        zoom = bounded_int(one(params, "zoom", required=True), "zoom", 10, 19)
        operator = one(params, "operator", default="all")
        if operator not in (*departures.FEEDS, "jr", "all"):
            raise ValueError("unknown operator")
        catalog, warnings, fetched_at = map_data.catalog()
        result = map_data.features_in_bbox(catalog, bbox, zoom, operator)
        return {"operator": operator, "bbox": bbox, "zoom": zoom, **result, "warnings": warnings,
                "jr_markers_fetched_at": fetched_at}
    if path == "/api/jr-patterns":
        station_id = bounded_int(one(params, "stop", required=True), "stop", 1, 999999999)
        limit = bounded_int(one(params, "limit", default="30"), "limit", 1, 50)
        key = ("patterns", station_id, limit)
        def get_patterns():
            try:
                return departures.jr_patterns(station_id, limit)
            except OSError:
                markers = map_data.catalog()[0]
                stops = CACHE.get_or_make(("buskita-catalog",), 3600, buskita.catalog)
                return buskita.patterns(station_id, markers, stops, limit)
        return CACHE.get_or_make(key, 900, get_patterns)
    if path == "/api/route-details":
        operator = one(params, "operator", required=True)
        if operator not in (*departures.FEEDS, "jr"):
            raise ValueError("unknown operator")
        stop = one(params, "stop", required=True)
        if operator == "jr":
            station_id = bounded_int(stop, "stop", 1, 999999999)
            pattern = one(params, "pattern", required=True)
            if len(pattern) > 80:
                raise ValueError("pattern too long")
            course_id = bounded_int(one(params, "course", required=True), "course", 1, 999999999)
            key = ("jr-route", station_id, pattern, course_id)
            return CACHE.get_or_make(key, 3600, lambda: departures.jr_route_details(station_id, pattern, course_id, map_data.catalog()[0]))
        trip = one(params, "trip", required=True)
        if len(stop) > 80 or len(trip) > 160:
            raise ValueError("stop or trip ID too long")
        sequence = bounded_int(one(params, "sequence", required=True), "sequence", 0, 10000)
        return departures.gtfs_route_details(operator, trip, stop, sequence)
    if path == "/api/departures":
        operator = one(params, "operator", required=True)
        if operator not in (*departures.FEEDS, "jr"):
            raise ValueError("unknown operator")
        stop = one(params, "stop", required=True)
        service_date = date.fromisoformat(one(params, "date", required=True))
        after = one(params, "after", default="00:00")
        departures.parse_minutes(after)
        limit = bounded_int(one(params, "limit", default="10"), "limit", 1, 50)
        if operator == "jr":
            station_id = bounded_int(stop, "stop", 1, 999999999)
            pattern = one(params, "pattern", required=True)
            if len(pattern) > 80:
                raise ValueError("pattern too long")
            category_raw = one(params, "jr_category")
            category = bounded_int(category_raw, "jr_category", 1, 4) if category_raw else None
            key = ("jr-departures", station_id, pattern, service_date, after, limit, category)
            if pattern.startswith("buskita:"):
                def get_buskita():
                    markers = map_data.catalog()[0]
                    stops = CACHE.get_or_make(("buskita-catalog",), 3600, buskita.catalog)
                    return buskita.departures_at(station_id, pattern, service_date, after, limit, markers, stops)
                return CACHE.get_or_make(key, 120, get_buskita)
            return CACHE.get_or_make(key, 600, lambda: departures.query_jr(station_id, pattern, service_date, after, limit, category))
        if len(stop) > 80:
            raise ValueError("stop ID too long")
        route = one(params, "route")
        destination = one(params, "destination")
        if route and len(route) > 80 or destination and len(destination) > 80:
            raise ValueError("filter too long")
        return departures.query_gtfs(operator, stop, service_date, after, limit, route, destination)
    raise LookupError("not found")


class Handler(BaseHTTPRequestHandler):
    server_version = "BUSSAP/0.1"

    def do_GET(self):
        if len(self.path) > 2048:
            self.send_json(414, {"error": "request URI too long"})
            return
        parsed = urlsplit(self.path)
        if parsed.path == "/network-map.pdf":
            self.send_pdf()
            return
        if parsed.path in STATIC_FILES:
            self.send_static(*STATIC_FILES[parsed.path])
            return
        params = parse_qs(parsed.query, keep_blank_values=True)
        try:
            result = dispatch(parsed.path, params)
            status = 503 if parsed.path == "/health" and result["status"] != "ready" else 200
            self.send_json(status, result)
        except LookupError:
            self.send_json(404, {"error": "not found"})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except (OSError, KeyError, StopIteration, zipfile.BadZipFile) as exc:
            self.send_json(502, {"error": "source unavailable", "detail": type(exc).__name__})

    def do_POST(self):
        self.send_json(405, {"error": "read-only API"})

    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, filename, content_type):
        try:
            body = (WEB_DIR / filename).read_bytes()
        except OSError:
            self.send_json(404, {"error": "not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_pdf(self):
        try:
            body = NETWORK_PDF.read_bytes()
        except OSError:
            self.send_json(404, {"error": "not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", 'inline; filename="sapporobus-reference.pdf"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        # Avoid storing stop searches and future phone locations in systemd logs.
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()
    if args.host != "127.0.0.1":
        parser.error("BUSSAP API must bind to 127.0.0.1; use Tailscale Serve for HTTPS access")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
