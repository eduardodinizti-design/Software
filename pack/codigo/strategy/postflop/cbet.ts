/**
 * Drill de c-bet no flop (pote de raise simples, agressor em posição contra o BB).
 *
 * Fonte: solver pós-flop (branch `solver-data`, `trainer-export/`), convertido por
 * `scripts/import-cbet-solver.mjs` para `public/solver/cbet/`. Nada aqui inventa estratégia:
 * - correção pela árvore simplificada do próprio solver (check + o size do board), EV em bb;
 * - EV perdido = max(EV check, EV bet) − EV(ação escolhida); perda < MIX_TOLERANCE_BB conta como mista aceita;
 * - a estratégia completa (check/33/65/100) e a resposta do BB só aparecem como informação.
 * Os dados v1 são provisórios (defesa do BB = ranges do trainer). Trocar os arquivos e o manifest basta.
 * Exports sem a árvore simplificada (ex.: v2 com a defesa do BB calculada) trazem `size: null` e só a
 * árvore completa; nesses spots o drill oferece apenas check/33/65/pote.
 */
import type { Card } from "@/domain/cards";
import { rankValue } from "@/domain/cards";
import type { Rng } from "@/domain/rng";

export const CBET_DATA_FORMAT = 1;
export const CBET_DATA_BASE = "/solver/cbet";
/** Perda abaixo disso (bb) é tratada como ação mista: o solver é indiferente na precisão usada (0,5%). */
export const MIX_TOLERANCE_BB = 0.02;
/** Foco "decisões que custam": diferença de EV entre check e bet a partir disso. */
export const COSTLY_DECISION_BB = 0.05;

export type CbetSize = "b33" | "b65" | "b100";
export type CbetChoice = "check" | "bet";

export type CbetTreeName = "simple" | "full";
export interface CbetManifestSpot { spot: string; label: string; file: string; version: string; note?: string | null; pot_bb: number; stack_bb: number; aggressor: string; flops: number; trees?: CbetTreeName[] }
export interface CbetManifest { format: number; generatedAt: string; version: string; note: string; spots: CbetManifestSpot[]; source?: { branch: string; commit: string | null } }

/**
 * [s_check, s_bet, ev_check, ev_bet, (f_check, f_b33, f_b65, f_b100, e_check, e_b33, e_b65, e_b100)?]
 * Em spots só com árvore completa o arquivo traz 8 números (f_*, e_*); o parser antepõe 4 NaN para manter
 * os índices da árvore completa (4..11). Os 4 primeiros só são lidos quando `flop.size` existe.
 */
export type CbetComboRow = number[];
export interface CbetFlop {
  flop: string;
  stratum: string;
  weight: number;
  equity_agg: number;
  actions: string[];
  freq: number[];
  /** Size da árvore simplificada (check + 1 size); null quando o export não traz essa árvore. */
  size: CbetSize | null;
  loss_bb: number | null;
  agg: Record<string, CbetComboRow>;
  def: Record<string, { actions: string[]; freq: number[] }>;
}
export interface CbetSpotData { format: number; spot: string; label: string; pot_bb: number; stack_bb: number; aggressor: string; version: string; note: string; flops: CbetFlop[]; open_bb?: number }

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const CARD_RE = /^[AKQJT2-9][shdc]$/;
const splitCards = (s: string): Card[] => (s.match(/.{2}/g) ?? []) as Card[];

