// capturar_maos.js — HOOK READ-ONLY: lê os campos dos handlers de mão do AppProtocol e
// manda eventos estruturados p/ o Python montar a mão (HandAccumulator). So LE.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='AppProtocol';
const HOOK=['OnAnteBRC','OnRoundStartBRC','OnHandCardRSP','OnActionBRC','OnRoundOverBRC','OnWinnerRSP'];
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
  const offCache={};
  function offs(obj){ const cn=clsName(obj); if(offCache[cn])return offCache[cn];
    const k=il.object_get_class(obj); const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
    const m={}; let f; while(!(f=il.class_get_fields(k,it)).isNull()){ m[cstr(il.field_get_name(f))]=il.field_get_offset(f); } offCache[cn]=m; return m; }
  function geti(obj,name){ const o=offs(obj); return o[name]!==undefined?obj.add(o[name]).readS32():null; }
  function getp(obj,name){ const o=offs(obj); return o[name]!==undefined?obj.add(o[name]).readPointer():ptr(0); }
  function readRFints(rf){ if(rf.isNull())return []; let count=0,a=ptr(0);
    try{ count=rf.add(24).readS32(); a=rf.add(16).readPointer(); }catch(e){ return []; }
    const out=[]; if(!a.isNull()){ for(let i=0;i<Math.min(count,5);i++){ try{ out.push(a.add(0x20+i*4).readS32()); }catch(e){} } } return out; }

  HOOK.forEach(name=>{ const mi=il.class_get_method_from_name(klass, Memory.allocUtf8String(name), 2); if(mi.isNull())return;
    const addr=mi.readPointer(); if(addr.isNull())return;
    Interceptor.attach(addr,{ onEnter(args){ try{
      const msg=args[1]; const cn=clsName(msg);
      if(cn==='AnteBRC'){ send({t:'ante', amount:geti(msg,'ante_')||0}); }
      else if(cn==='RoundStartBRC'){ const hc=getp(msg,'handCard_'); let hero=[];
        if(!hc.isNull()){ const c1=geti(hc,'card1_')||0, c2=geti(hc,'card2_')||0; hero=[c1,c2].filter(x=>x>0); }
        send({t:'round_start', stage:geti(msg,'stage_')||0, cur_blind:geti(msg,'curBlind_')||0,
              board:readRFints(getp(msg,'board_')), hero_cards:hero}); }
      else if(cn==='HandCardRSP'){ const c1=geti(msg,'card1_')||0, c2=geti(msg,'card2_')||0;
        send({t:'hand_card', cards:[c1,c2].filter(x=>x>0)}); }
      else if(cn==='ActionBRC'){ send({t:'action', seat:geti(msg,'seatid_')||0, atype:geti(msg,'actionType_')||0,
              chips:geti(msg,'chips_')||0, hand_chips:geti(msg,'handChips_')||0}); }
      else if(cn==='RoundOverBRC'){ send({t:'round_over'}); }
      else if(cn==='WinnerRSP'){ send({t:'winner'}); }
    }catch(e){ console.log('[cap] erro:', e); } }});
  });
  console.log('[cap] hooks de mão armados (READ-ONLY). Capturando mãos...');
}
function go(){ try{ main(); }catch(e){ console.log('[cap] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
