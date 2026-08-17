/*
 * SQCS checklist upgrade
 * - Editable checklist items
 * - Automatic FAIL / PASS / EXCELLENT
 * - Progress + completion
 * - Collapsible subsections (collapsed by default)
 * - Expand All / Collapse All
 * - Remembers open/closed state locally
 */

function _checklistPayload(){
  const payload=JSON.parse(JSON.stringify(window.SQCS_CHECKLIST||{}));
  document.querySelectorAll('.check-item').forEach(row=>{
    const s=row.dataset.section, sub=row.dataset.subsection, id=row.dataset.id;
    if(!s || !sub || !id)return;
    payload[s]=payload[s]||{}; payload[s][sub]=payload[s][sub]||{};
    payload[s][sub][id]=payload[s][sub][id]||{};
    const title=row.querySelector('.editable-title')?.textContent?.trim() ||
      row.querySelector('.check-copy strong')?.textContent?.trim() || id;
    payload[s][sub][id].description=title;
    payload[s][sub][id].response=row.dataset.response||'';
    payload[s][sub][id].feedback=row.querySelector('.feedback')?.value||'';
    payload[s][sub][id].last_modified=new Date().toISOString();
  });
  window.SQCS_CHECKLIST=payload;
  return payload;
}

function setResponse(btn){
  const row=btn.closest('.check-item');
  if(!row)return;
  row.querySelectorAll('.response-btn').forEach(b=>b.classList.remove('selected'));
  btn.classList.add('selected');
  row.dataset.response=btn.dataset.response||'';
  scheduleSave();
  updateSubsectionSummary(row.closest('.checklist-subsection'));
}

function hydrateChecklist(){
  document.querySelectorAll('.check-item').forEach(row=>{
    const data=window.SQCS_CHECKLIST?.[row.dataset.section]?.[row.dataset.subsection]?.[row.dataset.id];
    if(!data)return;
    row.dataset.response=data.response||'';
    row.querySelectorAll('.response-btn').forEach(b=>b.classList.toggle(
      'selected',(data.response||'').toLowerCase()===String(b.dataset.response||'').toLowerCase()
    ));
    const feedback=row.querySelector('.feedback');
    if(feedback && data.feedback != null)feedback.value=data.feedback;
    const title=row.querySelector('.editable-title');
    if(title && data.description)title.textContent=data.description;
  });
  document.querySelectorAll('.checklist-subsection').forEach(updateSubsectionSummary);
}

let saveTimer;
function scheduleSave(){
  clearTimeout(saveTimer);
  const s=document.getElementById('saveState');
  if(s)s.textContent='● Unsaved changes';
  saveTimer=setTimeout(saveChecklist,700);
}

async function saveChecklist(){
  if(!window.SQCS_SAVE_URL)return;
  const payload=_checklistPayload();
  const el=document.getElementById('saveState');
  if(el)el.textContent='● Saving…';
  try{
    const res=await fetch(window.SQCS_SAVE_URL,{
      method:'POST',
      headers:{'Content-Type':'application/json','X-CSRF-Token':window.SQCS_CSRF},
      body:JSON.stringify(payload)
    });
    const data=await res.json();
    if(!res.ok||!data.ok)throw new Error(data.error||'Save failed');
    if(el)el.textContent='● All changes saved';
    if(data.stats)updateChecklistLevel(data.stats);
    document.querySelectorAll('.checklist-subsection').forEach(updateSubsectionSummary);
  }catch(e){
    if(el)el.textContent='● Save failed';
    console.error(e);
  }
}

function updateChecklistLevel(s){
  s=s||{};
  const total=s.total_items||0, completed=total-(s.unanswered_count||0);
  const completion=total?Math.round(completed/total*100):0;
  const level=(s.fail_count||0)>0?'FAIL':(
    total>0&&s.unanswered_count===0&&s.excellent_count===total?'EXCELLENT':'PASS'
  );
  const t=document.getElementById('levelText'),
        p=document.getElementById('progressText'),
        sum=document.getElementById('saveSummary');
  if(t)t.textContent=level;
  if(p)p.textContent=`${completed}/${total} completed · ${completion}%`;
  if(sum)sum.textContent=`Level ${level} · ${completed}/${total} completed · ${completion}%`;
}

