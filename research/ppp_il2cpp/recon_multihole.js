// recon_multihole.js — RECON READ-ONLY focado nas mensagens de HOLE-CARD multi-mesa.
// Hooka o choke universal OnEnterRoomRSP (passam TODAS as msgs em args[1]) e, quando a classe
// casa /HoleCard|MultipleTable/, dumpa a estrutura recursiva (campos, RepeatedField expandido,
// Pb aninhados) UMA vez por tipo. Objetivo: achar o mapeamento mesa(ref)->cartas do herói p/
// ler as 2 mesas de uma mensagem viva (sem varrer memória). SO LE. Reusa a maquinaria do
// recon_mao_campos.js. Jogue com as 2 mesas ativas p/ disparar o MultipleTableHoleCardRSP.
'use strict';
const MOD = 'GameAssembly.dll', NS = 'PP.PPPoker', CLS = 'AppProtocol';
const HOOK = ['OnEnterRoomRSP'];                 // choke universal
const WANT = /HoleCard|MultipleTable/;           // só dumpa essas
const MAX_DEPTH = 4, MAX_ELEMS = 12;
const seen = {};

function cstr(p) { try { return p.isNull() ? '' : p.readCString(); } catch (e) { return ''; } }
let _M = null; function exp(n) { if (!_M) _M = Process.getModuleByName(MOD); return _M.getExportByName(n); }
function nf(n, r, a) { return new NativeFunction(exp(n), r, a); }

