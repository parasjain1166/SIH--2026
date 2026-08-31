-- RailBlock AI SQLite schema (Stage 2: Engineer + Officer workflow)

CREATE INDEX idx_occupancy_section_time
                    ON train_section_occupancies(section_id, entry_min, exit_min);

CREATE INDEX idx_requests_department_status
                    ON maintenance_requests(department, request_status);

CREATE INDEX idx_requests_priority
                    ON maintenance_requests(ai_priority DESC);

CREATE INDEX idx_requests_station
                    ON maintenance_requests(station_code);

CREATE INDEX idx_tasks_priority ON maintenance_tasks(computed_ai_priority DESC);

CREATE INDEX idx_tasks_section ON maintenance_tasks(section_id);

CREATE INDEX idx_tasks_station ON maintenance_tasks(station_code);

CREATE TABLE maintenance_requests (
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

CREATE TABLE maintenance_tasks (
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

CREATE TABLE metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

CREATE TABLE request_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_name TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(request_id) REFERENCES maintenance_requests(request_id) ON DELETE CASCADE
                );

CREATE TABLE stations (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    km REAL NOT NULL,
                    division TEXT,
                    zone TEXT,
                    state TEXT,
                    has_yard INTEGER NOT NULL DEFAULT 0,
                    platforms INTEGER NOT NULL DEFAULT 2
                );

CREATE TABLE task_gangs (
                    task_id TEXT NOT NULL,
                    gang_id TEXT NOT NULL,
                    PRIMARY KEY(task_id, gang_id),
                    FOREIGN KEY(task_id) REFERENCES maintenance_tasks(task_id) ON DELETE CASCADE
                );

CREATE TABLE task_machines (
                    task_id TEXT NOT NULL,
                    machine_id TEXT NOT NULL,
                    PRIMARY KEY(task_id, machine_id),
                    FOREIGN KEY(task_id) REFERENCES maintenance_tasks(task_id) ON DELETE CASCADE
                );

CREATE TABLE track_sections (
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

CREATE TABLE train_section_occupancies (
                    occupancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    train_no TEXT NOT NULL,
                    section_id TEXT NOT NULL,
                    entry_min INTEGER NOT NULL,
                    exit_min INTEGER NOT NULL,
                    FOREIGN KEY(train_no) REFERENCES trains(train_no) ON DELETE CASCADE,
                    FOREIGN KEY(section_id) REFERENCES track_sections(section_id) ON DELETE CASCADE
                );

CREATE TABLE trains (
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

