/**
 * RailBlock AI - Main Application & State Manager
 */

let appState = {
    corridor: null,
    tasks: [],
    trains: [],
    windows: [],
    clusters: null,
    schedules: null,
    kpis: null,
    activeTab: 'dashboard',
    selectedMemoBlock: null,
    currentMemoType: 't351',
    weights: {
        safety: 0.35,
        degradation: 0.25,
        urgency: 0.20,
        traffic: 0.12,
        tsr: 0.08
    }
};

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
    startClock();
    await loadInitialData();
    populateStationSelector();
    await analyzeSelectedStation();
    renderDashboard();
    renderDataHub();
    renderPriorityExplain();
    populateMemoSelector();
    loadKaggleStatus();
    initTrackMap();
    initGantt();
});

function startClock() {
    setInterval(() => {
        const now = new Date();
        const el = document.getElementById('live-clock');
        if (el) {
            el.innerText = now.toLocaleString('sv-SE', { timeZone: 'Asia/Kolkata', hour12: false }) + ' IST';
        }
    }, 1000);
}

// Switch Active Tabs
function switchTab(tabId) {
    appState.activeTab = tabId;
    
    // Update button states
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active-tab', 'text-sky-400');
        btn.classList.add('text-slate-400');
    });
    const activeBtn = document.getElementById(`tab-${tabId}`);
    if (activeBtn) {
        activeBtn.classList.add('active-tab');
        activeBtn.classList.remove('text-slate-400');
    }

    // Update section visibility
    document.querySelectorAll('.tab-content').forEach(sec => {
        sec.classList.add('hidden');
        sec.classList.remove('block');
    });
    const activeSec = document.getElementById(`view-${tabId}`);
    if (activeSec) {
        activeSec.classList.remove('hidden');
        activeSec.classList.add('block');
    }

    // Refresh specific tab visuals
    if (tabId === 'track-map') {
        renderTrackMap();
    } else if (tabId === 'gantt-schedule') {
        renderGanttChart();
    } else if (tabId === 'kaggle') {
        loadKaggleStatus();
    }
}

// Fetch Initial Data from REST API
async function loadInitialData() {
    try {
        const [corridorRes, tasksRes, trainsRes, clustersRes, schedulesRes, kpisRes] = await Promise.all([
            fetch('/api/corridor').then(r => r.json()),
            fetch('/api/tasks').then(r => r.json()),
            fetch('/api/trains').then(r => r.json()),
            fetch('/api/clusters').then(r => r.json()),
            fetch('/api/schedules?horizon=ALL').then(r => r.json()),
            fetch('/api/kpis').then(r => r.json())
        ]);

        appState.corridor = corridorRes;
        appState.tasks = tasksRes.tasks;
        appState.trains = trainsRes.trains;
        appState.clusters = clustersRes;
        appState.schedules = schedulesRes;
        appState.kpis = kpisRes;

    } catch (err) {
        console.error("Error loading initial data:", err);
    }
}

