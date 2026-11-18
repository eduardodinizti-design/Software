// recon_methods.js — lista os METODOS de PP.PPPoker.AppProtocol que casam
// Room/Seat/Enter/Player/Info, p/ achar o handler certo do estado da mesa. READ-ONLY.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='AppProtocol';
const PS=Process.pointerSize;
function cstr(p){try{return p.isNull()?'':p.readCString();}catch(e){return '';}}
let _M=null; function exp(x){if(!_M)_M=Process.getModuleByName(MOD);return _M.getExportByName(x);}
function nf(x,r,a){return new NativeFunction(exp(x),r,a);}
function main(){
  const il={
    domain_get:nf('il2cpp_domain_get','pointer',[]), thread_attach:nf('il2cpp_thread_attach','pointer',['pointer']),
    domain_get_assemblies:nf('il2cpp_domain_get_assemblies','pointer',['pointer','pointer']),
    assembly_get_image:nf('il2cpp_assembly_get_image','pointer',['pointer']), image_get_name:nf('il2cpp_image_get_name','pointer',['pointer']),
    class_from_name:nf('il2cpp_class_from_name','pointer',['pointer','pointer','pointer']),
    class_get_methods:nf('il2cpp_class_get_methods','pointer',['pointer','pointer']),
    method_get_name:nf('il2cpp_method_get_name','pointer',['pointer']),
    method_get_param_count:nf('il2cpp_method_get_param_count','uint32',['pointer']),
  };
  const d=il.domain_get(); il.thread_attach(d);
  const sp=Memory.alloc(PS); const arr=il.domain_get_assemblies(d,sp); const cnt=sp.readU64().toNumber();
  let img=ptr(0);
  for(let a=0;a<cnt;a++){ const im=il.assembly_get_image(arr.add(a*PS).readPointer());
    if(cstr(il.image_get_name(im)).toLowerCase().indexOf('pppoker')>=0){ img=im; break; } }
  const klass=il.class_from_name(img, Memory.allocUtf8String(NS), Memory.allocUtf8String(CLS));
  const it=Memory.alloc(PS); it.writePointer(ptr(0));
  const re=/room|seat|enter|player|info|table|sit/i;
  let m, n=0, hit=0;
  console.log('=== metodos AppProtocol que casam Room/Seat/Enter/Player/Info/Table ===');
  while(!(m=il.class_get_methods(klass,it)).isNull()){ n++;
    const nm=cstr(il.method_get_name(m)); if(re.test(nm)){ hit++; console.log('  '+nm+'  (params='+il.method_get_param_count(m)+')'); } }
  console.log('=== total metodos='+n+'  casaram='+hit+' ===');
}
function go(){ try{ main(); }catch(e){ console.log('[recon] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
