/**
 * Drill "3Bet: escolha o size" (pré-flop): alguém abriu 2bb e o herói escolhe fold, call, 3bet pequena,
 * 3bet grande ou all-in.
 *
 * Fonte: motor pré-flop NVT (branch `solver-data`, `trainer-export/preflop-3bet/`, pedido
 * `solver-requests/2026-10-21-sizes-de-3bet.md`), convertido por `scripts/import-3bet-solver.mjs` para
 * `public/solver/3bet/`. Nada aqui inventa estratégia:
 * - correção pelo EV de cada ação (relativo ao fold) que o próprio motor calculou; EV perdido = max(EV) − EV(escolha);
 * - perda abaixo de EV_MIX_TOL_BB (bb) / EV_MIX_TOL_PCT (% do prize pool) conta como mista aceita (mesma regra do trainer);
 * - frequências e a resposta do opener só aparecem como informação.
 * É um drill separado (histórico próprio), não um `TrainingScenario`: não entra no decision log nem no replay.
 */
import { ALL_HANDS, SUITS, combos, rankValue, type Card, type HandKey } from "@/domain/cards";
import type { Position } from "@/domain/positions";
import type { Rng } from "@/domain/rng";
import { EV_MIX_TOL_BB, EV_MIX_TOL_PCT } from "@/strategy/engine";

export const THREEBET_DATA_FORMAT = 1;
export const THREEBET_DATA_BASE = "/solver/3bet";
/** Frequência mínima para o motor "jogar" a mão (mesmo corte do solver pré-flop no trainer). */
export const PLAY_MIN_FREQ = 0.05;

export const ACTIONS = ["fold", "call", "s1", "s2", "allin"] as const;
export type ThreeBetAction = (typeof ACTIONS)[number];
export type Unit = "bb" | "pct";

/** [f_fold, f_call, f_s1, f_s2, f_allin, ev_fold, ev_call, ev_s1, ev_s2, ev_allin]; EV null = ação fora da árvore. */
export type HandRow = (number | null)[];
export interface ThreeBetContext {
  unit: Unit;
  version: string | null;
  stacks: { hero: number | null; opener: number | null; table: number[] | null };
  open_bb: number;
  sizes: { s1: number; s2: number };
  opener_response: Partial<Record<"s1" | "s2", { fold?: number; call?: number; allin?: number }>> | null;
  summary: Partial<Record<"freq_s1" | "freq_s2" | "perda_media_so_s1" | "perda_media_so_s2" | "perda_por_mao_3bet_so_s1" | "perda_por_mao_3bet_so_s2", number>> | null;
  note: string | null;
  iterations: number | null;
  rows: HandRow[];
}
export interface ThreeBetSpotData { format: number; spot: string; hero: string; opener: string; stack: number; version: string; hands: HandKey[]; contexts: Record<string, ThreeBetContext>; idx: number[] }
export interface ThreeBetManifestSpot { spot: string; hero: string; opener: string; stack: number; file: string; version: string; contexts: string[] }
export interface ThreeBetManifest { format: number; generatedAt: string; source?: { commit?: string | null }; spots: ThreeBetManifestSpot[] }

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export function parseThreeBetSpot(raw: unknown): ThreeBetSpotData {
  const d = raw as Omit<ThreeBetSpotData, "idx"> | null;
  const fail = (m: string): never => { throw new Error(`Dados de 3bet inválidos: ${m}`); };
  if (!d || typeof d !== "object") fail("não é um objeto");
  if (d!.format !== THREEBET_DATA_FORMAT) fail(`formato ${String(d!.format)}; rode scripts/import-3bet-solver.mjs`);
  if (!Array.isArray(d!.hands) || d!.hands.length !== 169) fail("mãos");
  const pos = new Map(d!.hands.map((h, i) => [h, i]));
  const idx = ALL_HANDS.map((h) => pos.get(h) ?? fail(`sem a mão ${h}`));
  if (!d!.contexts || !Object.keys(d!.contexts).length) fail("sem contextos");
  for (const [k, c] of Object.entries(d!.contexts)) {
    if (c.unit !== "bb" && c.unit !== "pct") fail(`${k}: unidade`);
    if (!isNum(c.sizes?.s1) || !isNum(c.sizes?.s2)) fail(`${k}: sizes`);
    if (!Array.isArray(c.rows) || c.rows.length !== 169 || c.rows.some((r) => !Array.isArray(r) || r.length !== 10 || !isNum(r[0]) || r[5] !== 0)) fail(`${k}: linhas`);
  }
  return { ...d!, idx };
}
export function parseThreeBetManifest(raw: unknown): ThreeBetManifest {
  const m = raw as Partial<ThreeBetManifest> | null;
  if (!m || m.format !== THREEBET_DATA_FORMAT || !Array.isArray(m.spots) || !m.spots.length) throw new Error("Manifest de 3bet inválido");
  return m as ThreeBetManifest;
}

