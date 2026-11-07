import type { DecisionAction, TrainingScenario } from "@/domain/scenario";
import { rangePercent } from "../ranges/stats";
import type { RangeDefinition } from "../ranges/types";
import type { ActionFrequency, StrategyDecision, StrategySourceInfo } from "../types";

/** Turns a single-action range into a decision for the hero's hand (rest of frequency = fold). */
export function decisionFromRange(s: TrainingScenario, range: RangeDefinition, source: StrategySourceInfo): StrategyDecision {
  const f = range.hands[s.hero.hand] ?? 0;
  const freqs: ActionFrequency[] = [
    { action: range.action as DecisionAction, frequency: f, ...(range.betSize ? { betSize: range.betSize } : {}) },
    { action: "fold" as DecisionAction, frequency: 1 - f },
  ].sort((a, b) => b.frequency - a.frequency);
  const [top, ...rest] = freqs as [ActionFrequency, ...ActionFrequency[]];
  const pct = rangePercent(range.hands).toFixed(1);
  const inRange = f > 0;
  const where = `range de open do ${s.spot.heroPosition} (${pct}% das mãos · ${source.label})`;
  const explanation = !inRange
    ? `${s.hero.hand} não está no ${where}.`
    : f < 1
      ? `${s.hero.hand} é mão de fronteira (spot misto): raise ${Math.round(f * 100)}% / fold ${Math.round((1 - f) * 100)}% no ${where}. As duas ações são aceitas.`
      : `${s.hero.hand} está no ${where}.`;
  return {
    recommended: top.action,
    frequency: top.frequency,
    alternatives: rest.filter((a) => a.frequency > 0),
    explanation,
    range,
    source,
    ...(top.betSize ? { recommendedBetSize: top.betSize } : {}),
  };
}