/* ---------------- Collapsible checklist subsections ---------------- */

const SQCS_COLLAPSE_KEY='sqcs.checklist.subsections.v1';

function subsectionKey(box){
  return [
    location.pathname,
    box?.dataset.section||'',
    box?.dataset.subsection||box?.querySelector('.checklist-subsection-title')?.textContent?.trim()||''
  ].join('::');
}

function readCollapseState(){
  try{return JSON.parse(localStorage.getItem(SQCS_COLLAPSE_KEY)||'{}')||{};}
  catch(_){return {};}
}

function writeCollapseState(state){
  try{localStorage.setItem(SQCS_COLLAPSE_KEY,JSON.stringify(state));}catch(_){/* storage may be unavailable */}
}

function subsectionItems(box){
  return [...box.querySelectorAll(':scope > .check-item')];
}

function subsectionLevel(box){
  const items=subsectionItems(box);
  const total=items.length;
  const fail=items.filter(r=>String(r.dataset.response||'').toLowerCase()==='fail').length;
  const excellent=items.filter(r=>String(r.dataset.response||'').toLowerCase()==='excellent').length;
  const completed=items.filter(r=>String(r.dataset.response||'').trim()!=='').length;
  if(fail)return 'FAIL';
  if(total && completed===total && excellent===total)return 'EXCELLENT';
  return 'PASS';
}

function updateSubsectionSummary(box){
  if(!box)return;
  const items=subsectionItems(box);
  const total=items.length;
  const completed=items.filter(r=>String(r.dataset.response||'').trim()!=='').length;
  const pct=total?Math.round(completed/total*100):0;
  const level=subsectionLevel(box);
  const levelEl=box.querySelector(':scope > .checklist-subsection-header .checklist-subsection-level');
  const progressEl=box.querySelector(':scope > .checklist-subsection-header .checklist-subsection-progress');
  if(levelEl){
    levelEl.textContent=level;
    levelEl.dataset.level=level;
  }
  if(progressEl)progressEl.textContent=`${completed}/${total} completed · ${pct}%`;
}

function setSubsectionCollapsed(box,collapsed,persist=true){
  if(!box)return;
  box.classList.toggle('is-collapsed',collapsed);
  const body=box.querySelector(':scope > .checklist-subsection-body');
  const toggle=box.querySelector(':scope > .checklist-subsection-header .checklist-subsection-toggle');
  if(body)body.hidden=collapsed;
  if(toggle){
    toggle.setAttribute('aria-expanded',String(!collapsed));
    toggle.textContent=collapsed?'▸':'▾';
  }
  if(persist){
    const state=readCollapseState();
    state[subsectionKey(box)]=collapsed;
    writeCollapseState(state);
  }
}

function toggleSubsection(box){
  setSubsectionCollapsed(box,!box.classList.contains('is-collapsed'));
}

function createSubsectionHeader(box,title){
  const header=document.createElement('div');
  header.className='checklist-subsection-header';
  header.innerHTML=`
    <button type="button" class="checklist-subsection-toggle" aria-expanded="false" aria-label="Expand subsection">▸</button>
    <div class="checklist-subsection-heading">
      <div class="checklist-subsection-title"></div>
      <div class="checklist-subsection-progress"></div>
    </div>
    <span class="checklist-subsection-level" data-level="PASS">PASS</span>`;
  header.querySelector('.checklist-subsection-title').textContent=title;
  header.addEventListener('click',e=>{
    if(e.target.closest('.checklist-subsection-toggle') || e.currentTarget===header)toggleSubsection(box);
  });
  box.prepend(header);
}

