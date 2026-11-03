#!/usr/bin/env python3
"""Bounded three-operator scheduled departure query for source validation.

GTFS results are date-specific within feed coverage. JR results are day-category
candidates; the Ekibus endpoint does not certify seasonal or exceptional dates.
"""

import argparse
import csv
import email.utils
import io
import json
import os
import shutil
import sys
import tempfile
import unicodedata
import urllib.request
import urllib.error
import zipfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("BUSSAP_DATA_DIR", ROOT / ".local-data"))
TOKYO = ZoneInfo("Asia/Tokyo")
FEEDS = {
    "chuo": "https://ckan.hoda.jp/dataset/24d1dd70-5395-4d6b-b41f-0d83e8eabdb9/resource/dbadfccc-670e-49b9-be77-c3f346ee3160/download/hokkaido_chuo.zip",
    "jotetsu": "https://ckan.hoda.jp/dataset/24d1dd70-5395-4d6b-b41f-0d83e8eabdb9/resource/fef98fef-6fe2-472f-bde3-9d4f0a509a4a/download/joutetsu.zip",
}
AGENCIES = {"chuo": "北海道中央バス", "jotetsu": "じょうてつ"}
JR_ENDPOINT = "https://ekibus-api.city.sapporo.jp/Get_station_linelist_timetable"
JR_BASE = "https://ekibus-api.city.sapporo.jp"
REQUIRED_GTFS = {"agency.txt", "calendar.txt", "calendar_dates.txt", "feed_info.txt", "routes.txt", "stops.txt", "stop_times.txt", "trips.txt"}
HOLIDAYS = json.loads((ROOT / "fixtures" / "japan_holidays_2026_2027.json").read_text(encoding="utf-8"))
JR_REVIEWED_REVISION = json.loads((ROOT / "fixtures" / "jr_local_samples.json").read_text(encoding="utf-8"))["revision"]


def rows(archive: zipfile.ZipFile, name: str):
    return csv.DictReader(io.TextIOWrapper(archive.open(name), encoding="utf-8-sig"))


def post_json(url: str, values: dict) -> dict:
    body = urlencode(values).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(url, data=body, method="POST"), timeout=15) as response:
        data = json.load(response)
    if data.get("result") != "0":
        raise ValueError(f"source returned result {data.get('result')!r}")
    return data


def find_stops(operator: str, name: str, limit: int) -> dict:
    if operator == "jr":
        data = post_json(JR_BASE + "/get_route_prediction", {"kind": 0, "search_flg": 0, "search_word": name, "pos_flg": 0, "lang": "ja"})
        matches = [{"id": f"jr:{r['station_id']}", "name": r["name"]} for r in data.get("route_prediction", []) if r.get("company_id") == 34]
    else:
        path = DATA_DIR / f"{operator}.zip"
        if not path.exists():
            raise ValueError(f"{operator} feed missing; run refresh first")
        needle = unicodedata.normalize("NFKC", name).casefold()
        with zipfile.ZipFile(path) as archive:
            matches = [{"id": f"{operator}:{r['stop_id']}", "name": r["stop_name"], "lat": float(r["stop_lat"]), "lon": float(r["stop_lon"]), "boarding_position": r.get("platform_code") or None} for r in rows(archive, "stops.txt") if needle in unicodedata.normalize("NFKC", r["stop_name"]).casefold()]
        # Keep Sapporo stops visible even when a broad match has more than the API limit.
        matches.sort(key=lambda stop: (
            unicodedata.normalize("NFKC", stop["name"]).casefold() != needle,
            (stop["lat"] - 43.0687) ** 2 + ((stop["lon"] - 141.3508) * 0.73) ** 2,
            stop["name"], stop["id"],
        ))
    return {"operator": operator, "query": name, "total_matches": len(matches), "stops": matches[:limit]}


def jr_patterns(station_id: int, limit: int | None) -> dict:
    data = post_json(JR_BASE + "/Get_station_linelist", {"kind": 0, "station_id": station_id, "lang": "ja"})
    patterns = []
    for line in data.get("station_linelist", []):
        if line.get("company_id") != 34:
            continue
        for course in line.get("course_list") or []:
            patterns.append({
                "pattern": f"{line['line_id']}:{course['course_id']}-{course['pos']}",
                "route": line.get("line_name"),
                "direction": course.get("course_name"),
                "boarding_position": course.get("stop_no"),
            })
    return {"operator": "jr", "station_id": station_id, "total_patterns": len(patterns), "patterns": patterns[:limit] if limit else patterns}


