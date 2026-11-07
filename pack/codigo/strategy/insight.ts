/**
 * "Por quê" de cada mão: EV de cada ação, onde a mão do herói fica em relação à fronteira do range,
 * mãos vizinhas na fronteira e o confronto (equity quando pagam, fold equity, equity necessária).
 * Tudo derivado da mesma solução que decidiu a mão; nada é inventado.
 */
import { ALL_HANDS, combos, TOTAL_COMBOS, type HandKey } from "@/domain/cards";
import { tablePositions, type Position } from "@/domain/positions";
import type { DecisionAction, TrainingScenario } from "@/domain/scenario";
import { equityMatrix, N_HANDS, pairWeights } from "./equity/preflop-equity";
import { openerPrior, pushFoldView } from "./providers/push-fold";
import { OPEN_PRIORITY } from "./ranges/reference-data";
import { rangePercent } from "./ranges/stats";
import type { StrategyDecision } from "./types";

export interface ActionEv { action: DecisionAction; ev: number }
export interface Neighbor { hand: HandKey; ev: number | null; frequency: number }

export interface HandInsight {
  hand: HandKey;
  /** Ação "de entrada" do spot (raise, shove ou call). */
  action: DecisionAction;
  unit: "bb" | "pct" | null;
  /** EV de cada ação relativo ao fold (null quando a fonte é um range de referência sem EV). */
  evs: ActionEv[] | null;
  /** EV de cada uma das 169 mãos para a ação de entrada (para a matriz). */
  handEvs: Record<HandKey, number> | null;
  rangePct: number;
  heroFrequency: number;
  /** % das mãos melhores que a do herói na ordem deste range (0 = a melhor). */
  heroTopPct: number;
  /** Distância até a fronteira, em % das mãos (positivo = dentro do range). */
  marginPct: number;
  zone: "dentro" | "fronteira" | "fora";
  /** Últimas mãos que entram e primeiras que ficam de fora. */
  lastIn: Neighbor[];
  firstOut: Neighbor[];
  matchup: ShoveMatchup | CallMatchup | null;
  /** Frases prontas para o painel. */
  lines: string[];
}
export interface ShoveMatchup {
  kind: "shove";
  /** Chance de todos foldarem (com remoção de cartas da sua mão; independência entre adversários). */
  foldAll: number;
  callers: { position: Position; callPct: number; equity: number }[];
}
export interface CallMatchup {
  kind: "call";
  shover: Position;
  shovePct: number;
  equity: number;
  /** Equity mínima para o call ser +EV no modelo (já com ICM/bounty). */
  breakeven: number;
  /** Pot odds só em fichas (sem ICM, sem bounty), heads-up. */
  potOdds?: number;
  /** breakeven − potOdds: positivo = risk premium (ICM/coberto); negativo = equity drop (bounty). */
  riskPremium?: number;
}

const BORDER_PCT = 2;
const pctTxt = (v: number, d = 1) => `${v.toFixed(d).replace(".", ",")}%`;
export function fmtEvValue(ev: number, unit: "bb" | "pct"): string {
  const v = Math.abs(ev) < 0.005 ? "0,00" : `${ev > 0 ? "+" : "−"}${Math.abs(ev).toFixed(2).replace(".", ",")}`;
  return unit === "bb" ? `${v} bb` : `${v}% do prize pool`;
}
const ACTION_PT: Partial<Record<DecisionAction, string>> = { fold: "Fold", call: "Call", raise: "Raise", all_in: "Shove", three_bet: "3Bet", four_bet: "4Bet" };

/** Probabilidade de pagar e equity contra o range de call, dado o range anterior (prior) e a mão do herói. */
function versus(h: number, prior: ArrayLike<number>, act: ArrayLike<number>) {
  const W = pairWeights(), EQ = equityMatrix();
  let den = 0, num = 0, eqNum = 0;
  for (let k = 0; k < N_HANDS; k++) {
    const w = W[h * N_HANDS + k]!;
    if (!w) continue;
    const p = w * Number(prior[k] ?? 1);
    den += p;
    const c = p * Number(act[k] ?? 0);
    num += c;
    eqNum += c * EQ[h * N_HANDS + k]!;
  }
  return { prob: den > 0 ? num / den : 0, equity: num > 0 ? eqNum / num : 0.5 };
}