// Render Executive Dashboard Tab
function renderDashboard() {
    if (!appState.kpis) return;

    const summary = appState.kpis.summary;
    const comp = appState.kpis.comparison;

    const corridorHeader = document.getElementById('header-corridor');
    if (corridorHeader && appState.corridor?.stations?.length) {
        const first = appState.corridor.stations[0];
        const last = appState.corridor.stations[appState.corridor.stations.length - 1];
        corridorHeader.innerText = `${first.code} - ${last.code} (${appState.corridor.total_length_km} KM)`;
    }

    // Header & Metric Cards
    document.getElementById('header-aai').innerText = `${summary.asset_availability_pct}%`;
    document.getElementById('header-shadow-gain').innerText = `+${summary.shadow_efficiency_gain_pct}% Hrs Saved`;
    
    document.getElementById('metric-aai').innerText = `${summary.asset_availability_pct}%`;
    document.getElementById('metric-hours-saved').innerText = `${summary.hours_saved_via_shadow} Hrs`;
    document.getElementById('metric-safety').innerText = `${summary.safety_mitigation_pct}%`;
    document.getElementById('metric-train-delay').innerText = `${summary.total_train_delay_mins} Mins`;

    // Benchmark Table
    const tbody = document.getElementById('benchmark-table-body');
    if (tbody && comp) {
        tbody.innerHTML = `
            <tr class="hover:bg-slate-900/40 transition">
                <td class="py-3 px-4 font-semibold text-white">Block Window Utilization Rate</td>
                <td class="py-3 px-4 text-rose-400 font-mono">${comp.block_utilization_pct.manual_siloed}% (Fragmented)</td>
                <td class="py-3 px-4 text-emerald-400 font-mono font-bold">${comp.block_utilization_pct.railblock_ai}% (Unified)</td>
                <td class="py-3 px-4 text-sky-400 font-mono font-bold">${comp.block_utilization_pct.improvement}</td>
            </tr>
            <tr class="hover:bg-slate-900/40 transition">
                <td class="py-3 px-4 font-semibold text-white">Total Track Downtime Required</td>
                <td class="py-3 px-4 text-rose-400 font-mono">${comp.total_track_downtime_hours.manual_siloed} Hours</td>
                <td class="py-3 px-4 text-emerald-400 font-mono font-bold">${comp.total_track_downtime_hours.railblock_ai} Hours</td>
                <td class="py-3 px-4 text-emerald-400 font-mono font-bold">-${comp.total_track_downtime_hours.hours_saved} Hours Saved</td>
            </tr>
            <tr class="hover:bg-slate-900/40 transition">
                <td class="py-3 px-4 font-semibold text-white">Train Punctuality Loss (Cascading Delay)</td>
                <td class="py-3 px-4 text-rose-400 font-mono">${comp.train_punctuality_loss_mins.manual_siloed} Mins</td>
                <td class="py-3 px-4 text-emerald-400 font-mono font-bold">${comp.train_punctuality_loss_mins.railblock_ai} Mins</td>
                <td class="py-3 px-4 text-emerald-400 font-mono font-bold">${comp.train_punctuality_loss_mins.reduction_pct} Delay Reduction</td>
            </tr>
            <tr class="hover:bg-slate-900/40 transition">
                <td class="py-3 px-4 font-semibold text-white">Fixed Asset Availability Index (AAI)</td>
                <td class="py-3 px-4 text-rose-400 font-mono">${comp.asset_availability_pct.manual_siloed}%</td>
                <td class="py-3 px-4 text-emerald-400 font-mono font-bold">${comp.asset_availability_pct.railblock_ai}%</td>
                <td class="py-3 px-4 text-sky-400 font-mono font-bold">${comp.asset_availability_pct.improvement}</td>
            </tr>
            <tr class="hover:bg-slate-900/40 transition">
                <td class="py-3 px-4 font-semibold text-white">Shadow / Joint Blocking Co-location</td>
                <td class="py-3 px-4 text-rose-400 font-mono">${comp.shadow_blocking_rate_pct.manual_siloed}%</td>
                <td class="py-3 px-4 text-purple-400 font-mono font-bold">${comp.shadow_blocking_rate_pct.railblock_ai}%</td>
                <td class="py-3 px-4 text-purple-400 font-mono font-bold">${comp.shadow_blocking_rate_pct.improvement} Co-location</td>
            </tr>
            <tr class="hover:bg-slate-900/40 transition">
                <td class="py-3 px-4 font-semibold text-white">Critical Safety Maintenance Compliance</td>
                <td class="py-3 px-4 text-rose-400 font-mono">${comp.critical_safety_compliance_pct.manual_siloed}%</td>
                <td class="py-3 px-4 text-emerald-400 font-mono font-bold">${comp.critical_safety_compliance_pct.railblock_ai}%</td>
                <td class="py-3 px-4 text-emerald-400 font-mono font-bold">${comp.critical_safety_compliance_pct.improvement} Compliance</td>
            </tr>
        `;
    }

    // Department Breakdown
    const deptBox = document.getElementById('dept-breakdown-cards');
    if (deptBox && appState.kpis.departmental) {
        const d = appState.kpis.departmental;
        deptBox.innerHTML = `
            <div class="p-3 rounded-lg bg-slate-900/60 border border-rail-border flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <span class="w-3 h-3 rounded bg-blue-500"></span>
                    <div>
                        <div class="font-bold text-slate-200">TMS (Track / Civil)</div>
                        <div class="text-[11px] text-slate-400">IMR Rail Flaws, CSM Tamping, BCM</div>
                    </div>
                </div>
                <div class="text-right">
                    <span class="font-mono font-bold text-blue-400 text-sm">${d.TMS.scheduled}/${d.TMS.total}</span>
                    <span class="text-[10px] text-slate-400 block">Scheduled</span>
                </div>
            </div>

            <div class="p-3 rounded-lg bg-slate-900/60 border border-rail-border flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <span class="w-3 h-3 rounded bg-emerald-500"></span>
                    <div>
                        <div class="font-bold text-slate-200">SMMS (Signalling & Telecom)</div>
                        <div class="text-[11px] text-slate-400">Point Machines, Axle Counters, T/351</div>
                    </div>
                </div>
                <div class="text-right">
                    <span class="font-mono font-bold text-emerald-400 text-sm">${d.SMMS.scheduled}/${d.SMMS.total}</span>
                    <span class="text-[10px] text-slate-400 block">Scheduled</span>
                </div>
            </div>

            <div class="p-3 rounded-lg bg-slate-900/60 border border-rail-border flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <span class="w-3 h-3 rounded bg-amber-500"></span>
                    <div>
                        <div class="font-bold text-slate-200">TDMS (Traction / TRD)</div>
                        <div class="text-[11px] text-slate-400">OHE AOH, Cantilevers, Power Blocks</div>
                    </div>
                </div>
                <div class="text-right">
                    <span class="font-mono font-bold text-amber-400 text-sm">${d.TDMS.scheduled}/${d.TDMS.total}</span>
                    <span class="text-[10px] text-slate-400 block">Scheduled</span>
                </div>
            </div>
        `;
    }

    // Multi-horizon Counts
    if (appState.schedules) {
        document.getElementById('daily-count-badge').innerText = `${appState.schedules.daily_plan.total_blocks} Blocks (${appState.schedules.daily_plan.shadow_blocks} Shadow)`;
        document.getElementById('weekly-count-badge').innerText = `${appState.schedules.weekly_plan.total_blocks} Blocks (${appState.schedules.weekly_plan.shadow_blocks} Shadow)`;
        document.getElementById('monthly-count-badge').innerText = `${appState.schedules.monthly_plan.total_blocks} Blocks (${appState.schedules.monthly_plan.shadow_blocks} Shadow)`;
        
        // TSR Roadmap
        const tsrList = document.getElementById('tsr-list');
        if (tsrList && appState.schedules.tsr_roadmap) {
            tsrList.innerHTML = appState.schedules.tsr_roadmap.map(item => `
                <div class="p-2.5 rounded bg-slate-900/60 border border-rail-border flex items-center justify-between">
                    <div>
                        <div class="font-semibold text-slate-200">${item.section_id} (KM ${item.location_km})</div>
                        <div class="text-[11px] text-slate-400">TSR: <span class="text-rose-400 font-mono">${item.current_tsr_kmh} km/h</span> â†’ <span class="text-emerald-400 font-mono">${item.target_max_speed_kmh} km/h</span> (${item.speed_restoration_gain})</div>
                    </div>
                    <span class="px-2 py-0.5 rounded font-mono text-[10px] ${item.status === 'SCHEDULED' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-300'}">
                        ${item.status}
                    </span>
                </div>
            `).join('');
        }
    }
}

