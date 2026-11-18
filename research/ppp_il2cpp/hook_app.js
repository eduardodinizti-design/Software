// hook_app.js — HOOK READ-ONLY dos handlers de mão do PP.PPPoker.AppProtocol.
// So LE: intercepta OnRoundStartBRC/OnHandCardRSP/OnActionBRC/OnWinnerRSP/OnEnterRoomRSP
// e imprime a CLASSE do objeto-mensagem de cada arg (p/ achar qual arg e o Protobuf).
// NAO chama metodo, NAO altera estado, NAO responde. Para o mapeamento de campos.
'use strict';
const MOD = 'GameAssembly.dll';
const NS = 'PP.PPPoker', CLS = 'AppProtocol';
const METHODS = [
  ['OnEnterRoomRSP', 2], ['OnRoundStartBRC', 2], ['OnHandCardRSP', 2],
  ['OnActionBRC', 2], ['OnActionNotifyBRC', 2], ['OnRoundOverBRC', 2],
  ['OnWinnerRSP', 2], ['OnSitDownBRC', 2], ['OnSeatStatusBRC', 2],
];
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
    class_from_name:nf('il2cpp_class_from_name','pointer',['pointer','pointer','pointer']),
    class_get_method_from_name:nf('il2cpp_class_get_method_from_name','pointer',['pointer','pointer','int']),
    class_get_name:nf('il2cpp_class_get_name','pointer',['pointer']),
    object_get_class:nf('il2cpp_object_get_class','pointer',['pointer']),
  };
  const d=il.domain_get(); il.thread_attach(d);
  // acha a image da PPPoker.dll
  const sp=Memory.alloc(Process.pointerSize);
  const arr=il.domain_get_assemblies(d,sp); const cnt=sp.readU64().toNumber();
  let img=ptr(0);
  for(let a=0;a<cnt;a++){
    const im=il.assembly_get_image(arr.add(a*Process.pointerSize).readPointer());
    if(cstr(il.image_get_name(im)).toLowerCase().indexOf('pppoker')>=0){ img=im; break; }
  }
  if(img.isNull()){ console.log('[hook] image PPPoker NAO achada'); return; }
  const klass=il.class_from_name(img, Memory.allocUtf8String(NS), Memory.allocUtf8String(CLS));
  if(klass.isNull()){ console.log('[hook] classe', CLS, 'NAO achada'); return; }

  function clsName(obj){ try{ if(obj.isNull())return 'null'; const k=il.object_get_class(obj); return cstr(il.class_get_name(k)); }catch(e){ return '?'; } }

  let hooked=0;
  METHODS.forEach(([name,argc])=>{
    const mi=il.class_get_method_from_name(klass, Memory.allocUtf8String(name), argc);
    if(mi.isNull()){ console.log('[hook] metodo NAO achado:', name); return; }
    const addr=mi.readPointer();                 // MethodInfo.methodPointer = 1o campo
    if(addr.isNull()){ console.log('[hook] addr nulo:', name); return; }
    Interceptor.attach(addr, {
      onEnter(args){
        // instancia: args[0]=this, args[1..argc]=params. Loga a classe de cada param.
        const parts=[];
        for(let i=1;i<=argc;i++){ parts.push('a'+i+'='+clsName(args[i])); }
        console.log('[MSG] '+name+'  '+parts.join('  '));
      }
    });
    hooked++;
  });
  console.log('[hook] AppProtocol: '+hooked+'/'+METHODS.length+' metodos hookados (READ-ONLY). Jogue uma mao.');
}
function go(){ try{ main(); }catch(e){ console.log('[hook] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); }
else{ const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
