// recon_arg2.js — READ-ONLY: inspeciona o 2o parâmetro (args[2]) dos handlers, procurando
// um id de MESA/ROOM/conexão (o discriminador que falta p/ multi-tabling). So LE.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='AppProtocol';
function cstr(p){try{return p.isNull()?'':p.readCString();}catch(e){return '';}}
let _M=null; function exp(x){if(!_M)_M=Process.getModuleByName(MOD);return _M.getExportByName(x);}
function nf(x,r,a){return new NativeFunction(exp(x),r,a);}
let done={};
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
  function dump(obj){ const k=il.object_get_class(obj); const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
    let f,p=[]; while(!(f=il.class_get_fields(k,it)).isNull()){ const n=cstr(il.field_get_name(f)); const o=il.field_get_offset(f);
      try{ const i=obj.add(o).readS32(); const pt=obj.add(o).readPointer(); const pc=(!pt.isNull()&&pt.compare(ptr('0x10000'))>0)?clsName(pt):null;
        p.push(n+'@'+o+'='+(pc&&pc!=='?'?('->'+pc):i)); }catch(e){} } return p.join('  '); }
  function inspect(name){ const mi=il.class_get_method_from_name(klass, Memory.allocUtf8String(name), 2); if(mi.isNull())return;
    Interceptor.attach(mi.readPointer(),{ onEnter(args){ if(done[name])return; done[name]=true;
      const a2=args[2]; let info='arg2='+a2+' int='+a2.toInt32();
      try{ const cl=clsName(a2); info+=' class='+cl; if(cl!=='?'&&cl!=='null'){ console.log('['+name+'] '+info+'\n   fields: '+dump(a2)); return; } }catch(e){ info+=' (nao-obj)'; }
      console.log('['+name+'] '+info); }}); }
  ['OnActionBRC','OnRoundStartBRC','OnEnterRoomRSP','OnHandCardRSP'].forEach(inspect);
  console.log('[recon-arg2] armado (READ-ONLY).');
}
function go(){ try{ main(); }catch(e){ console.log('[recon-arg2] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