// Render Data Hub Table
function renderDataHub() {
    const tbody = document.getElementById('data-hub-table-body');
    if (!tbody || !appState.tasks) return;

    const deptFilter = document.getElementById('hub-dept-filter')?.value || 'ALL';
    const horizonFilter = document.getElementById('hub-horizon-filter')?.value || 'ALL';

    const filtered = appState.tasks.filter(t => {
        if (deptFilter !== 'ALL' && t.department !== deptFilter) return false;
        if (horizonFilter !== 'ALL' && t.horizon !== horizonFilter) return false;
        return true;
    });

    tbody.innerHTML = filtered.map(t => {
        let deptBadge = 'bg-blue-500/20 text-blue-300 border-blue-500/30';
        if (t.department === 'SMMS') deptBadge = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
        if (t.department === 'TDMS') deptBadge = 'bg-amber-500/20 text-amber-300 border-amber-500/30';

        let statusBadge = 'bg-slate-700 text-slate-300';
        if (t.status === 'SCHEDULED') statusBadge = 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
        if (t.status === 'DEFERRED') statusBadge = 'bg-amber-500/20 text-amber-300 border border-amber-500/30';

        return `
            <tr class="hover:bg-slate-900/60 transition">
                <td class="py-2.5 px-3 font-mono text-slate-300 font-semibold">${t.task_id}</td>
                <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${deptBadge}">${t.department}</span></td>
                <td class="py-2.5 px-3">
                    <div class="font-medium text-slate-200">${t.task_name}</div>
                    <div class="text-[10px] font-mono text-slate-400">${t.task_category}</div>
                </td>
                <td class="py-2.5 px-3 font-mono text-slate-300">${t.section_id} <span class="text-slate-400">(${t.track_line})</span></td>
                <td class="py-2.5 px-3 font-mono text-slate-300">${t.required_duration_mins}m</td>
                <td class="py-2.5 px-3 font-mono ${t.urgency_days_overdue > 7 ? 'text-rose-400 font-bold' : 'text-slate-400'}">${t.urgency_days_overdue} days</td>
                <td class="py-2.5 px-3 font-mono font-bold ${t.computed_ai_priority >= 85 ? 'text-rose-400' : t.computed_ai_priority >= 70 ? 'text-amber-400' : 'text-sky-400'}">
                    ${t.computed_ai_priority}
                </td>
                <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded text-[10px] font-mono ${statusBadge}">${t.status}</span></td>
            </tr>
        `;
    }).join('');
}

function filterDataHub() {
    renderDataHub();
}

// Render AI Priority Explainability Table
function renderPriorityExplain() {
    const tbody = document.getElementById('priority-explain-table-body');
    if (!tbody || !appState.tasks) return;

    const sorted = [...appState.tasks].sort((a, b) => b.computed_ai_priority - a.computed_ai_priority);

    tbody.innerHTML = sorted.map((t, idx) => {
        const pColor = t.computed_ai_priority >= 85 ? 'text-rose-400' : t.computed_ai_priority >= 70 ? 'text-amber-400' : 'text-sky-400';
        return `
            <tr class="hover:bg-slate-900/60 transition">
                <td class="py-2 px-3 font-mono font-bold text-slate-400">#${idx + 1}</td>
                <td class="py-2 px-3">
                    <div class="font-medium text-slate-200">${t.task_name}</div>
                    <div class="text-[10px] text-slate-400 font-mono">${t.section_id} | KM ${t.start_km}-${t.end_km}</div>
                </td>
                <td class="py-2 px-3 font-mono font-semibold text-slate-300">${t.department}</td>
                <td class="py-2 px-3 text-center font-mono font-bold ${t.safety_criticality >= 8.5 ? 'text-rose-400' : 'text-slate-300'}">${t.safety_criticality}/10</td>
                <td class="py-2 px-3 text-center font-mono text-slate-300">${t.asset_degradation_score}/10</td>
                <td class="py-2 px-3 text-center font-mono ${t.urgency_days_overdue > 7 ? 'text-rose-400 font-bold' : 'text-slate-400'}">+${t.urgency_days_overdue}d</td>
                <td class="py-2 px-3 text-right font-mono font-bold ${pColor} text-sm">${t.computed_ai_priority}</td>
            </tr>
        `;
    }).join('');
}

