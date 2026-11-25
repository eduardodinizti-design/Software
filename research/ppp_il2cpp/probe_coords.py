"""Le os campos de layout do singleton FloatingWindowFrameManager (coordenadas reais)
e a estrutura de ScreenRegion. Descobre o sistema de coordenadas do tiling."""
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
 class_get_method_from_name:nf('il2cpp_class_get_method_from_name','pointer',['pointer','pointer','int']),
 runtime_invoke:nf('il2cpp_runtime_invoke','pointer',['pointer','pointer','pointer','pointer']),
 class_get_fields:nf('il2cpp_class_get_fields','pointer',['pointer','pointer']),
 field_get_name:nf('il2cpp_field_get_name','pointer',['pointer']),
 field_get_type:nf('il2cpp_field_get_type','pointer',['pointer']),
 field_get_offset:nf('il2cpp_field_get_offset','uint32',['pointer']),
 class_from_type:nf('il2cpp_class_from_type','pointer',['pointer']),
 class_get_name:nf('il2cpp_class_get_name','pointer',['pointer']),
 class_is_valuetype:nf('il2cpp_class_is_valuetype','int',['pointer']),
 class_value_size:nf('il2cpp_class_value_size','int',['pointer','pointer']),
};
const d=I.domain_get(); I.thread_attach(d);
const sz=Memory.alloc(8); const arr=I.domain_get_assemblies(d,sz); const n=sz.readU64().toNumber();
let img=NULL;
for(let i=0;i<n;i++){ const a=arr.add(i*8).readPointer(); const im=I.assembly_get_image(a); if(cs(I.image_get_name(im))==='PP.Production.PPPoker.dll'){img=im;break;} }
const u=s=>Memory.allocUtf8String(s);
const fm=I.class_from_name(img,u(''),u('FloatingWindowFrameManager'));
const mInst=I.class_get_method_from_name(fm,u('get_Instance'),0);
const e=Memory.alloc(8); e.writePointer(NULL);
const inst=I.runtime_invoke(mInst,NULL,NULL,e);
console.log('inst='+inst);
function rd(off,ty){ try{ const p=inst.add(off); return ty==='i'?p.readS32():ty==='f'?p.readFloat().toFixed(3):ty==='b'?p.readU8():p; }catch(e){return '?';} }
console.log('_hasLastRect(+0xf8)='+rd(0xf8,'b')+' _isTiled(+0x64)='+rd(0x64,'b')+' _tileZoom(+0x60)='+rd(0x60,'f')+' _lastLayoutSf(+0xf4)='+rd(0xf4,'f'));
console.log('_lastRX(+0xfc)='+rd(0xfc,'i')+' _lastRY(+0x100)='+rd(0x100,'i')+' _lastRW(+0x104)='+rd(0x104,'i')+' _lastRH(+0x108)='+rd(0x108,'i'));
console.log('_windowCreatedCount(+0x50)='+rd(0x50,'i')+' _lastAppliedScaler(+0x68)='+rd(0x68,'f'));
// ScreenRegion via tipo do campo _groupDragRegion (+0x90)
const it=Memory.alloc(8); it.writePointer(ptr(0)); let f, srType=null;
while(!(f=I.class_get_fields(fm,it)).isNull()){ if(cs(I.field_get_name(f))==='_groupDragRegion'){ srType=I.field_get_type(f); break; } }
if(srType){
  const sr=I.class_from_type(srType);
  console.log('\nScreenRegion: valuetype='+I.class_is_valuetype(sr)+' size='+I.class_value_size(sr,NULL));
  const it2=Memory.alloc(8); it2.writePointer(ptr(0)); let f2;
  while(!(f2=I.class_get_fields(sr,it2)).isNull()){
    const tc=I.class_from_type(I.field_get_type(f2));
    console.log('  +0x'+I.field_get_offset(f2).toString(16)+' '+cs(I.class_get_name(tc))+' '+cs(I.field_get_name(f2)));
  }
  // le o valor atual de _groupDragRegion (16 bytes) como 4 ints e 4 floats
  console.log('  _groupDragRegion bytes as int: '+[0,4,8,12].map(o=>inst.add(0x90+o).readS32()).join(','));
  console.log('  _groupDragRegion bytes as flt: '+[0,4,8,12].map(o=>inst.add(0x90+o).readFloat().toFixed(1)).join(','));
}
send('__D__');
"""
def om(m,d):
    if m.get('type')=='send' and m['payload']=='__D__': done.set()
    elif m.get('type')=='error': print('ERR',m.get('stack')); done.set()
s=frida.attach('PPPoker.exe'); sc=s.create_script(JS); sc.on('message',om)
sc.set_log_handler(lambda l,t: print(t)); sc.load(); done.wait(10); s.detach()
