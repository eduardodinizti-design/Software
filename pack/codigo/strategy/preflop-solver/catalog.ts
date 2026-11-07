/**
 * Catálogo do motor pré-flop do solver (branch `solver-data`, `preflop/catalog`), importado por
 * `scripts/import-preflop-solver.mjs` para `public/solver/preflop/`.
 *
 * O motor resolve a mesa inteira (RFI, respostas com call/3bet/all-in, multiway, vs 3bet, blind war) com o
 * pós-flop modelado por curvas de realização medidas nos solves de flop. Cada situação é uma mesa de 9 com
 * stacks fixos: chip_25, chip_40, pkochip_25 (PKO early), pkomid_25 (PKO mid) e, com ICM (e bounty no PKO),
 * {preitm, bubble, ft} × {iguais, curtos_ini, curtos_fim}.
 *
 * O motor de decisão do trainer é síncrono: os arquivos são carregados antes da sessão (`preloadPreflopSolverFor`)
 * e consultados aqui. Sem o arquivo carregado, `presetFor` devolve null e o spot cai na fonte anterior.
 */
import { ALL_HANDS, type HandKey } from "@/domain/cards";
import type { Position } from "@/domain/positions";
import type { StackBucket, TrainingScenario } from "@/domain/scenario";
import type { TournamentStage } from "@/domain/tournament";
import { relevantBountyPower } from "@/domain/pko";
import { HRC_LIMP } from "./hrc-limp";

export const PREFLOP_SOLVER_BASE = "/solver/preflop";
/** Ranges tirados do HRC (solver de referência), no mesmo formato: `scripts/import-hrc.py` → public/solver/hrc. */
export const HRC_BASE = "/solver/hrc";
import { fixPairOrder, type PairFix } from "./pair-order";
import { EV_MIX_TOL_BB, EV_MIX_TOL_PCT } from "../tolerances";
import { smoothIslands, type IslandFix, type SmoothActs } from "./island-smooth";
export const isHrcPreset = (name: string) => name.startsWith("hrc_");
/** Limp da SB abaixo disto é ruído do equilíbrio: a mão não chega ao spot "SB vs iso" (mesmo corte do MIN_FREQ do provider). */
export const MIN_LIMP_FREQ = 0.05;
export const POS9: Position[] = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];

type Arr = number[];
export interface RfiNode { raise: Arr; shove: Arr; ev: { fold: Arr; raise: Arr; shove: Arr } }
export interface RespNode { call: Arr; three: Arr; shove: Arr; ev: { fold: Arr; call: Arr; three: Arr; shove: Arr }; resumo: Record<string, number> | null }
/** ev: EV absoluto por mão (só nos ranges do HRC; o catálogo do time não traz). */
export interface Opv3Node { call: Arr; shove: Arr; ev?: { fold: Arr; call: Arr; shove: Arr } }
/** Uma ação de um nó da Blind War com limp: frequência e EV por mão (EV absoluto do HRC; o fold é a base). */
export interface LimpAct { freq: Arr; ev: Arr }
/**
 * Blind War com limp (só nos ranges do HRC): todos foldam até a SB.
 * sb: fold / call (= limp) / raise (open de `raiseSize` bb) / allin; bbVsLimp: check / raise (iso para `isoSize` bb) / allin;
 * sbVsIso: fold / call / allin; sbVsJam: fold / call (o BB foi all-in por cima do limp).
 */
