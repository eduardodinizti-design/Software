"""Diagnostico incremental de ApplyTileToRegion. STEP=1|2|3 (default 1).
 1: cria List<FWC> + conta (nao toca UI)
 2: +GetActiveTableControllers (preenche) + conta
 3: +ApplyTileToRegion (toca UI)
Cada marco vai por send() -> impresso na hora. Detach seguro, sem travar."""
import frida, threading, sys, time
step = int(sys.argv[1]) if len(sys.argv) > 1 else 1
done = threading.Event()

def bring_front():
    """Traz a janela Unity do PPPoker p/ foco (Update do Unity so roda em foreground)."""
    try:
        import win32gui, win32con
        found = []
        def cb(h, _):
            if win32gui.GetClassName(h) == 'UnityWndClass' and win32gui.IsWindowVisible(h):
                found.append(h)
            return True
        win32gui.EnumWindows(cb, None)
        for h in found:
            win32gui.ShowWindow(h, win32con.SW_RESTORE)
            try: win32gui.SetForegroundWindow(h)
            except Exception: pass
        return bool(found)
    except Exception as e:
        print('bring_front err', e); return False
JS = r"""
const MOD='GameAssembly.dll'; let _M=null; const STEP=__STEP__;
function exp(n){ if(!_M)_M=Process.getModuleByName(MOD); return _M.getExportByName(n); }
function nf(n,r,a){ return new NativeFunction(exp(n),r,a); }
function cs(p){ try{return p.isNull()?'':p.readCString();}catch(e){return '?';} }
function mark(s){ send({m:s}); }
const I={
 domain_get:nf('il2cpp_domain_get','pointer',[]), thread_attach:nf('il2cpp_thread_attach','pointer',['pointer']),
 domain_get_assemblies:nf('il2cpp_domain_get_assemblies','pointer',['pointer','pointer']),
 assembly_get_image:nf('il2cpp_assembly_get_image','pointer',['pointer']), image_get_name:nf('il2cpp_image_get_name','pointer',['pointer']),
 class_from_name:nf('il2cpp_class_from_name','pointer',['pointer','pointer','pointer']),
 class_get_method_from_name:nf('il2cpp_class_get_method_from_name','pointer',['pointer','pointer','int']),
 method_get_param:nf('il2cpp_method_get_param','pointer',['pointer','uint32']),
 class_from_type:nf('il2cpp_class_from_type','pointer',['pointer']),
 object_new:nf('il2cpp_object_new','pointer',['pointer']),
 object_unbox:nf('il2cpp_object_unbox','pointer',['pointer']),
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
const listClass=I.class_from_type(I.method_get_param(mGet,0));
const mListCtor=I.class_get_method_from_name(listClass,u('.ctor'),0);
const mCount=I.class_get_method_from_name(listClass,u('get_Count'),0);
function invoke(method,obj,p){ const e=Memory.alloc(8); e.writePointer(NULL); const r=I.runtime_invoke(method,obj,p||NULL,e); if(!e.readPointer().isNull()) throw new Error('exc IL2CPP'); return r; }
function count(list){ const b=invoke(mCount,list,NULL); return b.isNull()?-1:I.object_unbox(b).readS32(); }

mark('A resolve ok: fm='+!fm.isNull()+' get='+!mGet.isNull()+' apply='+!mApply.isNull()+' listClass='+!listClass.isNull()+' ctor='+!mListCtor.isNull()+' count='+!mCount.isNull());

let fired=false;
const listener=Interceptor.attach(mTick.readPointer(),{ onEnter(){
  if(fired) return; fired=true;
  try{ listener.detach(); }catch(e){}
  try{
    const inst=invoke(mInst,NULL,NULL); mark('B inst='+inst);
    const list=I.object_new(listClass); invoke(mListCtor,list,NULL); mark('C list criada count0='+count(list));
    if(STEP>=2){
      const lv=Memory.alloc(8); lv.writePointer(list); const p=Memory.alloc(8); p.writePointer(lv);
      invoke(mGet,inst,p); mark('D GetActiveTableControllers ok count='+count(list));
    }
    if(STEP>=3){
      const reg=Memory.alloc(16); reg.writeFloat(2880); reg.add(4).writeFloat(0); reg.add(8).writeFloat(2880); reg.add(12).writeFloat(2160);
      const zoom=Memory.alloc(4); zoom.writeFloat(1.0); const pbc=Memory.alloc(1); pbc.writeU8(0);
      const cw=Memory.alloc(4); cw.writeFloat(5760); const ch=Memory.alloc(4); ch.writeFloat(2160);
      const lv=Memory.alloc(8); lv.writePointer(list);
      const P=Memory.alloc(6*8);
      P.writePointer(lv); P.add(8).writePointer(reg); P.add(16).writePointer(zoom);
      P.add(24).writePointer(pbc); P.add(32).writePointer(cw); P.add(40).writePointer(ch);
      invoke(mApply,inst,P); mark('E ApplyTileToRegion OK');
    }
    mark('Z fim step='+STEP);
  }catch(e){ mark('ERRO: '+(e.message||e)); }
  send({done:true});
}});
setTimeout(()=>send({done:true}), 5000);
"""
JS = JS.replace('__STEP__', str(step))
def om(m,d):
    if m.get('type')=='send':
        p=m['payload']
        if isinstance(p,dict) and p.get('done'): done.set()
        elif isinstance(p,dict) and 'm' in p: print('  >>', p['m']); sys.stdout.flush()
    elif m.get('type')=='error': print('ERR',m.get('stack')); done.set()
try:
    print('[diag] trazendo PPPoker p/ foco:', bring_front()); time.sleep(0.6)
    s=frida.attach('PPPoker.exe')
    s.on('detached', lambda *a: done.set())
    sc=s.create_script(JS); sc.on('message',om); sc.load()
    done.wait(8)
    try: s.detach()
    except Exception: pass
except Exception as e:
    print('falha:', e)
print('[diag] fim step', step)
