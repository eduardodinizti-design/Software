// discrim_mesa.js — RECON READ-ONLY do DISCRIMINADOR DE MESA (multi-tabling).
// ActionBRC/RoundStartBRC não têm roomid no corpo; o id da mesa tem que vir de FORA do
// objeto: args[0]=this (AppProtocol, provável singleton), args[2]=contexto. Loga esses +
// o gameid do DealerInfoRSP e o roomid onde aparecer, p/ ver o que separa as duas mesas.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='AppProtocol';
const HOOK=['OnDealerInfoRSP','OnRoundStartBRC','OnActionBRC','OnHandCardRSP','OnAnteBRC','OnWinnerRSP'];
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
  const isObj=(p)=>{ try{ return !p.isNull() && p.compare(ptr('0x10000'))>0; }catch(e){ return false; } };
  const offCache={};
  function offs(obj){ const cn=clsName(obj); if(offCache[cn])return offCache[cn];
    const k=il.object_get_class(obj); const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
    const m={}; let f; while(!(f=il.class_get_fields(k,it)).isNull()){ m[cstr(il.field_get_name(f))]=il.field_get_offset(f); } offCache[cn]=m; return m; }
  function geti(obj,name){ try{ const o=offs(obj); return o[name]!==undefined?obj.add(o[name]).readS32():null; }catch(e){ return null; } }
  function readStr(obj,name){ try{ const o=offs(obj); if(o[name]===undefined)return null; const p=obj.add(o[name]).readPointer(); return isObj(p)?cstr(p.add(0x14)):null; }catch(e){ return null; } }
  // dumpa o arg "de fora" (args[2]/args[3]): como int e, se ponteiro p/ objeto, classe + 1º int
  function ctxInfo(p){ const out={ptr:p.toString()}; try{ out.int=p.toUInt32(); }catch(e){}
    if(isObj(p)){ out.cls=clsName(p); try{ out.first=p.add(0).readPointer().toString(); }catch(e){} } return out; }

  HOOK.forEach(name=>{ const mi=il.class_get_method_from_name(klass, Memory.allocUtf8String(name), 2); if(mi.isNull())return;
    const addr=mi.readPointer(); if(addr.isNull())return;
    Interceptor.attach(addr,{ onEnter(args){ try{
      const msg=args[1]; const cn=clsName(msg);
      const ev={h:name, cn:cn, this:args[0].toString(), a2:ctxInfo(args[2]), a3:ctxInfo(args[3])};
      if(cn==='ActionBRC'){ ev.seat=geti(msg,'seatid_'); ev.atype=geti(msg,'actionType_'); ev.chips=geti(msg,'chips_'); }
      else if(cn==='RoundStartBRC'){ ev.stage=geti(msg,'stage_'); ev.curBlind=geti(msg,'curBlind_'); }
      else if(cn==='DealerInfoRSP'){ ev.dealer=geti(msg,'dealer_'); ev.gameid=readStr(msg,'gameid_'); }
      else if(cn==='HandCardRSP'){ ev.c1=geti(msg,'card1_'); ev.c2=geti(msg,'card2_'); }
      send(ev);
    }catch(e){ console.log('[discrim] erro:', e); } }});
  });
  console.log('[discrim] hooks armados. Jogue as DUAS mesas; veja se a2/this separam em 2 grupos.');
}
function go(){ try{ main(); }catch(e){ console.log('[discrim] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