def parse_minutes(value: str) -> int:
    hour, minute, *rest = value.split(":")
    if not hour.isdigit() or not minute.isdigit() or int(minute) > 59 or (rest and (len(rest) != 1 or not rest[0].isdigit() or int(rest[0]) > 59)):
        raise ValueError(f"invalid GTFS time: {value}")
    return int(hour) * 60 + int(minute)


def local_timestamp(service_date: date, gtfs_time: str) -> str:
    return (datetime.combine(service_date, time(0, 0), TOKYO) + timedelta(minutes=parse_minutes(gtfs_time))).isoformat()


def refresh(operator: str) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / f"{operator}.zip"
    fd, temporary = tempfile.mkstemp(prefix=f"{operator}-", suffix=".zip", dir=DATA_DIR)
    os.close(fd)
    try:
        headers = {"User-Agent": "bussap-source-audit/0.1"}
        if target.exists():
            headers["If-Modified-Since"] = email.utils.formatdate(target.stat().st_mtime, usegmt=True)
        request = urllib.request.Request(FEEDS[operator], headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as exc:
            if exc.code != 304 or not target.exists():
                raise
            with zipfile.ZipFile(target) as archive:
                info = next(rows(archive, "feed_info.txt"))
            return {"operator": operator, "status": "unchanged", "feed_start_date": info["feed_start_date"], "feed_end_date": info["feed_end_date"], "bytes": target.stat().st_size, "path": str(target)}
        with response, open(temporary, "wb") as output:
            while chunk := response.read(65536):
                output.write(chunk)
                if output.tell() > 30_000_000:
                    raise ValueError("feed exceeds 30 MB download limit")
        with zipfile.ZipFile(temporary) as archive:
            missing = REQUIRED_GTFS - set(archive.namelist())
            if missing:
                raise ValueError(f"missing GTFS files: {', '.join(sorted(missing))}")
            if next(rows(archive, "agency.txt"))["agency_name"] != AGENCIES[operator]:
                raise ValueError("unexpected GTFS agency")
            info = next(rows(archive, "feed_info.txt"))
            if not info.get("feed_start_date") or not info.get("feed_end_date"):
                raise ValueError("feed has no coverage dates")
        if target.exists():
            shutil.copy2(target, DATA_DIR / f"{operator}.previous.zip")
        os.replace(temporary, target)
        return {"operator": operator, "status": "updated", "feed_start_date": info["feed_start_date"], "feed_end_date": info["feed_end_date"], "bytes": target.stat().st_size, "path": str(target)}
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def active_services(archive: zipfile.ZipFile, service_date: date) -> set[str]:
    ymd = service_date.strftime("%Y%m%d")
    weekday = service_date.strftime("%A").lower()
    active = {r["service_id"] for r in rows(archive, "calendar.txt") if r["start_date"] <= ymd <= r["end_date"] and r[weekday] == "1"}
    for row in rows(archive, "calendar_dates.txt"):
        if row["date"] == ymd:
            if row["exception_type"] == "1":
                active.add(row["service_id"])
            elif row["exception_type"] == "2":
                active.discard(row["service_id"])
            else:
                raise ValueError(f"unknown GTFS exception type: {row['exception_type']}")
    return active


def query_gtfs(operator: str, stop_id: str, service_date: date, after: str, limit: int, route_filter: str | None, destination_filter: str | None) -> dict:
    path = DATA_DIR / f"{operator}.zip"
    if not path.exists():
        raise ValueError(f"{operator} feed missing; run refresh first")
    with zipfile.ZipFile(path) as archive:
        info = next(rows(archive, "feed_info.txt"))
        ymd = service_date.strftime("%Y%m%d")
        coverage = {"from": info["feed_start_date"], "through": info["feed_end_date"]}
        if not coverage["from"] <= ymd <= coverage["through"]:
            return {"operator": operator, "service_date": service_date.isoformat(), "status": "outside_feed_coverage", "coverage": coverage, "departures": []}
        stop = next((r for r in rows(archive, "stops.txt") if r["stop_id"] == stop_id), None)
        if stop is None:
            raise ValueError(f"unknown {operator} stop ID: {stop_id}")
        active = active_services(archive, service_date)
        routes = {r["route_id"]: r for r in rows(archive, "routes.txt")}
        trips = {r["trip_id"]: r for r in rows(archive, "trips.txt") if r["service_id"] in active and (not route_filter or route_filter in routes[r["route_id"]]["route_long_name"]) and (not destination_filter or destination_filter in r.get("trip_headsign", ""))}
        cutoff = parse_minutes(after)
        departures = []
        for row in rows(archive, "stop_times.txt"):
            if row["stop_id"] != stop_id or row["trip_id"] not in trips:
                continue
            if parse_minutes(row["departure_time"]) < cutoff:
                continue
            trip = trips[row["trip_id"]]
            route = routes[trip["route_id"]]
            departures.append({
                "stop_id": f"{operator}:{stop_id}",
                "boarding_position": stop.get("platform_code") or None,
                "route_id": f"{operator}:{trip['route_id']}",
                "route": route["route_short_name"] or route["route_long_name"],
                "destination": trip.get("trip_headsign") or None,
                "scheduled_time": row["departure_time"],
                "scheduled_at": local_timestamp(service_date, row["departure_time"]),
                "trip_id": f"{operator}:{trip['trip_id']}",
            })
        departures.sort(key=lambda r: (r["scheduled_at"], r["route"], r["trip_id"]))
        return {
            "operator": operator,
            "service_date": service_date.isoformat(),
            "status": "scheduled_gtfs",
            "stop": {"id": f"{operator}:{stop_id}", "name": stop["stop_name"], "lat": float(stop["stop_lat"]), "lon": float(stop["stop_lon"]), "boarding_position": stop.get("platform_code") or None},
            "coverage": coverage,
            "feed_version": info.get("feed_version"),
            "feed_fetched_at": datetime.fromtimestamp(path.stat().st_mtime, TOKYO).isoformat(),
            "source": FEEDS[operator],
            "departures": departures[:limit],
        }


def jr_category(service_date: date) -> tuple[int, str]:
    year = str(service_date.year)
    if year not in HOLIDAYS:
        raise ValueError("JR holiday calendar unavailable for this year; pass --jr-category explicitly")
    if service_date.isoformat() in HOLIDAYS[year] or service_date.weekday() == 6:
        return 4, "Sunday or national holiday"
    if service_date.weekday() == 5:
        nth = (service_date.day - 1) // 7 + 1
        return (2, "first/third/fifth Saturday") if nth in (1, 3, 5) else (3, "second/fourth Saturday")
    return 1, "weekday"


def query_jr(station_id: int, pattern: str, service_date: date, after: str, limit: int, category_override: int | None) -> dict:
    category, label = (category_override, "manually selected") if category_override else jr_category(service_date)
    pattern_info = next((r for r in jr_patterns(station_id, None)["patterns"] if r["pattern"] == pattern), None)
    if pattern_info is None:
        raise ValueError("JR pattern is not listed at this stop")
    data = post_json(JR_ENDPOINT, {"kind": 0, "pattern": pattern, "departure_station_id": station_id})
    table = data.get("station_linelist_timetable", {}).get("time_table", {})
    if table.get("pattern") != pattern or table.get("start", {}).get("station_id") != station_id:
        raise ValueError("JR route or stop identity changed")
    lines = table.get("line_list", [])
    if len(lines) != 1 or lines[0].get("line_name") != pattern_info["route"]:
        raise ValueError("JR pattern did not select exactly one route")
    if table.get("date_of_revision") != JR_REVIEWED_REVISION:
        return {
            "operator": "jr",
            "service_date": service_date.isoformat(),
            "status": "source_revision_changed_review_required",
            "warning": "Ekibus revision changed; review routes and compare departures with the operator before using this source.",
            "stop": {"id": f"jr:{station_id}", "name": table["start"].get("station_name"), "boarding_position": pattern_info["boarding_position"]},
            "route": lines[0].get("line_name"),
            "pattern": pattern,
            "source_revision": table.get("date_of_revision"),
            "reviewed_revision": JR_REVIEWED_REVISION,
            "source": JR_ENDPOINT,
            "departures": [],
        }
    day = next((r for r in lines[0].get("dia_list", []) if r["dia_flg"] == category), None)
    if day is None:
        raise ValueError(f"JR category {category} unavailable for this route")
    cutoff = parse_minutes(after)
    times = [r for r in day["time_table"] if parse_minutes(r["time"]) >= cutoff]
    return {
        "operator": "jr",
        "service_date": service_date.isoformat(),
        "status": "day_category_candidate_unverified_for_date",
        "warning": "cant promise correct times now",
        "stop": {"id": f"jr:{station_id}", "name": table["start"].get("station_name"), "boarding_position": pattern_info["boarding_position"]},
        "route": lines[0].get("line_name"),
        "direction": pattern_info["direction"],
        "pattern": pattern,
        "day_category": category,
        "day_category_label": label,
        "source_revision": table.get("date_of_revision"),
        "reviewed_revision": JR_REVIEWED_REVISION,
        "source": JR_ENDPOINT,
        "departures": [{"route": lines[0].get("line_name"), "destination": r.get("course_name"), "scheduled_time": r["time"], "scheduled_at": None, "course_id": f"jr:{r.get('course_id')}"} for r in times[:limit]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    refresh_parser = sub.add_parser("refresh", help="download and validate GTFS ZIPs")
    refresh_parser.add_argument("operator", choices=(*FEEDS, "all"))
    find_parser = sub.add_parser("find-stops", help="find source-specific stop IDs by name")
    find_parser.add_argument("operator", choices=(*FEEDS, "jr"))
    find_parser.add_argument("--name", required=True)
    find_parser.add_argument("--limit", type=int, default=20)
    patterns_parser = sub.add_parser("jr-patterns", help="list JR patterns at one station ID")
    patterns_parser.add_argument("--stop", type=int, required=True)
    patterns_parser.add_argument("--limit", type=int, default=30)
    query_parser = sub.add_parser("query", help="query one exact boarding stop and service date")
    query_parser.add_argument("operator", choices=(*FEEDS, "jr"))
    query_parser.add_argument("--stop", required=True, help="source stop ID; JR uses a numeric station ID")
    query_parser.add_argument("--date", required=True, type=date.fromisoformat)
    query_parser.add_argument("--after", default="00:00")
    query_parser.add_argument("--limit", type=int, default=10)
    query_parser.add_argument("--route", help="GTFS route-name substring")
    query_parser.add_argument("--destination", help="GTFS trip headsign substring")
    query_parser.add_argument("--pattern", help="required JR line_id:course_id-pos")
    query_parser.add_argument("--jr-category", type=int, choices=range(1, 5), help="override inferred JR day category")
    args = parser.parse_args()
    try:
        if args.command == "refresh":
            result = [refresh(name) for name in (FEEDS if args.operator == "all" else (args.operator,))]
        elif args.command == "find-stops":
            if args.limit < 1 or args.limit > 100:
                raise ValueError("limit must be 1–100")
            result = find_stops(args.operator, args.name, args.limit)
        elif args.command == "jr-patterns":
            if args.limit < 1 or args.limit > 100:
                raise ValueError("limit must be 1–100")
            result = jr_patterns(args.stop, args.limit)
        else:
            if args.limit < 1 or args.limit > 100:
                raise ValueError("limit must be 1–100")
            parse_minutes(args.after)
            if args.operator == "jr":
                if not args.pattern:
                    raise ValueError("JR query requires --pattern")
                if args.route or args.destination:
                    raise ValueError("--route and --destination apply only to GTFS queries")
                result = query_jr(int(args.stop), args.pattern, args.date, args.after, args.limit, args.jr_category)
            else:
                if args.pattern or args.jr_category:
                    raise ValueError("JR options apply only to JR queries")
                result = query_gtfs(args.operator, args.stop, args.date, args.after, args.limit, args.route, args.destination)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, StopIteration) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
