/**
 * Blind War com limp: tabela NVT da SB 25bb (todos foldaram até a SB). Fallback: onde o HRC tem a situação
 * (chip EV 25bb e ICM 25bb por fase/stacks), quem responde é o provider do solver com os ranges do HRC (hrc-limp.ts).
 * Etapa 1 (spot "limp"): Raise 2,5x ou Limp (a tabela não tem fold: 100% raise ou limp).
 * Etapa 2 (spot "limp_call"): a SB completou e o BB deu iso-raise → Call, Jam ou Fold.
 */
import { ALL_HANDS, combos, type HandKey } from "@/domain/cards";
import { pairRisk, playerValues } from "@/icm/engine";
import { OPEN_PRIORITY } from "../ranges/reference-data";
import { icmContext, icmStacks } from "./icm-preflop";
import { BB_ISO_SIZE, type DecisionAction } from "@/domain/scenario";
import { NVT_TEAM_VERSION, sbLimpCode } from "../ranges/nvt-charts";
import { rangePercent } from "../ranges/stats";
import { rangeId, type RangeDefinition } from "../ranges/types";
import type { ActionFrequency, StrategyDecision, StrategyProvider } from "../types";

const SOURCE = { id: "nvt_team" as const, label: "Tabela NVT (time) · SB 25bb", version: NVT_TEAM_VERSION };
const PLAN: Record<string, string> = { R: "Raise 2,5x", k: "Limp/Call", j: "Limp/Jam", f: "Limp/Fold" };

const handsWith = (codes: string[]): Record<HandKey, number> =>
  Object.fromEntries(ALL_HANDS.filter((h) => codes.includes(sbLimpCode(h))).map((h) => [h, 1]));

export const sbLimpProvider: StrategyProvider = {
  source: SOURCE,
  supports: (spot) => spot === "limp" || spot === "limp_call",
  decide(s): StrategyDecision | null {
    if (s.context.mode && s.context.mode !== "chip_ev" && s.context.mode !== "icm" && s.context.mode !== "pko_icm") return null;
    if (s.context.format === "bounty" || s.context.stack !== 25 || s.spot.heroPosition !== "SB") return null;
    const ic = icmContext(s);
    if (ic) return icmDecision(s, ic);
    const code = sbLimpCode(s.hero.hand);
    const hand = s.hero.hand;
    let action: DecisionAction;
    let range: RangeDefinition;
    let explanation: string;
    const pct = (codes: string[]) => rangePercent(handsWith(codes)).toFixed(1).replace(".", ",");
    if (s.spot.type === "limp") {
      action = code === "R" ? "raise" : "limp";
      range = { id: `${rangeId("limp", s.context, "SB")}|nvt-sb25`, spot: "limp", action: "raise", position: "SB", context: s.context, hands: handsWith(["R"]), source: "nvt_team", version: NVT_TEAM_VERSION, notes: "Range de raise 2,5x da SB 25bb; o resto da tabela é limp." };
      explanation = code === "R"
        ? `${hand}: Raise 2,5x na tabela da SB 25bb (raise com ${pct(["R"])}% das mãos; o resto é limp).`
        : `${hand}: Limp na tabela da SB 25bb (plano: ${PLAN[code]}${code === "k" ? " — se o BB aumentar, pague" : code === "j" ? " — se o BB aumentar, vá all-in" : " — se o BB aumentar, desista"}). A SB limpa ${pct(["k", "j", "f"])}% e dá raise em ${pct(["R"])}%.`;
    } else {
      if (code === "R" || code === ".") return null; // essas mãos nunca completam (o gerador não as entrega aqui)
      action = code === "k" ? "call" : code === "j" ? "all_in" : "fold";
      range = { id: `${rangeId("limp_call", s.context, "SB")}|nvt-sb25`, spot: "limp_call", action: action === "fold" ? "call" : action, position: "SB", context: s.context, hands: handsWith(code === "f" ? ["k"] : [code]), source: "nvt_team", version: NVT_TEAM_VERSION, notes: "Resposta da SB ao iso-raise do BB depois do limp." };
      explanation = `${hand}: ${action === "call" ? "Call" : action === "all_in" ? "Jam (all-in)" : "Fold"} contra o iso-raise do BB para ${String(BB_ISO_SIZE).replace(".", ",")}bb (plano da tabela: ${PLAN[code]}). Das mãos que limpam, a SB paga ${pct(["k"])}%, dá jam com ${pct(["j"])}% e folda ${pct(["f"])}% (em % de todas as mãos).`;
    }
    const freqs: ActionFrequency[] = [{ action, frequency: 1 }];
    return { recommended: action, frequency: 1, alternatives: freqs.slice(1), explanation, range, source: SOURCE, theoryTags: ["nvt_team", "blind_war", "limp"] };
  },
};

/**
 * Blind War com ICM (referência calibrada sobre a tabela NVT da SB 25bb):
 * - raise × limp: a parte de raise cresce ou encolhe pela risk advantage da SB contra o BB
 *   (×exp(3,8 × vantagem), como no open com ICM); as mãos que saem do raise viram limp e vice-versa;
 * - vs iso: as mãos que continuam (call/jam) perdem as mais fracas na proporção do risk premium da SB
 *   contra o BB (2× o RP, até 60%); com desconto de bounty, as melhores mãos de fold passam a pagar.
 */