/** Valida os dados de um spot. Campos extras são ignorados (versões futuras podem acrescentar). */
export function parseCbetSpot(raw: unknown): CbetSpotData {
  const d = raw as Partial<CbetSpotData> | null;
  const fail = (m: string): never => { throw new Error(`Dados de c-bet inválidos: ${m}`); };
  if (!d || typeof d !== "object") fail("não é um objeto");
  if (d!.format !== CBET_DATA_FORMAT) fail(`formato ${String(d!.format)} (esperado ${CBET_DATA_FORMAT}); rode scripts/import-cbet-solver.mjs`);
  if (typeof d!.spot !== "string" || typeof d!.version !== "string") fail("sem spot/version");
  if (!isNum(d!.pot_bb) || !isNum(d!.stack_bb)) fail("pot/stack");
  if (!Array.isArray(d!.flops) || !d!.flops.length) fail("sem flops");
  for (const f of d!.flops!) {
    const cards = splitCards(f.flop);
    if (cards.length !== 3 || !cards.every((c) => CARD_RE.test(c))) fail(`flop ${f.flop}`);
    const simple = f.size !== null;
    if (simple && !["b33", "b65", "b100"].includes(f.size as string)) fail(`${f.flop}: size ${String(f.size)}`);
    if (!Array.isArray(f.actions) || !Array.isArray(f.freq)) fail(`${f.flop}: sem ações`);
    if (!f.agg || !Object.keys(f.agg).length) fail(`${f.flop}: sem combos`);
    for (const [c, row] of Object.entries(f.agg)) {
      if (!/^([AKQJT2-9][shdc]){2}$/.test(c) || !Array.isArray(row)) fail(`${f.flop}: combo ${c}`);
      if (simple) { if (row.length < 4 || !row.slice(0, 4).every(isNum)) fail(`${f.flop}: combo ${c}`); }
      else {
        // Só árvore completa: 8 números (f_*, e_*) → mesmos índices do formato de 12.
        // (idempotente: um objeto já normalizado, com 12 posições, passa de novo sem mudar).
        const fullPart = row.length === 12 ? row.slice(4) : row;
        if (fullPart.length !== 8 || !fullPart.every(isNum)) fail(`${f.flop}: combo ${c} (árvore completa)`);
        f.agg[c] = [NaN, NaN, NaN, NaN, ...fullPart];
      }
    }
    f.loss_bb ??= null;
    if (!isNum(f.weight) || !isNum(f.equity_agg)) fail(`${f.flop}: weight/equity`);
    f.def ??= {};
  }
  return d as CbetSpotData;
}

export function parseCbetManifest(raw: unknown): CbetManifest {
  const m = raw as Partial<CbetManifest> | null;
  if (!m || m.format !== CBET_DATA_FORMAT || !Array.isArray(m.spots) || !m.spots.length) throw new Error("Manifest de c-bet inválido");
  return m as CbetManifest;
}

type FetchJson = (path: string) => Promise<unknown>;
const browserFetch: FetchJson = async (path) => {
  const r = await fetch(path, { cache: "no-cache" });
  if (!r.ok) throw new Error(`Não foi possível carregar ${path} (${r.status})`);
  return r.json();
};
let manifestPromise: Promise<CbetManifest> | null = null;
const spotCache = new Map<string, Promise<CbetSpotData>>();

/** Manifest (sempre revalidado: é ele que diz qual versão dos dados está publicada). */
export function loadCbetManifest(fetchJson: FetchJson = browserFetch): Promise<CbetManifest> {
  manifestPromise ??= fetchJson(`${CBET_DATA_BASE}/manifest.json`).then(parseCbetManifest).catch((e) => { manifestPromise = null; throw e; });
  return manifestPromise;
}
/** Dados de um spot; o cache é por versão, então dados novos nunca se misturam com antigos. */
export function loadCbetSpot(entry: CbetManifestSpot, fetchJson: FetchJson = browserFetch): Promise<CbetSpotData> {
  const key = `${entry.file}@${entry.version}`;
  let p = spotCache.get(key);
  if (!p) {
    p = fetchJson(`${CBET_DATA_BASE}/${entry.file}?v=${encodeURIComponent(entry.version)}`).then(parseCbetSpot).catch((e) => { spotCache.delete(key); throw e; });
    spotCache.set(key, p);
  }
  return p;
}
export function clearCbetCache() { manifestPromise = null; spotCache.clear(); }

// ---------------------------------------------------------------------------------------------
// Sorteio de mãos: flop resolvido + permutação de naipes (mesma permutação no board e no combo).

const SUITS = ["s", "h", "d", "c"] as const;
export type SuitPerm = Record<string, string>;
export function randomSuitPerm(rng: Rng): SuitPerm {
  const s: string[] = [...SUITS];
  for (let i = s.length - 1; i > 0; i--) { const j = rng.int(i + 1); [s[i], s[j]] = [s[j]!, s[i]!]; }
  return Object.fromEntries(SUITS.map((x, i) => [x, s[i]!]));
}
export const permuteCard = (c: Card, p: SuitPerm): Card => `${c[0]}${p[c[1]!] ?? c[1]}`;
const byRankDesc = (a: Card, b: Card) => rankValue(b[0]) - rankValue(a[0]) || SUITS.indexOf(a[1] as never) - SUITS.indexOf(b[1] as never);

export type FlopPick = "weighted" | "uniform";
export type ComboFocus = "all" | "costly";
export interface CbetDealOptions { flopPick?: FlopPick; focus?: ComboFocus; strata?: string[]; tree?: CbetTree }

