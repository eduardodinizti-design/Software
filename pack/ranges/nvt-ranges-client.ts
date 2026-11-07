/**
 * Cliente de exemplo para o pacote "nvt-range-export" v1 (gerado por scripts/export-ranges.ts).
 * Sem dependências: copie este arquivo para o outro sistema junto com nvt-ranges.json.
 *
 *   const ranges = NvtRanges.fromJson(JSON.parse(fs.readFileSync("nvt-ranges.json", "utf8")));
 *   const node = ranges.find({ mode: "chip_ev", stack: 25, spot: "vs_open", hero: "BB", vs: ["BTN"] });
 *   ranges.strategy(node!, "A5s");           // { mix: [{action:"three_bet",frequency:0.6},...], ev: {...} }
 *   ranges.grade(node!, "A5s", "call");      // { correct, correctness, evLoss, best }
 *
 * Regras (as mesmas do trainer):
 * - certa = qualquer ação com frequência > 0 no nó (o pacote já descartou frequências < 5% e empates viram mix);
 * - quase indiferente: se o nó tem EV, uma ação que perde menos que 0,05bb (chip EV) ou 0,02% do prize pool (ICM)
 *   para a melhor também é certa, e também a ação +EV vs fold que perde até 10% do EV da melhor (no máximo 0,3bb / 0,06%);
 * - mão em `outOfRange` (vs 3bet) não chega ao spot: não pergunte essa mão.
 */

export type Mode = "chip_ev" | "icm" | "pko" | "pko_icm";
export type Stage = "early" | "mid" | "pre_itm" | "bubble" | "ft";
export type Spread = "iguais" | "curtos_ini" | "curtos_fim";
export type Action = "fold" | "call" | "raise" | "all_in" | "three_bet" | "three_bet_shove" | "four_bet" | "four_bet_shove" | "limp" | "check";

export interface ExportNode {
  id: string;
  context: { mode: Mode; format: "regular" | "pko" | "bounty"; stage: Stage; players: number; stack: number };
  spot: string;
  hero: string;
  vs: string[];
  spread?: Spread;
  table: { stacks: Record<string, number>; actions: { position: string; type: string; amount: number }[]; potBb: number };
  source: { id: string; label: string; version?: string };
  family: string | null;
  validated: boolean;
  evUnit: "bb" | "pct" | null;
  legalActions: Action[];
  actions: Action[];
  freq: Record<string, number[]>;
  ev: Record<string, (number | null)[]> | null;
  outOfRange?: number[];
  totals: Record<string, number>;
}
export interface ExportBundle {
  format: "nvt-range-export"; version: 1; generatedAt: string; engineCommit: string;
  validation: { version: string; gate: boolean };
  hands: string[]; combos: number[]; actionLabels: Record<string, string>;
  nodes: ExportNode[];
}

export const EV_MIX_TOL = { bb: 0.05, pct: 0.02 } as const;
const RANKS = "AKQJT98765432";

/** "AhKd" / "Ah Kd" / ["Ah","Kd"] → "AKo"; "AKs", "TT" passam direto. */
export function handKey(cards: string | [string, string]): string {
  if (typeof cards === "string" && /^[AKQJT2-9]{2}[so]?$/.test(cards)) return cards;
  const [a, b] = typeof cards === "string" ? cards.replace(/\s+/g, "").match(/.{2}/g)! : cards;
  const [r1, s1, r2, s2] = [a![0]!.toUpperCase(), a![1]!, b![0]!.toUpperCase(), b![1]!];
  const [hi, lo] = RANKS.indexOf(r1) <= RANKS.indexOf(r2) ? [r1, r2] : [r2, r1];
  return hi === lo ? `${hi}${lo}` : `${hi}${lo}${s1 === s2 ? "s" : "o"}`;
}

export class NvtRanges {
  private idx = new Map<string, number>();
  private constructor(readonly bundle: ExportBundle) {
    if (bundle.format !== "nvt-range-export" || bundle.version !== 1) throw new Error("pacote desconhecido");
    bundle.hands.forEach((h, i) => this.idx.set(h, i));
  }
  static fromJson(json: unknown) { return new NvtRanges(json as ExportBundle); }

  /**
   * Nó do spot. `stage` é opcional em chip EV/PKO (um nó só); no ICM, informe a fase e o spread (ou os stacks da
   * mesa por posição, e o spread mais próximo é escolhido como no trainer).
   */
  find(q: { mode: Mode; stack: number; spot: string; hero: string; vs?: string[]; stage?: Stage; spread?: Spread; stacks?: Record<string, number> }): ExportNode | null {
    const spread = q.spread ?? (q.stacks ? nearestSpread(q.stacks) : undefined);
    const vs = (q.vs ?? []).join(">");
    const all = this.bundle.nodes.filter((n) => n.context.mode === q.mode && n.context.stack === q.stack && n.spot === q.spot && n.hero === q.hero && n.vs.join(">") === vs && (!q.stage || n.context.stage === q.stage || (n.context.stage === "mid" && q.stage === "early")));
    return all.find((n) => !n.spread || !spread || n.spread === spread) ?? all[0] ?? null;
  }

