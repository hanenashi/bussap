#!/usr/bin/env python3
"""Compare three JR local timetable samples with the 2026-04 audit fixture.

This is a bounded source-health probe, not an arbitrary-date schedule adapter.
It makes three POST requests and prints only compact results.
"""

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "jr_local_samples.json"
ENDPOINT = "https://ekibus-api.city.sapporo.jp/Get_station_linelist_timetable"


def fetch(pattern: str, station_id: int) -> dict:
    body = urlencode({
        "kind": 0,
        "pattern": pattern,
        "departure_station_id": station_id,
    }).encode("ascii")
    request = Request(ENDPOINT, data=body, method="POST")
    with urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        return json.load(response)


def check(data: dict, sample: dict, expected_revision: int) -> list[str]:
    problems = []
    if data.get("result") != "0":
        return [f"source result {data.get('result')!r}"]
    table = data.get("station_linelist_timetable", {}).get("time_table", {})
    if table.get("pattern") != sample["pattern"]:
        problems.append("pattern changed")
    if table.get("start", {}).get("station_id") != sample["station_id"]:
        problems.append("stop ID changed")
    if table.get("date_of_revision") != expected_revision:
        problems.append(f"revision changed to {table.get('date_of_revision')!r}")
    lines = table.get("line_list", [])
    if len(lines) != 1 or lines[0].get("line_name") != sample["route"]:
        return problems + ["route identity changed"]
    by_day = {str(day.get("dia_flg")): day for day in lines[0].get("dia_list", [])}
    for category, expected in sample["first_three"].items():
        observed = [row.get("time") for row in by_day.get(category, {}).get("time_table", [])[:3]]
        if observed != expected:
            problems.append(f"category {category}: expected {expected}, got {observed}")
    return problems


def main() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    failures = 0
    for index, sample in enumerate(fixture["samples"]):
        if index:
            time.sleep(0.5)
        try:
            issues = check(fetch(sample["pattern"], sample["station_id"]), sample, fixture["revision"])
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues = [f"request failed: {type(exc).__name__}: {exc}"]
        if issues:
            failures += 1
            print(f"FAIL {sample['stop']} / {sample['route']}: {'; '.join(issues)}")
        else:
            print(f"PASS {sample['stop']} / {sample['route']}: revision and four day categories match")
    print(f"{len(fixture['samples']) - failures}/{len(fixture['samples'])} JR local samples passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
