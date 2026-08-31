"""
RailBlock AI - Constraint Optimization & Intelligent Block Scheduler
Schedules maintenance tasks and shadow clusters into corridor availability windows,
minimizing train punctuality loss and respecting machine, gang, and power cut constraints.
"""

from typing import List, Dict, Tuple, Any, Optional
from datetime import datetime, timedelta
import math

from .models import (
    MaintenanceTask, TrackSection, TrainSchedule, CorridorAvailabilityWindow,
    ScheduledBlock, Department, BlockType, PriorityHorizon, TrainType, TaskStatus
)
from .shadow_block_detector import ShadowBlockCluster


class BlockOptimizer:
    def __init__(
        self,
        passenger_delay_penalty: float = 50.0,
        freight_delay_penalty: float = 5.0,
        unserved_priority_penalty: float = 100.0,
        shadow_block_bonus: float = 200.0
    ):
        self.passenger_penalty = passenger_delay_penalty
        self.freight_penalty = freight_delay_penalty
        self.unserved_penalty = unserved_priority_penalty
        self.shadow_bonus = shadow_block_bonus

    def optimize_schedule(
        self,
        clusters: List[ShadowBlockCluster],
        windows: List[CorridorAvailabilityWindow],
        trains: List[TrainSchedule],
        sections: List[TrackSection],
        horizon: PriorityHorizon = PriorityHorizon.DAILY,
        date_str: str = "2026-08-30"
    ) -> List[ScheduledBlock]:
        """Schedules clusters into availability windows using multi-objective heuristic constraint optimization."""
        
        # Filter clusters and windows by horizon/section
        scheduled_blocks: List[ScheduledBlock] = []
        
        # Track machine and gang time-occupancies: resource_name -> list of (start_min, end_min, block_id)
        resource_timeline: Dict[str, List[Tuple[int, int, str]]] = {}
        
        # Sort clusters by priority of their tasks
        def cluster_priority(clust: ShadowBlockCluster) -> float:
            if not clust.tasks:
                return 0.0
            avg_prio = sum(t.computed_ai_priority for t in clust.tasks) / len(clust.tasks)
            max_prio = max(t.computed_ai_priority for t in clust.tasks)
            # Bonus for multi-department synergy
            synergy = 25.0 if clust.is_multi_department else 0.0
            return max_prio * 0.7 + avg_prio * 0.3 + synergy

        sorted_clusters = sorted(clusters, key=cluster_priority, reverse=True)
        
        # Build lookup for windows by (section_id, track_line)
        window_map: Dict[Tuple[str, str], List[CorridorAvailabilityWindow]] = {}
        for w in windows:
            key = (w.section_id, w.track_line)
            if key not in window_map:
                window_map[key] = []
            window_map[key].append(w)
            
        block_counter = 1
        
        for clust in sorted_clusters:
            key = (clust.section_id, clust.track_line)
            sec_windows = window_map.get(key, [])
            
            best_window: Optional[CorridorAvailabilityWindow] = None
            best_start_min: int = 0
            best_end_min: int = 0
            best_cost: float = float('inf')
            best_train_impacts: List[Dict[str, Any]] = []
            
            # Find best fitting window for this cluster
            for win in sec_windows:
                # Can cluster fit in this window?
                dur = clust.joint_duration_mins
                
                # Try placing at the start of window, middle, or night slots
                potential_starts = [
                    win.start_time_mins,
                    max(win.start_time_mins, 60),    # 01:00 AM
                    max(win.start_time_mins, 120),   # 02:00 AM
                    win.start_time_mins + 15
                ]
                
                for candidate_start in potential_starts:
                    candidate_end = candidate_start + dur
                    if candidate_end > win.end_time_mins + 30:  # allow 30 min flexibility with train regulation
                        continue
                        
                    # Check resource conflict
                    conflict = False
                    for r in clust.required_machines + clust.required_gangs:
                        if r in resource_timeline:
                            for (r_start, r_end, b_id) in resource_timeline[r]:
                                if not (candidate_end <= r_start or candidate_start >= r_end):
                                    conflict = True
                                    break
                        if conflict:
                            break
                            
                    if conflict:
                        continue
                        
                    # Evaluate train impacts during this candidate block
                    train_impacts, cost = self._evaluate_train_interference(
                        clust.section_id, candidate_start, candidate_end, trains
                    )
                    
                    # Reward multi-department savings
                    cost -= (clust.hours_saved * self.shadow_bonus)
                    
                    if cost < best_cost:
                        best_cost = cost
                        best_window = win
                        best_start_min = candidate_start
                        best_end_min = candidate_end
                        best_train_impacts = train_impacts
                        
            # If feasible window found
            if best_window is not None:
                # Format time strings
                start_h = (best_start_min // 60) % 24
                start_m = best_start_min % 60
                end_h = (best_end_min // 60) % 24
                end_m = best_end_min % 60
                
                start_time_str = f"{start_h:02d}:{start_m:02d}"
                end_time_str = f"{end_h:02d}:{end_m:02d}"
                
                # Determine Block Type
                if clust.is_multi_department:
                    b_type = BlockType.INTEGRATED_BLOCK
                elif clust.requires_power_block:
                    b_type = BlockType.POWER_BLOCK
                elif clust.requires_st_disconnection:
                    b_type = BlockType.DISCONNECTION
                else:
                    b_type = BlockType.TRAFFIC_BLOCK
                    
                block_id = f"BLK_{horizon.value[:3]}_{block_counter:03d}"
                block_counter += 1
                
                # Book resources
                all_resources = clust.required_machines + clust.required_gangs
                for r in all_resources:
                    if r not in resource_timeline:
                        resource_timeline[r] = []
                    resource_timeline[r].append((best_start_min, best_end_min, block_id))
                    
                # Generate official Indian Railways memos
                station_code = clust.section_id.split('_')[1] if '_' in clust.section_id else "SEC"
                
                sec_block = ScheduledBlock(
                    block_id=block_id,
                    horizon=horizon,
                    date_str=date_str,
                    section_id=clust.section_id,
                    track_line=clust.track_line,
                    start_km=clust.start_km,
                    end_km=clust.end_km,
                    start_time_str=start_time_str,
                    end_time_str=end_time_str,
                    start_time_mins=best_start_min,
                    end_time_mins=best_end_min,
                    duration_mins=clust.joint_duration_mins,
                    block_type=b_type,
                    departments_involved=list(clust.departments),
                    tasks=clust.tasks,
                    is_shadow_block=clust.is_multi_department,
                    assigned_resources=all_resources,
                    trains_regulated=best_train_impacts,
                    total_train_delay_mins=sum(t.get("delay_mins", 0) for t in best_train_impacts),
                    passenger_trains_affected=sum(1 for t in best_train_impacts if t.get("is_passenger")),
                    freight_trains_affected=sum(1 for t in best_train_impacts if not t.get("is_passenger")),
                    block_permit_no=f"IR/BDMS/{date_str.replace('-', '')}/{block_id}",
                    st_disconnection_memo_t351=f"SNT/T351/{station_code}/{block_id}" if clust.requires_st_disconnection else "N/A",
                    trd_power_permit_no=f"TRD/PB/{station_code}/{block_id}" if clust.requires_power_block else "N/A",
                    coa_control_grant_id=f"COA-SANCTION-{block_id}-OK"
                )
                
                # Update task states
                for t in clust.tasks:
                    t.status = TaskStatus.SCHEDULED
                    t.scheduled_start = f"{date_str} {start_time_str}"
                    t.scheduled_end = f"{date_str} {end_time_str}"
                    
                scheduled_blocks.append(sec_block)
            else:
                # Mark deferred
                for t in clust.tasks:
                    t.status = TaskStatus.DEFERRED
                    
        return scheduled_blocks

    def _evaluate_train_interference(
        self,
        section_id: str,
        start_min: int,
        end_min: int,
        trains: List[TrainSchedule]
    ) -> Tuple[List[Dict[str, Any]], float]:
        """Calculates punctuality loss and loop regulations if a block is granted in this window."""
        impacts: List[Dict[str, Any]] = []
        cost = 0.0
        
        for t in trains:
            for occ in t.section_occupancies:
                if occ["section_id"] == section_id:
                    # Check overlap with block [start_min, end_min]
                    if not (occ["exit_min"] <= start_min or occ["entry_min"] >= end_min):
                        # Train is impacted!
                        is_pass = t.train_type in [TrainType.PREMIUM_EXP, TrainType.MAIL_EXPRESS, TrainType.PASSENGER]
                        
                        # Calculate delay
                        delay = max(5, end_min - occ["entry_min"] + 5)
                        
                        if t.train_type == TrainType.PREMIUM_EXP:
                            # Severe penalty for Vande Bharat / Rajdhani
                            cost += delay * 500.0
                            action = "RESCHEDULED_CRITICAL"
                        elif t.train_type == TrainType.MAIL_EXPRESS:
                            cost += delay * 100.0
                            action = "REGULATED_BEHIND_BLOCK"
                        elif t.train_type == TrainType.PASSENGER:
                            cost += delay * 40.0
                            action = "LOOP_REGULATION"
                        else:
                            # Freight
                            cost += delay * 5.0
                            action = "LOOP_LINE_STABLED"
                            
                        impacts.append({
                            "train_no": t.train_no,
                            "train_name": t.train_name,
                            "train_type": t.train_type.value,
                            "priority_rank": t.priority_rank,
                            "delay_mins": min(delay, 90),
                            "action": action,
                            "is_passenger": is_pass
                        })
                        
        return impacts, cost