export interface LimpData { sb: Record<string, LimpAct>; raiseSize: number | null; bbVsLimp: Record<string, LimpAct>; isoSize: number | null; sbVsIso?: Record<string, LimpAct>; sbVsJam?: Record<string, LimpAct> }
export interface PreflopPreset {
  format: number; name: string; note: string; stacks: number[]; unit: "bb" | "pct"; iterations: number | null; version: string;
  hands: HandKey[]; rfi: Record<string, RfiNode>; resp: Record<string, RespNode>; opv3: Record<string, Opv3Node>;
  limp?: LimpData;
  /** índice de cada mão do trainer (ALL_HANDS) no array do arquivo. */
  idx: number[];
  /** Pares corrigidos para a ordem natural (só arquivos do HRC; ver pair-order.ts). */
  pairFixes?: PairFix[];
  /** Mãos que destoavam das vizinhas por ruído (EV dentro da margem) e passaram a jogar como elas (island-smooth.ts). */
  islandFixes?: IslandFix[];
  /** Mãos que destoam das vizinhas mas o EV do HRC confirma (não mexidas; auditoria). */
  islandConfident?: IslandFix[];
}
export interface PreflopManifest { format: number; generatedAt: string; source?: { commit?: string | null }; presets: { name: string; file: string; note: string; unit: string; stacks: number[]; version: string }[] }

export function parsePreflopPreset(raw: unknown): PreflopPreset {
  const d = raw as Omit<PreflopPreset, "idx"> | null;
  if (!d || d.format !== 1 || !Array.isArray(d.hands) || d.hands.length !== 169 || !d.resp || !d.opv3 || !d.rfi || d.stacks?.length !== 9) throw new Error("Catálogo pré-flop inválido");
  const pos = new Map(d.hands.map((h, i) => [h, i]));
  const idx = ALL_HANDS.map((h) => { const i = pos.get(h); if (i === undefined) throw new Error(`Catálogo pré-flop sem a mão ${h}`); return i; });
  // Arquivos do HRC: pares na ordem natural (ruído do Monte Carlo em nós de pouco alcance; ver pair-order.ts).
  const p = { ...structuredClone(d), idx };
  const pairFixes = isHrcPreset(p.name) ? fixPairOrder(p, p.unit === "pct" ? EV_MIX_TOL_PCT : EV_MIX_TOL_BB) : [];
  const isl = isHrcPreset(p.name) ? smoothPreset(p) : { fixes: [], confident: [] };
  return { ...p, pairFixes, islandFixes: isl.fixes, islandConfident: isl.confident };
}

/** Margem da régua de validação: até aqui a diferença de EV é ruído do solver (0,05bb / 0,02% do prize pool). */
export const ISLAND_MARGIN = { bb: 0.05, pct: 0.02 } as const;
const minus = (a: Arr, b: Arr) => a.map((x, i) => x - (b[i] ?? 0));
const restOf = (...fs: Arr[]) => fs[0]!.map((_, i) => Math.max(0, 1 - fs.reduce((a, f) => a + (f[i] ?? 0), 0)));
/** Suaviza as mãos que destoam das vizinhas em todos os nós de um arquivo do HRC (in place nas frequências). */
function smoothPreset(p: Pick<PreflopPreset, "hands" | "unit" | "rfi" | "resp" | "opv3" | "limp">): { fixes: IslandFix[]; confident: IslandFix[] } {
  const margin = ISLAND_MARGIN[p.unit];
  const fixes: IslandFix[] = [], confident: IslandFix[] = [];
  const run = (name: string, acts: SmoothActs) => { const r = smoothIslands(name, p.hands, acts, margin); fixes.push(...r.fixes); confident.push(...r.confident); };
  const zero = p.hands.map(() => 0);
  // SB fora do open: o resto do open da SB é limp (Blind War, nó próprio abaixo).
  for (const [k, n] of Object.entries(p.rfi)) if (k !== "SB") run(`open ${k}`, { raise: { freq: n.raise, ev: minus(n.ev.raise, n.ev.fold) }, shove: { freq: n.shove, ev: minus(n.ev.shove, n.ev.fold) }, fold: { freq: restOf(n.raise, n.shove), ev: zero } });
  for (const [k, n] of Object.entries(p.resp)) run(`vs open ${k}`, { call: { freq: n.call, ev: minus(n.ev.call, n.ev.fold) }, three: { freq: n.three, ev: minus(n.ev.three, n.ev.fold) }, shove: { freq: n.shove, ev: minus(n.ev.shove, n.ev.fold) }, fold: { freq: restOf(n.call, n.three, n.shove), ev: zero } });
  for (const [k, n] of Object.entries(p.opv3)) if (n.ev) run(`vs 3bet ${k}`, { call: { freq: n.call, ev: minus(n.ev.call, n.ev.fold) }, shove: { freq: n.shove, ev: minus(n.ev.shove, n.ev.fold) }, fold: { freq: restOf(n.call, n.shove), ev: zero } });
  if (p.limp) smoothLimp(p.limp, p.hands, margin, run);
  return { fixes, confident };
}
/** Nós da Blind War: SB first-in (base fold), BB contra o limp (base check), SB contra o iso (base fold). */
function smoothLimp(L: Pick<LimpData, "sb" | "bbVsLimp" | "sbVsIso">, hands: readonly string[], margin: number, run: (name: string, acts: SmoothActs) => void) {
  const node = (name: string, n: Record<string, LimpAct> | undefined, base: string) => {
    if (!n || !n[base]) return;
    const b = n[base]!.ev;
    run(name, Object.fromEntries(Object.entries(n).map(([k, v]) => [k, { freq: v.freq, ev: minus(v.ev, b) }])));
  };
  void hands; void margin;
  node("Blind War SB", L.sb, "fold");
  node("BB vs limp", L.bbVsLimp, L.bbVsLimp["check"] ? "check" : "call");
  node("SB vs iso", L.sbVsIso, "fold");
}