export function handInsight(s: TrainingScenario, d: StrategyDecision): HandInsight {
  const hand = s.hero.hand;
  const h = ALL_HANDS.indexOf(hand);
  const range = d.range.hands;
  const pushFold = d.actionEvs !== undefined && (s.spot.type === "open_shove" || s.spot.type === "vs_open_shove" || s.spot.type === "3bet_shove");
  const action: DecisionAction = s.spot.type === "vs_open_shove" || s.spot.type === "limp_call" || s.spot.type === "vs_open" || s.spot.type === "vs_3bet" ? "call" : s.spot.type === "open_raise" || s.spot.type === "limp" || s.spot.type === "vs_limp" ? "raise" : "all_in";
  const view = pushFold ? pushFoldView(s) : null;
  const unit = view ? view.solution.unit : null;
  let evArr: Float64Array | null = null;
  if (view) {
    const sol = view.solution;
    evArr = s.spot.type === "vs_open_shove" ? sol.callers.find((c) => c.seat === s.table.heroSeat)!.callEv : sol.pushEv;
  }
  const handEvs = evArr ? Object.fromEntries(ALL_HANDS.map((x, i) => [x, evArr![i]!])) as Record<HandKey, number> : null;

  // Ordem do range: frequência e, no empate, EV (solver) ou a prioridade de open (referência).
  const prio = new Map(OPEN_PRIORITY.map((x, i) => [x, i]));
  const order = [...ALL_HANDS].sort((a, b) => {
    const fa = range[a] ?? 0, fb = range[b] ?? 0;
    if (fa !== fb) return fb - fa;
    if (handEvs) return handEvs[b]! - handEvs[a]!;
    return (prio.get(a) ?? 999) - (prio.get(b) ?? 999);
  });
  const rangePct = rangePercent(range);
  const heroFrequency = range[hand] ?? 0;
  let before = 0;
  for (const x of order) { if (x === hand) break; before += combos(x); }
  const heroTopPct = (before / TOTAL_COMBOS) * 100;
  const afterPct = ((before + combos(hand)) / TOTAL_COMBOS) * 100;
  const marginPct = heroFrequency > 0 ? rangePct - heroTopPct - (afterPct - heroTopPct) * (1 - heroFrequency) : rangePct - heroTopPct;
  const zone = heroFrequency > 0 && heroFrequency < 1 ? "fronteira" : Math.abs(marginPct) < BORDER_PCT || (heroFrequency > 0 && marginPct < BORDER_PCT) ? "fronteira" : heroFrequency > 0 ? "dentro" : "fora";
  const nb = (x: HandKey): Neighbor => ({ hand: x, ev: handEvs ? handEvs[x]! : null, frequency: range[x] ?? 0 });
  const inList = order.filter((x) => (range[x] ?? 0) > 0);
  const outList = order.filter((x) => (range[x] ?? 0) === 0);
  const lastIn = inList.slice(-3).map(nb);
  const firstOut = outList.slice(0, 3).map(nb);

  const evs: ActionEv[] | null = d.actionEvs ?? null;

  let matchup: HandInsight["matchup"] = null;
  if (view) {
    const t = s.table;
    const sol = view.solution;
    const order6 = tablePositions(t.size);
    if (s.spot.type === "vs_open_shove") {
      const shover = s.spot.aggressors[0]!;
      const eqs = Float64Array.from({ length: N_HANDS }, (_, i) => versus(i, [], sol.push).equity);
      // EV(call) é linear na equity contra o range de shove: o ponto de equilíbrio sai da reta.
      let sx = 0, sy = 0, sxx = 0, sxy = 0;
      for (let i = 0; i < N_HANDS; i++) { const x = eqs[i]!, y = evArr![i]!; sx += x; sy += y; sxx += x * x; sxy += x * y; }
      const a = (N_HANDS * sxy - sx * sy) / (N_HANDS * sxx - sx * sx), b = (sy - a * sx) / N_HANDS;
      matchup = { kind: "call", shover, shovePct: rangePercent(Object.fromEntries(ALL_HANDS.map((x, i) => [x, sol.push[i]!]))), equity: eqs[h]!, breakeven: a > 0 ? -b / a : 1 };
    } else {
      const openerSeat = s.spot.type === "3bet_shove" ? order6.indexOf(s.spot.aggressors[0]!) : -1;
      const prior = openerSeat >= 0 ? view.opener?.prior ?? openerPrior(t, s.context, openerSeat) : null;
      const callers = sol.callers.map((c) => {
        const pr = c.seat === openerSeat && prior ? prior : [];
        const v = versus(h, pr, c.call);
        return { position: t.players[c.seat]!.position, callPct: v.prob * 100, equity: v.equity };
      });
      matchup = { kind: "shove", foldAll: callers.reduce((p, c) => p * (1 - c.callPct / 100), 1), callers };
    }
  }

  const lines: string[] = [];
  const verb = s.spot.type === "vs_open" || s.spot.type === "vs_3bet" ? "Continuar" : ACTION_PT[action] ?? action;
  if (evs && unit) {
    const sorted = [...evs].sort((a, b) => b.ev - a.ev);
    const best = sorted[0]!, second = sorted[1];
    const diff = second ? best.ev - second.ev : Math.abs(best.ev);
    lines.push(diff < (unit === "bb" ? 0.05 : 0.01)
      ? `${hand} é praticamente indiferente aqui: ${ACTION_PT[best.action] ?? best.action}${second ? ` e ${ACTION_PT[second.action] ?? second.action}` : ""} têm quase o mesmo EV.`
      : `${ACTION_PT[best.action] ?? best.action} é a melhor ação com ${hand}: ${sorted.length > 2 ? `a segunda melhor (${ACTION_PT[second!.action] ?? second!.action})` : "a outra opção"} custa ${fmtEvValue(diff, unit).replace(/^[+−]/, "")}.`);
  }
  const posTxt = heroFrequency > 0
    ? `${hand} está entre as ${pctTxt(afterPct)} melhores mãos para ${verb.toLowerCase()} neste spot, e o range vai até ${pctTxt(rangePct)}`
    : `${hand} fica fora: o range de ${verb.toLowerCase()} vai até ${pctTxt(rangePct)} e esta mão só entraria com ${pctTxt(afterPct)}`;
  lines.push(`${posTxt}${zone === "fronteira" ? " (mão de fronteira)." : zone === "dentro" ? ` (folga de ${pctTxt(marginPct)}).` : ` (faltam ${pctTxt(-marginPct)}).`}`);
  if (matchup?.kind === "shove") {
    const cs = matchup.callers.filter((c) => c.callPct >= 0.5);
    lines.push(`Todos foldam ${pctTxt(matchup.foldAll * 100, 0)} das vezes.${cs.length ? ` Quando pagam: ${cs.map((c) => `${c.position} paga ${pctTxt(c.callPct, 0)} e você tem ${pctTxt(c.equity * 100, 0)} de equity`).join("; ")}.` : ""}`);
  }
  // Decomposição do EV do shove (chip EV, open shove): o que vem do fold de todos e o que vem quando pagam.
  if (matchup?.kind === "shove" && evs && unit === "bb" && s.spot.type === "open_shove" && (s.context.mode ?? "chip_ev") === "chip_ev") {
    const t = s.table;
    const pot = t.blinds.sb + t.blinds.bb + (t.blinds.anteType === "bb-ante" ? t.blinds.ante : 0);
    const total = evs.find((e) => e.action === "all_in")?.ev ?? 0;
    const steal = matchup.foldAll * pot;
    const called = total - steal;
    const n = (v: number) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(2).replace(".", ",")}`;
    lines.push(`Conta do shove: todos foldam ${pctTxt(matchup.foldAll * 100, 0)} × pote de ${pot.toFixed(1).replace(".", ",")}bb = ${n(steal)}bb; quando pagam (${pctTxt((1 - matchup.foldAll) * 100, 0)}), o all-in vale ${n(called)}bb no total. EV = ${n(total)}bb.`);
  }
  if (matchup?.kind === "call") {
    const extra = s.context.mode === "icm" ? " (já com a pressão do ICM)" : s.context.mode === "pko" || s.context.mode === "pko_icm" ? " (já com o bounty)" : "";
    if (view) {
      const t = s.table;
      const blindOf = (p: Position) => (p === "SB" ? t.blinds.sb : p === "BB" ? t.blinds.bb : 0);
      const eff = view.solution.callers.find((c) => c.seat === t.heroSeat)?.effective ?? 0;
      const dead = t.blinds.sb + t.blinds.bb + (t.blinds.anteType === "bb-ante" ? t.blinds.ante : 0) - blindOf(matchup.shover) - blindOf(s.spot.heroPosition);
      const call = eff - blindOf(s.spot.heroPosition);
      const potAfter = dead + 2 * eff;
      if (call > 0 && potAfter > 0) {
        const odds = call / potAfter;
        matchup.potOdds = odds;
        const chip = (s.context.mode ?? "chip_ev") === "chip_ev";
        lines.push(`Pot odds${chip ? "" : " em fichas"}: você paga ${call.toFixed(1).replace(".", ",")}bb para disputar um pote de ${potAfter.toFixed(1).replace(".", ",")}bb → precisa de ${pctTxt(odds * 100)} de equity se ninguém mais entrar.`);
        if (!chip) {
          // Diferença entre a equity mínima do modelo (ICM/bounty) e as pot odds em fichas.
          const rp = matchup.breakeven - odds;
          matchup.riskPremium = rp;
          const pts = `${Math.abs(rp * 100).toFixed(1).replace(".", ",")} pontos`;
          const icm = s.context.mode === "icm" || s.context.mode === "pko_icm";
          const bounty = s.context.mode === "pko" || s.context.mode === "pko_icm";
          if (Math.abs(rp) < 0.005) lines.push(`${icm ? "ICM" : "Bounty"} quase não muda a conta aqui: a equity mínima fica praticamente nas pot odds.`);
          else if (rp > 0) lines.push(`Risk premium de +${pts}: ${icm ? "com o ICM" : "sendo coberto"}, o call precisa de ${pctTxt(matchup.breakeven * 100)} em vez de ${pctTxt(odds * 100)}${icm ? " (as fichas que você perde valem mais do que as que ganha)" : ""}.`);
          else lines.push(`Desconto (equity drop) de ${pts}${bounty ? " pelo bounty de quem você cobre" : ""}: o call precisa de só ${pctTxt(matchup.breakeven * 100)} em vez de ${pctTxt(odds * 100)}.`);
        }
      }
    }
    lines.push(`O ${matchup.shover} empurra ${pctTxt(matchup.shovePct)} das mãos. Contra esse range, ${hand} tem ${pctTxt(matchup.equity * 100)} de equity e o call precisa de ${pctTxt(matchup.breakeven * 100)}${extra}.`);
  }
  if (d.source.id === "solver") { if (!evs) lines.push(`Solver pré-flop NVT: frequências do equilíbrio (este nó não traz EV por mão).`); }
  else if (!evs && (s.spot.type === "vs_open" || s.spot.type === "vs_3bet")) lines.push(`Referência aproximada (não solver): a ordem acima é das mãos que continuam (3bet/4bet, call ou all-in) contra o ${s.spot.type === "vs_open" ? "open" : "3bet"} do ${s.spot.aggressors[0]}.`);
  else if (!evs) lines.push(d.source.id === "nvt_team"
    ? `Tabela NVT do time (${s.spot.type === "open_raise" ? "open raise" : "shove PKO"}): sem EV por mão. A posição na ordem de entrada mostra o quanto a mão está perto do limite.`
    : "Range de referência (open raise): sem EV por mão. A posição na ordem de entrada mostra o quanto a mão está perto do limite.");
  return { hand, action, unit, evs, handEvs, rangePct, heroFrequency, heroTopPct, marginPct, zone, lastIn, firstOut, matchup, lines };
}

/** Quanto custou a ação escolhida contra a melhor (null sem EV ou sem resposta). */
export function evLossOf(d: StrategyDecision, chosen: DecisionAction | null): number | null {
  if (!d.actionEvs || !chosen) return null;
  if (d.outsideDrill) return 0;
  const pick = d.actionEvs.find((e) => e.action === chosen);
  if (!pick) return null;
  return Math.max(0, Math.max(...d.actionEvs.map((e) => e.ev)) - pick.ev);
}
