#!/usr/bin/env python3
"""Read-only localhost API for the BUSSAP source-validation data engine."""

import argparse
import json
import threading
import time
import zipfile
from collections import OrderedDict
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import departures


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
        return CACHE.get_or_make(key, 3600 if operator == "jr" else 300, lambda: departures.find_stops(operator, name, limit))
    if path == "/api/jr-patterns":
        station_id = bounded_int(one(params, "stop", required=True), "stop", 1, 999999999)
        limit = bounded_int(one(params, "limit", default="30"), "limit", 1, 50)
        key = ("patterns", station_id, limit)
        return CACHE.get_or_make(key, 900, lambda: departures.jr_patterns(station_id, limit))
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
