const $ = id => document.getElementById(id);
const symbols = {s:'♠',h:'♥',d:'♦',c:'♣'};
const streetNames = {preflop:'Pré-flop',flop:'Flop',turn:'Turn',river:'River'};
const offline = !!window.LAB_DATA;
const labConfig = window.LAB_DATA?.metadata || window.LAB_CONFIG || {};
const nvtMode = !!labConfig.nvt;
const actionLabels = {fold:'Fold',call:'Call',check:'Check',raise:'Raise',three_bet:'3bet',four_bet:'4bet',all_in:'All-in',three_bet_shove:'3bet all-in',four_bet_shove:'4bet all-in',limp:'Limp'};
let index=0, phase=0, running=false, busy=false, timer=null, current=null;
let records=[], epoch=0, complete=false, controlMode='automatic', revision=0, switching=false;
let resolved=new Set();

function card(c,hide=false) {
  if(!c) return '<div class="card ghost">·</div>';
  return `<div class="card ${hide?'back':c[1]}"><span>${c[0]==='T'?'10':c[0]}</span><span class="suit">${symbols[c[1]]}</span></div>`;
}
function log(message,type='info',data=null) {
  records.push({at:new Date().toISOString(),index,phase,controlMode,type,message,data});
  if(records.length===1) $('logs').textContent='';
  const el=document.createElement('div');el.className='log';
  const time=document.createElement('time');time.textContent=new Date().toLocaleTimeString('pt-BR');
  el.append(time,document.createTextNode(message));$('logs').append(el);$('logs').scrollTop=$('logs').scrollHeight;
}
function buttonNames() {
  if(nvtMode) return current?.reading.hero_buttons?.map(b=>[b.action,b.raw_text]) || [];
  return index===1||index===2 ? [['fold','Fold'],['check','Check'],['bet','Bet 4 BB']]
    : [['fold','Fold'],['call','Call 2,5 BB'],['raise','Raise 8 BB']];
}
function paintScene(event) {
  const fallbackBoards=[[],['7h','As','Ts'],['7h','As','Ts','2h'],['7h','As','Ts','2h','3c'],['7h','As','Ts','2h','3c']];
  const state=event?.state||{hero:['5c','2s'],board:fallbackBoards[index]||[],street:['preflop','flop','turn','river','river'][index]||'river',pot_bb:[9.6,12.1,12.1,24.1,48.1][index]||48.1};
  $('hero').classList.remove('folded');
  $('heroCards').innerHTML=state.hero.map(c=>card(c,$('obscure').checked)).join('');
  $('board').innerHTML=Array.from({length:5},(_,i)=>card(state.board[i])).join('');
  $('street').textContent=streetNames[state.street].toUpperCase();
  $('pot').textContent=state.pot_bb.toLocaleString('pt-BR')+' BB';
  $('counter').textContent=String(Math.min(index+1,5)).padStart(2,'0')+' / 05';
  if(nvtMode) {
    if(!event) {
      $('heroCards').innerHTML=card(null)+card(null);
      $('board').innerHTML=Array.from({length:5},()=>card(null)).join('');
      $('pot').textContent='—';
    }
    document.querySelectorAll('.seat').forEach(el=>el.hidden=true);
    const area=document.querySelector('.tablearea');area.classList.add('nvt');
    let seats=$('nvtSeats');if(!seats){seats=document.createElement('div');seats.id='nvtSeats';seats.className='nvt-seats';area.prepend(seats);}
    seats.textContent='';
    if(event) for(const [position,stack] of Object.entries(event.state.table_stacks)) {
      if(position===event.state.position) continue;
      const el=document.createElement('div');el.textContent=position+' · '+stack+' BB';seats.append(el);
    }
    document.querySelector('.heroname').textContent=event?'HERO · '+event.state.position+' · range de referência 25 BB':'Aguardando cenário NVT · 9-max';
    $('street').textContent='PRÉ-FLOP · 9-MAX';
  }
  $('buttons').textContent='';
  for(const [action,label] of buttonNames()) {
    const b=document.createElement('button');b.textContent=label;b.dataset.action=action;b.disabled=true;
    b.onclick=()=>act(action,'human');$('buttons').append(b);
  }
}
function usableButton(action) {
  const b=current?.reading.hero_buttons?.find(x=>x.action===action);
  return b && (['fold','check'].includes(action) || (b.unit==='BB' && Number.isFinite(b.amount)));
}
function controls() {
  $('play').disabled=switching||complete;
  $('play').textContent=running?'Ⅱ Pausar':controlMode==='manual'||controlMode==='paused'?'▶ Retomar automático':'▶ '+(phase||index?'Continuar automático':'Iniciar simulação');
  $('manual').disabled=switching||complete;
  $('manual').textContent=controlMode==='manual'?'Atualizar leitura manual':'Assumir controle';
  $('reset').disabled=switching;
  $('next').disabled=switching||busy||running||complete||controlMode==='paused'||(controlMode==='manual'&&phase!==4);
  $('next').textContent=controlMode==='manual'?'Próximo cenário manual':'Avançar uma etapa';
  $('obscure').disabled=busy||switching||phase>0;
  $('controlState').textContent={automatic:'AUTOMÁTICO',manual:'MANUAL · VOCÊ DECIDE',paused:'PAUSADO · SEM AÇÕES'}[controlMode];
  $('evaluate').disabled=controlMode!=='manual'||busy||switching||!current?.grades||phase===4;
  for(const b of $('buttons').children) b.disabled=!(controlMode==='manual'&&!busy&&!switching&&phase===3&&!resolved.has(index)&&usableButton(b.dataset.action));
}
function mark(p) {for(let i=0;i<4;i++) $('p'+i).classList.toggle('current',i===p);}
function halt() {running=false;clearTimeout(timer);}
function schedule() {clearTimeout(timer);if(running&&!busy&&!switching&&!complete&&controlMode==='automatic') timer=setTimeout(advance,Number($('speed').value));}
function resetFields() {
  ['readHero','readBoard','readStreet','latency'].forEach(id=>$(id).textContent='—');
  $('choice').textContent='Aguardando nova leitura';$('decision').classList.remove('warning');
  $('reason').textContent='Roteiro demonstrativo; ranges reais ainda não importados.';mark(-1);
  $('rangePanel').hidden=true;$('grade').textContent='';
  if(nvtMode) $('reason').textContent='Aguardando consulta ao pacote NVT validado.';
}
function showRange() {
  if(!current?.range_decision)return;
  $('rangePanel').hidden=false;$('rangeMix').textContent='';$('grade').textContent='';
  const result=current.range_decision;
  for(const item of result.mix||[]) {
    const el=document.createElement('span');el.textContent=(actionLabels[item.action]||item.action)+' '+(item.frequency*100).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%';$('rangeMix').append(el);
  }
  $('rangeNode').textContent=result.provenance?result.provenance.node_id+' · motor '+result.provenance.engine_commit+' · pacote '+result.provenance.package_sha256.slice(0,12)+'…':result.reason;
  const selected=current.range_selection;
  $('rangeSelection').textContent=selected?'Sorteio reproduzível do mix: '+(actionLabels[selected.action]||selected.action)+'. Semente fixa para repetir o teste; frequências originais preservadas.':'Sem seleção: contexto ou leitura pendente.';
  $('rangeAnswer').textContent='';
  for(const action of current.legal_range_actions||[]) {
    const option=document.createElement('option');option.value=action;option.textContent=actionLabels[action]||action;$('rangeAnswer').append(option);
  }
}
function showGrade(grade) {
  if(!grade)return;
  const text=grade.correct===true?'Escolha aceita pelo range':grade.correct===false?'Escolha fora do critério do range':'Avaliação pendente';
  $('grade').textContent=text+(grade.ev_loss!=null?' · perda de EV '+grade.ev_loss.toFixed(4)+' '+grade.ev_unit:' · EV da escolha indisponível ou não avaliado');
}
async function evaluateAnswer() {
  if(controlMode!=='manual'||busy||switching||!current)return;
  const localEpoch=epoch,action=$('rangeAnswer').value;busy=true;controls();
  try {
    const result=offline?{status:'evaluated',actor:'human',executed:false,action,grade:current.grades[action],observation:current.observation}
      :await fetchJSON('/api/answer',{token:current.token,action});
    if(localEpoch!==epoch)return;
    if(result.status==='evaluated'){showGrade(result.grade);log('Resposta manual avaliada: '+action+' · nenhum clique aplicado.','manual_answer',result);}
    else log(result.reason,'blocked',result);
  } catch(error){log(error.message,'error');}
  finally{if(localEpoch===epoch){busy=false;controls();}}
}
function showReading() {
  $('readHero').textContent=current.reading.hero?.join(' · ')||'Pendente';
  $('readBoard').textContent=current.reading.board?.join(' · ')||'Sem cartas reconhecidas';
  $('readStreet').textContent=streetNames[current.reading.street]||'Desconhecida';
  $('latency').textContent=current.optical_seconds.toFixed(3)+' s';
}
async function fetchJSON(path,body) {
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!response.ok) throw Error(await response.text());return response.json();
}
function finish() {
  complete=true;halt();$('status').textContent='Roteiro concluído';
  $('explanation').textContent='Exporte o diário ou reinicie. Cada situação deste roteiro é independente.';
  log('Roteiro concluído.','finished');controls();
}
async function changeControl(mode,{reset=false,start=true}={}) {
  if(switching) return;
  halt();epoch++;const localEpoch=epoch;current=null;busy=false;switching=true;controls();
  try {
    if(!offline) {
      const result=await fetchJSON('/api/control',{mode,reset});revision=result.revision;
      resolved=new Set(result.resolved_scenarios);
    } else {revision++;if(reset) resolved.clear();}
    if(localEpoch!==epoch) return;
    if(reset) {index=0;phase=0;complete=false;records=[];$('logs').textContent='Nova sessão pronta.';}
    controlMode=mode;phase=0;resetFields();$('thumb').hidden=true;$('hash').textContent='Aguardando nova captura.';
    log('Controle: '+{automatic:'automático',manual:'manual',paused:'pausado'}[mode]+' · decisões pendentes invalidadas.','control',{mode,revision});
    if(mode==='paused') {
      $('status').textContent='Simulação pausada';$('explanation').textContent='Nenhuma ação nova será aplicada. Assuma o controle ou retome o automático.';
    } else {
      if(resolved.has(index)) index++;
      if(index>=5) {finish();return;}
      paintScene();
      $('status').textContent=mode==='manual'?'Preparando controle manual':'Preparando nova leitura';
      $('explanation').textContent=offline?'A evidência gravada será carregada novamente.':'Uma captura nova será processada pelo OCR.';
    }
  } catch(error) {
    controlMode='paused';$('status').textContent='Controle bloqueado';$('explanation').textContent=error.message;log(error.message,'error');
  } finally {switching=false;controls();}
  if(!complete&&controlMode!=='paused'&&(start||controlMode==='manual')) {
    running=controlMode==='automatic';controls();await advance();
  }
}
async function advance() {
  if(busy||switching||complete||controlMode==='paused') return;
  busy=true;controls();const localEpoch=epoch;
  try {
    if(phase===0) {
      mark(0);$('status').textContent='Capturando a mesa';
      const result=offline?structuredClone(window.LAB_DATA[$('obscure').checked?'blocked':'normal'][index])
        :await fetchJSON('/api/observe',{index,obscure:$('obscure').checked,revision});
      if(localEpoch!==epoch) return;
      if(result.status==='cancelled'||result.status==='failed') {halt();throw Error(result.reason);}
      current=result;current.controlRevision=revision;paintScene(current);
      showRange();
      $('thumb').src=current.image;$('thumb').hidden=false;$('hash').textContent='SHA-256 '+current.observation.frame_sha256.slice(0,18)+'…';
      log('Captura · geração '+current.observation.generation,'capture',{sha256:current.observation.frame_sha256,revision});
      phase=1;
      if(controlMode==='manual') {
        showReading();mark(3);phase=3;$('status').textContent='Você está no controle';
        $('choice').textContent='ESCOLHA UM BOTÃO NA MESA';$('decision').classList.remove('warning');
        $('reason').textContent='O motor não executará nenhuma ação enquanto você estiver no modo manual.';
        $('explanation').textContent='Escolha Fold, Call, Raise, Check ou Bet entre os botões disponíveis.';
      }
    } else if(phase===1) {
      mark(1);showReading();$('status').textContent='Leitura óptica concluída';
      $('explanation').textContent='Cartas e botões reconhecidos. O contexto do roteiro é identificado separadamente.';
      log('OCR: Hero '+(current.reading.hero?.join(' ')||'pendente'),'reading',current.reading);phase=2;
    } else if(phase===2) {
      mark(2);const valid=current.decision.status==='found';$('decision').classList.toggle('warning',!valid);
      $('choice').textContent=valid?current.decision.options[0].action.toUpperCase():'AÇÃO BLOQUEADA';
      $('reason').textContent=valid?(nvtMode?'Seleção do range NVT. Você pode assumir o controle antes da execução.':'Política demo-1. Você pode assumir o controle antes da execução.'):current.decision.reason;
      $('status').textContent=valid?'Política encontrada':'Leitura incompleta';
      log(valid?'Decisão: '+$('choice').textContent:'Ação automática bloqueada.','decision',
        {...current.decision,range_decision:current.range_decision,range_selection:current.range_selection});phase=3;
    } else if(phase===3&&controlMode==='automatic') {
      mark(3);
      if(current.decision.status==='found') {await act(current.decision.options[0].action,'engine');return;}
      log('Execução bloqueada: '+current.decision.reason,'blocked');phase=4;
    } else if(phase===4) {
      index++;if(index>=5) {finish();return;}
      phase=0;current=null;resetFields();paintScene();
      if(controlMode==='manual') {busy=false;await advance();return;}
    }
  } catch(error) {halt();$('status').textContent='Falha na simulação';$('explanation').textContent=error.message;log(error.message,'error');}
  finally {if(localEpoch===epoch) {busy=false;controls();schedule();}}
}
async function act(action,actor) {
  const localEpoch=epoch;
  if(!current||phase!==3||switching||current.controlRevision!==revision||resolved.has(index)) return;
  if((actor==='engine'&&controlMode!=='automatic')||(actor==='human'&&(controlMode!=='manual'||busy))) return;
  busy=true;controls();
  try {
    let outcome;
    if(offline) {
      if(!usableButton(action)) outcome={status:'blocked',reason:'Botão ou valor indisponível.'};
      else if(actor==='engine') outcome={...current.execution,actor};
      else {const b=current.reading.hero_buttons.find(x=>x.action===action);outcome={status:'applied',target:'simulator_only',action,sizing_bb:b.amount,actor};}
    } else outcome=await fetchJSON('/api/apply',{token:current.token,actor,action});
    if(localEpoch!==epoch) return;
    if(outcome.status==='applied') {
      resolved.add(index);const button=$('buttons').querySelector(`[data-action="${action}"]`);button?.classList.add('hit');
      if(current.grades){outcome.grade=current.grades[action];showGrade(outcome.grade);}
      if(action==='fold') $('hero').classList.add('folded');
      $('status').textContent=(actor==='human'?'Você: ':'Motor: ')+action.toUpperCase()+' aplicado';
      $('explanation').textContent='Cenário encerrado. A próxima situação do roteiro é independente; não recalcula sua linha estratégica.';
      log((actor==='human'?'VOCÊ':'MOTOR')+' acionou '+action.toUpperCase(),'action',
        {...outcome,actor,revision,observation:current.observation});phase=4;
    } else {
      log(outcome.reason,'blocked',outcome);$('status').textContent='Ação bloqueada';
      $('explanation').textContent=outcome.reason;halt();
      if(outcome.cause==='expired_source') {current=null;phase=0;resetFields();}
    }
  } catch(error) {halt();log(error.message,'error');}
  finally {if(localEpoch===epoch) {busy=false;controls();schedule();}}
}
$('play').onclick=()=>running?changeControl('paused'):changeControl('automatic');
$('manual').onclick=()=>changeControl('manual');
$('evaluate').onclick=evaluateAnswer;
$('next').onclick=advance;
$('reset').onclick=()=>changeControl('automatic',{reset:true,start:false});
$('obscure').onchange=()=>paintScene(current);$('speed').onchange=schedule;
$('evidence').onclick=()=>{if(!current)return;$('fullImage').src=current.image;const copy={...current};delete copy.image;$('raw').textContent=JSON.stringify(copy,null,2);$('dialog').showModal();};
$('thumb').onclick=$('evidence').onclick;$('close').onclick=()=>$('dialog').close();
$('download').onclick=()=>{const blob=new Blob([JSON.stringify({mode:offline?'recorded_execution_replay':'local_live_ocr',policy:nvtMode?'NVT-preflop-'+labConfig.engine_commit:'demo-1-not-trainer',events:records},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='visualpilot-simulacao.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
$('mode').textContent=offline?'REPLAY INTERATIVO · OCR REAL GRAVADO':'LOCAL · OCR EXECUTADO AGORA';
$('runtime').textContent=offline?'Execução registrada':'Motor local';
if(offline) $('sourceNote').textContent='Replay de execuções reais gravadas. Ações manuais são aplicadas na mesa fictícia; não são execuções gravadas do motor. Retomar recarrega a evidência. Cenários independentes.';
if(nvtMode) {
  document.querySelector('h1').textContent='Seu range. Sua decisão.';
  document.querySelector('.decision .overline').textContent='NVT Range Lab · motor '+labConfig.engine_commit;
  $('sourceNote').textContent=(offline?'Replay de OCR e consultas NVT reais gravadas. ':'OCR e consulta NVT executados localmente. ')+
    'Pré-flop, posições, stacks e spot vêm do cenário controlado; não são inferidos do screenshot. Mix preservado, sem inventar sizings.';
}
paintScene();controls();
