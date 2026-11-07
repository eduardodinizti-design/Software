/**
 * Open com stack curto (15bb): estratégia mista raise + shove (Reg Life, RFI 15bb).
 * O raise vem da fonte de open (tabela NVT, range personalizado ou referência); o shove vem do
 * Nash push/fold calculado na mesma mesa. As duas ações são aceitas quando cada fonte a joga.
 */
import { OPEN_SHOVE_MAX_STACK, type DecisionAction, type TrainingScenario } from "@/domain/scenario";
import type { ActionFrequency, StrategyDecision } from "../types";
import { pushFoldProvider } from "./push-fold";

const fmtBb = (v: number) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(2).replace(".", ",")}bb`;

export function withOpenShove(s: TrainingScenario, d: StrategyDecision): StrategyDecision {
  if (s.spot.type !== "open_raise" || !s.legalActions.includes("all_in") || s.legalActions.includes("limp") || s.context.stack > OPEN_SHOVE_MAX_STACK) return d;
  if (s.context.mode && s.context.mode !== "chip_ev" && s.context.mode !== "icm") return d;
  let shove: StrategyDecision | null = null;
  try {
    shove = pushFoldProvider.decide({ ...s, spot: { ...s.spot, type: "open_shove" }, legalActions: ["fold", "all_in"] });
  } catch {
    return d;
  }
  if (!shove) return d;
  const all = [{ action: d.recommended, frequency: d.frequency }, ...d.alternatives];
  const raise = all.find((a) => a.action === "raise")?.frequency ?? 0;
  const push = shove.range.hands[s.hero.hand] ?? 0;
  const ev = shove.actionEvs?.find((a) => a.action === "all_in")?.ev ?? 0;
  // Frequências exibidas: raise (fonte de open) e shove (Nash) aceitos; fold só se nenhuma das duas joga a mão inteira.
  const fold = 1 - Math.max(raise, push);
  const total = raise + push + fold || 1;
  const order: DecisionAction[] = ["raise", "all_in", "fold"];
  const freqs: ActionFrequency[] = ([
    { action: "raise", frequency: raise / total, ...(d.recommendedBetSize ? { betSize: d.recommendedBetSize } : {}) },
    { action: "all_in", frequency: push / total },
    { action: "fold", frequency: fold / total },
  ] as ActionFrequency[]).filter((a) => a.frequency > 0).sort((a, b) => b.frequency - a.frequency || order.indexOf(a.action) - order.indexOf(b.action));
  const [top, ...rest] = freqs as [ActionFrequency, ...ActionFrequency[]];
  const shoveTxt = push > 0
    ? ` Com ${s.context.stack}bb o open também pode ser all-in: ${s.hero.hand} está no range de shove Nash do ${s.spot.heroPosition} (${fmtBb(ev)} em relação ao fold), então Shove também é aceito.`
    : ` Com ${s.context.stack}bb existe open shove, mas ${s.hero.hand} não está no range de shove Nash do ${s.spot.heroPosition} (${fmtBb(ev)} em relação ao fold).`;
  const { recommendedBetSize, ...base } = d;
  return {
    ...base,
    recommended: top.action,
    frequency: top.frequency,
    ...(top.action === "raise" && recommendedBetSize ? { recommendedBetSize } : {}),
    alternatives: rest,
    explanation: `${d.explanation}${shoveTxt}`,
    theoryTags: [...(d.theoryTags ?? []), "open_shove_mix"],
  };
}
