"""
RailBlock AI - Core Domain Models
Represents Track Infrastructure, TMS (Track), SMMS (Signalling), TDMS (Traction/OHE),
Train Timetables (COA), Corridor Windows, and Scheduled Joint/Shadow Blocks.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime, time


class Department(str, Enum):
    TMS = "TMS"       # Track Management System (Engineering / Civil)
    SMMS = "SMMS"     # Signalling Maintenance & Management System (S&T)
    TDMS = "TDMS"     # Traction Distribution Management System (TRD / Electrical)
    JOINT = "JOINT"   # Multi-department Joint / Shadow Block


class BlockType(str, Enum):
    TRAFFIC_BLOCK = "TRAFFIC_BLOCK"          # Track occupancy by Engineering/Machines
    POWER_BLOCK = "POWER_BLOCK"              # OHE de-energization & earthing
    DISCONNECTION = "DISCONNECTION"          # S&T Disconnection Notice (T/351)
    INTEGRATED_BLOCK = "INTEGRATED_BLOCK"    # Joint Shadow Block (Traffic + Power + Disconnection)


class PriorityHorizon(str, Enum):
    DAILY = "DAILY"        # 24-48 Hour Tactical Operational Window
    WEEKLY = "WEEKLY"      # 7-Day Rolling Corridor Plan
    MONTHLY = "MONTHLY"    # 30-Day Master Cyclic Maintenance


class TrainType(str, Enum):
    PREMIUM_EXP = "PREMIUM_EXP"      # Vande Bharat / Rajdhani / Shatabdi
    MAIL_EXPRESS = "MAIL_EXPRESS"    # Superfast / Mail / Express
    PASSENGER = "PASSENGER"          # Suburban / Passenger Local
    FREIGHT_CONTAINER = "FREIGHT_CONTAINER"  # High-priority goods (CONCOR)
    FREIGHT_BULK = "FREIGHT_BULK"            # Coal / Iron Ore / Cement / POL


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    DEFERRED = "DEFERRED"


@dataclass
class TrackSection:
    section_id: str                      # e.g., "SEC-NDLS-GZB-UP"
    corridor_name: str                   # e.g., "Delhi-Kanpur HDN Corridor"
    start_station: str                   # e.g., "NDLS"
    end_station: str                     # e.g., "GZB"
    line_type: str                       # "UP", "DN", "3RD", "4TH"
    start_km: float                      # e.g., 0.0
    end_km: float                        # e.g., 25.4
    max_speed_kmh: int = 130
    current_tsr_kmh: Optional[int] = None  # Temporary Speed Restriction
    is_electrified: bool = True
    signaling_system: str = "AUTOMATIC_BLOCK"  # "AUTOMATIC_BLOCK", "ABSOLUTE_BLOCK", "EI"
    daily_train_density: int = 110       # Trains per day
    line_capacity_pct: float = 125.0     # Saturation percentage
    substations: List[str] = field(default_factory=list)

    @property
    def length_km(self) -> float:
        return round(abs(self.end_km - self.start_km), 2)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["length_km"] = self.length_km
        return d


@dataclass
class MaintenanceTask:
    task_id: str
    department: Department
    task_name: str
    task_category: str                   # e.g. "USFD_IMR_REPLACEMENT", "TAMPING_CSM", "POINT_MACHINE_POH"
    section_id: str
    track_line: str                      # "UP", "DN", "BOTH", "YARD"
    start_km: float
    end_km: float
    station_code: Optional[str] = None
    required_duration_mins: int = 120
    min_duration_mins: int = 60
    
    # Priority & Risk Metrics (1 to 10 scale)
    safety_criticality: float = 5.0      # Higher = catastrophic failure risk
    asset_degradation_score: float = 5.0 # Higher = physical wear & tear severity
    urgency_days_overdue: int = 0        # Overdue maintenance inspection days
    gmt_accumulated: float = 40.0        # Gross Million Tonnes carried
    speed_restriction_if_deferred_kmh: Optional[int] = None
    
    # Block & Safety Requirements
    requires_traffic_block: bool = True
    requires_power_block: bool = False
    requires_st_disconnection: bool = False
    is_shadow_eligible: bool = True
    
    # Resource Requirements
    required_machines: List[str] = field(default_factory=list) # e.g. ["CSM_TAMPING_01"]
    required_gangs: List[str] = field(default_factory=list)    # e.g. ["PWAY_GANG_03"]
    required_power_cut_substation: Optional[str] = None
    
    # Scheduling State
    submission_date: str = ""
    target_completion_date: str = ""
    horizon: PriorityHorizon = PriorityHorizon.DAILY
    status: TaskStatus = TaskStatus.PENDING
    
    # AI-Engine Computed Fields
    computed_ai_priority: float = 0.0    # 0 to 100 Score
    risk_rank: int = 0
    shadow_cluster_id: Optional[str] = None
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["department"] = self.department.value
        d["horizon"] = self.horizon.value
        d["status"] = self.status.value
        return d


@dataclass
class TrainSchedule:
    train_no: str
    train_name: str
    train_type: TrainType
    direction: str                       # "UP" or "DN"
    origin: str
    destination: str
    priority_rank: int                   # 1 (Highest, e.g. Vande Bharat) to 10 (Freight)
    
    # Time-distance section occupancy: list of {"section_id": str, "entry_min": int, "exit_min": int}
    section_occupancies: List[Dict[str, Any]] = field(default_factory=list)
    can_divert_to_loop: bool = False
    max_tolerable_delay_mins: int = 15
    is_freight_forecast: bool = False
    freight_commodity: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["train_type"] = self.train_type.value
        return d


@dataclass
class CorridorAvailabilityWindow:
    window_id: str
    section_id: str
    track_line: str
    start_time_mins: int                 # Minutes from midnight 0 to 1440
    end_time_mins: int
    duration_mins: int
    window_type: str                     # "NIGHT_SLACK", "DAY_INTERVAL", "ENGINEERED_CORRIDOR"
    date_str: str = ""                   # e.g. "2026-08-30"
    train_conflict_count: int = 0
    conflicting_trains: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScheduledBlock:
    block_id: str
    horizon: PriorityHorizon
    date_str: str
    section_id: str
    track_line: str
    start_km: float
    end_km: float
    start_time_str: str                  # e.g. "01:30"
    end_time_str: str                    # e.g. "04:30"
    start_time_mins: int
    end_time_mins: int
    duration_mins: int
    block_type: BlockType
    departments_involved: List[Department]
    tasks: List[MaintenanceTask]
    is_shadow_block: bool
    assigned_resources: List[str]
    
    # Traffic Regulation Impact
    trains_regulated: List[Dict[str, Any]] = field(default_factory=list)
    total_train_delay_mins: int = 0
    passenger_trains_affected: int = 0
    freight_trains_affected: int = 0
    
    # Official IR Disconnection / Permit Memos
    block_permit_no: str = ""
    st_disconnection_memo_t351: str = ""
    trd_power_permit_no: str = ""
    coa_control_grant_id: str = ""
    status: str = "CONFIRMED"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["horizon"] = self.horizon.value
        d["block_type"] = self.block_type.value
        d["departments_involved"] = [dept.value for dept in self.departments_involved]
        d["tasks"] = [task.to_dict() if hasattr(task, 'to_dict') else task for task in self.tasks]
        return d


@dataclass
class SystemKPISummary:
    total_maintenance_demands: int
    tasks_scheduled_count: int
    tasks_deferred_count: int
    total_block_hours_granted: float
    shadow_blocks_count: int
    shadow_blocking_efficiency_gain_pct: float
    asset_availability_index_pct: float
    train_punctuality_impact_mins: int
    safety_risk_reduction_pct: float
    speed_restrictions_avoided: int
    departmental_utilization: Dict[str, Any] = field(default_factory=dict)
    horizon_breakdown: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
