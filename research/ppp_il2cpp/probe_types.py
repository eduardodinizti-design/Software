"""Tipos dos parametros/retorno de ApplyTileToRegion e GetActiveTableControllers."""
import frida, threading
done = threading.Event()
JS = r"""
const MOD='GameAssembly.dll'; let _M=null;
function exp(n){ if(!_M)_M=Process.getModuleByName(MOD); return _M.getExportByName(n); }
function nf(n,r,a){ return new NativeFunction(exp(n),r,a); }
function cs(p){ try{return p.isNull()?'':p.readCString();}catch(e){return '?';} }
const I={
 domain_get:nf('il2cpp_domain_get','pointer',[]), thread_attach:nf('il2cpp_thread_attach','pointer',['pointer']),
 domain_get_assemblies:nf('il2cpp_domain_get_assemblies','pointer',['pointer','pointer']),
 assembly_get_image:nf('il2cpp_assembly_get_image','pointer',['pointer']), image_get_name:nf('il2cpp_image_get_name','pointer',['pointer']),
 class_from_name:nf('il2cpp_class_from_name','pointer',['pointer','pointer','pointer']),
 class_get_methods:nf('il2cpp_class_get_methods','pointer',['pointer','pointer']),
 method_get_name:nf('il2cpp_method_get_name','pointer',['pointer']),
 method_get_param_count:nf('il2cpp_method_get_param_count','uint32',['pointer']),
 method_get_param:nf('il2cpp_method_get_param','pointer',['pointer','uint32']),
 method_get_param_name:nf('il2cpp_method_get_param_name','pointer',['pointer','uint32']),
 method_get_return_type:nf('il2cpp_method_get_return_type','pointer',['pointer']),
 class_from_type:nf('il2cpp_class_from_type','pointer',['pointer']),
 class_get_name:nf('il2cpp_class_get_name','pointer',['pointer']),
 class_get_namespace:nf('il2cpp_class_get_namespace','pointer',['pointer']),
};
const d=I.domain_get(); I.thread_attach(d);
const sz=Memory.alloc(8); const arr=I.domain_get_assemblies(d,sz); const n=sz.readU64().toNumber();
let img=NULL;
for(let i=0;i<n;i++){ const a=arr.add(i*8).readPointer(); const im=I.assembly_get_image(a); if(cs(I.image_get_name(im))==='PP.Production.PPPoker.dll'){img=im;break;} }
const u=s=>Memory.allocUtf8String(s);
const k=I.class_from_name(img,u(''),u('FloatingWindowFrameManager'));
function tname(t){ try{ const c=I.class_from_type(t); const ns=cs(I.class_get_namespace(c)); const nm=cs(I.class_get_name(c)); return (ns?ns+'.':'')+nm; }catch(e){ return '?'; } }
function describe(name){
  const it=Memory.alloc(8); it.writePointer(ptr(0)); let m;
  while(!(m=I.class_get_methods(k,it)).isNull()){
    if(cs(I.method_get_name(m))!==name) continue;
    const pc=I.method_get_param_count(m); let ps=[];
    for(let i=0;i<pc;i++){ const t=I.method_get_param(m,i); ps.push(tname(t)+' '+cs(I.method_get_param_name(m,i))); }
    const rt=tname(I.method_get_return_type(m));
    console.log(rt+' '+name+'('+ps.join(', ')+')');
  }
}
['ApplyTileToRegion','GetActiveTableControllers','ApplyTile','ZoomTiledWindows','get_ContentArea'].forEach(describe);
send('__D__');
"""
def om(m,d):
    if m.get('type')=='send' and m['payload']=='__D__': done.set()
    elif m.get('type')=='error': print('ERR',m.get('stack')); done.set()
s=frida.attach('PPPoker.exe'); sc=s.create_script(JS); sc.on('message',om)
sc.set_log_handler(lambda l,t: print(t)); sc.load(); done.wait(10); s.detach()
