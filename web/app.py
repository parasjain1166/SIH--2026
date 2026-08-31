"""
RailBlock AI - Web Application & REST API Server
Provides high-performance endpoints for the interactive operations cockpit,
GIS Track Schematic, Multi-Horizon Gantt charts, What-If Simulation, and Memo Generation.
"""

import os
from flask import Flask, render_template, jsonify, request, send_from_directory

from core.models import PriorityHorizon, Department, BlockType, MaintenanceTask, TaskStatus
from core.data_generator import (
    STATIONS, generate_track_sections, generate_maintenance_tasks,
    generate_train_timetable, compute_corridor_availability_windows
)
from core.kaggle_importer import KaggleDataImporter
from core.database import RailBlockDatabase
from core.ai_prioritizer import AIPrioritizer
from core.shadow_block_detector import ShadowBlockDetector
from core.optimizer import BlockOptimizer
from core.multi_horizon_planner import MultiHorizonPlanner
from core.kpi_engine import KPIEngine
from core.whatif_simulator import WhatIfSimulator
from core.report_generator import ReportGenerator

# Initialize Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")

# Persistent SQLite State & Engine Instances
kaggle_importer = KaggleDataImporter()
database = RailBlockDatabase()
database.initialize_schema()

# CSV/generator data is used only to seed SQLite. The running application then reads
# its operational data back from the database.
if not database.has_seed_data():
    try:
        seed_stations = kaggle_importer.load_real_stations()
        if seed_stations:
            seed_sections = kaggle_importer.build_track_sections_from_stations(seed_stations)
            seed_tasks = kaggle_importer.load_real_maintenance_tasks()
            seed_trains = kaggle_importer.load_real_trains(seed_sections)
            database.replace_dataset(seed_stations, seed_sections, seed_tasks, seed_trains, "KAGGLE_REAL")
        else:
            seed_sections = generate_track_sections()
            seed_tasks = generate_maintenance_tasks(seed_sections, seed=42)
            seed_trains = generate_train_timetable(seed_sections)
            seed_stations = [dict(st, division="Demo HDN", zone="NR", state="Demo") for st in STATIONS]
            database.replace_dataset(seed_stations, seed_sections, seed_tasks, seed_trains, "DEFAULT_HDN")
    except Exception:
        seed_sections = generate_track_sections()
        seed_tasks = generate_maintenance_tasks(seed_sections, seed=42)
        seed_trains = generate_train_timetable(seed_sections)
        seed_stations = [dict(st, division="Demo HDN", zone="NR", state="Demo") for st in STATIONS]
        database.replace_dataset(seed_stations, seed_sections, seed_tasks, seed_trains, "DEFAULT_HDN")

active_data_source = database.get_active_source()
station_catalog = database.load_stations()
sections = database.load_sections()
tasks = database.load_tasks()
trains = database.load_trains()
windows = compute_corridor_availability_windows(sections, trains)

prioritizer = AIPrioritizer()
prioritizer.prioritize_all_tasks(tasks, sections)

detector = ShadowBlockDetector(max_km_separation=6.0)
optimizer = BlockOptimizer()
planner = MultiHorizonPlanner(detector, optimizer)
simulator = WhatIfSimulator(sections, tasks, trains, prioritizer, detector, optimizer)

# Pre-generate Multi-Horizon Plans
plans_cache = planner.generate_all_horizons(tasks, sections, trains, windows, base_date="2026-08-30")
database.update_task_computed_state(tasks)
daily_blocks_list = [b for b in plans_cache["daily_plan"]["blocks"]]


@app.route("/")
def role_select():
    return render_template("role_select.html")


@app.route("/engineer")
def engineer_portal():
    return render_template("engineer.html")


@app.route("/officer")
def officer_portal():
    return render_template("index.html")


def _mins_to_clock(total_mins: int) -> str:
    day = int(total_mins) // 1440
    mins = int(total_mins) % 1440
    hh, mm = divmod(mins, 60)
    suffix = f" (+{day}d)" if day else ""
    return f"{hh:02d}:{mm:02d}{suffix}"


def _resolve_station(query: str):
    q = (query or "").strip().lower()
    if not q:
        return None
    for st in station_catalog:
        if st.get("code", "").lower() == q or st.get("name", "").lower() == q:
            return st
    for st in station_catalog:
        if st.get("code", "").lower().startswith(q) or st.get("name", "").lower().startswith(q):
            return st
    for st in station_catalog:
        if q in st.get("code", "").lower() or q in st.get("name", "").lower():
            return st
    return None


