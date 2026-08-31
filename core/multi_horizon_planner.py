"""
RailBlock AI - Multi-Horizon Planning Engine
Generates and coordinates:
1. Daily Tactical Block Schedule (24h/48h operational precision)
2. Weekly Rolling Corridor Plan (7-Day track machine routing & gang shifts)
3. Monthly Master Plan (30-Day cyclic POH/AOH & TSR elimination roadmap)
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

from .models import (
    MaintenanceTask, TrackSection, TrainSchedule, CorridorAvailabilityWindow,
    ScheduledBlock, PriorityHorizon, Department, BlockType
)
from .shadow_block_detector import ShadowBlockDetector, ShadowBlockCluster
from .optimizer import BlockOptimizer


class MultiHorizonPlanner:
    def __init__(
        self,
        shadow_detector: ShadowBlockDetector,
        optimizer: BlockOptimizer
    ):
        self.detector = shadow_detector
        self.optimizer = optimizer

    def generate_all_horizons(
        self,
        tasks: List[MaintenanceTask],
        sections: List[TrackSection],
        trains: List[TrainSchedule],
        windows: List[CorridorAvailabilityWindow],
        base_date: str = "2026-08-30"
    ) -> Dict[str, Any]:
        """Generates synchronized Daily, Weekly, and Monthly plans."""
        base_dt = datetime.strptime(base_date, "%Y-%m-%d")
        
        # 1. Daily Horizon Plan (Day 1: Urgent & Emergency tasks)
        daily_tasks = [t for t in tasks if t.horizon == PriorityHorizon.DAILY or t.computed_ai_priority >= 75.0]
        daily_clusters = self.detector.detect_clusters(daily_tasks)
        daily_blocks = self.optimizer.optimize_schedule(
            daily_clusters, windows, trains, sections, PriorityHorizon.DAILY, base_date
        )
        
        # 2. Weekly Horizon Plan (7-Day rolling schedule)
        # Distributes tasks over Days 1-7 by corridor segments
        weekly_tasks = [t for t in tasks if t.horizon in [PriorityHorizon.DAILY, PriorityHorizon.WEEKLY]]
        weekly_clusters = self.detector.detect_clusters(weekly_tasks)
        
        weekly_blocks: List[ScheduledBlock] = []
        for day_offset in range(7):
            curr_date = (base_dt + timedelta(days=day_offset)).strftime("%Y-%m-%d")
            # Partition clusters across days based on section segments
            day_clusters = [c for idx, c in enumerate(weekly_clusters) if idx % 7 == day_offset]
            if day_clusters:
                blocks = self.optimizer.optimize_schedule(
                    day_clusters, windows, trains, sections, PriorityHorizon.WEEKLY, curr_date
                )
                weekly_blocks.extend(blocks)
                
        # 3. Monthly Horizon Plan (30-Day Master Schedule)
        # Includes all tasks (Daily, Weekly, Monthly) distributed over 4 weeks
        monthly_clusters = self.detector.detect_clusters(tasks)
        monthly_blocks: List[ScheduledBlock] = []
        
        # Distribute over 30 days (sample 10 key maintenance windows)
        for day_offset in range(0, 30, 3):
            curr_date = (base_dt + timedelta(days=day_offset)).strftime("%Y-%m-%d")
            day_clusters = [c for idx, c in enumerate(monthly_clusters) if (idx * 3) % 30 == day_offset]
            if day_clusters:
                blocks = self.optimizer.optimize_schedule(
                    day_clusters, windows, trains, sections, PriorityHorizon.MONTHLY, curr_date
                )
                monthly_blocks.extend(blocks)

        # 4. TSR (Temporary Speed Restriction) Elimination Roadmap
        tsr_roadmap = self._generate_tsr_elimination_roadmap(sections, tasks, monthly_blocks)

        return {
            "daily_plan": {
                "horizon": "DAILY",
                "date": base_date,
                "total_blocks": len(daily_blocks),
                "shadow_blocks": sum(1 for b in daily_blocks if b.is_shadow_block),
                "total_hours": round(sum(b.duration_mins for b in daily_blocks) / 60.0, 1),
                "blocks": [b.to_dict() for b in daily_blocks]
            },
            "weekly_plan": {
                "horizon": "WEEKLY",
                "start_date": base_date,
                "end_date": (base_dt + timedelta(days=6)).strftime("%Y-%m-%d"),
                "total_blocks": len(weekly_blocks),
                "shadow_blocks": sum(1 for b in weekly_blocks if b.is_shadow_block),
                "total_hours": round(sum(b.duration_mins for b in weekly_blocks) / 60.0, 1),
                "blocks": [b.to_dict() for b in weekly_blocks]
            },
            "monthly_plan": {
                "horizon": "MONTHLY",
                "start_date": base_date,
                "end_date": (base_dt + timedelta(days=29)).strftime("%Y-%m-%d"),
                "total_blocks": len(monthly_blocks),
                "shadow_blocks": sum(1 for b in monthly_blocks if b.is_shadow_block),
                "total_hours": round(sum(b.duration_mins for b in monthly_blocks) / 60.0, 1),
                "blocks": [b.to_dict() for b in monthly_blocks]
            },
            "tsr_roadmap": tsr_roadmap
        }

    def _generate_tsr_elimination_roadmap(
        self,
        sections: List[TrackSection],
        tasks: List[MaintenanceTask],
        scheduled_blocks: List[ScheduledBlock]
    ) -> List[Dict[str, Any]]:
        """Tracks the removal of speed restrictions as track maintenance is carried out."""
        roadmap = []
        for sec in sections:
            if sec.current_tsr_kmh is not None:
                # Find matching block
                resolving_blocks = [
                    b for b in scheduled_blocks 
                    if b.section_id == sec.section_id and any(t.department == Department.TMS for t in b.tasks)
                ]
                resolved_date = resolving_blocks[0].date_str if resolving_blocks else "Pending Next Month"
                speed_gain = sec.max_speed_kmh - sec.current_tsr_kmh
                time_saved_per_train = round((sec.length_km / sec.current_tsr_kmh - sec.length_km / sec.max_speed_kmh) * 60, 1)

                roadmap.append({
                    "section_id": sec.section_id,
                    "location_km": f"{sec.start_km} - {sec.end_km}",
                    "current_tsr_kmh": sec.current_tsr_kmh,
                    "target_max_speed_kmh": sec.max_speed_kmh,
                    "speed_restoration_gain": f"+{speed_gain} km/h",
                    "time_saved_per_train_mins": time_saved_per_train,
                    "scheduled_resolution_date": resolved_date,
                    "status": "SCHEDULED" if resolving_blocks else "PENDING_BLOCK_SANCTION"
                })
        return roadmap
