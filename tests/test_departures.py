"""Check date and boarding semantics using a tiny synthetic GTFS feed."""

import importlib.util
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "departures.py"
spec = importlib.util.spec_from_file_location("departures", SCRIPT)
departures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(departures)


FILES = {
    "agency.txt": "agency_name,agency_timezone\n北海道中央バス,Asia/Tokyo\n",
    "feed_info.txt": "feed_start_date,feed_end_date,feed_version\n20261101,20261130,test\n",
    "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nregular,1,1,1,1,1,0,0,20261101,20261130\nholiday,0,0,0,0,0,0,0,20261101,20261130\n",
    "calendar_dates.txt": "service_id,date,exception_type\nregular,20261103,2\nholiday,20261103,1\n",
    "routes.txt": "route_id,route_short_name,route_long_name\nr1,,麻０５屯田線\n",
    "stops.txt": "stop_id,stop_name,stop_lat,stop_lon,platform_code\ns1,地下鉄麻生駅,43.1,141.3,4\n",
    "trips.txt": "route_id,service_id,trip_id,trip_headsign\nr1,regular,t1,屯田６条１２丁目\nr1,holiday,t2,屯田６条１２丁目\nr1,regular,t3,地下鉄麻生駅\n",
    "stop_times.txt": "trip_id,stop_id,stop_sequence,departure_time\nt1,s1,1,25:15:00\nt2,s1,1,10:30:00\nt3,s1,1,08:00:00\n",
}


class DepartureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        target = Path(self.directory.name) / "chuo.zip"
        with zipfile.ZipFile(target, "w") as archive:
            for name, content in FILES.items():
                archive.writestr(name, content)
        self.patch = patch.object(departures, "DATA_DIR", Path(self.directory.name))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    def test_exception_replaces_regular_service(self):
        result = departures.query_gtfs("chuo", "s1", date(2026, 11, 3), "00:00", 10, "麻０５", "屯田")
        self.assertEqual(result["status"], "scheduled_gtfs")
        self.assertEqual([r["scheduled_time"] for r in result["departures"]], ["10:30:00"])
        self.assertEqual(result["stop"]["boarding_position"], "4")

    def test_overnight_and_direction(self):
        result = departures.query_gtfs("chuo", "s1", date(2026, 11, 4), "24:00", 10, None, "屯田")
        self.assertEqual(len(result["departures"]), 1)
        self.assertEqual(result["departures"][0]["scheduled_at"], "2026-11-05T01:15:00+09:00")

    def test_coverage_and_jr_day_category(self):
        result = departures.query_gtfs("chuo", "s1", date(2026, 12, 1), "00:00", 10, None, None)
        self.assertEqual(result["status"], "outside_feed_coverage")
        self.assertEqual(departures.jr_category(date(2026, 11, 3))[0], 4)
        self.assertEqual(departures.jr_category(date(2026, 11, 7))[0], 2)
        self.assertEqual(departures.jr_category(date(2026, 11, 14))[0], 3)


if __name__ == "__main__":
    unittest.main()
