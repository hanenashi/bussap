"""Check the JR fallback against stop identity and bounded source pages."""

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import buskita  # noqa: E402
import server  # noqa: E402


MARKERS = [{"operator": "jr", "station_id": 340598, "name": "琴似１条３丁目",
            "boarding_position": "1", "lat": 43.0777, "lon": 141.305035}]
STOPS = [{"id": 1611, "company_no": "jhb", "name": "琴似１条３丁目", "platformNo": "1",
          "position": {"latitude": "43.0777", "longitude": "141.305035"}},
         {"id": 9, "company_no": "jhb", "name": "琴似営業所前", "platformNo": "1",
          "position": {"latitude": "43.1", "longitude": "141.3"}}]


class BuskitaTests(unittest.TestCase):
    def test_exact_stop_and_position_required(self):
        self.assertEqual(buskita.matching_positions(340598, MARKERS, STOPS),
                         [{"busstop": "1611", "platform": "1", "name": "琴似１条３丁目"}])
        moved = [{**STOPS[0], "position": {"latitude": "43.2", "longitude": "141.3"}}]
        self.assertEqual(buskita.matching_positions(340598, MARKERS, moved), [])

    def test_morning_query_pages_and_preserves_destination(self):
        calls = []
        def fake_post(path, payload):
            calls.append(payload["targetTime"])
            if len(calls) == 1:
                times = [f"07:{i:02}" for i in range(10)]
            else:
                times = ["07:10", "07:11"]
            return {"result": [{"startDateTime": at, "departureBusstop": "1611", "departureCompany": "jhb", "arrivalBusstop": 9,
                                "routes": [{"name": "琴似八軒線[琴４０]"}]} for at in times]}
        with patch.object(buskita, "post", side_effect=fake_post):
            result = buskita.departures_at(340598, "buskita:1611:1", date(2026, 11, 13),
                                           "00:00", 50, MARKERS, STOPS)
        self.assertEqual(calls, ["2026/11/13 04:00", "2026/11/13 07:10"])
        self.assertEqual(len(result["departures"]), 12)
        self.assertEqual(result["departures"][0]["destination"], "琴似営業所前")
        self.assertEqual(result["status"], "buskita_next_departures")

    def test_source_failure_uses_buskita_pattern(self):
        with patch.object(server.departures, "jr_patterns", side_effect=OSError("offline")), \
             patch.object(server.map_data, "catalog", return_value=(MARKERS, [], None)), \
             patch.object(server.buskita, "catalog", return_value=STOPS):
            result = server.dispatch("/api/jr-patterns", {"stop": ["340598"], "limit": ["50"]})
        self.assertEqual(result["source"], "buskita")
        self.assertEqual(result["patterns"][0]["pattern"], "buskita:1611:1")


if __name__ == "__main__":
    unittest.main()
