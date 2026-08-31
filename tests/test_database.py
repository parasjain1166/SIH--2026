"""SQLite persistence tests that do not require Flask."""

import os
import tempfile
import unittest

from core.ai_prioritizer import AIPrioritizer
from core.database import RailBlockDatabase
from core.kaggle_importer import KaggleDataImporter


class TestSQLiteDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = RailBlockDatabase(os.path.join(self.tmp.name, "railblock_test.db"))
        importer = KaggleDataImporter()
        stations = importer.load_real_stations()
        sections = importer.build_track_sections_from_stations(stations)
        tasks = importer.load_real_maintenance_tasks()
        trains = importer.load_real_trains(sections)
        self.db.replace_dataset(stations, sections, tasks, trains, "KAGGLE_REAL")

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_counts(self):
        counts = self.db.get_counts()
        self.assertEqual(counts["stations"], 20)
        self.assertEqual(counts["sections"], 38)
        self.assertEqual(counts["trains"], 26)
        self.assertEqual(counts["maintenance_tasks"], 17)
        self.assertGreater(counts["occupancies"], 0)

    def test_domain_round_trip_and_priority(self):
        sections = self.db.load_sections()
        tasks = self.db.load_tasks()
        trains = self.db.load_trains()
        AIPrioritizer().prioritize_all_tasks(tasks, sections)
        self.assertAlmostEqual(max(t.computed_ai_priority for t in tasks), 89.14, places=2)
        self.assertTrue(any(t.section_occupancies for t in trains))

    def test_computed_state_persists(self):
        sections = self.db.load_sections()
        tasks = self.db.load_tasks()
        AIPrioritizer().prioritize_all_tasks(tasks, sections)
        self.db.update_task_computed_state(tasks)
        reloaded = self.db.load_tasks()
        self.assertAlmostEqual(max(t.computed_ai_priority for t in reloaded), 89.14, places=2)
        self.assertEqual(min(t.risk_rank for t in reloaded), 1)


if __name__ == "__main__":
    unittest.main()
