// Job Radar: permanent Inbox learning reanalysis control.
(function(){
  let requestId=null,timer=null;
  function button(){return document.getElementById('applyLearningButton')}
  function setLabel(text,disabled=false){const b=button();if(b){b.textContent=text;b.disabled=disabled}}
  async function poll(){
    if(!requestId)return;
    const {data:r,error}=await sb.from('learning_reanalysis_requests').select('status,reviewed_count,archived_count,error_message').eq('id',requestId).single();
    if(error)return;
    if(r.status==='DONE'){
      clearInterval(timer);timer=null;setLabel(`🧠 Aplicar aprendizaje · ${r.archived_count||0} eliminadas`);requestId=null;await loadData();
    }else if(r.status==='ERROR'){
      clearInterval(timer);timer=null;setLabel('🧠 Aplicar aprendizaje');requestId=null;alert('No se pudo aplicar el aprendizaje: '+(r.error_message||'error desconocido'));
    }else setLabel(r.status==='RUNNING'?'🧠 IA reevaluando…':'🧠 Reevaluación en cola…',true);
  }
  window.applyLearning=async function(){
    if(userActive!=='PENDING')return;
    setLabel('🧠 Preparando reevaluación…',true);
    const {data:id,error}=await sb.rpc('request_learning_reanalysis');
    if(error){setLabel('🧠 Aplicar aprendizaje');alert('No se pudo iniciar: '+error.message);return}
    requestId=id;await poll();timer=setInterval(poll,5000);
  };
  function mount(){
    const panel=document.querySelector('.filter-panel');if(!panel||button())return;
    const row=document.createElement('div');row.className='toolbar';row.id='learningTools';
    const b=document.createElement('button');b.id='applyLearningButton';b.textContent='🧠 Aplicar aprendizaje';b.onclick=window.applyLearning;
    row.appendChild(b);panel.appendChild(row);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
