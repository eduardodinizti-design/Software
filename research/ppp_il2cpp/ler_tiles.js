// ler_tiles.js — lê, por MESA, o RETÂNGULO do tile na tela (via TableUIPanel._roomId +
// RectTransform.GetWorldCorners). READ-ONLY. RPC: readTiles() -> [{roomid, rect:[x0,y0,x1,y1]}]
// em coords de TELA do Unity (origem embaixo-à-esquerda do client da janela). O Python soma
// o offset do client da janela e inverte o Y.
'use strict';
const MOD = 'GameAssembly.dll';
function cstr(p){try{return p.isNull()?'':p.readCString();}catch(e){return '';}}
let _M=null; function exp(n){if(!_M)_M=Process.getModuleByName(MOD);return _M.getExportByName(n);}
function nf(n,r,a){return new NativeFunction(exp(n),r,a);}

let il=null, imgs=null;
function boot(){
  if(il) return;
  il={
    domain_get:nf('il2cpp_domain_get','pointer',[]), thread_attach:nf('il2cpp_thread_attach','pointer',['pointer']),
    domain_get_assemblies:nf('il2cpp_domain_get_assemblies','pointer',['pointer','pointer']),
    assembly_get_image:nf('il2cpp_assembly_get_image','pointer',['pointer']), image_get_name:nf('il2cpp_image_get_name','pointer',['pointer']),
    class_from_name:nf('il2cpp_class_from_name','pointer',['pointer','pointer','pointer']),
    class_get_method_from_name:nf('il2cpp_class_get_method_from_name','pointer',['pointer','pointer','int']),
    class_get_name:nf('il2cpp_class_get_name','pointer',['pointer']),
    image_get_class_count:nf('il2cpp_image_get_class_count','uint32',['pointer']),
    image_get_class:nf('il2cpp_image_get_class','pointer',['pointer','uint32']),
    class_get_fields:nf('il2cpp_class_get_fields','pointer',['pointer','pointer']),
    field_get_name:nf('il2cpp_field_get_name','pointer',['pointer']), field_get_offset:nf('il2cpp_field_get_offset','uint32',['pointer']),
    field_get_type:nf('il2cpp_field_get_type','pointer',['pointer']), type_get_name2:nf('il2cpp_type_get_name','pointer',['pointer']),
    class_get_type:nf('il2cpp_class_get_type','pointer',['pointer']), type_get_object:nf('il2cpp_type_get_object','pointer',['pointer']),
    array_new:nf('il2cpp_array_new','pointer',['pointer','uint64']),
  };
  const d=il.domain_get(); il.thread_attach(d);
  const sp=Memory.alloc(Process.pointerSize); const arr=il.domain_get_assemblies(d,sp); const cnt=sp.readU64().toNumber();
  imgs={};
  for(let a=0;a<cnt;a++){ const im=il.assembly_get_image(arr.add(a*Process.pointerSize).readPointer()); imgs[cstr(il.image_get_name(im)).toLowerCase()]=im; }
}
function img(name){ const n=name.toLowerCase(); return imgs[n] || imgs[n+'.dll'] || null; }
function klass(imgName, ns, name){ const im=img(imgName); if(!im)return ptr(0);
  try{ return il.class_from_name(im, Memory.allocUtf8String(ns), Memory.allocUtf8String(name)); }catch(e){ return ptr(0); } }
function method(k, name, argc){ if(!k||k.isNull())return ptr(0);
  try{ return il.class_get_method_from_name(k, Memory.allocUtf8String(name), argc); }catch(e){ return ptr(0); } }
// acha a classe pelo NOME varrendo a imagem (independe do namespace)
function classByName(imgName, name){ const im=img(imgName); if(!im)return ptr(0);
  let n=0; try{ n=il.image_get_class_count(im); }catch(e){ return ptr(0); }
  for(let i=0;i<n;i++){ let c; try{ c=il.image_get_class(im,i); }catch(e){ continue; }
    if(c.isNull())continue; if(cstr(il.class_get_name(c))===name) return c; } return ptr(0); }
// chama método il2cpp: addr=mi.readPointer() (methodPointer@0); convenção (this?, args..., MethodInfo*)
function callI(mi, ret, argtypes, thisptr, args){ const addr=mi.readPointer();
  const f=new NativeFunction(addr, ret, ['pointer'].concat(argtypes).concat(['pointer']));
  return f.apply(null, [thisptr].concat(args).concat([mi])); }
function callS(mi, ret, argtypes, args){ const addr=mi.readPointer();
  const f=new NativeFunction(addr, ret, argtypes.concat(['pointer']));
  return f.apply(null, args.concat([mi])); }

