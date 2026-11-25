// recon_enterroom.js — READ-ONLY: dumpa a estrutura de EnterRoomRSP/SeatStatusBRC
// p/ achar o mapa ASSENTO -> (account/ID + nick). So LE. Base: capturar_maos.js.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='AppProtocol';
const HOOK=['OnEnterRoomRSP','OnSitDownRSP','OnSitDownBRC','OnOtherEnterRoomBRC','OnRoomInfoUpdateBRC','OnMttTableRSP','OnDealerInfoRSP'];
const PS=Process.pointerSize;
function cstr(p){try{return p.isNull()?'':p.readCString();}catch(e){return '';}}
function u16(p){ try{ if(p.isNull())return null; const len=p.add(0x10).readS32(); if(len<0||len>200)return null; return p.add(0x14).readUtf16String(len);}catch(e){return null;} }
let _M=null; function exp(x){if(!_M)_M=Process.getModuleByName(MOD);return _M.getExportByName(x);}
function nf(x,r,a){return new NativeFunction(exp(x),r,a);}
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
  const sp=Memory.alloc(PS); const arr=il.domain_get_assemblies(d,sp); const cnt=sp.readU64().toNumber();
  let img=ptr(0);
  for(let a=0;a<cnt;a++){ const im=il.assembly_get_image(arr.add(a*PS).readPointer());
    if(cstr(il.image_get_name(im)).toLowerCase().indexOf('pppoker')>=0){ img=im; break; } }
  const klass=il.class_from_name(img, Memory.allocUtf8String(NS), Memory.allocUtf8String(CLS));
  const clsName=(o)=>{ try{ return o.isNull()?'null':cstr(il.class_get_name(il.object_get_class(o))); }catch(e){ return '?'; } };
  function fieldsOf(obj){ const k=il.object_get_class(obj); const it=Memory.alloc(PS); it.writePointer(ptr(0));
    const out=[]; let f; while(!(f=il.class_get_fields(k,it)).isNull()){ out.push([cstr(il.field_get_name(f)), il.field_get_offset(f)]); } return out; }
  function dump(obj,label){ if(obj.isNull()){console.log(label+'=null');return;} console.log(label+' ['+clsName(obj)+']');
    fieldsOf(obj).forEach(([nm,off])=>{ let s32=null,pcn=null,str=null;
      try{s32=obj.add(off).readS32();}catch(e){}
      try{const p=obj.add(off).readPointer(); if(!p.isNull()){pcn=clsName(p); if(pcn==='String')str=u16(p);}}catch(e){}
      console.log('   @'+off+' '+nm+' = '+s32+(str!=null?('  str="'+str+'"'):'')+(pcn&&pcn!=='String'?('  ->['+pcn+']'):'')); }); }
  // RepeatedField (mesmo layout do capturar_maos): array@16, count@24, itens@array+0x20
  function listItems(rf){ try{ if(rf.isNull())return []; const count=rf.add(24).readS32(); const a=rf.add(16).readPointer();
    const out=[]; if(!a.isNull()&&count>0&&count<64){ for(let i=0;i<Math.min(count,9);i++){ out.push(a.add(0x20+i*PS).readPointer()); } } return out; }catch(e){ return []; } }

  HOOK.forEach(name=>{ const mi=il.class_get_method_from_name(klass, Memory.allocUtf8String(name), 2); if(mi.isNull()){console.log('[recon] (sem metodo '+name+')');return;}
    const addr=mi.readPointer(); if(addr.isNull())return;
    Interceptor.attach(addr,{ onEnter(args){ try{
      const msg=args[1]; console.log('\n======== '+name+'  msg=['+clsName(msg)+'] ========');
      dump(msg,'MSG');
      // procura campos que pareçam lista de assentos e dumpa os itens
      fieldsOf(msg).forEach(([nm,off])=>{ let p=ptr(0); try{p=msg.add(off).readPointer();}catch(e){}
        if(p.isNull())return; const pcn=clsName(p); const low=nm.toLowerCase();
        if(low.indexOf('seat')>=0||low.indexOf('player')>=0||low.indexOf('user')>=0||pcn.indexOf('Seat')>=0||pcn.indexOf('Player')>=0){
          const items=listItems(p); if(items.length){ console.log('  >>> LISTA '+nm+' ['+pcn+'] itens='+items.length);
            items.forEach((it,i)=>dump(it,'     ITEM['+i+']')); }
        }
      });
    }catch(e){ console.log('[recon] erro:', e.stack||e); } }});
  });
  console.log('[recon] hooks EnterRoom/SeatStatus armados. Abra/entre numa mesa p/ disparar o dump.');
}
function go(){ try{ main(); }catch(e){ console.log('[recon] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
