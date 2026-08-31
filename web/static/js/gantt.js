/**
 * RailBlock AI - Multi-Horizon Interactive Gantt Timeline
 */

let currentGanttHorizon = 'DAILY';

function initGantt() {
    renderGanttChart();
}

function setGanttHorizon(horizon) {
    currentGanttHorizon = horizon;
    
    // Update button styles
    ['daily', 'weekly', 'monthly'].forEach(h => {
        const btn = document.getElementById(`gantt-btn-${h}`);
        if (btn) {
            if (h === horizon.toLowerCase()) {
                btn.className = "px-3 py-1 rounded-md text-xs font-semibold bg-sky-500 text-white transition";
            } else {
                btn.className = "px-3 py-1 rounded-md text-xs font-semibold text-slate-400 hover:text-white transition";
            }
        }
    });

    renderGanttChart();
}

function renderGanttChart() {
    const container = document.getElementById('gantt-chart-container');
    if (!container || !appState.schedules) return;

    if (currentGanttHorizon === 'DAILY') {
        renderDailyGantt(container);
    } else if (currentGanttHorizon === 'WEEKLY') {
        renderWeeklyGantt(container);
    } else {
        renderMonthlyGantt(container);
    }
}

// 1. Daily 24-Hour Timeline Gantt
function renderDailyGantt(container) {
    const blocks = appState.schedules.daily_plan.blocks;
    const sections = appState.corridor.sections;

    // Group blocks by section_id
    const sectionIds = [...new Set(sections.map(s => s.section_id))];

    let html = `
        <div class="bg-slate-950 p-4 rounded-xl border border-rail-border overflow-x-auto select-none">
            <!-- 24-Hour Time Header Ruler -->
            <div class="flex items-center border-b border-slate-800 pb-2 mb-3 min-w-[900px]">
                <div class="w-48 text-xs font-mono font-bold text-slate-400">Track Section (UP/DN)</div>
                <div class="flex-1 grid grid-cols-12 text-[10px] font-mono text-slate-400 text-center">
                    <div>00:00</div><div>02:00</div><div>04:00</div><div>06:00</div>
                    <div>08:00</div><div>10:00</div><div>12:00</div><div>14:00</div>
                    <div>16:00</div><div>18:00</div><div>20:00</div><div>22:00</div>
                </div>
            </div>

            <!-- Gantt Rows -->
            <div class="space-y-2 min-w-[900px]">
    `;

    // Filter to sections that have scheduled blocks or notable traffic
    const activeSections = sections.filter(s => 
        blocks.some(b => b.section_id === s.section_id) || s.current_tsr_kmh !== null
    );

    activeSections.forEach(sec => {
        const secBlocks = blocks.filter(b => b.section_id === sec.section_id);

        html += `
            <div class="flex items-center h-12 bg-slate-900/40 hover:bg-slate-900/80 rounded border border-slate-800/80 px-2 transition relative">
                <!-- Section Name Label -->
                <div class="w-44 pr-2 truncate">
                    <span class="text-xs font-bold text-slate-200 block truncate">${sec.section_id}</span>
                    <span class="text-[10px] font-mono text-slate-400">KM ${sec.start_km}-${sec.end_km} (${sec.line_type})</span>
                </div>

                <!-- Timeline Bar Background Container -->
                <div class="flex-1 h-8 bg-slate-950/60 rounded border border-slate-800 relative overflow-hidden">
                    <!-- Hourly Guidelines -->
                    <div class="absolute inset-0 grid grid-cols-12 pointer-events-none divide-x divide-slate-900/60">
                        <div></div><div></div><div></div><div></div>
                        <div></div><div></div><div></div><div></div>
                        <div></div><div></div><div></div><div></div>
                    </div>
        `;

        // Render Block Bars in this row
        secBlocks.forEach(b => {
            const leftPct = (b.start_time_mins / 1440.0) * 100.0;
            const widthPct = (b.duration_mins / 1440.0) * 100.0;

            let barBg = 'bg-sky-600 border-sky-400 text-sky-100';
            if (b.is_shadow_block) {
                barBg = 'bg-gradient-to-r from-purple-700 via-indigo-600 to-purple-800 border-purple-400 text-purple-100 shadow-block-glow';
            } else if (b.block_type === 'POWER_BLOCK') {
                barBg = 'bg-amber-600 border-amber-400 text-amber-100';
            } else if (b.block_type === 'DISCONNECTION') {
                barBg = 'bg-emerald-600 border-emerald-400 text-emerald-100';
            }

            const deptBadges = b.departments_involved.map(d => `<span class="text-[8px] font-mono px-1 py-0.2 bg-black/40 rounded">${d}</span>`).join(' ');

            html += `
                <div class="absolute top-1 bottom-1 rounded border ${barBg} px-2 flex items-center justify-between text-xs cursor-pointer shadow-md z-10 transition hover:scale-[1.02]"
                     style="left: ${leftPct}%; width: ${Math.max(widthPct, 7.5)}%;"
                     onclick="inspectBlock('${b.block_id}')"
                     title="${b.block_id} | ${b.start_time_str}-${b.end_time_str} | ${b.tasks.length} Tasks | Click for Official IR Memo">
                    <div class="flex items-center space-x-1 truncate">
                        ${b.is_shadow_block ? '<i class="fa-solid fa-layer-group text-[10px] text-purple-200"></i>' : '<i class="fa-solid fa-screwdriver-wrench text-[10px]"></i>'}
                        <span class="font-mono font-bold text-[10px] truncate">${b.start_time_str}-${b.end_time_str}</span>
                    </div>
                    <div class="flex items-center space-x-1">
                        ${deptBadges}
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    });

    html += `
            </div>
        </div>
    `;

    container.innerHTML = html;
}

// 2. Weekly 7-Day Rolling Calendar Grid
function renderWeeklyGantt(container) {
    const weekly = appState.schedules.weekly_plan;
    const blocks = weekly.blocks;

    let html = `
        <div class="space-y-4">
            <div class="flex items-center justify-between text-xs text-slate-400 bg-slate-900/60 p-3 rounded-lg border border-rail-border">
                <span>Rolling Window: <strong class="text-white font-mono">${weekly.start_date} â†’ ${weekly.end_date}</strong></span>
                <span>Total Possession: <strong class="text-sky-400 font-mono">${weekly.total_hours} Hours</strong> across ${weekly.total_blocks} Blocks</span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    `;

    // Group blocks by date
    const dateGroups = {};
    blocks.forEach(b => {
        if (!dateGroups[b.date_str]) dateGroups[b.date_str] = [];
        dateGroups[b.date_str].push(b);
    });

    Object.keys(dateGroups).sort().forEach((dateStr, idx) => {
        const dayBlocks = dateGroups[dateStr];
        html += `
            <div class="bg-slate-900/60 p-4 rounded-xl border border-rail-border space-y-3">
                <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                    <div class="flex items-center space-x-2">
                        <span class="px-2 py-0.5 rounded font-mono font-bold bg-sky-500/20 text-sky-300 text-[10px]">Day ${idx + 1}</span>
                        <span class="font-bold text-slate-200 text-xs font-mono">${dateStr}</span>
                    </div>
                    <span class="text-[10px] text-slate-400 font-mono">${dayBlocks.length} Blocks</span>
                </div>

                <div class="space-y-2">
                    ${dayBlocks.map(b => `
                        <div class="p-2.5 rounded-lg ${b.is_shadow_block ? 'bg-purple-950/40 border-purple-800/60' : 'bg-slate-950 border-slate-800'} border text-xs cursor-pointer hover:border-sky-500 transition"
                             onclick="inspectBlock('${b.block_id}')">
                            <div class="flex items-center justify-between mb-1">
                                <span class="font-bold font-mono ${b.is_shadow_block ? 'text-purple-300' : 'text-sky-300'}">${b.block_id}</span>
                                <span class="font-mono text-[10px] text-slate-400">${b.start_time_str} - ${b.end_time_str} (${b.duration_mins}m)</span>
                            </div>
                            <div class="text-[11px] text-slate-300 font-medium truncate">${b.section_id}</div>
                            <div class="flex items-center justify-between mt-2 text-[10px]">
                                <span class="text-slate-400 font-mono">${b.assigned_resources.slice(0, 2).join(', ') || 'Track Gang'}</span>
                                ${b.is_shadow_block ? '<span class="text-purple-400 font-mono font-bold">SHADOW JOINT</span>' : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    });

    html += `
            </div>
        </div>
    `;

    container.innerHTML = html;
}

// 3. Monthly 30-Day Master Schedule Grid
function renderMonthlyGantt(container) {
    const monthly = appState.schedules.monthly_plan;
    const blocks = monthly.blocks;

    let html = `
        <div class="space-y-4">
            <div class="flex items-center justify-between text-xs text-slate-400 bg-slate-900/60 p-3 rounded-lg border border-rail-border">
                <span>30-Day Master Cyclic Schedule: <strong class="text-white font-mono">${monthly.start_date} â†’ ${monthly.end_date}</strong></span>
                <span>Total Cyclic Capacity: <strong class="text-purple-400 font-mono">${monthly.total_hours} Hours</strong> (${monthly.shadow_blocks} Shadow Blocks)</span>
            </div>

            <div class="overflow-x-auto bg-slate-950 rounded-xl border border-rail-border p-4">
                <table class="w-full text-xs text-left text-slate-300">
                    <thead class="bg-slate-900/80 text-slate-400 uppercase font-mono border-b border-rail-border">
                        <tr>
                            <th class="py-2.5 px-3">Date</th>
                            <th class="py-2.5 px-3">Block ID</th>
                            <th class="py-2.5 px-3">Section Limits</th>
                            <th class="py-2.5 px-3">Time Window</th>
                            <th class="py-2.5 px-3">Type</th>
                            <th class="py-2.5 px-3">Primary Heavy Machinery</th>
                            <th class="py-2.5 px-3 text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800">
                        ${blocks.map(b => `
                            <tr class="hover:bg-slate-900/60 transition">
                                <td class="py-2.5 px-3 font-mono font-bold text-slate-300">${b.date_str}</td>
                                <td class="py-2.5 px-3 font-mono font-semibold ${b.is_shadow_block ? 'text-purple-400' : 'text-sky-400'}">${b.block_id}</td>
                                <td class="py-2.5 px-3 font-medium text-slate-200">${b.section_id} (KM ${b.start_km}-${b.end_km})</td>
                                <td class="py-2.5 px-3 font-mono text-slate-300">${b.start_time_str} - ${b.end_time_str} (${b.duration_mins}m)</td>
                                <td class="py-2.5 px-3">
                                    <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold ${b.is_shadow_block ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' : 'bg-sky-500/20 text-sky-300'}">
                                        ${b.is_shadow_block ? 'INTEGRATED SHADOW' : b.block_type}
                                    </span>
                                </td>
                                <td class="py-2.5 px-3 font-mono text-slate-400 text-[11px]">${b.assigned_resources.join(', ') || 'Specialist P-Way Gang'}</td>
                                <td class="py-2.5 px-3 text-right">
                                    <button onclick="inspectBlock('${b.block_id}')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-sky-400 text-[10px] font-bold rounded transition">
                                        View Memo
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;

    container.innerHTML = html;
}
