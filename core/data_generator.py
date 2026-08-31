"""
RailBlock AI - Realistic Railway Corridor & Maintenance Data Generator
Simulates an Indian Railways High-Density Network (HDN) Corridor (Delhi - Aligarh - Tundla, 150 km)
with realistic Track (TMS), Signal (SMMS), Traction (TDMS), Timetable & Freight Forecast (COA) data.
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Any

from .models import (
    Department, BlockType, PriorityHorizon, TrainType, TaskStatus,
    TrackSection, MaintenanceTask, TrainSchedule, CorridorAvailabilityWindow
)


STATIONS = [
    {"code": "NDLS", "name": "New Delhi", "km": 0.0, "has_yard": True},
    {"code": "ANVT", "name": "Anand Vihar", "km": 12.5, "has_yard": True},
    {"code": "SBB",  "name": "Sahibabad", "km": 19.8, "has_yard": False},
    {"code": "GZB",  "name": "Ghaziabad Jn", "km": 25.4, "has_yard": True},
    {"code": "MIU",  "name": "Maripat", "km": 35.8, "has_yard": False},
    {"code": "DER",  "name": "Dadri", "km": 42.1, "has_yard": True},
    {"code": "AJR",  "name": "Ajaibpur", "km": 50.3, "has_yard": False},
    {"code": "DKDE", "name": "Dankaur", "km": 58.7, "has_yard": False},
    {"code": "WAIR", "name": "Wair", "km": 70.2, "has_yard": False},
    {"code": "CHL",  "name": "Chola", "km": 77.6, "has_yard": False},
    {"code": "KRJ",  "name": "Khurja Jn", "km": 89.4, "has_yard": True},
    {"code": "SOM",  "name": "Somna", "km": 110.1, "has_yard": False},
    {"code": "ALJN", "name": "Aligarh Jn", "km": 131.2, "has_yard": True},
    {"code": "HRS",  "name": "Hathras Jn", "km": 150.0, "has_yard": False}
]

SUBSTATIONS = ["TSS_GZB_25KV", "TSS_DER_25KV", "TSS_KRJ_25KV", "TSS_ALJN_25KV"]


def generate_track_sections() -> List[TrackSection]:
    """Generates contiguous track sections along the corridor for UP and DN lines."""
    sections: List[TrackSection] = []
    for i in range(len(STATIONS) - 1):
        st1 = STATIONS[i]
        st2 = STATIONS[i+1]
        
        # UP Line
        sec_up = TrackSection(
            section_id=f"SEC_{st1['code']}_{st2['code']}_UP",
            corridor_name="Delhi-Kanpur HDN Corridor",
            start_station=st1["code"],
            end_station=st2["code"],
            line_type="UP",
            start_km=st1["km"],
            end_km=st2["km"],
            max_speed_kmh=130 if st1["km"] >= 25.4 else 110,
            current_tsr_kmh=45 if i in [3, 8] else None,  # Realistic TSRs in 2 sections
            is_electrified=True,
            signaling_system="AUTOMATIC_BLOCK" if st1["km"] < 90.0 else "EI_ABSOLUTE_BLOCK",
            daily_train_density=128 if st1["km"] < 50 else 105,
            line_capacity_pct=135.0 if st1["km"] < 50 else 118.0,
            substations=[SUBSTATIONS[min(i // 4, len(SUBSTATIONS) - 1)]]
        )
        sections.append(sec_up)
        
        # DN Line
        sec_dn = TrackSection(
            section_id=f"SEC_{st1['code']}_{st2['code']}_DN",
            corridor_name="Delhi-Kanpur HDN Corridor",
            start_station=st1["code"],
            end_station=st2["code"],
            line_type="DN",
            start_km=st1["km"],
            end_km=st2["km"],
            max_speed_kmh=130 if st1["km"] >= 25.4 else 110,
            current_tsr_kmh=30 if i == 5 else None,
            is_electrified=True,
            signaling_system="AUTOMATIC_BLOCK" if st1["km"] < 90.0 else "EI_ABSOLUTE_BLOCK",
            daily_train_density=128 if st1["km"] < 50 else 105,
            line_capacity_pct=135.0 if st1["km"] < 50 else 118.0,
            substations=[SUBSTATIONS[min(i // 4, len(SUBSTATIONS) - 1)]]
        )
        sections.append(sec_dn)
    
    return sections


def generate_maintenance_tasks(sections: List[TrackSection], seed: int = 42) -> List[MaintenanceTask]:
    """Generates realistic maintenance demands from TMS, SMMS, and TDMS with varying severities and overdue states."""
    random.seed(seed)
    tasks: List[MaintenanceTask] = []
    
    tms_templates = [
        {"cat": "USFD_IMR_RAIL_FLAW", "name": "Emergency IMR Flaw Clamp & Rail Renewal", "dur": 120, "crit": 9.8, "deg": 9.5, "pwr": False, "tsr": 30, "mach": ["WELD_GENSET_01"], "gang": ["PWAY_GANG_01"], "horiz": PriorityHorizon.DAILY},
        {"cat": "TRACK_TAMPING_CSM", "name": "Plain Track Tamping & Alignment (CSM)", "dur": 240, "crit": 7.2, "deg": 7.8, "pwr": False, "tsr": 60, "mach": ["CSM_TAMPING_01", "DGS_STABILIZER_01"], "gang": ["MACHINE_CREW_01"], "horiz": PriorityHorizon.DAILY},
        {"cat": "POINTS_CROSSING_TAMPING", "name": "Turnout Tamping by UNIMAT Machine", "dur": 180, "crit": 8.1, "deg": 8.0, "pwr": False, "tsr": 45, "mach": ["UNIMAT_TURNOUT_02"], "gang": ["PWAY_GANG_02"], "horiz": PriorityHorizon.WEEKLY},
        {"cat": "BALLAST_CLEANING_BCM", "name": "Deep Screening of Ballast by BCM", "dur": 300, "crit": 7.0, "deg": 8.4, "pwr": True, "tsr": 30, "mach": ["BCM_MACHINE_03", "BALLAST_HOPPER_01"], "gang": ["BCM_HEAVY_CREW"], "horiz": PriorityHorizon.MONTHLY},
        {"cat": "RAIL_GRINDING_RGM", "name": "Rail Grinding for Rolling Contact Fatigue", "dur": 210, "crit": 6.8, "deg": 7.1, "pwr": False, "tsr": None, "mach": ["RGM_GRINDER_01"], "gang": ["RGM_CREW"], "horiz": PriorityHorizon.WEEKLY},
        {"cat": "CWR_DESTRESSING", "name": "Destressing of Continuous Welded Rail (CWR)", "dur": 180, "crit": 7.9, "deg": 7.5, "pwr": False, "tsr": 50, "mach": ["RAIL_TENSOR_01"], "gang": ["PWAY_GANG_03"], "horiz": PriorityHorizon.WEEKLY},
        {"cat": "SLEEPER_CASUAL_RENEWAL", "name": "Casual Damaged Sleeper Replacement", "dur": 150, "crit": 6.2, "deg": 6.0, "pwr": False, "tsr": None, "mach": [], "gang": ["PWAY_GANG_04"], "horiz": PriorityHorizon.MONTHLY},
    ]
    
    smms_templates = [
        {"cat": "POINT_MACHINE_OVERHAUL", "name": "Quarterly POH & Obstruction Test of Point Machine", "dur": 120, "crit": 8.9, "deg": 8.2, "pwr": False, "st": True, "gang": ["SNT_MAINT_GANG_01"], "horiz": PriorityHorizon.DAILY},
        {"cat": "TRACK_CIRCUIT_CALIBRATION", "name": "DC/AFTC Track Circuit Bonding & Relay Health Check", "dur": 90, "crit": 7.5, "deg": 7.0, "pwr": False, "st": True, "gang": ["SNT_MAINT_GANG_02"], "horiz": PriorityHorizon.DAILY},
        {"cat": "AXLE_COUNTER_MSDAC_TEST", "name": "MSDAC Wheel Sensor Calibration & Dual Reset Testing", "dur": 120, "crit": 8.4, "deg": 7.9, "pwr": False, "st": True, "gang": ["SNT_TECH_GANG_01"], "horiz": PriorityHorizon.WEEKLY},
        {"cat": "ELECTRONIC_INTERLOCKING_POH", "name": "EI Executive Card Diagnostics & Standby Sync", "dur": 180, "crit": 9.1, "deg": 7.5, "pwr": False, "st": True, "gang": ["EI_SPECIALIST_TEAM"], "horiz": PriorityHorizon.MONTHLY},
        {"cat": "SIGNAL_CABLE_MEGGARING", "name": "Main S&T Signaling Cable Insulation Resistance Test", "dur": 150, "crit": 6.9, "deg": 7.2, "pwr": False, "st": True, "gang": ["SNT_CABLE_GANG"], "horiz": PriorityHorizon.WEEKLY},
        {"cat": "LC_GATE_INTERLOCKING_AUDIT", "name": "Level Crossing Gate Boom Lock & Interlocking Servicing", "dur": 120, "crit": 8.7, "deg": 8.0, "pwr": False, "st": True, "gang": ["SNT_MAINT_GANG_03"], "horiz": PriorityHorizon.DAILY}
    ]
    
    tdms_templates = [
        {"cat": "OHE_AOH_TOWER_WAGON", "name": "Annual Overhaul (AOH) of OHE Cantilevers & Droppers", "dur": 210, "crit": 7.8, "deg": 8.1, "pwr": True, "mach": ["TOWER_WAGON_TRD_01"], "gang": ["TRD_OHE_CREW_01"], "horiz": PriorityHorizon.WEEKLY},
        {"cat": "CONTACT_WIRE_RENEWAL", "name": "Worn Contact Wire Splicing & Height-Stagger Tuning", "dur": 240, "crit": 9.2, "deg": 9.0, "pwr": True, "mach": ["TOWER_WAGON_TRD_02", "WIRING_TRAIN_01"], "gang": ["TRD_HEAVY_CREW"], "horiz": PriorityHorizon.DAILY},
        {"cat": "NEUTRAL_SECTION_MAINT", "name": "PTFE Neutral Section Inspection & Arc Horn Gap Tuning", "dur": 150, "crit": 8.8, "deg": 8.5, "pwr": True, "mach": ["TOWER_WAGON_TRD_01"], "gang": ["TRD_OHE_CREW_02"], "horiz": PriorityHorizon.DAILY},
        {"cat": "TREE_TRIMMING_HIGH_VOLTAGE", "name": "Hazardous Tree Branch Trimming near 25kV Live Feeder", "dur": 120, "crit": 7.4, "deg": 6.8, "pwr": True, "mach": [], "gang": ["TRD_TREE_GANG"], "horiz": PriorityHorizon.DAILY},
        {"cat": "SUBSTATION_CB_OVERHAUL", "name": "25kV Vacuum Circuit Breaker & Transformer POH", "dur": 180, "crit": 8.6, "deg": 7.8, "pwr": True, "mach": [], "gang": ["PSI_SPECIALIST_TEAM"], "horiz": PriorityHorizon.MONTHLY},
        {"cat": "INSULATOR_WASHING", "name": "Hot-line / De-energized OHE Insulator High-Pressure Cleaning", "dur": 180, "crit": 6.5, "deg": 7.0, "pwr": True, "mach": ["INSULATOR_WASHING_CAR"], "gang": ["TRD_WASHING_CREW"], "horiz": PriorityHorizon.WEEKLY}
    ]
    
    task_idx = 1
    
    # 1. Targeted Correlated Tasks (Intentional Co-location for Shadow Blocking demonstration!)
    # Cluster 1: Ghaziabad - Maripat UP (Track tamping + Point machine + OHE AOH)
    sec_gzb_miu_up = next(s for s in sections if s.section_id == "SEC_GZB_MIU_UP")
    
    tasks.append(MaintenanceTask(
        task_id=f"TASK_TMS_{task_idx:03d}",
        department=Department.TMS,
        task_name="Heavy Plain Track Tamping (CSM) KM 26.0 - 32.0",
        task_category="TRACK_TAMPING_CSM",
        section_id=sec_gzb_miu_up.section_id,
        track_line="UP",
        start_km=26.0,
        end_km=32.0,
        station_code="GZB",
        required_duration_mins=210,
        safety_criticality=8.2,
        asset_degradation_score=8.5,
        urgency_days_overdue=14,
        gmt_accumulated=58.2,
        speed_restriction_if_deferred_kmh=50,
        requires_traffic_block=True,
        requires_power_block=False,
        requires_st_disconnection=False,
        required_machines=["CSM_TAMPING_01"],
        required_gangs=["MACHINE_CREW_01"],
        horizon=PriorityHorizon.DAILY,
        submission_date="2026-08-28",
        target_completion_date="2026-08-30"
    ))
    task_idx += 1

    tasks.append(MaintenanceTask(
        task_id=f"TASK_SMMS_{task_idx:03d}",
        department=Department.SMMS,
        task_name="GZB Yard Point Machine 104A/B POH & Disconnection",
        task_category="POINT_MACHINE_OVERHAUL",
        section_id=sec_gzb_miu_up.section_id,
        track_line="UP",
        start_km=25.8,
        end_km=26.4,
        station_code="GZB",
        required_duration_mins=150,
        safety_criticality=8.8,
        asset_degradation_score=8.1,
        urgency_days_overdue=8,
        gmt_accumulated=58.2,
        speed_restriction_if_deferred_kmh=30,
        requires_traffic_block=True,
        requires_power_block=False,
        requires_st_disconnection=True,
        required_machines=[],
        required_gangs=["SNT_MAINT_GANG_01"],
        horizon=PriorityHorizon.DAILY,
        submission_date="2026-08-28",
        target_completion_date="2026-08-30"
    ))
    task_idx += 1

    tasks.append(MaintenanceTask(
        task_id=f"TASK_TDMS_{task_idx:03d}",
        department=Department.TDMS,
        task_name="OHE Cantilever & Jumper Inspection KM 26.0 - 30.0",
        task_category="OHE_AOH_TOWER_WAGON",
        section_id=sec_gzb_miu_up.section_id,
        track_line="UP",
        start_km=26.0,
        end_km=30.0,
        station_code="GZB",
        required_duration_mins=180,
        safety_criticality=8.5,
        asset_degradation_score=8.4,
        urgency_days_overdue=11,
        gmt_accumulated=58.2,
        speed_restriction_if_deferred_kmh=None,
        requires_traffic_block=True,
        requires_power_block=True,
        requires_st_disconnection=False,
        required_machines=["TOWER_WAGON_TRD_01"],
        required_gangs=["TRD_OHE_CREW_01"],
        required_power_cut_substation="TSS_GZB_25KV",
        horizon=PriorityHorizon.DAILY,
        submission_date="2026-08-27",
        target_completion_date="2026-08-30"
    ))
    task_idx += 1

    # Cluster 2: Khurja - Somna DN (Ballast Cleaning + S&T Track Circuit + OHE Contact wire replacement)
    sec_krj_som_dn = next(s for s in sections if s.section_id == "SEC_KRJ_SOM_DN")
    
    tasks.append(MaintenanceTask(
        task_id=f"TASK_TMS_{task_idx:03d}",
        department=Department.TMS,
        task_name="Emergency IMR Rail Flaw Replacement KM 94.2",
        task_category="USFD_IMR_RAIL_FLAW",
        section_id=sec_krj_som_dn.section_id,
        track_line="DN",
        start_km=94.0,
        end_km=94.5,
        station_code="KRJ",
        required_duration_mins=120,
        safety_criticality=9.9,
        asset_degradation_score=9.6,
        urgency_days_overdue=3,
        gmt_accumulated=72.4,
        speed_restriction_if_deferred_kmh=20,
        requires_traffic_block=True,
        requires_power_block=False,
        requires_st_disconnection=False,
        required_machines=["WELD_GENSET_01"],
        required_gangs=["PWAY_GANG_01"],
        horizon=PriorityHorizon.DAILY,
        submission_date="2026-08-29",
        target_completion_date="2026-08-30"
    ))
    task_idx += 1

    tasks.append(MaintenanceTask(
        task_id=f"TASK_TDMS_{task_idx:03d}",
        department=Department.TDMS,
        task_name="Burnt OHE Jumper & Contact Wire Splicing KM 93.5 - 95.0",
        task_category="CONTACT_WIRE_RENEWAL",
        section_id=sec_krj_som_dn.section_id,
        track_line="DN",
        start_km=93.5,
        end_km=95.0,
        station_code="KRJ",
        required_duration_mins=150,
        safety_criticality=9.4,
        asset_degradation_score=9.1,
        urgency_days_overdue=5,
        gmt_accumulated=72.4,
        speed_restriction_if_deferred_kmh=30,
        requires_traffic_block=True,
        requires_power_block=True,
        requires_st_disconnection=False,
        required_machines=["TOWER_WAGON_TRD_02"],
        required_gangs=["TRD_HEAVY_CREW"],
        required_power_cut_substation="TSS_KRJ_25KV",
        horizon=PriorityHorizon.DAILY,
        submission_date="2026-08-29",
        target_completion_date="2026-08-30"
    ))
    task_idx += 1

    tasks.append(MaintenanceTask(
        task_id=f"TASK_SMMS_{task_idx:03d}",
        department=Department.SMMS,
        task_name="AFTC Track Circuit Tuning & Glued Joint Inspection KM 94.0",
        task_category="TRACK_CIRCUIT_CALIBRATION",
        section_id=sec_krj_som_dn.section_id,
        track_line="DN",
        start_km=94.0,
        end_km=94.8,
        station_code="KRJ",
        required_duration_mins=90,
        safety_criticality=8.0,
        asset_degradation_score=7.7,
        urgency_days_overdue=6,
        gmt_accumulated=72.4,
        speed_restriction_if_deferred_kmh=None,
        requires_traffic_block=True,
        requires_power_block=False,
        requires_st_disconnection=True,
        required_machines=[],
        required_gangs=["SNT_MAINT_GANG_02"],
        horizon=PriorityHorizon.DAILY,
        submission_date="2026-08-28",
        target_completion_date="2026-08-30"
    ))
    task_idx += 1

    # 2. General Spread Across Sections & Horizons (Daily, Weekly, Monthly)
    for sec in sections:
        # Generate 1-2 TMS tasks
        for _ in range(random.randint(1, 2)):
            tmpl = random.choice(tms_templates)
            km_start = round(sec.start_km + random.uniform(0.5, max(0.6, sec.length_km - 2.0)), 1)
            km_end = round(km_start + random.uniform(0.5, 3.5), 1)
            tasks.append(MaintenanceTask(
                task_id=f"TASK_TMS_{task_idx:03d}",
                department=Department.TMS,
                task_name=f"{tmpl['name']} (KM {km_start}-{km_end})",
                task_category=tmpl["cat"],
                section_id=sec.section_id,
                track_line=sec.line_type,
                start_km=km_start,
                end_km=km_end,
                station_code=sec.start_station,
                required_duration_mins=tmpl["dur"],
                safety_criticality=round(min(10.0, max(2.0, tmpl["crit"] + random.uniform(-1.0, 1.0))), 1),
                asset_degradation_score=round(min(10.0, max(2.0, tmpl["deg"] + random.uniform(-1.0, 1.0))), 1),
                urgency_days_overdue=random.randint(0, 30),
                gmt_accumulated=round(random.uniform(35.0, 85.0), 1),
                speed_restriction_if_deferred_kmh=tmpl.get("tsr"),
                requires_traffic_block=True,
                requires_power_block=tmpl.get("pwr", False),
                requires_st_disconnection=False,
                required_machines=tmpl.get("mach", []),
                required_gangs=tmpl.get("gang", ["PWAY_GANG_01"]),
                required_power_cut_substation=sec.substations[0] if tmpl.get("pwr") and sec.substations else None,
                horizon=tmpl["horiz"],
                submission_date="2026-08-27",
                target_completion_date="2026-09-05"
            ))
            task_idx += 1

        # Generate 1 SMMS task
        if random.random() > 0.3:
            tmpl = random.choice(smms_templates)
            km_start = round(sec.start_km + random.uniform(0.2, max(0.5, sec.length_km - 1.0)), 1)
            km_end = round(km_start + 0.5, 1)
            tasks.append(MaintenanceTask(
                task_id=f"TASK_SMMS_{task_idx:03d}",
                department=Department.SMMS,
                task_name=f"{tmpl['name']} @ {sec.start_station}",
                task_category=tmpl["cat"],
                section_id=sec.section_id,
                track_line=sec.line_type,
                start_km=km_start,
                end_km=km_end,
                station_code=sec.start_station,
                required_duration_mins=tmpl["dur"],
                safety_criticality=round(min(10.0, max(2.0, tmpl["crit"] + random.uniform(-1.0, 1.0))), 1),
                asset_degradation_score=round(min(10.0, max(2.0, tmpl["deg"] + random.uniform(-1.0, 1.0))), 1),
                urgency_days_overdue=random.randint(0, 25),
                gmt_accumulated=round(random.uniform(35.0, 85.0), 1),
                speed_restriction_if_deferred_kmh=None,
                requires_traffic_block=True,
                requires_power_block=False,
                requires_st_disconnection=tmpl.get("st", True),
                required_machines=[],
                required_gangs=tmpl.get("gang", ["SNT_MAINT_GANG_01"]),
                horizon=tmpl["horiz"],
                submission_date="2026-08-28",
                target_completion_date="2026-09-04"
            ))
            task_idx += 1

        # Generate 1 TDMS task
        if random.random() > 0.35:
            tmpl = random.choice(tdms_templates)
            km_start = round(sec.start_km + random.uniform(0.3, max(0.6, sec.length_km - 2.0)), 1)
            km_end = round(km_start + random.uniform(1.0, 4.0), 1)
            tasks.append(MaintenanceTask(
                task_id=f"TASK_TDMS_{task_idx:03d}",
                department=Department.TDMS,
                task_name=f"{tmpl['name']} (KM {km_start}-{km_end})",
                task_category=tmpl["cat"],
                section_id=sec.section_id,
                track_line=sec.line_type,
                start_km=km_start,
                end_km=km_end,
                station_code=sec.start_station,
                required_duration_mins=tmpl["dur"],
                safety_criticality=round(min(10.0, max(2.0, tmpl["crit"] + random.uniform(-1.0, 1.0))), 1),
                asset_degradation_score=round(min(10.0, max(2.0, tmpl["deg"] + random.uniform(-1.0, 1.0))), 1),
                urgency_days_overdue=random.randint(0, 20),
                gmt_accumulated=round(random.uniform(35.0, 85.0), 1),
                speed_restriction_if_deferred_kmh=None,
                requires_traffic_block=True,
                requires_power_block=tmpl.get("pwr", True),
                requires_st_disconnection=False,
                required_machines=tmpl.get("mach", ["TOWER_WAGON_TRD_01"]),
                required_gangs=tmpl.get("gang", ["TRD_OHE_CREW_01"]),
                required_power_cut_substation=sec.substations[0] if sec.substations else None,
                horizon=tmpl["horiz"],
                submission_date="2026-08-28",
                target_completion_date="2026-09-02"
            ))
            task_idx += 1
            
    return tasks


def generate_train_timetable(sections: List[TrackSection]) -> List[TrainSchedule]:
    """Generates passenger and goods train schedules across the corridor throughout 24 hours."""
    trains: List[TrainSchedule] = []
    
    # 1. High Priority Timetabled Trains (Vande Bharat, Rajdhani, Express)
    flagship_trains = [
        {"no": "22436", "name": "Vande Bharat Express", "type": TrainType.PREMIUM_EXP, "dir": "DN", "orig": "NDLS", "dest": "BSB", "dep_min": 360, "prio": 1, "speed": 130},
        {"no": "22435", "name": "Vande Bharat Express", "type": TrainType.PREMIUM_EXP, "dir": "UP", "orig": "BSB", "dest": "NDLS", "dep_min": 1260, "prio": 1, "speed": 130},
        {"no": "12302", "name": "Howrah Rajdhani Express", "type": TrainType.PREMIUM_EXP, "dir": "DN", "orig": "NDLS", "dest": "HWH", "dep_min": 1010, "prio": 1, "speed": 130},
        {"no": "12301", "name": "Howrah Rajdhani Express", "type": TrainType.PREMIUM_EXP, "dir": "UP", "orig": "HWH", "dest": "NDLS", "dep_min": 590, "prio": 1, "speed": 130},
        {"no": "12002", "name": "Bhopal Shatabdi Express", "type": TrainType.PREMIUM_EXP, "dir": "DN", "orig": "NDLS", "dest": "RKMP", "dep_min": 375, "prio": 2, "speed": 130},
        {"no": "12418", "name": "Prayagraj Express", "type": TrainType.MAIL_EXPRESS, "dir": "DN", "orig": "NDLS", "dest": "PRYJ", "dep_min": 1330, "prio": 3, "speed": 110},
        {"no": "12417", "name": "Prayagraj Express", "type": TrainType.MAIL_EXPRESS, "dir": "UP", "orig": "PRYJ", "dest": "NDLS", "dep_min": 420, "prio": 3, "speed": 110},
        {"no": "12560", "name": "Shiv Ganga Express", "type": TrainType.MAIL_EXPRESS, "dir": "DN", "orig": "NDLS", "dest": "BSB", "dep_min": 1205, "prio": 3, "speed": 110},
        {"no": "12420", "name": "Gomti Express", "type": TrainType.MAIL_EXPRESS, "dir": "DN", "orig": "NDLS", "dest": "LKO", "dep_min": 735, "prio": 4, "speed": 100},
        {"no": "12419", "name": "Gomti Express", "type": TrainType.MAIL_EXPRESS, "dir": "UP", "orig": "LKO", "dest": "NDLS", "dep_min": 870, "prio": 4, "speed": 100},
        {"no": "12398", "name": "Mahabodhi Express", "type": TrainType.MAIL_EXPRESS, "dir": "DN", "orig": "NDLS", "dest": "GAYA", "dep_min": 770, "prio": 4, "speed": 110},
        {"no": "12802", "name": "Purushottam Express", "type": TrainType.MAIL_EXPRESS, "dir": "DN", "orig": "NDLS", "dest": "PURI", "dep_min": 1365, "prio": 4, "speed": 110}
    ]
    
    sec_up_list = [s for s in sections if s.line_type == "UP"]
    sec_dn_list = [s for s in sections if s.line_type == "DN"]
    
    for f in flagship_trains:
        t = TrainSchedule(
            train_no=f["no"],
            train_name=f["name"],
            train_type=f["type"],
            direction=f["dir"],
            origin=f["orig"],
            destination=f["dest"],
            priority_rank=f["prio"],
            can_divert_to_loop=False,
            max_tolerable_delay_mins=10 if f["prio"] <= 2 else 20
        )
        
        # Calculate section occupancy times
        curr_min = f["dep_min"]
        target_sections = sec_dn_list if f["dir"] == "DN" else list(reversed(sec_up_list))
        
        for sec in target_sections:
            run_time = int((sec.length_km / f["speed"]) * 60) + random.randint(1, 3)
            t.section_occupancies.append({
                "section_id": sec.section_id,
                "entry_min": curr_min,
                "exit_min": curr_min + run_time
            })
            curr_min += run_time
            
        trains.append(t)
        
    # 2. Regular Suburban Passenger Locals (Peak Morning 07:00-10:00, Peak Evening 17:00-20:30)
    suburban_slots = [
        (420, "UP"), (450, "DN"), (480, "UP"), (510, "DN"), (540, "UP"), (570, "DN"),
        (1020, "UP"), (1050, "DN"), (1080, "UP"), (1110, "DN"), (1140, "UP"), (1170, "DN")
    ]
    for idx, (dep, d) in enumerate(suburban_slots):
        train_no = f"641{idx+10:02d}"
        t = TrainSchedule(
            train_no=train_no,
            train_name=f"Ghaziabad-Aligarh EMU Local",
            train_type=TrainType.PASSENGER,
            direction=d,
            origin="GZB" if d == "DN" else "ALJN",
            destination="ALJN" if d == "DN" else "GZB",
            priority_rank=5,
            can_divert_to_loop=True,
            max_tolerable_delay_mins=25
        )
        curr_min = dep
        target_sections = sec_dn_list if d == "DN" else list(reversed(sec_up_list))
        for sec in target_sections:
            run_time = int((sec.length_km / 65) * 60) + 2  # stops at all stations
            t.section_occupancies.append({
                "section_id": sec.section_id,
                "entry_min": curr_min,
                "exit_min": curr_min + run_time
            })
            curr_min += run_time
        trains.append(t)
        
    # 3. Goods / Freight Trains (Forecasted by Control Office)
    # Freight trains can be regulated on loop lines during maintenance blocks!
    freight_commodities = ["COAL_RAKE_NCL", "CONCOR_CONTAINER", "CEMENT_BOXN", "POL_TANKER", "FOODGRAIN_BCN"]
    freight_deps = [30, 90, 150, 210, 630, 690, 800, 890, 1250, 1310, 1390]
    
    for idx, dep in enumerate(freight_deps):
        d = "DN" if idx % 2 == 0 else "UP"
        comm = freight_commodities[idx % len(freight_commodities)]
        t_type = TrainType.FREIGHT_CONTAINER if "CONTAINER" in comm else TrainType.FREIGHT_BULK
        t = TrainSchedule(
            train_no=f"G-{comm[:4]}-{idx+101}",
            train_name=f"Freight {comm} Spl",
            train_type=t_type,
            direction=d,
            origin="DER_YARD" if d == "DN" else "TDL_YARD",
            destination="TDL_YARD" if d == "DN" else "DER_YARD",
            priority_rank=8 if t_type == TrainType.FREIGHT_CONTAINER else 9,
            can_divert_to_loop=True,
            max_tolerable_delay_mins=60,
            is_freight_forecast=True,
            freight_commodity=comm
        )
        curr_min = dep
        target_sections = sec_dn_list if d == "DN" else list(reversed(sec_up_list))
        for sec in target_sections:
            run_time = int((sec.length_km / 50) * 60) + 3
            t.section_occupancies.append({
                "section_id": sec.section_id,
                "entry_min": curr_min,
                "exit_min": curr_min + run_time
            })
            curr_min += run_time
        trains.append(t)
        
    return trains


def compute_corridor_availability_windows(
    sections: List[TrackSection], 
    trains: List[TrainSchedule],
    min_window_duration_mins: int = 60
) -> List[CorridorAvailabilityWindow]:
    """Computes available white-space maintenance windows by analyzing train headway and track occupancy."""
    windows: List[CorridorAvailabilityWindow] = []
    
    for sec in sections:
        # Collect all train occupancies on this section
        occupancies = []
        for t in trains:
            for occ in t.section_occupancies:
                if occ["section_id"] == sec.section_id:
                    occupancies.append((occ["entry_min"], occ["exit_min"], t.train_no, t.priority_rank))
                    
        # Sort by entry time
        occupancies.sort(key=lambda x: x[0])
        
        # Find gaps
        last_exit = 0
        w_idx = 1
        
        for occ in occupancies:
            gap_start = last_exit
            gap_end = occ[0]
            gap_dur = gap_end - gap_start
            
            if gap_dur >= min_window_duration_mins:
                # Classify window type
                if gap_start < 300 or gap_end > 1380:
                    w_type = "NIGHT_SLACK"
                elif 660 <= gap_start <= 900:
                    w_type = "AFTERNOON_WINDOW"
                else:
                    w_type = "DAY_INTERVAL"
                    
                windows.append(CorridorAvailabilityWindow(
                    window_id=f"WIN_{sec.section_id}_{w_idx:02d}",
                    section_id=sec.section_id,
                    track_line=sec.line_type,
                    start_time_mins=gap_start,
                    end_time_mins=gap_end,
                    duration_mins=gap_dur,
                    window_type=w_type,
                    date_str="2026-08-30",
                    train_conflict_count=0,
                    conflicting_trains=[]
                ))
                w_idx += 1
            last_exit = max(last_exit, occ[1])
            
        # Check gap after last train until midnight (1440 mins)
        if 1440 - last_exit >= min_window_duration_mins:
            windows.append(CorridorAvailabilityWindow(
                window_id=f"WIN_{sec.section_id}_{w_idx:02d}",
                section_id=sec.section_id,
                track_line=sec.line_type,
                start_time_mins=last_exit,
                end_time_mins=1440,
                duration_mins=1440 - last_exit,
                window_type="NIGHT_SLACK",
                date_str="2026-08-30"
            ))
            
    return windows