function icmDecision(s: Parameters<StrategyProvider["decide"]>[0], ic: NonNullable<ReturnType<typeof icmContext>>): StrategyDecision | null {
  const t = s.table;
  const sb = t.heroSeat;
  const bb = t.players.find((p) => p.position === "BB")!.seat;
  const stacks = icmStacks(t, ic.others);
  const base = playerValues(stacks, ic.prizes, ic.pko);
  const heroRp = pairRisk(stacks, ic.prizes, sb, bb, base, ic.pko).riskPremium;
  const bbRp = pairRisk(stacks, ic.prizes, bb, sb, base, ic.pko).riskPremium;
  const hand = s.hero.hand;
  const code = sbLimpCode(hand);
  const order = OPEN_PRIORITY;
  const sg = (v: number) => `${v < 0 ? "−" : "+"}${Math.abs(v * 100).toFixed(1).replace(".", ",")}%`;
  const icmTxt = ` ICM: seu risk premium contra o BB é ${sg(heroRp)} e o dele contra você ${sg(bbRp)}${ic.pko ? " (com bounty)" : ""}. Referência calibrada sobre a tabela NVT da SB 25bb, não solver.`;
  const comboPct = (set: Set<HandKey>) => (([...set].reduce((a, h) => a + combos(h), 0)) / 1326 * 100).toFixed(1).replace(".", ",");
  if (s.spot.type === "limp") {
    const raise = order.filter((h) => sbLimpCode(h) === "R");
    const limp = order.filter((h) => ["k", "j", "f"].includes(sbLimpCode(h)));
    const mult = Math.min(1.8, Math.max(0.4, Math.exp(3.8 * (bbRp - heroRp))));
    const baseCombos = raise.reduce((a, h) => a + combos(h), 0);
    const target = baseCombos * mult;
    const newRaise = new Set<HandKey>();
    let acc = 0;
    for (const h of [...raise, ...limp]) { if (acc >= target - 1e-9) break; newRaise.add(h); acc += combos(h); }
    const action: DecisionAction = newRaise.has(hand) ? "raise" : "limp";
    const range: RangeDefinition = { id: `${rangeId("limp", s.context, "SB")}|nvt-sb25|icm`, spot: "limp", action: "raise", position: "SB", context: s.context, hands: Object.fromEntries([...newRaise].map((h) => [h, 1])), source: ic.pko ? "pko" : "icm", version: NVT_TEAM_VERSION, notes: "Raise da SB 25bb ajustado pelo ICM; o resto é limp." };
    const moved = code === "R" && action === "limp" ? " Na tabela sem ICM esta mão daria raise; com a pressão de ICM ela vai de limp." : code !== "R" && action === "raise" ? " Na tabela sem ICM esta mão limparia; com a vantagem de risco ela vai de raise." : "";
    const explanation = `${hand}: ${action === "raise" ? "Raise 2,5x" : "Limp"} (raise com ${comboPct(newRaise)}% das mãos com ICM; sem ICM ${(baseCombos / 1326 * 100).toFixed(1).replace(".", ",")}%).${moved}${icmTxt}`;
    return { recommended: action, frequency: 1, alternatives: [], explanation, range, source: { id: ic.pko ? "pko" : "icm", label: "Blind War com ICM (tabela NVT ajustada)", version: NVT_TEAM_VERSION }, theoryTags: ["icm", "blind_war", "limp"] };
  }
  if (code === "R" || code === ".") return null;
  const cont = order.filter((h) => ["k", "j"].includes(sbLimpCode(h)));
  const folds = order.filter((h) => sbLimpCode(h) === "f");
  const contCombos = cont.reduce((a, h) => a + combos(h), 0);
  const dropShare = heroRp > 0 ? Math.min(0.6, 2 * heroRp) : 0;
  const addShare = heroRp < 0 ? Math.min(0.6, -2 * heroRp) : 0;
  const keep = new Set<HandKey>();
  let acc = 0;
  for (const h of cont) { if (acc >= contCombos * (1 - dropShare) - 1e-9) break; keep.add(h); acc += combos(h); }
  const added = new Set<HandKey>();
  let acc2 = 0;
  for (const h of folds) { if (acc2 >= contCombos * addShare - 1e-9) break; added.add(h); acc2 += combos(h); }
  let action: DecisionAction;
  if (keep.has(hand)) action = code === "j" ? "all_in" : "call";
  else if (added.has(hand)) action = "call";
  else action = "fold";
  const range: RangeDefinition = { id: `${rangeId("limp_call", s.context, "SB")}|nvt-sb25|icm`, spot: "limp_call", action: "call", position: "SB", context: s.context, hands: Object.fromEntries([...keep, ...added].map((h) => [h, 1])), source: ic.pko ? "pko" : "icm", version: NVT_TEAM_VERSION, notes: "Mãos da SB que continuam contra o iso do BB, ajustadas pelo ICM." };
  const changed = (code === "k" || code === "j") && action === "fold" ? ` Sem ICM esta mão ${code === "j" ? "iria de jam" : "pagaria"}; com o risk premium contra o BB ela folda.` : code === "f" && action === "call" ? " Sem ICM esta mão foldaria; com o desconto do bounty ela paga." : "";
  const explanation = `${hand}: ${action === "call" ? "Call" : action === "all_in" ? "Jam (all-in)" : "Fold"} contra o iso-raise do BB para ${String(BB_ISO_SIZE).replace(".", ",")}bb (plano da tabela sem ICM: ${PLAN[code]}).${changed} Com ICM continuam ${comboPct(new Set([...keep, ...added]))}% das mãos (sem ICM, ${(contCombos / 1326 * 100).toFixed(1).replace(".", ",")}%).${icmTxt}`;
  return { recommended: action, frequency: 1, alternatives: [], explanation, range, source: { id: ic.pko ? "pko" : "icm", label: "Blind War com ICM (tabela NVT ajustada)", version: NVT_TEAM_VERSION }, theoryTags: ["icm", "blind_war", "limp"] };
}