function main() {
  const il = {
    domain_get: nf('il2cpp_domain_get', 'pointer', []),
    thread_attach: nf('il2cpp_thread_attach', 'pointer', ['pointer']),
    domain_get_assemblies: nf('il2cpp_domain_get_assemblies', 'pointer', ['pointer', 'pointer']),
    assembly_get_image: nf('il2cpp_assembly_get_image', 'pointer', ['pointer']),
    image_get_name: nf('il2cpp_image_get_name', 'pointer', ['pointer']),
    class_from_name: nf('il2cpp_class_from_name', 'pointer', ['pointer', 'pointer', 'pointer']),
    class_get_method_from_name: nf('il2cpp_class_get_method_from_name', 'pointer', ['pointer', 'pointer', 'int']),
    class_get_name: nf('il2cpp_class_get_name', 'pointer', ['pointer']),
    object_get_class: nf('il2cpp_object_get_class', 'pointer', ['pointer']),
    class_get_fields: nf('il2cpp_class_get_fields', 'pointer', ['pointer', 'pointer']),
    field_get_name: nf('il2cpp_field_get_name', 'pointer', ['pointer']),
    field_get_offset: nf('il2cpp_field_get_offset', 'uint32', ['pointer']),
  };
  const d = il.domain_get(); il.thread_attach(d);
  const sp = Memory.alloc(Process.pointerSize);
  const arr = il.domain_get_assemblies(d, sp); const cnt = sp.readU64().toNumber();
  let img = ptr(0);
  for (let a = 0; a < cnt; a++) {
    const im = il.assembly_get_image(arr.add(a * Process.pointerSize).readPointer());
    if (cstr(il.image_get_name(im)).toLowerCase().indexOf('pppoker') >= 0) { img = im; break; }
  }
  const klass = il.class_from_name(img, Memory.allocUtf8String(NS), Memory.allocUtf8String(CLS));
  const clsName = (o) => { try { return o.isNull() ? 'null' : cstr(il.class_get_name(il.object_get_class(o))); } catch (e) { return '?'; } };
  const isObjPtr = (p) => { try { return !p.isNull() && p.compare(ptr('0x10000')) > 0; } catch (e) { return false; } };

  function fieldsOf(obj) {
    const k = il.object_get_class(obj);
    const it = Memory.alloc(Process.pointerSize); it.writePointer(ptr(0));
    const out = []; let f;
    while (!(f = il.class_get_fields(k, it)).isNull()) {
      const fn = cstr(il.field_get_name(f));
      if (/FieldNumber$|DefaultValue$|^_parser$|^_unknownFields$|^_hasBits/.test(fn)) continue;
      out.push([fn, il.field_get_offset(f)]);
    }
    return out;
  }
  function dumpRepeated(rf, depth, indent) {
    let count = 0, a = ptr(0);
    try { count = rf.add(24).readS32(); a = rf.add(16).readPointer(); } catch (e) { return indent + '(RepeatedField ilegível)'; }
    if (a.isNull() || count <= 0) return indent + 'count=' + count + ' (vazio)';
    const n = Math.min(count, MAX_ELEMS);
    let asObj = false;
    try { const p0 = a.add(0x20).readPointer(); asObj = isObjPtr(p0) && clsName(p0) !== '?' && clsName(p0) !== 'null'; } catch (e) { }
    const lines = [indent + 'count=' + count + (asObj ? ' [objetos]' : ' [ints]')];
    for (let i = 0; i < n; i++) {
      if (asObj) {
        let el = ptr(0); try { el = a.add(0x20 + i * Process.pointerSize).readPointer(); } catch (e) { }
        if (isObjPtr(el)) lines.push(indent + ' [' + i + '] ' + clsName(el) + dumpObj(el, depth - 1, indent + '    '));
        else lines.push(indent + ' [' + i + '] (nulo)');
      } else {
        let v = 0; try { v = a.add(0x20 + i * 4).readS32(); } catch (e) { }
        lines.push(indent + ' [' + i + '] = ' + v);
      }
    }
    return lines.join('\n');
  }
  function dumpObj(obj, depth, indent) {
    if (!isObjPtr(obj)) return ' = ' + obj;
    const parts = [];
    for (const [fn, off] of fieldsOf(obj)) {
      let line;
      try {
        const p = obj.add(off).readPointer();
        const pc = isObjPtr(p) ? clsName(p) : null;
        if (pc && /RepeatedField/.test(pc)) {
          line = fn + '@' + off + ' (' + pc + '):\n' + dumpRepeated(p, depth, indent + '    ');
        } else if (pc && pc.indexOf('.') < 0 && depth > 0 && pc !== '?' && pc !== 'String') {
          line = fn + '@' + off + ' ->' + pc + ' {' + dumpObj(p, depth - 1, indent + '    ') + '\n' + indent + '}';
        } else if (pc === 'String') {
          line = fn + '@' + off + ' ="' + cstr(p.add(0x14)) + '"';
        } else {
          line = fn + '@' + off + ' = ' + obj.add(off).readS32() + (pc ? (' ->' + pc) : '');
        }
      } catch (e) { line = fn + '@' + off + ' = ?'; }
      parts.push(indent + line);
    }
    return '\n' + parts.join('\n');
  }

  let hooked = 0;
  HOOK.forEach(name => {
    const mi = il.class_get_method_from_name(klass, Memory.allocUtf8String(name), 2);
    if (mi.isNull()) return;
    const addr = mi.readPointer(); if (addr.isNull()) return;
    Interceptor.attach(addr, {
      onEnter(args) {
        try {
          const msg = args[1]; const cn = clsName(msg);
          if (!WANT.test(cn) || seen[cn]) return; seen[cn] = true;
          console.log('\n========== ' + cn + ' ==========' + dumpObj(msg, MAX_DEPTH, '  '));
        } catch (e) { console.log('[recon] erro:', e.stack || e); }
      }
    });
    hooked++;
  });
  console.log('[recon-multihole] ' + hooked + ' choke(s) armado(s) (READ-ONLY). Esperando HoleCard/MultipleTable...');
  console.log('[recon-multihole] Joga as 2 MESAS (p/ disparar o MultipleTableHoleCardRSP).');
}
function go() { try { main(); } catch (e) { console.log('[recon] erro:', e.stack || e); } }
if (Process.findModuleByName(MOD)) { go(); } else { const id = setInterval(() => { if (Process.findModuleByName(MOD)) { clearInterval(id); go(); } }, 500); }
