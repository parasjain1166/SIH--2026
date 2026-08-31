function officerEsc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function officerBadge(s){
 const cls={SUBMITTED:'text-sky-300 border-sky-500/30 bg-sky-500/10',UNDER_REVIEW:'text-amber-300 border-amber-500/30 bg-amber-500/10',APPROVED:'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',REJECTED:'text-red-300 border-red-500/30 bg-red-500/10',COMPLETED:'text-purple-300 border-purple-500/30 bg-purple-500/10'}[s]||'text-slate-300 border-slate-700';
 return `<span class="text-[10px] px-2 py-0.5 rounded-full border font-mono ${cls}">${officerEsc(s)}</span>`;
}

async function loadOfficerRequests(){
 const filter=document.getElementById('officer-request-filter')?.value||'ALL';
 const url='/api/officer/requests'+(filter!=='ALL'?`?status=${encodeURIComponent(filter)}`:'');
 const d=await fetch(url).then(r=>r.json());
 const c=d.counts||{};
 const set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=v||0;};
 set('req-count-total',c.total);set('req-count-submitted',c.submitted);set('req-count-review',c.under_review);set('req-count-approved',c.approved);set('req-count-rejected',c.rejected);
 const box=document.getElementById('officer-request-list'); if(!box)return;
 if(!d.requests?.length){box.innerHTML='<div class="p-4 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-500">No requests in this filter. Open Engineer Portal to submit a prototype request.</div>';return;}
 box.innerHTML=d.requests.map(r=>`
  <div class="p-4 rounded-xl border border-slate-800 bg-slate-950/70 hover:border-purple-500/40 transition">
   <div class="flex justify-between gap-3">
    <div><div class="flex flex-wrap items-center gap-2"><span class="font-mono font-bold text-purple-300">${officerEsc(r.request_id)}</span>${officerBadge(r.request_status)}<span class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">${officerEsc(r.department)}</span></div><div class="font-semibold text-white mt-1">${officerEsc(r.task_name)}</div><div class="text-[11px] text-slate-500 mt-1">${officerEsc(r.station_code)} • ${officerEsc(r.section_id)} • ${r.start_km}-${r.end_km} km • ${r.required_duration_mins} min</div><div class="text-[11px] text-slate-500">Engineer: ${officerEsc(r.engineer_name)}</div></div>
    <div class="text-right shrink-0"><div class="text-[9px] uppercase text-slate-500">AI pre-score</div><div class="text-xl font-mono font-bold text-amber-300">${Number(r.ai_priority||0).toFixed(2)}</div></div>
   </div>
   <div class="mt-3 flex items-center gap-2"><button onclick="analyzeOfficerRequest('${officerEsc(r.request_id)}')" class="px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold"><i class="fa-solid fa-magnifying-glass-chart mr-1"></i>Analyze</button>${r.officer_instruction?`<span class="text-[11px] text-emerald-300 truncate">Instruction: ${officerEsc(r.officer_instruction)}</span>`:''}</div>
  </div>`).join('');
}

