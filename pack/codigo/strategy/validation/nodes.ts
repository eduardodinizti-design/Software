/**
 * O lado "nosso" de cada nó comparado com a referência: estratégia e EV (relativo ao fold) do motor do trainer.
 * Usado por `scripts/validate-ranges.ts` e pelos testes.
 */
import { ALL_HANDS, combos, type HandKey } from "@/domain/cards";
import type { Position } from "@/domain/positions";
import type { StackBucket } from "@/domain/scenario";
import { solvePushFold, type PushFoldSeat } from "../pushfold/nash";
import { fieldModel } from "@/icm/engine";
import { openerPrior } from "../providers/push-fold";
import { RESTEAL_OPEN_SIZE } from "@/domain/scenario";
import { PKO_CASH_SHARE } from "@/domain/tournament";
import type { TableState } from "@/domain/table";
import { nvtOpenRange } from "../ranges/nvt-charts";
import { at, POS9, type PreflopPreset } from "../preflop-solver/catalog";
import { MIN_FREQ } from "../providers/preflop-solver";
import { compareNode, parseRange, type NodeComparison, type NodeStrategy } from "./compare";
import { solverFamily } from "./status";

export type NodeSpec =
  | { type: "solver"; preset: string; kind: "rfi" | "resp" | "opv3"; key: string }
  /** opener: resteal — o opener abre RESTEAL_OPEN_SIZE (range de referência do trainer), quem está no meio folda e `pusher` dá all-in por cima. */
  /** bounties (PKO + ICM): cabeça de cada assento na moeda dos prêmios; metade é paga na hora (PKO_CASH_SHARE). */
  | { type: "nash"; stacks: number[]; pusher: Position; payouts?: number[]; caller?: Position; opener?: Position; bounties?: number[];
      /** PKO em fichas (começo/meio): cabeças em bounties iniciais e stack inicial em BBs, como o trainer no modo "pko". */
      pkoChip?: { startStackBb: number; heads: number[]; field?: { remaining: number; paid: number; prizes: number[]; bounties: number[]; otherBounty?: number | null; otherAvgBb?: number | null } } }
  | { type: "team_open"; stack: StackBucket; position: Position };

export interface ReferenceFile {
  family: string;
  /** Ferramenta e configuração usadas (ex.: "HRC 3.4 Pro, postflop model, 9-max 25bb BB ante 1bb"). */
  source: string;
  author?: string;
  date?: string;
  node: NodeSpec;
  /** Range de cada ação na referência, em texto (raise, allin, call, 3bet, push). */
  ranges: Record<string, string>;
}

export interface OurNode { strategy: NodeStrategy; ev: Record<string, Partial<Record<HandKey, number>>> | null; unit: "bb" | "pct"; reach?: Partial<Record<HandKey, number>> }

const rec = (p: PreflopPreset, a: number[]) => Object.fromEntries(ALL_HANDS.map((h) => [h, at(p, a, h)])) as Record<HandKey, number>;
const minus = (p: PreflopPreset, a: number[], f: number[]) => Object.fromEntries(ALL_HANDS.map((h) => [h, at(p, a, h) - at(p, f, h)])) as Record<HandKey, number>;

/** Ações da referência → nomes internos. */
const ALIAS: Record<string, string> = { raise: "raise", open: "raise", allin: "allin", "all-in": "allin", shove: "allin", push: "allin", jam: "allin", call: "call", "3bet": "3bet", threebet: "3bet", three: "3bet" };
export const normalizeRanges = (r: Record<string, string>): NodeStrategy => Object.fromEntries(Object.entries(r).map(([k, v]) => [ALIAS[k.toLowerCase()] ?? k.toLowerCase(), parseRange(v)]));

