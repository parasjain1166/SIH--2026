"""
RailBlock AI - What-If Scenario & Disruption Simulator
Enables interactive simulation of dynamic operational events:
- Emergency USFD rail fracture / OHE breakdown injection
- Cascading train delay & corridor window shift
- Machine unavailability / crew shortfall
- Siloed vs Integrated Shadow Blocking comparative simulation
"""

import copy
from typing import List, Dict, Any

from .models import (
    MaintenanceTask, TrackSection, TrainSchedule, CorridorAvailabilityWindow,
    ScheduledBlock, Department, PriorityHorizon, TaskStatus, BlockType
)
from .ai_prioritizer import AIPrioritizer
from .shadow_block_detector import ShadowBlockDetector
from .optimizer import BlockOptimizer
from .kpi_engine import KPIEngine
from .data_generator import compute_corridor_availability_windows


class WhatIfSimulator:
    def __init__(
        self,
        sections: List[TrackSection],
        tasks: List[MaintenanceTask],
        trains: List[TrainSchedule],
        prioritizer: AIPrioritizer,
        detector: ShadowBlockDetector,
        optimizer: BlockOptimizer
    ):
        self.base_sections = sections
        self.base_tasks = tasks
        self.base_trains = trains
        self.prioritizer = prioritizer
        self.detector = detector
        self.optimizer = optimizer

    def run_scenario(self, scenario_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Runs a simulated what-if condition and returns before/after comparisons."""
        
        sim_tasks = copy.deepcopy(self.base_tasks)
        sim_trains = copy.deepcopy(self.base_trains)
        sim_sections = copy.deepcopy(self.base_sections)
        
        description = ""
        
        if scenario_type == "INJECT_EMERGENCY_DEFECT":
            # Injects an urgent IMR Rail Flaw or burnt OHE wire
            dept_str = params.get("department", "TMS")
            sec_id = params.get("section_id", "SEC_GZB_MIU_UP")
            km = params.get("km", 29.5)
            
            new_task = MaintenanceTask(
                task_id=f"EMERGENCY_{dept_str}_999",
                department=Department(dept_str),
                task_name=f"EMERGENCY: Rail Flaw / Wire Defect @ KM {km}",
                task_category="USFD_IMR_RAIL_FLAW" if dept_str == "TMS" else "CONTACT_WIRE_RENEWAL",
                section_id=sec_id,
                track_line="UP",
                start_km=km,
                end_km=km + 0.5,
                required_duration_mins=90,
                safety_criticality=10.0,
                asset_degradation_score=9.9,
                urgency_days_overdue=1,
                gmt_accumulated=80.0,
                speed_restriction_if_deferred_kmh=20,
                requires_traffic_block=True,
                requires_power_block=(dept_str == "TDMS"),
                requires_st_disconnection=(dept_str == "SMMS"),
                horizon=PriorityHorizon.DAILY,
                status=TaskStatus.PENDING
            )
            sim_tasks.insert(0, new_task)
            description = f"EMERGENCY: {dept_str} defect injected at {sec_id} (KM {km}). AI re-prioritized schedule to prevent derailment / speed restriction."

        elif scenario_type == "TRAIN_DELAY_CASCADE":
            # Injects a delay into a specific train
            train_no = params.get("train_no", "22436")
            delay_mins = params.get("delay_mins", 60)
            
            for t in sim_trains:
                if t.train_no == train_no:
                    for occ in t.section_occupancies:
                        occ["entry_min"] += delay_mins
                        occ["exit_min"] += delay_mins
            description = f"Train {train_no} delayed by {delay_mins} mins. Corridor availability windows dynamically recalculated."

        elif scenario_type == "SILOED_VS_INTEGRATED_COMPARISON":
            description = "Simulating traditional departmental siloed planning (zero shadow blocking) vs RailBlock AI."

        # Re-compute windows
        sim_windows = compute_corridor_availability_windows(sim_sections, sim_trains)
        
        # Prioritize
        self.prioritizer.prioritize_all_tasks(sim_tasks, sim_sections)
        
        # Run optimization with or without shadow blocking
        if scenario_type == "SILOED_VS_INTEGRATED_COMPARISON" and not params.get("enable_shadow", True):
            # Treat each task as an isolated single-task cluster
            single_clusters = []
            for idx, t in enumerate(sim_tasks):
                c = self.detector.detect_clusters([t])[0]
                single_clusters.append(c)
            sim_blocks = self.optimizer.optimize_schedule(
                single_clusters, sim_windows, sim_trains, sim_sections, PriorityHorizon.DAILY
            )
        else:
            sim_clusters = self.detector.detect_clusters(sim_tasks)
            sim_blocks = self.optimizer.optimize_schedule(
                sim_clusters, sim_windows, sim_trains, sim_sections, PriorityHorizon.DAILY
            )

        kpis = KPIEngine.compute_kpis(sim_tasks, sim_blocks)

        return {
            "scenario_type": scenario_type,
            "description": description,
            "params": params,
            "kpis": kpis,
            "scheduled_blocks_count": len(sim_blocks),
            "shadow_blocks_count": sum(1 for b in sim_blocks if b.is_shadow_block),
            "blocks": [b.to_dict() for b in sim_blocks]
        }
