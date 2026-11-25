// capturar_maos.js — HOOK READ-ONLY: lê os campos dos handlers de mão do AppProtocol e
// manda eventos estruturados p/ o Python montar a mão (HandAccumulator). So LE.
'use strict';
const MOD='GameAssembly.dll', NS='PP.PPPoker', CLS='AppProtocol';
const HOOK=['OnAnteBRC','OnRoundStartBRC','OnHandCardRSP','OnActionBRC','OnRoundOverBRC','OnWinnerRSP',
  'OnDealerInfoRSP','OnSeatStatusBRC','OnSitDownBRC','OnShowHandRSP','OnEnterRoomRSP'];
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
    image_get_class_count:nf('il2cpp_image_get_class_count','uint32',['pointer']),
    image_get_class:nf('il2cpp_image_get_class','pointer',['pointer','uint32']),
    class_get_type:nf('il2cpp_class_get_type','pointer',['pointer']), type_get_object:nf('il2cpp_type_get_object','pointer',['pointer']),
  };
  const d=il.domain_get(); il.thread_attach(d);
  const sp=Memory.alloc(Process.pointerSize); const arr=il.domain_get_assemblies(d,sp); const cnt=sp.readU64().toNumber();
  let img=ptr(0);
  for(let a=0;a<cnt;a++){ const im=il.assembly_get_image(arr.add(a*Process.pointerSize).readPointer());
    if(cstr(il.image_get_name(im)).toLowerCase().indexOf('pppoker')>=0){ img=im; break; } }
  const klass=il.class_from_name(img, Memory.allocUtf8String(NS), Memory.allocUtf8String(CLS));
  const clsName=(o)=>{ try{ return o.isNull()?'null':cstr(il.class_get_name(il.object_get_class(o))); }catch(e){ return '?'; } };
  const offCache={};
  function offs(obj){ const cn=clsName(obj); if(offCache[cn])return offCache[cn];
    const k=il.object_get_class(obj); const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
    const m={}; let f; while(!(f=il.class_get_fields(k,it)).isNull()){ m[cstr(il.field_get_name(f))]=il.field_get_offset(f); } offCache[cn]=m; return m; }
  function geti(obj,name){ const o=offs(obj); return o[name]!==undefined?obj.add(o[name]).readS32():null; }
  function getp(obj,name){ const o=offs(obj); return o[name]!==undefined?obj.add(o[name]).readPointer():ptr(0); }
  function readRFints(rf){ if(rf.isNull())return []; let count=0,a=ptr(0);
    try{ count=rf.add(24).readS32(); a=rf.add(16).readPointer(); }catch(e){ return []; }
    const out=[]; if(!a.isNull()){ for(let i=0;i<Math.min(count,5);i++){ try{ out.push(a.add(0x20+i*4).readS32()); }catch(e){} } } return out; }
  // RepeatedField de OBJETOS (ponteiros): devolve até max elementos p/ ler por geti/getp.
  function readRFobjs(rf,max){ if(rf.isNull())return []; let count=0,a=ptr(0);
    try{ count=rf.add(24).readS32(); a=rf.add(16).readPointer(); }catch(e){ return []; }
    const out=[]; if(!a.isNull()){ for(let i=0;i<Math.min(count,max||12);i++){ try{ const p=a.add(0x20+i*Process.pointerSize).readPointer(); if(!p.isNull())out.push(p); }catch(e){} } } return out; }
  function uidOf(ss){ try{ const pl=getp(ss,'player_'); return pl.isNull()?0:(geti(pl,'uid_')||0); }catch(e){ return 0; } }
  // string IL2CPP (UTF-16): len@0x10, chars@0x14. Devolve '' se vazio/inválido.
  function readStr(obj,name){ try{ const o=offs(obj); if(o[name]===undefined)return ''; const p=obj.add(o[name]).readPointer();
    if(p.isNull()||p.compare(ptr('0x10000'))<=0)return ''; const len=p.add(0x10).readS32(); if(len<=0||len>64)return '';
    return p.add(0x14).readUtf16String(len); }catch(e){ return ''; } }
  function nickOf(ss){ try{ const pl=getp(ss,'player_'); return pl.isNull()?'':readStr(pl,'name_'); }catch(e){ return ''; } }
  // bounty (PKO): hunterBonus no SeatStatus; starBounty p/ star hunter.
  function bountyOf(ss){ const hb=geti(ss,'hunterBonus_')||0, sb=geti(ss,'starBounty_')||0; return hb||sb||0; }

  // ---- TILES: roomid por PÁGINA (ordem) p/ o auto-posicionamento do HUD (main thread) ----
  let _coreImg=ptr(0);
  for(let a=0;a<cnt;a++){ const im=il.assembly_get_image(arr.add(a*Process.pointerSize).readPointer());
    if(cstr(il.image_get_name(im)).toLowerCase().indexOf('unityengine.coremodule')>=0){ _coreImg=im; break; } }
  function classByName(image,name){ if(image.isNull())return ptr(0); let n=0; try{ n=il.image_get_class_count(image); }catch(e){ return ptr(0); }
    for(let i=0;i<n;i++){ let c; try{ c=il.image_get_class(image,i); }catch(e){ continue; } if(c.isNull())continue;
      if(cstr(il.class_get_name(c))===name) return c; } return ptr(0); }
  const _mtPage=classByName(img,'MultiTablePage');
  const _objCls=_coreImg.isNull()?ptr(0):il.class_from_name(_coreImg, Memory.allocUtf8String('UnityEngine'), Memory.allocUtf8String('Object'));
  const _findM=_objCls.isNull()?ptr(0):il.class_get_method_from_name(_objCls, Memory.allocUtf8String('FindObjectsOfType'), 1);
  function findTablePages(){ if(_mtPage.isNull()||_findM.isNull())return null;
    try{ const t=il.type_get_object(il.class_get_type(_mtPage)); const f=new NativeFunction(_findM.readPointer(),'pointer',['pointer','pointer']);
      const parr=f(t,_findM); if(parr.isNull())return []; const len=parr.add(0x18).readS32(); const out=[];
      for(let i=0;i<Math.min(len,16);i++){ const p=parr.add(0x20+i*Process.pointerSize).readPointer(); if(p.isNull())continue;
        let roomid=0; try{ const ti=p.add(120).readPointer(); if(!ti.isNull())roomid=ti.add(16).readS32(); }catch(e){} out.push(roomid); }
      return out; }catch(e){ return null; } }
  let _lastTiles=0;
  function maybeTiles(){ const now=Date.now(); if(now-_lastTiles<3000)return; _lastTiles=now;
    try{ const order=findTablePages(); if(order&&order.length) send({t:'tiles', order:order}); }catch(e){} }

  HOOK.forEach(name=>{ const mi=il.class_get_method_from_name(klass, Memory.allocUtf8String(name), 2); if(mi.isNull())return;
    const addr=mi.readPointer(); if(addr.isNull())return;
    Interceptor.attach(addr,{ onEnter(args){ try{
      const msg=args[1]; const cn=clsName(msg);
      // DISCRIMINADOR DE MESA (multi-tabling): args[2] = roomid da mesa do evento
      // (provado ao vivo 20/11: separa as mesas; ActionBRC/RoundStart não têm no corpo).
      const room=(function(){try{return args[2].toUInt32();}catch(e){return 0;}})();
      const S=function(o){o.room=room;send(o);};
      maybeTiles();       // emite a ordem de tiles (throttled) p/ o HUD auto-posicionar
      if(cn==='AnteBRC'){ S({t:'ante', amount:geti(msg,'ante_')||0}); }
      else if(cn==='RoundStartBRC'){ const hc=getp(msg,'handCard_'); let hero=[];
        if(!hc.isNull()){ const c1=geti(hc,'card1_')||0, c2=geti(hc,'card2_')||0; hero=[c1,c2].filter(x=>x>0); }
        S({t:'round_start', stage:geti(msg,'stage_')||0, cur_blind:geti(msg,'curBlind_')||0,
              board:readRFints(getp(msg,'board_')), hero_cards:hero}); }
      else if(cn==='HandCardRSP'){ const c1=geti(msg,'card1_')||0, c2=geti(msg,'card2_')||0;
        S({t:'hand_card', cards:[c1,c2].filter(x=>x>0)}); }
      else if(cn==='ActionBRC'){ S({t:'action', seat:geti(msg,'seatid_')||0, atype:geti(msg,'actionType_')||0,
              chips:geti(msg,'chips_')||0, hand_chips:geti(msg,'handChips_')||0}); }
      else if(cn==='RoundOverBRC'){ S({t:'round_over'}); }
      else if(cn==='DealerInfoRSP'){ const seats=[];
        readRFobjs(getp(msg,'startInfo_'),12).forEach(si=>{ seats.push({seat:geti(si,'seatid_')||0, stack:geti(si,'chips_')||0, in_game:geti(si,'isInGame_')||0, bounty:geti(si,'hunterBonus_')||0}); });
        S({t:'dealer', button:geti(msg,'dealer_'), sb_seat:geti(msg,'smallBlind_'), bb_seat:geti(msg,'bigBlind_'), seats:seats}); }
      else if(cn==='SeatStatusBRC' || cn==='SitDownBRC'){ // SeatStatus (direto) ou embrulhado em status_
        let ss=msg; if(getp(msg,'player_').isNull()){ const st=getp(msg,'status_'); if(!st.isNull())ss=st; }
        const seat=geti(ss,'seatid_'); if(seat!==null) S({t:'seat', seat:seat, uid:uidOf(ss), nick:nickOf(ss), stack:geti(ss,'handChips_')||0, bounty:bountyOf(ss), hero:((geti(ss,'card1_')||0)>0)}); }
      else if(cn==='ShowHandRSP'){ const shows=[];
        readRFobjs(getp(msg,'info_'),10).forEach(si=>{ const cs=[geti(si,'card1_')||0,geti(si,'card2_')||0,geti(si,'card3_')||0,geti(si,'card4_')||0].filter(x=>x>0);
          shows.push({seat:geti(si,'seatid_')||0, cards:cs}); });
        S({t:'show', shows:shows}); }
      else if(cn==='EnterRoomRSP'){ // ROSTER completo ao entrar: varre campos RepeatedField de
        // objetos-assento (têm seatid_) e emite uid+nick de cada um (p/ o HUD).
        try{ const o=offs(msg); for(const fn in o){ let p; try{ p=msg.add(o[fn]).readPointer(); }catch(e){ continue; }
          if(p.isNull()||p.compare(ptr('0x10000'))<=0) continue; if(!/RepeatedField/.test(clsName(p))) continue;
          readRFobjs(p,12).forEach(el=>{ let seat; try{ seat=geti(el,'seatid_'); }catch(e){ seat=null; }
            if(seat===null) return; S({t:'seat', seat:seat, uid:uidOf(el), nick:nickOf(el), stack:geti(el,'handChips_')||0, bounty:bountyOf(el)}); }); } }catch(e){} }
      else if(cn==='WinnerRSP'){ const winners=[], seat_uids=[];
        readRFobjs(getp(msg,'winner_'),12).forEach(w=>{ winners.push({seat:geti(w,'seatid_')||0, uid:geti(w,'uid_')||0, chips:geti(w,'chips_')||0}); });
        readRFobjs(getp(msg,'currentProfit_'),12).forEach(u=>{ seat_uids.push({seat:geti(u,'seatid_')||0, uid:geti(u,'uid_')||0}); });
        S({t:'winner', winners:winners, seat_uids:seat_uids}); }
    }catch(e){ console.log('[cap] erro:', e); } }});
  });
  console.log('[cap] hooks de mão armados (READ-ONLY). Capturando mãos...');
}
function go(){ try{ main(); }catch(e){ console.log('[cap] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