export interface CbetHand {
  id: string;
  spot: string;
  flopIndex: number;
  /** Combo e board como estão nos dados (para corrigir). */
  combo: string;
  /** Como aparecem na mesa (naipes permutados). */
  board: [Card, Card, Card];
  hero: [Card, Card];
}

/** Família da textura (o estrato sem o prefixo "video:"). */
export const stratumOf = (f: CbetFlop) => f.stratum.replace(/^video:/, "");

export function eligibleFlops(data: CbetSpotData, opts: CbetDealOptions = {}): number[] {
  const all = data.flops.map((_, i) => i);
  const byStrata = opts.strata?.length ? all.filter((i) => opts.strata!.some((s) => stratumOf(data.flops[i]!).startsWith(s))) : all;
  return byStrata.length ? byStrata : all;
}

export function dealCbetHand(data: CbetSpotData, rng: Rng, opts: CbetDealOptions = {}): CbetHand {
  const idx = eligibleFlops(data, opts);
  let fi: number;
  if ((opts.flopPick ?? "weighted") === "weighted") {
    // Peso do estrato (fração dos 22.100 flops). Flops "video" têm peso 0: entram com o menor peso positivo.
    const minPos = Math.min(...idx.map((i) => data.flops[i]!.weight).filter((w) => w > 0), 1);
    const ws = idx.map((i) => Math.max(data.flops[i]!.weight, minPos));
    let x = rng.next() * ws.reduce((a, b) => a + b, 0);
    fi = idx[idx.length - 1]!;
    for (let k = 0; k < idx.length; k++) { x -= ws[k]!; if (x <= 0) { fi = idx[k]!; break; } }
  } else fi = idx[rng.int(idx.length)]!;
  const flop = data.flops[fi]!;
  const all = Object.keys(flop.agg).sort();
  const costly = all.filter((c) => comboSpread(flop, c, opts.tree ?? "simple") >= COSTLY_DECISION_BB);
  const pool = opts.focus === "costly" && costly.length ? costly : all;
  const combo = pool[rng.int(pool.length)]!;
  const perm = randomSuitPerm(rng);
  const board = splitCards(flop.flop).map((c) => permuteCard(c, perm)).sort(byRankDesc) as [Card, Card, Card];
  const hero = splitCards(combo).map((c) => permuteCard(c, perm)).sort(byRankDesc) as [Card, Card];
  return { id: `${data.spot}|${fi}|${combo}|${SUITS.map((s) => perm[s]).join("")}`, spot: data.spot, flopIndex: fi, combo, board, hero };
}

// ---------------------------------------------------------------------------------------------
// Correção.

export type CbetGrade = "best" | "mixed" | "error";
/** Ação no flop: check ou um dos sizes da árvore do solver. */
export type CbetAction = "check" | CbetSize;
/** "simple" = check + o size do board (árvore simplificada); "full" = check, 33%, 65% e pote (árvore completa). */
export type CbetTree = "simple" | "full";
export const FULL_ACTIONS: CbetAction[] = ["check", "b33", "b65", "b100"];

export interface CbetOption { action: CbetAction; ev: number; freq: number; loss: number }
export interface CbetResult {
  tree: CbetTree;
  choice: CbetAction;
  best: CbetAction;
  grade: CbetGrade;
  /** EV perdido em bb (≥ 0). */
  loss: number;
  /** Opções da árvore usada na correção, com EV, frequência do solver e perda de cada uma. */
  options: CbetOption[];
  /** Estratégia da árvore completa para este combo (frequências), se exportada. */
  full: { action: string; freq: number }[] | null;
  // Compatibilidade (árvore simplificada); null quando o spot só tem a árvore completa.
  evCheck: number | null;
  evBet: number | null;
  freqCheck: number | null;
  freqBet: number | null;
}

/** O arquivo traz os EVs da árvore completa (export com 12 números por combo). */
export const hasFullTree = (flop: CbetFlop) => Object.values(flop.agg).every((r) => r.length >= 12);
export const spotHasFullTree = (data: CbetSpotData) => data.flops.every(hasFullTree);
/** O arquivo traz a árvore simplificada (check + o size do board). */
export const hasSimpleTree = (flop: CbetFlop) => flop.size !== null;
export const spotHasSimpleTree = (data: CbetSpotData) => data.flops.every(hasSimpleTree);