// UI Weights Handler
function updateWeightsUI() {
    document.getElementById('val-ws').innerText = parseFloat(document.getElementById('slider-ws').value).toFixed(2);
    document.getElementById('val-wd').innerText = parseFloat(document.getElementById('slider-wd').value).toFixed(2);
    document.getElementById('val-wu').innerText = parseFloat(document.getElementById('slider-wu').value).toFixed(2);
    document.getElementById('val-wt').innerText = parseFloat(document.getElementById('slider-wt').value).toFixed(2);
    document.getElementById('val-wa').innerText = parseFloat(document.getElementById('slider-wa').value).toFixed(2);
}

async function reoptimizeWeights() {
    const payload = {
        weight_safety: parseFloat(document.getElementById('slider-ws').value),
        weight_degradation: parseFloat(document.getElementById('slider-wd').value),
        weight_urgency: parseFloat(document.getElementById('slider-wu').value),
        weight_traffic: parseFloat(document.getElementById('slider-wt').value),
        weight_tsr: parseFloat(document.getElementById('slider-wa').value)
    };

    try {
        const res = await fetch('/api/reoptimize', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }).then(r => r.json());

        // Refresh data
        await loadInitialData();
        renderDashboard();
        renderDataHub();
        renderPriorityExplain();
        renderGanttChart();
        alert("Optimization complete: AI Prioritization weights updated and schedules regenerated!");
    } catch (err) {
        console.error("Reoptimization error:", err);
    }
}

// Memo Selector & View
function populateMemoSelector() {
    const select = document.getElementById('memo-block-select');
    if (!select || !appState.schedules) return;

    const allBlocks = [
        ...appState.schedules.daily_plan.blocks,
        ...appState.schedules.weekly_plan.blocks
    ];

    select.innerHTML = allBlocks.map(b => `
        <option value="${b.block_id}">${b.block_id} - ${b.section_id} (${b.start_time_str} - ${b.end_time_str}) [${b.is_shadow_block ? 'SHADOW' : b.block_type}]</option>
    `).join('');

    if (allBlocks.length > 0) {
        appState.selectedMemoBlock = allBlocks[0].block_id;
        loadBlockMemo();
    }
}

async function loadBlockMemo() {
    const select = document.getElementById('memo-block-select');
    const blockId = select ? select.value : appState.selectedMemoBlock;
    if (!blockId) return;

    try {
        const res = await fetch(`/api/memo/${blockId}`).then(r => r.json());
        const memoBox = document.getElementById('memo-text-content');
        if (memoBox) {
            if (appState.currentMemoType === 't351') {
                memoBox.innerText = res.t351_memo;
            } else if (appState.currentMemoType === 'power') {
                memoBox.innerText = res.power_block_memo;
            } else {
                memoBox.innerText = res.coa_grant_order;
            }
        }
    } catch (err) {
        console.error("Error loading memo:", err);
    }
}

function setMemoType(type) {
    appState.currentMemoType = type;
    ['t351', 'power', 'coa'].forEach(t => {
        const btn = document.getElementById(`btn-memo-${t}`);
        if (btn) {
            if (t === type) {
                btn.className = "px-3 py-1 rounded text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
            } else {
                btn.className = "px-3 py-1 rounded text-xs font-bold text-slate-400 hover:text-white";
            }
        }
    });
    loadBlockMemo();
}