function buildCollapsibleSubsections(){
  const rows=[...document.querySelectorAll('.check-item')];
  if(!rows.length)return;

  /* If the existing template already provides subsection wrappers, use them. */
  const existing=[...document.querySelectorAll('.checklist-subsection')];
  if(existing.length){
    existing.forEach(box=>{
      let body=box.querySelector(':scope > .checklist-subsection-body');
      if(!body){
        body=document.createElement('div');
        body.className='checklist-subsection-body';
        [...box.children].filter(c=>!c.classList.contains('checklist-subsection-header')).forEach(c=>body.appendChild(c));
        box.appendChild(body);
      }
      if(!box.querySelector(':scope > .checklist-subsection-header')){
        const title=box.dataset.subsection||'Checklist subsection';
        createSubsectionHeader(box,title);
      }
      updateSubsectionSummary(box);
    });
  }else{
    /* Build wrappers from the data-subsection values used by the existing rows. */
    const groups=new Map();
    rows.forEach(row=>{
      const parent=row.parentElement;
      const key=`${row.dataset.section||''}::${row.dataset.subsection||'General'}`;
      if(!groups.has(key))groups.set(key,{parent,section:row.dataset.section||'',sub:row.dataset.subsection||'General',rows:[]});
      groups.get(key).rows.push(row);
    });

    groups.forEach(group=>{
      const box=document.createElement('section');
      box.className='checklist-subsection';
      box.dataset.section=group.section;
      box.dataset.subsection=group.sub;
      group.parent.insertBefore(box,group.rows[0]);
      const body=document.createElement('div');
      body.className='checklist-subsection-body';
      box.appendChild(body);
      group.rows.forEach(row=>body.appendChild(row));
      createSubsectionHeader(box,group.sub.replace(/^__custom__$/,'Custom items'));
      updateSubsectionSummary(box);
    });
  }

  const state=readCollapseState();
  document.querySelectorAll('.checklist-subsection').forEach(box=>{
    const key=subsectionKey(box);
    /* New subsections start collapsed. Existing saved state wins. */
    setSubsectionCollapsed(box,Object.prototype.hasOwnProperty.call(state,key)?!!state[key]:true,false);
    updateSubsectionSummary(box);
  });
}

function expandAllSubsections(){
  document.querySelectorAll('.checklist-subsection').forEach(box=>setSubsectionCollapsed(box,false));
}

function collapseAllSubsections(){
  document.querySelectorAll('.checklist-subsection').forEach(box=>setSubsectionCollapsed(box,true));
}

function addChecklistCollapseControls(){
  const host=document.querySelector('[data-checklist-controls]') ||
             document.querySelector('.checklist-header') ||
             document.querySelector('.checklist') ||
             document.querySelector('main');
  if(!host || document.getElementById('checklistCollapseControls'))return;
  const controls=document.createElement('div');
  controls.id='checklistCollapseControls';
  controls.className='checklist-collapse-controls';
  controls.innerHTML=`
    <button type="button" class="btn btn-small btn-ghost" onclick="expandAllSubsections()">Expand All</button>
    <button type="button" class="btn btn-small btn-ghost" onclick="collapseAllSubsections()">Collapse All</button>`;
  host.prepend(controls);
}

