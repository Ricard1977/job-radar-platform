// Job Radar frontend enhancements: learning status, live counters and salary filter.
(function(){
  let requestId=null,timer=null,statusTimer=null,minSalary=0;
  const originalAiMatch=window.aiMatch;
  const originalRefresh=window.refreshFilterButtons;
  function button(){return document.getElementById('applyLearningButton')}
  function status(){return document.getElementById('learningStatus')}
  function setButton(disabled=false){const b=button();if(b){b.textContent='🧠 Aplicar aprendizaje';b.disabled=disabled}}
  function setStatus(text='',kind=''){
    const e=status();if(!e)return;e.textContent=text;e.dataset.kind=kind;
    if(statusTimer){clearTimeout(statusTimer);statusTimer=null}
    if(text&&(kind==='done'||kind==='error'))statusTimer=setTimeout(()=>{if(status())status().textContent=''},10000);
  }
  function salaryNumber(text){if(!text)return null;const nums=String(text).replace(/\./g,'').replace(/,/g,'.').match(/\d+(?:\.\d+)?/g);if(!nums)return null;let n=Number(nums[0]);if(/\bk\b/i.test(text)&&n<1000)n*=1000;if(/hour|hora/i.test(text))n*=1760;if(/month|mes/i.test(text))n*=12;return Number.isFinite(n)?n:null}
  function salaryMatch(j){if(!minSalary)return true;const n=salaryNumber(j.salary);return n==null||n>=minSalary}
  window.aiMatch=function(j){return originalAiMatch(j)&&salaryMatch(j)};
  function userCount(key){return data.filter(j=>{const u=s(j.id);if(key==='PENDING')return (!u.interest&&!u.applied)||u.interest==='no';if(key==='MY_INTEREST')return u.interest==='yes';if(key==='APPLIED')return u.applied;return true}).length}
  function aiCount(key){return data.filter(j=>userMatch(j)&&salaryMatch(j)&&(key==='ALL'||(key==='NO_AI'?!j.decision:j.decision===key))).length}
  window.refreshFilterButtons=function(){originalRefresh();[...$('userFilters').children].forEach(b=>{const k=b.dataset.key;b.textContent=`${userLabels[k]} (${userCount(k)})`});[...$('aiFilters').children].forEach(b=>{const k=b.dataset.key;b.textContent=`${aiLabels[k]} (${aiCount(k)})`})};
  async function poll(){
    if(!requestId)return;
    const {data:r,error}=await sb.from('learning_reanalysis_requests').select('status,reviewed_count,archived_count,error_message').eq('id',requestId).single();
    if(error){setStatus('No se pudo consultar el estado','error');return}
    if(r.status==='DONE'){clearInterval(timer);timer=null;setButton(false);setStatus(`✓ ${r.archived_count||0} eliminadas · ${r.reviewed_count||0} revisadas`,'done');requestId=null;await loadData()}
    else if(r.status==='ERROR'){clearInterval(timer);timer=null;setButton(false);setStatus('Error al aplicar aprendizaje','error');requestId=null}
    else{setButton(true);setStatus(r.status==='RUNNING'?'IA reevaluando…':'Reevaluación en cola…','working')}
  }
  window.applyLearning=async function(){if(userActive!=='PENDING'||requestId)return;setButton(true);setStatus('Preparando reevaluación…','working');const {data:id,error}=await sb.rpc('request_learning_reanalysis');if(error){setButton(false);setStatus('No se pudo iniciar: '+error.message,'error');return}requestId=id;await poll();timer=setInterval(poll,5000)};
  function mount(){
    const panel=document.querySelector('.filter-panel');if(!panel)return;
    let row=document.getElementById('learningTools');if(!row){row=document.createElement('div');row.className='toolbar';row.id='learningTools';panel.appendChild(row)}
    let b=button();if(!b){b=document.createElement('button');b.id='applyLearningButton';b.onclick=window.applyLearning;row.appendChild(b)}setButton(false);
    let st=status();if(!st){st=document.createElement('span');st.id='learningStatus';st.style.cssText='align-self:center;font-size:13px;color:#687386;min-height:18px';row.appendChild(st)}
    if(!document.getElementById('salaryTools')){const salaryRow=document.createElement('div');salaryRow.className='toolbar';salaryRow.id='salaryTools';salaryRow.innerHTML='<span style="align-self:center;font-size:12px;font-weight:700;color:#7b8493">SUELDO MÍNIMO</span><select id="salaryFilter" style="border:1px solid #d6dce7;background:#fff;padding:9px 13px;border-radius:999px"><option value="0">Todos</option><option value="40000">40.000 €</option><option value="50000">50.000 €</option><option value="60000">60.000 €</option><option value="70000">70.000 €</option><option value="80000">80.000 €</option><option value="100000">100.000 €</option></select><span style="align-self:center;font-size:12px;color:#7b8493">Sin salario publicado: se mantiene visible</span>';panel.appendChild(salaryRow);document.getElementById('salaryFilter').onchange=e=>{minSalary=Number(e.target.value)||0;updateStats();render()}}
    refreshFilterButtons();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
