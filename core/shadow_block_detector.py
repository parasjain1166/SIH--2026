"""
RailBlock AI - Multi-Department Shadow / Joint Block Detector
Identifies spatial-temporal synergies across TMS (Track), SMMS (Signal), and TDMS (Traction/OHE)
to bundle separate maintenance demands into unified, high-efficiency "Shadow Blocks".
"""

from typing import List, Dict, Tuple, Any, Optional
from collections import defaultdict
from .models import MaintenanceTask, Department, BlockType, PriorityHorizon


class ShadowBlockCluster:
    def __init__(self, cluster_id: str, section_id: str, track_line: str):
        self.cluster_id = cluster_id
        self.section_id = section_id
        self.track_line = track_line
        self.tasks: List[MaintenanceTask] = []
        self.departments: set[Department] = set()
        self.start_km: float = 999999.0
        self.end_km: float = -1.0
        self.max_duration_mins: int = 0
        self.sum_individual_duration_mins: int = 0
        self.requires_power_block: bool = False
        self.requires_st_disconnection: bool = False
        self.required_machines: List[str] = []
        self.required_gangs: List[str] = []
        self.substations: set[str] = set()

    def add_task(self, task: MaintenanceTask):
        self.tasks.append(task)
        self.departments.add(task.department)
        self.start_km = min(self.start_km, task.start_km)
        self.end_km = max(self.end_km, task.end_km)
        self.sum_individual_duration_mins += task.required_duration_mins
        
        # When tasks are executed together, joint block duration is max(tasks) + safety buffer (15-30m)
        self.max_duration_mins = max(self.max_duration_mins, task.required_duration_mins)
        
        if task.requires_power_block:
            self.requires_power_block = True
        if task.requires_st_disconnection:
            self.requires_st_disconnection = True
        if task.required_power_cut_substation:
            self.substations.add(task.required_power_cut_substation)
            
        for m in task.required_machines:
            if m not in self.required_machines:
                self.required_machines.append(m)
        for g in task.required_gangs:
            if g not in self.required_gangs:
                self.required_gangs.append(g)

    @property
    def joint_duration_mins(self) -> int:
        # 15 min buffer for joint safety briefing, earthing discharge rod, and track clearance
        if len(self.tasks) > 1:
            return self.max_duration_mins + 15
        return self.max_duration_mins

    @property
    def hours_saved(self) -> float:
        return round((self.sum_individual_duration_mins - self.joint_duration_mins) / 60.0, 2)

    @property
    def efficiency_gain_pct(self) -> float:
        if self.sum_individual_duration_mins == 0:
            return 0.0
        return round(((self.sum_individual_duration_mins - self.joint_duration_mins) / self.sum_individual_duration_mins) * 100.0, 1)

    @property
    def is_multi_department(self) -> bool:
        return len(self.departments) > 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "section_id": self.section_id,
            "track_line": self.track_line,
            "start_km": self.start_km,
            "end_km": self.end_km,
            "task_count": len(self.tasks),
            "departments": [d.value for d in self.departments],
            "is_shadow_block": self.is_multi_department,
            "joint_duration_mins": self.joint_duration_mins,
            "sum_individual_duration_mins": self.sum_individual_duration_mins,
            "hours_saved": self.hours_saved,
            "efficiency_gain_pct": self.efficiency_gain_pct,
            "requires_power_block": self.requires_power_block,
            "requires_st_disconnection": self.requires_st_disconnection,
            "required_machines": self.required_machines,
            "required_gangs": self.required_gangs,
            "task_ids": [t.task_id for t in self.tasks]
        }


class ShadowBlockDetector:
    def __init__(self, max_km_separation: float = 6.0):
        self.max_km_separation = max_km_separation

    def detect_clusters(self, tasks: List[MaintenanceTask]) -> List[ShadowBlockCluster]:
        """Groups compatible tasks on the same section and track line into Shadow Block Clusters."""
        # 1. Group by (section_id, track_line, horizon)
        grouped: Dict[Tuple[str, str, PriorityHorizon], List[MaintenanceTask]] = defaultdict(list)
        for task in tasks:
            grouped[(task.section_id, task.track_line, task.horizon)].append(task)

        clusters: List[ShadowBlockCluster] = []
        cluster_counter = 1

        for (sec_id, line, horizon), sec_tasks in grouped.items():
            # Sort by start_km
            sec_tasks.sort(key=lambda t: t.start_km)
            
            # Sub-cluster based on KM proximity and department diversity
            curr_cluster = None
            for t in sec_tasks:
                if curr_cluster is None:
                    curr_cluster = ShadowBlockCluster(
                        cluster_id=f"SHADOW_CLUST_{cluster_counter:03d}",
                        section_id=sec_id,
                        track_line=line
                    )
                    cluster_counter += 1
                    curr_cluster.add_task(t)
                    t.shadow_cluster_id = curr_cluster.cluster_id
                else:
                    # Check spatial distance
                    km_distance = abs(t.start_km - curr_cluster.start_km)
                    if km_distance <= self.max_km_separation:
                        curr_cluster.add_task(t)
                        t.shadow_cluster_id = curr_cluster.cluster_id
                    else:
                        clusters.append(curr_cluster)
                        curr_cluster = ShadowBlockCluster(
                            cluster_id=f"SHADOW_CLUST_{cluster_counter:03d}",
                            section_id=sec_id,
                            track_line=line
                        )
                        cluster_counter += 1
                        curr_cluster.add_task(t)
                        t.shadow_cluster_id = curr_cluster.cluster_id

            if curr_cluster is not None:
                clusters.append(curr_cluster)

        return clusters

    def calculate_shadow_summary(self, clusters: List[ShadowBlockCluster]) -> Dict[str, Any]:
        multi_dept_clusters = [c for c in clusters if c.is_multi_department]
        total_hours_saved = sum(c.hours_saved for c in multi_dept_clusters)
        total_individual_hours = sum(c.sum_individual_duration_mins for c in clusters) / 60.0
        total_joint_hours = sum(c.joint_duration_mins for c in clusters) / 60.0
        
        overall_gain = 0.0
        if total_individual_hours > 0:
            overall_gain = round(((total_individual_hours - total_joint_hours) / total_individual_hours) * 100.0, 1)

        return {
            "total_clusters": len(clusters),
            "shadow_clusters_count": len(multi_dept_clusters),
            "total_hours_saved": round(total_hours_saved, 2),
            "total_individual_hours": round(total_individual_hours, 2),
            "total_joint_hours": round(total_joint_hours, 2),
            "overall_efficiency_gain_pct": overall_gain,
            "clusters": [c.to_dict() for c in clusters]
        }
