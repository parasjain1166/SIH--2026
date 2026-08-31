"""
RailBlock AI - Intelligent Multi-Criteria AI Prioritization Engine
Evaluates maintenance tasks from TMS, SMMS, and TDMS based on:
1. Safety Risk Score (Structural, derailment risk, electrification hazards)
2. Asset Degradation & Failure Probability (GMT accumulated, wear & tear)
3. Urgency & Overdue Penalty (Exponential aging of overdue maintenance)
4. Traffic Disruption & Punctuality Impact (Corridor train density, speed differential)
5. Speed Restriction (TSR) Elimination Value
"""

import math
from typing import List, Dict, Any, Tuple
from .models import MaintenanceTask, TrackSection, Department, PriorityHorizon


class AIPrioritizer:
    def __init__(
        self,
        weight_safety: float = 0.35,
        weight_degradation: float = 0.25,
        weight_urgency: float = 0.20,
        weight_traffic_impact: float = 0.12,
        weight_tsr_avoidance: float = 0.08
    ):
        self.w_s = weight_safety
        self.w_d = weight_degradation
        self.w_u = weight_urgency
        self.w_t = weight_traffic_impact
        self.w_a = weight_tsr_avoidance

    def evaluate_task(self, task: MaintenanceTask, section: TrackSection) -> Dict[str, Any]:
        """Calculates detailed component scores and the composite AI Priority Score (0 - 100)."""
        
        # 1. Safety Score (0 - 100)
        # Scaled from 1-10 safety criticality + specific hazard multipliers
        base_safety = (task.safety_criticality / 10.0) * 100.0
        if "IMR" in task.task_category or "RAIL_FLAW" in task.task_category:
            base_safety = min(100.0, base_safety * 1.15)
        if "CONTACT_WIRE" in task.task_category or "NEUTRAL_SECTION" in task.task_category:
            base_safety = min(100.0, base_safety * 1.10)
        safety_score = round(min(100.0, base_safety), 1)

        # 2. Asset Degradation & Failure Risk Score (0 - 100)
        # Uses degradation score (1-10) + GMT accumulated stress
        gmt_stress = min(1.3, max(0.8, task.gmt_accumulated / 50.0))
        base_deg = (task.asset_degradation_score / 10.0) * 100.0 * gmt_stress
        degradation_score = round(min(100.0, base_deg), 1)

        # 3. Urgency & Overdue Score (0 - 100)
        # Non-linear exponential curve as overdue days increase
        days_overdue = max(0, task.urgency_days_overdue)
        if days_overdue == 0:
            urgency_score = 35.0
        else:
            urgency_score = min(100.0, 35.0 + 65.0 * (1.0 - math.exp(-0.08 * days_overdue)))
        urgency_score = round(urgency_score, 1)

        # 4. Traffic & Network Impact Score (0 - 100)
        # Based on section density & capacity saturation
        density_factor = min(1.0, section.daily_train_density / 140.0)
        capacity_factor = min(1.0, section.line_capacity_pct / 150.0)
        traffic_score = round((density_factor * 0.6 + capacity_factor * 0.4) * 100.0, 1)

        # 5. TSR Avoidance Score (0 - 100)
        if task.speed_restriction_if_deferred_kmh is not None:
            # Slower speed restriction = higher bottleneck severity = higher score
            speed_drop = max(0, section.max_speed_kmh - task.speed_restriction_if_deferred_kmh)
            tsr_score = round(min(100.0, (speed_drop / 100.0) * 100.0), 1)
        elif section.current_tsr_kmh is not None:
            # Task could remove an active TSR
            speed_drop = max(0, section.max_speed_kmh - section.current_tsr_kmh)
            tsr_score = round(min(100.0, (speed_drop / 100.0) * 90.0), 1)
        else:
            tsr_score = 25.0

        # Composite Weighted Score (0 - 100)
        composite_score = (
            self.w_s * safety_score +
            self.w_d * degradation_score +
            self.w_u * urgency_score +
            self.w_t * traffic_score +
            self.w_a * tsr_score
        )
        composite_score = round(min(100.0, max(10.0, composite_score)), 2)

        # Determine Priority Classification
        if composite_score >= 85.0 or task.safety_criticality >= 9.5:
            classification = "CRITICAL_EMERGENCY"
            badge_color = "red"
        elif composite_score >= 70.0:
            classification = "HIGH_PRIORITY"
            badge_color = "amber"
        elif composite_score >= 50.0:
            classification = "MEDIUM_PRIORITY"
            badge_color = "blue"
        else:
            classification = "ROUTINE_SCHEDULED"
            badge_color = "slate"

        return {
            "task_id": task.task_id,
            "composite_score": composite_score,
            "classification": classification,
            "badge_color": badge_color,
            "components": {
                "safety_score": safety_score,
                "degradation_score": degradation_score,
                "urgency_score": urgency_score,
                "traffic_score": traffic_score,
                "tsr_score": tsr_score
            },
            "weights": {
                "safety": self.w_s,
                "degradation": self.w_d,
                "urgency": self.w_u,
                "traffic": self.w_t,
                "tsr": self.w_a
            },
            "risk_factors": self._get_risk_factors(task, section, composite_score)
        }

    def _get_risk_factors(self, task: MaintenanceTask, section: TrackSection, score: float) -> List[str]:
        factors = []
        if task.safety_criticality >= 8.5:
            factors.append(f"High Safety Criticality Index ({task.safety_criticality}/10)")
        if task.urgency_days_overdue > 7:
            factors.append(f"Statutory Maintenance Overdue by {task.urgency_days_overdue} days")
        if task.gmt_accumulated >= 60.0:
            factors.append(f"High Traffic Stress ({task.gmt_accumulated} GMT carried)")
        if task.speed_restriction_if_deferred_kmh:
            factors.append(f"Prevents Severe TSR of {task.speed_restriction_if_deferred_kmh} km/h")
        if section.line_capacity_pct > 120.0:
            factors.append(f"Corridor Saturated ({section.line_capacity_pct}% Line Capacity)")
        return factors

    def prioritize_all_tasks(
        self,
        tasks: List[MaintenanceTask],
        sections: List[TrackSection]
    ) -> List[MaintenanceTask]:
        """Evaluates all tasks and assigns computed_ai_priority and rank."""
        section_map = {s.section_id: s for s in sections}
        
        for task in tasks:
            sec = section_map.get(task.section_id)
            if sec:
                eval_res = self.evaluate_task(task, sec)
                task.computed_ai_priority = eval_res["composite_score"]
            else:
                task.computed_ai_priority = 50.0

        # Sort tasks descending by composite score
        tasks.sort(key=lambda t: t.computed_ai_priority, reverse=True)
        
        for rank, task in enumerate(tasks, start=1):
            task.risk_rank = rank

        return tasks
