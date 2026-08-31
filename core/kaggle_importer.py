"""
RailBlock AI - Kaggle & Real-World Dataset Ingestion Pipeline
Integrates real Indian Railways Kaggle datasets (Timetables, Stations, Train Schedules, Defect logs)
and provides custom CSV upload and automatic schema normalization.
"""

import os
import csv
import json
from typing import List, Dict, Tuple, Any, Optional
from datetime import datetime

from .models import (
    TrackSection, MaintenanceTask, TrainSchedule,
    Department, BlockType, PriorityHorizon, TrainType, TaskStatus
)


class KaggleDataImporter:
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.data_dir = os.path.join(base_dir, "data", "kaggle_real")
        else:
            self.data_dir = data_dir

    def load_real_stations(self) -> List[Dict[str, Any]]:
        """Loads real station master records from stations.csv."""
        path = os.path.join(self.data_dir, "stations.csv")
        stations = []
        if not os.path.exists(path):
            return stations

        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stations.append({
                    "code": row["station_code"],
                    "name": row["station_name"],
                    "km": float(row["km_from_origin"]),
                    "division": row["division"],
                    "zone": row["zone"],
                    "state": row["state"],
                    "has_yard": row.get("has_yard", "False").lower() == "true",
                    "platforms": int(row.get("platforms", 2))
                })
        return stations

    def build_track_sections_from_stations(self, stations: List[Dict[str, Any]]) -> List[TrackSection]:
        """Synthesizes contiguous UP and DN track sections from real station KM distances."""
        sections: List[TrackSection] = []
        substations = ["TSS_GZB_25KV", "TSS_DER_25KV", "TSS_KRJ_25KV", "TSS_ALJN_25KV", "TSS_TDL_25KV", "TSS_CNB_25KV"]
        
        for i in range(len(stations) - 1):
            st1 = stations[i]
            st2 = stations[i+1]
            sub = substations[min(i // 3, len(substations) - 1)]

            # UP Section
            sec_up = TrackSection(
                section_id=f"SEC_{st1['code']}_{st2['code']}_UP",
                corridor_name=f"{st1['division']} Division Trunk Route",
                start_station=st1["code"],
                end_station=st2["code"],
                line_type="UP",
                start_km=st1["km"],
                end_km=st2["km"],
                max_speed_kmh=130 if st1["km"] >= 25.4 else 110,
                current_tsr_kmh=45 if i in [2, 5] else None,
                is_electrified=True,
                signaling_system="AUTOMATIC_BLOCK" if st1["km"] < 100.0 else "EI_ABSOLUTE_BLOCK",
                daily_train_density=125 if st1["km"] < 60 else 110,
                line_capacity_pct=130.0 if st1["km"] < 60 else 115.0,
                substations=[sub]
            )
            sections.append(sec_up)

            # DN Section
            sec_dn = TrackSection(
                section_id=f"SEC_{st1['code']}_{st2['code']}_DN",
                corridor_name=f"{st1['division']} Division Trunk Route",
                start_station=st1["code"],
                end_station=st2["code"],
                line_type="DN",
                start_km=st1["km"],
                end_km=st2["km"],
                max_speed_kmh=130 if st1["km"] >= 25.4 else 110,
                current_tsr_kmh=30 if i == 3 else None,
                is_electrified=True,
                signaling_system="AUTOMATIC_BLOCK" if st1["km"] < 100.0 else "EI_ABSOLUTE_BLOCK",
                daily_train_density=125 if st1["km"] < 60 else 110,
                line_capacity_pct=130.0 if st1["km"] < 60 else 115.0,
                substations=[sub]
            )
            sections.append(sec_dn)

        return sections

    def load_real_trains(self, sections: List[TrackSection]) -> List[TrainSchedule]:
        """Loads real trains and calculates occupancy intervals across the corridor sections."""
        trains_path = os.path.join(self.data_dir, "trains.csv")
        trains: List[TrainSchedule] = []
        if not os.path.exists(trains_path):
            return trains

        sec_up_list = [s for s in sections if s.line_type == "UP"]
        sec_dn_list = [s for s in sections if s.line_type == "DN"]

        with open(trains_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                t_type = TrainType(row["train_type"])
                is_freight = row.get("is_freight", "False").lower() == "true"
                
                # Parse departure time (HH:MM) to minutes
                dep_parts = row["departure_time"].split(":")
                dep_mins = int(dep_parts[0]) * 60 + int(dep_parts[1])

                t = TrainSchedule(
                    train_no=row["train_no"],
                    train_name=row["train_name"],
                    train_type=t_type,
                    direction=row["direction"],
                    origin=row["origin"],
                    destination=row["destination"],
                    priority_rank=int(row["priority_rank"]),
                    can_divert_to_loop=is_freight or t_type == TrainType.PASSENGER,
                    max_tolerable_delay_mins=15 if int(row["priority_rank"]) <= 2 else 45,
                    is_freight_forecast=is_freight,
                    freight_commodity=row["train_name"] if is_freight else None
                )

                # Assign section traversals.  Clip the corridor traversal to the
                # known origin/destination when either station exists in this dataset.
                # This keeps station-level analysis realistic for local trains instead
                # of incorrectly making every train occupy every section.
                speed = float(row.get("speed_kmh", 100))
                curr_min = dep_mins

                station_order = []
                if sec_dn_list:
                    station_order = [sec_dn_list[0].start_station] + [sec.end_station for sec in sec_dn_list]
                station_index = {code: idx for idx, code in enumerate(station_order)}
                origin_idx = station_index.get(row["origin"])
                dest_idx = station_index.get(row["destination"])

                base_sections = sec_dn_list if row["direction"] == "DN" else list(reversed(sec_up_list))
                target_sections = []
                for sec in base_sections:
                    # Section index is based on the low-KM -> high-KM station order,
                    # even when an UP train traverses those sections in reverse.
                    try:
                        sec_idx = station_index[sec.start_station]
                    except KeyError:
                        continue

                    include = True
                    if origin_idx is not None and dest_idx is not None:
                        lo, hi = sorted((origin_idx, dest_idx))
                        include = lo <= sec_idx < hi
                    elif origin_idx is not None:
                        include = sec_idx >= origin_idx if row["direction"] == "DN" else sec_idx < origin_idx
                    elif dest_idx is not None:
                        include = sec_idx < dest_idx if row["direction"] == "DN" else sec_idx >= dest_idx

                    if include:
                        target_sections.append(sec)

                for sec in target_sections:
                    run_time = int((sec.length_km / max(40.0, speed)) * 60) + 2
                    t.section_occupancies.append({
                        "section_id": sec.section_id,
                        "entry_min": curr_min,
                        "exit_min": curr_min + run_time
                    })
                    curr_min += run_time

                trains.append(t)

        return trains

    def load_real_maintenance_tasks(self) -> List[MaintenanceTask]:
        """Loads real TMS, SMMS, and TDMS maintenance records from CSVs."""
        tasks: List[MaintenanceTask] = []
        
        # 1. TMS Tasks
        tms_path = os.path.join(self.data_dir, "tms_defects_real.csv")
        if os.path.exists(tms_path):
            with open(tms_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tsr_val = int(row["speed_restriction_if_deferred_kmh"]) if row.get("speed_restriction_if_deferred_kmh") and row["speed_restriction_if_deferred_kmh"] != "None" else None
                    mach = [m.strip() for m in row["required_machines"].split(",") if m.strip()] if row.get("required_machines") else []
                    gang = [g.strip() for g in row["required_gangs"].split(",") if g.strip()] if row.get("required_gangs") else []

                    tasks.append(MaintenanceTask(
                        task_id=row["task_id"],
                        department=Department.TMS,
                        task_name=row["task_name"],
                        task_category=row["task_category"],
                        section_id=row["section_id"],
                        track_line=row["track_line"],
                        start_km=float(row["start_km"]),
                        end_km=float(row["end_km"]),
                        station_code=row.get("station_code"),
                        required_duration_mins=int(row["required_duration_mins"]),
                        safety_criticality=float(row["safety_criticality"]),
                        asset_degradation_score=float(row["asset_degradation_score"]),
                        urgency_days_overdue=int(row["urgency_days_overdue"]),
                        gmt_accumulated=float(row["gmt_accumulated"]),
                        speed_restriction_if_deferred_kmh=tsr_val,
                        requires_traffic_block=row.get("requires_traffic_block", "True").lower() == "true",
                        requires_power_block=row.get("requires_power_block", "False").lower() == "true",
                        required_machines=mach,
                        required_gangs=gang,
                        horizon=PriorityHorizon(row.get("horizon", "DAILY")),
                        status=TaskStatus(row.get("status", "PENDING"))
                    ))

        # 2. SMMS Tasks
        smms_path = os.path.join(self.data_dir, "smms_faults_real.csv")
        if os.path.exists(smms_path):
            with open(smms_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    gang = [g.strip() for g in row["required_gangs"].split(",") if g.strip()] if row.get("required_gangs") else []

                    tasks.append(MaintenanceTask(
                        task_id=row["task_id"],
                        department=Department.SMMS,
                        task_name=row["task_name"],
                        task_category=row["task_category"],
                        section_id=row["section_id"],
                        track_line=row["track_line"],
                        start_km=float(row["start_km"]),
                        end_km=float(row["end_km"]),
                        station_code=row.get("station_code"),
                        required_duration_mins=int(row["required_duration_mins"]),
                        safety_criticality=float(row["safety_criticality"]),
                        asset_degradation_score=float(row["asset_degradation_score"]),
                        urgency_days_overdue=int(row["urgency_days_overdue"]),
                        gmt_accumulated=float(row["gmt_accumulated"]),
                        requires_traffic_block=row.get("requires_traffic_block", "True").lower() == "true",
                        requires_st_disconnection=row.get("requires_st_disconnection", "True").lower() == "true",
                        required_gangs=gang,
                        horizon=PriorityHorizon(row.get("horizon", "DAILY")),
                        status=TaskStatus(row.get("status", "PENDING"))
                    ))

        # 3. TDMS Tasks
        tdms_path = os.path.join(self.data_dir, "tdms_jobs_real.csv")
        if os.path.exists(tdms_path):
            with open(tdms_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mach = [m.strip() for m in row["required_machines"].split(",") if m.strip()] if row.get("required_machines") else []
                    gang = [g.strip() for g in row["required_gangs"].split(",") if g.strip()] if row.get("required_gangs") else []

                    tasks.append(MaintenanceTask(
                        task_id=row["task_id"],
                        department=Department.TDMS,
                        task_name=row["task_name"],
                        task_category=row["task_category"],
                        section_id=row["section_id"],
                        track_line=row["track_line"],
                        start_km=float(row["start_km"]),
                        end_km=float(row["end_km"]),
                        station_code=row.get("station_code"),
                        required_duration_mins=int(row["required_duration_mins"]),
                        safety_criticality=float(row["safety_criticality"]),
                        asset_degradation_score=float(row["asset_degradation_score"]),
                        urgency_days_overdue=int(row["urgency_days_overdue"]),
                        gmt_accumulated=float(row["gmt_accumulated"]),
                        requires_traffic_block=row.get("requires_traffic_block", "True").lower() == "true",
                        requires_power_block=row.get("requires_power_block", "True").lower() == "true",
                        required_machines=mach,
                        required_gangs=gang,
                        required_power_cut_substation=row.get("required_power_cut_substation"),
                        horizon=PriorityHorizon(row.get("horizon", "DAILY")),
                        status=TaskStatus(row.get("status", "PENDING"))
                    ))

        return tasks

    def download_kaggle_dataset(self, dataset_slug: str) -> Dict[str, Any]:
        """Attempts to download a dataset from Kaggle via kaggle API."""
        try:
            import kaggle
            kaggle.api.authenticate()
            target_dir = os.path.join(self.data_dir, "downloads", dataset_slug.replace("/", "_"))
            os.makedirs(target_dir, exist_ok=True)
            kaggle.api.dataset_download_files(dataset_slug, path=target_dir, unzip=True)
            return {
                "status": "success",
                "message": f"Successfully downloaded Kaggle dataset: {dataset_slug}",
                "path": target_dir,
                "files": os.listdir(target_dir)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Kaggle API notice: {str(e)}. (Ensure ~/.kaggle/kaggle.json exists or upload CSV files directly)",
                "fallback_available": True
            }

    def get_dataset_summary(self) -> Dict[str, Any]:
        """Returns statistics on the real Kaggle Indian Railways dataset."""
        stations = self.load_real_stations()
        tasks = self.load_real_maintenance_tasks()
        sections = self.build_track_sections_from_stations(stations)
        trains = self.load_real_trains(sections)

        return {
            "dataset_name": "Indian Railways Golden Trunk Corridor (Kaggle Edition)",
            "corridor_length_km": stations[-1]["km"] if stations else 0.0,
            "total_stations": len(stations),
            "total_track_sections": len(sections),
            "total_trains": len(trains),
            "passenger_trains": sum(1 for t in trains if not t.is_freight_forecast),
            "freight_trains": sum(1 for t in trains if t.is_freight_forecast),
            "total_maintenance_demands": len(tasks),
            "tms_demands": sum(1 for t in tasks if t.department == Department.TMS),
            "smms_demands": sum(1 for t in tasks if t.department == Department.SMMS),
            "tdms_demands": sum(1 for t in tasks if t.department == Department.TDMS),
            "files_present": [
                f for f in ["stations.csv", "trains.csv", "schedules.csv", "tms_defects_real.csv", "smms_faults_real.csv", "tdms_jobs_real.csv"]
                if os.path.exists(os.path.join(self.data_dir, f))
            ]
        }