let C=null;
function classes(){
  if(C) return C;
  C={
    panel: classByName('PP.Production.PPPoker','TableUIPanel'),
    obj: klass('UnityEngine.CoreModule','UnityEngine','Object'),
    comp: klass('UnityEngine.CoreModule','UnityEngine','Component'),
    rect: klass('UnityEngine.CoreModule','UnityEngine','RectTransform'),
    vec3: klass('UnityEngine.CoreModule','UnityEngine','Vector3'),
    screen: klass('UnityEngine.CoreModule','UnityEngine','Screen'),
    tr: klass('UnityEngine.CoreModule','UnityEngine','Transform'),
    rtu: klass('UnityEngine.UI','UnityEngine','RectTransformUtility'),
    cam: klass('UnityEngine.CoreModule','UnityEngine','Camera'),
    go: klass('UnityEngine.CoreModule','UnityEngine','GameObject'),
  };
  // fallbacks de namespace
  if(C.panel.isNull()) C.panel = klass('PP.Production.PPPoker','','TableUIPanel');
  C.m={
    find: method(C.obj,'FindObjectsOfType',1) ,
    getTransform: method(C.comp,'get_transform',0),
    getCorners: method(C.rect,'GetWorldCorners',1),
    screenH: method(C.screen,'get_height',0),
    screenW: method(C.screen,'get_width',0),
    getPos: method(C.tr,'get_position',0),
    camPixelRect: method(C.cam,'get_pixelRect',0),
    camName: method(C.go,'get_name',0),
    camGo: method(C.comp,'get_gameObject',0),
    camDepth: method(C.cam,'get_depth',0),
  };
  if(C.m.find.isNull()){ const fb=method(C.obj,'FindObjectsOfTypeAll',1); if(!fb.isNull())C.m.find=fb; }
  return C;
}

function readTiles(){
  boot(); const c=classes();
  const out=[];
  if(c.panel.isNull()||c.m.find.isNull()) return {err:'panel/find nao resolvido', have:{panel:!c.panel.isNull(), find:!c.m.find.isNull()}};
  const typeObj = il.type_get_object(il.class_get_type(c.panel));
  const arrp = callS(c.m.find,'pointer',['pointer'],[typeObj]);     // Object[]
  if(arrp.isNull()) return {tiles:out, n:0};
  const len = arrp.add(0x18).readS32();
  const sh = c.m.screenH.isNull()? 0 : callS(c.m.screenH,'int',[],[]);
  for(let i=0;i<Math.min(len,16);i++){
    try{
      const panel = arrp.add(0x20 + i*Process.pointerSize).readPointer(); if(panel.isNull())continue;
      const roomid = panel.add(120).readS32();
      let rect=null;
      if(!c.m.getTransform.isNull() && !c.m.getCorners.isNull()){
        const tr = callI(c.m.getTransform,'pointer',[],panel,[]);   // Transform (=RectTransform p/ UI)
        if(!tr.isNull()){
          const varr = il.array_new(c.vec3, 4);
          callI(c.m.getCorners,'void',['pointer'],tr,[varr]);
          const base = varr.add(0x20); const pts=[];
          for(let k=0;k<4;k++){ const b=base.add(k*12); pts.push([b.readFloat(), b.add(4).readFloat()]); }
          const xs=pts.map(p=>p[0]), ys=pts.map(p=>p[1]);
          rect=[Math.min.apply(null,xs), Math.min.apply(null,ys), Math.max.apply(null,xs), Math.max.apply(null,ys)];
        }
      }
      out.push({roomid:roomid, rect:rect});
    }catch(e){ out.push({err:String(e)}); }
  }
  return {tiles:out, n:len, screenH:sh};
}

function instancesOf(name){ const c=classes(); const k=classByName('PP.Production.PPPoker',name); if(k.isNull())return [];
  try{ const t=il.type_get_object(il.class_get_type(k)); const arr=callS(c.m.find,'pointer',['pointer'],[t]); if(arr.isNull())return [];
    const n=arr.add(0x18).readS32(); const out=[]; for(let i=0;i<Math.min(n,16);i++){ const p=arr.add(0x20+i*Process.pointerSize).readPointer(); if(!p.isNull())out.push(p); } return out; }catch(e){ return []; } }
// retângulo [x0,y0,x1,y1] (coords Unity) de um RectTransform via GetWorldCorners
function cornersOf(rt){ const c=classes(); if(!rt||rt.isNull())return null;
  try{ const varr=il.array_new(c.vec3,4); callI(c.m.getCorners,'void',['pointer'],rt,[varr]);
    const base=varr.add(0x20),xs=[],ys=[]; for(let k=0;k<4;k++){ const b=base.add(k*12); xs.push(b.readFloat()); ys.push(b.add(4).readFloat()); }
    return [Math.min.apply(null,xs),Math.min.apply(null,ys),Math.max.apply(null,xs),Math.max.apply(null,ys)]; }catch(e){ return null; } }
// Vector3 get_position via convenção sret (x64): f(retPtr, this, MethodInfo)
function posOf(tr){ const c=classes(); if(!tr||tr.isNull()||c.m.getPos.isNull())return null;
  try{ const addr=c.m.getPos.readPointer(); const f=new NativeFunction(addr,'void',['pointer','pointer','pointer']);
    const ret=Memory.alloc(12); f(ret, tr, c.m.getPos); return [ret.readFloat(), ret.add(4).readFloat()]; }catch(e){ return null; } }