/** Árvore realmente usada: a pedida, ou a que o arquivo tem quando a pedida não foi exportada. */
function treeFor(flop: CbetFlop, row: CbetComboRow | null, tree: CbetTree): CbetTree {
  const full = row ? row.length >= 12 : hasFullTree(flop);
  return (tree === "full" || flop.size === null) && full ? "full" : "simple";
}

/** Ações que o drill oferece neste flop. */
export function cbetActions(flop: CbetFlop, tree: CbetTree): CbetAction[] {
  return treeFor(flop, null, tree) === "full" ? FULL_ACTIONS.filter((a) => flop.actions.includes(a)) : ["check", flop.size!];
}

/** Bet mais usado pelo range inteiro na árvore completa (para textos quando não há size do board). */
export function mainBetSize(flop: CbetFlop): CbetSize {
  const bets = flop.actions.map((a, i) => ({ a, f: flop.freq[i] ?? 0 })).filter((x) => x.a !== "check");
  return (bets.reduce((m, x) => (x.f > m.f ? x : m), bets[0] ?? { a: "b33", f: 0 }).a) as CbetSize;
}

function optionsFor(flop: CbetFlop, row: CbetComboRow, tree: CbetTree): CbetOption[] {
  const raw: { action: CbetAction; ev: number; freq: number }[] = treeFor(flop, row, tree) === "full"
    ? flop.actions.map((a, i) => ({ action: a as CbetAction, freq: row[4 + i] ?? 0, ev: row[8 + i] ?? 0 }))
    : [{ action: "check", freq: row[0]!, ev: row[2]! }, { action: flop.size!, freq: row[1]!, ev: row[3]! }];
  const max = Math.max(...raw.map((o) => o.ev));
  return raw.map((o) => ({ ...o, loss: Math.max(0, max - o.ev) }));
}

/** Diferença entre a melhor e a pior opção (foco "decisões que custam"). */
export function comboSpread(flop: CbetFlop, combo: string, tree: CbetTree): number {
  const row = flop.agg[combo];
  if (!row) return 0;
  const evs = optionsFor(flop, row, tree).map((o) => o.ev);
  return Math.max(...evs) - Math.min(...evs);
}

/** Corrige a ação pelo EV perdido na árvore escolhida (perda < MIX_TOLERANCE_BB = mista aceita). */
export function gradeCbetAction(flop: CbetFlop, combo: string, choice: CbetAction, tree: CbetTree = "simple"): CbetResult {
  const row = flop.agg[combo];
  if (!row) throw new Error(`Combo ${combo} fora do range do agressor em ${flop.flop}`);
  const used: CbetTree = treeFor(flop, row, tree);
  const options = optionsFor(flop, row, used);
  const chosen = options.find((o) => o.action === choice);
  if (!chosen) throw new Error(`Ação ${choice} não existe na árvore ${used} de ${flop.flop}`);
  const best = options.reduce((a, o) => (o.ev > a.ev ? o : a)).action;
  const loss = chosen.loss;
  const grade: CbetGrade = choice === best ? "best" : loss < MIX_TOLERANCE_BB ? "mixed" : "error";
  const full = row.length >= 8 ? flop.actions.map((a, i) => ({ action: a, freq: row[4 + i] ?? 0 })) : null;
  const simple = flop.size !== null;
  return { tree: used, choice, best, grade, loss, options, full, evCheck: simple ? row[2]! : null, evBet: simple ? row[3]! : null, freqCheck: simple ? row[0]! : null, freqBet: simple ? row[1]! : null };
}

/** Árvore simplificada com escolha check/bet (bet = o size do board). */
export function gradeCbet(flop: CbetFlop, combo: string, choice: CbetChoice): CbetResult {
  if (flop.size === null) throw new Error(`${flop.flop}: este export não tem a árvore simplificada`);
  return gradeCbetAction(flop, combo, choice === "bet" ? flop.size : "check", "simple");
}

// ---------------------------------------------------------------------------------------------
// Explicação (só fatos dos dados + leitura padrão de teoria, marcada como tal).

export const sizeLabel = (s: string) => s === "check" ? "Check" : s === "b33" ? "Bet 33%" : s === "b65" ? "Bet 65%" : s === "b100" ? "Bet pote" : s;
export const sizePct = (s: CbetSize) => s === "b33" ? 0.33 : s === "b65" ? 0.65 : 1;
export const betAmountBb = (data: CbetSpotData, s: CbetSize) => Math.round(data.pot_bb * sizePct(s) * 10) / 10;

