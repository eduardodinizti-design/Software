/**
 * Spots de reação: Vs Open (fold / call / 3bet / all-in) e Vs 3Bet (fold / call / 4bet / all-in).
 *
 * Referência aproximada (não solver), montada com princípios de teoria e com a equity real das mãos:
 * - range do opener = tabela de open do time (ou a referência); range da 3bet = top X% (frequência por posição);
 * - call: equity contra o range do agressor × realização de equity (posição, stack, gente atrás) ≥ pot odds;
 * - 3bet/4bet: valor = as mãos com mais equity; blefe = bloqueadores e suited na borda do range;
 * - com 25bb ou menos, o all-in vem do Nash push/fold da mesa real (o mesmo do resteal), com EV calculado.
 * O time pode trocar por tabelas próprias quando tiver; a fonte fica identificada no feedback.
 */
import { ALL_HANDS, combos, TOTAL_COMBOS, type HandKey } from "@/domain/cards";
import { tablePositions, type Position } from "@/domain/positions";
import type { DecisionAction, TrainingScenario } from "@/domain/scenario";
import { equityMatrix, N_HANDS, pairWeights } from "../equity/preflop-equity";
import { solvePushFoldCached } from "../pushfold/nash";
import { pairRisk, playerValues } from "@/icm/engine";
import { icmContext, icmOpenRange, icmStacks } from "./icm-preflop";
import { openRangeFor } from "../ranges/open-range";
import { strengthOrder, topOfRange, topRange } from "../ranges/strength";
import { threeBetPct } from "../ranges/three-bet";
import type { RangeDefinition } from "../ranges/types";
import { rangeId } from "../ranges/types";
import type { ActionFrequency, StrategyDecision, StrategyProvider, StrategySourceInfo } from "../types";

export const REACTION_VERSION = "reaction-ref-1";
export const REACTION_SOURCE: StrategySourceInfo = { id: "nvt_range", label: "Referência aproximada (vs open / vs 3bet)", version: REACTION_VERSION };
const NOTE = "Referência aproximada: equity real contra o range do agressor, realização de equity por posição e stack e frequências típicas de 3bet. Não é solver; troque pelas tabelas do time quando existirem.";

type Mix = Partial<Record<DecisionAction, number>>;
export interface ReactionStrategy {
  /** Ação por mão (frequências somam 1). */
  mix: Record<HandKey, Mix>;
  /** Equity de cada mão contra o range do agressor. */
  eq: Float64Array;
  potOdds: number;
  /** Equity mínima para pagar já com a realização de equity. */
  need: number;
  realization: number;
  aggressorPct: number;
  /** % de todas as mãos em cada ação. */
  freqPct: Mix;
  /** EV do all-in (Nash) por mão, quando existe. */
  shoveEv: Float64Array | null;
  sizeLabel: string;
  roles: Record<HandKey, "valor" | "blefe" | "call" | "shove" | "fold">;
  /** Unidade do EV do all-in: bb (chip EV) ou % do prize pool (ICM). */
  evUnit: "bb" | "pct";
  /** ICM: risk premium do herói contra o opener e vice-versa, e quanto o range do opener mudou. */
  icm: { heroRp: number; theirRp: number; openerMult: number; extraNeed: number } | null;
}

/** Quanto do risk premium vira equity extra exigida para pagar um open (não é all-in: parte do stack). */
export const ICM_CALL_WEIGHT = 0.4;

/** Equity de cada uma das 169 mãos contra um range (remoção de cartas exata). */
function equityVs(range: ArrayLike<number>): Float64Array {
  const W = pairWeights(), EQ = equityMatrix();
  return Float64Array.from({ length: N_HANDS }, (_, h) => {
    let num = 0, den = 0;
    for (let k = 0; k < N_HANDS; k++) { const w = W[h * N_HANDS + k]! * Number(range[k] ?? 0); den += w; num += w * EQ[h * N_HANDS + k]!; }
    return den > 0 ? num / den : 0.5;
  });
}
const pctOf = (w: ArrayLike<number>) => (ALL_HANDS.reduce((t, h, i) => t + combos(h) * Number(w[i] ?? 0), 0) / TOTAL_COMBOS) * 100;
const blindOf = (p: Position) => (p === "SB" ? 0.5 : p === "BB" ? 1 : 0);
const potNow = (s: TrainingScenario) => s.table.actions.reduce((t, a) => t + a.amount, 0);