// dump de TODOS os campos de uma classe (nome@offset:tipo)
function dumpFields(name){ const k=classByName('PP.Production.PPPoker',name); if(k.isNull())return [];
  const it=Memory.alloc(Process.pointerSize); it.writePointer(ptr(0)); const out=[]; let f;
  try{ while(!(f=il.class_get_fields(k,it)).isNull()){ const fn=cstr(il.field_get_name(f)); const off=il.field_get_offset(f);
    let tn=''; try{ tn=cstr(il.type_get_name2(il.field_get_type(f))); }catch(e){} out.push(fn+'@'+off+':'+tn); } }catch(e){}
  return out; }
// lê os tiles pela RAIZ da MultiTablePage (get_transform) + campos + botões
let _dumped=false;
function readLayout(){ boot(); const c=classes(); const pages=[],buttons=[];
  const dump = _dumped?null:{MultiTablePage:dumpFields('MultiTablePage'), GameLayerBase:dumpFields('GameLayerBase'),
    HoldemGameLayer:dumpFields('HoldemGameLayer'), MttGameLayer:dumpFields('MttGameLayer')}; _dumped=true;
  instancesOf('MultiTablePage').forEach(p=>{ try{ const root=callI(c.m.getTransform,'pointer',[],p,[]);
    let roomid=0; try{ const ti=p.add(120).readPointer(); if(!ti.isNull())roomid=ti.add(16).readS32(); }catch(e){}
    pages.push({roomid:roomid, rootpos:posOf(root), framepos:posOf(p.add(168).readPointer())}); }catch(e){} });
  instancesOf('TableDealerButton').forEach(b=>{ try{ const roomid=b.add(120).readS32(); const tr=callI(c.m.getTransform,'pointer',[],b,[]);
    buttons.push({roomid:roomid, rootpos:posOf(tr), corners:cornersOf(tr)}); }catch(e){} });
  return {pages:pages, buttons:buttons, dump:dump, cams:readCameras(),
    screenH:c.m.screenH.isNull()?0:callS(c.m.screenH,'int',[],[]),
    screenW:c.m.screenW.isNull()?0:callS(c.m.screenW,'int',[],[])}; }

function instancesOfClass(k){ if(!k||k.isNull())return []; const c=classes();
  try{ const t=il.type_get_object(il.class_get_type(k)); const arr=callS(c.m.find,'pointer',['pointer'],[t]); if(arr.isNull())return [];
    const n=arr.add(0x18).readS32(); const out=[]; for(let i=0;i<Math.min(n,40);i++){ const p=arr.add(0x20+i*Process.pointerSize).readPointer(); if(!p.isNull())out.push(p);} return out; }catch(e){ return []; } }
function il2str(s){ try{ if(!s||s.isNull())return ''; const len=s.add(0x10).readS32(); if(len<=0||len>120)return ''; return s.add(0x14).readUtf16String(len); }catch(e){ return ''; } }
// Rect (x,y,w,h) do viewport da câmera na tela, via get_pixelRect (sret 16 bytes)
function pixelRectOf(cam){ const c=classes(); if(c.m.camPixelRect.isNull())return null;
  try{ const addr=c.m.camPixelRect.readPointer(); const f=new NativeFunction(addr,'void',['pointer','pointer','pointer']);
    const ret=Memory.alloc(16); f(ret,cam,c.m.camPixelRect); return [ret.readFloat(),ret.add(4).readFloat(),ret.add(8).readFloat(),ret.add(12).readFloat()]; }catch(e){ return null; } }
function camName(cam){ const c=classes(); try{ const go=callI(c.m.camGo,'pointer',[],cam,[]); if(go.isNull())return '';
  const nm=callI(c.m.camName,'pointer',[],go,[]); return il2str(nm); }catch(e){ return ''; } }
function readCameras(){ boot(); const c=classes(); const out=[];
  instancesOfClass(c.cam).forEach(cam=>{ try{ let depth=0; if(!c.m.camDepth.isNull())depth=callI(c.m.camDepth,'float',[],cam,[]);
    out.push({name:camName(cam), rect:pixelRectOf(cam), depth:depth}); }catch(e){} }); return out; }

let _last = 0;
function armHook(){
  boot();
  const app = klass('PP.Production.PPPoker','PP.PPPoker','AppProtocol');
  let hooked = 0;
  ['OnActionBRC','OnRoundStartBRC','OnSeatStatusBRC','OnWinnerRSP'].forEach(n=>{
    const mi = method(app, n, 2); if(mi.isNull()) return;
    const addr = mi.readPointer(); if(addr.isNull()) return;
    Interceptor.attach(addr, { onEnter(){ const now=Date.now(); if(now-_last<1500) return; _last=now;
      try{ send(readLayout()); }catch(e){ send({err:String(e)}); } } });
    hooked++;
  });
  console.log('[tiles] hooks main-thread armados: '+hooked+' (jogue p/ disparar)');
}
function go(){ try{ armHook(); }catch(e){ console.log('[tiles] erro:', e.stack||e); } }
if(Process.findModuleByName(MOD)){ go(); } else { const id=setInterval(()=>{ if(Process.findModuleByName(MOD)){ clearInterval(id); go(); } },500); }
