// actions.js — protótipo de AÇÃO: organizar as mesas do PPPoker chamando a
// função nativa FloatingWindowFrameManager.TileTableWindows().
//
// SEGURANÇA:
//  - Por padrão roda em DRY-RUN: só resolve a classe/métodos e confirma que
//    existem. NÃO chama nada, NÃO altera a tela.
//  - A chamada real só acontece quando o runner manda a mensagem {type:'tile'}
//    (run_actions.py --tile). Aí ela é feita na MAIN THREAD do Unity (via hook
//    no Update), que é o único lugar seguro p/ mexer na UI — chamar de outra
//    thread crasharia o cliente.
//
// Isso continua sendo injeção (frida.attach). Rodar só em conta teste/play money.

'use strict';
const MOD = 'GameAssembly.dll';
const GAME_IMAGE = 'PP.Production.PPPoker.dll';
const CLASS_NS = '';                      // FloatingWindowFrameManager não tem namespace
const CLASS_NAME = 'FloatingWindowFrameManager';
const TILE_METHOD = 'TileTableWindows';   // 0 args
const TICK_METHOD = 'Update';             // 0 args, roda todo frame na main thread

let _M = null;
function exp(n) { if (!_M) _M = Process.getModuleByName(MOD); return _M.getExportByName(n); }
function nf(n, r, a) { return new NativeFunction(exp(n), r, a); }
function cstr(p) { try { return p.isNull() ? '' : p.readCString(); } catch (e) { return ''; } }

const il2 = {
  domain_get: nf('il2cpp_domain_get', 'pointer', []),
  thread_attach: nf('il2cpp_thread_attach', 'pointer', ['pointer']),
  domain_get_assemblies: nf('il2cpp_domain_get_assemblies', 'pointer', ['pointer', 'pointer']),
  assembly_get_image: nf('il2cpp_assembly_get_image', 'pointer', ['pointer']),
  image_get_name: nf('il2cpp_image_get_name', 'pointer', ['pointer']),
  class_from_name: nf('il2cpp_class_from_name', 'pointer', ['pointer', 'pointer', 'pointer']),
  class_get_method_from_name: nf('il2cpp_class_get_method_from_name', 'pointer', ['pointer', 'pointer', 'int']),
  runtime_invoke: nf('il2cpp_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']),
};

function getImage(name) {
  const domain = il2.domain_get();
  il2.thread_attach(domain);
  const sz = Memory.alloc(Process.pointerSize);
  const arr = il2.domain_get_assemblies(domain, sz);
  const n = sz.readU64().toNumber();
  for (let i = 0; i < n; i++) {
    const asm = arr.add(i * Process.pointerSize).readPointer();
    const img = il2.assembly_get_image(asm);
    if (cstr(il2.image_get_name(img)) === name) return img;
  }
  return NULL;
}

function utf8(s) { return Memory.allocUtf8String(s); }

function resolve() {
  const img = getImage(GAME_IMAGE);
  if (img.isNull()) throw new Error('image ' + GAME_IMAGE + ' nao encontrada');
  const klass = il2.class_from_name(img, utf8(CLASS_NS), utf8(CLASS_NAME));
  if (klass.isNull()) throw new Error('classe ' + CLASS_NAME + ' nao encontrada');
  const mTile = il2.class_get_method_from_name(klass, utf8(TILE_METHOD), 0);
  const mTick = il2.class_get_method_from_name(klass, utf8(TICK_METHOD), 0);
  const mInst = il2.class_get_method_from_name(klass, utf8('get_Instance'), 0);
  return { klass, mTile, mTick, mInst };
}

let pending = false;         // vira true quando o runner pede o tile
let hooked = false;

function armTileOnMainThread(r) {
  if (hooked) return;
  hooked = true;
  const tickPtr = r.mTick.readPointer();   // MethodInfo.methodPointer (offset 0) = código nativo
  console.log('[actions] hook no Update @' + tickPtr + ' instalado (aguardando pedido de tile)');
  Interceptor.attach(tickPtr, {
    onEnter(args) {
      if (!pending) return;
      pending = false;
      try {
        // instância via get_Instance() (estático), na main thread — confiável
        const exc1 = Memory.alloc(Process.pointerSize); exc1.writePointer(NULL);
        const inst = il2.runtime_invoke(r.mInst, NULL, NULL, exc1);
        if (!exc1.readPointer().isNull()) { console.log('[actions] get_Instance lançou exceção'); return; }
        if (inst.isNull()) { console.log('[actions] get_Instance retornou null (modo floating inativo?)'); return; }
        const exc2 = Memory.alloc(Process.pointerSize); exc2.writePointer(NULL);
        il2.runtime_invoke(r.mTile, inst, NULL, exc2);
        const e = exc2.readPointer();
        console.log('[actions] TileTableWindows() chamado via inst=' + inst + (e.isNull() ? ' OK' : ' (exceção!)'));
      } catch (err) {
        console.log('[actions] erro ao chamar tile:', err.message);
      }
    }
  });
}

function main() {
  const r = resolve();
  console.log('[actions] resolvido:');
  console.log('  classe ' + CLASS_NAME + ' @' + r.klass);
  console.log('  ' + TILE_METHOD + '(0) = ' + (r.mTile.isNull() ? 'NAO ACHOU' : r.mTile));
  console.log('  ' + TICK_METHOD + '(0) = ' + (r.mTick.isNull() ? 'NAO ACHOU' : r.mTick));
  console.log('  get_Instance(0) = ' + (r.mInst.isNull() ? 'NAO ACHOU' : r.mInst));
  if (r.mTile.isNull() || r.mTick.isNull() || r.mInst.isNull()) {
    console.log('[actions] faltou método — abortando ação.');
    send('__ACTIONS_READY__');
    return;
  }
  // DRY-RUN não instala hook nenhum. O hook no Update só é instalado quando
  // chega o 1º pedido de tile (sob demanda), p/ a ação rodar na main thread.
  recv('tile', function onTile(msg) {
    console.log('[actions] pedido de tile recebido');
    armTileOnMainThread(r);   // instala o hook sob demanda
    pending = true;
    recv('tile', onTile);     // re-arma p/ próximos pedidos
  });
  send('__ACTIONS_READY__');
}

if (Process.findModuleByName(MOD)) {
  try { main(); } catch (e) { console.log('[actions] erro:', e.stack || e); send('__ACTIONS_READY__'); }
} else {
  const id = setInterval(() => {
    if (Process.findModuleByName(MOD)) { clearInterval(id); try { main(); } catch (e) { console.log('[actions] erro:', e.stack || e); send('__ACTIONS_READY__'); } }
  }, 500);
}
