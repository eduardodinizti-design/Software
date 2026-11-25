// recon_pb.js — dump READ-ONLY de TODOS os nomes de classe da PP.Production.Protocol.dll
// (Protobuf Pb.*). So nomes, nada de metodo/chamada. Pra achar as msgs de fluxo da mao.
'use strict';
const MOD = 'GameAssembly.dll';
function cstr(p){try{return p.isNull()?'':p.readCString();}catch(e){return '';}}
let _M=null; function exp(n){if(!_M)_M=Process.getModuleByName(MOD);return _M.getExportByName(n);}
function nf(n,r,a){return new NativeFunction(exp(n),r,a);}
function main(){
  const il={
    domain_get:nf('il2cpp_domain_get','pointer',[]),
    thread_attach:nf('il2cpp_thread_attach','pointer',['pointer']),
    domain_get_assemblies:nf('il2cpp_domain_get_assemblies','pointer',['pointer','pointer']),
    assembly_get_image:nf('il2cpp_assembly_get_image','pointer',['pointer']),
    image_get_name:nf('il2cpp_image_get_name','pointer',['pointer']),
    image_get_class_count:nf('il2cpp_image_get_class_count','uint32',['pointer']),
    image_get_class:nf('il2cpp_image_get_class','pointer',['pointer','uint32']),
    class_get_name:nf('il2cpp_class_get_name','pointer',['pointer']),
    class_get_namespace:nf('il2cpp_class_get_namespace','pointer',['pointer']),
  };
  const d=il.domain_get(); il.thread_attach(d);
  const sp=Memory.alloc(Process.pointerSize);
  const arr=il.domain_get_assemblies(d,sp); const cnt=sp.readU64().toNumber();
  for(let a=0;a<cnt;a++){
    const asm=arr.add(a*Process.pointerSize).readPointer();
    const img=il.assembly_get_image(asm);
    const nm=cstr(il.image_get_name(img));
    if(nm.toLowerCase().indexOf('protocol')<0) continue;
    const n=il.image_get_class_count(img);
    console.log('[image] '+nm+' classes='+n);
    for(let i=0;i<n;i++){
      const k=il.image_get_class(img,i); if(k.isNull())continue;
      const cn=cstr(il.class_get_name(k)); const ns=cstr(il.class_get_namespace(k));
      console.log((ns?ns+'.':'')+cn);
    }
  }
}
function go(){try{main();}catch(e){console.log('erro:',e.stack||e);}send('__RECON_DONE__');}
if(Process.findModuleByName(MOD)){go();}else{const id=setInterval(()=>{if(Process.findModuleByName(MOD)){clearInterval(id);go();}},500);}
