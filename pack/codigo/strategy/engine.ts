import type { DecisionAction, TrainingScenario } from "@/domain/scenario";
import { manualProvider, nvtRangeProvider, nvtTeamProvider } from "./providers";
import { pushFoldProvider } from "./providers/push-fold";
import { pkoTeamProvider } from "./providers/pko-team";
import { sbLimpProvider } from "./providers/sb-limp";
import { withOpenShove } from "./providers/open-shove-mix";
import { reactionProvider } from "./providers/reaction";
import { icmOpenProvider } from "./providers/icm-preflop";
import { preflopSolverProvider } from "./providers/preflop-solver";
import type { BetSize, GradeResult, SourceProbe, StrategyDecision, StrategyProvider } from "./types";
import { evLossOf } from "./insight";

export class UnsupportedSpotError extends Error {}
/** Fontes que podem ter família validada (ver familyOf): solver pré-flop/HRC e tabelas do time; o Nash tem probe. */
const VALIDATABLE_SOURCES = new Set(["solver", "nvt_team"]);
import { EV_MIX_TOL_BB, EV_MIX_TOL_PCT, evMixAccepted } from "./tolerances";
export { EV_MIX_TOL_BB, EV_MIX_TOL_PCT };

/**
 * Single entry point for decisions. UI sends a scenario, receives a decision.
 * Providers are tried in priority order; the first that answers wins.
 */
export class StrategyEngine {
  constructor(private providers: StrategyProvider[]) {}

  decide(s: TrainingScenario): StrategyDecision {
    for (const p of this.providers) {
      if (!p.supports(s.spot.type)) continue;
      const d = p.decide(s);
      if (d && (d.range.context.mode ?? "chip_ev") === (s.context.mode ?? "chip_ev")) return s.spot.type === "open_raise" ? withOpenShove(s, d) : d;
    }
    throw new UnsupportedSpotError(`Nenhuma estratégia disponível para o spot ${s.spot.type}`);
  }

  /**
   * Qual fonte responderia, sem calcular quando o provider sabe dizer isso barato (o Nash com ICM leva segundos).
   * Mesma ordem e mesmo critério de `decide`. Usado pela trava de validação: null quando não há fonte ou quando
   * nenhuma fonte restante pode ser validada.
   */
  probe(s: TrainingScenario): SourceProbe | null {
    const list = this.providers.filter((p) => p.supports(s.spot.type));
    for (const [i, p] of list.entries()) {
      // Daqui para frente nenhuma fonte é validável: a trava já sabe a resposta (não validado) sem calcular.
      if (!list.slice(i).some((q) => q.probe || VALIDATABLE_SOURCES.has(q.source.id))) return null;
      if (p.probe) { const r = p.probe(s); if (r && r.mode === (s.context.mode ?? "chip_ev")) return r; continue; }
      const d = p.decide(s);
      if (d && (d.range.context.mode ?? "chip_ev") === (s.context.mode ?? "chip_ev")) return { source: d.source, rangeId: d.range.id, mode: d.range.context.mode ?? "chip_ev" };
    }
    return null;
  }

  grade(d: StrategyDecision, chosen: DecisionAction, betSize?: BetSize | null): GradeResult {
    // Quase indiferente: quando a fonte calcula EV e a ação escolhida perde menos que a tolerância
    // (0,05bb ou 0,02% do prize pool, a margem da régua), ela conta como mix válido, mesmo que o equilíbrio seja puro.
    if (d.outsideDrill) return { correct: true, chosen, chosenFrequency: 1, sizeCorrect: null, correctness: chosen === d.recommended ? "CORRECT" : "ACCEPTABLE_MIXED_ACTION" };
    const loss = evLossOf(d, chosen);
    if (loss !== null && chosen !== d.recommended && d.actionEvs && evMixAccepted(d.actionEvs, chosen, d.evUnit)) {
      return { correct: true, chosen, chosenFrequency: Math.max(0.01, d.alternatives.find((a) => a.action === chosen)?.frequency ?? 0), sizeCorrect: null, correctness: "ACCEPTABLE_MIXED_ACTION" };
    }
    const all = [{ action: d.recommended, frequency: d.frequency, betSize: d.recommendedBetSize }, ...d.alternatives];
    const candidates = all.filter((a) => a.action === chosen);
    const hasSizes = candidates.some((a) => a.betSize !== undefined);
    const matches = candidates.filter((a) => !a.betSize || sameBetSize(a.betSize, betSize));
    const chosenFrequency = matches.reduce((sum, a) => sum + a.frequency, 0);
    const correct = chosenFrequency > 0;
    return { correct, chosen, chosenFrequency, sizeCorrect: hasSizes ? matches.some((a) => a.frequency > 0) : null,
      correctness: !correct ? "STRATEGIC_ERROR" : chosen === d.recommended && (!d.recommendedBetSize || sameBetSize(d.recommendedBetSize, betSize)) ? "CORRECT" : "ACCEPTABLE_MIXED_ACTION" };
  }
}

export const strategyEngine = new StrategyEngine([manualProvider, preflopSolverProvider, icmOpenProvider, nvtTeamProvider, nvtRangeProvider, pkoTeamProvider, sbLimpProvider, reactionProvider, pushFoldProvider]);

export function sameBetSize(a: BetSize, b?: BetSize | null): boolean {
  return !!b && a.sizeBB === b.sizeBB && a.sizeOpenMultiplier === b.sizeOpenMultiplier;
}