const HIGH: Record<string, string> = { A: "ás alto", K: "rei alto", Q: "dama alta", J: "valete alto", T: "dez alto", M: "carta média (7–9) alta", L: "baixo (6 ou menos)" };
const TEX: Record<string, string> = { mono: "monotone", "2tone": "dois naipes", rbw: "rainbow" };
/** Estrato do export em português ("T-rbw-con" → "dez alto, rainbow, conectado"). */
export function describeStratum(stratum: string): string {
  const s = stratum.replace(/^video:/, "");
  if (s === "trinca") return "trinca no board";
  const par = s.match(/^par-(alto|medio|baixo)-(\w+)$/);
  if (par) return `board pareado (par ${par[1] === "medio" ? "médio" : par[1]}), ${TEX[par[2]!] ?? par[2]}`;
  const [h, tex, con] = s.split("-");
  return [HIGH[h ?? ""] ?? h, TEX[tex ?? ""] ?? tex, con === "con" ? "conectado" : con === "desc" ? "desconectado" : con].filter(Boolean).join(", ");
}

/** Porque o board pede esse size: leitura padrão de teoria a partir da equity e do size do solver. */
export function sizeReason(flop: CbetFlop): string {
  const eq = flop.equity_agg;
  const betFreq = 1 - (flop.freq[flop.actions.indexOf("check")] ?? 0);
  const eqTxt = `equity do range do agressor ${(eq * 100).toFixed(1).replace(".", ",")}%`;
  // Sem árvore simplificada: o size citado é o mais usado pelo range no solver completo.
  const size = flop.size ?? mainBetSize(flop);
  const lead = flop.size === null ? "Size mais usado pelo range" : "Size";
  if (size === "b33") {
    return `${lead} pequeno: ${eqTxt} e c-bet de ${Math.round(betFreq * 100)}% no solver completo. É vantagem de range — o range todo tem equity, sem precisar polarizar — então a aposta barata e frequente nega equity das mãos fracas do BB.`;
  }
  return `${lead} ${size === "b100" ? "grande (pote)" : "médio-grande"}: ${eqTxt} e c-bet de ${Math.round(betFreq * 100)}% no solver completo. Aqui a vantagem é de nuts (mais mãos muito fortes que o BB) e o board é dinâmico, então o range de aposta fica polarizado e aposta maior; as mãos médias preferem check.`;
}

// ---------------------------------------------------------------------------------------------
// Classificação da mão do herói no flop (só descrição para o feedback).

const RANK_NAME: Record<string, string> = { A: "ás", K: "rei", Q: "dama", J: "valete", T: "dez", "9": "nove", "8": "oito", "7": "sete", "6": "seis", "5": "cinco", "4": "quatro", "3": "três", "2": "dois" };
function straightInfo(vals: number[]): { made: boolean; outs: number } {
  const set = new Set(vals);
  if (set.has(14)) set.add(1);
  let made = false;
  const completing = new Set<number>();
  for (let lo = 1; lo <= 10; lo++) {
    const window = [lo, lo + 1, lo + 2, lo + 3, lo + 4];
    const missing = window.filter((v) => !set.has(v));
    if (!missing.length) made = true;
    else if (missing.length === 1) completing.add(missing[0]!);
  }
  return { made, outs: completing.size };
}

