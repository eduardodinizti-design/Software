/* inject_recon.js — JS do PRÓPRIO jogo (roda no V8 da Suprema via agent.evalString).
   Instala helpers em globalThis.__nvt e faz o recon inicial do fluxo de rede/mão.
   TUDO que sai vai por console.log('[[NVT]]'+json), que o agente encaminha ao Python.
   READ-ONLY: só lê/observa; os hooks são wrappers que CHAMAM o original e observam. */
(function () {
  var TAG = '[[NVT]]';
  var G = (typeof globalThis !== 'undefined') ? globalThis : (typeof window !== 'undefined' ? window : this);

  function emit(o) { try { console.log(TAG + JSON.stringify(o)); } catch (e) { try { console.log(TAG + '{"err":"stringify"}'); } catch (e2) {} } }

  // stringify seguro: corta profundidade, tamanho de array/string e ciclos.
  function safe(v, depth) {
    depth = depth == null ? 2 : depth;
    var seen = [];
    function rec(x, d) {
      if (x === null) return null;
      var t = typeof x;
      if (t === 'number' || t === 'boolean') return x;
      if (t === 'string') return x.length > 200 ? x.slice(0, 200) + '…' : x;
      if (t === 'function') return '<fn ' + (x.name || '') + '>';
      if (t !== 'object') return String(t);
      if (seen.indexOf(x) >= 0) return '<cycle>';
      seen.push(x);
      if (d <= 0) return Array.isArray(x) ? ('<array ' + x.length + '>') : '<obj>';
      if (Array.isArray(x)) { var a = []; for (var i = 0; i < Math.min(x.length, 12); i++) a.push(rec(x[i], d - 1)); if (x.length > 12) a.push('…+' + (x.length - 12)); return a; }
      var o = {}, keys = [];
      try { keys = Object.keys(x); } catch (e) { return '<keys?>'; }
      for (var j = 0; j < Math.min(keys.length, 40); j++) { try { o[keys[j]] = rec(x[keys[j]], d - 1); } catch (e) { o[keys[j]] = '<err>'; } }
      if (keys.length > 40) o['…'] = '+' + (keys.length - 40);
      return o;
    }
    return rec(v, depth);
  }

  function byPath(path) { var o = G, p = path.split('.'); for (var i = 0; i < p.length; i++) { if (o == null) return undefined; o = o[p[i]]; } return o; }

  // mapa raso de nomes->tipo de um objeto (p/ achar onde está o dispatch de mensagens)
  function shape(o) {
    var out = {};
    try { Object.keys(o).forEach(function (k) { var t; try { t = typeof o[k]; } catch (e) { t = '?'; } out[k] = t; }); } catch (e) { return '<no-keys>'; }
    return out;
  }

  var NVT = {
    TAG: TAG,
    emit: emit,
    // dump das chaves/tipos de um caminho global (ex.: "spp", "spp.net")
    dump: function (path, depth) { try { emit({ dump: path, val: safe(byPath(path), depth == null ? 1 : depth) }); } catch (e) { emit({ dump: path, err: String(e) }); } },
    shape: function (path) { try { emit({ shape: path, keys: shape(byPath(path)) }); } catch (e) { emit({ shape: path, err: String(e) }); } },
    // envolve obj[name] p/ observar chamadas (args resumidos). Chama o ORIGINAL (não altera).
    hookfn: function (path, name, label) {
      try {
        var o = byPath(path); if (!o || typeof o[name] !== 'function') { emit({ hookfn: path + '.' + name, ok: false, reason: 'nao-funcao' }); return; }
        if (o['__nvt_' + name]) { emit({ hookfn: path + '.' + name, ok: true, already: true }); return; }
        var orig = o[name]; o['__nvt_' + name] = orig;
        o[name] = function () {
          try { var a = []; for (var i = 0; i < Math.min(arguments.length, 6); i++) a.push(safe(arguments[i], 2)); emit({ call: label || (path + '.' + name), args: a }); } catch (e) {}
          return orig.apply(this, arguments);
        };
        emit({ hookfn: path + '.' + name, ok: true });
      } catch (e) { emit({ hookfn: path + '.' + name, ok: false, err: String(e) }); }
    },
    // procura, em um objeto, propriedades-função cujo nome sugira recebimento de mensagens
    findHandlers: function (path) {
      try {
        var o = byPath(path), hits = [];
        Object.keys(o).forEach(function (k) {
          if (typeof o[k] === 'function' && /on[A-Z]|recv|receive|dispatch|handle|message|msg|packet|proto|notify|push/i.test(k)) hits.push(k);
        });
        emit({ findHandlers: path, hits: hits });
      } catch (e) { emit({ findHandlers: path, err: String(e) }); }
    },
    // envolve WebSocket (se o jogo usa o WS do V8) p/ ver todo tráfego de mensagens
    hookWS: function () {
      try {
        if (typeof WebSocket === 'undefined' || !WebSocket.prototype) { emit({ hookWS: false, reason: 'sem-WebSocket' }); return; }
        if (WebSocket.prototype.__nvt) { emit({ hookWS: true, already: true }); return; }
        WebSocket.prototype.__nvt = true;
        var proto = WebSocket.prototype, origSend = proto.send;
        proto.send = function (d) { try { emit({ ws: 'send', len: (d && d.byteLength) || (d && d.length) || 0, kind: (typeof d) }); } catch (e) {} return origSend.apply(this, arguments); };
        var desc = Object.getOwnPropertyDescriptor(proto, 'onmessage');
        // intercepta via addEventListener também (muitos clientes usam isso)
        var origAdd = proto.addEventListener;
        if (origAdd) proto.addEventListener = function (type, fn, opt) {
          if (type === 'message' && typeof fn === 'function') { var f = fn; fn = function (ev) { try { emit({ ws: 'recv', len: (ev && ev.data && (ev.data.byteLength || ev.data.length)) || 0, kind: (ev && typeof ev.data) }); } catch (e) {} return f.apply(this, arguments); }; }
          return origAdd.call(this, type, fn, opt);
        };
        emit({ hookWS: true });
      } catch (e) { emit({ hookWS: false, err: String(e) }); }
    },
  };
  G.__nvt = NVT;

  // ---- recon inicial automático ----
  emit({ hello: 'nvt-recon', globals: { spp: typeof G.spp, cc: typeof G.cc, game: typeof G.game, WebSocket: typeof G.WebSocket, jsb: typeof G.jsb } });
  if (typeof G.spp !== 'undefined') { NVT.shape('spp'); NVT.findHandlers('spp'); }
  NVT.hookWS();
})();
