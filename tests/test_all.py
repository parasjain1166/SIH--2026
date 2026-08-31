"""
RailBlock AI - Comprehensive Test Suite
Tests:
1. Model initialization and serialization
2. Synthetic Railway data generation
3. AI Multi-Criteria Prioritizer & Risk Scoring
4. Multi-Department Shadow Block Clustering
5. Constraint Optimization & Multi-Horizon Scheduling
6. What-If Disruption Simulator & KPI Engine
7. REST API Endpoints
"""

import unittest
import json
from datetime import datetime

from core.models import (
    Department, BlockType, PriorityHorizon, TrainType,
    TrackSection, MaintenanceTask, TrainSchedule, ScheduledBlock
)
from core.data_generator import (
    STATIONS, generate_track_sections, generate_maintenance_tasks,
    generate_train_timetable, compute_corridor_availability_windows
)
from core.ai_prioritizer import AIPrioritizer
from core.shadow_block_detector import ShadowBlockDetector
from core.optimizer import BlockOptimizer
from core.multi_horizon_planner import MultiHorizonPlanner
from core.kpi_engine import KPIEngine
from core.whatif_simulator import WhatIfSimulator
from core.report_generator import ReportGenerator
from web.app import app


class TestRailBlockAI(unittest.TestCase):
    def setUp(self):
        self.sections = generate_track_sections()
        self.tasks = generate_maintenance_tasks(self.sections, seed=42)
        self.trains = generate_train_timetable(self.sections)
        self.windows = compute_corridor_availability_windows(self.sections, self.trains)
        self.prioritizer = AIPrioritizer()
        self.detector = ShadowBlockDetector()
        self.optimizer = BlockOptimizer()
        self.planner = MultiHorizonPlanner(self.detector, self.optimizer)
        self.simulator = WhatIfSimulator(
            self.sections, self.tasks, self.trains, self.prioritizer, self.detector, self.optimizer
        )

    def test_data_generation_integrity(self):
        """Verify that corridor, stations, and departments are properly generated."""
        self.assertEqual(len(STATIONS), 14)
        self.assertGreater(len(self.sections), 20)
        self.assertGreater(len(self.tasks), 30)
        self.assertGreater(len(self.trains), 20)
        self.assertGreater(len(self.windows), 10)

        # Check departments present
        depts = {t.department for t in self.tasks}
        self.assertIn(Department.TMS, depts)
        self.assertIn(Department.SMMS, depts)
        self.assertIn(Department.TDMS, depts)

    def test_ai_prioritization(self):
        """Verify that critical defects receive higher composite priority than routine tasks."""
        prioritized = self.prioritizer.prioritize_all_tasks(self.tasks, self.sections)
        self.assertEqual(len(prioritized), len(self.tasks))
        
        # Check that top ranked task has high safety/degradation score
        top_task = prioritized[0]
        self.assertGreaterEqual(top_task.computed_ai_priority, 80.0)
        self.assertEqual(top_task.risk_rank, 1)

        # Verify ranking order is monotonically decreasing
        for i in range(len(prioritized) - 1):
            self.assertGreaterEqual(prioritized[i].computed_ai_priority, prioritized[i+1].computed_ai_priority)

    def test_shadow_block_detection(self):
        """Verify that co-located tasks across Track + S&T + TRD are bundled into shadow blocks."""
        clusters = self.detector.detect_clusters(self.tasks)
        self.assertGreater(len(clusters), 0)

        multi_dept_clusters = [c for c in clusters if c.is_multi_department]
        self.assertGreater(len(multi_dept_clusters), 0, "Should detect at least 1 multi-department shadow block cluster")

        # Verify hours saved is positive
        for c in multi_dept_clusters:
            self.assertGreater(c.hours_saved, 0.0)
            self.assertGreater(c.efficiency_gain_pct, 0.0)

    def test_schedule_optimization_and_multi_horizon(self):
        """Verify optimization generates valid non-conflicting blocks for Daily, Weekly, Monthly plans."""
        self.prioritizer.prioritize_all_tasks(self.tasks, self.sections)
        plans = self.planner.generate_all_horizons(self.tasks, self.sections, self.trains, self.windows)

        self.assertIn("daily_plan", plans)
        self.assertIn("weekly_plan", plans)
        self.assertIn("monthly_plan", plans)
        self.assertIn("tsr_roadmap", plans)

        daily_blocks = plans["daily_plan"]["blocks"]
        self.assertGreater(len(daily_blocks), 0)

        # Check block duration and time sanity
        for b in daily_blocks:
            self.assertGreater(b["duration_mins"], 0)
            self.assertLess(b["start_time_mins"], b["end_time_mins"])

    def test_kpi_engine_and_benchmarks(self):
        """Verify KPI computations and comparative analytics."""
        self.prioritizer.prioritize_all_tasks(self.tasks, self.sections)
        clusters = self.detector.detect_clusters(self.tasks)
        blocks = self.optimizer.optimize_schedule(clusters, self.windows, self.trains, self.sections)
        
        kpis = KPIEngine.compute_kpis(self.tasks, blocks)
        self.assertIn("summary", kpis)
        self.assertIn("comparison", kpis)

        summary = kpis["summary"]
        self.assertGreaterEqual(summary["asset_availability_pct"], 80.0)
        self.assertGreaterEqual(summary["safety_mitigation_pct"], 70.0)

    def test_whatif_simulator(self):
        """Verify What-If scenario injection and instant re-optimization."""
        # 1. Emergency Defect Injection
        res_defect = self.simulator.run_scenario("INJECT_EMERGENCY_DEFECT", {
            "department": "TMS", "section_id": "SEC_GZB_MIU_UP", "km": 28.0
        })
        self.assertIn("EMERGENCY", res_defect["description"])
        self.assertGreater(res_defect["scheduled_blocks_count"], 0)

        # 2. Train Delay Cascade
        res_delay = self.simulator.run_scenario("TRAIN_DELAY_CASCADE", {
            "train_no": "22436", "delay_mins": 45
        })
        self.assertIn("delayed", res_delay["description"])

    def test_report_generator_memos(self):
        """Verify that Form S&T T/351, Power Block, and COA block advice memos are generated."""
        dummy_task = self.tasks[0]
        dummy_block = ScheduledBlock(
            block_id="BLK_TEST_001",
            horizon=PriorityHorizon.DAILY,
            date_str="2026-08-30",
            section_id="SEC_GZB_MIU_UP",
            track_line="UP",
            start_km=26.0,
            end_km=30.0,
            start_time_str="01:30",
            end_time_str="04:30",
            start_time_mins=90,
            end_time_mins=270,
            duration_mins=180,
            block_type=BlockType.INTEGRATED_BLOCK,
            departments_involved=[Department.TMS, Department.SMMS, Department.TDMS],
            tasks=[dummy_task],
            is_shadow_block=True,
            assigned_resources=["CSM_TAMPING_01", "TOWER_WAGON_TRD_01"],
            block_permit_no="IR/BDMS/20260830/TEST",
            st_disconnection_memo_t351="SNT/T351/GZB/TEST",
            trd_power_permit_no="TRD/PB/GZB/TEST",
            coa_control_grant_id="COA-SANCTION-TEST"
        )

        t351 = ReportGenerator.generate_t351_memo(dummy_block, dummy_task)
        self.assertIn("FORM S&T T/351", t351)
        self.assertIn("SNT/T351/GZB/TEST", t351)

        pb = ReportGenerator.generate_power_block_memo(dummy_block, dummy_task)
        self.assertIn("POWER BLOCK PERMIT", pb)

        coa = ReportGenerator.generate_coa_block_grant(dummy_block)
        self.assertIn("OFFICIAL TRAFFIC BLOCK ADVICE", coa)

    def test_flask_api_endpoints(self):
        """Verify REST API responses with test client."""
        client = app.test_client()
        
        # Test Corridor
        r_corridor = client.get("/api/corridor")
        self.assertEqual(r_corridor.status_code, 200)
        self.assertIn("stations", r_corridor.get_json())

        # Test Tasks
        r_tasks = client.get("/api/tasks")
        self.assertEqual(r_tasks.status_code, 200)
        self.assertGreater(r_tasks.get_json()["total_count"], 0)

        # Test Schedules
        r_sched = client.get("/api/schedules?horizon=ALL")
        self.assertEqual(r_sched.status_code, 200)
        self.assertIn("daily_plan", r_sched.get_json())

        # Test KPIs
        r_kpi = client.get("/api/kpis")
        self.assertEqual(r_kpi.status_code, 200)
        self.assertIn("summary", r_kpi.get_json())

    def test_kaggle_importer_and_switch(self):
        """Verify Kaggle dataset parsing, summary, and data source switching."""
        from core.kaggle_importer import KaggleDataImporter
        importer = KaggleDataImporter()
        
        # Test station loading
        stations = importer.load_real_stations()
        self.assertGreaterEqual(len(stations), 10)
        
        # Test sections
        sections = importer.build_track_sections_from_stations(stations)
        self.assertGreaterEqual(len(sections), 18)
        
        # Test tasks and trains
        tasks = importer.load_real_maintenance_tasks()
        trains = importer.load_real_trains(sections)
        self.assertGreater(len(tasks), 0)
        self.assertGreater(len(trains), 0)

        # Test dataset summary
        summary = importer.get_dataset_summary()
        self.assertIn("total_stations", summary)
        self.assertGreater(summary["total_stations"], 0)

        # Test API switch endpoint
        client = app.test_client()
        r_status = client.get("/api/kaggle/status")
        self.assertEqual(r_status.status_code, 200)
        
        r_switch = client.post("/api/kaggle/switch-source", 
                               data=json.dumps({"source": "KAGGLE_REAL"}), 
                               content_type="application/json")
        self.assertEqual(r_switch.status_code, 200)
        self.assertEqual(r_switch.get_json()["status"], "success")


if __name__ == "__main__":
    unittest.main()