export function ourNode(spec: NodeSpec, getPreset: (name: string) => PreflopPreset | null): OurNode | null {
  if (spec.type === "solver") {
    const p = getPreset(spec.preset); if (!p) return null;
    if (spec.kind === "rfi") {
      const n = p.rfi[spec.key]; if (!n) return null;
      return { unit: p.unit, strategy: { raise: rec(p, n.raise), allin: rec(p, n.shove) }, ev: { raise: minus(p, n.ev.raise, n.ev.fold), allin: minus(p, n.ev.shove, n.ev.fold) } };
    }
    if (spec.kind === "resp") {
      const n = p.resp[spec.key]; if (!n) return null;
      return { unit: p.unit, strategy: { call: rec(p, n.call), "3bet": rec(p, n.three), allin: rec(p, n.shove) }, ev: { call: minus(p, n.ev.call, n.ev.fold), "3bet": minus(p, n.ev.three, n.ev.fold), allin: minus(p, n.ev.shove, n.ev.fold) } };
    }
    const n = p.opv3[spec.key]; const opener = spec.key.split(">")[0]!; const rfi = p.rfi[opener];
    if (!n || !rfi) return null;
    // vs 3bet: só as mãos que o próprio motor abre; o arquivo não traz o EV deste nó.
    return { unit: p.unit, strategy: { call: rec(p, n.call), allin: rec(p, n.shove) }, ev: null, reach: Object.fromEntries(ALL_HANDS.map((h) => [h, at(p, rfi.raise, h) >= MIN_FREQ ? 1 : 0])) };
  }
  if (spec.type === "nash") {
    if (spec.stacks.length !== 9) return null;
    const seats: PushFoldSeat[] = spec.stacks.map((stack, i) => ({ stack, blind: i === 7 ? 0.5 : i === 8 ? 1 : 0, ante: i === 8 ? 1 : 0 }));
    const pusher = POS9.indexOf(spec.pusher);
    if (spec.opener) {
      // Resteal como o trainer resolve: opener com o range de open do HRC (chip EV) ou de referência, sem flat.
      const op = POS9.indexOf(spec.opener);
      const table = { size: 9, format: "regular", players: POS9.map((position, seat) => ({ seat, position, stackBb: spec.stacks[seat]! })) } as unknown as TableState;
      const phase = spec.payouts ? ({ 9: "ft", 8: "bubble", 7: "pre_itm" } as Record<number, string>)[spec.payouts.length] : undefined;
      // PKO no começo/meio: field do torneio (ICM exato por grupos) + bounties, opener com o open do HRC da fase.
      const fl = spec.pkoChip?.field;
      const fm = fl ? fieldModel({ table: spec.stacks, remaining: fl.remaining, paid: fl.paid, prizes: fl.prizes, otherAvg: fl.otherAvgBb ?? null, maxField: fl.remaining, bounties: fl.bounties, otherBounty: fl.otherBounty ?? null, cashShare: PKO_CASH_SHARE }) : null;
      const model = fl ? `pkochip_${fl.remaining > 140 ? "early" : "mid"}` : !spec.payouts ? "chip" : phase ? `${spec.bounties ? "pko" : "icm"}_${phase}` : null;
      const prior = openerPrior(table, { format: "regular", stage: "mid", players: 9, stack: 25 }, op, model);
      const base = fm ? fm.stacks.map((stack, i) => seats[i] ?? { stack, blind: 0, ante: 0 }) : seats;
      const sol = solvePushFold({
        seats: base.map((x, i) => (i === op ? { ...x, invested: RESTEAL_OPEN_SIZE } : x)),
        pusher,
        callers: [...POS9.map((_, i) => i).filter((i) => i > pusher), op],
        priors: { [op]: prior },
        foldWinner: op,
        ...(fm ? { payouts: fm.payouts, bounties: { heads: fm.pko!.heads, cashShare: PKO_CASH_SHARE } } : {}),
        ...(!fm && spec.payouts ? { payouts: spec.payouts } : {}),
        ...(!fm && spec.bounties && spec.payouts ? { bounties: { heads: spec.bounties, cashShare: PKO_CASH_SHARE } } : {}),
      });
      return { unit: sol.unit, strategy: { allin: Object.fromEntries(ALL_HANDS.map((h, i) => [h, sol.push[i] ?? 0])) as Record<HandKey, number> }, ev: { allin: Object.fromEntries(ALL_HANDS.map((h, i) => [h, sol.pushEv[i] ?? 0])) as Record<HandKey, number> } };
    }
    // PKO começo/meio: o modelo do trainer (pkoChipField) = field do torneio inteiro (ICM exato por grupos) +
    // bounties em dinheiro, com os números do torneio da referência.
    const fl = spec.pkoChip?.field;
    const fm = fl ? fieldModel({ table: spec.stacks, remaining: fl.remaining, paid: fl.paid, prizes: fl.prizes, otherAvg: fl.otherAvgBb ?? null, maxField: fl.remaining, bounties: fl.bounties, otherBounty: fl.otherBounty ?? null, cashShare: PKO_CASH_SHARE }) : null;
    const pko = fm ? { bounties: { heads: fm.pko!.heads, cashShare: PKO_CASH_SHARE } }
      : spec.bounties && spec.payouts ? { bounties: { heads: spec.bounties, cashShare: PKO_CASH_SHARE } } : {};
    const sol = fm
      ? solvePushFold({ seats: fm.stacks.map((stack, i) => seats[i] ?? { stack, blind: 0, ante: 0 }), pusher, callers: POS9.map((_, i) => i).filter((i) => i > pusher), payouts: fm.payouts, ...pko })
      : solvePushFold({ seats, pusher, ...(spec.payouts ? { payouts: spec.payouts } : {}), ...pko });
    const byHand = (a: ArrayLike<number>) => Object.fromEntries(ALL_HANDS.map((h, i) => [h, a[i] ?? 0])) as Record<HandKey, number>;
    if (spec.caller) {
      const c = sol.callers.find((x) => x.seat === POS9.indexOf(spec.caller!)); if (!c) return null;
      return { unit: sol.unit, strategy: { call: byHand(c.call) }, ev: { call: byHand(c.callEv) } };
    }
    return { unit: sol.unit, strategy: { allin: byHand(sol.push) }, ev: { allin: byHand(sol.pushEv) } };
  }
  const r = nvtOpenRange({ format: "regular", stage: "mid", players: 9, stack: spec.stack, mode: "chip_ev" }, spec.position);
  if (!r) return null;
  // EV: o do solver chip EV no mesmo stack, quando existe (para medir se uma divergência é barata).
  const p = spec.stack === 25 || spec.stack === 40 ? getPreset(`chip_${spec.stack}`) : null;
  const n = p?.rfi[spec.position];
  return { unit: "bb", strategy: { raise: Object.fromEntries(ALL_HANDS.map((h) => [h, r.hands[h] ?? 0])) as Record<HandKey, number> }, ev: p && n ? { raise: minus(p, n.ev.raise, n.ev.fold) } : null };
}

