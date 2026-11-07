/**
 * Shove PKO pelas tabelas do time (NVT): a cor de cada mão vira decisão conforme o tamanho do KO.
 *
 * Decisões tomadas (sem dado nas imagens, ver nvt-charts.ts):
 * - Stack: as tabelas batem com o Nash de ~15–17bb → valem no stack 15bb do trainer.
 * - "KO" = peso do bounty na mão, medido como o bounty (metade em dinheiro, convertida em fichas pelo
 *   stack inicial em BBs atuais) dividido pelo stack efetivo. É o seu bounty que faz quem te cobre pagar
 *   mais largo; por isso "fold KO alto" = com a sua cabeça valendo muito, aperte.
 *   Faixas: baixo < 40% do stack · normal 40–60% · alto 60–100% · muito alto > 100%.
 *   Calibradas nos cenários PKO do trainer: no middle a mediana é ~48% (normal); no early, com o stack
 *   inicial valendo 25bb, 15bb de stack carregam um bounty quase do tamanho do stack (muito alto).
 * - "Shove KO muito alto" (só na SB) olha o bounty do BB quando você o cobre: vale a pena caçar.
 * - "Exploit" e "Limp exploit": não são cobrados. Exploit com KO baixo = as duas ações aceitas;
 *   limp não existe no modelo shove/fold, então essas mãos contam como fold.
 */
import type { DecisionAction } from "@/domain/scenario";
import { PKO_CASH_SHARE } from "@/domain/tournament";
import type { PlayerState } from "@/domain/table";
import { chartCodes, NVT_CHARTS, NVT_TEAM_VERSION } from "../ranges/nvt-charts";
import { rangePercent } from "../ranges/stats";
import { rangeId, type RangeDefinition } from "../ranges/types";
import type { ActionFrequency, StrategyDecision, StrategyProvider } from "../types";
import { pushFoldView } from "./push-fold";

export type KoLevel = "baixo" | "normal" | "alto" | "muito_alto";
export const KO_LEVEL_PT: Record<KoLevel, string> = { baixo: "KO baixo", normal: "KO normal", alto: "KO alto", muito_alto: "KO muito alto" };
export const NVT_PKO_STACK = 15;

/** Faixa do KO pelo peso do bounty (em fichas) em relação ao stack. */
export function koLevel(bountyBb: number, stackBb: number): KoLevel {
  const r = stackBb > 0 ? bountyBb / stackBb : 0;
  return r < 0.4 ? "baixo" : r < 0.6 ? "normal" : r <= 1 ? "alto" : "muito_alto";
}

/** Bounty de um jogador em BBs (só a metade paga em dinheiro na hora). */
export const bountyBb = (p: PlayerState, startStackBb: number) => (p.bountyMultiplier ?? 1) * startStackBb * PKO_CASH_SHARE;

/** Frequência de shove de cada código da tabela, para o KO da mão. */
export function codeFrequency(code: string, hero: KoLevel, bbVictim: KoLevel | null): number {
  switch (code) {
    case "S": return 1;
    case "r": return hero === "baixo" ? 1 : 0;
    case "x": return hero === "baixo" ? 0.5 : 0;
    case "c": return hero === "alto" || hero === "muito_alto" ? 0 : 1;
    case "b": return hero === "muito_alto" ? 0 : 1;
    case "y": return bbVictim === "muito_alto" ? 1 : 0;
    default: return 0; // "." e "l" (limp exploit)
  }
}

const SOURCE = { id: "nvt_team" as const, label: "Tabela NVT (time) · Shove PKO", version: NVT_TEAM_VERSION };

export const pkoTeamProvider: StrategyProvider = {
  source: SOURCE,
  supports: (spot) => spot === "open_shove",
  decide(s): StrategyDecision | null {
    if (s.context.mode !== "pko" || s.context.format !== "pko" || s.context.stack !== NVT_PKO_STACK) return null;
    const unit = s.tournament.startingStackBb;
    if (unit === undefined) return null;
    const chart = NVT_CHARTS.find((c) => c.group === "pko_shove" && c.positions.includes(s.spot.heroPosition));
    if (!chart) return null;
    const t = s.table;
    const hero = t.players[t.heroSeat]!;
    const level = koLevel(bountyBb(hero, unit), hero.stackBb);
    const bb = t.players.find((p) => p.position === "BB");
    const victim = s.spot.heroPosition === "SB" && bb && hero.stackBb >= bb.stackBb ? koLevel(bountyBb(bb, unit), bb.stackBb) : null;
    const codes = chartCodes(chart);
    const hands: Record<string, number> = {};
    for (const [h, code] of Object.entries(codes)) { const f = codeFrequency(code, level, victim); if (f) hands[h] = f; }
    const range: RangeDefinition = {
      id: `${rangeId("open_shove", s.context, s.spot.heroPosition)}|nvt-${chart.id}|${level}`, spot: "open_shove", action: "all_in",
      position: s.spot.heroPosition, context: s.context, hands, source: "nvt_team", version: NVT_TEAM_VERSION,
      notes: "Tabela NVT de shove PKO (~15–17bb), ajustada pelo tamanho do KO.",
    };
    const f = hands[s.hero.hand] ?? 0;
    const freqs: ActionFrequency[] = [{ action: "all_in" as DecisionAction, frequency: f }, { action: "fold" as DecisionAction, frequency: 1 - f }].sort((a, b) => b.frequency - a.frequency);
    const [top, ...rest] = freqs as [ActionFrequency, ...ActionFrequency[]];
    const code = codes[s.hero.hand] ?? ".";
    const why: Record<string, string> = {
      S: "está no shove base da tabela", r: "entra só com KO baixo", x: "é exploit com KO baixo (as duas ações valem)",
      c: "sai com KO alto", b: "sai só com KO muito alto", y: "entra quando o bounty do BB é muito alto", l: "na tabela é limp (exploit); no modelo shove/fold conta como fold", ".": "não está na tabela",
    };
    // Comparação com o Nash (bounties reais da mesa), sem mudar a correção.
    let nash = "";
    try {
      const v = pushFoldView(s);
      nash = ` Nash PKO com os bounties desta mesa: shove ${v.heroEv >= 0 ? "+" : ""}${v.heroEv.toFixed(2)}bb vs fold (${rangePercent(v.heroRange.hands).toFixed(1)}% de shove).`;
    } catch { /* sem comparação */ }
    const ratio = Math.round((bountyBb(hero, unit) / hero.stackBb) * 100);
    return {
      recommended: top.action,
      frequency: top.frequency,
      alternatives: rest.filter((a) => a.frequency > 0),
      explanation: `${s.hero.hand} ${why[code] ?? why["."]}. Seu bounty vale ~${ratio}% do seu stack → ${KO_LEVEL_PT[level]}${victim ? `; bounty do BB: ${KO_LEVEL_PT[victim]}` : ""}. Range de shove do ${s.spot.heroPosition} aqui: ${rangePercent(hands).toFixed(1)}% (tabela ${chart.label}).${nash}`,
      range,
      source: SOURCE,
      theoryTags: ["nvt_team", "pko", "push_fold"],
    };
  },
};
