"""Observa o PPPoker chamando ApplyTile/ApplyTileToRegion ao organizar, p/ aprender
o formato do `region` e das demais args. READ-ONLY sobre a lógica: só hooka e loga;
dispara TileTableWindows (que o PPPoker ja usa) p/ provocar as chamadas internas."""
import frida, threading, sys
done = threading.Event()
JS = r"""
const MOD='GameAssembly.dll'; let _M=null;
function exp(n){ if(!_M)_M=Process.getModuleByName(MOD); return _M.getExportByName(n); }
function nf(n,r,a){ return new NativeFunction(exp(n),r,a); }
function cs(p){ try{return p.isNull()?'':p.readCString();}catch(e){return '?';} }
const I={
 domain_get:nf('il2cpp_domain_get','pointer',[]),
 thread_attach:nf('il2cpp_thread_attach','pointer',['pointer']),
 domain_get_assemblies:nf('il2cpp_domain_get_assemblies','pointer',['pointer','pointer']),
 assembly_get_image:nf('il2cpp_assembly_get_image','pointer',['pointer']),
 image_get_name:nf('il2cpp_image_get_name','pointer',['pointer']),
 class_from_name:nf('il2cpp_class_from_name','pointer',['pointer','pointer','pointer']),
 class_get_method_from_name:nf('il2cpp_class_get_method_from_name','pointer',['pointer','pointer','int']),
 runtime_invoke:nf('il2cpp_runtime_invoke','pointer',['pointer','pointer','pointer','pointer']),
};
const d=I.domain_get(); I.thread_attach(d);
const sz=Memory.alloc(8); const arr=I.domain_get_assemblies(d,sz); const n=sz.readU64().toNumber();
let img=NULL;
for(let i=0;i<n;i++){ const a=arr.add(i*8).readPointer(); const im=I.assembly_get_image(a); if(cs(I.image_get_name(im))==='PP.Production.PPPoker.dll'){img=im;break;} }
const u=s=>Memory.allocUtf8String(s);
const k=I.class_from_name(img,u(''),u('FloatingWindowFrameManager'));
const mptr=nm=>{ const m=I.class_get_method_from_name(k,u(nm),-1); return m.isNull()?null:m.readPointer(); };
const mInst=I.class_get_method_from_name(k,u('get_Instance'),0);
const mTile=I.class_get_method_from_name(k,u('TileTableWindows'),0);
const mTick=I.class_get_method_from_name(k,u('Update'),0);

function dumpFloatsAt(p, nfl){ let o=[]; for(let i=0;i<nfl;i++){ try{o.push(p.add(i*4).readFloat().toFixed(1)); }catch(e){o.push('?'); } } return o.join(','); }

let logged={};
function hookCount(name){
  const it=Memory.alloc(8); it.writePointer(ptr(0));
  const gm=nf('il2cpp_class_get_methods','pointer',['pointer','pointer']);
  const gn=nf('il2cpp_method_get_name','pointer',['pointer']);
  const gpc=nf('il2cpp_method_get_param_count','uint32',['pointer']);
  let m, cnt=0;
  while(!(m=gm(k,it)).isNull()){
    if(cs(gn(m))===name){ cnt++;
      const pc=gpc(m); const fp=m.readPointer();
      Interceptor.attach(fp,{ onEnter(args){ console.log('   -> '+name+'(pc='+pc+') chamado'); } });
    }
  }
  console.log('[probe] hook('+name+') x'+cnt);
}
['TileTableWindows','ApplyTile','ApplyTileToRegion','ZoomTiledWindows','GetNextWindowPosition',
 'PositionWindowAtTopLeft','ClampAllTablesToRegions','SetWindowVisualCenter','FitScalerForRegion',
 'GetActiveTableControllers'].forEach(hookCount);

function hook(name, nargs){
  // acha o methodPointer da 1a sobrecarga desse nome
  const it=Memory.alloc(8); it.writePointer(ptr(0));
  const gm=nf('il2cpp_class_get_methods','pointer',['pointer','pointer']);
  const gn=nf('il2cpp_method_get_name','pointer',['pointer']);
  const gpc=nf('il2cpp_method_get_param_count','uint32',['pointer']);
  let m;
  while(!(m=gm(k,it)).isNull()){
    if(cs(gn(m))===name){
      const pc=gpc(m); const fp=m.readPointer();
      Interceptor.attach(fp,{ onEnter(args){
        if(logged[name]) return; logged[name]=true;
        let line='[HOOK '+name+' pc='+pc+'] ';
        for(let i=0;i<Math.min(pc+1,7);i++){ line+='a'+i+'='+args[i]+' '; }
        // candidato a region = args[2] (ptr p/ Rect) -> 4 floats
        try{ line+='| region?@a2 floats=['+dumpFloatsAt(args[2],4)+'] '; }catch(e){}
        try{ line+='| a5f='+args[5].readFloat().toFixed(1)+' a6f='+args[6].readFloat().toFixed(1); }catch(e){}
        console.log(line);
      }});
      console.log('[probe] hook instalado em '+name+' pc='+pc+' @'+fp);
    }
  }
}
hook('ApplyTile');
hook('ApplyTileToRegion');

// dispara TileTableWindows na main thread (hook no Update, 1x)
let fired=false;
Interceptor.attach(mTick.readPointer(),{ onEnter(){
  if(fired) return; fired=true;
  try{
    const e1=Memory.alloc(8); e1.writePointer(NULL);
    const inst=I.runtime_invoke(mInst,NULL,NULL,e1);
    const e2=Memory.alloc(8); e2.writePointer(NULL);
    I.runtime_invoke(mTile,inst,NULL,e2);
    console.log('[probe] TileTableWindows disparado');
  }catch(e){ console.log('[probe] erro disparo:'+e.message); }
}});
setTimeout(()=>send('__D__'), 2500);
"""
def om(m,d):
    if m.get('type')=='send' and m['payload']=='__D__': done.set()
    elif m.get('type')=='error': print('ERR',m.get('stack')); done.set()
s=frida.attach('PPPoker.exe'); sc=s.create_script(JS); sc.on('message',om)
sc.set_log_handler(lambda l,t: print(t)); sc.load(); done.wait(8); s.detach()
