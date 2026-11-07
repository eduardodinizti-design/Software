/**
 * ICM nos spots de open raise (e no range do opener usado pelo Vs Open / defesa do BB).
 *
 * Modelo (referência calibrada, não solver): parte do range sem ICM (tabela do time ou referência) e
 * ajusta pelo risco entre o herói e quem ainda fala, medido pelo motor de ICM da mesa:
 * - risk advantage = média do RP dos adversários contra o herói − média do RP do herói contra eles;
 * - tamanho do range × exp(3,8 × risk advantage), limitado a 0,4–1,8× e a 75% das mãos.
 * Calibração (estudos de ICM/GTO Wizard): stacks iguais quase não mudam o RFI; CO 45bb coberto pelo BTN
 * perto do dinheiro (−12 pts) cai de 34% para ~23%; chip leader na mesa final (+10 a +12 pts) sobe de
 * 33% para 50–55%. As blinds pesam mais na média (são quem mais defende).
 */
import { ALL_HANDS, combos, TOTAL_COMBOS, type HandKey } from "@/domain/cards";
import type { Position } from "@/domain/positions";
import type { StrategyContext, TrainingScenario } from "@/domain/scenario";
import type { TableState } from "@/domain/table";
import { pairRisk, playerValues, type PkoSpec } from "@/icm/engine";
import { PKO_CASH_SHARE } from "@/domain/tournament";
import { OPEN_PRIORITY } from "../ranges/reference-data";
import { openRangeFor } from "../ranges/open-range";
import { rangePercent } from "../ranges/stats";
import type { RangeDefinition } from "../ranges/types";
import type { StrategyDecision, StrategyProvider, StrategySourceInfo } from "../types";
import { decisionFromRange } from "./range-decision";

export const ICM_OPEN_VERSION = "icm-open-ref-1";
export const ICM_OPEN_SOURCE: StrategySourceInfo = { id: "icm", label: "Open com ICM (referência calibrada)", version: ICM_OPEN_VERSION };
const ADVANTAGE_K = 3.8;

export interface IcmPressure {
  /** RP médio do herói contra quem fala depois. */
  heroRp: number;
  /** RP médio dos que falam depois contra o herói. */
  theirRp: number;
  /** theirRp − heroRp (positivo = herói pressiona). */
  advantage: number;
  multiplier: number;
  rows: { position: Position; heroRp: number; theirRp: number }[];
}

/** Contexto de ICM do cenário: premiação e, no PKO + ICM, os bounties (mesma moeda). */
export function icmContext(s: TrainingScenario): { prizes: number[]; pko: PkoSpec | null; others: number[] } | null {
  if (s.context.mode !== "icm" && s.context.mode !== "pko_icm") return null;
  const prizes = s.tournament.payouts?.prizes;
  if (!prizes?.length) return null;
  const others = s.tournament.fieldOthers ?? [];
  const pko = s.context.mode === "pko_icm" && s.table.players.every((p) => p.bounty !== null)
    ? { heads: [...s.table.players.map((p) => p.bounty ?? 0), ...others.map(() => s.tournament.fieldOtherBounty ?? 0)], cashShare: PKO_CASH_SHARE } : null;
  return { prizes, pko, others };
}
/** Stacks do cálculo de ICM: mesa (índices = assentos) + jogadores das outras mesas. */
export const icmStacks = (t: TableState, others: number[] = []) => [...t.players.map((p) => p.stackBb), ...others];

/** Pressão de ICM do jogador `seat` contra quem ainda fala depois dele (pares de RP do motor). */
export function icmPressure(t: TableState, prizes: number[], seat: number, pko: PkoSpec | null = null, others: number[] = []): IcmPressure {
  const stacks = icmStacks(t, others);
  const base = playerValues(stacks, prizes, pko);
  const behind = t.players.filter((p) => p.seat > seat && p.status !== "folded");
  const rows = behind.map((p) => ({ position: p.position, heroRp: pairRisk(stacks, prizes, seat, p.seat, base, pko).riskPremium, theirRp: pairRisk(stacks, prizes, p.seat, seat, base, pko).riskPremium }));
  const w = (pos: Position) => (pos === "SB" || pos === "BB" ? 1.5 : 1);
  const tw = rows.reduce((a, r) => a + w(r.position), 0) || 1;
  const heroRp = rows.reduce((a, r) => a + w(r.position) * r.heroRp, 0) / tw;
  const theirRp = rows.reduce((a, r) => a + w(r.position) * r.theirRp, 0) / tw;
  const advantage = theirRp - heroRp;
  const multiplier = Math.min(1.8, Math.max(0.4, Math.exp(ADVANTAGE_K * advantage)));
  return { heroRp, theirRp, advantage, multiplier, rows };
}