const presets = new Map<string, PreflopPreset>();
const loading = new Map<string, Promise<PreflopPreset | null>>();
export const getPreset = (name: string) => presets.get(name) ?? null;
export function setPreset(p: PreflopPreset) { presets.set(p.name, p); }
export function clearPreflopCatalog() { presets.clear(); loading.clear(); hrcManifestP = null; }

type FetchJson = (path: string) => Promise<unknown>;
const browserFetch: FetchJson = async (path) => { const r = await fetch(path, { cache: "no-cache" }); if (!r.ok) throw new Error(`${path}: ${r.status}`); return r.json(); };
let manifestP: Promise<PreflopManifest | null> | null = null;
export function loadPreflopManifest(fetchJson: FetchJson = browserFetch) {
  manifestP ??= fetchJson(`${PREFLOP_SOLVER_BASE}/manifest.json`).then((m) => m as PreflopManifest).catch(() => { manifestP = null; return null; });
  return manifestP;
}
let hrcManifestP: Promise<PreflopManifest | null> | null = null;
export function loadHrcManifest(fetchJson: FetchJson = browserFetch) {
  hrcManifestP ??= fetchJson(`${HRC_BASE}/manifest.json`).then((m) => m as PreflopManifest).catch(() => { hrcManifestP = null; return null; });
  return hrcManifestP;
}
/** Carrega uma situação (uma vez por versão). Falha silenciosa: o spot usa a fonte anterior. */
export async function loadPreset(name: string, fetchJson: FetchJson = browserFetch): Promise<PreflopPreset | null> {
  const hrc = isHrcPreset(name);
  const BASE = hrc ? HRC_BASE : PREFLOP_SOLVER_BASE;
  const m = await (hrc ? loadHrcManifest(fetchJson) : loadPreflopManifest(fetchJson));
  const e = m?.presets.find((p) => p.name === name);
  if (!e) return null;
  const cur = presets.get(name);
  if (cur && cur.version === e.version) return cur;
  const key = `${name}@${e.version}`;
  let p = loading.get(key);
  if (!p) {
    p = fetchJson(`${BASE}/${e.file}?v=${encodeURIComponent(e.version)}`).then((raw) => { const x = parsePreflopPreset(raw); presets.set(name, x); return x; }).catch(() => { loading.delete(key); return null; });
    loading.set(key, p);
  }
  return p;
}

// ---------------------------------------------------------------------------------------------
// Qual situação do catálogo corresponde ao cenário.

