"""
RailBlock AI - SQLite persistence layer.

CSV files are treated as import/seed sources only. The running application reads its
station, section, train, occupancy, and maintenance data from SQLite.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import (
    Department,
    MaintenanceTask,
    PriorityHorizon,
    TaskStatus,
    TrackSection,
    TrainSchedule,
    TrainType,
)


class RailBlockDatabase:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # RAILBLOCK_DB_PATH lets hosted deployments place SQLite on a
            # persistent disk (for example /var/data/railblock.db on Render).
            # If it is not set, local development continues to use data/railblock.db.
            env_db_path = os.environ.get("RAILBLOCK_DB_PATH", "").strip()
            if env_db_path:
                db_path = os.path.abspath(env_db_path)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                db_path = os.path.join(base_dir, "data", "railblock.db")
        self.db_path = db_path
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS stations (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    km REAL NOT NULL,
                    division TEXT,
                    zone TEXT,
                    state TEXT,
                    has_yard INTEGER NOT NULL DEFAULT 0,
                    platforms INTEGER NOT NULL DEFAULT 2
                );

                CREATE TABLE IF NOT EXISTS track_sections (
                    section_id TEXT PRIMARY KEY,
                    corridor_name TEXT NOT NULL,
                    start_station TEXT NOT NULL,
                    end_station TEXT NOT NULL,
                    line_type TEXT NOT NULL,
                    start_km REAL NOT NULL,
                    end_km REAL NOT NULL,
                    max_speed_kmh INTEGER NOT NULL DEFAULT 130,
                    current_tsr_kmh INTEGER,
                    is_electrified INTEGER NOT NULL DEFAULT 1,
                    signaling_system TEXT NOT NULL DEFAULT 'AUTOMATIC_BLOCK',
                    daily_train_density INTEGER NOT NULL DEFAULT 110,
                    line_capacity_pct REAL NOT NULL DEFAULT 125.0,
                    substations_json TEXT NOT NULL DEFAULT '[]',
                    FOREIGN KEY(start_station) REFERENCES stations(code),
                    FOREIGN KEY(end_station) REFERENCES stations(code)
                );

                CREATE TABLE IF NOT EXISTS trains (
                    train_no TEXT PRIMARY KEY,
                    train_name TEXT NOT NULL,
                    train_type TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    priority_rank INTEGER NOT NULL,
                    can_divert_to_loop INTEGER NOT NULL DEFAULT 0,
                    max_tolerable_delay_mins INTEGER NOT NULL DEFAULT 15,
                    is_freight_forecast INTEGER NOT NULL DEFAULT 0,
                    freight_commodity TEXT
                );

                CREATE TABLE IF NOT EXISTS train_section_occupancies (
                    occupancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    train_no TEXT NOT NULL,
                    section_id TEXT NOT NULL,
                    entry_min INTEGER NOT NULL,
                    exit_min INTEGER NOT NULL,
                    FOREIGN KEY(train_no) REFERENCES trains(train_no) ON DELETE CASCADE,
                    FOREIGN KEY(section_id) REFERENCES track_sections(section_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_occupancy_section_time
                    ON train_section_occupancies(section_id, entry_min, exit_min);

                CREATE TABLE IF NOT EXISTS maintenance_tasks (
                    task_id TEXT PRIMARY KEY,
                    department TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    task_category TEXT NOT NULL,
                    section_id TEXT NOT NULL,
                    track_line TEXT NOT NULL,
                    start_km REAL NOT NULL,
                    end_km REAL NOT NULL,
                    station_code TEXT,
                    required_duration_mins INTEGER NOT NULL DEFAULT 120,
                    min_duration_mins INTEGER NOT NULL DEFAULT 60,
                    safety_criticality REAL NOT NULL DEFAULT 5.0,
                    asset_degradation_score REAL NOT NULL DEFAULT 5.0,
                    urgency_days_overdue INTEGER NOT NULL DEFAULT 0,
                    gmt_accumulated REAL NOT NULL DEFAULT 40.0,
                    speed_restriction_if_deferred_kmh INTEGER,
                    requires_traffic_block INTEGER NOT NULL DEFAULT 1,
                    requires_power_block INTEGER NOT NULL DEFAULT 0,
                    requires_st_disconnection INTEGER NOT NULL DEFAULT 0,
                    is_shadow_eligible INTEGER NOT NULL DEFAULT 1,
                    required_power_cut_substation TEXT,
                    submission_date TEXT NOT NULL DEFAULT '',
                    target_completion_date TEXT NOT NULL DEFAULT '',
                    horizon TEXT NOT NULL DEFAULT 'DAILY',
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    computed_ai_priority REAL NOT NULL DEFAULT 0.0,
                    risk_rank INTEGER NOT NULL DEFAULT 0,
                    shadow_cluster_id TEXT,
                    scheduled_start TEXT,
                    scheduled_end TEXT,
                    FOREIGN KEY(section_id) REFERENCES track_sections(section_id),
                    FOREIGN KEY(station_code) REFERENCES stations(code)
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_station ON maintenance_tasks(station_code);
                CREATE INDEX IF NOT EXISTS idx_tasks_section ON maintenance_tasks(section_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_priority ON maintenance_tasks(computed_ai_priority DESC);

                CREATE TABLE IF NOT EXISTS task_machines (
                    task_id TEXT NOT NULL,
                    machine_id TEXT NOT NULL,
                    PRIMARY KEY(task_id, machine_id),
                    FOREIGN KEY(task_id) REFERENCES maintenance_tasks(task_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_gangs (
                    task_id TEXT NOT NULL,
                    gang_id TEXT NOT NULL,
                    PRIMARY KEY(task_id, gang_id),
                    FOREIGN KEY(task_id) REFERENCES maintenance_tasks(task_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS maintenance_requests (
                    request_id TEXT PRIMARY KEY,
                    engineer_name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    station_code TEXT NOT NULL,
                    section_id TEXT NOT NULL,
                    track_line TEXT NOT NULL,
                    start_km REAL NOT NULL,
                    end_km REAL NOT NULL,
                    task_name TEXT NOT NULL,
                    task_category TEXT NOT NULL DEFAULT 'FIELD_REPORTED',
                    required_duration_mins INTEGER NOT NULL DEFAULT 120,
                    min_duration_mins INTEGER NOT NULL DEFAULT 60,
                    safety_criticality REAL NOT NULL DEFAULT 5.0,
                    asset_degradation_score REAL NOT NULL DEFAULT 5.0,
                    urgency_days_overdue INTEGER NOT NULL DEFAULT 0,
                    gmt_accumulated REAL NOT NULL DEFAULT 40.0,
                    speed_restriction_if_deferred_kmh INTEGER,
                    requires_traffic_block INTEGER NOT NULL DEFAULT 1,
                    requires_power_block INTEGER NOT NULL DEFAULT 0,
                    requires_st_disconnection INTEGER NOT NULL DEFAULT 0,
                    is_shadow_eligible INTEGER NOT NULL DEFAULT 1,
                    required_machines_json TEXT NOT NULL DEFAULT '[]',
                    required_gangs_json TEXT NOT NULL DEFAULT '[]',
                    required_power_cut_substation TEXT,
                    horizon TEXT NOT NULL DEFAULT 'DAILY',
                    request_status TEXT NOT NULL DEFAULT 'SUBMITTED',
                    ai_priority REAL NOT NULL DEFAULT 0.0,
                    ai_classification TEXT NOT NULL DEFAULT '',
                    ai_components_json TEXT NOT NULL DEFAULT '{}',
                    submitted_at TEXT NOT NULL,
                    decided_by TEXT,
                    decided_at TEXT,
                    officer_note TEXT NOT NULL DEFAULT '',
                    officer_instruction TEXT NOT NULL DEFAULT '',
                    converted_task_id TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_requests_department_status
                    ON maintenance_requests(department, request_status);
                CREATE INDEX IF NOT EXISTS idx_requests_station
                    ON maintenance_requests(station_code);
                CREATE INDEX IF NOT EXISTS idx_requests_priority
                    ON maintenance_requests(ai_priority DESC);

                CREATE TABLE IF NOT EXISTS request_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_name TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(request_id) REFERENCES maintenance_requests(request_id) ON DELETE CASCADE
                );
                """
            )

    def has_seed_data(self) -> bool:
        self.initialize_schema()
        with self.connect() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM stations").fetchone()["c"]
            return int(count) > 0

    def replace_dataset(
        self,
        stations: List[Dict[str, Any]],
        sections: List[TrackSection],
        tasks: List[MaintenanceTask],
        trains: List[TrainSchedule],
        source_name: str,
    ) -> None:
        """Replace the working dataset in a single transaction."""
        self.initialize_schema()
        with self.connect() as conn:
            conn.execute("DELETE FROM task_machines")
            conn.execute("DELETE FROM task_gangs")
            conn.execute("DELETE FROM maintenance_tasks")
            conn.execute("DELETE FROM train_section_occupancies")
            conn.execute("DELETE FROM trains")
            conn.execute("DELETE FROM track_sections")
            conn.execute("DELETE FROM stations")

            conn.executemany(
                """
                INSERT INTO stations(code, name, km, division, zone, state, has_yard, platforms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        st["code"], st["name"], float(st.get("km", 0.0)),
                        st.get("division", ""), st.get("zone", ""), st.get("state", ""),
                        int(bool(st.get("has_yard", False))), int(st.get("platforms", 2)),
                    )
                    for st in stations
                ],
            )

            conn.executemany(
                """
                INSERT INTO track_sections(
                    section_id, corridor_name, start_station, end_station, line_type,
                    start_km, end_km, max_speed_kmh, current_tsr_kmh, is_electrified,
                    signaling_system, daily_train_density, line_capacity_pct, substations_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        s.section_id, s.corridor_name, s.start_station, s.end_station, s.line_type,
                        s.start_km, s.end_km, s.max_speed_kmh, s.current_tsr_kmh,
                        int(bool(s.is_electrified)), s.signaling_system, s.daily_train_density,
                        s.line_capacity_pct, json.dumps(s.substations),
                    )
                    for s in sections
                ],
            )

            conn.executemany(
                """
                INSERT INTO trains(
                    train_no, train_name, train_type, direction, origin, destination,
                    priority_rank, can_divert_to_loop, max_tolerable_delay_mins,
                    is_freight_forecast, freight_commodity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        t.train_no, t.train_name, t.train_type.value, t.direction, t.origin,
                        t.destination, t.priority_rank, int(bool(t.can_divert_to_loop)),
                        t.max_tolerable_delay_mins, int(bool(t.is_freight_forecast)),
                        t.freight_commodity,
                    )
                    for t in trains
                ],
            )

            occ_rows = []
            for t in trains:
                for occ in t.section_occupancies:
                    occ_rows.append(
                        (t.train_no, occ["section_id"], int(occ["entry_min"]), int(occ["exit_min"]))
                    )
            conn.executemany(
                """
                INSERT INTO train_section_occupancies(train_no, section_id, entry_min, exit_min)
                VALUES (?, ?, ?, ?)
                """,
                occ_rows,
            )

            task_rows = []
            machine_rows = []
            gang_rows = []
            for t in tasks:
                task_rows.append(
                    (
                        t.task_id, t.department.value, t.task_name, t.task_category, t.section_id,
                        t.track_line, t.start_km, t.end_km, t.station_code,
                        t.required_duration_mins, t.min_duration_mins, t.safety_criticality,
                        t.asset_degradation_score, t.urgency_days_overdue, t.gmt_accumulated,
                        t.speed_restriction_if_deferred_kmh, int(bool(t.requires_traffic_block)),
                        int(bool(t.requires_power_block)), int(bool(t.requires_st_disconnection)),
                        int(bool(t.is_shadow_eligible)), t.required_power_cut_substation,
                        t.submission_date, t.target_completion_date, t.horizon.value, t.status.value,
                        t.computed_ai_priority, t.risk_rank, t.shadow_cluster_id,
                        t.scheduled_start, t.scheduled_end,
                    )
                )
                machine_rows.extend((t.task_id, m) for m in t.required_machines)
                gang_rows.extend((t.task_id, g) for g in t.required_gangs)

            conn.executemany(
                """
                INSERT INTO maintenance_tasks(
                    task_id, department, task_name, task_category, section_id, track_line,
                    start_km, end_km, station_code, required_duration_mins, min_duration_mins,
                    safety_criticality, asset_degradation_score, urgency_days_overdue,
                    gmt_accumulated, speed_restriction_if_deferred_kmh,
                    requires_traffic_block, requires_power_block, requires_st_disconnection,
                    is_shadow_eligible, required_power_cut_substation, submission_date,
                    target_completion_date, horizon, status, computed_ai_priority, risk_rank,
                    shadow_cluster_id, scheduled_start, scheduled_end
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                task_rows,
            )
            conn.executemany("INSERT INTO task_machines(task_id, machine_id) VALUES (?, ?)", machine_rows)
            conn.executemany("INSERT INTO task_gangs(task_id, gang_id) VALUES (?, ?)", gang_rows)

            conn.execute(
                "INSERT INTO metadata(key, value) VALUES ('active_source', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (source_name,),
            )

    def get_active_source(self) -> str:
        self.initialize_schema()
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key='active_source'").fetchone()
            return row["value"] if row else "SQLITE"

    def load_stations(self) -> List[Dict[str, Any]]:
        self.initialize_schema()
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM stations ORDER BY km, code").fetchall()
        return [
            {
                "code": r["code"],
                "name": r["name"],
                "km": float(r["km"]),
                "division": r["division"] or "",
                "zone": r["zone"] or "",
                "state": r["state"] or "",
                "has_yard": bool(r["has_yard"]),
                "platforms": int(r["platforms"]),
            }
            for r in rows
        ]

    def load_sections(self) -> List[TrackSection]:
        self.initialize_schema()
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM track_sections ORDER BY start_km, line_type").fetchall()
        return [
            TrackSection(
                section_id=r["section_id"],
                corridor_name=r["corridor_name"],
                start_station=r["start_station"],
                end_station=r["end_station"],
                line_type=r["line_type"],
                start_km=float(r["start_km"]),
                end_km=float(r["end_km"]),
                max_speed_kmh=int(r["max_speed_kmh"]),
                current_tsr_kmh=r["current_tsr_kmh"],
                is_electrified=bool(r["is_electrified"]),
                signaling_system=r["signaling_system"],
                daily_train_density=int(r["daily_train_density"]),
                line_capacity_pct=float(r["line_capacity_pct"]),
                substations=json.loads(r["substations_json"] or "[]"),
            )
            for r in rows
        ]

    def load_trains(self) -> List[TrainSchedule]:
        self.initialize_schema()
        with self.connect() as conn:
            train_rows = conn.execute("SELECT * FROM trains ORDER BY priority_rank, train_no").fetchall()
            occ_rows = conn.execute(
                "SELECT train_no, section_id, entry_min, exit_min "
                "FROM train_section_occupancies ORDER BY train_no, entry_min"
            ).fetchall()

        occ_map: Dict[str, List[Dict[str, Any]]] = {}
        for r in occ_rows:
            occ_map.setdefault(r["train_no"], []).append(
                {
                    "section_id": r["section_id"],
                    "entry_min": int(r["entry_min"]),
                    "exit_min": int(r["exit_min"]),
                }
            )

        return [
            TrainSchedule(
                train_no=r["train_no"],
                train_name=r["train_name"],
                train_type=TrainType(r["train_type"]),
                direction=r["direction"],
                origin=r["origin"],
                destination=r["destination"],
                priority_rank=int(r["priority_rank"]),
                section_occupancies=occ_map.get(r["train_no"], []),
                can_divert_to_loop=bool(r["can_divert_to_loop"]),
                max_tolerable_delay_mins=int(r["max_tolerable_delay_mins"]),
                is_freight_forecast=bool(r["is_freight_forecast"]),
                freight_commodity=r["freight_commodity"],
            )
            for r in train_rows
        ]

    def load_tasks(self) -> List[MaintenanceTask]:
        self.initialize_schema()
        with self.connect() as conn:
            task_rows = conn.execute("SELECT * FROM maintenance_tasks ORDER BY task_id").fetchall()
            machine_rows = conn.execute("SELECT task_id, machine_id FROM task_machines ORDER BY machine_id").fetchall()
            gang_rows = conn.execute("SELECT task_id, gang_id FROM task_gangs ORDER BY gang_id").fetchall()

        machines: Dict[str, List[str]] = {}
        for r in machine_rows:
            machines.setdefault(r["task_id"], []).append(r["machine_id"])
        gangs: Dict[str, List[str]] = {}
        for r in gang_rows:
            gangs.setdefault(r["task_id"], []).append(r["gang_id"])

        return [
            MaintenanceTask(
                task_id=r["task_id"],
                department=Department(r["department"]),
                task_name=r["task_name"],
                task_category=r["task_category"],
                section_id=r["section_id"],
                track_line=r["track_line"],
                start_km=float(r["start_km"]),
                end_km=float(r["end_km"]),
                station_code=r["station_code"],
                required_duration_mins=int(r["required_duration_mins"]),
                min_duration_mins=int(r["min_duration_mins"]),
                safety_criticality=float(r["safety_criticality"]),
                asset_degradation_score=float(r["asset_degradation_score"]),
                urgency_days_overdue=int(r["urgency_days_overdue"]),
                gmt_accumulated=float(r["gmt_accumulated"]),
                speed_restriction_if_deferred_kmh=r["speed_restriction_if_deferred_kmh"],
                requires_traffic_block=bool(r["requires_traffic_block"]),
                requires_power_block=bool(r["requires_power_block"]),
                requires_st_disconnection=bool(r["requires_st_disconnection"]),
                is_shadow_eligible=bool(r["is_shadow_eligible"]),
                required_machines=machines.get(r["task_id"], []),
                required_gangs=gangs.get(r["task_id"], []),
                required_power_cut_substation=r["required_power_cut_substation"],
                submission_date=r["submission_date"] or "",
                target_completion_date=r["target_completion_date"] or "",
                horizon=PriorityHorizon(r["horizon"]),
                status=TaskStatus(r["status"]),
                computed_ai_priority=float(r["computed_ai_priority"]),
                risk_rank=int(r["risk_rank"]),
                shadow_cluster_id=r["shadow_cluster_id"],
                scheduled_start=r["scheduled_start"],
                scheduled_end=r["scheduled_end"],
            )
            for r in task_rows
        ]

    def update_task_computed_state(self, tasks: Iterable[MaintenanceTask]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                UPDATE maintenance_tasks
                SET computed_ai_priority=?, risk_rank=?, shadow_cluster_id=?,
                    scheduled_start=?, scheduled_end=?, status=?
                WHERE task_id=?
                """,
                [
                    (
                        t.computed_ai_priority, t.risk_rank, t.shadow_cluster_id,
                        t.scheduled_start, t.scheduled_end, t.status.value, t.task_id,
                    )
                    for t in tasks
                ],
            )


    def _request_row_to_dict(self, r: sqlite3.Row) -> Dict[str, Any]:
        d = dict(r)
        d["requires_traffic_block"] = bool(d.get("requires_traffic_block"))
        d["requires_power_block"] = bool(d.get("requires_power_block"))
        d["requires_st_disconnection"] = bool(d.get("requires_st_disconnection"))
        d["is_shadow_eligible"] = bool(d.get("is_shadow_eligible"))
        d["required_machines"] = json.loads(d.pop("required_machines_json", "[]") or "[]")
        d["required_gangs"] = json.loads(d.pop("required_gangs_json", "[]") or "[]")
        d["ai_components"] = json.loads(d.pop("ai_components_json", "{}") or "{}")
        return d

    def create_maintenance_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist a field request before it becomes an operational maintenance task."""
        self.initialize_schema()
        dept = str(payload["department"]).upper()
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            prefix = f"REQ-{dept}-"
            rows = conn.execute(
                "SELECT request_id FROM maintenance_requests WHERE request_id LIKE ?",
                (prefix + "%",),
            ).fetchall()
            max_n = 0
            for row in rows:
                try:
                    max_n = max(max_n, int(str(row["request_id"]).split("-")[-1]))
                except (ValueError, TypeError):
                    pass
            request_id = f"{prefix}{max_n + 1:04d}"
            conn.execute(
                """
                INSERT INTO maintenance_requests(
                    request_id, engineer_name, department, station_code, section_id, track_line,
                    start_km, end_km, task_name, task_category, required_duration_mins,
                    min_duration_mins, safety_criticality, asset_degradation_score,
                    urgency_days_overdue, gmt_accumulated, speed_restriction_if_deferred_kmh,
                    requires_traffic_block, requires_power_block, requires_st_disconnection,
                    is_shadow_eligible, required_machines_json, required_gangs_json,
                    required_power_cut_substation, horizon, request_status, ai_priority,
                    ai_classification, ai_components_json, submitted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          'SUBMITTED', ?, ?, ?, ?)
                """,
                (
                    request_id, payload["engineer_name"], dept, payload["station_code"],
                    payload["section_id"], payload.get("track_line", "UP"),
                    float(payload.get("start_km", 0.0)), float(payload.get("end_km", payload.get("start_km", 0.0))),
                    payload["task_name"], payload.get("task_category", "FIELD_REPORTED"),
                    int(payload.get("required_duration_mins", 120)), int(payload.get("min_duration_mins", 60)),
                    float(payload.get("safety_criticality", 5.0)), float(payload.get("asset_degradation_score", 5.0)),
                    int(payload.get("urgency_days_overdue", 0)), float(payload.get("gmt_accumulated", 40.0)),
                    payload.get("speed_restriction_if_deferred_kmh"),
                    int(bool(payload.get("requires_traffic_block", True))),
                    int(bool(payload.get("requires_power_block", False))),
                    int(bool(payload.get("requires_st_disconnection", False))),
                    int(bool(payload.get("is_shadow_eligible", True))),
                    json.dumps(payload.get("required_machines", [])), json.dumps(payload.get("required_gangs", [])),
                    payload.get("required_power_cut_substation"), payload.get("horizon", "DAILY"),
                    float(payload.get("ai_priority", 0.0)), payload.get("ai_classification", ""),
                    json.dumps(payload.get("ai_components", {})), now,
                ),
            )
            conn.execute(
                "INSERT INTO request_events(request_id, event_type, actor_name, detail, created_at) VALUES (?, ?, ?, ?, ?)",
                (request_id, "SUBMITTED", payload["engineer_name"], "Engineer submitted maintenance request", now),
            )
        return self.get_maintenance_request(request_id)

    def list_maintenance_requests(
        self, department: Optional[str] = None, status: Optional[str] = None, engineer_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        self.initialize_schema()
        clauses, params = [], []
        if department and department.upper() != "ALL":
            clauses.append("department=?")
            params.append(department.upper())
        if status and status.upper() != "ALL":
            clauses.append("request_status=?")
            params.append(status.upper())
        if engineer_name:
            clauses.append("LOWER(engineer_name)=LOWER(?)")
            params.append(engineer_name)
        sql = "SELECT * FROM maintenance_requests"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY CASE request_status WHEN 'SUBMITTED' THEN 0 WHEN 'UNDER_REVIEW' THEN 1 WHEN 'APPROVED' THEN 2 ELSE 3 END, ai_priority DESC, submitted_at DESC"
        with self.connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [self._request_row_to_dict(r) for r in rows]

    def get_maintenance_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        self.initialize_schema()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM maintenance_requests WHERE request_id=?", (request_id,)).fetchone()
        return self._request_row_to_dict(row) if row else None

    def update_request_analysis(self, request_id: str, ai_priority: float, classification: str, components: Dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE maintenance_requests SET ai_priority=?, ai_classification=?, ai_components_json=?, request_status=CASE WHEN request_status='SUBMITTED' THEN 'UNDER_REVIEW' ELSE request_status END WHERE request_id=?",
                (float(ai_priority), classification, json.dumps(components), request_id),
            )

    def decide_maintenance_request(
        self, request_id: str, decision: str, officer_name: str, note: str = "", instruction: str = "", converted_task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        decision = decision.upper()
        if decision not in {"APPROVED", "REJECTED"}:
            raise ValueError("decision must be APPROVED or REJECTED")
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """UPDATE maintenance_requests
                   SET request_status=?, decided_by=?, decided_at=?, officer_note=?, officer_instruction=?, converted_task_id=?
                   WHERE request_id=?""",
                (decision, officer_name, now, note or "", instruction or "", converted_task_id, request_id),
            )
            conn.execute(
                "INSERT INTO request_events(request_id, event_type, actor_name, detail, created_at) VALUES (?, ?, ?, ?, ?)",
                (request_id, decision, officer_name, instruction or note or decision, now),
            )
        result = self.get_maintenance_request(request_id)
        if not result:
            raise KeyError(request_id)
        return result

    def mark_request_completed(self, request_id: str, engineer_name: str, detail: str = "") -> Dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            row = conn.execute("SELECT request_status FROM maintenance_requests WHERE request_id=?", (request_id,)).fetchone()
            if not row:
                raise KeyError(request_id)
            if row["request_status"] != "APPROVED":
                raise ValueError("Only approved requests can be completed")
            conn.execute("UPDATE maintenance_requests SET request_status='COMPLETED' WHERE request_id=?", (request_id,))
            conn.execute(
                "INSERT INTO request_events(request_id, event_type, actor_name, detail, created_at) VALUES (?, 'COMPLETED', ?, ?, ?)",
                (request_id, engineer_name, detail or "Engineer marked work completed", now),
            )
        result = self.get_maintenance_request(request_id)
        if not result:
            raise KeyError(request_id)
        return result

    def insert_maintenance_task(self, task: MaintenanceTask) -> None:
        """Insert one officer-approved request into the operational maintenance task table."""
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO maintenance_tasks(
                    task_id, department, task_name, task_category, section_id, track_line, start_km, end_km,
                    station_code, required_duration_mins, min_duration_mins, safety_criticality,
                    asset_degradation_score, urgency_days_overdue, gmt_accumulated,
                    speed_restriction_if_deferred_kmh, requires_traffic_block, requires_power_block,
                    requires_st_disconnection, is_shadow_eligible, required_power_cut_substation,
                    submission_date, target_completion_date, horizon, status, computed_ai_priority, risk_rank,
                    shadow_cluster_id, scheduled_start, scheduled_end
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id, task.department.value, task.task_name, task.task_category, task.section_id,
                    task.track_line, task.start_km, task.end_km, task.station_code, task.required_duration_mins,
                    task.min_duration_mins, task.safety_criticality, task.asset_degradation_score,
                    task.urgency_days_overdue, task.gmt_accumulated, task.speed_restriction_if_deferred_kmh,
                    int(task.requires_traffic_block), int(task.requires_power_block), int(task.requires_st_disconnection),
                    int(task.is_shadow_eligible), task.required_power_cut_substation, task.submission_date,
                    task.target_completion_date, task.horizon.value, task.status.value, task.computed_ai_priority,
                    task.risk_rank, task.shadow_cluster_id, task.scheduled_start, task.scheduled_end,
                ),
            )
            conn.executemany("INSERT OR IGNORE INTO task_machines(task_id, machine_id) VALUES (?, ?)", [(task.task_id, x) for x in task.required_machines])
            conn.executemany("INSERT OR IGNORE INTO task_gangs(task_id, gang_id) VALUES (?, ?)", [(task.task_id, x) for x in task.required_gangs])

    def get_request_counts(self) -> Dict[str, int]:
        self.initialize_schema()
        with self.connect() as conn:
            total = int(conn.execute("SELECT COUNT(*) c FROM maintenance_requests").fetchone()["c"])
            rows = conn.execute("SELECT request_status, COUNT(*) c FROM maintenance_requests GROUP BY request_status").fetchall()
        result = {"total": total, "submitted": 0, "under_review": 0, "approved": 0, "rejected": 0, "completed": 0}
        for r in rows:
            result[str(r["request_status"]).lower()] = int(r["c"])
        return result

    def get_counts(self) -> Dict[str, int]:
        self.initialize_schema()
        with self.connect() as conn:
            return {
                "stations": int(conn.execute("SELECT COUNT(*) c FROM stations").fetchone()["c"]),
                "sections": int(conn.execute("SELECT COUNT(*) c FROM track_sections").fetchone()["c"]),
                "trains": int(conn.execute("SELECT COUNT(*) c FROM trains").fetchone()["c"]),
                "occupancies": int(conn.execute("SELECT COUNT(*) c FROM train_section_occupancies").fetchone()["c"]),
                "maintenance_tasks": int(conn.execute("SELECT COUNT(*) c FROM maintenance_tasks").fetchone()["c"]),
            }
