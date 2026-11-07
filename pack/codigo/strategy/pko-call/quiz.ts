/**
 * Quiz "Call de shove no PKO por bounty power".
 *
 * Base: um spot de push/fold resolvido no HRC em chip EV (scripts/import-hrc-pushfold.py), com o EV do call
 * relativo ao fold de cada mão do herói. O bounty entra pela tabela Bounty Power → equity drop do material do time
 * (`tableEquityDrop`): com o herói cobrindo o shover, cada ponto de equity a menos vale o pote final em bb, então
 *
 *   call ⇔ EV chip EV do call > −drop × (pote antes do call + custo do call).
 *
 * Cada rodada sorteia um BP entre BP_CHOICES e uma mão da fronteira desse BP (EV perto da linha de corte),
 * com naipes aleatórios, sem repetir a mão anterior. Quando o herói cobre e fala antes dos blinds, "continuar"
 * é call ou all-in por cima (isolar), o de maior EV no HRC; o bounty conta igual nos dois.
 *
 * Overcall (kind "overcall"): alguém abriu 2bb, o stack curto deu all-in por cima e o herói decide com o opener
 * ainda para falar. O EV vem do mesmo jeito do HRC (árvore com open 2bb, 3bet só all-in e cold call). Pode ser
 * corrigido em chip EV puro (corte em EV > 0, BP 0) ou com o bounty pela tabela (aproximado: a tabela é heads-up).
 */
import { ALL_HANDS, combos, type Card, type HandKey } from "@/domain/cards";
import { PKO_BOUNTY_CHIP_VALUE, tableEquityDrop } from "@/domain/pko";
import type { Rng } from "@/domain/rng";

export interface PkoCallSpot {
  format: 1;
  /** pushfold_call: o shove é o primeiro raise; overcall: alguém abriu (2bb) e o curto deu all-in por cima. */
  kind: "pushfold_call" | "overcall";
  name: string;
  note: string;
  unit: "bb";
  model: "chipev";
  stacks: number[];
  ante: number;
  shover: string;
  hero: string;
  /** Pote antes do call (bb): shove + blinds + ante. */
  pot: number;
  /** Custo do call (bb). */
  call: number;
  shove: Record<string, number>;
  /** Quem folda entre o shover e o herói. */
  folders?: string[];
  /** Overcall: quem abriu, o tamanho do open (bb) e quem foldou entre ele e o shover. O opener fala depois do herói. */
  opener?: string;
  openSize?: number;
  openFolders?: string[];
  /** Frequência de continuar (call + all-in por cima). */
  heroCall: Record<string, number>;
  /** EV de continuar − EV do fold, em bb, como o HRC exportou (o melhor entre call e all-in por cima). */
  heroCallEv: Record<string, number>;
  /** All-in por cima (isolar): frequência e se tem EV maior que o call. Ausente quando o herói só pode pagar (BB). */
  heroIso?: Record<string, number> | null;
  heroIsoBest?: Record<string, number> | null;
  version: string;
}
export interface PkoCallManifest { spots: { name: string; file: string; note: string; shover: string; hero: string; opener?: string; stacks: number[]; version: string }[] }
export type PkoCallKind = "shove" | "overcall";

export const BP_CHOICES = [0.5, 1, 2, 3] as const;
/** Modo chip EV puro (sem bounty): corte em EV > 0. */
export const CHIP_ONLY: readonly number[] = [0];
/** Distância máxima (bb) entre o EV da mão e a linha de corte do BP sorteado: só mãos de fronteira. */
export const FRONTIER_BB = 1.2;
export const POS9 = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"] as const;

const BASES: Record<PkoCallKind, string> = { shove: "/solver/hrc/pushfold", overcall: "/solver/hrc/overcall" };
type FetchJson = (p: string) => Promise<unknown>;
const browserFetch: FetchJson = async (p) => { const r = await fetch(p); if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); };
export async function loadPkoCallManifest(fetchJson: FetchJson = browserFetch, kind: PkoCallKind = "shove"): Promise<PkoCallManifest> {
  return (await fetchJson(`${BASES[kind]}/manifest.json`)) as PkoCallManifest;
}
export async function loadPkoCallSpot(e: PkoCallManifest["spots"][number], fetchJson: FetchJson = browserFetch, kind: PkoCallKind = "shove"): Promise<PkoCallSpot> {
  return (await fetchJson(`${BASES[kind]}/${e.file}?v=${encodeURIComponent(e.version)}`)) as PkoCallSpot;
}
/** Todos os spots de um tipo (manifest ausente = nenhum spot). */
export async function loadPkoCallSpots(kind: PkoCallKind, fetchJson: FetchJson = browserFetch): Promise<PkoCallSpot[]> {
  const m = await loadPkoCallManifest(fetchJson, kind).catch(() => null);
  return m ? Promise.all(m.spots.map((e) => loadPkoCallSpot(e, fetchJson, kind))) : [];
}
const slug = (p: string) => p.toLowerCase().replace("+", "");
/** O spot de push/fold com o mesmo shover, stack e herói, sem o open antes (para comparar com o overcall). */
export function headsUpTwin(s: PkoCallSpot, pushfold: PkoCallSpot[]): PkoCallSpot | null {
  if (s.kind !== "overcall") return null;
  const name = `${slug(s.shover)}${stackOf(s, s.shover)}_${slug(s.hero)}${stackOf(s, s.hero)}_chipev`;
  return pushfold.find((x) => x.name === name) ?? null;
}
/** Fração das mãos (por combos) com que o herói continua no spot. */
export const continuePct = (s: PkoCallSpot) => ALL_HANDS.reduce((a, h) => a + (s.heroCall[h] ?? 0) * combos(h), 0) / 1326;

