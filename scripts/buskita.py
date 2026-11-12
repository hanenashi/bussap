"""Bounded JR Buskita fallback for when Sapporo Ekibus is unreachable.

Buskita is linked by JR Hokkaido Bus. Its web API is undocumented, so every
response is checked before a matching stop or departure is shown.
"""

import json
import math
import unicodedata
import urllib.request
from datetime import date, datetime

import departures


BASE = "https://api.buskita.com"
SOURCE = "https://jhb.buskita.com/"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/plain, */*",
           "Referer": SOURCE, "User-Agent": "Mozilla/5.0 BUSSAP personal timetable"}


def post(path: str, values: dict) -> dict:
    request = urllib.request.Request(BASE + path, data=json.dumps(values).encode(), headers=HEADERS, method="POST")
    with urllib.request.urlopen(request, timeout=12) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise OSError("Buskita response too large")
    try:
        result = json.loads(body)
    except ValueError as exc:
        raise OSError("Buskita response is not JSON") from exc
    if not isinstance(result, dict):
        raise OSError("Buskita response changed shape")
    return result


def catalog() -> list[dict]:
    revision = post("/get-busstops-version", {"siteId": 1, "language": 1}).get("busstopsDictionaryVersion")
    if not isinstance(revision, int) or revision < 1:
        raise OSError("Buskita stop revision is unavailable")
    data = post("/get-busstops", {"siteId": 1, "language": 1, "version": revision})
    stops = data.get("busstops")
    if not isinstance(stops, list) or len(stops) < 1000:
        raise OSError("Buskita stop list is incomplete")
    return [stop for stop in stops if isinstance(stop, dict) and stop.get("company_no") == "jhb"]


def norm(name: str) -> str:
    return unicodedata.normalize("NFKC", name).strip()


def matching_positions(station_id: int, markers: list[dict], stops: list[dict]) -> list[dict]:
    positions = []
    for marker in markers:
        if marker.get("operator") != "jr" or marker.get("station_id") != station_id:
            continue
        candidates = []
        for stop in stops:
            if norm(stop.get("name", "")) != norm(marker["name"]):
                continue
            if str(stop.get("platformNo") or "") != str(marker.get("boarding_position") or ""):
                continue
            try:
                lat = float(stop["position"]["latitude"])
                lon = float(stop["position"]["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            distance = math.hypot((lat - marker["lat"]) * 111_000, (lon - marker["lon"]) * 81_000)
            if distance <= 100:
                candidates.append((distance, stop))
        if not candidates:
            continue
        candidates.sort(key=lambda item: item[0])
        if len(candidates) > 1 and candidates[1][0] - candidates[0][0] < 10:
            continue
        match = candidates[0][1]
        position = str(match["platformNo"])
        if not any(p["platform"] == position for p in positions):
            positions.append({"busstop": str(match["id"]), "platform": position, "name": marker["name"]})
    return positions


def pattern_id(position: dict) -> str:
    return f"buskita:{position['busstop']}:{position['platform']}"


def patterns(station_id: int, markers: list[dict], stops: list[dict], limit: int) -> dict:
    positions = matching_positions(station_id, markers, stops)
    if not positions:
        raise OSError("no verified Buskita stop match")
    result = [{"pattern": pattern_id(p), "route": "この乗り場の次のバス",
               "direction": "バスキタ掲載便", "boarding_position": p["platform"]} for p in positions]
    return {"operator": "jr", "station_id": station_id, "total_patterns": len(result),
            "patterns": result[:limit], "source": "buskita"}


def departures_at(station_id: int, pattern: str, service_date: date, after: str, limit: int,
                  markers: list[dict], stops: list[dict]) -> dict:
    position = next((p for p in matching_positions(station_id, markers, stops) if pattern_id(p) == pattern), None)
    if position is None:
        raise ValueError("Buskita pattern is not listed at this stop")
    minutes = departures.parse_minutes(after)
    rides = []
    target = max(minutes, 4 * 60)
    page_limit = min(6, (limit + 9) // 10)
    pagination_caveat = ""
    for _ in range(page_limit):
        if target >= 24 * 60:
            break
        stamp = f"{service_date:%Y/%m/%d} {target // 60:02}:{target % 60:02}"
        data = post("/search-routes-from-busstop", {"language": 1, "siteId": 1,
                    "busstop": position["busstop"], "company": "jhb",
                    "platformNo": position["platform"], "targetTime": stamp})
        page = data.get("result")
        if not isinstance(page, list) or len(page) > 10:
            raise OSError("Buskita departure list changed shape")
        if not page:
            break
        try:
            times = [departures.parse_minutes(ride.get("startDateTime", "")) for ride in page]
        except (AttributeError, ValueError) as exc:
            raise OSError("Buskita departure time changed shape") from exc
        if times != sorted(times) or times[0] < target:
            raise OSError("Buskita departure order changed")
        rides.extend(page)
        if len(page) < 10:
            break
        if times.count(times[-1]) > 1:
            pagination_caveat = "同じ分の便が続くため、以降は表示していません。"
            break
        target = times[-1] + 1
    names = {str(stop["id"]): stop["name"] for stop in stops}
    result = []
    for ride in rides:
        if str(ride.get("departureBusstop")) != position["busstop"] or ride.get("departureCompany") != "jhb":
            raise OSError("Buskita departure stop changed")
        route = ride.get("routes")
        scheduled = ride.get("startDateTime")
        if not isinstance(route, list) or len(route) != 1 or not isinstance(scheduled, str):
            raise OSError("Buskita route changed shape")
        if departures.parse_minutes(scheduled) < minutes:
            continue
        line = route[0]
        if not isinstance(line, dict):
            raise OSError("Buskita route changed shape")
        if not isinstance(line.get("name"), str) or not line["name"]:
            raise OSError("Buskita route has no name")
        destination = names.get(str(ride.get("arrivalBusstop")))
        if not destination:
            raise OSError("Buskita destination is unknown")
        result.append({"route": line["name"], "destination": destination,
                       "scheduled_time": scheduled, "scheduled_at": None})
    if len(result) > limit:
        result = result[:limit]
    return {"operator": "jr", "service_date": service_date.isoformat(),
            "status": "buskita_next_departures", "warning": f"バスキタ掲載時刻です。最大{limit}便を表示。選択日の運行は公式情報でご確認ください。{pagination_caveat}",
            "stop": {"id": f"jr:{station_id}", "name": position["name"],
                     "boarding_position": position["platform"]},
            "route": "この乗り場の次のバス", "pattern": pattern,
            "source_fetched_at": datetime.now(departures.TOKYO).isoformat(),
            "source": SOURCE, "source_link": f"{SOURCE}#/busstop/{position['busstop']}/jhb/{position['platform']}",
            "departures": result}
