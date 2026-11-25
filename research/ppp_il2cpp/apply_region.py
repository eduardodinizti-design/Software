"""TESTE: confinar as mesas do PPPoker a uma REGIAO via ApplyTileToRegion.
Monta List<FloatingWindowController> (GetActiveTableControllers preenche),
ScreenRegion{X,Y,W,H} e chama na main thread. Region default = metade direita
do render (2880,0,2880,2160) p/ validar visualmente o sistema de coordenadas.
Passe 4 numeros p/ custom: python apply_region.py X Y W H
"""
import frida, threading, sys
done = threading.Event()
rx, ry, rw, rh = (2880.0, 0.0, 2880.0, 2160.0)
if len(sys.argv) == 5:
    rx, ry, rw, rh = map(float, sys.argv[1:5])
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
 class_get_method_from_name:nf('il2cpp_class_get_method_from_name','pointer',['pointer','pointer','int']),
 method_get_param:nf('il2cpp_method_get_param','pointer',['pointer','uint32']),
 class_from_type:nf('il2cpp_class_from_type','pointer',['pointer']),
 object_new:nf('il2cpp_object_new','pointer',['pointer']),
 runtime_invoke:nf('il2cpp_runtime_invoke','pointer',['pointer','pointer','pointer','pointer']),
};
const d=I.domain_get(); I.thread_attach(d);
const sz=Memory.alloc(8); const arr=I.domain_get_assemblies(d,sz); const n=sz.readU64().toNumber();
let img=NULL;
for(let i=0;i<n;i++){ const a=arr.add(i*8).readPointer(); const im=I.assembly_get_image(a); if(cs(I.image_get_name(im))==='PP.Production.PPPoker.dll'){img=im;break;} }
const u=s=>Memory.allocUtf8String(s);
const fm=I.class_from_name(img,u(''),u('FloatingWindowFrameManager'));
const mInst=I.class_get_method_from_name(fm,u('get_Instance'),0);
const mGet =I.class_get_method_from_name(fm,u('GetActiveTableControllers'),1);
const mApply=I.class_get_method_from_name(fm,u('ApplyTileToRegion'),6);
const mTick=I.class_get_method_from_name(fm,u('Update'),0);
// classe List<FWC> inflada = tipo do param0 de GetActiveTableControllers
const listClass=I.class_from_type(I.method_get_param(mGet,0));
const mListCtor=I.class_get_method_from_name(listClass,u('.ctor'),0);
const mListCount=I.class_get_method_from_name(listClass,u('get_Count'),0);
const RX=__RX__,RY=__RY__,RW=__RW__,RH=__RH__;

function invoke(method,obj,paramsArr){
  const exc=Memory.alloc(8); exc.writePointer(NULL);
  const ret=I.runtime_invoke(method,obj,paramsArr||NULL,exc);
  if(!exc.readPointer().isNull()) throw new Error('exc IL2CPP');
  return ret;
}
let fired=false;
Interceptor.attach(mTick.readPointer(),{ onEnter(){
  if(fired) return; fired=true;
  try{
    const inst=invoke(mInst,NULL,NULL);
    // criar List vazia + .ctor
    const list=I.object_new(listClass); invoke(mListCtor,list,NULL);
    // GetActiveTableControllers(inst, list)  (param ref: ptr->ptr)
    const pList=Memory.alloc(8); pList.writePointer(list);
    const p1=Memory.alloc(8); p1.writePointer(pList);
    invoke(mGet,inst,p1);
    const cnt=invoke(mListCount,list,NULL).toInt32 ? invoke(mListCount,list,NULL) : null;
    // count (unbox int)
    const ou=nf('il2cpp_object_unbox','pointer',['pointer']);
    const cboxed=invoke(mListCount,list,NULL); const count=cboxed.isNull()?-1:ou(cboxed).readS32();
    console.log('[apply] mesas na lista='+count);
    // ScreenRegion (16 bytes: X,Y,W,H floats)
    const reg=Memory.alloc(16); reg.writeFloat(RX); reg.add(4).writeFloat(RY); reg.add(8).writeFloat(RW); reg.add(12).writeFloat(RH);
    const zoom=Memory.alloc(4); zoom.writeFloat(1.0);
    const pbc=Memory.alloc(1); pbc.writeU8(0);
    const cw=Memory.alloc(4); cw.writeFloat(5760.0);
    const ch=Memory.alloc(4); ch.writeFloat(2160.0);
    // params: [&list, &region, &zoom, &pbc, &cw, &ch]
    const P=Memory.alloc(6*8);
    const pl2=Memory.alloc(8); pl2.writePointer(list);
    P.writePointer(pl2);
    P.add(8).writePointer(reg);
    P.add(16).writePointer(zoom);
    P.add(24).writePointer(pbc);
    P.add(32).writePointer(cw);
    P.add(40).writePointer(ch);
    invoke(mApply,inst,P);
    console.log('[apply] ApplyTileToRegion OK region=('+RX+','+RY+','+RW+','+RH+')');
  }catch(e){ console.log('[apply] ERRO: '+(e.stack||e.message)); }
  send('__D__');
}});
setTimeout(()=>send('__D__'), 4000);
"""
JS = (JS.replace('__RX__', repr(rx)).replace('__RY__', repr(ry))
        .replace('__RW__', repr(rw)).replace('__RH__', repr(rh)))
def om(m,d):
    if m.get('type')=='send' and m['payload']=='__D__': done.set()
    elif m.get('type')=='error': print('ERR',m.get('stack')); done.set()
s=frida.attach('PPPoker.exe'); sc=s.create_script(JS); sc.on('message',om)
sc.set_log_handler(lambda l,t: print(t)); sc.load(); done.wait(10); s.detach()
