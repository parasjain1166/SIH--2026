/**
 * RailBlock AI - Interactive GIS & Track Corridor Schematic
 */

function initTrackMap() {
    renderTrackMap();
}

function renderTrackMap() {
    const container = document.getElementById('track-schematic-svg-container');
    if (!container || !appState.corridor) return;

    const stations = appState.corridor.stations;
    const sections = appState.corridor.sections;
    const dailyBlocks = appState.schedules ? appState.schedules.daily_plan.blocks : [];

    const width = 1100;
    const height = 320;
    const paddingX = 50;
    const trackUpY = 110;
    const trackDnY = 190;
    const scaleX = (width - paddingX * 2) / 150.0;

    let svgHtml = `
        <svg viewBox="0 0 ${width} ${height}" class="w-full h-full select-none">
            <!-- Background Grid -->
            <defs>
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" stroke-width="0.5"/>
                </pattern>
                <filter id="glow-purple" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over"/>
                </filter>
                <filter id="glow-red" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over"/>
                </filter>
            </defs>
            <rect width="${width}" height="${height}" fill="#090d16" />
            <rect width="${width}" height="${height}" fill="url(#grid)" />

            <!-- Corridor Label & KM Ruler Header -->
            <text x="${paddingX}" y="35" fill="#94a3b8" font-size="12" font-weight="bold" font-family="monospace">
                DELHI - ALIGARH - TUNDLA HIGH-DENSITY CORRIDOR (150 KM)
            </text>
            <line x1="${paddingX}" y1="50" x2="${width - paddingX}" y2="50" stroke="#334155" stroke-width="1" />
    `;

    // KM Markers along ruler
    for (let km = 0; km <= 150; km += 25) {
        const x = paddingX + km * scaleX;
        svgHtml += `
            <line x1="${x}" y1="46" x2="${x}" y2="54" stroke="#64748b" stroke-width="1.5" />
            <text x="${x}" y="65" fill="#64748b" font-size="9" font-family="monospace" text-anchor="middle">KM ${km}</text>
        `;
    }

    // Draw Main Track Baseline (UP & DN)
    svgHtml += `
        <!-- UP Line Track Base -->
        <text x="12" y="${trackUpY + 4}" fill="#38bdf8" font-size="10" font-family="monospace" font-weight="bold">UP</text>
        <line x1="${paddingX}" y1="${trackUpY}" x2="${width - paddingX}" y2="${trackUpY}" stroke="#1e293b" stroke-width="6" stroke-linecap="round" />
        
        <!-- DN Line Track Base -->
        <text x="12" y="${trackDnY + 4}" fill="#38bdf8" font-size="10" font-family="monospace" font-weight="bold">DN</text>
        <line x1="${paddingX}" y1="${trackDnY}" x2="${width - paddingX}" y2="${trackDnY}" stroke="#1e293b" stroke-width="6" stroke-linecap="round" />
    `;

    // Draw Sections & Active TSRs
    sections.forEach(sec => {
        const x1 = paddingX + sec.start_km * scaleX;
        const x2 = paddingX + sec.end_km * scaleX;
        const y = sec.line_type === "UP" ? trackUpY : trackDnY;
        const isTsr = sec.current_tsr_kmh !== null;

        const strokeColor = isTsr ? "#ef4444" : "#0284c7";
        const strokeWidth = isTsr ? "4" : "3";
        const filter = isTsr ? 'filter="url(#glow-red)"' : '';

        svgHtml += `
            <line class="track-segment" 
                  x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" 
                  stroke="${strokeColor}" stroke-width="${strokeWidth}" stroke-linecap="round"
                  ${filter}
                  onclick="inspectSection('${sec.section_id}')">
                <title>${sec.section_id} (KM ${sec.start_km}-${sec.end_km}) | Speed: ${isTsr ? 'TSR ' + sec.current_tsr_kmh + ' km/h' : sec.max_speed_kmh + ' km/h'}</title>
            </line>
        `;

        // If TSR, add cautionary marker
        if (isTsr) {
            const midX = (x1 + x2) / 2;
            svgHtml += `
                <g transform="translate(${midX}, ${y - 12})">
                    <rect x="-16" y="-7" width="32" height="14" rx="3" fill="#ef4444" />
                    <text x="0" y="3" fill="#ffffff" font-size="8" font-family="monospace" font-weight="bold" text-anchor="middle">${sec.current_tsr_kmh}k</text>
                </g>
            `;
        }
    });

    // Draw Scheduled Maintenance Blocks on Tracks
    dailyBlocks.forEach(b => {
        const x1 = paddingX + b.start_km * scaleX;
        const x2 = paddingX + b.end_km * scaleX;
        const y = b.track_line === "UP" ? trackUpY : trackDnY;
        const blockWidth = Math.max(16, x2 - x1);
        const rectColor = b.is_shadow_block ? "#a855f7" : "#3b82f6";

        svgHtml += `
            <g transform="translate(${x1}, ${y - 16})" class="cursor-pointer" onclick="inspectBlock('${b.block_id}')">
                <rect x="0" y="0" width="${blockWidth}" height="32" rx="4" fill="${rectColor}" fill-opacity="0.3" stroke="${rectColor}" stroke-width="2" stroke-dasharray="3,3" filter="url(#glow-purple)" />
                <text x="${blockWidth / 2}" y="36" fill="#c084fc" font-size="8" font-family="monospace" font-weight="bold" text-anchor="middle">${b.is_shadow_block ? 'SHADOW' : 'BLOCK'}</text>
            </g>
        `;
    });

    // Draw Stations & Interlocking Nodes
    stations.forEach(stn => {
        const x = paddingX + stn.km * scaleX;

        // Station Vertical Mast & Circle Nodes on both lines
        svgHtml += `
            <line x1="${x}" y1="80" x2="${x}" y2="225" stroke="#334155" stroke-width="1" stroke-dasharray="2,2" />
            
            <!-- UP Station Node -->
            <g class="station-node" onclick="inspectStation('${stn.code}')">
                <circle cx="${x}" cy="${trackUpY}" r="${stn.has_yard ? 5.5 : 4}" fill="#0f172a" stroke="#38bdf8" stroke-width="2" />
            </g>

            <!-- DN Station Node -->
            <g class="station-node" onclick="inspectStation('${stn.code}')">
                <circle cx="${x}" cy="${trackDnY}" r="${stn.has_yard ? 5.5 : 4}" fill="#0f172a" stroke="#38bdf8" stroke-width="2" />
            </g>

            <!-- Station Label -->
            <text x="${x}" y="245" fill="#e2e8f0" font-size="9.5" font-weight="bold" font-family="monospace" text-anchor="middle">${stn.code}</text>
            <text x="${x}" y="258" fill="#64748b" font-size="8" font-family="monospace" text-anchor="middle">${stn.km}k</text>
        `;

        if (stn.has_yard) {
            svgHtml += `
                <rect x="${x - 10}" y="263" width="20" height="9" rx="2" fill="#1e293b" />
                <text x="${x}" y="270" fill="#38bdf8" font-size="6.5" font-family="monospace" text-anchor="middle">YARD</text>
            `;
        }
    });

    // Traction Substations (TSS 25kV) Markers
    const substations = [
        {km: 25.4, code: "TSS_GZB"},
        {km: 42.1, code: "TSS_DER"},
        {km: 89.4, code: "TSS_KRJ"},
        {km: 131.2, code: "TSS_ALJN"}
    ];

    substations.forEach(tss => {
        const x = paddingX + tss.km * scaleX;
        svgHtml += `
            <g transform="translate(${x}, 290)">
                <circle cx="0" cy="0" r="4" fill="#f59e0b" />
                <text x="0" y="10" fill="#f59e0b" font-size="7.5" font-family="monospace" text-anchor="middle">${tss.code}</text>
            </g>
        `;
    });

    svgHtml += `</svg>`;
    container.innerHTML = svgHtml;
}