/** "Overpair", "Top pair (kicker A)", "Flush draw", "Ar (ás alto)"… */
export function describeFlopHand(hero: readonly Card[], board: readonly Card[]): string {
  const hv = hero.map((c) => rankValue(c[0])), bv = board.map((c) => rankValue(c[0]));
  const all = [...hero, ...board];
  const suitCount = (s: string) => all.filter((c) => c[1] === s).length;
  const flushSuit = SUITS.find((s) => suitCount(s) >= 5);
  const fdSuit = SUITS.find((s) => suitCount(s) === 4 && hero.some((c) => c[1] === s));
  const st = straightInfo([...hv, ...bv]);
  const counts = new Map<number, number>();
  for (const v of [...hv, ...bv]) counts.set(v, (counts.get(v) ?? 0) + 1);
  const boardCounts = new Map<number, number>();
  for (const v of bv) boardCounts.set(v, (boardCounts.get(v) ?? 0) + 1);
  const heroUses = (v: number) => hv.includes(v);
  const groups = [...counts.entries()].sort((a, b) => b[1] - a[1] || b[0] - a[0]);
  const top = Math.max(...bv);
  const sortedBoard = [...new Set(bv)].sort((a, b) => b - a);
  const name = (v: number) => RANK_NAME[["", "", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"][v]!] ?? String(v);

  const draws: string[] = [];
  if (fdSuit) draws.push(hero.filter((c) => c[1] === fdSuit).length === 2 ? "flush draw" : "flush draw (uma carta)");
  if (!st.made && st.outs >= 2) draws.push("open-ended");
  else if (!st.made && st.outs === 1) draws.push("gutshot");
  const withDraw = (s: string) => draws.length ? `${s} + ${draws.join(" + ")}` : s;

  if (groups[0]![1] === 4 && heroUses(groups[0]![0])) return "Quadra";
  if (groups[0]![1] === 3 && groups[1]?.[1] === 2 && (heroUses(groups[0]![0]) || heroUses(groups[1]![0]))) return "Full house";
  if (flushSuit && hero.some((c) => c[1] === flushSuit)) return "Flush";
  if (st.made) return "Sequência";
  if (groups[0]![1] === 3 && heroUses(groups[0]![0])) return hv[0] === hv[1] ? "Set" : "Trinca";
  const heroPairs = hv.filter((v) => (boardCounts.get(v) ?? 0) === 1);
  if (hv[0] !== hv[1] && heroPairs.length === 2) return withDraw("Dois pares");
  if (hv[0] === hv[1]) {
    const p = hv[0]!;
    if (p > top) return withDraw("Overpair");
    if (p > (sortedBoard[1] ?? 0)) return withDraw(`Par de ${name(p)} (abaixo da carta alta)`);
    return withDraw(`Par baixo (${name(p)})`);
  }
  if (heroPairs.length === 1) {
    const p = heroPairs[0]!;
    const kicker = hv.find((v) => v !== p)!;
    const pos = sortedBoard.indexOf(p);
    const label = pos === 0 ? `Top pair (kicker ${name(kicker)})` : pos === 1 ? "Segundo par" : "Par de baixo";
    return withDraw(label);
  }
  const overs = hv.filter((v) => v > top).length;
  const base = overs === 2 ? "Duas overcards" : Math.max(...hv) === 14 ? "Ar (ás alto)" : overs === 1 ? "Ar com overcard" : "Ar";
  if (!draws.length) return base;
  const d = draws.join(" + ");
  return `${d[0]!.toUpperCase()}${d.slice(1)}${overs ? ` + ${overs === 2 ? "duas overcards" : "overcard"}` : ""}`;
}

// ---------------------------------------------------------------------------------------------
// Resumo de uma série (EV perdido por 100 mãos, por estrato).

export interface CbetRecord { at: number; spot: string; version: string; flop: string; stratum: string; combo: string; choice: CbetAction | CbetChoice; best: CbetAction | CbetChoice; grade: CbetGrade; loss: number; ms: number; tree?: CbetTree }
export interface CbetSummary { hands: number; best: number; mixed: number; errors: number; evLostPer100: number | null; byStratum: { stratum: string; hands: number; errors: number; loss: number }[] }

export function summarizeCbet(rows: CbetRecord[]): CbetSummary {
  const by = new Map<string, { hands: number; errors: number; loss: number }>();
  for (const r of rows) {
    const k = describeStratum(r.stratum);
    const e = by.get(k) ?? { hands: 0, errors: 0, loss: 0 };
    e.hands++; if (r.grade === "error") e.errors++; e.loss += r.loss;
    by.set(k, e);
  }
  return {
    hands: rows.length,
    best: rows.filter((r) => r.grade === "best").length,
    mixed: rows.filter((r) => r.grade === "mixed").length,
    errors: rows.filter((r) => r.grade === "error").length,
    evLostPer100: rows.length ? (rows.reduce((a, r) => a + r.loss, 0) / rows.length) * 100 : null,
    byStratum: [...by.entries()].map(([stratum, v]) => ({ stratum, ...v })).sort((a, b) => b.loss - a.loss),
  };
}

const HISTORY_KEY = "nvt-cbet-history-v1";
const HISTORY_MAX = 2000;
export function loadCbetHistory(): CbetRecord[] {
  try {
    const raw = typeof localStorage === "undefined" ? null : localStorage.getItem(HISTORY_KEY);
    const v = raw ? JSON.parse(raw) : [];
    return Array.isArray(v) ? v : [];
  } catch { return []; }
}
export function appendCbetHistory(rows: CbetRecord[]) {
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify([...loadCbetHistory(), ...rows].slice(-HISTORY_MAX))); } catch { /* ignore */ }
}
