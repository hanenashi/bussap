#!/usr/bin/env python3
"""Bounded stop coordinates for BUSSAP's street map."""

import argparse
import json
import math
import os
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from functools import lru_cache

import departures


JR_MARKERS_URL = departures.JR_BASE + "/Get_marker_data"
JR_MARKERS_PATH = departures.DATA_DIR / "jr-markers.json"


def refresh_jr_markers():
    request = urllib.request.Request(JR_MARKERS_URL, data=b"", method="POST", headers={"User-Agent": "BUSSAP personal stop map/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(8_000_001)
    if len(body) > 8_000_000:
        raise ValueError("JR marker response exceeds 8 MB")
    data = json.loads(body)
    if data.get("result") != "0" or not isinstance(data.get("marker_detail_data"), list):
        raise ValueError("JR marker source changed shape")
    jr_rows = [row for row in data["marker_detail_data"] if row.get("company_id") == 34]
    numbered_stations = {int(row["station_id"]) for row in jr_rows if str(row.get("no", "0")) != "0"}
    stops = {}
    for row in jr_rows:
        if row.get("company_id") != 34:
            continue
        try:
            station_id = int(row["station_id"])
            lat, lon = float(row["lat"]), float(row["lng"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("JR marker has invalid ID or coordinate") from exc
        if not 41 <= lat <= 46 or not 139 <= lon <= 146 or not math.isfinite(lat + lon):
            raise ValueError("JR marker is outside Hokkaido")
        name = row.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("JR marker has no name")
        number = str(row.get("no") or "0")
        if number == "0" and station_id in numbered_stations:
            continue
        stop = {"id": f"jr:{station_id}:{number}", "station_id": station_id, "operator": "jr", "name": name,
                "lat": lat, "lon": lon, "boarding_position": number if number != "0" else None,
                "coordinate_kind": "boarding" if number != "0" else "station"}
        previous = stops.get(stop["id"])
        if previous and previous != stop:
            raise ValueError("JR marker ID has conflicting coordinates")
        stops[stop["id"]] = stop
    if len(stops) < 500:
        raise ValueError("JR marker source has too few stops")
    snapshot = {"source": JR_MARKERS_URL, "fetched_at": datetime.now(departures.TOKYO).isoformat(),
                "stops": sorted(stops.values(), key=lambda stop: stop["id"])}
    departures.DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="jr-markers-", suffix=".json", dir=departures.DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(snapshot, output, ensure_ascii=False, separators=(",", ":"))
        if JR_MARKERS_PATH.exists():
            shutil.copy2(JR_MARKERS_PATH, departures.DATA_DIR / "jr-markers.previous.json")
        os.replace(temporary, JR_MARKERS_PATH)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"status": "updated", "count": len(stops), "fetched_at": snapshot["fetched_at"]}


def catalog():
    versions = tuple((operator, (departures.DATA_DIR / f"{operator}.zip").stat().st_mtime_ns)
                     for operator in departures.FEEDS if (departures.DATA_DIR / f"{operator}.zip").exists())
    marker_version = JR_MARKERS_PATH.stat().st_mtime_ns if JR_MARKERS_PATH.exists() else None
    return _read_catalog(versions, marker_version)


@lru_cache(maxsize=4)
def _read_catalog(versions, marker_version):
    stops = []
    for operator, _mtime in versions:
        with zipfile.ZipFile(departures.DATA_DIR / f"{operator}.zip") as archive:
            for row in departures.rows(archive, "stops.txt"):
                try:
                    lat, lon = float(row["stop_lat"]), float(row["stop_lon"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not 41 <= lat <= 46 or not 139 <= lon <= 146 or not math.isfinite(lat + lon):
                    continue
                stops.append({"id": f"{operator}:{row['stop_id']}", "operator": operator, "name": row["stop_name"],
                              "lat": lat, "lon": lon, "boarding_position": row.get("platform_code") or None,
                              "coordinate_kind": "boarding"})
    warnings = []
    fetched_at = None
    if marker_version is None:
        warnings.append("JR stop map is unavailable until its marker snapshot is refreshed")
    else:
        snapshot = json.loads(JR_MARKERS_PATH.read_text(encoding="utf-8"))
        if not isinstance(snapshot.get("stops"), list):
            raise ValueError("JR marker snapshot is invalid")
        stops.extend(snapshot["stops"])
        fetched_at = snapshot.get("fetched_at")
    return stops, warnings, fetched_at


def features_in_bbox(stops, bbox, zoom, operator="all"):
    south, west, north, east = bbox
    visible = [stop for stop in stops if (operator == "all" or stop["operator"] == operator)
               and south <= stop["lat"] <= north and west <= stop["lon"] <= east]
    cell = 0.008 * 2 ** (13 - zoom)
    while True:
        groups = {}
        for stop in visible:
            key = (math.floor(stop["lat"] / cell), math.floor(stop["lon"] / (cell / 0.73)))
            groups.setdefault(key, []).append(stop)
        if len(groups) <= 350:
            break
        cell *= 1.5
    features = []
    for group in groups.values():
        if len(group) == 1:
            features.append({"type": "stop", **group[0]})
        else:
            features.append({"type": "cluster", "count": len(group),
                             "lat": sum(stop["lat"] for stop in group) / len(group),
                             "lon": sum(stop["lon"] for stop in group) / len(group),
                             "members": group if len(group) <= 20 else [],
                             "operators": sorted({stop["operator"] for stop in group})})
    return {"total_stops": len(visible), "features": features}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("refresh-jr",))
    args = parser.parse_args()
    if args.command == "refresh-jr":
        print(json.dumps(refresh_jr_markers(), ensure_ascii=False))


if __name__ == "__main__":
    main()
