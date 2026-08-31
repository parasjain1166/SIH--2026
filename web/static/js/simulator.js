/**
 * RailBlock AI - Interactive What-If Disruption Simulator
 */

async function runSimulationScenario(scenarioType) {
    const descBox = document.getElementById('sim-scenario-description');
    const badge = document.getElementById('sim-status-badge');
    if (descBox) descBox.innerText = "Simulating dynamic railway disruption and running AI Constraint Solver...";
    if (badge) {
        badge.className = "text-xs px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-mono animate-pulse";
        badge.innerText = "Computing Re-optimization...";
    }

    let payload = {
        scenario: scenarioType,
        params: {}
    };

    if (scenarioType === 'INJECT_EMERGENCY_DEFECT') {
        payload.params = {
            department: "TMS",
            section_id: "SEC_GZB_MIU_UP",
            km: 29.5
        };
    } else if (scenarioType === 'TRAIN_DELAY_CASCADE') {
        payload.params = {
            train_no: "22436",
            delay_mins: 60
        };
    } else if (scenarioType === 'SILOED_MODE') {
        payload.scenario = "SILOED_VS_INTEGRATED_COMPARISON";
        payload.params = { enable_shadow: false };
    } else if (scenarioType === 'SHADOW_MODE') {
        payload.scenario = "SILOED_VS_INTEGRATED_COMPARISON";
        payload.params = { enable_shadow: true };
    }

    try {
        const res = await fetch('/api/simulate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }).then(r => r.json());

        renderSimulationResults(res);
    } catch (err) {
        console.error("Simulation error:", err);
        if (descBox) descBox.innerText = "Simulation request failed.";
    }
}

function renderSimulationResults(simData) {
    const descBox = document.getElementById('sim-scenario-description');
    const badge = document.getElementById('sim-status-badge');
    const kpiBlocks = document.getElementById('sim-kpi-blocks');
    const kpiShadow = document.getElementById('sim-kpi-shadow');
    const kpiSaved = document.getElementById('sim-kpi-saved');
    const kpiDelay = document.getElementById('sim-kpi-delay');
    const blockList = document.getElementById('sim-block-list');

    if (descBox) descBox.innerText = simData.description;
    if (badge) {
        badge.className = "text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono";
        badge.innerText = "Schedule Re-optimized âœ“";
    }

    const summary = simData.kpis.summary;
    if (kpiBlocks) kpiBlocks.innerText = summary.scheduled_blocks;
    if (kpiShadow) kpiShadow.innerText = summary.shadow_blocks;
    if (kpiSaved) kpiSaved.innerText = `${summary.hours_saved_via_shadow}h`;
    if (kpiDelay) kpiDelay.innerText = `${summary.total_train_delay_mins}m`;

    if (blockList && simData.blocks) {
        blockList.innerHTML = simData.blocks.map(b => `
            <div class="p-2.5 rounded-lg ${b.is_shadow_block ? 'bg-purple-950/40 border-purple-800/60' : 'bg-slate-900/80 border-slate-800'} border flex items-center justify-between text-xs">
                <div>
                    <div class="flex items-center space-x-2">
                        <span class="font-bold font-mono ${b.is_shadow_block ? 'text-purple-300' : 'text-sky-300'}">${b.block_id}</span>
                        <span class="font-semibold text-slate-200">${b.section_id} (${b.track_line} Line)</span>
                    </div>
                    <div class="text-[10px] text-slate-400 font-mono mt-0.5">
                        ${b.start_time_str} - ${b.end_time_str} (${b.duration_mins}m) | Tasks: ${b.tasks.map(t => '[' + t.department + ' ' + t.task_category + ']').join(', ')}
                    </div>
                </div>
                <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold ${b.is_shadow_block ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' : 'bg-sky-500/20 text-sky-300'}">
                    ${b.is_shadow_block ? 'SHADOW JOINT' : b.block_type}
                </span>
            </div>
        `).join('');
    }
}
