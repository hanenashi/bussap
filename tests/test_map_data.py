"""Map grouping must preserve exact boarding identities."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import map_data


class MapDataTests(unittest.TestCase):
    def test_bbox_filter_and_cluster_members_keep_boarding_ids(self):
        stops = [
            {"id": "jr:340001:11", "operator": "jr", "name": "札幌駅前", "lat": 43.06558, "lon": 141.35038, "boarding_position": "11"},
            {"id": "jr:340001:12", "operator": "jr", "name": "札幌駅前", "lat": 43.06560, "lon": 141.35040, "boarding_position": "12"},
            {"id": "chuo:s1", "operator": "chuo", "name": "札幌駅前", "lat": 43.06559, "lon": 141.35039, "boarding_position": "1"},
            {"id": "jotetsu:s2", "operator": "jotetsu", "name": "遠い停留所", "lat": 43.2, "lon": 141.7, "boarding_position": None},
        ]
        result = map_data.features_in_bbox(stops, (43.06, 141.34, 43.07, 141.36), 15)
        self.assertEqual(result["total_stops"], 3)
        self.assertEqual(len(result["features"]), 1)
        cluster = result["features"][0]
        self.assertEqual(cluster["type"], "cluster")
        self.assertEqual({stop["id"] for stop in cluster["members"]}, {"jr:340001:11", "jr:340001:12", "chuo:s1"})
        jr = map_data.features_in_bbox(stops, (43.06, 141.34, 43.07, 141.36), 15, "jr")
        self.assertEqual(jr["total_stops"], 2)
        self.assertEqual({stop["boarding_position"] for stop in jr["features"][0]["members"]}, {"11", "12"})


if __name__ == "__main__":
    unittest.main()