type FetchJson = (path: string) => Promise<unknown>;
const browserFetch: FetchJson = async (path) => {
  const r = await fetch(path, { cache: "no-cache" });
  if (!r.ok) throw new Error(`Não foi possível carregar ${path} (${r.status})`);
  return r.json();
};
let manifestP: Promise<ThreeBetManifest> | null = null;
const spotCache = new Map<string, Promise<ThreeBetSpotData>>();
export function loadThreeBetManifest(fetchJson: FetchJson = browserFetch): Promise<ThreeBetManifest> {
  manifestP ??= fetchJson(`${THREEBET_DATA_BASE}/manifest.json`).then(parseThreeBetManifest).catch((e) => { manifestP = null; throw e; });
  return manifestP;
}
/** Dados de um spot (cache por versão: dados novos nunca se misturam com antigos). */
export function loadThreeBetSpot(e: ThreeBetManifestSpot, fetchJson: FetchJson = browserFetch): Promise<ThreeBetSpotData> {
  const key = `${e.file}@${e.version}`;
  let p = spotCache.get(key);
  if (!p) {
    p = fetchJson(`${THREEBET_DATA_BASE}/${e.file}?v=${encodeURIComponent(e.version)}`).then(parseThreeBetSpot).catch((err) => { spotCache.delete(key); throw err; });
    spotCache.set(key, p);
  }
  return p;
}
export function clearThreeBetCache() { manifestP = null; spotCache.clear(); }

// ---------------------------------------------------------------------------------------------
// Contextos e posições.

const POS: Record<string, Position> = { utg: "UTG", lj: "LJ", hj: "HJ", co: "CO", btn: "BTN", sb: "SB", bb: "BB" };
export const positionOf = (code: string): Position => POS[code] ?? (code.toUpperCase() as Position);
export const heroPos = (s: { hero: string }) => positionOf(s.hero);
export const openerPos = (s: { opener: string }) => positionOf(s.opener);

export type ContextMode = "chip" | "icm" | "pko";
export type Phase = "preitm" | "bolha" | "ft";
export type StackCase = "iguais" | "curtos_ini" | "curtos_fim" | "cobrindo" | "coberto";
export interface ContextInfo { mode: ContextMode; phase: Phase | null; stacks: StackCase | null }
export function parseContext(name: string): ContextInfo {
  if (name === "chip") return { mode: "chip", phase: null, stacks: null };
  const m = name.match(/^(preitm|bolha|ft)_(iguais|curtos_ini|curtos_fim|cobrindo|coberto)_(icm|pko)$/);
  if (!m) return { mode: "chip", phase: null, stacks: null };
  return { mode: m[3] as ContextMode, phase: m[1] as Phase, stacks: m[2] as StackCase };
}
export const PHASE_PT: Record<Phase, string> = { preitm: "pré-ITM (7 pagos de 9)", bolha: "bolha (8 pagos de 9)", ft: "mesa final (9 pagos)" };
export const STACKS_PT: Record<StackCase, string> = { iguais: "stacks iguais", curtos_ini: "curtos nas primeiras posições", curtos_fim: "curtos nas posições finais", cobrindo: "você cobre o opener", coberto: "o opener cobre você" };
export function describeContext(name: string): string {
  const c = parseContext(name);
  if (c.mode === "chip") return "chip EV";
  return `${c.mode === "pko" ? "PKO + ICM" : "ICM"}, ${PHASE_PT[c.phase!]}, ${STACKS_PT[c.stacks!]}`;
}

export interface ThreeBetFilter { spots: string[]; stacks: number[]; mode: ContextMode; phases: Phase[]; stackCases: StackCase[] }
/** Pares (spot, contexto) do manifest que passam pelo filtro. Lista vazia em um campo = todos. */
export function matchingContexts(m: ThreeBetManifest, f: ThreeBetFilter): { spot: ThreeBetManifestSpot; context: string }[] {
  const out: { spot: ThreeBetManifestSpot; context: string }[] = [];
  for (const s of m.spots) {
    if (f.spots.length && !f.spots.includes(`${s.hero}_vs_${s.opener}`)) continue;
    if (f.stacks.length && !f.stacks.includes(s.stack)) continue;
    for (const c of s.contexts) {
      const ci = parseContext(c);
      if (ci.mode !== f.mode) continue;
      if (ci.phase && f.phases.length && !f.phases.includes(ci.phase)) continue;
      if (ci.stacks && f.stackCases.length && !f.stackCases.includes(ci.stacks)) continue;
      out.push({ spot: s, context: c });
    }
  }
  return out;
}

