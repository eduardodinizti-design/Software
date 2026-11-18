// recon_hands.js — Recon READ-ONLY do IL2CPP do PPPoker: classes de MÃO/CARTA/JOGADOR.
// So LE metadata (nomes de classe/metodo). NAO chama metodo, NAO altera nada.
'use strict';
const MOD = 'GameAssembly.dll';

// classes de interesse p/ a LEITURA DE MAO (dados da partida)
const CLASS_KEYWORDS = [
  'card', 'player', 'seat', 'hand', 'holecard', 'board', 'pot', 'dealer',
  'gameplay', 'gamedata', 'roomdata', 'tabledata', 'tableinfo', 'playerinfo',
  'seatinfo', 'handinfo', 'gameround', 'street', 'betinfo', 'actioninfo',
];
// metodos/campos destacados dentro das classes casadas
const METHOD_HILITE = [
  'card', 'hand', 'player', 'seat', 'pot', 'bet', 'action', 'deal', 'fold',
  'call', 'raise', 'check', 'stack', 'chip', 'hole', 'board', 'name', 'id',
  'win', 'result', 'show', 'nick', 'position', 'blind', 'street', 'round', 'get_',
];
// assemblies do JOGO (ignora Unity/System p/ reduzir ruido)
const ASM_KEYWORDS = ['pppoker', 'pp.production', 'pp.', 'assembly-csharp'];

function cstr(p) { try { return p.isNull() ? '' : p.readCString(); } catch (e) { return ''; } }
let _M = null;
function exp(name) { if (!_M) _M = Process.getModuleByName(MOD); return _M.getExportByName(name); }
function nf(name, ret, args) { return new NativeFunction(exp(name), ret, args); }

function main() {
  const il = {
    domain_get: nf('il2cpp_domain_get', 'pointer', []),
    thread_attach: nf('il2cpp_thread_attach', 'pointer', ['pointer']),
    domain_get_assemblies: nf('il2cpp_domain_get_assemblies', 'pointer', ['pointer', 'pointer']),
    assembly_get_image: nf('il2cpp_assembly_get_image', 'pointer', ['pointer']),
    image_get_name: nf('il2cpp_image_get_name', 'pointer', ['pointer']),
    image_get_class_count: nf('il2cpp_image_get_class_count', 'uint32', ['pointer']),
    image_get_class: nf('il2cpp_image_get_class', 'pointer', ['pointer', 'uint32']),
    class_get_name: nf('il2cpp_class_get_name', 'pointer', ['pointer']),
    class_get_namespace: nf('il2cpp_class_get_namespace', 'pointer', ['pointer']),
    class_get_methods: nf('il2cpp_class_get_methods', 'pointer', ['pointer', 'pointer']),
    method_get_name: nf('il2cpp_method_get_name', 'pointer', ['pointer']),
    method_get_param_count: nf('il2cpp_method_get_param_count', 'uint32', ['pointer']),
  };
  const domain = il.domain_get();
  il.thread_attach(domain);
  const sizePtr = Memory.alloc(Process.pointerSize);
  const asmArray = il.domain_get_assemblies(domain, sizePtr);
  const asmCount = sizePtr.readU64().toNumber();
  const kw = (s, list) => { s = (s || '').toLowerCase(); return list.some(k => s.indexOf(k) >= 0); };
  let matched = 0, scanned = 0;
  for (let a = 0; a < asmCount; a++) {
    const asm = asmArray.add(a * Process.pointerSize).readPointer();
    const img = il.assembly_get_image(asm);
    const imgName = cstr(il.image_get_name(img));
    if (!kw(imgName, ASM_KEYWORDS)) continue;           // so a assembly do jogo
    const n = il.image_get_class_count(img);
    for (let i = 0; i < n; i++) {
      const klass = il.image_get_class(img, i);
      if (klass.isNull()) continue;
      scanned++;
      const cname = cstr(il.class_get_name(klass));
      if (!cname || !kw(cname, CLASS_KEYWORDS)) continue;
      const ns = cstr(il.class_get_namespace(klass));
      matched++;
      console.log('\n== ' + (ns ? ns + '.' : '') + cname + '   [' + imgName + ']');
      const iter = Memory.alloc(Process.pointerSize); iter.writePointer(ptr(0));
      let m, cnt = 0;
      while (!(m = il.class_get_methods(klass, iter)).isNull() && cnt < 60) {
        const mname = cstr(il.method_get_name(m));
        const star = kw(mname, METHOD_HILITE) ? ' *' : '';
        console.log('   ' + mname + '(' + il.method_get_param_count(m) + ')' + star);
        cnt++;
      }
    }
  }
  console.log('\n[recon-hands] varridas:', scanned, '| casadas:', matched);
}

function go() { try { main(); } catch (e) { console.log('[recon-hands] erro:', e.stack || e); } send('__RECON_DONE__'); }
if (Process.findModuleByName(MOD)) { go(); }
else { const id = setInterval(() => { if (Process.findModuleByName(MOD)) { clearInterval(id); go(); } }, 500); }