const PHASE: Partial<Record<TournamentStage, string>> = { pre_itm: "preitm", bubble: "bubble", ft: "ft" };
const SPREADS: Record<string, number[]> = {
  iguais: [25, 25, 25, 25, 25, 25, 25, 25, 25],
  curtos_fim: [35, 35, 30, 30, 25, 20, 15, 15, 20],
  curtos_ini: [15, 15, 20, 20, 25, 30, 35, 35, 30],
};

/** Situações candidatas para um contexto (antes de olhar os stacks da mesa). */
export function presetNamesFor(ctx: { mode?: string; format: string; stage: TournamentStage; stack: StackBucket | number }): string[] {
  const mode = ctx.mode ?? "chip_ev";
  // chip_15 só existe como ranges do HRC (3bet = all-in, como no resto do trainer a 15bb).
  if (mode === "chip_ev" && ctx.format === "regular" && (ctx.stack === 25 || ctx.stack === 40 || ctx.stack === 15) && !PHASE[ctx.stage]) return [`chip_${ctx.stack}`];
  // 8/10/12bb: só a Blind War (HRC heads-up SB vs BB com limp; o resto da mesa segue com o push/fold Nash).
  if (mode === "chip_ev" && ctx.format === "regular" && (ctx.stack === 8 || ctx.stack === 10 || ctx.stack === 12) && !PHASE[ctx.stage]) return [`chip_${ctx.stack}`];
  // PKO chip EV: desligado até o solver entregar as situações por bounty power. As duas atuais não passam na
  // auditoria (docs/auditoria-solver-2026-10-25.md): pkochip_25 avalia o bounty pela convenção antiga (0,5; BP efetivo
  // ≈ 2,4 na tabela do time) e abre 95% em todas as posições; pkomid_25 não convergiu (16% das ações jogadas perdem EV).
  // PKO no começo/meio (30/10): ranges do HRC, Multi Table ICM + Bounty Mode PKO (torneio de 200, 30 pagos; começo
  // 180 restantes, meio 100), só os arquivos do HRC (hrc_pkoearly_25 / hrc_pkomid_25): presetFor nunca cai nas
  // situações antigas do catálogo do time com o mesmo nome.
  if ((mode === "pko" || (mode === "chip_ev" && ctx.format === "pko")) && ctx.stack === 25 && !PHASE[ctx.stage]) return [ctx.stage === "early" ? "pkoearly_25" : "pkomid_25"];
  if (PKO_CHIP_PRESETS_ENABLED && (mode === "pko" || (mode === "chip_ev" && ctx.format === "pko")) && ctx.stack === 25 && !PHASE[ctx.stage]) return ctx.stage === "early" ? ["pkochip_25", "pkomid_25"] : ["pkomid_25", "pkochip_25"];
  if ((mode === "icm" || mode === "pko_icm") && ctx.stack === 25 && PHASE[ctx.stage]) {
    const fmt = mode === "pko_icm" ? "pko" : "icm";
    return Object.keys(SPREADS).map((s) => `${PHASE[ctx.stage]}_${s}_${fmt}`);
  }
  return [];
}

/** Distribuição de stacks do catálogo mais parecida com a mesa (por posição, normalizada pela média). */
export function nearestSpread(s: Pick<TrainingScenario, "table">): string {
  const seats = s.table.players.map((p) => ({ i: POS9.indexOf(p.position), st: p.stackBb })).filter((x) => x.i >= 0);
  const mean = seats.reduce((a, x) => a + x.st, 0) / Math.max(1, seats.length);
  let best = "iguais", bestD = Infinity;
  for (const [k, v] of Object.entries(SPREADS)) {
    const m = seats.reduce((a, x) => a + v[x.i]!, 0) / Math.max(1, seats.length);
    const dist = seats.reduce((a, x) => a + (x.st / mean - v[x.i]! / m) ** 2, 0);
    if (dist < bestD - 1e-9) { bestD = dist; best = k; }
  }
  return best;
}

