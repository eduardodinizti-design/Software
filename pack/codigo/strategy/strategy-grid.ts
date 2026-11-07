/**
 * Estratégia completa do spot para as 169 mãos (todas as ações, com as frequências e EVs que o trainer cobra):
 * a mesma decisão do motor, refeita trocando só a mão do herói. Alimenta a matriz colorida por ação do feedback
 * (mixes visíveis célula a célula) e o resumo do range por ação, pesado por combos.
 */
import { ALL_HANDS, combos, type Card, type HandKey } from "@/domain/cards";
import type { DecisionAction, TrainingScenario } from "@/domain/scenario";
import { strategyEngine } from "./engine";
import { presetFor } from "./preflop-solver/catalog";
import { opensHand } from "./providers/preflop-solver";
import type { StrategyDecision } from "./types";

export interface GridCell {
  mix: { action: DecisionAction; frequency: number }[]; evs: { action: DecisionAction; ev: number }[] | null;
  /** Vs 3bet: a mão não está no seu range de open (não chega neste spot); não é "fold". */
  outOfRange?: boolean;
}
export interface StrategyGrid {
  cells: Record<HandKey, GridCell>;
  /** Ações que aparecem no spot, na ordem de exibição (mais agressiva primeiro, fold por último). */
  actions: DecisionAction[];
  /** % dos combos em cada ação (soma 100, sobre as mãos que chegam ao spot). */
  totals: Partial<Record<DecisionAction, number>>;
  evUnit: "bb" | "pct" | null;
  /** % dos combos fora do range de open (vs 3bet do solver). */
  outOfRangePct?: number;
}

/** Ordem de exibição: all-in → raises → call/limp/check → fold. */
export const ACTION_ORDER: DecisionAction[] = ["all_in", "four_bet_shove", "three_bet_shove", "four_bet", "three_bet", "raise", "call", "limp", "check", "fold"];

/** Cartas representativas de uma mão (só servem para a mão "existir"; pré-flop sem board). */
export function representativeCards(h: HandKey): [Card, Card] {
  if (h.length === 2) return [`${h[0]}s`, `${h[1]}h`];
  return h[2] === "s" ? [`${h[0]}s`, `${h[1]}s`] : [`${h[0]}s`, `${h[1]}h`];
}

export const mixOf = (d: StrategyDecision) => [{ action: d.recommended, frequency: d.frequency }, ...d.alternatives];

export function strategyGrid(s: TrainingScenario, decide: (s: TrainingScenario) => StrategyDecision = (x) => strategyEngine.decide(x)): StrategyGrid {
  const cells = {} as Record<HandKey, GridCell>;
  const seen = new Set<DecisionAction>();
  const weight: Partial<Record<DecisionAction, number>> = {};
  let unit: StrategyGrid["evUnit"] = null;
  // Vs 3bet com o HRC: só as mãos que você abre chegam aqui; as outras ficam marcadas, não como fold.
  const p = s.spot.type === "vs_3bet" ? presetFor(s) : null;
  const inRange = (h: HandKey) => !p || opensHand(p, s.spot.heroPosition, h);
  let outW = 0;
  for (const h of ALL_HANDS) {
    if (!inRange(h)) { cells[h] = { mix: [], evs: null, outOfRange: true }; outW += combos(h); continue; }
    const d = h === s.hero.hand ? decide(s) : decide({ ...s, hero: { hand: h, cards: representativeCards(h) } });
    const mix = mixOf(d).filter((m) => m.frequency > 0);
    cells[h] = { mix, evs: d.actionEvs ?? null };
    if (d.evUnit) unit = d.evUnit;
    for (const m of mix) { seen.add(m.action); weight[m.action] = (weight[m.action] ?? 0) + m.frequency * combos(h); }
  }
  for (const a of s.legalActions) seen.add(a);
  const actions = ACTION_ORDER.filter((a) => seen.has(a));
  const totals = Object.fromEntries(actions.map((a) => [a, ((weight[a] ?? 0) / Math.max(1, 1326 - outW)) * 100])) as StrategyGrid["totals"];
  return { cells, actions, totals, evUnit: unit, ...(outW ? { outOfRangePct: (outW / 1326) * 100 } : {}) };
}
