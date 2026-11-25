// suprema_capture_agent.js — agente Frida no SupremaPoker.exe (Cocos Creator + V8, x86).
// Reusa o caminho de injeção JÁ VERIFICADO por RE no organizador (NVT-Mesas):
//   se::ScriptEngine::getInstance() [RVA 0x2ac54] + evalString(this, code, -1, NULL, NULL)
//   [RVA 0x2a85e, thiscall]; jobs rodam na MAIN THREAD no hook de Director::drawScene.
//
// PAPEL NA CAPTURA: injeta JS do PRÓPRIO jogo que ESCUTA o fluxo da mão (spp.*/WebSocket)
// e cospe eventos marcados via console.log('[[NVT]]...'). Este agente HOOKA o log nativo
// (OutputDebugStringA/W — p/ onde o cc.log/console.log do Cocos vai no Windows) e
// ENCAMINHA só as linhas marcadas p/ o Python via send(). READ-ONLY: não altera jogo.
'use strict';

const COCOS = 'libcocos2d.dll';
const EXE = 'SupremaPoker.exe';
const RVA_GETINST = 0x2ac54;   // se::ScriptEngine::getInstance (cdecl -> ptr)
const RVA_EVAL = 0x2a85e;      // se::ScriptEngine::evalString (thiscall)
const TAG = '[[NVT]]';         // prefixo das linhas que o JS do jogo emite p/ nós

let _exeBase = null, _seGet = null, _seEval = null;
function resolveEval() {
  if (!_exeBase) _exeBase = Process.getModuleByName(EXE).base;
  if (!_seGet) _seGet = new NativeFunction(_exeBase.add(RVA_GETINST), 'pointer', []);
  if (!_seEval) _seEval = new NativeFunction(_exeBase.add(RVA_EVAL), 'int',
    ['pointer', 'pointer', 'int', 'pointer', 'pointer'], 'thiscall');
}
function doEval(code) {
  resolveEval();
  const se = _seGet();
  if (se.isNull()) throw new Error('se::ScriptEngine instance == null');
  const s = Memory.allocUtf8String(code);
  return _seEval(se, s, -1, NULL, NULL);
}

// fila executada na MAIN THREAD (pump no drawScene) — evalString fora dela desestabiliza o V8.
const SYM_DRAW = '?drawScene@Director@cocos2d@@QAEXXZ';
const queue = [];
let _pumpHooked = false;
function pump() {
  if (_pumpHooked) return;
  const mod = Process.getModuleByName(COCOS);
  const draw = mod.findExportByName(SYM_DRAW);
  if (!draw) { console.log('[agent] drawScene nao encontrado; jobs nao vao rodar'); return; }
  Interceptor.attach(draw, {
    onEnter() { while (queue.length) { const j = queue.shift(); try { j(); } catch (e) { console.log('[agent] job err: ' + e); } } }
  });
  _pumpHooked = true;
}
function onMain(fn) {
  return new Promise((res, rej) => { pump(); queue.push(() => { try { res(fn()); } catch (e) { rej(e); } }); });
}

// ---- ponte de SAÍDA: linhas de log do jogo marcadas com TAG viram send() p/ o Python ----
function handleLogLine(line) {
  if (!line) return;
  const i = line.indexOf(TAG);
  if (i < 0) return;                 // só nos interessa o que o nosso JS injetado emitiu
  const payload = line.slice(i + TAG.length);
  try { send({ nvt: JSON.parse(payload) }); }      // evento estruturado
  catch (e) { send({ nvt_raw: payload }); }         // texto solto (recon)
}
let _logHooked = false;
function hookLogs() {
  if (_logHooked) return;
  const k = Process.getModuleByName('kernel32.dll');
  const a = k.findExportByName('OutputDebugStringA');
  if (a) Interceptor.attach(a, { onEnter(args) { try { handleLogLine(args[0].readAnsiString()); } catch (e) {} } });
  const w = k.findExportByName('OutputDebugStringW');
  if (w) Interceptor.attach(w, { onEnter(args) { try { handleLogLine(args[0].readUtf16String()); } catch (e) {} } });
  _logHooked = true;
}

// Hooks extras de log, achados ao vivo (ex.: export de log do libcocos2d). O runner pode
// pedir p/ hookar um endereço/símbolo que o DebugSymbol revelar, se console.log NÃO cair
// em OutputDebugString neste build.
function hookLogAt(addrStr) {
  try {
    const p = ptr(addrStr);
    Interceptor.attach(p, { onEnter(args) { try { handleLogLine(args[0].readUtf8String() || args[0].readAnsiString()); } catch (e) {} } });
    return true;
  } catch (e) { return false; }
}

rpc.exports = {
  ready() { try { resolveEval(); hookLogs(); return true; } catch (e) { return String(e); } },
  // roda JS no cliente (main thread). Use p/ injetar o recon/emissor.
  evalString(code) { return onMain(() => doEval(code)); },
  hookLogAt(addrStr) { return onMain(() => hookLogAt(addrStr)); },
  // lista exports do libcocos2d que casam /log|print|trace/i (p/ achar o canal de log ao vivo)
  logExports() {
    const mod = Process.getModuleByName(COCOS);
    return mod.enumerateExports().filter(e => /log|print|trace|console/i.test(e.name))
      .slice(0, 60).map(e => ({ name: e.name, addr: e.address.toString() }));
  },
};