function printMemo() {
    const memoContent = document.getElementById('memo-text-content').innerText;
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <html><head><title>Indian Railways Official Memo</title></head>
        <body style="font-family: monospace; white-space: pre; padding: 20px;">${memoContent}</body></html>
    `);
    printWindow.document.close();
    printWindow.print();
}


// ----------------------------------------------------
// Station-Level Prototype Analysis
// ----------------------------------------------------
function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function populateStationSelector() {
    const list = document.getElementById('station-options');
    if (!list || !appState.corridor?.stations) return;
    list.innerHTML = appState.corridor.stations.map(st =>
        `<option value="${escapeHtml(st.code)}">${escapeHtml(st.name)} (${escapeHtml(st.code)})</option>`
    ).join('');
}

async function analyzeSelectedStation() {
    const input = document.getElementById('station-search-input');
    const status = document.getElementById('station-analysis-status');
    const button = document.getElementById('station-analyze-btn');
    if (!input) return;

    const stationQuery = input.value.trim();
    if (!stationQuery) {
        if (status) status.innerText = 'Type a station name or code first.';
        return;
    }

    if (button) {
        button.disabled = true;
        button.classList.add('opacity-60', 'cursor-wait');
    }
    if (status) {
        status.innerHTML = `<span class="text-sky-400"><i class="fa-solid fa-circle-notch fa-spin mr-1"></i>Running station analysis for ${escapeHtml(stationQuery)}...</span>`;
    }

    try {
        const response = await fetch(`/api/station-analysis?station=${encodeURIComponent(stationQuery)}`);
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Station analysis failed.');
        }
        renderStationAnalysis(data);
        if (status) {
            status.innerHTML = `<span class="text-emerald-400"><i class="fa-solid fa-circle-check mr-1"></i>Analysis complete for ${escapeHtml(data.station.name)} (${escapeHtml(data.station.code)}).</span>`;
        }
    } catch (err) {
        console.error('Station analysis error:', err);
        if (status) status.innerHTML = `<span class="text-rose-400"><i class="fa-solid fa-triangle-exclamation mr-1"></i>${escapeHtml(err.message)}</span>`;
        const workflow = document.getElementById('station-workflow');
        if (workflow) workflow.innerHTML = `<div class="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300">${escapeHtml(err.message)} Choose a station from the loaded list.</div>`;
    } finally {
        if (button) {
            button.disabled = false;
            button.classList.remove('opacity-60', 'cursor-wait');
        }
    }
}

function renderStationAnalysis(data) {
    const summary = document.getElementById('station-summary');
    if (summary) summary.classList.remove('hidden');

    const stationEl = document.getElementById('sa-station');
    const trainEl = document.getElementById('sa-trains');
    const taskEl = document.getElementById('sa-tasks');
    const resultEl = document.getElementById('sa-result');
    if (stationEl) stationEl.innerText = `${data.station.name} (${data.station.code})`;
    if (trainEl) trainEl.innerText = data.train_count;
    if (taskEl) taskEl.innerText = data.maintenance_count;

    const finalStep = data.workflow?.[data.workflow.length - 1];
    if (resultEl) {
        resultEl.innerText = finalStep?.status === 'SCHEDULED' ? 'BLOCK SCHEDULED' :
            finalStep?.status === 'DEFERRED' ? 'DEFERRED' : 'NO BLOCK NEEDED';
        resultEl.className = finalStep?.status === 'SCHEDULED'
            ? 'text-sm font-bold font-mono text-emerald-400'
            : finalStep?.status === 'DEFERRED'
                ? 'text-sm font-bold font-mono text-amber-400'
                : 'text-sm font-bold font-mono text-slate-300';
    }

    renderStationWorkflow(data.workflow || []);
    renderStationTrains(data.trains || [], data.train_count || 0);
    renderStationPriorities(data.tasks || []);
    renderStationOptimizer(data);
}

function renderStationWorkflow(steps) {
    const box = document.getElementById('station-workflow');
    if (!box) return;
    const statusStyles = {
        DONE: 'border-emerald-500/30 bg-emerald-500/5 text-emerald-300',
        SCHEDULED: 'border-purple-500/30 bg-purple-500/5 text-purple-300',
        DEFERRED: 'border-amber-500/30 bg-amber-500/5 text-amber-300',
        NO_DEMAND: 'border-slate-700 bg-slate-900/40 text-slate-300',
        NO_WINDOW: 'border-rose-500/30 bg-rose-500/5 text-rose-300',
        NO_BLOCK_REQUIRED: 'border-slate-700 bg-slate-900/40 text-slate-300'
    };
    box.innerHTML = steps.map(step => `
        <div class="p-3 rounded-lg border ${statusStyles[step.status] || statusStyles.DONE}">
            <div class="flex items-center justify-between gap-2 mb-1.5">
                <span class="font-bold text-xs text-white">${step.step}. ${escapeHtml(step.name)}</span>
                <span class="text-[9px] font-mono uppercase">${escapeHtml(step.status)}</span>
            </div>
            <p class="text-[11px] leading-relaxed text-slate-400">${escapeHtml(step.detail)}</p>
        </div>
    `).join('');
}

function renderStationTrains(trains, totalCount) {
    const box = document.getElementById('station-train-results');
    if (!box) return;
    if (!trains.length) {
        box.innerHTML = '<div class="text-slate-500">No train occupancy found for the adjacent sections.</div>';
        return;
    }
    const visible = trains.slice(0, 6);
    box.innerHTML = `
        <div class="text-[10px] text-slate-500 font-mono mb-2">${totalCount} train(s) checked • showing first ${visible.length}</div>
        ${visible.map(t => `
            <div class="flex items-center justify-between gap-2 p-2 rounded bg-slate-900/70 border border-slate-800">
                <div class="min-w-0">
                    <div class="font-mono font-bold text-sky-300">${escapeHtml(t.train_no)} <span class="text-slate-300 font-sans">${escapeHtml(t.train_name)}</span></div>
                    <div class="text-[10px] text-slate-500">${escapeHtml(t.origin)} → ${escapeHtml(t.destination)} • ${escapeHtml(t.direction)} • Priority ${t.priority_rank}</div>
                </div>
                <div class="font-mono text-emerald-300 whitespace-nowrap">${escapeHtml(t.computed_pass_time)}</div>
            </div>
        `).join('')}
    `;
}

function renderStationPriorities(tasks) {
    const box = document.getElementById('station-priority-results');
    if (!box) return;
    if (!tasks.length) {
        box.innerHTML = '<div class="text-slate-500">No TMS/SMMS/TDMS maintenance demand is loaded around this station, so no priority score is required.</div>';
        return;
    }

    const top = tasks[0];
    const ev = top.priority_breakdown;
    const c = ev?.components || {};
    const w = ev?.weights || {};
    const formula = ev ? `${w.safety}×${c.safety_score} + ${w.degradation}×${c.degradation_score} + ${w.urgency}×${c.urgency_score} + ${w.traffic}×${c.traffic_score} + ${w.tsr}×${c.tsr_score}` : '';

    box.innerHTML = `
        <div class="p-2.5 rounded bg-amber-500/5 border border-amber-500/20">
            <div class="flex items-center justify-between gap-2">
                <span class="font-bold text-white">#${top.risk_rank} ${escapeHtml(top.task_id)}</span>
                <span class="text-lg font-mono font-bold text-amber-300">${top.computed_ai_priority}/100</span>
            </div>
            <div class="text-[11px] text-slate-300 mt-1">${escapeHtml(top.task_name)}</div>
            ${ev ? `<div class="mt-2 grid grid-cols-5 gap-1 text-center text-[9px] font-mono">
                <div class="bg-slate-900 rounded p-1">Safety<br><span class="text-white">${c.safety_score}</span></div>
                <div class="bg-slate-900 rounded p-1">Degrad.<br><span class="text-white">${c.degradation_score}</span></div>
                <div class="bg-slate-900 rounded p-1">Urgency<br><span class="text-white">${c.urgency_score}</span></div>
                <div class="bg-slate-900 rounded p-1">Traffic<br><span class="text-white">${c.traffic_score}</span></div>
                <div class="bg-slate-900 rounded p-1">TSR<br><span class="text-white">${c.tsr_score}</span></div>
            </div>
            <div class="mt-2 text-[9px] text-slate-500 font-mono break-words">${escapeHtml(formula)} = <span class="text-amber-300">${top.computed_ai_priority}</span></div>` : ''}
        </div>
        ${tasks.slice(1, 4).map(t => `
            <div class="flex justify-between gap-2 border-b border-slate-800 pb-1.5">
                <span class="truncate">${escapeHtml(t.department)} • ${escapeHtml(t.task_name)}</span>
                <span class="font-mono text-slate-300">${t.computed_ai_priority}</span>
            </div>
        `).join('')}
    `;
}

function renderStationOptimizer(data) {
    const box = document.getElementById('station-optimizer-results');
    if (!box) return;

    const cluster = data.best_shadow_cluster;
    const block = data.recommended_block;
    const bestWindow = data.windows?.[0];

    let html = '';
    if (cluster) {
        html += `
            <div class="p-2.5 rounded bg-purple-500/5 border border-purple-500/20">
                <div class="font-bold text-purple-300">Shadow Block Found</div>
                <div class="mt-1 text-slate-300">${cluster.departments.map(escapeHtml).join(' + ')} • ${cluster.task_count} tasks</div>
                <div class="mt-2 grid grid-cols-3 gap-1 text-center font-mono text-[10px]">
                    <div class="bg-slate-900 rounded p-1.5">Separate<br><b class="text-white">${cluster.sum_individual_duration_mins}m</b></div>
                    <div class="bg-slate-900 rounded p-1.5">Joint<br><b class="text-white">${cluster.joint_duration_mins}m</b></div>
                    <div class="bg-slate-900 rounded p-1.5">Saved<br><b class="text-purple-300">${cluster.hours_saved}h</b></div>
                </div>
            </div>`;
    } else if (data.maintenance_count) {
        html += '<div class="text-slate-400">Maintenance exists, but no multi-department shadow cluster was found at this station.</div>';
    } else {
        html += '<div class="text-slate-500">No loaded maintenance demand, so the optimizer does not need to create a block.</div>';
    }

    if (bestWindow) {
        html += `<div class="p-2 rounded bg-slate-900/70 border border-slate-800"><span class="text-slate-500">Largest free window:</span> <span class="font-mono text-sky-300">${escapeHtml(bestWindow.start_time)}–${escapeHtml(bestWindow.end_time)}</span> <span class="text-slate-500">(${bestWindow.duration_mins}m)</span></div>`;
    }

    if (block) {
        html += `
            <div class="p-2.5 rounded bg-emerald-500/5 border border-emerald-500/20">
                <div class="font-bold text-emerald-300"><i class="fa-solid fa-circle-check mr-1"></i>${escapeHtml(block.block_id)} scheduled</div>
                <div class="mt-1 font-mono text-white">${escapeHtml(block.date_str)} • ${escapeHtml(block.start_time_str)}–${escapeHtml(block.end_time_str)}</div>
                <div class="text-[10px] text-slate-400 mt-1">${escapeHtml(block.section_id)} • ${escapeHtml(block.block_type)} • Train delay ${block.total_train_delay_mins}m</div>
            </div>`;
    }
    box.innerHTML = html;
}

// Allow Enter key to run the station analysis.
document.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && document.activeElement?.id === 'station-search-input') {
        analyzeSelectedStation();
    }
});

// ----------------------------------------------------
// Kaggle & Real-World Indian Railways Data Handlers
// ----------------------------------------------------
let currentKaggleFile = 'stations';

async function loadKaggleStatus() {
    try {
        const res = await fetch('/api/kaggle/status').then(r => r.json());
        
        const statStations = document.getElementById('kaggle-stat-stations');
        const statTrains = document.getElementById('kaggle-stat-trains');
        const statSections = document.getElementById('kaggle-stat-sections');
        const statTasks = document.getElementById('kaggle-stat-tasks');
        const badge = document.getElementById('kaggle-active-badge');

        if (statStations) statStations.innerText = res.total_stations;
        if (statTrains) statTrains.innerText = res.total_trains;
        if (statSections) statSections.innerText = res.total_track_sections;
        if (statTasks) statTasks.innerText = res.total_maintenance_demands;

        if (badge) {
            badge.innerText = res.active_source === 'KAGGLE_REAL' ? 'Kaggle Dataset Active' : 'Default Corridor Active';
            badge.className = res.active_source === 'KAGGLE_REAL' 
                ? "px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-mono font-bold"
                : "px-2.5 py-0.5 rounded-full bg-slate-700 text-slate-300 text-xs font-mono font-bold";
        }

        const btnKaggle = document.getElementById('btn-source-kaggle');
        const btnDefault = document.getElementById('btn-source-default');
        if (btnKaggle && btnDefault) {
            if (res.active_source === 'KAGGLE_REAL') {
                btnKaggle.className = "w-full py-2 px-3 rounded-lg text-xs font-bold bg-sky-500 text-white flex items-center justify-between transition shadow-md shadow-sky-500/20";
                btnDefault.className = "w-full py-2 px-3 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 flex items-center justify-between transition";
            } else {
                btnDefault.className = "w-full py-2 px-3 rounded-lg text-xs font-bold bg-sky-500 text-white flex items-center justify-between transition shadow-md shadow-sky-500/20";
                btnKaggle.className = "w-full py-2 px-3 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 flex items-center justify-between transition";
            }
        }

        renderKaggleTable(currentKaggleFile);
    } catch (err) {
        console.error("Error loading Kaggle status:", err);
    }
}

async function switchDataSource(source) {
    try {
        const res = await fetch('/api/kaggle/switch-source', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({source: source})
        }).then(r => r.json());

        // Reload entire application state with new dataset
        await loadInitialData();
        renderDashboard();
        renderDataHub();
        renderPriorityExplain();
        populateMemoSelector();
        renderTrackMap();
        renderGanttChart();
        loadKaggleStatus();

        alert(`Active Data Source switched to: ${source === 'KAGGLE_REAL' ? 'Indian Railways Kaggle Dataset' : 'Default 150 KM HDN Corridor'}`);
    } catch (err) {
        console.error("Error switching data source:", err);
    }
}

async function fetchFromKaggleAPI() {
    const slugInput = document.getElementById('kaggle-slug-input');
    const feedback = document.getElementById('kaggle-fetch-feedback');
    const slug = slugInput ? slugInput.value : "vijayv/indian-railway-data";

    if (feedback) feedback.innerText = "Connecting to Kaggle API and downloading dataset...";

    try {
        const res = await fetch('/api/kaggle/fetch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({dataset_slug: slug})
        }).then(r => r.json());

        if (feedback) {
            feedback.innerText = res.message;
            feedback.className = res.status === 'success' ? "text-[10px] text-emerald-400 pt-1" : "text-[10px] text-amber-400 pt-1";
        }
    } catch (err) {
        console.error("Error fetching Kaggle dataset:", err);
        if (feedback) feedback.innerText = "Fetch request failed.";
    }
}

function viewKaggleFile(fileType) {
    currentKaggleFile = fileType;
    ['stations', 'trains', 'tms', 'smms', 'tdms'].forEach(f => {
        const btn = document.getElementById(`btn-kf-${f}`);
        if (btn) {
            if (f === fileType) {
                btn.className = "px-3 py-1 rounded font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30";
            } else {
                btn.className = "px-3 py-1 rounded font-bold text-slate-400 hover:text-white";
            }
        }
    });
    renderKaggleTable(fileType);
}

function renderKaggleTable(fileType) {
    const thead = document.getElementById('kaggle-table-head');
    const tbody = document.getElementById('kaggle-table-body');
    if (!thead || !tbody) return;

    if (fileType === 'stations' && appState.corridor) {
        thead.innerHTML = `<tr><th class="py-2 px-3">Code</th><th class="py-2 px-3">Station Name</th><th class="py-2 px-3">KM Distance</th><th class="py-2 px-3">Division</th></tr>`;
        tbody.innerHTML = appState.corridor.stations.map(stn => `
            <tr class="hover:bg-slate-900/60 transition">
                <td class="py-2 px-3 font-mono font-bold text-sky-400">${stn.code}</td>
                <td class="py-2 px-3 font-semibold text-slate-200">${stn.name}</td>
                <td class="py-2 px-3 font-mono text-slate-300">${stn.km} KM</td>
                <td class="py-2 px-3 font-mono text-slate-400">${escapeHtml(stn.division || 'Demo')}</td>
            </tr>
        `).join('');
    } else if (fileType === 'trains' && appState.trains) {
        thead.innerHTML = `<tr><th class="py-2 px-3">Train No</th><th class="py-2 px-3">Name</th><th class="py-2 px-3">Type</th><th class="py-2 px-3">Route</th><th class="py-2 px-3 text-right">Priority</th></tr>`;
        tbody.innerHTML = appState.trains.map(t => `
            <tr class="hover:bg-slate-900/60 transition">
                <td class="py-2 px-3 font-mono font-bold text-amber-400">${t.train_no}</td>
                <td class="py-2 px-3 font-semibold text-slate-200">${t.train_name}</td>
                <td class="py-2 px-3 font-mono text-slate-300 text-[10px]">${t.train_type}</td>
                <td class="py-2 px-3 font-mono text-slate-400">${t.origin} â†’ ${t.destination} (${t.direction})</td>
                <td class="py-2 px-3 font-mono font-bold text-right text-sky-400">Rank ${t.priority_rank}</td>
            </tr>
        `).join('');
    } else if (fileType === 'tms') {
        const tmsTasks = appState.tasks.filter(t => t.department === 'TMS');
        thead.innerHTML = `<tr><th class="py-2 px-3">Task ID</th><th class="py-2 px-3">Category</th><th class="py-2 px-3">Section</th><th class="py-2 px-3">Duration</th><th class="py-2 px-3 text-right">Safety</th></tr>`;
        tbody.innerHTML = tmsTasks.map(t => `
            <tr class="hover:bg-slate-900/60 transition">
                <td class="py-2 px-3 font-mono font-bold text-blue-400">${t.task_id}</td>
                <td class="py-2 px-3 font-semibold text-slate-200">${t.task_name}</td>
                <td class="py-2 px-3 font-mono text-slate-400">${t.section_id} (KM ${t.start_km}-${t.end_km})</td>
                <td class="py-2 px-3 font-mono text-slate-300">${t.required_duration_mins}m</td>
                <td class="py-2 px-3 font-mono font-bold text-right text-rose-400">${t.safety_criticality}/10</td>
            </tr>
        `).join('');
    } else if (fileType === 'smms') {
        const smmsTasks = appState.tasks.filter(t => t.department === 'SMMS');
        thead.innerHTML = `<tr><th class="py-2 px-3">Fault ID</th><th class="py-2 px-3">Signalling Gear</th><th class="py-2 px-3">Location</th><th class="py-2 px-3">Duration</th><th class="py-2 px-3 text-right">Disconnection</th></tr>`;
        tbody.innerHTML = smmsTasks.map(t => `
            <tr class="hover:bg-slate-900/60 transition">
                <td class="py-2 px-3 font-mono font-bold text-emerald-400">${t.task_id}</td>
                <td class="py-2 px-3 font-semibold text-slate-200">${t.task_name}</td>
                <td class="py-2 px-3 font-mono text-slate-400">${t.section_id}</td>
                <td class="py-2 px-3 font-mono text-slate-300">${t.required_duration_mins}m</td>
                <td class="py-2 px-3 font-mono font-bold text-right text-emerald-400">Form T/351</td>
            </tr>
        `).join('');
    } else {
        const tdmsTasks = appState.tasks.filter(t => t.department === 'TDMS');
        thead.innerHTML = `<tr><th class="py-2 px-3">Job ID</th><th class="py-2 px-3">OHE Job Details</th><th class="py-2 px-3">Section</th><th class="py-2 px-3">Duration</th><th class="py-2 px-3 text-right">Power Block</th></tr>`;
        tbody.innerHTML = tdmsTasks.map(t => `
            <tr class="hover:bg-slate-900/60 transition">
                <td class="py-2 px-3 font-mono font-bold text-amber-400">${t.task_id}</td>
                <td class="py-2 px-3 font-semibold text-slate-200">${t.task_name}</td>
                <td class="py-2 px-3 font-mono text-slate-400">${t.section_id}</td>
                <td class="py-2 px-3 font-mono text-slate-300">${t.required_duration_mins}m</td>
                <td class="py-2 px-3 font-mono font-bold text-right text-amber-400">25kV Cut</td>
            </tr>
        `).join('');
    }
}

