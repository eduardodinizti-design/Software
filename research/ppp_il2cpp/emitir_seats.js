// emitir_seats.js — READ-ONLY: lê HoldemManager._playerDataList e emite, por mesa,
// o mapa assento -> {uid, nick, stack}. O Python grava logs/live_seats.json.
// Offsets descobertos por recon (HoldemPlayerData: _seatId@24 _uid@32 _name@40
// _handChips@104 _isSittingOut@252; HoldemManager: _gameid@272 _playerDataList@576).
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='AppProtocol';
const PS=Process.pointerSize;
// handlers que carregam/atualizam o HoldemManager (do recon):
const HOOK=['OnEnterRoomRSP'];   // choke UNIVERSAL: entrega todas as msgs, incl. HoldemManager
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
  const offCache={};
  function offs(obj){ const cn=clsName(obj); if(offCache[cn])return offCache[cn];
    const k=il.object_get_class(obj); const it=Memory.alloc(PS); it.writePointer(ptr(0));
    const m={}; let f; while(!(f=il.class_get_fields(k,it)).isNull()){ m[cstr(il.field_get_name(f))]=il.field_get_offset(f); } offCache[cn]=m; return m; }
  function geti(obj,name){ const o=offs(obj); return o[name]!==undefined?obj.add(o[name]).readS32():null; }
  function getp(obj,name){ const o=offs(obj); return o[name]!==undefined?obj.add(o[name]).readPointer():ptr(0); }
  function items(list){ try{ if(list.isNull())return []; const n=list.add(0x18).readS32(); const a=list.add(0x10).readPointer();
    const out=[]; if(!a.isNull()&&n>0&&n<64){ for(let i=0;i<Math.min(n,9);i++){ const p=a.add(0x20+i*PS).readPointer(); if(!p.isNull())out.push(p); } } return out; }catch(e){ return []; } }
  // List<int> (cartas): backing array guarda int32 inline a partir de +0x20
  function intitems(list){ try{ if(list.isNull())return []; const n=list.add(0x18).readS32(); const a=list.add(0x10).readPointer();
    const out=[]; if(!a.isNull()&&n>0&&n<16){ for(let i=0;i<n;i++){ out.push(a.add(0x20+i*4).readS32()); } } return out; }catch(e){ return []; } }

  function snapshot(hm){ try{
    if(hm.isNull()||clsName(hm)!=='HoldemManager')return;
    const gameid=u16(getp(hm,'_gameid'))||''; const ref=(gameid.split('-')[1])||gameid||'?';
    const pl=getp(hm,'_playerDataList'); const its=items(pl); if(!its.length)return;
    const players=[]; its.forEach(pd=>{ const uid=geti(pd,'_uid'); if(!uid)return;
      players.push({seat:geti(pd,'_seatId'), uid:uid, name:(u16(getp(pd,'_name'))||'').trim(),
                    stack:geti(pd,'_handChips'), sit:geti(pd,'_isSittingOut'),
                    // --- estado completo p/ percepcao (pre-flop): aposta, acao, cartas ---
                    bet:geti(pd,'_betChips'), act:geti(pd,'_actionType'),
                    hascard:geti(pd,'_hasCard'), cards:intitems(getp(pd,'_handCardsCode'))}); });
    if(!players.length)return;
    // nivel-mesa: dealer/SB/BB (posicoes) + blind (bb = 2*sb)
    const table={dealer:geti(hm,'_nowDealerSeat'), sbseat:geti(hm,'_nowSmallBlindSeat'),
                 bbseat:geti(hm,'_nowBigBlindSeat'), sb:geti(hm,'_smallBlind'),
                 minraise:geti(hm,'_myMinBetRaiseChips'), maxraise:geti(hm,'_myMaxBetRaiseChips')};
    send({t:'seats', ref:ref, room:(u16(getp(hm,'_roomName'))||''), table:table, players:players});
  }catch(e){ console.log('[emit] erro snap:', e); } }

  let lastHM=null, dbg=0;
  HOOK.forEach(name=>{ const mi=il.class_get_method_from_name(klass, Memory.allocUtf8String(name), 2); if(mi.isNull()){console.log('[emit] (sem metodo '+name+')');return;}
    const addr=mi.readPointer(); if(addr.isNull())return;
    Interceptor.attach(addr,{ onEnter(args){ try{ const m=args[1]; const cn=clsName(m);
      if(dbg<50){ dbg++; console.log('[dbg] '+cn); }
      if(cn==='HoldemManager'){ lastHM=m; snapshot(m); }
      else { const gm=getp(m,'_gameManager'); if(!gm.isNull()&&clsName(gm)==='HoldemManager'){ lastHM=gm; snapshot(gm); } }
    }catch(e){ console.log('[emit] erro:', e); } }});
  });
  // cacheia o HoldemManager: uma vez pego, re-emite a cada 2s (robusto a baixa atividade)
  setInterval(()=>{ try{ if(lastHM) snapshot(lastHM); }catch(e){} }, 2000);
  console.log('[emit] emissor de assentos armado (READ-ONLY, cache+2s).');
}
function go(){ try{ main(); }catch(e){ console.log('[emit] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
