// hook_mtt.js — HOOK READ-ONLY do MttProtocol: captura a PERCEPCAO de MESA FINAL
// (rank atual + jogadores restantes). Dumpa MttMyRankInfoBRC toda vez (valor vivo) e
// os outros 1x. So LE.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='MttProtocol';
const HOOK=['OnMttMyRankInfoBRC','OnMttDivideRewardBRC','OnMttBlindStructureRSP','OnQueryPlayerDimensionRSP'];
const LIVE=new Set(['MttMyRankInfoBRC']);   // dumpa sempre (acompanhar rank cair ate a FT)
let seen={};
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
  function dumpFields(obj){
    const k=il.object_get_class(obj); const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
    let f, lines=[];
    while(!(f=il.class_get_fields(k,it)).isNull()){
      const fn=cstr(il.field_get_name(f)); const off=il.field_get_offset(f);
      if(/FieldNumber$|DefaultValue$|^_parser$|^_unknownFields$|^_hasBits/.test(fn)) continue;
      let v; try{ const i32=obj.add(off).readS32(); const p=obj.add(off).readPointer();
        const pc=(!p.isNull()&&p.compare(ptr('0x10000'))>0)?clsName(p):null; v=pc&&pc!=='?'?('->'+pc):i32;
      }catch(e){ v='?'; } lines.push(fn+'@'+off+'='+v);
    } return lines.join('  ');
  }
  let hooked=0;
  HOOK.forEach(name=>{
    const mi=il.class_get_method_from_name(klass, Memory.allocUtf8String(name), 2); if(mi.isNull())return;
    const addr=mi.readPointer(); if(addr.isNull())return;
    Interceptor.attach(addr,{ onEnter(args){ const cn=clsName(args[1]);
      if(LIVE.has(cn)){ console.log('[FT/RANK] '+cn+': '+dumpFields(args[1])); }
      else if(!seen[cn]){ seen[cn]=true; console.log('\n[MTT] '+cn+': '+dumpFields(args[1])); }
    }}); hooked++;
  });
  console.log('[hook-mtt] '+hooked+'/'+HOOK.length+' hookados (READ-ONLY). Capturando rank/FT...');
}
function go(){ try{ main(); }catch(e){ console.log('[hook] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
