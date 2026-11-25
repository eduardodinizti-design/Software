"""Campos de ScreenRegion e FloatingWindowFrameManager + metodos/ctor de ScreenRegion."""
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
 class_get_fields:nf('il2cpp_class_get_fields','pointer',['pointer','pointer']),
 field_get_name:nf('il2cpp_field_get_name','pointer',['pointer']),
 field_get_type:nf('il2cpp_field_get_type','pointer',['pointer']),
 field_get_offset:nf('il2cpp_field_get_offset','uint32',['pointer']),
 class_get_methods:nf('il2cpp_class_get_methods','pointer',['pointer','pointer']),
 method_get_name:nf('il2cpp_method_get_name','pointer',['pointer']),
 method_get_param_count:nf('il2cpp_method_get_param_count','uint32',['pointer']),
 method_get_param:nf('il2cpp_method_get_param','pointer',['pointer','uint32']),
 method_get_param_name:nf('il2cpp_method_get_param_name','pointer',['pointer','uint32']),
 class_from_type:nf('il2cpp_class_from_type','pointer',['pointer']),
 class_get_name:nf('il2cpp_class_get_name','pointer',['pointer']),
 class_get_namespace:nf('il2cpp_class_get_namespace','pointer',['pointer']),
 class_is_valuetype:nf('il2cpp_class_is_valuetype','int',['pointer']),
 class_value_size:nf('il2cpp_class_value_size','int',['pointer','pointer']),
};
const d=I.domain_get(); I.thread_attach(d);
const sz=Memory.alloc(8); const arr=I.domain_get_assemblies(d,sz); const n=sz.readU64().toNumber();
let img=NULL;
for(let i=0;i<n;i++){ const a=arr.add(i*8).readPointer(); const im=I.assembly_get_image(a); if(cs(I.image_get_name(im))==='PP.Production.PPPoker.dll'){img=im;break;} }
const u=s=>Memory.allocUtf8String(s);
function tname(t){ try{ const c=I.class_from_type(t); const ns=cs(I.class_get_namespace(c)); return (ns?ns+'.':'')+cs(I.class_get_name(c)); }catch(e){return '?';} }
function fields(k, label){
  console.log('\n== CAMPOS '+label+' (valuetype='+I.class_is_valuetype(k)+' size='+I.class_value_size(k,NULL)+') ==');
  const it=Memory.alloc(8); it.writePointer(ptr(0)); let f;
  while(!(f=I.class_get_fields(k,it)).isNull()){
    console.log('  +0x'+I.field_get_offset(f).toString(16)+' '+tname(I.field_get_type(f))+' '+cs(I.field_get_name(f)));
  }
}
function methods(k,label){
  console.log('\n== METODOS '+label+' ==');
  const it=Memory.alloc(8); it.writePointer(ptr(0)); let m;
  while(!(m=I.class_get_methods(k,it)).isNull()){
    const nm=cs(I.method_get_name(m)); const pc=I.method_get_param_count(m); let ps=[];
    for(let i=0;i<pc;i++){ ps.push(tname(I.method_get_param(m,i))+' '+cs(I.method_get_param_name(m,i))); }
    console.log('  '+nm+'('+ps.join(', ')+')');
  }
}
const sr=I.class_from_name(img,u(''),u('ScreenRegion'));
if(sr.isNull()){ console.log('ScreenRegion nao achada no namespace vazio'); }
else { fields(sr,'ScreenRegion'); methods(sr,'ScreenRegion'); }
const fm=I.class_from_name(img,u(''),u('FloatingWindowFrameManager'));
fields(fm,'FloatingWindowFrameManager');
send('__D__');
"""
def om(m,d):
    if m.get('type')=='send' and m['payload']=='__D__': done.set()
    elif m.get('type')=='error': print('ERR',m.get('stack')); done.set()
s=frida.attach('PPPoker.exe'); sc=s.create_script(JS); sc.on('message',om)
sc.set_log_handler(lambda l,t: print(t)); sc.load(); done.wait(10); s.detach()
