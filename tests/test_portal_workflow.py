"""Engineer/officer workflow persistence tests; Flask is not required."""

import os
import tempfile
import unittest

from core.database import RailBlockDatabase
from core.kaggle_importer import KaggleDataImporter


class TestPortalWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = RailBlockDatabase(os.path.join(self.tmp.name, "portal.db"))
        importer = KaggleDataImporter()
        stations = importer.load_real_stations()
        sections = importer.build_track_sections_from_stations(stations)
        tasks = importer.load_real_maintenance_tasks()
        trains = importer.load_real_trains(sections)
        self.db.replace_dataset(stations, sections, tasks, trains, "KAGGLE_REAL")

    def tearDown(self):
        self.tmp.cleanup()

    def _request(self, department="TMS"):
        return self.db.create_maintenance_request({
            "engineer_name": "Prototype Engineer",
            "department": department,
            "station_code": "GZB",
            "section_id": "SEC_GZB_MIU_UP",
            "track_line": "UP",
            "start_km": 26.0,
            "end_km": 26.4,
            "task_name": "Prototype field defect",
            "task_category": "RAIL_FLAW",
            "required_duration_mins": 120,
            "min_duration_mins": 60,
            "safety_criticality": 9.0,
            "asset_degradation_score": 8.0,
            "urgency_days_overdue": 3,
            "gmt_accumulated": 60.0,
            "requires_traffic_block": True,
            "requires_power_block": department == "TDMS",
            "requires_st_disconnection": department == "SMMS",
            "required_machines": [],
            "required_gangs": [],
            "horizon": "DAILY",
            "ai_priority": 82.0,
            "ai_classification": "HIGH_PRIORITY",
            "ai_components": {"safety_score": 90.0},
        })

    def test_submission_and_review_state(self):
        req = self._request()
        self.assertEqual(req["request_status"], "SUBMITTED")
        self.db.update_request_analysis(req["request_id"], 86.5, "CRITICAL_EMERGENCY", {"safety_score": 95})
        reviewed = self.db.get_maintenance_request(req["request_id"])
        self.assertEqual(reviewed["request_status"], "UNDER_REVIEW")
        self.assertEqual(reviewed["ai_priority"], 86.5)

    def test_rejection_never_creates_operational_task(self):
        before = self.db.get_counts()["maintenance_tasks"]
        req = self._request("TDMS")
        rejected = self.db.decide_maintenance_request(req["request_id"], "REJECTED", "Officer", "Not feasible", "Do not proceed")
        after = self.db.get_counts()["maintenance_tasks"]
        self.assertEqual(rejected["request_status"], "REJECTED")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
