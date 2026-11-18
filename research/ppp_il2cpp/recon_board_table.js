// recon_board_table.js — READ-ONLY: (1) decodifica o board_ (RepeatedField) do
// RoundStartBRC e (2) procura um DISCRIMINADOR DE MESA em args[0] (this handler) e
// args[2] (contexto). So LE.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='AppProtocol';
function cstr(p){try{return p.isNull()?'':p.readCString();}catch(e){return '';}}
let _M=null; function exp(x){if(!_M)_M=Process.getModuleByName(MOD);return _M.getExportByName(x);}
function nf(x,r,a){return new NativeFunction(exp(x),r,a);}
let didRF=false, didArg0=false, didArg2=false, didAction0=false;
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
    console.log('\n['+label+'] '+clsName(obj)+':\n   '+parts.join('  ')); }
  // le um RepeatedField<int32> -> array de ints (layout IL2CPP: elementos em +0x20)
  function readRF(rf){ if(rf.isNull())return null; const fs=fieldsOf(rf);
    console.log('\n[RF-fields] '+clsName(rf)+': '+fs.map(([n,o])=>n+'@'+o).join('  '));
    let cntOff=-1, arrOff=-1; for(const [n,o] of fs){ if(/count/i.test(n))cntOff=o; if(/array|^items$/i.test(n))arrOff=o; }
    const out={cntOff,arrOff};
    try{ if(cntOff>=0) out.count=rf.add(cntOff).readS32();
      if(arrOff>=0){ const a=rf.add(arrOff).readPointer(); out.arrPtr=a;
        if(!a.isNull()){ const n=out.count!==undefined?out.count:a.add(0x18).readS32();
          const vals=[]; for(let i=0;i<Math.min(n,7);i++){ vals.push(a.add(0x20+i*4).readS32()); } out.vals=vals; } } }catch(e){ out.err=String(e); }
    return out; }

  // RoundStartBRC: board_
  const mr=il.class_get_method_from_name(klass, Memory.allocUtf8String('OnRoundStartBRC'), 2);
  if(!mr.isNull()) Interceptor.attach(mr.readPointer(),{ onEnter(args){ const msg=args[1];
    if(clsName(msg)!=='RoundStartBRC') return;
    if(!didRF){ const bo=offOf(msg,'board_'); const rf=bo>=0?msg.add(bo).readPointer():ptr(0);
      console.log('\n[BOARD] board_@'+bo+' -> '+clsName(rf)); const r=readRF(rf);
      console.log('   RF: '+JSON.stringify(r)); didRF=true; }
    if(!didArg0){ dumpScalars(args[0],'ARG0/this(RoundStart)'); didArg0=true; }
    if(!didArg2){ try{ if(!args[2].isNull()) dumpScalars(args[2],'ARG2/ctx(RoundStart)'); }catch(e){} didArg2=true; }
  }});
  // ActionBRC: inspeciona args[0]/args[2] p/ achar id de mesa por ação (multi-tabling)
  const ma=il.class_get_method_from_name(klass, Memory.allocUtf8String('OnActionBRC'), 2);
  if(!ma.isNull()) Interceptor.attach(ma.readPointer(),{ onEnter(args){ if(didAction0)return; if(clsName(args[1])!=='ActionBRC')return;
    dumpScalars(args[0],'ARG0/this(Action)'); try{ if(!args[2].isNull()) dumpScalars(args[2],'ARG2/ctx(Action)'); }catch(e){} didAction0=true; }});
  console.log('[recon-bt] armado (READ-ONLY). Jogue uma mão (precisa chegar ao flop p/ board).');
}
function go(){ try{ main(); }catch(e){ console.log('[recon-bt] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
