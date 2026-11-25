// alerta_ft.js — HOOK READ-ONLY do MttProtocol: manda p/ o Python (a) rank/FT
// (MttMyRankInfoBRC) e (b) atividade de DEAL (divisão de prêmio). So LE — nunca aceita,
// rejeita ou envia resposta.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='MttProtocol';
const RANK_METHOD='OnMttMyRankInfoBRC';
const RANK_FIELDS={rank_:'rank', itmPlayerNum_:'itm', totalPlayerNum_:'total',
                   alivePlayerNum_:'alive', currentRewardPpcoins_:'reward'};
// DEAL/CHOP: o deal da FT (botões aceitar/rejeitar) é o EvChop do TableProtocol; mantém
// também o MttDivideReward do MttProtocol. {classe: [métodos]}.
const DEAL_TARGETS={
  TableProtocol:['OnEvChopInfoBRC','OnEvChopOperationRSP','OnEvChopOperationBRC','OnEvChopOverBRC'],
  MttProtocol:['OnMttDivideRewardBRC','OnHostDivideRewardBRC','OnHostDivideRewardRSP',
               'OnPlayerVoteDivideRSP','OnPlayerRefuseDivideBRC'],
};
const DEAL_RE=/EvChop|Chop|Divide|Reward|Refuse|Vote/i;
let RANK_OFF=null;
function cstr(p){try{return p.isNull()?'':p.readCString();}catch(e){return '';}}
let _M=null; function exp(x){if(!_M)_M=Process.getModuleByName(MOD);return _M.getExportByName(x);}
function nf(x,r,a){return new NativeFunction(exp(x),r,a);}
function main(){
  const il={
    domain_get:nf('il2cpp_domain_get','pointer',[]), thread_attach:nf('il2cpp_thread_attach','pointer',['pointer']),
    domain_get_assemblies:nf('il2cpp_domain_get_assemblies','pointer',['pointer','pointer']),
    assembly_get_image:nf('il2cpp_assembly_get_image','pointer',['pointer']), image_get_name:nf('il2cpp_image_get_name','pointer',['pointer']),
    class_from_name:nf('il2cpp_class_from_name','pointer',['pointer','pointer','pointer']),
    class_get_method_from_name:nf('il2cpp_class_get_method_from_name','pointer',['pointer','pointer','int']),
    class_get_name:nf('il2cpp_class_get_name','pointer',['pointer']), object_get_class:nf('il2cpp_object_get_class','pointer',['pointer']),
    class_get_fields:nf('il2cpp_class_get_fields','pointer',['pointer','pointer']),
    field_get_name:nf('il2cpp_field_get_name','pointer',['pointer']), field_get_offset:nf('il2cpp_field_get_offset','uint32',['pointer']),
  };
  const d=il.domain_get(); il.thread_attach(d);
  const sp=Memory.alloc(Process.pointerSize); const arr=il.domain_get_assemblies(d,sp); const cnt=sp.readU64().toNumber();
  let img=ptr(0);
  for(let a=0;a<cnt;a++){ const im=il.assembly_get_image(arr.add(a*Process.pointerSize).readPointer());
    if(cstr(il.image_get_name(im)).toLowerCase().indexOf('pppoker')>=0){ img=im; break; } }
  const klass=il.class_from_name(img, Memory.allocUtf8String(NS), Memory.allocUtf8String(CLS));
  const clsName=(o)=>{ try{ return o.isNull()?'null':cstr(il.class_get_name(il.object_get_class(o))); }catch(e){ return '?'; } };
  function rankOffsets(obj){ const k=il.object_get_class(obj); const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
    const m={}; let f; while(!(f=il.class_get_fields(k,it)).isNull()){ const fn=cstr(il.field_get_name(f)); if(RANK_FIELDS[fn]!==undefined) m[RANK_FIELDS[fn]]=il.field_get_offset(f); } return m; }

  // --- RANK / FT ---
  const mr=il.class_get_method_from_name(klass, Memory.allocUtf8String(RANK_METHOD), 2);
  if(!mr.isNull()){ Interceptor.attach(mr.readPointer(), { onEnter(args){ const msg=args[1]; if(msg.isNull())return;
    try{ if(!RANK_OFF) RANK_OFF=rankOffsets(msg); const r={kind:'rank'}; for(const k in RANK_OFF){ r[k]=msg.add(RANK_OFF[k]).readS32(); } send(r); }catch(e){} } }); }

  // --- DEAL/CHOP (filtra pela CLASSE da msg por causa do code-sharing IL2CPP) ---
  let dh=0;
  for(const cls in DEAL_TARGETS){
    const dk=il.class_from_name(img, Memory.allocUtf8String(NS), Memory.allocUtf8String(cls));
    if(dk.isNull()) continue;
    DEAL_TARGETS[cls].forEach(name=>{ const mi=il.class_get_method_from_name(dk, Memory.allocUtf8String(name), 2); if(mi.isNull())return;
      const addr=mi.readPointer(); if(addr.isNull())return;
      Interceptor.attach(addr,{ onEnter(args){ const cn=clsName(args[1]);
        if(!DEAL_RE.test(cn)) return;   // so msgs de deal/chop
        send({kind:'deal', msg:cn}); } }); dh++;
    });
  }
  console.log('[alerta] hooks OK (READ-ONLY): rank/FT + deal/chop ('+dh+' handlers). Monitorando...');
}
function go(){ try{ main(); }catch(e){ console.log('[alerta] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