// ---------------------------------------------------------------------------------------------
// Leitura de uma mão.

export const rowOf = (d: ThreeBetSpotData, ctx: string, hand: HandKey): HandRow => d.contexts[ctx]!.rows[d.idx[ALL_HANDS.indexOf(hand)]!]!;
/** Ações que existem na árvore do contexto (EV não nulo). */
export const legalActions = (d: ThreeBetSpotData, ctx: string): ThreeBetAction[] => ACTIONS.filter((_, i) => d.contexts[ctx]!.rows.some((r) => r[5 + i] !== null));
/** Soma das frequências de call, 3bets e all-in (o resto é fold). */
export const playFreq = (r: HandRow) => (r[1] ?? 0) + (r[2] ?? 0) + (r[3] ?? 0) + (r[4] ?? 0);
const bestNonFoldEv = (r: HandRow) => Math.max(...[r[6], r[7], r[8], r[9]].filter(isNum));

export type HandFocus = "all" | "played";
/**
 * Mãos sorteáveis: todas (por combos) ou "mãos que jogam" — as que o motor não folda 100% (≥ PLAY_MIN_FREQ) mais as
 * folds mais próximas de jogar (as de maior EV fora do fold), em número igual a 1/4 das que jogam. É só uma regra
 * de sorteio; a correção é sempre pelo EV do motor.
 */
export function handPool(d: ThreeBetSpotData, ctx: string, focus: HandFocus): HandKey[] {
  if (focus === "all") return ALL_HANDS;
  const played = ALL_HANDS.filter((h) => playFreq(rowOf(d, ctx, h)) >= PLAY_MIN_FREQ);
  const folds = ALL_HANDS.filter((h) => !played.includes(h)).sort((a, b) => bestNonFoldEv(rowOf(d, ctx, b)) - bestNonFoldEv(rowOf(d, ctx, a)));
  const pool = [...played, ...folds.slice(0, Math.ceil(played.length / 4))];
  return pool.length ? pool : ALL_HANDS;
}

export interface ThreeBetHand { id: string; spot: string; context: string; hand: HandKey; cards: [Card, Card] }
/** Cartas concretas para uma mão (naipes aleatórios). */
export function cardsFor(hand: HandKey, rng: Rng): [Card, Card] {
  const s1 = SUITS[rng.int(4)]!;
  let s2: string = s1;
  if (hand.length === 2 || hand.endsWith("o")) { const others = SUITS.filter((x) => x !== s1); s2 = others[rng.int(others.length)]!; }
  const a = `${hand[0]}${s1}`, b = `${hand[1]}${s2}`;
  return rankValue(a[0]) >= rankValue(b[0]) ? [a, b] : [b, a];
}
export function dealThreeBetHand(d: ThreeBetSpotData, ctx: string, rng: Rng, focus: HandFocus = "all"): ThreeBetHand {
  const pool = handPool(d, ctx, focus);
  let x = rng.next() * pool.reduce((a, h) => a + combos(h), 0);
  let hand = pool[pool.length - 1]!;
  for (const h of pool) { x -= combos(h); if (x <= 0) { hand = h; break; } }
  const cards = cardsFor(hand, rng);
  return { id: `${d.spot}|${ctx}|${hand}|${cards.join("")}`, spot: d.spot, context: ctx, hand, cards };
}

// ---------------------------------------------------------------------------------------------
// Correção.

export type ThreeBetGrade = "best" | "mixed" | "error";
export interface ThreeBetOption { action: ThreeBetAction; ev: number; freq: number; loss: number }
export interface ThreeBetResult { choice: ThreeBetAction; best: ThreeBetAction; grade: ThreeBetGrade; loss: number; unit: Unit; tolerance: number; options: ThreeBetOption[] }
export const mixTolerance = (u: Unit) => (u === "pct" ? EV_MIX_TOL_PCT : EV_MIX_TOL_BB);