/** Pontuação de "bom blefe" (bloqueador de ás/rei, suited, conectores), para 3bet/4bet na borda. */
function bluffScore(h: HandKey, offsuitBlockers: boolean): number {
  const suited = h.endsWith("s"), pair = h.length === 2;
  if (pair) return 0;
  const [a, b] = [h[0]!, h[1]!];
  const low = "5432".includes(b);
  if (a === "A" && suited) return low ? 3 : 2.5;
  if (a === "K" && suited) return 2;
  if (suited && "T98765".includes(a) && Math.abs("AKQJT98765432".indexOf(a) - "AKQJT98765432".indexOf(b)) <= 2) return 1.5;
  if (offsuitBlockers && (a === "A" || a === "K") && !suited) return 1.2;
  return 0;
}

/**
 * Quanto da equity crua a mão costuma realizar em relação à média: pares e suited realizam mais
 * (flush, sequência, set), offsuit desconectadas realizam menos (dominadas, sem draws).
 */
export function playability(h: HandKey): number {
  if (h.length === 2) return 1;
  const R = "AKQJT98765432";
  const gap = Math.abs(R.indexOf(h[0]!) - R.indexOf(h[1]!));
  const connected = gap <= 2 && R.indexOf(h[1]!) <= R.indexOf("5");
  if (h.endsWith("s")) return connected ? 1.12 : 1.07;
  if (h[0] === "A" || h[0] === "K") return 0.93;
  return connected ? 0.93 : 0.86;
}

const cache = new Map<string, ReactionStrategy>();

/** Escolhe as mãos (por ordem) até completar `pct` % das combinações. */
function takeTop(order: HandKey[], pct: number, skip: Set<HandKey>): Set<HandKey> {
  const out = new Set<HandKey>();
  const target = (pct / 100) * TOTAL_COMBOS;
  let acc = 0;
  for (const h of order) {
    if (skip.has(h)) continue;
    if (acc >= target - 1e-9) break;
    out.add(h);
    acc += combos(h);
  }
  return out;
}