def _station_section_ids(station_code: str):
    return {
        s.section_id for s in sections
        if s.start_station == station_code or s.end_station == station_code
    }


def _refresh_operational_state():
    """Reload approved operational tasks from SQLite and rebuild optimizer state."""
    global tasks, windows, plans_cache, simulator, planner, daily_blocks_list
    tasks = database.load_tasks()
    prioritizer.prioritize_all_tasks(tasks, sections)
    windows = compute_corridor_availability_windows(sections, trains)
    planner = MultiHorizonPlanner(detector, optimizer)
    simulator = WhatIfSimulator(sections, tasks, trains, prioritizer, detector, optimizer)
    plans_cache = planner.generate_all_horizons(tasks, sections, trains, windows, base_date="2026-08-30")
    database.update_task_computed_state(tasks)
    daily_blocks_list = [b for b in plans_cache["daily_plan"]["blocks"]]


def _request_dict_to_task(req):
    return MaintenanceTask(
        task_id=req["request_id"],
        department=Department(req["department"]),
        task_name=req["task_name"],
        task_category=req.get("task_category") or "FIELD_REPORTED",
        section_id=req["section_id"],
        track_line=req.get("track_line") or "UP",
        start_km=float(req.get("start_km", 0.0)),
        end_km=float(req.get("end_km", req.get("start_km", 0.0))),
        station_code=req.get("station_code"),
        required_duration_mins=int(req.get("required_duration_mins", 120)),
        min_duration_mins=int(req.get("min_duration_mins", 60)),
        safety_criticality=float(req.get("safety_criticality", 5.0)),
        asset_degradation_score=float(req.get("asset_degradation_score", 5.0)),
        urgency_days_overdue=int(req.get("urgency_days_overdue", 0)),
        gmt_accumulated=float(req.get("gmt_accumulated", 40.0)),
        speed_restriction_if_deferred_kmh=req.get("speed_restriction_if_deferred_kmh"),
        requires_traffic_block=bool(req.get("requires_traffic_block", True)),
        requires_power_block=bool(req.get("requires_power_block", False)),
        requires_st_disconnection=bool(req.get("requires_st_disconnection", False)),
        is_shadow_eligible=bool(req.get("is_shadow_eligible", True)),
        required_machines=list(req.get("required_machines", [])),
        required_gangs=list(req.get("required_gangs", [])),
        required_power_cut_substation=req.get("required_power_cut_substation"),
        submission_date=(req.get("submitted_at") or "")[:10],
        horizon=PriorityHorizon(req.get("horizon", "DAILY")),
        status=TaskStatus.PENDING,
        computed_ai_priority=float(req.get("ai_priority", 0.0)),
    )


def _evaluate_request(req):
    section = next((s for s in sections if s.section_id == req["section_id"]), None)
    if not section:
        raise ValueError("Selected track section is not available in the active corridor dataset")
    task = _request_dict_to_task(req)
    result = prioritizer.evaluate_task(task, section)
    return task, section, result


@app.route("/api/portal/summary", methods=["GET"])
def portal_summary():
    return jsonify({
        "database": "SQLite",
        "requests": database.get_request_counts(),
        "operational_tasks": len(tasks),
        "stations": len(station_catalog),
    })


@app.route("/api/station-sections", methods=["GET"])
def station_sections():
    station = _resolve_station(request.args.get("station", ""))
    if not station:
        return jsonify({"error": "Station not found"}), 404
    matches = [s.to_dict() for s in sections if s.start_station == station["code"] or s.end_station == station["code"]]
    return jsonify({"station": station, "sections": matches})