function inspectSection(sectionId) {
    if (!appState.corridor) return;
    const sec = appState.corridor.sections.find(s => s.section_id === sectionId);
    if (!sec) return;

    const card = document.getElementById('section-inspector-card');
    const badge = document.getElementById('inspect-sec-badge');
    const title = document.getElementById('inspect-sec-title');
    const details = document.getElementById('inspect-sec-details');

    if (card && badge && title && details) {
        badge.innerText = sec.section_id;
        title.innerText = `${sec.start_station} â†’ ${sec.end_station} (${sec.line_type} Line, KM ${sec.start_km} - ${sec.end_km})`;
        
        details.innerHTML = `
            <div>
                <span class="text-slate-400 block text-[10px]">Speed Limit:</span>
                <span class="font-bold text-white font-mono">${sec.max_speed_kmh} km/h ${sec.current_tsr_kmh ? '<span class="text-rose-400">(TSR: ' + sec.current_tsr_kmh + ' km/h)</span>' : ''}</span>
            </div>
            <div>
                <span class="text-slate-400 block text-[10px]">Signaling System:</span>
                <span class="font-bold text-slate-200">${sec.signaling_system}</span>
            </div>
            <div>
                <span class="text-slate-400 block text-[10px]">Daily Traffic Density:</span>
                <span class="font-bold text-sky-400 font-mono">${sec.daily_train_density} Trains/Day (${sec.line_capacity_pct}%)</span>
            </div>
            <div>
                <span class="text-slate-400 block text-[10px]">25kV Substation:</span>
                <span class="font-bold text-amber-400 font-mono">${sec.substations.join(', ') || 'N/A'}</span>
            </div>
        `;
        card.classList.remove('hidden');
    }
}

function inspectStation(stnCode) {
    const sec = appState.corridor.sections.find(s => s.start_station === stnCode);
    if (sec) inspectSection(sec.section_id);
}

function inspectBlock(blockId) {
    switchTab('memos');
    const select = document.getElementById('memo-block-select');
    if (select) {
        select.value = blockId;
        loadBlockMemo();
    }
}

function closeInspector() {
    const card = document.getElementById('section-inspector-card');
    if (card) card.classList.add('hidden');
}