/** Situações PKO chip EV do catálogo em uso (desligadas: ver presetNamesFor). */
export const PKO_CHIP_PRESETS_ENABLED = false;
/**
 * Bounty power equivalente das duas situações PKO chip EV na convenção do trainer (0,27 stack inicial por bounty
 * inicial). O motor usou 0,5: cabeça/stack 1,3 e 0,58 equivalem a BP ≈ 2,4 e ≈ 1,07 na tabela do time.
 */
export const PKO_PRESET_BP = { pkochip_25: 2.4, pkomid_25: 1.07 } as const;

/** Nome da situação do catálogo para o cenário (ou null). Só usa contexto e stacks da mesa: serve também ao gerador. */
export function presetNameFor(s: Pick<TrainingScenario, "context" | "table" | "spot">): string | null {
  const names = presetNamesFor(s.context);
  if (!names.length) return null;
  if (names.length === 1) return names[0]!;
  if (names[0]!.startsWith("pko")) {
    const bp = relevantBountyPower(s as TrainingScenario);
    const want = bp === null ? names[0]! : Math.abs(bp - PKO_PRESET_BP.pkochip_25) <= Math.abs(bp - PKO_PRESET_BP.pkomid_25) ? "pkochip_25" : "pkomid_25";
    return getPreset(want) || getPreset(`hrc_${want}`) ? want : names.find((n) => n !== want)!;
  }
  const spread = nearestSpread(s);
  return names.find((n) => n.includes(`_${spread}_`)) ?? names[0]!;
}

/** Situação carregada para o cenário (ou null: o spot fica com a fonte anterior). Ranges do HRC (referência) primeiro. */
export function presetFor(s: TrainingScenario): PreflopPreset | null {
  const name = presetNameFor(s);
  if (!name) return null;
  // PKO começo/meio: só o arquivo do HRC (o pkomid_25 antigo do catálogo do time não convergiu).
  return getPreset(`hrc_${name}`) ?? (HRC_ONLY.has(name) ? null : getPreset(name));
}
const HRC_ONLY = new Set(["pkoearly_25", "pkomid_25"]);

/**
 * Situação do HRC com a Blind War com limp para o cenário (tabela síncrona `HRC_LIMP`, sem depender do arquivo
 * carregado), no formato de situação do catálogo (só o ramo `limp`). Null quando o HRC não tem a situação.
 */
export function limpPresetFor(s: Pick<TrainingScenario, "context" | "table" | "spot">): PreflopPreset | null {
  const base = presetNameFor(s);
  const name = base ? `hrc_${base}` : null;
  const L = name ? HRC_LIMP[name] : undefined;
  if (!name || !L) return null;
  const cached = limpCache.get(name);
  if (cached) return cached;
  // Cópia (HRC_LIMP também serve ao gerador, que sorteia as mãos pelo limp cru) com as mãos destoantes suavizadas.
  const limp = structuredClone({ sb: L.sb, raiseSize: L.raiseSize, bbVsLimp: L.bbVsLimp, isoSize: L.isoSize, sbVsIso: L.sbVsIso });
  const p: PreflopPreset = { format: 1, name, note: "", stacks: [], unit: L.unit, iterations: null, version: L.version, hands: [...ALL_HANDS], rfi: {}, resp: {}, opv3: {},
    idx: ALL_HANDS.map((_, i) => i), limp };
  const isl = smoothPreset(p);
  p.islandFixes = isl.fixes; p.islandConfident = isl.confident;
  limpCache.set(name, p);
  return p;
}
const limpCache = new Map<string, PreflopPreset>();

/**
 * Open da SB (todos foldaram até ela) com o limp entre as opções: sempre que o HRC tem a Blind War com limp da
 * situação, o open raise e o open shove da SB viram fold / limp / raise / all-in. Sem isso o trainer jogava a fatia
 * que o HRC limpa no raise ou no shove (a melhor ação que sobrava), e o spot ficava fácil demais.
 */