  /** Mix (ações com frequência > 0, maior primeiro) e EV de cada ação para a mão. */
  strategy(node: ExportNode, hand: string | [string, string]) {
    const i = this.idx.get(handKey(hand));
    if (i === undefined) throw new Error(`mão inválida: ${String(hand)}`);
    if (node.outOfRange?.includes(i)) return { outOfRange: true as const, mix: [], ev: null };
    const mix = node.actions.map((a) => ({ action: a, frequency: node.freq[a]![i]! })).filter((m) => m.frequency > 0).sort((x, y) => y.frequency - x.frequency);
    const ev = node.ev ? Object.fromEntries(node.actions.map((a) => [a, node.ev![a]![i]])) as Record<Action, number | null> : null;
    return { outOfRange: false as const, mix, ev };
  }

  /** Corrige a resposta como o trainer. */
  grade(node: ExportNode, hand: string | [string, string], chosen: Action) {
    const st = this.strategy(node, hand);
    if (st.outOfRange) return { correct: true, correctness: "OUT_OF_RANGE" as const, evLoss: 0, best: null };
    const best = st.mix[0]?.action ?? "fold";
    const inMix = st.mix.some((m) => m.action === chosen);
    let evLoss: number | null = null;
    if (st.ev && st.ev[chosen] !== null && st.ev[chosen] !== undefined) {
      const top = Math.max(...Object.values(st.ev).filter((x): x is number => x !== null));
      evLoss = Math.max(0, top - st.ev[chosen]!);
    }
    const tol = node.evUnit ? EV_MIX_TOL[node.evUnit] : 0;
    const top = st.ev ? Math.max(...Object.values(st.ev).filter((x): x is number => x !== null)) : 0;
    const chosenEv = st.ev?.[chosen] ?? null;
    // Mix válido também pelo EV relativo: ação +EV vs fold que perde até 10% do EV da melhor, no máximo 0,3bb / 0,06%.
    const relOk = evLoss !== null && chosenEv !== null && chosenEv > 0 && evLoss <= 0.1 * top && evLoss <= (node.evUnit === "pct" ? 0.06 : 0.3);
    const nearTie = evLoss !== null && (evLoss < tol || relOk);
    const correct = inMix || nearTie;
    return { correct, correctness: !correct ? ("STRATEGIC_ERROR" as const) : chosen === best ? ("CORRECT" as const) : ("ACCEPTABLE_MIXED_ACTION" as const), evLoss, best };
  }

  /** Matriz 13×13 (linhas/colunas AKQ…2; acima da diagonal suited, abaixo offsuit) da frequência de uma ação. */
  matrix(node: ExportNode, action: Action): number[][] {
    return [...RANKS].map((r, i) => [...RANKS].map((c, j) => {
      const h = i === j ? `${r}${c}` : i < j ? `${r}${c}s` : `${c}${r}o`;
      return node.freq[action]?.[this.idx.get(h)!] ?? 0;
    }));
  }
}

/** Distribuição de stacks mais próxima (mesma conta do trainer), a partir dos stacks por posição (9-max). */
const POS9 = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];
const SPREADS: Record<Spread, number[]> = {
  iguais: [25, 25, 25, 25, 25, 25, 25, 25, 25],
  curtos_fim: [35, 35, 30, 30, 25, 20, 15, 15, 20],
  curtos_ini: [15, 15, 20, 20, 25, 30, 35, 35, 30],
};
export function nearestSpread(stacks: Record<string, number>): Spread {
  const seats = POS9.map((p, i) => ({ i, st: stacks[p] })).filter((x): x is { i: number; st: number } => typeof x.st === "number");
  const mean = seats.reduce((a, x) => a + x.st, 0) / Math.max(1, seats.length);
  let best: Spread = "iguais", bestD = Infinity;
  for (const [k, v] of Object.entries(SPREADS) as [Spread, number[]][]) {
    const m = seats.reduce((a, x) => a + v[x.i]!, 0) / Math.max(1, seats.length);
    const d = seats.reduce((a, x) => a + (x.st / mean - v[x.i]! / m) ** 2, 0);
    if (d < bestD - 1e-9) { bestD = d; best = k; }
  }
  return best;
}
