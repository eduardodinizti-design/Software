// hook_deal.js — HOOK READ-ONLY das mensagens de DEAL/CHOP. O "deal" com botões
// aceitar/rejeitar na FT é o EvChop (EV chop) do TableProtocol; mantém também o
// MttDivideReward do MttProtocol. So LE — NAO aceita, NAO rejeita, NAO envia nada.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker';
const TARGETS={
  TableProtocol:['OnEvChopInfoBRC','OnEvChopOperationRSP','OnEvChopOperationBRC','OnEvChopOverBRC',
                 'OnEvchopUserSettingRSP','OnEvchopGetUserSettingRSP'],
  MttProtocol:['OnMttDivideRewardBRC','OnHostDivideRewardBRC','OnHostDivideRewardRSP',
               'OnPlayerVoteDivideRSP','OnPlayerRefuseDivideBRC'],
};
const DEAL_RE=/EvChop|Chop|Divide|Reward|Refuse|Vote/i;
let n=0;
function cstr(p){try{return p.isNull()?'':p.readCString();}catch(e){return '';}}
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
  const sp=Memory.alloc(Process.pointerSize); const arr=il.domain_get_assemblies(d,sp); const cnt=sp.readU64().toNumber();
  let img=ptr(0);
  for(let a=0;a<cnt;a++){ const im=il.assembly_get_image(arr.add(a*Process.pointerSize).readPointer());
    if(cstr(il.image_get_name(im)).toLowerCase().indexOf('pppoker')>=0){ img=im; break; } }
  const clsName=(o)=>{ try{ return o.isNull()?'null':cstr(il.class_get_name(il.object_get_class(o))); }catch(e){ return '?'; } };
  function dump(obj){ const k=il.object_get_class(obj); const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
    let f, lines=[]; while(!(f=il.class_get_fields(k,it)).isNull()){ const fn=cstr(il.field_get_name(f)); const off=il.field_get_offset(f);
      if(/FieldNumber$|DefaultValue$|^_parser$|^_unknownFields$|^_hasBits/.test(fn)) continue;
      let v; try{ const i=obj.add(off).readS32(); const p=obj.add(off).readPointer(); const pc=(!p.isNull()&&p.compare(ptr('0x10000'))>0)?clsName(p):null; v=pc&&pc!=='?'?('->'+pc):i; }catch(e){ v='?'; }
      lines.push(fn+'@'+off+'='+v); } return lines.join('  '); }
  let hooked=0, miss=[];
  for(const cls in TARGETS){
    const klass=il.class_from_name(img, Memory.allocUtf8String(NS), Memory.allocUtf8String(cls));
    if(klass.isNull()){ miss.push(cls); continue; }
    TARGETS[cls].forEach(name=>{ const mi=il.class_get_method_from_name(klass, Memory.allocUtf8String(name), 2); if(mi.isNull())return;
      const addr=mi.readPointer(); if(addr.isNull())return;
      Interceptor.attach(addr,{ onEnter(args){ const cn=clsName(args[1]);
        if(!DEAL_RE.test(cn)) return;
        n++; console.log('\n[DEAL #'+n+'] (via '+cls+'.'+name+') '+cn+':\n   '+dump(args[1])); }}); hooked++;
    });
  }
  console.log('[deal] '+hooked+' hooks armados (READ-ONLY)'+(miss.length?(' | classes nao achadas: '+miss.join(',')):'')+'. Esperando deal/chop...');
}
function go(){ try{ main(); }catch(e){ console.log('[deal] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
