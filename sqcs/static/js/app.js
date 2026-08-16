function toggleSidebar(){document.getElementById('sidebar')?.classList.toggle('open')}
function showFile(input){document.getElementById('fileName').textContent=input.files?.[0]?.name || 'Choose a document'}

document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('.flash').forEach((el)=>setTimeout(()=>el.remove(),7000));
  if(window.SQCS_CHECKLIST){ hydrateChecklist(); }
});

function hydrateChecklist(){
  document.querySelectorAll('.check-item').forEach((row)=>{
    const section=row.dataset.section, sub=row.dataset.subsection, id=row.dataset.id;
    const data=window.SQCS_CHECKLIST?.[section]?.[sub]?.[id];
    if(!data) return;
    row.dataset.response=data.response||'';
    row.querySelectorAll('.response-btn').forEach(btn=>btn.classList.toggle('selected',btn.dataset.response.toLowerCase()===(data.response||'').toLowerCase()));
    const feedback=row.querySelector('.feedback'); if(feedback) feedback.value=data.feedback||'';
  });
}
function setResponse(btn){
  const row=btn.closest('.check-item');
  row.querySelectorAll('.response-btn').forEach(b=>b.classList.remove('selected')); btn.classList.add('selected'); row.dataset.response=btn.dataset.response;
  scheduleSave();
}
let saveTimer;
function scheduleSave(){ clearTimeout(saveTimer); document.getElementById('saveState').textContent='● Unsaved changes'; document.getElementById('saveState').classList.add('dirty'); saveTimer=setTimeout(saveChecklist,900); }
async function saveChecklist(){
  if(!window.SQCS_SAVE_URL) return;
  const payload=JSON.parse(JSON.stringify(window.SQCS_CHECKLIST||{}));
  document.querySelectorAll('.check-item').forEach(row=>{
    const s=row.dataset.section, sub=row.dataset.subsection, id=row.dataset.id;
    payload[s]=payload[s]||{}; payload[s][sub]=payload[s][sub]||{}; payload[s][sub][id]=payload[s][sub][id]||{description:row.querySelector('.check-copy strong')?.textContent||'',response:'',feedback:'',last_modified:null};
    payload[s][sub][id].response=row.dataset.response||'';
    payload[s][sub][id].feedback=row.querySelector('.feedback')?.value||'';
    payload[s][sub][id].last_modified=new Date().toISOString();
  });
  window.SQCS_CHECKLIST=payload;
  const el=document.getElementById('saveState'); el.textContent='● Saving…';
  try{
    const res=await fetch(window.SQCS_SAVE_URL,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':window.SQCS_CSRF},body:JSON.stringify(payload)});
    const data=await res.json(); if(!res.ok||!data.ok) throw new Error(data.error||'Save failed');
    document.getElementById('saveState').textContent='● All changes saved'; el.classList.remove('dirty');
    const sb=document.getElementById('saveSummary'); if(sb) sb.textContent=`Saved · ${data.stats.excellent_count} excellent · ${data.stats.fail_count} fail · ${data.stats.unanswered_count} unanswered`;
  }catch(err){ el.textContent='● Save failed — retrying'; el.classList.add('error'); console.error(err); }
}
document.addEventListener('input',(e)=>{if(e.target.matches('.feedback')) scheduleSave()});

async function importChecklistFile(input){ const file=input.files?.[0]; if(!file||!window.SQCS_IMPORT_URL)return; const data=new FormData(); data.append('json_file',file); data.append('_csrf',window.SQCS_CSRF); try{ const res=await fetch(window.SQCS_IMPORT_URL,{method:'POST',body:data}); if(!res.ok) throw new Error('Import failed'); window.location.reload(); }catch(e){ alert(e.message||'Import failed'); } }