export function reactionStrategy(s: TrainingScenario): ReactionStrategy {
  const t = s.table;
  const hero = t.players[t.heroSeat]!;
  const aggPos = s.spot.aggressors[0]!;
  const agg = t.players.find((p) => p.position === aggPos)!;
  const S = s.context.stack;
  const key = `${s.scenarioId}`;
  const hit = cache.get(key);
  if (hit) return hit;

  const order = tablePositions(t.size);
  const heroPos = hero.position;
  const pot = potNow(s);
  const mix: Record<HandKey, Mix> = {};
  const roles: ReactionStrategy["roles"] = {};
  let shoveEv: Float64Array | null = null;
  let eq: Float64Array, potOdds: number, need: number, R: number, aggPct: number, sizeLabel: string;

  const ic = icmContext(s);
  const prizes = ic?.prizes ?? null;
  const pko = ic?.pko ?? null;
  const others = ic?.others ?? [];
  let icm: ReactionStrategy["icm"] = null;
  const riskPair = (a: number, b: number) => {
    const stacks = icmStacks(t, others);
    const base = playerValues(stacks, prizes!, pko);
    return { heroRp: pairRisk(stacks, prizes!, a, b, base, pko).riskPremium, theirRp: pairRisk(stacks, prizes!, b, a, base, pko).riskPremium };
  };
  if (s.spot.type === "vs_open") {
    let open = openRangeFor(s.context, aggPos).hands;
    if (prizes?.length) {
      // ICM: o opener abre com o range ajustado pela pressão dele (mesa no momento do open) e o herói
      // paga o risk premium contra o opener na equity exigida.
      const atOpen = { ...t, players: t.players.map((p) => ({ ...p, status: "active" as const })) };
      const op = icmOpenRange(s.context, atOpen, agg.seat, prizes, pko, others);
      open = op.range.hands;
      const { heroRp, theirRp } = riskPair(t.heroSeat, agg.seat);
      // Risk premium negativo (bounty de quem você cobre) vira desconto na equity exigida.
      icm = { heroRp, theirRp, openerMult: op.pressure.multiplier, extraNeed: heroRp * ICM_CALL_WEIGHT };
    }
    const O = Float64Array.from(ALL_HANDS, (h) => open[h] ?? 0);
    aggPct = pctOf(O);
    eq = equityVs(O);
    const openTotal = t.actions.filter((a) => a.seat === agg.seat).reduce((x, a) => x + a.amount, 0) + (aggPos === "SB" ? 0.5 : 0);
    const callAmt = openTotal - blindOf(heroPos);
    potOdds = callAmt / (pot + callAmt);
    const behind = order.length - 1 - order.indexOf(heroPos);
    // Realização média por papel e stack: BB fecha a ação (realiza mais que a SB); em posição realiza mais.
    const RB: Record<"bb" | "sb" | "ip", Record<number, number>> = { bb: { 100: 0.77, 40: 0.8, 25: 0.72, 15: 0.68 }, sb: { 100: 0.66, 40: 0.68, 25: 0.68, 15: 0.66 }, ip: { 100: 0.92, 40: 0.93, 25: 0.92, 15: 0.9 } };
    const role = heroPos === "BB" ? "bb" : heroPos === "SB" ? "sb" : "ip";
    R = Math.min(1, (RB[role][S] ?? RB[role][100]!) - (heroPos === "BB" ? 0 : behind * 0.025));
    need = potOdds / R + (icm?.extraNeed ?? 0);
    const byEq = [...ALL_HANDS].sort((a, b) => eq[ALL_HANDS.indexOf(b)]! - eq[ALL_HANDS.indexOf(a)]!);
    const defend = new Set(ALL_HANDS.filter((h) => eq[ALL_HANDS.indexOf(h)]! * playability(h) >= need));
    const who = heroPos === "SB" ? "sb" : heroPos === "BB" ? "bb" : "ip";
    const mult = S >= 100 ? { ip: 3.75, sb: 4.75, bb: 5.1 }[who] : S >= 40 ? { ip: 3.1, sb: 3.6, bb: 4.6 }[who] : { ip: 2.5, sb: 2.9, bb: 3.4 }[who];
    sizeLabel = S <= 15 ? "all-in" : `${(Math.round(openTotal * mult * 10) / 10).toString().replace(".", ",")}bb (${mult.toString().replace(".", ",")}x o open)`;
    // ICM: 3bet encolhe (a 4bet do opener custa caro) e fica mais polarizada.
    const t3 = threeBetPct(aggPos, heroPos) * (S >= 100 ? 1 : 1.1) * (icm ? Math.min(1.4, Math.max(0.35, 1 - 3 * icm.heroRp)) : 1);
    if (S >= 40) {
      const value = takeTop(byEq, t3 * 0.65, new Set());
      const minEq = need - 0.1;
      const bluffOrder = [...ALL_HANDS].filter((h) => !value.has(h) && eq[ALL_HANDS.indexOf(h)]! >= minEq && bluffScore(h, heroPos === "BB" && S <= 40) > 0)
        .sort((a, b) => bluffScore(b, heroPos === "BB" && S <= 40) - bluffScore(a, heroPos === "BB" && S <= 40) || eq[ALL_HANDS.indexOf(b)]! - eq[ALL_HANDS.indexOf(a)]!);
      const bluff = takeTop(bluffOrder, t3 * 0.35, new Set());
      for (const h of ALL_HANDS) {
        if (value.has(h)) { mix[h] = { three_bet: 1 }; roles[h] = "valor"; }
        else if (bluff.has(h)) { mix[h] = { three_bet: 1 }; roles[h] = "blefe"; }
        else if (defend.has(h)) { mix[h] = { call: 1 }; roles[h] = "call"; }
        else { mix[h] = { fold: 1 }; roles[h] = "fold"; }
      }
    } else {
      // 25bb e 15bb: all-in pelo Nash da mesa real (opener com o open dele investido), o resto call/fold.
      const opener = order.indexOf(aggPos);
      const heroSeat = t.heroSeat;
      const seats = [
        ...t.players.map((p) => ({ stack: p.stackBb, blind: p.position === "SB" ? t.blinds.sb : p.position === "BB" ? t.blinds.bb : 0, ante: p.position === "BB" ? t.blinds.ante : 0, ...(p.seat === opener ? { invested: openTotal } : {}) })),
        ...(prizes?.length ? others.map((stack) => ({ stack, blind: 0, ante: 0 })) : []),
      ];
      const behindSeats = t.players.filter((p) => p.seat > heroSeat).map((p) => p.seat);
      const sol = solvePushFoldCached({ seats, pusher: heroSeat, callers: [...behindSeats, opener], priors: { [opener]: O }, foldWinner: opener, ...(prizes?.length ? { payouts: prizes } : {}), ...(pko ? { bounties: { heads: pko.heads, cashShare: pko.cashShare } } : {}) });
      shoveEv = sol.pushEv;
      const top = S <= 25 && S > 15 ? takeTop(byEq, 2.5, new Set()) : new Set<HandKey>();
      const canCall = S > 15 || heroPos === "SB" || heroPos === "BB";
      // EV do call (aproximado: equity × realização × pote − preço, menos o risk premium no ICM) na mesma
      // unidade do shove; com ICM, bb → % do prize pool pelo valor marginal da ficha do herói.
      let bbToUnit = 1;
      if (sol.unit === "pct" && prizes?.length) {
        const st0 = icmStacks(t, others);
        const up = [...st0]; up[heroSeat]! += 1; const dn = [...st0]; dn[heroSeat]! -= 1;
        const pool = prizes.reduce((a, b) => a + b, 0);
        bbToUnit = ((playerValues(up, prizes, pko)[heroSeat]! - playerValues(dn, prizes, pko)[heroSeat]!) / 2 / pool) * 100;
      }
      const eps = 0.05 * bbToUnit;
      for (const h of ALL_HANDS) {
        const i = ALL_HANDS.indexOf(h);
        if (top.has(h)) { mix[h] = sol.push[i]! > 0 ? { three_bet: 0.5, all_in: 0.5 } : { three_bet: 1 }; roles[h] = "valor"; continue; }
        const evJam = sol.pushEv[i]!;
        const eqEff = eq[i]! * playability(h) - (icm?.extraNeed ?? 0) * R;
        const evCall = canCall ? (R * eqEff * (pot + callAmt) - callAmt) * bbToUnit : -Infinity;
        const best = Math.max(0, evJam, evCall);
        const m: Mix = {};
        if (best <= eps && evJam < eps && evCall < eps) { m.fold = 1; }
        else if (Math.abs(evJam - evCall) <= eps && evJam > 0 && evCall > 0) { m.all_in = 0.5; m.call = 0.5; }
        else if (evJam >= evCall) m.all_in = 1;
        else m.call = 1;
        mix[h] = m;
        roles[h] = (m.all_in ?? 0) >= 0.5 ? "shove" : m.call ? "call" : "fold";
      }
    }
  } else {
    // vs_3bet: o herói abriu e tomou 3bet.
    // ICM: quem dá 3bet também sofre o risk premium dele contra o herói (3beta menos, mais forte);
    // o herói paga o seu risk premium na equity exigida, faz menos 4bet de blefe e só jam com folga.
    if (prizes?.length) {
      const { heroRp, theirRp } = riskPair(t.heroSeat, agg.seat);
      icm = { heroRp, theirRp, openerMult: 1, extraNeed: heroRp * ICM_CALL_WEIGHT };
    }
    const tbScale = icm ? Math.max(0.4, Math.min(1.6, Math.exp(-3.8 * icm.theirRp + 1.5 * icm.heroRp))) : 1;
    const tPct = threeBetPct(heroPos, aggPos) * (S >= 100 ? 1 : S >= 40 ? 1.1 : 1.2) * tbScale;
    // Range de 3bet polarizado: ~65% valor (topo) + ~35% blefes com bloqueador/suited.
    const T = topRange(tPct * 0.65);
    {
      const bl = [...ALL_HANDS].filter((h) => (T[ALL_HANDS.indexOf(h)] ?? 0) === 0 && bluffScore(h, false) > 0).sort((a, b) => bluffScore(b, false) - bluffScore(a, false));
      for (const h of takeTop(bl, tPct * 0.35, new Set())) T[ALL_HANDS.indexOf(h)] = 1;
    }
    aggPct = pctOf(T);
    eq = equityVs(T);
    const open = t.actions.filter((a) => a.seat === t.heroSeat && a.type === "raise").reduce((x, a) => x + a.amount, 0) + blindOf(heroPos);
    const tbTotal = t.actions.filter((a) => a.seat === agg.seat).reduce((x, a) => x + a.amount, 0);
    const callAmt = tbTotal - open;
    potOdds = callAmt / (pot + callAmt);
    const heroIp = aggPos === "SB" || aggPos === "BB";
    // Pote de 3bet: mais fundo = mais implied odds; raso = menos manobra (realiza menos).
    R = (heroIp ? { 100: 0.95, 40: 0.85, 25: 0.75 } : { 100: 0.8, 40: 0.7, 25: 0.6 })[S as 100 | 40 | 25] ?? 0.8;
    need = potOdds / R + (icm?.extraNeed ?? 0);
    const heroOpen = openRangeFor(s.context, heroPos).hands;
    const inOpen = (h: HandKey) => (heroOpen[h] ?? 0) > 0;
    if (S >= 100) {
      sizeLabel = `${(Math.round(tbTotal * (heroIp ? 2.25 : 2.5) * 10) / 10).toString().replace(".", ",")}bb (${heroIp ? "2,25" : "2,5"}x a 3bet)`;
      const rp = icm?.heroRp ?? 0;
      const value = new Set(ALL_HANDS.filter((h) => eq[ALL_HANDS.indexOf(h)]! >= 0.6 + Math.max(0, rp) * 0.5));
      const valueCombos = [...value].reduce((x, h) => x + combos(h), 0);
      const bluffs = new Set<HandKey>();
      let acc = 0;
      const bluffShare = 0.5 * Math.max(0, 1 - 3 * Math.max(0, rp));
      for (const h of ["A5s", "A4s", "A3s", "A2s", "K5s", "K4s"] as HandKey[]) {
        if (!inOpen(h) || acc >= valueCombos * bluffShare) continue;
        bluffs.add(h); acc += combos(h);
      }
      for (const h of ALL_HANDS) {
        const e = eq[ALL_HANDS.indexOf(h)]!;
        if (value.has(h)) { mix[h] = { four_bet: 1 }; roles[h] = "valor"; }
        else if (bluffs.has(h)) { mix[h] = { four_bet: 1 }; roles[h] = "blefe"; }
        else if (e * playability(h) >= need) { mix[h] = { call: 1 }; roles[h] = "call"; }
        else { mix[h] = { fold: 1 }; roles[h] = "fold"; }
      }
    } else {
      // 40bb / 25bb: 4bet é all-in. EV aproximado do all-in (quem deu 3bet paga com a parte de cima do range) × call.
      sizeLabel = "all-in";
      const eff = Math.min(hero.stackBb, agg.stackBb) - (heroPos === "BB" || aggPos === "BB" ? 0 : 0);
      const callFrac = S >= 40 ? 70 : 85;
      const callRange = topOfRange(T, callFrac);
      // ICM: quando pagam o jam, a equity precisa cobrir também o risk premium (desconto no PKO).
      const eqC = Float64Array.from(equityVs(callRange), (e) => e - (icm?.heroRp ?? 0));
      const dead = pot - open - tbTotal;
      shoveEv = Float64Array.from({ length: N_HANDS }, (_, i) => {
        const f = 1 - callFrac / 100;
        return f * pot + (1 - f) * (eqC[i]! * (2 * eff + dead) - (eff - open));
      });
      for (const h of ALL_HANDS) {
        const i = ALL_HANDS.indexOf(h);
        const evCall = R * (playability(h) * eq[i]! - (icm?.extraNeed ?? 0)) * (pot + callAmt) - callAmt;
        const evJam = shoveEv[i]!;
        const best = Math.max(0, evCall, evJam);
        const near = (v: number) => best - v < 0.15;
        const m: Mix = {};
        if (best === 0 || (evCall < 0 && evJam < 0)) { mix[h] = { fold: 1 }; roles[h] = "fold"; continue; }
        if (near(evJam) && near(evCall) && evCall > 0 && evJam > 0) { m.all_in = 0.5; m.call = 0.5; }
        else if (evJam >= evCall) m.all_in = 1;
        else m.call = 1;
        mix[h] = m;
        roles[h] = m.all_in && m.all_in >= 0.5 ? "shove" : "call";
      }
    }
    // Mãos fora do range de open nunca chegam aqui; ficam como fold para a matriz.
    for (const h of ALL_HANDS) if (!inOpen(h)) { mix[h] = { fold: 1 }; roles[h] = "fold"; }
  }

  const freqPct: Mix = {};
  const base = s.spot.type === "vs_3bet" ? openRangeFor(s.context, heroPos).hands : null;
  const denom = base ? ALL_HANDS.reduce((x, h) => x + combos(h) * (base[h] ?? 0), 0) : TOTAL_COMBOS;
  for (const h of ALL_HANDS) {
    const w = base ? base[h] ?? 0 : 1;
    for (const [a, f] of Object.entries(mix[h]!)) freqPct[a as DecisionAction] = (freqPct[a as DecisionAction] ?? 0) + (combos(h) * w * (f ?? 0)) / denom * 100;
  }
  const out: ReactionStrategy = { mix, eq, potOdds, need, realization: R, aggressorPct: aggPct, freqPct, shoveEv, sizeLabel, roles, evUnit: prizes?.length && s.spot.type === "vs_open" ? "pct" : "bb", icm };
  cache.set(key, out);
  if (cache.size > 64) cache.delete(cache.keys().next().value as string);
  return out;
}

