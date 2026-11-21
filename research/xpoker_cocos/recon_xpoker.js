// recon_xpoker.js — RECON READ-ONLY do X-Poker (Cocos2d-x / GLFW, externo).
// Identifica a ENGINE de script (JS/jsb ou Lua) e ACHA a entrada p/ rodar script
// (o análogo do se::ScriptEngine::evalString da Suprema) — exportada ou não.
// So LE: enumera módulos, exports e strings reveladores. Manda tudo via send().
'use strict';

function listModules() {
  return Process.enumerateModules().map(m => ({ name: m.name, base: m.base.toString(), size: m.size }));
}

// exports de qualquer módulo cujo nome casa /cocos|js|lua|script|spidermonkey|v8/i,
// filtrando símbolos reveladores (ScriptEngine/eval/execute/js/lua/log).
function scriptExports() {
  const out = [];
  const reMod = /cocos|jsb|js_|libjs|lua|script|spidermonkey|mozjs|v8/i;
  const reSym = /ScriptEngine|evalString|executeString|executeScript|eval|runScript|jsb|lua_|luaL_|log|console/i;
  Process.enumerateModules().forEach(m => {
    if (!reMod.test(m.name)) return;
    let exps = [];
    try { exps = m.enumerateExports(); } catch (e) { return; }
    exps.forEach(e => { if (reSym.test(e.name)) out.push({ mod: m.name, name: e.name, addr: e.address.toString() }); });
  });
  return out.slice(0, 200);
}

// pistas sobre qual engine: presença de módulos/símbolos típicos
function engineHints() {
  const mods = Process.enumerateModules().map(m => m.name.toLowerCase());
  return {
    hasCocos: mods.some(n => n.indexOf('cocos') >= 0),
    hasLua: mods.some(n => n.indexOf('lua') >= 0),
    jsEngine: mods.some(n => /spidermonkey|mozjs|v8|libjs/.test(n)),
    modsSample: mods.filter(n => /cocos|lua|js|v8|glfw|game|poker/.test(n)).slice(0, 30),
  };
}

rpc.exports = {
  modules() { return listModules(); },
  scriptExports() { return scriptExports(); },
  engineHints() { return engineHints(); },
  // dumpa exports de um módulo específico que casem um regex (p/ cavar fino ao vivo)
  exportsOf(modName, pattern) {
    const re = new RegExp(pattern || '.', 'i');
    try { return Process.getModuleByName(modName).enumerateExports().filter(e => re.test(e.name)).slice(0, 300).map(e => ({ name: e.name, addr: e.address.toString() })); }
    catch (e) { return String(e); }
  },
};

send({ recon: 'xpoker-ready', hints: engineHints() });