async function analyzeOfficerRequest(id){
 const panel=document.getElementById('officer-analysis-panel');
 panel.innerHTML='<div class="text-amber-300"><i class="fa-solid fa-spinner fa-spin mr-2"></i>Checking AI priority, timetable and free windows...</div>';
 const res=await fetch(`/api/officer/requests/${encodeURIComponent(id)}/analyze`,{method:'POST'}); const d=await res.json();
 if(!res.ok){panel.innerHTML=`<div class="text-red-300">${officerEsc(d.error||'Analysis failed')}</div>`;return;}
 const req=d.request, ai=d.ai, comp=ai.components||{}, win=d.windows?.[0], shadow=d.shadow_cluster;
 const decidable=!['APPROVED','REJECTED','COMPLETED'].includes(req.request_status);
 panel.innerHTML=`
  <div class="flex items-center justify-between gap-2"><div><div class="font-mono font-bold text-purple-300">${officerEsc(req.request_id)}</div><div class="text-white font-semibold">${officerEsc(req.task_name)}</div></div>${officerBadge(req.request_status)}</div>
  <div class="mt-3 p-3 rounded-lg border border-amber-500/25 bg-amber-500/5"><div class="text-[9px] uppercase text-amber-400">AI Priority</div><div class="text-3xl font-mono font-bold text-white">${ai.composite_score}<span class="text-sm text-slate-500">/100</span></div><div class="text-amber-300 font-semibold">${officerEsc(ai.classification)}</div></div>
  <div class="grid grid-cols-5 gap-1 mt-3 text-center text-[9px] font-mono"><div class="p-2 bg-slate-900 rounded">Safety<br><b>${comp.safety_score}</b></div><div class="p-2 bg-slate-900 rounded">Degrade<br><b>${comp.degradation_score}</b></div><div class="p-2 bg-slate-900 rounded">Urgency<br><b>${comp.urgency_score}</b></div><div class="p-2 bg-slate-900 rounded">Traffic<br><b>${comp.traffic_score}</b></div><div class="p-2 bg-slate-900 rounded">TSR<br><b>${comp.tsr_score}</b></div></div>
  <div class="mt-3 space-y-2 text-slate-400"><div><span class="text-sky-300 font-bold">Timetable:</span> ${d.timetable.trains_checked} train movements checked on ${officerEsc(d.section.section_id)}.</div><div><span class="text-emerald-300 font-bold">Best free window:</span> ${win?`${officerEsc(win.start_time)}–${officerEsc(win.end_time)} (${win.duration_mins} min)`:'No qualifying window found'}</div><div><span class="text-purple-300 font-bold">Shadow block:</span> ${shadow?`${shadow.departments.join(' + ')} • estimated ${shadow.hours_saved} h saved`:'No multi-department request cluster yet'}</div></div>
  <div class="mt-3 p-3 rounded bg-slate-900 border border-slate-800"><div class="text-[9px] uppercase text-slate-500 mb-1">Decision trace</div>${d.decision_trace.map(x=>`<div class="py-1 border-b border-slate-800 last:border-0"><i class="fa-solid fa-check text-emerald-400 mr-1"></i>${officerEsc(x)}</div>`).join('')}</div>
  ${decidable?`<div class="mt-4 space-y-2"><textarea id="officer-note-input" rows="2" placeholder="Officer note / reason" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs text-white"></textarea><textarea id="officer-instruction-input" rows="2" placeholder="Instruction to engineer" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs text-white">Proceed as per sanctioned block and coordinate with control.</textarea><div class="flex gap-2"><button onclick="decideOfficerRequest('${officerEsc(id)}','APPROVE')" class="flex-1 px-3 py-2 rounded bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold">Approve</button><button onclick="decideOfficerRequest('${officerEsc(id)}','REJECT')" class="flex-1 px-3 py-2 rounded bg-red-500 hover:bg-red-400 text-white font-bold">Reject</button></div></div>`:`<div class="mt-4 text-slate-500">Decision already recorded.</div>`}
 `;
 await loadOfficerRequests();
}

async function decideOfficerRequest(id,decision){
 const officer=document.getElementById('officer-name')?.value.trim()||'Control Officer';
 const note=document.getElementById('officer-note-input')?.value.trim()||'';
 const instruction=document.getElementById('officer-instruction-input')?.value.trim()|| (decision==='APPROVE'?'Proceed as per sanctioned block and coordinate with control.':'Request not sanctioned.');
 if(!confirm(`${decision==='APPROVE'?'Approve':'Reject'} ${id}?`))return;
 const res=await fetch(`/api/officer/requests/${encodeURIComponent(id)}/decision`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,officer_name:officer,note,instruction})});
 const d=await res.json(); if(!res.ok){alert(d.error||'Decision failed');return;}
 await loadOfficerRequests(); await analyzeOfficerRequest(id);
 // Existing dashboard data may have changed after approval.
 if(decision==='APPROVE' && typeof loadInitialData==='function'){ try{await loadInitialData();}catch(e){} }
}

document.addEventListener('DOMContentLoaded',()=>{loadOfficerRequests().catch(()=>{});});