export function compareReference(ref: ReferenceFile, getPreset: (name: string) => PreflopPreset | null): (NodeComparison & { error?: undefined }) | { error: string } {
  const ours = ourNode(ref.node, getPreset);
  if (!ours) return { error: "nó não encontrado no motor" };
  return compareNode(ours.strategy, normalizeRanges(ref.ranges), ours.ev, ours.unit, ours.reach);
}

/** Convergência de uma situação do catálogo: fração das ações jogadas (≥5%) que perdem EV relevante. */
export function solverInconsistency(p: PreflopPreset): number {
  const tol = p.unit === "bb" ? 0.05 : 0.02;
  let bad = 0, tot = 0;
  for (const [pos, n] of Object.entries(p.rfi)) {
    if (pos === "SB") continue; // a SB também limpa (fora do nó)
    for (let i = 0; i < 169; i++) {
      const f = { raise: n.raise[i]!, shove: n.shove[i]!, fold: Math.max(0, 1 - n.raise[i]! - n.shove[i]!) };
      const e = { raise: n.ev.raise[i]!, shove: n.ev.shove[i]!, fold: n.ev.fold[i]! };
      const best = Math.max(e.raise, e.shove, e.fold);
      for (const k of ["raise", "shove", "fold"] as const) if (f[k] >= 0.05) { tot++; if (best - e[k] > tol) bad++; }
    }
  }
  for (const n of Object.values(p.resp)) {
    for (let i = 0; i < 169; i++) {
      const f = { call: n.call[i]!, three: n.three[i]!, shove: n.shove[i]!, fold: Math.max(0, 1 - n.call[i]! - n.three[i]! - n.shove[i]!) };
      const e = { call: n.ev.call[i]!, three: n.ev.three[i]!, shove: n.ev.shove[i]!, fold: n.ev.fold[i]! };
      const best = Math.max(...Object.values(e));
      for (const k of ["call", "three", "shove", "fold"] as const) if (f[k] >= 0.05) { tot++; if (best - e[k] > tol) bad++; }
    }
  }
  return tot ? bad / tot : 0;
}

export const MAX_INCONSISTENCY = 0.03;
/** Mínimo de nós comparados para validar uma família. */
export const MIN_NODES: Record<string, number> = { solver: 10, nash: 4, team: 6 };

export interface FamilyVerdict { family: string; status: "validado" | "reprovado" | "em_validacao"; nodes: number; passed: number; agreement: number; notes: string[] }

/** Junta as comparações por família e aplica a régua. */
export function familyVerdicts(refs: ReferenceFile[], getPreset: (name: string) => PreflopPreset | null, presetNames: string[]): FamilyVerdict[] {
  const by = new Map<string, ReferenceFile[]>();
  for (const r of refs) { const a = by.get(r.family) ?? []; a.push(r); by.set(r.family, a); }
  const out: FamilyVerdict[] = [];
  for (const [family, rs] of by) {
    const notes: string[] = [];
    let passed = 0, agr = 0, w = 0;
    for (const r of rs) {
      const c = compareReference(r, getPreset);
      if ("error" in c && c.error) { notes.push(`${JSON.stringify(r.node)}: ${c.error}`); continue; }
      const cmp = c as NodeComparison;
      agr += cmp.agreement; w++;
      if (cmp.passed) passed++;
      else notes.push(`${JSON.stringify(r.node)}: ${(cmp.agreement * 100).toFixed(1)}% de concordância, pior divergência ${cmp.worstGap === null ? "sem EV" : cmp.worstGap.toFixed(3)} (${cmp.divergent.slice(0, 5).map((d) => `${d.hand} ${d.ours}≠${d.ref}`).join(", ")})`);
    }
    const kind = family.split(":")[0]!;
    if (kind === "solver") {
      for (const name of presetNames.filter((n) => solverFamily(n) === family)) {
        const p = getPreset(name); if (!p) continue;
        const inc = solverInconsistency(p);
        if (inc > MAX_INCONSISTENCY) notes.push(`${name}: ${(inc * 100).toFixed(1)}% das ações jogadas perdem EV (máx. 3%): cálculo não convergiu`);
      }
    }
    const failed = notes.length > 0;
    const enough = w >= (MIN_NODES[kind] ?? 6);
    out.push({ family, nodes: w, passed, agreement: w ? agr / w : 0, notes, status: failed ? "reprovado" : enough ? "validado" : "em_validacao" });
  }
  return out.sort((a, b) => a.family.localeCompare(b.family));
}

export const combosOf = (r: Partial<Record<HandKey, number>>) => ALL_HANDS.reduce((a, h) => a + (r[h] ?? 0) * combos(h), 0);
