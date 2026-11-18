// recon_table2.js — READ-ONLY: acha o DISCRIMINADOR DE MESA e captura o BOARD (count>0).
// Loga por ação/rodada: ptr da instância AppProtocol (args[0]), classe do alvo de Tag,
// e o board decodificado quando houver. So LE.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='AppProtocol';
function cstr(p){try{return p.isNull()?'':p.readCString();}catch(e){return '';}}
let _M=null; function exp(x){if(!_M)_M=Process.getModuleByName(MOD);return _M.getExportByName(x);}
function nf(x,r,a){return new NativeFunction(exp(x),r,a);}
let nLog=0, gotBoard=false, tagDumped=false;
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
  function fieldsOf(obj){ const k=il.object_get_class(obj); const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
    const m=[]; let f; while(!(f=il.class_get_fields(k,it)).isNull()){ m.push([cstr(il.field_get_name(f)), il.field_get_offset(f)]); } return m; }
  function offOf(obj,name){ for(const [n,o] of fieldsOf(obj)) if(n===name) return o; return -1; }
  function dumpScalars(obj,label){ const parts=[]; for(const [n,o] of fieldsOf(obj)){
    if(/FieldNumber$|DefaultValue$|^_parser$|^_unknownFields$|^_hasBits/.test(n)) continue;
    try{ const i=obj.add(o).readS32(); const p=obj.add(o).readPointer(); const pc=(!p.isNull()&&p.compare(ptr('0x10000'))>0)?clsName(p):null;
      parts.push(n+'@'+o+'='+(pc&&pc!=='?'?('->'+pc):i)); }catch(e){} }
    console.log('['+label+'] '+clsName(obj)+': '+parts.join('  ')); }
  function readBoard(msg){ const bo=offOf(msg,'board_'); if(bo<0)return null; const rf=msg.add(bo).readPointer(); if(rf.isNull())return null;
    const count=rf.add(24).readS32(); const a=rf.add(16).readPointer(); const vals=[];
    if(!a.isNull()){ for(let i=0;i<Math.min(count,5);i++) vals.push(a.add(0x20+i*4).readS32()); } return {count,vals}; }
  function tagInfo(self){ try{ const t=self.add(0).readPointer(); if(t.isNull())return 'Tag=null';
    return 'Tag->'+clsName(t)+'@'+t; }catch(e){ return 'Tag=?'; } }

  const mr=il.class_get_method_from_name(klass, Memory.allocUtf8String('OnRoundStartBRC'), 2);
  if(!mr.isNull()) Interceptor.attach(mr.readPointer(),{ onEnter(args){ if(clsName(args[1])!=='RoundStartBRC')return;
    const so=offOf(args[1],'stage_'); const stage=so>=0?args[1].add(so).readS32():-1; const b=readBoard(args[1]);
    if(nLog<16){ nLog++; console.log('RS  this='+args[0]+'  '+tagInfo(args[0])+'  stage='+stage+'  board='+JSON.stringify(b)); }
    if(b && b.count>0 && !gotBoard){ gotBoard=true; console.log('>>> BOARD count>0: '+JSON.stringify(b)); }
    if(!tagDumped){ try{ const t=args[0].add(0).readPointer(); if(!t.isNull()){ dumpScalars(t,'TAG-target'); tagDumped=true; } }catch(e){} }
  }});
  const ma=il.class_get_method_from_name(klass, Memory.allocUtf8String('OnActionBRC'), 2);
  if(!ma.isNull()) Interceptor.attach(ma.readPointer(),{ onEnter(args){ if(clsName(args[1])!=='ActionBRC')return;
    const so=offOf(args[1],'seatid_'); const seat=so>=0?args[1].add(so).readS32():-1;
    if(nLog<16){ nLog++; console.log('ACT this='+args[0]+'  '+tagInfo(args[0])+'  seat='+seat); }
  }});
  console.log('[recon-t2] armado (READ-ONLY). Jogue; precisa chegar ao FLOP p/ board count>0.');
}
function go(){ try{ main(); }catch(e){ console.log('[recon-t2] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
