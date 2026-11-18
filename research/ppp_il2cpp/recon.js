// recon.js — Reconhecimento READ-ONLY do IL2CPP do PPPoker via Frida.
//
// O QUE FAZ: resolve as classes/métodos internos do cliente (MultiWindowManager,
// FloatingWindowController, MultiTableViewForPC, ApplyTile, CreateTableWindow, etc.)
// e imprime nome + nº de parâmetros + endereço de cada método relevante.
//
// O QUE **NÃO** FAZ: não chama nenhum método, não altera estado, não cria/move
// janela, não hooka nada. É só leitura de metadata em runtime. Seguro p/ observar.
//
// Uso (ver run_recon.py): frida -n PPPoker.exe -l recon.js  (ou via o runner Python)

'use strict';

const MOD = 'GameAssembly.dll';

// nomes de classe que nos interessam p/ o ORGANIZADOR (case-insensitive, substring)
const CLASS_KEYWORDS = [
  'window', 'floating', 'multitable', 'multiwindow', 'transparentwindow',
  'tile', 'tiling', 'layout', 'arrange', 'tablewindow', 'tableview',
  'desktop', 'frame'
];
// dentro das classes casadas, destacamos métodos com estes termos
const METHOD_HILITE = [
  'tile', 'arrange', 'layout', 'create', 'destroy', 'close', 'open',
  'show', 'hide', 'move', 'set', 'pos', 'size', 'maximize', 'window',
  'front', 'detach', 'dock', 'float', 'start', 'enable', 'apply'
];

function cstr(p) { try { return p.isNull() ? '' : p.readCString(); } catch (e) { return ''; } }
let _M = null;
function exp(name) { if (!_M) _M = Process.getModuleByName(MOD); return _M.getExportByName(name); }
function nf(name, ret, args) { return new NativeFunction(exp(name), ret, args); }

function main() {
  const il2cpp = {
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

  const domain = il2cpp.domain_get();
  il2cpp.thread_attach(domain);

  const sizePtr = Memory.alloc(Process.pointerSize);
  const asmArray = il2cpp.domain_get_assemblies(domain, sizePtr);
  const asmCount = sizePtr.readU64().toNumber();
  console.log('[recon] assemblies:', asmCount);

  const kw = (s, list) => { s = s.toLowerCase(); return list.some(k => s.indexOf(k) >= 0); };
  let matched = 0, scanned = 0;

  for (let a = 0; a < asmCount; a++) {
    const asm = asmArray.add(a * Process.pointerSize).readPointer();
    const img = il2cpp.assembly_get_image(asm);
    const imgName = cstr(il2cpp.image_get_name(img));
    const n = il2cpp.image_get_class_count(img);
    for (let i = 0; i < n; i++) {
      const klass = il2cpp.image_get_class(img, i);
      if (klass.isNull()) continue;
      scanned++;
      const cname = cstr(il2cpp.class_get_name(klass));
      if (!cname || !kw(cname, CLASS_KEYWORDS)) continue;
      const ns = cstr(il2cpp.class_get_namespace(klass));
      matched++;
      console.log('\n== ' + (ns ? ns + '.' : '') + cname + '   [' + imgName + ']');
      // iterar métodos
      const iter = Memory.alloc(Process.pointerSize);
      iter.writePointer(ptr(0));
      let m;
      while (!(m = il2cpp.class_get_methods(klass, iter)).isNull()) {
        const mname = cstr(il2cpp.method_get_name(m));
        const pc = il2cpp.method_get_param_count(m);
        const star = kw(mname, METHOD_HILITE) ? ' *' : '';
        console.log('   ' + mname + '(' + pc + ')  @' + m + star);
      }
    }
  }
  console.log('\n[recon] classes varridas:', scanned, '| classes casadas:', matched);
  console.log('[recon] FIM (nenhum método foi chamado; nada foi alterado).');
}

// GameAssembly já está carregado quando o jogo roda; se não, espera.
function go() {
  try { main(); } catch (e) { console.log('[recon] erro:', e.stack || e); }
  send('__RECON_DONE__');
}
if (Process.findModuleByName(MOD)) {
  go();
} else {
  console.log('[recon] aguardando', MOD, '...');
  const id = setInterval(() => {
    if (Process.findModuleByName(MOD)) { clearInterval(id); go(); }
  }, 500);
}