@app.route("/api/engineer/requests", methods=["POST"])
def submit_engineer_request():
    data = request.get_json() or {}
    required = ["engineer_name", "department", "station_code", "section_id", "task_name"]
    missing = [k for k in required if not str(data.get(k, "")).strip()]
    if missing:
        return jsonify({"error": "Missing required fields", "fields": missing}), 400
    dept = str(data["department"]).upper()
    if dept not in {"TMS", "SMMS", "TDMS"}:
        return jsonify({"error": "Department must be TMS, SMMS or TDMS"}), 400
    station = _resolve_station(str(data["station_code"]))
    section = next((s for s in sections if s.section_id == data["section_id"]), None)
    if not station or not section:
        return jsonify({"error": "Station or section not found in active dataset"}), 400
    if station["code"] not in {section.start_station, section.end_station}:
        return jsonify({"error": "Selected section is not adjacent to the selected station"}), 400

    start_km = float(data.get("start_km", station.get("km", section.start_km)))
    end_km = float(data.get("end_km", start_km))
    payload = dict(data)
    payload.update({
        "department": dept,
        "station_code": station["code"],
        "track_line": section.line_type,
        "start_km": start_km,
        "end_km": end_km,
        "task_category": str(data.get("task_category") or data["task_name"]).strip().upper().replace(" ", "_")[:80],
    })
    # Department-specific defaults can be overridden by the engineer form.
    payload.setdefault("requires_traffic_block", True)
    if dept == "SMMS":
        payload.setdefault("requires_st_disconnection", True)
    if dept == "TDMS":
        payload.setdefault("requires_power_block", True)

    # Calculate a first-pass AI score on submission so the officer inbox arrives pre-triaged.
    preview = dict(payload)
    preview["request_id"] = "PREVIEW"
    preview["submitted_at"] = ""
    task, _, ai = _evaluate_request(preview)
    payload["ai_priority"] = ai["composite_score"]
    payload["ai_classification"] = ai["classification"]
    payload["ai_components"] = ai["components"]
    saved = database.create_maintenance_request(payload)
    return jsonify({"status": "submitted", "request": saved, "ai_preview": ai}), 201


@app.route("/api/engineer/requests", methods=["GET"])
def get_engineer_requests():
    dept = request.args.get("department")
    engineer_name = request.args.get("engineer_name")
    rows = database.list_maintenance_requests(department=dept, engineer_name=engineer_name)
    return jsonify({"total_count": len(rows), "requests": rows})


