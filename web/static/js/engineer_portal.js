const $ = id => document.getElementById(id);
let stations = [];

function esc(v){ return String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function csvList(v){ return String(v||'').split(',').map(x=>x.trim()).filter(Boolean); }

async function loadStations(){
  const d = await fetch('/api/stations').then(r=>r.json());
  stations = d.stations || [];
  $('eng-station').innerHTML = stations.map(s=>`<option value="${esc(s.code)}">${esc(s.name)} (${esc(s.code)})</option>`).join('');
  const preferred = stations.find(s=>s.code==='GZB');
  if(preferred) $('eng-station').value='GZB';
  await loadSections();
}

async function loadSections(){
  const code=$('eng-station').value;
  const d=await fetch('/api/station-sections?station='+encodeURIComponent(code)).then(r=>r.json());
  const list=d.sections||[];
  $('eng-section').innerHTML=list.map(s=>`<option value="${esc(s.section_id)}">${esc(s.section_id)} • ${esc(s.line_type)} • ${s.start_km}-${s.end_km} km</option>`).join('');
  const st=stations.find(x=>x.code===code);
  if(st){ $('eng-start-km').value=Number(st.km).toFixed(1); $('eng-end-km').value=Number(st.km).toFixed(1); }
}

function applyDeptDefaults(){
  const d=$('eng-dept').value;
  $('eng-traffic').checked=true;
  $('eng-power').checked=d==='TDMS';
  $('eng-disconnection').checked=d==='SMMS';
  loadEngineerRequests();
}

async function submitRequest(ev){
  ev.preventDefault();
  $('submit-status').textContent='Saving to SQLite...';
  const tsr=$('eng-tsr').value.trim();
  const payload={
    engineer_name:$('eng-name').value.trim(), department:$('eng-dept').value,
    station_code:$('eng-station').value, section_id:$('eng-section').value,
    task_name:$('eng-task').value.trim(), start_km:Number($('eng-start-km').value), end_km:Number($('eng-end-km').value),
    required_duration_mins:Number($('eng-duration').value), min_duration_mins:Math.min(60,Number($('eng-duration').value)),
    safety_criticality:Number($('eng-safety').value), asset_degradation_score:Number($('eng-deg').value),
    urgency_days_overdue:Number($('eng-overdue').value), gmt_accumulated:Number($('eng-gmt').value),
    speed_restriction_if_deferred_kmh:tsr?Number(tsr):null, horizon:$('eng-horizon').value,
    requires_traffic_block:$('eng-traffic').checked, requires_power_block:$('eng-power').checked,
    requires_st_disconnection:$('eng-disconnection').checked, is_shadow_eligible:true,
    required_machines:csvList($('eng-machines').value), required_gangs:[]
  };
  const res=await fetch('/api/engineer/requests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const d=await res.json();
  if(!res.ok){ $('submit-status').textContent=d.error||'Submit failed'; return; }
  $('submit-status').textContent=`${d.request.request_id} sent to officer.`;
  $('ai-preview').classList.remove('hidden');
  $('ai-preview').innerHTML=`<div class="font-bold text-amber-300 mb-1">AI pre-triage</div><div class="text-2xl font-mono font-bold text-white">${d.ai_preview.composite_score}/100</div><div class="text-slate-400">${esc(d.ai_preview.classification)}</div><div class="mt-2 text-slate-500">Officer still makes the final decision.</div>`;
  $('eng-task').value='';
  await loadEngineerRequests();
}

function statusBadge(s){
  const cls={SUBMITTED:'text-sky-300 border-sky-500/30 bg-sky-500/10',UNDER_REVIEW:'text-amber-300 border-amber-500/30 bg-amber-500/10',APPROVED:'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',REJECTED:'text-red-300 border-red-500/30 bg-red-500/10',COMPLETED:'text-purple-300 border-purple-500/30 bg-purple-500/10'}[s]||'text-slate-300 border-slate-700 bg-slate-900';
  return `<span class="text-[10px] font-mono px-2 py-0.5 rounded-full border ${cls}">${esc(s)}</span>`;
}

async function loadEngineerRequests(){
  const dept=$('eng-dept')?.value||'TMS';
  const d=await fetch('/api/engineer/requests?department='+encodeURIComponent(dept)).then(r=>r.json());
  const box=$('engineer-requests');
  if(!d.requests?.length){ box.innerHTML='<div class="p-4 rounded-lg border border-slate-800 bg-slate-950/50">No requests for this department yet.</div>'; return; }
  box.innerHTML=d.requests.map(r=>`
    <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div class="flex flex-col md:flex-row md:items-start justify-between gap-3">
        <div><div class="flex items-center gap-2 flex-wrap"><span class="font-mono text-sky-300 font-bold">${esc(r.request_id)}</span>${statusBadge(r.request_status)}<span class="text-xs text-slate-500">${esc(r.station_code)} • ${esc(r.section_id)}</span></div><div class="font-semibold text-white mt-1">${esc(r.task_name)}</div><div class="text-xs text-slate-500 mt-1">Submitted by ${esc(r.engineer_name)} • ${esc(r.submitted_at)}</div></div>
        <div class="text-right"><div class="text-[10px] uppercase text-slate-500">AI priority</div><div class="text-xl font-mono font-bold text-amber-300">${Number(r.ai_priority||0).toFixed(2)}</div></div>
      </div>
      ${r.officer_instruction?`<div class="mt-3 p-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 text-xs"><span class="text-emerald-300 font-bold">Officer instruction:</span> ${esc(r.officer_instruction)}</div>`:''}
      ${r.officer_note?`<div class="mt-2 text-xs text-slate-400"><b>Officer note:</b> ${esc(r.officer_note)}</div>`:''}
      ${r.request_status==='APPROVED'?`<button onclick="markComplete('${esc(r.request_id)}')" class="mt-3 px-3 py-1.5 text-xs rounded bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold">Mark Work Completed</button>`:''}
    </div>`).join('');
}

async function markComplete(id){
  const detail=prompt('Completion note (optional):','Work completed as instructed.') ?? '';
  const res=await fetch(`/api/engineer/requests/${encodeURIComponent(id)}/complete`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({engineer_name:$('eng-name').value.trim()||'Engineer',detail})});
  const d=await res.json(); if(!res.ok){alert(d.error||'Unable to complete');return;} loadEngineerRequests();
}

$('eng-station').addEventListener('change',loadSections);
$('eng-dept').addEventListener('change',applyDeptDefaults);
$('engineer-form').addEventListener('submit',submitRequest);
loadStations().then(()=>{applyDeptDefaults();});