export const finalPot = (s: PkoCallSpot) => s.pot + s.call;
export const stackOf = (s: PkoCallSpot, pos: string) => s.stacks[POS9.indexOf(pos as (typeof POS9)[number])] ?? 0;
/** Linha de corte em EV chip EV (bb) para um BP: abaixo dela é fold. */
export const evCut = (s: PkoCallSpot, bp: number) => -(tableEquityDrop(bp) / 100) * finalPot(s) || 0;
/** Equity mínima para pagar no freezeout e com o desconto do BP. */
export const requiredEquity = (s: PkoCallSpot, bp: number) => s.call / finalPot(s) - tableEquityDrop(bp) / 100;
/** Bounty do shover em bb pela régua do trainer (0,27 stack inicial por bounty inicial): BP × 0,27 × stack do shover. */
export const bountyBb = (s: PkoCallSpot, bp: number) => bp * PKO_BOUNTY_CHIP_VALUE * stackOf(s, s.shover);

export interface PkoCallHand { spot: string; hand: HandKey; cards: [Card, Card]; bp: number; ev: number; cut: number; /** o HRC prefere continuar com all-in por cima em vez de call */ iso: boolean }
export type PkoCallChoice = "call" | "fold";
export interface PkoCallResult { choice: PkoCallChoice; best: PkoCallChoice; correct: boolean; margin: number }

const SUITS = ["s", "h", "d", "c"];
function cardsFor(h: HandKey, r: Rng): [Card, Card] {
  const a = h[0]!, b = h[1]!;
  const s1 = SUITS[r.int(4)]!;
  if (h.length === 2) { let s2 = SUITS[r.int(4)]!; while (s2 === s1) s2 = SUITS[r.int(4)]!; return [a + s1, b + s2]; }
  if (h[2] === "s") return [a + s1, b + s1];
  let s2 = SUITS[r.int(4)]!; while (s2 === s1) s2 = SUITS[r.int(4)]!;
  return [a + s1, b + s2];
}

/** Mãos de fronteira para um BP: EV a até FRONTIER_BB da linha de corte. */
export function frontier(s: PkoCallSpot, bp: number): HandKey[] {
  const cut = evCut(s, bp);
  return ALL_HANDS.filter((h) => s.heroCallEv[h] !== undefined && Math.abs(s.heroCallEv[h]! - cut) <= FRONTIER_BB);
}

/** Quem ainda fala depois do herói (o EV do HRC já considera que eles podem entrar na mão). */
export const behind = (s: PkoCallSpot) => POS9.slice(POS9.indexOf(s.hero as (typeof POS9)[number]) + 1);
export const hasIso = (s: PkoCallSpot) => !!s.heroIso;

export function dealPkoCall(s: PkoCallSpot, r: Rng, previous?: HandKey | null, choices: readonly number[] = BP_CHOICES): PkoCallHand {
  const bps = choices.filter((b) => frontier(s, b).some((h) => h !== previous));
  const bp = bps.length ? bps[r.int(bps.length)]! : choices[r.int(choices.length)]!;
  let pool = frontier(s, bp).filter((h) => h !== previous);
  if (!pool.length) pool = ALL_HANDS.filter((h) => h !== previous && s.heroCallEv[h] !== undefined);
  const total = pool.reduce((a, h) => a + combos(h), 0);
  let x = r.next() * total, hand = pool[pool.length - 1]!;
  for (const h of pool) { x -= combos(h); if (x <= 0) { hand = h; break; } }
  return { spot: s.name, hand, cards: cardsFor(hand, r), bp, ev: s.heroCallEv[hand]!, cut: evCut(s, bp), iso: !!s.heroIsoBest?.[hand] };
}

export function gradePkoCall(h: PkoCallHand, choice: PkoCallChoice): PkoCallResult {
  const best: PkoCallChoice = h.ev > h.cut ? "call" : "fold";
  return { choice, best, correct: choice === best, margin: Math.abs(h.ev - h.cut) };
}

export const fmtBb = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(2).replace(".", ",")}bb`;
export const fmtBp = (v: number) => v.toFixed(1).replace(".", ",");