@app.route("/api/engineer/requests/<request_id>/complete", methods=["POST"])
def complete_engineer_request(request_id):
    data = request.get_json() or {}
    engineer_name = str(data.get("engineer_name") or "Engineer").strip()
    try:
        row = database.mark_request_completed(request_id, engineer_name, str(data.get("detail") or ""))
        return jsonify({"status": "completed", "request": row})
    except KeyError:
        return jsonify({"error": "Request not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/officer/requests", methods=["GET"])
def get_officer_requests():
    status = request.args.get("status")
    rows = database.list_maintenance_requests(status=status)
    return jsonify({"total_count": len(rows), "requests": rows, "counts": database.get_request_counts()})


@app.route("/api/officer/requests/<request_id>/analyze", methods=["POST"])
def analyze_officer_request(request_id):
    req = database.get_maintenance_request(request_id)
    if not req:
        return jsonify({"error": "Request not found"}), 404
    try:
        task, section, ai = _evaluate_request(req)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    database.update_request_analysis(request_id, ai["composite_score"], ai["classification"], ai["components"])

    # Timetable and free-window evidence for this exact section.
    train_hits = []
    for tr in trains:
        occs = [o for o in tr.section_occupancies if o["section_id"] == section.section_id]
        for occ in occs:
            train_hits.append({
                "train_no": tr.train_no, "train_name": tr.train_name, "train_type": tr.train_type.value,
                "entry": _mins_to_clock(occ["entry_min"]), "exit": _mins_to_clock(occ["exit_min"]),
                "priority_rank": tr.priority_rank,
            })
    section_windows = [w for w in windows if w.section_id == section.section_id and w.track_line == task.track_line]
    section_windows = sorted(section_windows, key=lambda w: w.duration_mins, reverse=True)

    # Look for pending requests that could form a multi-department shadow cluster.
    pending_rows = [r for r in database.list_maintenance_requests() if r["request_status"] in {"SUBMITTED", "UNDER_REVIEW"}]
    pending_tasks = [_request_dict_to_task(r) for r in pending_rows]
    prioritizer.prioritize_all_tasks(pending_tasks, sections)
    pending_clusters = detector.detect_clusters(pending_tasks) if pending_tasks else []
    matching_cluster = next((c for c in pending_clusters if any(t.task_id == request_id for t in c.tasks)), None)

    return jsonify({
        "request": database.get_maintenance_request(request_id),
        "ai": ai,
        "section": section.to_dict(),
        "timetable": {"trains_checked": len(train_hits), "trains": train_hits[:25]},
        "windows": [
            {**w.to_dict(), "start_time": _mins_to_clock(w.start_time_mins), "end_time": _mins_to_clock(w.end_time_mins)}
            for w in section_windows[:8]
        ],
        "shadow_cluster": matching_cluster.to_dict() if matching_cluster else None,
        "decision_trace": [
            "Engineer field request loaded from SQLite",
            f"AI priority calculated: {ai['composite_score']}/100 ({ai['classification']})",
            f"Timetable checked for {len(train_hits)} train movements on {section.section_id}",
            f"Found {len(section_windows)} qualifying free windows",
            (f"Shadow opportunity detected across {len(matching_cluster.departments)} department(s)" if matching_cluster else "No multi-request shadow opportunity detected yet"),
            "Officer remains the final approving authority",
        ],
    })


@app.route("/api/officer/requests/<request_id>/decision", methods=["POST"])
def decide_officer_request(request_id):
    data = request.get_json() or {}
    decision_raw = str(data.get("decision") or "").upper()
    decision = {"APPROVE": "APPROVED", "APPROVED": "APPROVED", "REJECT": "REJECTED", "REJECTED": "REJECTED"}.get(decision_raw)
    if not decision:
        return jsonify({"error": "decision must be APPROVE or REJECT"}), 400
    officer_name = str(data.get("officer_name") or "Control Officer").strip()
    req = database.get_maintenance_request(request_id)
    if not req:
        return jsonify({"error": "Request not found"}), 404
    if req["request_status"] in {"APPROVED", "REJECTED", "COMPLETED"}:
        return jsonify({"error": f"Request is already {req['request_status']}"}), 409

    converted_task_id = None
    if decision == "APPROVED":
        # Recalculate immediately before sanction and convert request into an optimizer task.
        task, _, ai = _evaluate_request(req)
        converted_task_id = "ENG-" + request_id.replace("REQ-", "")
        task.task_id = converted_task_id
        task.computed_ai_priority = ai["composite_score"]
        task.status = TaskStatus.PENDING
        database.insert_maintenance_task(task)
        result = database.decide_maintenance_request(
            request_id, decision, officer_name, str(data.get("note") or ""),
            str(data.get("instruction") or "Proceed as per sanctioned block and coordinate with control."),
            converted_task_id,
        )
        _refresh_operational_state()
        scheduled = next((t.to_dict() for t in tasks if t.task_id == converted_task_id), None)
        return jsonify({"status": "approved", "request": result, "operational_task": scheduled})

    result = database.decide_maintenance_request(
        request_id, decision, officer_name, str(data.get("note") or ""), str(data.get("instruction") or "Request not sanctioned."), None
    )
    return jsonify({"status": "rejected", "request": result})


@app.route("/api/corridor", methods=["GET"])
def get_corridor():
    total_length = max((float(s.get("km", 0.0)) for s in station_catalog), default=0.0)
    return jsonify({
        "stations": station_catalog,
        "sections": [s.to_dict() for s in sections],
        "total_length_km": total_length,
        "total_sections": len(sections)
    })


@app.route("/api/stations", methods=["GET"])
def get_stations():
    q = (request.args.get("q") or "").strip().lower()
    matches = station_catalog
    if q:
        matches = [
            st for st in station_catalog
            if q in st.get("code", "").lower() or q in st.get("name", "").lower()
        ]
    return jsonify({"total_count": len(matches), "stations": matches[:50]})


@app.route("/api/station-analysis", methods=["GET"])
def station_analysis():
    query = request.args.get("station", "")
    station = _resolve_station(query)
    if not station:
        return jsonify({
            "error": "Station not found in the loaded prototype dataset.",
            "query": query,
            "available_stations": station_catalog[:20]
        }), 404

    code = station["code"]
    section_ids = _station_section_ids(code)
    nearby_sections = [s for s in sections if s.section_id in section_ids]

    # Trains are relevant when their computed corridor occupancy touches an adjacent section.
    station_trains = []
    for t in trains:
        occs = [o for o in t.section_occupancies if o["section_id"] in section_ids]
        if not occs:
            continue
        pass_min = min(o["entry_min"] for o in occs)
        station_trains.append({
            "train_no": t.train_no,
            "train_name": t.train_name,
            "train_type": t.train_type.value,
            "direction": t.direction,
            "origin": t.origin,
            "destination": t.destination,
            "priority_rank": t.priority_rank,
            "computed_pass_time": _mins_to_clock(pass_min)
        })
    station_trains.sort(key=lambda x: (x["computed_pass_time"], x["priority_rank"]))

    station_tasks = [
        t for t in tasks
        if t.station_code == code or t.section_id in section_ids
    ]
    section_map = {s.section_id: s for s in sections}
    task_details = []
    for t in sorted(station_tasks, key=lambda x: x.computed_ai_priority, reverse=True):
        sec = section_map.get(t.section_id)
        evaluation = prioritizer.evaluate_task(t, sec) if sec else None
        d = t.to_dict()
        d["priority_breakdown"] = evaluation
        task_details.append(d)

    local_clusters = detector.detect_clusters(station_tasks)
    cluster_details = [c.to_dict() for c in local_clusters]
    shadow_clusters = [c for c in local_clusters if c.is_multi_department]

    local_windows = [w for w in windows if w.section_id in section_ids]
    window_details = sorted(
        [{**w.to_dict(), "start_time": _mins_to_clock(w.start_time_mins), "end_time": _mins_to_clock(w.end_time_mins)} for w in local_windows],
        key=lambda w: w["duration_mins"], reverse=True
    )[:8]

    all_blocks = []
    for plan_key in ["daily_plan", "weekly_plan", "monthly_plan"]:
        for b in plans_cache[plan_key]["blocks"]:
            if b["section_id"] in section_ids:
                all_blocks.append(b)
    all_blocks.sort(key=lambda b: (b.get("date_str", ""), b.get("start_time_mins", 0)))

    top_task = task_details[0] if task_details else None
    best_cluster = max(shadow_clusters, key=lambda c: c.hours_saved, default=None)
    best_window = window_details[0] if window_details else None
    recommended_block = all_blocks[0] if all_blocks else None

    workflow = [
        {
            "step": 1,
            "name": "Station & Section Mapping",
            "status": "DONE",
            "detail": f"Mapped {station['name']} ({code}) to {len(nearby_sections)} adjacent UP/DN track sections."
        },
        {
            "step": 2,
            "name": "Train Timetable Check",
            "status": "DONE",
            "detail": f"Checked {len(station_trains)} trains whose corridor occupancy touches this station area."
        },
        {
            "step": 3,
            "name": "AI Priority Calculation",
            "status": "DONE" if top_task else "NO_DEMAND",
            "detail": (f"Highest maintenance priority is {top_task['computed_ai_priority']}/100 ({top_task['task_name']})." if top_task else "No maintenance demand is loaded for this station area.")
        },
        {
            "step": 4,
            "name": "Shadow Block Detection",
            "status": "DONE" if local_clusters else "NO_DEMAND",
            "detail": (f"Found {len(local_clusters)} maintenance cluster(s), including {len(shadow_clusters)} multi-department shadow cluster(s)." if local_clusters else "No nearby maintenance tasks to cluster.")
        },
        {
            "step": 5,
            "name": "Free Window Search",
            "status": "DONE" if best_window else "NO_WINDOW",
            "detail": (f"Best displayed free window is {best_window['start_time']}–{best_window['end_time']} ({best_window['duration_mins']} min)." if best_window else "No qualifying free corridor window was found.")
        },
        {
            "step": 6,
            "name": "Optimizer Recommendation",
            "status": "SCHEDULED" if recommended_block else "NO_BLOCK_REQUIRED" if not station_tasks else "DEFERRED",
            "detail": (f"Recommended {recommended_block['block_id']} on {recommended_block['date_str']} from {recommended_block['start_time_str']} to {recommended_block['end_time_str']}." if recommended_block else ("No maintenance block is required for the loaded station data." if not station_tasks else "Maintenance exists, but no feasible scheduled block is present in the current plan."))
        }
    ]

    return jsonify({
        "station": station,
        "adjacent_sections": [s.to_dict() for s in nearby_sections],
        "train_count": len(station_trains),
        "trains": station_trains[:20],
        "maintenance_count": len(task_details),
        "tasks": task_details,
        "clusters": cluster_details,
        "best_shadow_cluster": best_cluster.to_dict() if best_cluster else None,
        "windows": window_details,
        "recommended_block": recommended_block,
        "workflow": workflow,
        "prototype_note": "Results use the currently loaded corridor dataset; this is a decision-support prototype, not a live Indian Railways feed."
    })


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    dept = request.args.get("department")
    horizon = request.args.get("horizon")
    
    filtered = tasks
    if dept and dept != "ALL":
        filtered = [t for t in filtered if t.department.value == dept]
    if horizon and horizon != "ALL":
        filtered = [t for t in filtered if t.horizon.value == horizon]
        
    return jsonify({
        "total_count": len(filtered),
        "tasks": [t.to_dict() for t in filtered]
    })


@app.route("/api/trains", methods=["GET"])
def get_trains():
    t_type = request.args.get("type")
    filtered = trains
    if t_type and t_type != "ALL":
        filtered = [t for t in filtered if t.train_type.value == t_type]
    return jsonify({
        "total_count": len(filtered),
        "trains": [t.to_dict() for t in filtered]
    })


@app.route("/api/windows", methods=["GET"])
def get_windows():
    return jsonify({
        "total_count": len(windows),
        "windows": [w.to_dict() for w in windows]
    })


@app.route("/api/clusters", methods=["GET"])
def get_clusters():
    clusters = detector.detect_clusters(tasks)
    summary = detector.calculate_shadow_summary(clusters)
    return jsonify(summary)


@app.route("/api/schedules", methods=["GET"])
def get_schedules():
    global plans_cache
    horizon = request.args.get("horizon", "DAILY").upper()
    if horizon == "WEEKLY":
        return jsonify(plans_cache["weekly_plan"])
    elif horizon == "MONTHLY":
        return jsonify(plans_cache["monthly_plan"])
    elif horizon == "ALL":
        return jsonify(plans_cache)
    return jsonify(plans_cache["daily_plan"])


@app.route("/api/kpis", methods=["GET"])
def get_kpis():
    # Gather scheduled daily blocks
    daily_blocks = [
        b for b in plans_cache["daily_plan"]["blocks"]
    ]
    # Reconstruct ScheduledBlock objects for KPI engine
    daily_clusters = detector.detect_clusters([t for t in tasks if t.horizon == PriorityHorizon.DAILY or t.computed_ai_priority >= 75.0])
    scheduled_daily = optimizer.optimize_schedule(daily_clusters, windows, trains, sections, PriorityHorizon.DAILY)
    kpis = KPIEngine.compute_kpis(tasks, scheduled_daily)
    return jsonify(kpis)


@app.route("/api/memo/<block_id>", methods=["GET"])
def get_memo(block_id: str):
    # Find matching block in plans
    target_block = None
    for h in ["daily_plan", "weekly_plan", "monthly_plan"]:
        for b in plans_cache[h]["blocks"]:
            if b["block_id"] == block_id:
                target_block = b
                break
        if target_block:
            break
            
    if not target_block:
        return jsonify({"error": "Block not found"}), 404
        
    # Reconstruct dummy models for memo text
    dummy_task = None
    if target_block["tasks"]:
        first_t = target_block["tasks"][0]
        dummy_task = tasks[0] # fallback
        for t in tasks:
            if t.task_id == first_t.get("task_id"):
                dummy_task = t
                break

    # We need a ScheduledBlock wrapper to call report generator
    class BlockWrapper:
        def __init__(self, d):
            for k, v in d.items():
                setattr(self, k, v)
            self.departments_involved = [Department(dept) for dept in d["departments_involved"]]
            self.block_type = BlockType(d["block_type"])
            self.is_shadow_block = d["is_shadow_block"]
            self.tasks = tasks[:len(d["tasks"])]

    bw = BlockWrapper(target_block)
    
    t351 = ReportGenerator.generate_t351_memo(bw, dummy_task)
    pb = ReportGenerator.generate_power_block_memo(bw, dummy_task)
    coa = ReportGenerator.generate_coa_block_grant(bw)
    
    return jsonify({
        "block_id": block_id,
        "t351_memo": t351,
        "power_block_memo": pb,
        "coa_grant_order": coa
    })


@app.route("/api/simulate", methods=["POST"])
def run_simulation():
    data = request.get_json() or {}
    scenario = data.get("scenario", "INJECT_EMERGENCY_DEFECT")
    params = data.get("params", {})
    res = simulator.run_scenario(scenario, params)
    return jsonify(res)


@app.route("/api/reoptimize", methods=["POST"])
def reoptimize():
    global prioritizer, tasks, plans_cache
    data = request.get_json() or {}
    w_s = float(data.get("weight_safety", 0.35))
    w_d = float(data.get("weight_degradation", 0.25))
    w_u = float(data.get("weight_urgency", 0.20))
    w_t = float(data.get("weight_traffic", 0.12))
    w_a = float(data.get("weight_tsr", 0.08))
    
    prioritizer = AIPrioritizer(w_s, w_d, w_u, w_t, w_a)
    prioritizer.prioritize_all_tasks(tasks, sections)
    plans_cache = planner.generate_all_horizons(tasks, sections, trains, windows, base_date="2026-08-30")
    database.update_task_computed_state(tasks)
    
    return jsonify({
        "status": "success",
        "message": "AI Priority weights updated and multi-horizon schedules regenerated!",
        "plans": plans_cache
    })




@app.route("/health", methods=["GET"])
def health_check():
    """Lightweight health endpoint for Render and uptime checks."""
    try:
        counts = database.get_counts()
        return jsonify({
            "status": "ok",
            "service": "RailBlock AI",
            "database": "SQLite",
            "stations": counts.get("stations", 0),
            "tasks": counts.get("maintenance_tasks", 0),
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "detail": str(exc)}), 500


@app.route("/api/database/status", methods=["GET"])
def database_status():
    return jsonify({
        "engine": "SQLite",
        "database_file": os.path.basename(database.db_path),
        "database_path": database.db_path,
        "active_source": database.get_active_source(),
        "counts": database.get_counts(),
        "note": "CSV files are seed/import sources; the running app reads operational data from SQLite."
    })


@app.route("/api/kaggle/status", methods=["GET"])
def kaggle_status():
    summary = kaggle_importer.get_dataset_summary()
    summary["active_source"] = active_data_source
    return jsonify(summary)


@app.route("/api/kaggle/switch-source", methods=["POST"])
def switch_data_source():
    global sections, tasks, trains, windows, plans_cache, active_data_source, simulator, planner, station_catalog
    data = request.get_json() or {}
    source = data.get("source", "KAGGLE_REAL")

    if source == "KAGGLE_REAL":
        seed_stations = kaggle_importer.load_real_stations()
        seed_sections = kaggle_importer.build_track_sections_from_stations(seed_stations)
        seed_tasks = kaggle_importer.load_real_maintenance_tasks()
        seed_trains = kaggle_importer.load_real_trains(seed_sections)
        source_name = "KAGGLE_REAL"
    else:
        seed_stations = [dict(st, division="Demo HDN", zone="NR", state="Demo") for st in STATIONS]
        seed_sections = generate_track_sections()
        seed_tasks = generate_maintenance_tasks(seed_sections, seed=42)
        seed_trains = generate_train_timetable(seed_sections)
        source_name = "DEFAULT_HDN"

    # Import source data into SQLite, then reload the running objects from SQLite.
    database.replace_dataset(seed_stations, seed_sections, seed_tasks, seed_trains, source_name)
    active_data_source = database.get_active_source()
    station_catalog = database.load_stations()
    sections = database.load_sections()
    tasks = database.load_tasks()
    trains = database.load_trains()

    windows = compute_corridor_availability_windows(sections, trains)
    prioritizer.prioritize_all_tasks(tasks, sections)
    planner = MultiHorizonPlanner(detector, optimizer)
    simulator = WhatIfSimulator(sections, tasks, trains, prioritizer, detector, optimizer)
    plans_cache = planner.generate_all_horizons(tasks, sections, trains, windows, base_date="2026-08-30")
    database.update_task_computed_state(tasks)

    return jsonify({
        "status": "success",
        "active_source": active_data_source,
        "storage": "SQLITE",
        "database_path": database.db_path,
        "total_tasks": len(tasks),
        "total_trains": len(trains),
        "total_sections": len(sections)
    })


@app.route("/api/kaggle/fetch", methods=["POST"])
def fetch_kaggle_dataset():
    data = request.get_json() or {}
    slug = data.get("dataset_slug", "vijayv/indian-railway-data")
    res = kaggle_importer.download_kaggle_dataset(slug)
    return jsonify(res)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
