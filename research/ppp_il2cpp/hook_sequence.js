// hook_sequence.js — HOOK READ-ONLY: loga a ORDEM das mensagens da mão (sem dedup) com
// os campos escalares-chave, p/ entender o ciclo de vida (RoundStart por rua ou por mão?
// onde o board atualiza? valores do enum actionType?). So LE.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='AppProtocol';
const HOOK=['OnEnterRoomRSP','OnRoundStartBRC','OnHandCardRSP','OnActionBRC','OnActionNotifyBRC',
            'OnRoundOverBRC','OnWinnerRSP','OnShowHandRSP','OnSeatStatusBRC','OnAnteBRC','OnShowMyCardBRC'];
// campos escalares a logar por tipo de mensagem (nome do campo protobuf):
const SHOW={
  ActionBRC:['seatid_','actionType_','chips_','handChips_'],
  ActionNotifyBRC:['seatid_','callNeedChips_','minChipin_','maxChipin_','canActionNum_'],
  RoundStartBRC:['stage_','curBlind_','riverSqueeze_'],
  HandCardRSP:['card1_','card2_','card3_','card4_','card5_','canViewHand_','isAllin_'],
  AnteBRC:['ante_'],
  RoundOverBRC:[], WinnerRSP:[], ShowHandRSP:['winRateEnable_'], SeatStatusBRC:[],
};
function cstr(p){try{return p.isNull()?'':p.readCString();}catch(e){return '';}}
let _M=null; function exp(n){if(!_M)_M=Process.getModuleByName(MOD);return _M.getExportByName(n);}
function nf(n,r,a){return new NativeFunction(exp(n),r,a);}
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
  const offCache={};
  function offsets(obj){ const cn=clsName(obj); if(offCache[cn])return offCache[cn];
    const k=il.object_get_class(obj); const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
    const m={}; let f; while(!(f=il.class_get_fields(k,it)).isNull()){ m[cstr(il.field_get_name(f))]=il.field_get_offset(f); }
    offCache[cn]=m; return m;
  }
  function line(obj){ const cn=clsName(obj); const want=SHOW[cn];
    if(want===undefined) return null;                 // só os tipos que nos interessam
    const off=offsets(obj); const parts=[];
    for(const fn of want){ if(off[fn]!==undefined){ try{ parts.push(fn.replace(/_$/,'')+'='+obj.add(off[fn]).readS32()); }catch(e){} } }
    return cn+(parts.length?('  '+parts.join(' ')):'');
  }
  let n=0;
  HOOK.forEach(name=>{ const mi=il.class_get_method_from_name(klass, Memory.allocUtf8String(name), 2); if(mi.isNull())return;
    const addr=mi.readPointer(); if(addr.isNull())return;
    Interceptor.attach(addr,{ onEnter(args){ const l=line(args[1]); if(l!==null){ n++; console.log(String(n).padStart(3,' ')+'  '+l); } }});
  });
  console.log('[seq] hookado (READ-ONLY). Jogue UMA mão completa (ate o showdown/resultado).');
}
function go(){ try{ main(); }catch(e){ console.log('[seq] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