const PT: Partial<Record<DecisionAction, string>> = { fold: "Fold", call: "Call", three_bet: "3Bet", four_bet: "4Bet", all_in: "All-in" };
const pct = (v: number) => `${v.toFixed(1).replace(".", ",")}%`;

export const reactionProvider: StrategyProvider = {
  source: REACTION_SOURCE,
  supports: (spot) => spot === "vs_open" || spot === "vs_3bet",
  decide(s): StrategyDecision | null {
    if (s.context.mode && s.context.mode !== "chip_ev" && s.context.mode !== "icm" && s.context.mode !== "pko_icm") return null;
    if (!this.supports(s.spot.type) || !s.spot.aggressors[0]) return null;
    const st = reactionStrategy(s);
    const hand = s.hero.hand;
    const i = ALL_HANDS.indexOf(hand);
    const m = st.mix[hand] ?? { fold: 1 };
    const freqs = (Object.entries(m) as [DecisionAction, number][]).filter(([, f]) => f > 0).map(([action, frequency]) => ({ action, frequency } as ActionFrequency))
      .sort((a, b) => b.frequency - a.frequency);
    const [top, ...rest] = freqs as [ActionFrequency, ...ActionFrequency[]];
    const agg = s.spot.aggressors[0];
    const vs3 = s.spot.type === "vs_3bet";
    const cont: Record<HandKey, number> = {};
    for (const h of ALL_HANDS) { const f = 1 - (st.mix[h]?.fold ?? 0); if (f > 0) cont[h] = f; }
    const range: RangeDefinition = {
      id: `${rangeId(s.spot.type, s.context, s.spot.heroPosition)}|vs-${agg}`, spot: s.spot.type, action: "call", position: s.spot.heroPosition,
      context: s.context, hands: cont, source: "nvt_range", version: REACTION_VERSION, notes: NOTE,
    };
    const comp = (["three_bet", "four_bet", "all_in", "call", "fold"] as DecisionAction[]).filter((a) => (st.freqPct[a] ?? 0) > 0.05).map((a) => `${PT[a]} ${pct(st.freqPct[a]!)}`).join(" · ");
    const role = st.roles[hand];
    const roleTxt = role === "valor" ? `${vs3 ? "4bet" : "3bet"} por valor (está entre as mãos com mais equity contra o range de ${vs3 ? "3bet" : "open"})`
      : role === "blefe" ? `${vs3 ? "4bet" : "3bet"} de blefe com bloqueador/suited (fica de fora do call, mas bloqueia mãos fortes e joga bem quando paga)`
      : role === "shove" ? "all-in (o shove rende mais que pagar ou foldar)"
      : role === "call" ? "call (equity suficiente para o preço, já descontando a posição)"
      : "fold (equity abaixo do necessário para o preço)";
    const evTxt = st.shoveEv ? ` All-in vs fold: ${st.shoveEv[i]! >= 0 ? "+" : "−"}${Math.abs(st.shoveEv[i]!).toFixed(2).replace(".", ",")}${st.evUnit === "pct" ? "% do prize pool" : "bb"}${vs3 ? " (estimativa do modelo)" : st.evUnit === "pct" ? " (Nash com ICM)" : " (Nash)"}.` : "";
    const sg = (v: number) => `${v < 0 ? "−" : "+"}${Math.abs(v * 100).toFixed(1).replace(".", ",")}%`;
    const pkoTxt = s.context.mode === "pko_icm" ? " Com bounty: cobrir o adversário dá desconto (risk premium negativo); ser coberto encarece." : "";
    const icmTxt = st.icm ? ` ICM: seu risk premium contra o ${agg} é ${sg(st.icm.heroRp)} (o dele contra você ${sg(st.icm.theirRp)}), ${st.icm.heroRp >= 0 ? "somado à" : "descontado da"} equity exigida para pagar;${vs3 ? ` a 3bet dele já vem ${st.icm.theirRp > st.icm.heroRp ? "mais forte (ele também sofre pressão)" : "mais larga (ele tem risk advantage)"} e a sua 4bet de blefe encolhe.` : ` o range de open dele já vem ajustado pela pressão de ICM (×${st.icm.openerMult.toFixed(2).replace(".", ",")}) e a 3bet fica menor e polarizada.`}${pkoTxt}` : "";
    const explanation = `${hand}: ${roleTxt}. Contra o range ${vs3 ? `de 3bet do ${agg} (~${pct(st.aggressorPct)})` : `de open do ${agg} (${pct(st.aggressorPct)})`}, ${hand} tem ${pct(st.eq[i]! * 100)} de equity; o call custa pot odds de ${pct(st.potOdds * 100)} e, com a realização de equity desta mão nesta posição (${Math.round(st.realization * playability(hand) * 100)}%: ${hand.length === 2 ? "par" : hand.endsWith("s") ? "suited realiza mais" : "offsuit realiza menos"}), precisa de ${pct((st.potOdds / (st.realization * playability(hand)) + (st.icm?.extraNeed ?? 0)) * 100)}${st.icm ? " (já com o risk premium)" : ""}.${evTxt}${icmTxt} Size ${vs3 ? "da 4bet" : "da 3bet"}: ${st.sizeLabel}. Estratégia ${vs3 ? "do seu range de open" : "de todas as mãos"}: ${comp}. ${NOTE}${s.context.format !== "regular" && s.context.mode !== "pko_icm" ? " Bounty não entra neste spot." : ""}`;
    const source: StrategySourceInfo = st.icm
      ? { id: s.context.mode === "pko_icm" ? "pko" : "icm", label: `${vs3 ? "Vs 3bet" : "Vs open / 3bet"} com ICM${s.context.mode === "pko_icm" ? " + bounty" : ""} (referência calibrada)`, version: REACTION_VERSION }
      : REACTION_SOURCE;
    return { recommended: top.action, frequency: top.frequency, alternatives: rest, explanation, range, source, theoryTags: ["reference", vs3 ? "vs_3bet" : "vs_open", ...(st.icm ? ["icm"] : []), ...(s.context.mode === "pko_icm" ? ["pko"] : [])] };
  },
};

/** Ordem de força exportada para testes (as mãos de valor devem vir do topo). */
export const _strength = strengthOrder;