export function sbLimpOption(s: Pick<TrainingScenario, "context" | "table" | "spot">): boolean {
  return s.spot.heroPosition === "SB" && (s.spot.type === "open_raise" || s.spot.type === "open_shove") && !!limpPresetFor(s);
}

/** Pré-carrega as situações que uma sessão pode usar (formatos × fases × stacks dos filtros). */
export async function preloadPreflopSolverFor(f: { formats: string[]; stages: TournamentStage[]; stacks: number[]; strategyContext?: string | null }, fetchJson?: FetchJson) {
  const names = new Set<string>();
  for (const format of f.formats) for (const stage of f.stages) for (const stack of f.stacks) {
    const icm = !!PHASE[stage];
    const mode = icm ? (format === "pko" ? "pko_icm" : "icm") : format === "pko" ? "pko" : "chip_ev";
    for (const n of presetNamesFor({ mode, format, stage, stack })) names.add(n);
  }
  await Promise.all([...names].flatMap((n) => [loadPreset(n, fetchJson), loadPreset(`hrc_${n}`, fetchJson)]));
  return [...names].flatMap((n) => [n, `hrc_${n}`]).filter((n) => presets.has(n));
}

/** Pré-carrega as situações das famílias do solver já validadas (trava de validação: a Home precisa delas para saber o que está disponível). */
export async function preloadValidatedSolverPresets(isValidated: (family: string) => boolean, family: (preset: string) => string, fetchJson?: FetchJson) {
  const [m, h] = await Promise.all([loadPreflopManifest(fetchJson), loadHrcManifest(fetchJson)]);
  const names = [...(m?.presets ?? []), ...(h?.presets ?? [])].map((p) => p.name).filter((n) => isValidated(family(n)));
  await Promise.all(names.map((n) => loadPreset(n, fetchJson)));
  return names;
}

/** Valor de um nó para a mão do trainer. */
export const at = (p: PreflopPreset, a: Arr, hand: HandKey) => a[p.idx[ALL_HANDS.indexOf(hand)]!] ?? 0;
export const toRecord = (p: PreflopPreset, a: Arr): Record<HandKey, number> => Object.fromEntries(ALL_HANDS.map((h, i) => [h, a[p.idx[i]!] ?? 0]));

const SPREAD_PT: Record<string, string> = { iguais: "stacks iguais (25bb)", curtos_ini: "stacks curtos nas primeiras posições", curtos_fim: "stacks curtos nas posições finais" };
const PHASE_PT: Record<string, string> = { preitm: "pré-ITM (7 pagos de 9)", bubble: "bolha (8 pagos de 9)", ft: "mesa final" };
/** Descrição curta da situação de referência ("bolha (8 pagos de 9), stacks iguais, com bounty"). */
export function describePreset(name: string): string {
  if (isHrcPreset(name)) return `ranges do HRC, ${describePreset(name.slice(4))}`;
  if (/^chip_(8|10|12)$/.test(name)) return `chip EV, Blind War SB vs BB com ${name.split("_")[1]}bb`;
  if (name.startsWith("chip_")) return `chip EV, todos com ${name.split("_")[1]}bb`;
  if (name === "pkochip_25") return "PKO, cabeça de 1,3 stack (BP ≈ 2,4 na convenção do trainer), todos com 25bb";
  if (name === "pkomid_25") return "PKO no meio do torneio (Multi Table ICM + bounty, 100 de 200 restantes), todos com 25bb";
  if (name === "pkoearly_25") return "PKO no começo do torneio (Multi Table ICM + bounty, 180 de 200 restantes), todos com 25bb";
  const [ph, ...rest] = name.split("_"); const fmt = rest.pop(); const sp = rest.join("_");
  return `${PHASE_PT[ph!] ?? ph}, ${SPREAD_PT[sp] ?? sp}${fmt === "pko" ? ", com bounty (PKO + ICM)" : ", ICM"}`;
}