/**
 * Range de open com ICM: mantém a composição da fonte sem ICM (as mãos dela primeiro, na ordem de
 * prioridade de open) e corta ou estende até o novo tamanho.
 */
export function icmOpenRange(ctx: StrategyContext, t: TableState, seat: number, prizes: number[], pko: PkoSpec | null = null, others: number[] = []): { range: RangeDefinition; pressure: IcmPressure; basePct: number } {
  const pos = t.players[seat]!.position;
  const base = openRangeFor({ ...ctx, mode: "chip_ev" }, pos);
  const basePct = rangePercent(base.hands);
  const pressure = icmPressure(t, prizes, seat, pko, others);
  const targetPct = Math.min(75, basePct * pressure.multiplier);
  const inBase = OPEN_PRIORITY.filter((h) => (base.hands[h] ?? 0) > 0);
  const order: HandKey[] = [...inBase, ...OPEN_PRIORITY.filter((h) => !((base.hands[h] ?? 0) > 0))];
  const target = (targetPct / 100) * TOTAL_COMBOS;
  const hands: Record<HandKey, number> = {};
  let acc = 0;
  for (const h of order) {
    const c = combos(h);
    if (acc + c <= target + 1e-9) { hands[h] = 1; acc += c; continue; }
    const f = Math.round(((target - acc) / c) * 20) / 20;
    if (f >= 0.1) hands[h] = Math.min(1, f);
    break;
  }
  void ALL_HANDS;
  const range: RangeDefinition = {
    id: `${base.id}|icm`, spot: "open_raise", action: "raise", position: pos, context: ctx, hands, source: pko ? "pko" : "icm", version: ICM_OPEN_VERSION,
    notes: `Open com ICM${pko ? " e bounty" : ""}: range sem ICM (${base.source === "nvt_team" ? "tabela NVT" : "referência"}, ${basePct.toFixed(1)}%) ajustado pela pressão de ICM (×${pressure.multiplier.toFixed(2)}).`,
  };
  return { range, pressure, basePct };
}

const pct = (v: number) => `${v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(1).replace(".", ",")}%`;

export const icmOpenProvider: StrategyProvider = {
  source: ICM_OPEN_SOURCE,
  supports: (spot) => spot === "open_raise",
  decide(s: TrainingScenario): StrategyDecision | null {
    const ic = icmContext(s);
    if (!ic) return null;
    const { range, pressure, basePct } = icmOpenRange(s.context, s.table, s.table.heroSeat, ic.prizes, ic.pko, ic.others);
    const d = decisionFromRange(s, range, ICM_OPEN_SOURCE);
    const newPct = rangePercent(range.hands);
    const worst = [...pressure.rows].sort((a, b) => b.heroRp - a.heroRp)[0];
    const best = [...pressure.rows].sort((a, b) => b.theirRp - a.theirRp)[0];
    const dir = pressure.advantage > 0.01 ? "você tem risk advantage: quem fala depois está mais pressionado que você, então o open abre" : pressure.advantage < -0.01 ? "você está em desvantagem de risco: quem fala depois te pressiona mais do que você a eles, então o open fecha" : "os riscos estão equilibrados, então o open quase não muda";
    const icmTxt = `${ic.pko ? " PKO + ICM: o bounty de quem você cobre dá desconto (risk premium negativo) e quem te cobre pesa mais." : ""} ICM: seu risk premium médio contra quem fala depois é ${pct(pressure.heroRp)} e o deles contra você ${pct(pressure.theirRp)}; ${dir} (${basePct.toFixed(1).replace(".", ",")}% sem ICM → ${newPct.toFixed(1).replace(".", ",")}% com ICM).${worst ? ` Mais perigoso: ${worst.position} (seu risk premium contra ele: ${pct(worst.heroRp)}).` : ""}${best && best.theirRp > 0.08 ? ` Mais pressionado por você: ${best.position} (${pct(best.theirRp)} contra você).` : ""} Referência calibrada pelos estudos de ICM, não solver.`;
    return { ...d, source: ic.pko ? { ...ICM_OPEN_SOURCE, id: "pko", label: "Open com ICM + bounty (referência calibrada)" } : ICM_OPEN_SOURCE, explanation: `${d.explanation}${icmTxt}`, theoryTags: ["icm", ...(ic.pko ? ["pko"] : []), "open_raise", "reference"] };
  },
};
