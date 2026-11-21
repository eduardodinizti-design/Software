// recon_assentos.js — RECON READ-ONLY do UI Unity do PPPoker p/ achar os ASSENTOS na tela.
// Enumera classes cujo nome casa /Table|Seat|MultiTable|View|Room|Hud|Player/ e dumpa seus
// campos (nome + tipo), destacando RectTransform / roomId / seatId / UnityEngine. Objetivo:
// achar o painel-raiz da mesa (RectTransform = retângulo do tile) + o roomid + os assentos.
'use strict';
const MOD = 'GameAssembly.dll';
const RE_CLASS = /Table|MultiTable|SeatView|SeatItem|SeatUI|RoomView|TableView|TableUI|PlayerView|PlayerItem|HudView/i;
const RE_FIELD = /rect|transform|roomid|room_|tableid|seatid|seat_|position|pos_|uid|canvas|rooturl|screen/i;
const MAX_CLASSES = 120;

function cstr(p){try{return p.isNull()?'':p.readCString();}catch(e){return '';}}
let _M=null; function exp(n){if(!_M)_M=Process.getModuleByName(MOD);return _M.getExportByName(n);}
function nf(n,r,a){return new NativeFunction(exp(n),r,a);}

function main(){
  const il={
    domain_get:nf('il2cpp_domain_get','pointer',[]), thread_attach:nf('il2cpp_thread_attach','pointer',['pointer']),
    domain_get_assemblies:nf('il2cpp_domain_get_assemblies','pointer',['pointer','pointer']),
    assembly_get_image:nf('il2cpp_assembly_get_image','pointer',['pointer']), image_get_name:nf('il2cpp_image_get_name','pointer',['pointer']),
    image_get_class_count:nf('il2cpp_image_get_class_count','uint32',['pointer']),
    image_get_class:nf('il2cpp_image_get_class','pointer',['pointer','uint32']),
    class_get_name:nf('il2cpp_class_get_name','pointer',['pointer']), class_get_namespace:nf('il2cpp_class_get_namespace','pointer',['pointer']),
    class_get_fields:nf('il2cpp_class_get_fields','pointer',['pointer','pointer']),
    field_get_name:nf('il2cpp_field_get_name','pointer',['pointer']), field_get_offset:nf('il2cpp_field_get_offset','uint32',['pointer']),
    field_get_type:nf('il2cpp_field_get_type','pointer',['pointer']), type_get_name:nf('il2cpp_type_get_name','pointer',['pointer']),
  };
  const d=il.domain_get(); il.thread_attach(d);
  const sp=Memory.alloc(Process.pointerSize); const arr=il.domain_get_assemblies(d,sp); const cnt=sp.readU64().toNumber();
  let found=0;
  for(let a=0;a<cnt && found<MAX_CLASSES;a++){
    const asm=arr.add(a*Process.pointerSize).readPointer(); const img=il.assembly_get_image(asm);
    const imgName=cstr(il.image_get_name(img));
    let nclasses=0; try{ nclasses=il.image_get_class_count(img); }catch(e){ continue; }
    for(let c=0;c<nclasses && found<MAX_CLASSES;c++){
      let klass; try{ klass=il.image_get_class(img,c); }catch(e){ continue; }
      if(klass.isNull())continue;
      const name=cstr(il.class_get_name(klass)); if(!RE_CLASS.test(name))continue;
      // dumpa campos
      const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
      const fields=[]; let f;
      try{ while(!(f=il.class_get_fields(klass,it)).isNull()){ const fn=cstr(il.field_get_name(f));
        let tn=''; try{ tn=cstr(il.type_get_name(il.field_get_type(f))); }catch(e){}
        const off=il.field_get_offset(f);
        if(RE_FIELD.test(fn)||/RectTransform|Transform|Canvas|Vector/.test(tn)) fields.push(fn+'@'+off+':'+tn);
      } }catch(e){}
      if(fields.length){ send({cls:name, img:imgName.replace('.dll',''), fields:fields}); found++; }
    }
  }
  send({done:found});
}
function go(){ try{ main(); }catch(e){ console.log('[recon] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