export function gradeThreeBet(d: ThreeBetSpotData, ctx: string, hand: HandKey, choice: ThreeBetAction): ThreeBetResult {
  const c = d.contexts[ctx];
  if (!c) throw new Error(`Contexto ${ctx} não existe em ${d.spot}`);
  const r = rowOf(d, ctx, hand);
  const raw = ACTIONS.map((a, i) => ({ action: a, freq: r[i] ?? 0, ev: r[5 + i] })).filter((o): o is { action: ThreeBetAction; freq: number; ev: number } => isNum(o.ev));
  const max = Math.max(...raw.map((o) => o.ev));
  const options = raw.map((o) => ({ ...o, loss: Math.max(0, max - o.ev) }));
  const chosen = options.find((o) => o.action === choice);
  if (!chosen) throw new Error(`Ação ${choice} fora da árvore de ${d.spot} (${ctx})`);
  const best = options.reduce((a, o) => (o.ev > a.ev ? o : a)).action;
  const tolerance = mixTolerance(c.unit);
  const grade: ThreeBetGrade = choice === best ? "best" : chosen.loss < tolerance ? "mixed" : "error";
  return { choice, best, grade, loss: chosen.loss, unit: c.unit, tolerance, options };
}

// ---------------------------------------------------------------------------------------------
// Textos.

export const fmt = (v: number, d = 2) => `${v < 0 ? "−" : ""}${Math.abs(v).toFixed(d).replace(".", ",")}`;
export const unitLabel = (u: Unit) => (u === "pct" ? "% do prize pool" : "bb");
export const evText = (v: number, u: Unit) => (u === "pct" ? `${fmt(v, 3)}%` : `${fmt(v)}bb`);
export function actionLabel(a: ThreeBetAction, c?: ThreeBetContext): string {
  if (a === "fold") return "Fold";
  if (a === "call") return "Call";
  if (a === "allin") return "All-in";
  const amt = c ? ` ${fmt(c.sizes[a], 1)}bb` : "";
  return `3Bet ${a === "s1" ? "pequena" : "grande"}${amt}`;
}
/** Total que o herói coloca com a ação (bb, contando o que já postou). */
export function actionAmount(a: ThreeBetAction, c: ThreeBetContext, heroStack: number): number {
  if (a === "fold") return 0;
  if (a === "call") return c.open_bb;
  if (a === "allin") return heroStack;
  return c.sizes[a];
}

/** Custo de jogar o spot com um size só (resumo do motor; o opener se adapta). */
export function oneSizeCost(c: ThreeBetContext): { s1: number | null; s2: number | null } {
  const s = c.summary ?? {};
  return { s1: isNum(s.perda_por_mao_3bet_so_s1) ? s.perda_por_mao_3bet_so_s1 : null, s2: isNum(s.perda_por_mao_3bet_so_s2) ? s.perda_por_mao_3bet_so_s2 : null };
}

// ---------------------------------------------------------------------------------------------
// Série e histórico (separado do decision log do trainer).

export interface ThreeBetRecord { at: number; spot: string; context: string; version: string; hand: HandKey; choice: ThreeBetAction; best: ThreeBetAction; grade: ThreeBetGrade; loss: number; unit: Unit; ms: number }
export interface ThreeBetSummary { hands: number; best: number; mixed: number; errors: number; lossBbPer100: number | null; lossPctPer100: number | null; byAction: { action: ThreeBetAction; errors: number }[] }
export function summarizeThreeBet(rows: ThreeBetRecord[]): ThreeBetSummary {
  const per100 = (u: Unit) => { const xs = rows.filter((r) => r.unit === u); return xs.length ? (xs.reduce((a, r) => a + r.loss, 0) / xs.length) * 100 : null; };
  const byBest = new Map<ThreeBetAction, number>();
  for (const r of rows) if (r.grade === "error") byBest.set(r.best, (byBest.get(r.best) ?? 0) + 1);
  return {
    hands: rows.length,
    best: rows.filter((r) => r.grade === "best").length,
    mixed: rows.filter((r) => r.grade === "mixed").length,
    errors: rows.filter((r) => r.grade === "error").length,
    lossBbPer100: per100("bb"),
    lossPctPer100: per100("pct"),
    byAction: [...byBest.entries()].map(([action, errors]) => ({ action, errors })).sort((a, b) => b.errors - a.errors),
  };
}
const HISTORY_KEY = "nvt-3bet-history-v1";
const HISTORY_MAX = 2000;
export function loadThreeBetHistory(): ThreeBetRecord[] {
  try { const raw = typeof localStorage === "undefined" ? null : localStorage.getItem(HISTORY_KEY); const v = raw ? JSON.parse(raw) : []; return Array.isArray(v) ? v : []; } catch { return []; }
}
export function appendThreeBetHistory(rows: ThreeBetRecord[]) {
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify([...loadThreeBetHistory(), ...rows].slice(-HISTORY_MAX))); } catch { /* ignore */ }
}