function addChecklistCollapseStyles(){
  if(document.getElementById('sqcsChecklistCollapseStyles'))return;
  const style=document.createElement('style');
  style.id='sqcsChecklistCollapseStyles';
  style.textContent=`
    .checklist-collapse-controls{display:flex;gap:.5rem;flex-wrap:wrap;margin:0 0 1rem}
    .checklist-subsection{margin:0 0 1rem;border:1px solid var(--border-color,#d8dee8);border-radius:12px;overflow:hidden;background:var(--card-bg,#fff)}
    .checklist-subsection-header{display:flex;align-items:center;gap:.65rem;min-height:58px;padding:.7rem .85rem;cursor:pointer;user-select:none}
    .checklist-subsection-header:hover{background:rgba(127,127,127,.06)}
    .checklist-subsection-toggle{width:34px;height:34px;flex:0 0 34px;border:0;background:transparent;font-size:1.25rem;cursor:pointer}
    .checklist-subsection-heading{min-width:0;flex:1}
    .checklist-subsection-title{font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .checklist-subsection-progress{font-size:.82rem;opacity:.72;margin-top:2px}
    .checklist-subsection-level{font-size:.75rem;font-weight:800;letter-spacing:.04em;padding:.28rem .55rem;border-radius:999px}
    .checklist-subsection-level[data-level="FAIL"]{background:#fee2e2;color:#b91c1c}
    .checklist-subsection-level[data-level="PASS"]{background:#fef3c7;color:#92400e}
    .checklist-subsection-level[data-level="EXCELLENT"]{background:#dcfce7;color:#166534}
    .checklist-subsection-body{padding:.2rem .85rem .85rem}
    .checklist-subsection.is-collapsed .checklist-subsection-body{display:none}
    @media(max-width:640px){
      .checklist-subsection-header{min-height:64px;padding:.7rem .65rem}
      .checklist-subsection-title{white-space:normal}
      .checklist-subsection-progress{font-size:.76rem}
      .checklist-subsection-level{font-size:.68rem}
    }
    @media(prefers-color-scheme:dark){
      .checklist-subsection-level[data-level="FAIL"]{background:#451a1a;color:#fecaca}
      .checklist-subsection-level[data-level="PASS"]{background:#422006;color:#fde68a}
      .checklist-subsection-level[data-level="EXCELLENT"]{background:#052e16;color:#bbf7d0}
    }
  `;
  document.head.appendChild(style);
}

function addChecklistItem(){
  const sections=[...document.querySelectorAll('.custom-items')];
  if(!sections.length)return;
  const box=sections[0], section=box.dataset.section, id='CUSTOM-'+Date.now();
  const row=document.createElement('div');
  row.className='check-item';
  row.dataset.section=section;
  row.dataset.subsection='__custom__';
  row.dataset.id=id;
  row.dataset.standard='0';
  row.innerHTML=`<div class="check-copy"><span class="item-id">${id}</span><div><strong contenteditable="true" class="editable-title">New checklist item</strong></div></div>
  <div class="response-grid"><button type="button" class="response-btn" data-response="Excellent" onclick="setResponse(this)">Excellent</button><button type="button" class="response-btn" data-response="Need Review" onclick="setResponse(this)">Need Review</button><button type="button" class="response-btn" data-response="Fail" onclick="setResponse(this)">Fail</button></div>
  <textarea class="feedback" rows="2" placeholder="Feedback / evidence / action note…"></textarea>
  <div class="action-strip"><button type="button" class="btn btn-small btn-ghost" onclick="moveItem(this,-1)">↑</button><button type="button" class="btn btn-small btn-ghost" onclick="moveItem(this,1)">↓</button><button type="button" class="btn btn-small btn-danger" onclick="deleteChecklistItem(this)">🗑️ Delete</button></div>`;
  box.appendChild(row);
  row.querySelector('.editable-title')?.focus();
  scheduleSave();
  updateSubsectionSummary(row.closest('.checklist-subsection'));
}

function deleteChecklistItem(btn){
  const row=btn.closest('.check-item');
  const box=row?.closest('.checklist-subsection');
  row?.remove();
  scheduleSave();
  updateSubsectionSummary(box);
}

function moveItem(btn,dir){
  const row=btn.closest('.check-item'), parent=row?.parentElement;
  if(!row||!parent)return;
  if(dir<0&&row.previousElementSibling)parent.insertBefore(row,row.previousElementSibling);
  if(dir>0&&row.nextElementSibling)parent.insertBefore(row.nextElementSibling,row);
  scheduleSave();
  updateSubsectionSummary(row.closest('.checklist-subsection'));
}

document.addEventListener('input',e=>{
  if(e.target.matches('.feedback,.editable-title')){
    scheduleSave();
    updateSubsectionSummary(e.target.closest('.checklist-subsection'));
  }
});

document.addEventListener('DOMContentLoaded',()=>{
  addChecklistCollapseStyles();
  buildCollapsibleSubsections();
  addChecklistCollapseControls();
  if(window.SQCS_CHECKLIST)hydrateChecklist();
  document.querySelectorAll('.checklist-subsection').forEach(updateSubsectionSummary);
});
