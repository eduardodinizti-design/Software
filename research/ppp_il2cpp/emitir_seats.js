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
    field_get_type:nf('il2cpp_field_get_type','pointer',['pointer']), type_get_type:nf('il2cpp_type_get_type','int',['pointer']),
    field_get_flags:nf('il2cpp_field_get_flags','int',['pointer']),
    field_static_get_value:nf('il2cpp_field_static_get_value','void',['pointer','pointer']),
    class_get_parent:nf('il2cpp_class_get_parent','pointer',['pointer']),
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
  // BOUNTY (PKO): acha campos por NOME na msg MTT/premio (reflexao). So nomes com
  // 'bounty' sao CONFIAVEIS; reward/prize/ko ficam como CANDIDATOS p/ calibrar ao vivo.
  // So leitura de S32 em offsets (seguro). ADITIVO: nunca afeta o caminho dos assentos.
  function scanBounty(obj){ try{ if(!obj||obj.isNull())return null; const o=offs(obj);
    const b={}, oth={};
    for(const nm in o){ let v=null;
      if(/bounty/i.test(nm)){ try{ v=obj.add(o[nm]).readS32(); }catch(e){} if(v!==null)b[nm]=v; }
      else if(/reward|bonus|knock|prize|premi/i.test(nm)){ try{ v=obj.add(o[nm]).readS32(); }catch(e){} if(v!==null)oth[nm]=v; } }
    if(!Object.keys(b).length && !Object.keys(oth).length)return null;
    return {bounty:b, other:oth}; }catch(e){ return null; } }
  function items(list){ try{ if(list.isNull())return []; const n=list.add(0x18).readS32(); const a=list.add(0x10).readPointer();
    const out=[]; if(!a.isNull()&&n>0&&n<64){ for(let i=0;i<Math.min(n,9);i++){ const p=a.add(0x20+i*PS).readPointer(); if(!p.isNull())out.push(p); } } return out; }catch(e){ return []; } }
  // List<int> (cartas): backing array guarda int32 inline a partir de +0x20
  function intitems(list){ try{ if(list.isNull())return []; const n=list.add(0x18).readS32(); const a=list.add(0x10).readPointer();
    const out=[]; if(!a.isNull()&&n>0&&n<16){ for(let i=0;i<n;i++){ out.push(a.add(0x20+i*4).readS32()); } } return out; }catch(e){ return []; } }
  // --- CAPTURA ROBUSTA do HoldemManager (sem depender de entrar na mesa) ---
  // reffields: campos de REFERENCIA (class/object/genericinst) de uma classe. SO
  // referencia -> nunca lemos value-type como ponteiro (zero deref de lixo = zero
  // risco de crash no PPPoker). Cache por classe.
  const refCache={};
  function reffields(obj){ const cn=clsName(obj); if(refCache[cn])return refCache[cn];
    const k=il.object_get_class(obj); const it=Memory.alloc(PS); it.writePointer(ptr(0));
    const out=[]; let f;
    while(!(f=il.class_get_fields(k,it)).isNull()){
      try{ const te=il.type_get_type(il.field_get_type(f))&0xff;
        if(te===0x12||te===0x1c||te===0x15){ out.push({name:cstr(il.field_get_name(f)), off:il.field_get_offset(f)}); }
      }catch(e){}
    }
    refCache[cn]=out; return out; }
  function isHM(p){ try{ if(!p||p.isNull())return false; const c=il.object_get_class(p); return !c.isNull()&&cstr(il.class_get_name(c))==='HoldemManager'; }catch(e){ return false; } }
  // Acha o HoldemManager a partir de um objeto raiz (this/dispatcher ou mensagem),
  // andando SO por campos de referencia. depth limita a recursao; a 2a passada so
  // entra em campos cujo NOME sugere manager (barato e seguro).
  // hero presente = algum assento com 2 cartas validas (so o hero fica face-up).
  function heroCards(hm){ try{ const its=items(getp(hm,'_playerDataList'));
    for(const pd of its){ const c=intitems(getp(pd,'_handCardsCode')); let v=0;
      for(const x of c){ const r=x&0xff; if(r>=2&&r<=14)v++; } if(v>=2)return true; } return false; }catch(e){ return false; } }
  function dealtCount(hm){ try{ const its=items(getp(hm,'_playerDataList')); let n=0;
    for(const pd of its){ if(geti(pd,'_hasCard'))n++; } return n; }catch(e){ return 0; } }
  // coleta HoldemManagers alcancaveis (so campos de referencia, bounded).
  function collectHM(obj, depth, acc){ try{
    if(!obj||obj.isNull()||acc.length>=12)return;
    if(isHM(obj)){ acc.push(obj); return; }
    if(depth<=0)return;
    const fs=reffields(obj);
    for(const fd of fs){ let p; try{ p=obj.add(fd.off).readPointer(); }catch(e){ continue; } if(p.isNull())continue;
      if(isHM(p)){ acc.push(p); continue; }
      if(depth>1 && /manager|game|room|holdem|table|ctrl|logic|module|scene|current|active|list/i.test(fd.name)){
        collectHM(p, depth-1, acc); } }
  }catch(e){} }
  // melhor HM = o da MESA ATIVA: prefere com HERO (2 cartas), senao mais dealt.
  function bestHM(self, m){ const acc=[]; collectHM(self,3,acc); collectHM(m,2,acc);
    let best=null, score=-1;
    for(const hm of acc){ const s=(heroCards(hm)?1000:0)+dealtCount(hm); if(s>score){ score=s; best=hm; } }
    return best; }
  // SINGLETON ESTATICO do HoldemManager (fix 24/11): o AppProtocol nao segura o HM (medido: alcancavel=
  // NENHUM). O HM eh um singleton -> acha a CLASSE por nome e le o campo ESTATICO self-type (Instance).
  // Independe de hook/mensagem. Seguro: so campos de REFERENCIA (nunca deref de value-type).
  function findHMClass(){ for(const ns of ['PP.PPPoker','PP.PPPoker.Holdem','PPPoker','Holdem','PP','']){
    try{ const k=il.class_from_name(img, Memory.allocUtf8String(ns), Memory.allocUtf8String('HoldemManager'));
      if(!k.isNull()) return k; }catch(e){} } return ptr(0); }
  let _hmStaticLog=false;
  function findHMStatic(){ try{ let k=findHMClass();
    if(k.isNull()){ if(!_hmStaticLog){_hmStaticLog=true;console.log('[diag] HM class NAO achada por nome');} return null; }
    // sobe pela hierarquia: o padrao Singleton<HoldemManager> guarda o _instance na classe-BASE.
    for(let depth=0; depth<5 && !k.isNull(); depth++){
      const it=Memory.alloc(PS); it.writePointer(ptr(0)); let f;
      while(!(f=il.class_get_fields(k,it)).isNull()){ try{
        if(!(il.field_get_flags(f) & 0x10)) continue;                            // 0x10 = STATIC
        const te=il.type_get_type(il.field_get_type(f))&0xff;
        if(te!==0x12 && te!==0x1c && te!==0x15) continue;                        // so referencia (seguro)
        const out=Memory.alloc(PS); il.field_static_get_value(f, out); const v=out.readPointer();
        if(!v.isNull() && isHM(v)){ if(!_hmStaticLog){_hmStaticLog=true;
          console.log('[diag] HM singleton: campo estatico '+cstr(il.field_get_name(f))+' @ '+clsName(v));} return v; }
      }catch(e){} }
      try{ k=il.class_get_parent(k); }catch(e){ break; }
    }
    if(!_hmStaticLog){_hmStaticLog=true;console.log('[diag] HM class OK mas sem static self-type (nem nas bases)');}
    return null;
  }catch(e){ return null; } }

  // --- BOARD (RoundStartBRC.board_) + carry do POTE: ADITIVO, nunca quebra assentos ---
  let _board=[], _stage=0, _potCarried=0, _lastBetSum=0, _curGame='', _dumpedHM=false, _diagDumped=false;
  function fieldsOf(obj){ try{ const k=il.object_get_class(obj); const it=Memory.alloc(PS); it.writePointer(ptr(0));
    const m=[]; let f; while(!(f=il.class_get_fields(k,it)).isNull()){ m.push([cstr(il.field_get_name(f)), il.field_get_offset(f)]); } return m; }catch(e){ return []; } }
  function offByName(obj,name){ for(const fo of fieldsOf(obj)){ if(fo[0]===name) return fo[1]; } return -1; }
  function readBoardRF(rf){ try{ if(rf.isNull())return []; let cntOff=-1,arrOff=-1;
    for(const fo of fieldsOf(rf)){ if(/count/i.test(fo[0]))cntOff=fo[1]; if(/array|^items$/i.test(fo[0]))arrOff=fo[1]; }
    if(arrOff<0)return []; const a=rf.add(arrOff).readPointer(); if(a.isNull())return [];
    let n=cntOff>=0?rf.add(cntOff).readS32():a.add(0x18).readS32(); if(n<0||n>7)return [];
    const out=[]; for(let i=0;i<n;i++){ out.push(a.add(0x20+i*4).readS32()); } return out; }catch(e){ return []; } }

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
    // POS-FLOP por MEMORIA (Eduardo 19/11): to_call EXATO (derivado dos betChips ja lidos)
    // + pote (derivado: carry entre ruas + bets da rua) + board (RoundStartBRC cacheado).
    let maxbet=0, betsum=0, herobet=0, heroSeat=null;
    players.forEach(p=>{ const bb=(typeof p.bet==='number'?p.bet:0); if(bb>maxbet)maxbet=bb; betsum+=bb;
      if(p.hascard && (p.cards||[]).filter(function(x){var r=x&0xff;return r>=2&&r<=14;}).length>=2){ herobet=bb; heroSeat=p.seat; } });
    _lastBetSum=betsum;
    // VEZ do heroi (ADITIVO, anti-crossing): assento que DEVE agir == assento do hero?
    // O nome exato do campo no HoldemManager varia; tenta candidatos (geti=null se nao existe,
    // seguro) e o debug unico abaixo revela o nome real ao vivo p/ afinar a lista.
    if(!_dumpedHM){ _dumpedHM=true; try{ const o=offs(hm);
      const cand=Object.keys(o).filter(function(k){return /seat|act|op|turn|cur|now/i.test(k);});
      console.log('[emit] HM campos(seat/act/op/turn/cur/now): '+cand.join(',')); }catch(e){} }
    let actSeat=null;
    ['_nowActionSeat','_nowOperateSeat','_curActionSeat','_nowActSeat','_operateSeat','_curOpSeat',
     '_actionSeat','_activeSeat','_nowOpSeat','_curOperateSeat','_nowTurnSeat'].forEach(function(nm){
       if(actSeat===null){ const v=geti(hm,nm); if(v!==null && v>=0) actSeat=v; } });
    const heroTurn=(actSeat!==null && heroSeat!==null && actSeat===heroSeat);
    if(gameid && gameid!==_curGame){ _curGame=gameid; _potCarried=0; _board=[]; _stage=0; }  // nova mao
    const tocall=Math.max(0, maxbet-herobet);
    const pot=_potCarried+betsum;
    // nivel-mesa: dealer/SB/BB (posicoes) + blind (bb = 2*sb) + board/stage/to_call/pote
    const table={dealer:geti(hm,'_nowDealerSeat'), sbseat:geti(hm,'_nowSmallBlindSeat'),
                 bbseat:geti(hm,'_nowBigBlindSeat'), sb:geti(hm,'_smallBlind'),
                 minraise:geti(hm,'_myMinBetRaiseChips'), maxraise:geti(hm,'_myMaxBetRaiseChips'),
                 board:_board.slice(), stage:_stage, tocall:tocall, pot:pot,
                 actseat:actSeat, heroseat:heroSeat, heroturn:heroTurn};
    send({t:'seats', ref:ref, room:(u16(getp(hm,'_roomName'))||''), table:table, players:players});
  }catch(e){ console.log('[emit] erro snap:', e); } }

  let lastHM=null, dbg=0;
  HOOK.forEach(name=>{ const mi=il.class_get_method_from_name(klass, Memory.allocUtf8String(name), 2); if(mi.isNull()){console.log('[emit] (sem metodo '+name+')');return;}
    const addr=mi.readPointer(); if(addr.isNull())return;
    Interceptor.attach(addr,{ onEnter(args){ try{ const m=args[1], self=args[0]; const cn=clsName(m);
      if(dbg<50){ dbg++; console.log('[dbg] '+cn); }
      // MULTI-MESA: cartas do heroi por MESA (roomid) numa msg viva -> cacheia sem varrer memoria.
      // Estrutura (recon 22/11): items_@24 (lista de MultipleTableHoleCardItem{roomid_@28,
      // cards_@32 (RepeatedField int), hadHandSqueeze_@40}). ref = roomid (mesmo da emissao seats).
      if(cn==='MultipleTableHoleCardRSP'){ try{
        const items=m.add(24).readPointer();
        const icount=items.isNull()?0:items.add(24).readS32();
        const iarr=items.isNull()?ptr(0):items.add(16).readPointer();
        for(let i=0;i<icount&&i<16;i++){ const it=iarr.add(0x20+i*Process.pointerSize).readPointer();
          if(it.isNull())continue; const roomid=it.add(28).readS32();
          const crf=it.add(32).readPointer(); const cc=crf.isNull()?0:crf.add(24).readS32();
          const ca=crf.isNull()?ptr(0):crf.add(16).readPointer(); const cards=[];
          for(let j=0;j<cc&&j<4;j++){ try{ cards.push(ca.add(0x20+j*4).readS32()); }catch(e){} }
          if(cards.length) send({t:'holecards', ref:(''+roomid), cards:cards}); }
      }catch(e){ console.log('[emit] erro multihole:', e); } return; }
      // BOUNTY (aditivo e guardado): em msg MTT/premio, emite candidatos de bounty.
      try{ if(/mtt|bounty|reward|prize|premi/i.test(cn)){ const bo=scanBounty(m);
        if(bo){ const sb=(lastHM&&!lastHM.isNull())?geti(lastHM,'_smallBlind'):null;
          send({t:'bounty', cls:cn, bounty:bo.bounty, other:bo.other, sb:sb}); } } }catch(e){}
      if(cn==='HoldemManager'){ lastHM=m; snapshot(m); return; }
      // RASTREIA A MESA ATIVA: se nao temos HM OU o atual perdeu o hero (fim da mao /
      // trocou de mesa no rebalanceamento), re-escolhe o melhor HM (o do hero). Barato:
      // so re-busca quando o lastHM nao tem hero. Dispatcher fira em TODA msg.
      if(!lastHM || !heroCards(lastHM)){ const hm=bestHM(self,m);
        if(hm && hm!==lastHM && (heroCards(hm) || !lastHM)){
          lastHM=hm; console.log('[emit] HM da mesa ATIVA (hero='+heroCards(hm)+', dealt='+dealtCount(hm)+')'); snapshot(hm); } }
    }catch(e){ console.log('[emit] erro:', e); } }});
  });
  // BOARD (ADITIVO): hook em OnRoundStartBRC -> decodifica board_ (RepeatedField) e cacheia.
  // Carry do pote: ao começar FLOP/TURN/RIVER (stage>=2) as apostas da rua anterior foram
  // recolhidas -> entram no _potCarried. Nunca quebra os assentos (try/catch).
  try{ const mr=il.class_get_method_from_name(klass, Memory.allocUtf8String('OnRoundStartBRC'), 2);
    if(!mr.isNull()){ const ra=mr.readPointer(); if(!ra.isNull()){
      Interceptor.attach(ra,{ onEnter(args){ try{ const msg=args[1]; if(clsName(msg)!=='RoundStartBRC')return;
        const so=offByName(msg,'stage_'); const st=so>=0?msg.add(so).readS32():0;
        const bo=offByName(msg,'board_'); const rf=bo>=0?msg.add(bo).readPointer():ptr(0);
        const b=readBoardRF(rf);
        if(st>=2){ _potCarried += _lastBetSum; } else { _potCarried = 0; }
        _stage=st; _board=b;
        console.log('[emit] board stage='+st+' n='+b.length);
        // DIAGNÓSTICO 24/11 (seats mortos): dump ÚNICO do grafo a partir do self do board hook, p/ VER
        // onde o HoldemManager está alcançável (só campos de REFERÊNCIA = seguro). Mostra o caminho real.
        if(!_diagDumped){ _diagDumped=true; try{ const self=args[0];
          console.log('[diag] board self cls='+clsName(self)+' | msg cls='+clsName(msg));
          for(const fd of reffields(self)){ try{ const p=self.add(fd.off).readPointer();
            if(!p.isNull()) console.log('[diag]  self.'+fd.name+' -> '+clsName(p)); }catch(e){} }
          const acc=[]; (function walk(o,d,path){ if(!o||o.isNull()||acc.length>=25||d<0)return;
            if(isHM(o)){ acc.push(path); return; }
            for(const fd of reffields(o)){ try{ const p=o.add(fd.off).readPointer();
              if(!p.isNull()) walk(p,d-1,path+'.'+fd.name); }catch(e){} } })(self,5,'self');
          console.log('[diag] HoldemManager alcançável em: '+(acc.join(' | ')||'NENHUM caminho <=5'));
        }catch(e){ console.log('[diag] erro:', e); } }
        // FIX 24/11 (seats parados): OnEnterRoomRSP deixou de disparar (PPPoker mudou o dispatcher) ->
        // lastHM nunca era setado -> snapshot nunca rodava -> 0 seats (so board). Este hook
        // (OnRoundStartBRC) FUNCIONA -> acho o HoldemManager a partir DELE (bestHM, args[0]=dispatcher,
        // msg). Uma vez setado lastHM, o board + o setInterval(2s) voltam a emitir seats/to_call.
        if(!lastHM || !heroCards(lastHM)){ try{ let hm=bestHM(args[0], msg);
          if(!hm) hm=findHMStatic();                     // AppProtocol nao segura o HM -> singleton estatico
          if(hm && (heroCards(hm) || !lastHM)){ lastHM=hm;
            console.log('[emit] HM pego (hero='+heroCards(hm)+', dealt='+dealtCount(hm)+')'); } }catch(e){} }
        if(lastHM) snapshot(lastHM);
      }catch(e){} } });
      console.log('[emit] hook board (RoundStartBRC) armado.'); } }
  }catch(e){ console.log('[emit] (sem OnRoundStartBRC):', e); }
  // cacheia o HoldemManager: uma vez pego, re-emite a cada 2s (robusto a baixa atividade)
  setInterval(()=>{ try{ if(!lastHM){ const hm=findHMStatic(); if(hm){ lastHM=hm; console.log('[emit] HM via SINGLETON (polling 2s)'); } } if(lastHM) snapshot(lastHM); }catch(e){} }, 2000);
  console.log('[emit] emissor de assentos armado (READ-ONLY, cache+2s).');
}
function go(){ try{ main(); }catch(e){ console.log('[emit] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
