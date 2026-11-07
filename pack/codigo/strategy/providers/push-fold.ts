import { EV_MIX_TOL_BB, EV_MIX_TOL_PCT } from "../tolerances";
/** Push/fold spots (open shove, call vs open shove) answered by the chip-EV Nash solver. */
import { ALL_HANDS, type HandKey } from "@/domain/cards";
import { tablePositions, type Position } from "@/domain/positions";
import { raiseHandInfo } from "@/strategy/pushfold/raise-hands";
import { RESTEAL_OPEN_SIZE, STACK_BUCKETS, type DecisionAction, type SpotType, type StrategyContext, type TrainingScenario } from "@/domain/scenario";
import { referenceOrFallbackOpenRange } from "../ranges/reference-data";
import type { TableState } from "@/domain/table";
import { isIcmStage, modelPayouts, PKO_CASH_SHARE } from "@/domain/tournament";
import { describeBountyPower, playerBountyPower } from "@/domain/pko";
import { fieldModel } from "@/icm/engine";
import { solvePushFoldCached, type PushFoldInput, type PushFoldSolution } from "../pushfold/nash";
import { HRC_OPENS } from "../pushfold/hrc-opens";
import { rangePercent } from "../ranges/stats";
import { rangeId, type RangeDefinition } from "../ranges/types";
import type { ActionFrequency, StrategyDecision, StrategyProvider, StrategySourceInfo, VillainRead, VillainReadLine } from "../types";
import { profileLabel, tableVillains } from "@/domain/villain";
import { continueFactor, REF_FOLD_TO_3BET, REF_STEAL, scaleRange, sharePct, shoveFactor } from "../exploit/villain-read";

export const NASH_VERSION = "nash-cev-2";
export const NASH_ICM_VERSION = "nash-icm-3";
export const NASH_SOURCE: StrategySourceInfo = { id: "nash_pushfold", label: "Nash push/fold (chip EV)", version: NASH_VERSION };
export const NASH_ICM_SOURCE: StrategySourceInfo = { id: "icm", label: "Nash push/fold (ICM)", version: NASH_ICM_VERSION };
export const NASH_PKO_VERSION = "nash-pko-icm-4";
export const NASH_PKO_SOURCE: StrategySourceInfo = { id: "pko", label: "Nash push/fold (PKO + ICM)", version: NASH_PKO_VERSION };
const PKO_NOTE = "PKO: metade do bounty eliminado em dinheiro, metade para a cabeça de quem eliminou; os bounties na mesa valem pela fatia de fichas de cada um (modelo do HRC).";
export const NASH_PKO_CEV_VERSION = "nash-pko-field-3";
export const NASH_PKO_CEV_SOURCE: StrategySourceInfo = { id: "pko", label: "Nash push/fold (PKO, começo/meio do torneio)", version: NASH_PKO_CEV_VERSION };
const PKO_CEV_NOTE = "PKO no começo/meio do torneio, no modelo do HRC (Multi Table ICM + Bounty Mode PKO): ICM exato sobre o torneio inteiro (premissa: 200 inscritos, 15% pagos, curva modelo; restantes 90% no começo, 50% no meio; outras mesas com o stack médio) e bounties em dinheiro (metade na hora, metade na cabeça; todos os bounties do torneio divididos pelas fichas). Validado contra o HRC (push/fold 10bb, começo e meio).";

/** PKO começo/meio: torneio de referência (premissas explícitas, as mesmas das referências do HRC). */
export const PKO_FIELD = { entrants: 200, paidShare: 0.15, remainingShare: { early: 0.9, mid: 0.5 } as Record<string, number> };
/** Cabeça média de quem sobrou (bounties iniciais): metade de cada cabeça eliminada sai em dinheiro. */
export const pkoAvgHead = (entrants: number, remaining: number) => {
  const out = entrants - remaining;
  return (entrants - 0.5 * out * (1 + (0.3 * out) / entrants)) / remaining;
};
/**
 * Field do PKO de começo/meio (no modelo do HRC): prêmios na moeda do bounty inicial (PKO 50/50: prêmios somam
 * inscritos × bounty inicial), outras mesas com o stack médio do torneio e a cabeça média; sem compressão (ICM exato
 * por grupos no motor). null sem stack inicial.
 */
export function pkoChipField(s: TrainingScenario): { payouts: number[]; field: { others: number[]; otherHead: number } } | null {
  const start = s.tournament.startingStackBb;
  if (start === undefined || !(start > 0)) return null;
  const n = s.table.players.length;
  const entrants = PKO_FIELD.entrants;
  const remaining = Math.max(n + 1, Math.round(entrants * (PKO_FIELD.remainingShare[s.context.stage] ?? 0.5)));
  const paid = Math.round(entrants * PKO_FIELD.paidShare);
  const fm = fieldModel({
    table: s.table.players.map((p) => p.stackBb), remaining, paid, prizePool: entrants, otherAvg: (start * entrants) / remaining, maxField: remaining,
    bounties: s.table.players.map((p) => p.bountyMultiplier ?? 1), otherBounty: pkoAvgHead(entrants, remaining), cashShare: PKO_CASH_SHARE,
  });
  return { payouts: fm.payouts, field: { others: fm.stacks.slice(n), otherHead: pkoAvgHead(entrants, remaining) } };
}
const MODEL_NOTE = "Equilíbrio Nash chip EV calculado com equity real, com overcalls (até 3 jogadores no all-in, side pots exatos); sem ICM e sem bounty.";
const ICM_NOTE = "Equilíbrio Nash com ICM de mesa (Malmuth-Harville), com overcalls (até 3 jogadores no all-in).";

/** Solver input from an actual table: real stacks, blinds and BB ante. */
export function pushFoldInputFromTable(t: TableState, pusherSeat: number, payouts?: number[], withBounties = false, stage: StrategyContext["stage"] = "mid", bountyChipsPerUnit?: number, field?: { others: number[]; otherHead?: number }): PushFoldInput {
  // ICM: bounties em dinheiro. Chip EV: bounty = múltiplo do bounty inicial × BBs atuais do stack inicial.
  // Fase informada (ICM): jogadores das outras mesas entram como assentos que não agem.
  const others = payouts && field?.others.length ? field.others : [];
  const heads = withBounties ? [...t.players.map((p) => (bountyChipsPerUnit !== undefined ? (p.bountyMultiplier ?? 0) * bountyChipsPerUnit : p.bounty ?? 0)), ...others.map(() => field?.otherHead ?? 0)] : null;
  const raise = t.actions.find((a) => a.type === "raise");
  // Range do opener (HRC): chip EV; ICM / PKO + ICM pela fase; PKO no começo/meio (field + bounties) pkochip_<fase>.
  const model = !payouts ? (withBounties ? null : "chip") : isIcmStage(stage) ? `${withBounties ? "pko" : "icm"}_${stage}` : withBounties ? `pkochip_${stage}` : "chip";
  const rs = raise ? resteal(t, pusherSeat, raise.seat, stage, model) : null;
  return {
    pusher: pusherSeat,
    ...(rs ?? {}),
    ...(!rs && others.length ? { callers: t.players.filter((p) => p.seat > pusherSeat).map((p) => p.seat) } : {}),
    ...(payouts ? { payouts } : {}),
    ...(heads && (payouts || bountyChipsPerUnit !== undefined) ? { bounties: { heads, cashShare: PKO_CASH_SHARE } } : {}),
    seats: [
      ...t.players.map((p) => ({
        stack: p.stackBb,
        blind: p.position === "SB" ? t.blinds.sb : p.position === "BB" ? t.blinds.bb : 0,
        ante: p.position === "BB" && t.blinds.anteType === "bb-ante" ? t.blinds.ante : 0,
        ...(raise && p.seat === raise.seat ? { invested: RESTEAL_OPEN_SIZE } : {}),
      })),
      ...others.map((stack) => ({ stack, blind: 0, ante: 0 })),
    ],
  };
}

/** Nearest open-raise reference bucket for an opener's stack. */
function openBucket(stackBb: number): StrategyContext["stack"] {
  return STACK_BUCKETS.reduce((best, b) => (Math.abs(b - stackBb) < Math.abs(best - stackBb) ? b : best), STACK_BUCKETS[0]!);
}

/**
 * Opener's open range as a 169 prior, for a table where `openerSeat` raised first in.
 * `hrc` (resteal, 9-max regular): the HRC model ("chip", "icm_<stage>", "pko_<stage>"; PKO falls back to the ICM open of the stage) whose 2bb open range
 * from the resteal tree (`HRC_OPENS`, nearest computed stack) is used, which is what makes the resteal match HRC;
 * otherwise (or when HRC has no data for that model) the reference open range.
 */
export function openerPrior(t: TableState, ctx: StrategyContext, openerSeat: number, hrc: string | null = null): Float64Array {
  const opener = t.players[openerSeat]!;
  // Mesas PKO também (até 30/10 só "regular" passava aqui: o PKO + ICM do trainer usava o range de referência,
  // embora a validação, que monta a mesa como regular, usasse o do HRC).
  if (hrc && t.size === 9 && (ctx.format === "regular" || ctx.format === "pko") && opener.stackBb >= 10 && opener.stackBb <= 30) {
    // PKO sem dados do HRC para a fase: usa o open do ICM da mesma fase (PKO + ICM) ou do chip EV (PKO no começo/meio).
    const has = (m: string) => Object.keys(HRC_OPENS).some((k) => k.startsWith(`${m}:`));
    const model = has(hrc) ? hrc : hrc.startsWith("pko_") ? hrc.replace("pko_", "icm_") : hrc.startsWith("pkochip_") ? "chip" : hrc;
    const stacks = Object.keys(HRC_OPENS).filter((k) => k.startsWith(`${model}:`)).map((k) => Number(k.split(":")[1]));
    if (stacks.length) {
      const stack = stacks.reduce((b, x) => (Math.abs(x - opener.stackBb) < Math.abs(b - opener.stackBb) ? x : b), stacks[0]!);
      const f = HRC_OPENS[`${model}:${stack}`]?.[opener.position];
      if (f) return Float64Array.from(f);
    }
  }
  const range = referenceOrFallbackOpenRange({ format: ctx.format, stage: ctx.stage, players: ctx.players, stack: openBucket(opener.stackBb) }, opener.position);
  return Float64Array.from(ALL_HANDS, (h) => range.hands[h] ?? 0);
}

/** Resteal subgame: hero shoves over the open; seats behind hero act first, then the opener. */
function resteal(t: TableState, heroSeat: number, openerSeat: number, stage: StrategyContext["stage"], hrc: string | null = null): Pick<PushFoldInput, "callers" | "priors" | "foldWinner"> {
  const ctx: StrategyContext = { format: t.format, stage, players: t.size, stack: 25 };
  const behind = t.players.filter((p) => p.seat > heroSeat).map((p) => p.seat);
  return { callers: [...behind, openerSeat], priors: { [openerSeat]: openerPrior(t, ctx, openerSeat, hrc) }, foldWinner: openerSeat };
}

const toHands = (f: Float64Array): Record<HandKey, number> => {
  const out: Record<HandKey, number> = {};
  ALL_HANDS.forEach((h, i) => { if (f[i]! > 0) out[h] = f[i]!; });
  return out;
};

function rangeFor(spot: SpotType, ctx: StrategyContext, pos: Position, hands: Record<HandKey, number>, suffix: string): RangeDefinition {
  const icm = ctx.mode === "icm" || ctx.mode === "pko_icm";
  const pkoChip = ctx.mode === "pko";
  const pko = ctx.mode === "pko_icm";
  if (pkoChip) return { id: `${rangeId(spot, ctx, pos)}|${suffix}`, spot, action: spot === "vs_open_shove" ? "call" : "all_in", position: pos, context: ctx, hands, source: "pko", version: NASH_PKO_CEV_VERSION, notes: PKO_CEV_NOTE };
  return {
    id: `${rangeId(spot, ctx, pos)}|${suffix}`,
    spot,
    action: spot === "vs_open_shove" ? "call" : "all_in",
    position: pos,
    context: ctx,
    hands,
    source: pko ? "pko" : icm ? "icm" : "nash_pushfold",
    version: pko ? NASH_PKO_VERSION : icm ? NASH_ICM_VERSION : NASH_VERSION,
    notes: pko ? `${ICM_NOTE} ${PKO_NOTE}` : icm ? ICM_NOTE : MODEL_NOTE,
  };
}

const fmtEv = (ev: number, unit: "bb" | "pct") => {
  const v = Math.abs(ev) < 0.005 ? "≈0" : `${ev > 0 ? "+" : ""}${ev.toFixed(2)}`;
  return unit === "bb" ? `${v}bb` : `${v}% do prize pool`;
};

export interface PushFoldView {
  solution: PushFoldSolution;
  heroRange: RangeDefinition;
  /** Shover's range (vs_open_shove only). */
  shoverRange: RangeDefinition | null;
  /** EV(action) − EV(fold) for the hero hand, in solution.unit. */
  heroEv: number;
  effectiveBb: number;
  /** ICM: hero's frequency under chip EV. PKO: under plain ICM (no bounties). For comparison. */
  chipEvFrequency: number | null;
  /** Resteal only: the opener's open range size and how much of it calls hero's shove. */
  opener: { position: Position; openPct: number; callPctOfRange: number; prior: Float64Array } | null;
  /** Exploit (scenario.exploit): leitura dos vilões e a resposta do equilíbrio para comparar. */
  /** Exploit: só informa (a nota segue o equilíbrio); frequência e EV da melhor resposta contra os stats. */
  read: { lines: VillainReadLine[]; exploitFrequency: number; exploitEv: number } | null;
}

/**
 * Exploit: cada vilão da mesa joga o range do equilíbrio ajustado pelos stats dele (`exploit/villain-read.ts`) e o
 * herói faz a melhor resposta. Quem paga: Fold para 3-Bet; quem dá o shove: Steal.
 */
function exploitSolve(s: TrainingScenario, input: PushFoldInput, sol: PushFoldSolution): { sol: PushFoldSolution; lines: VillainReadLine[] } | null {
  const villains = new Map(tableVillains(s.seed, s.table).map((v) => [v.seat, v]));
  const heroShoves = s.spot.type === "open_shove" || s.spot.type === "3bet_shove";
  const fixedCalls: NonNullable<PushFoldInput["fixedCalls"]> = {};
  const lines: VillainReadLine[] = [];
  const pos = (seat: number) => s.table.players[seat]!.position;
  for (const c of sol.callers) {
    if (c.seat === s.table.heroSeat) continue;
    const v = villains.get(c.seat);
    if (!v) continue;
    const prior = input.priors?.[c.seat] ?? null;
    const f = continueFactor(v.stats);
    const call = scaleRange(c.call, c.callEv, prior, f);
    fixedCalls[c.seat] = { call, overcall: scaleRange(c.overcall, c.callEv, prior, f) };
    lines.push({ seat: c.seat, position: pos(c.seat), name: v.name, profile: profileLabel(v.profile), stat: "Fold para 3-Bet", value: v.stats.foldTo3Bet, ref: REF_FOLD_TO_3BET, verb: "paga", gtoPct: sharePct(c.call, prior), exploitPct: sharePct(call, prior) });
  }
  let fixedPush: Float64Array | undefined;
  if (!heroShoves) {
    const v = villains.get(input.pusher);
    if (v) {
      fixedPush = scaleRange(sol.push, sol.pushEv, null, shoveFactor(v.stats));
      lines.unshift({ seat: input.pusher, position: pos(input.pusher), name: v.name, profile: profileLabel(v.profile), stat: "Steal", value: v.stats.steal, ref: REF_STEAL, verb: "empurra", gtoPct: sharePct(sol.push, null), exploitPct: sharePct(fixedPush, null) });
    }
  }
  if (!lines.length) return null;
  // Vilões fixos: o herói só precisa da melhor resposta (uma iteração basta).
  const ex = solvePushFoldCached({ ...input, fixedCalls, ...(fixedPush ? { fixedPush } : {}) }, 1);
  return { sol: ex, lines };
}

/** Payouts the scenario must be solved with: ICM mode requires the (model) structure. */
function scenarioPayouts(s: TrainingScenario): number[] | undefined {
  if (s.context.mode !== "icm" && s.context.mode !== "pko_icm") return undefined;
  const prizes = s.tournament.payouts?.prizes;
  if (!prizes?.length) throw new Error("Spot ICM sem estrutura de premiação");
  return prizes;
}

function heroFrequency(s: TrainingScenario, sol: PushFoldSolution, i: number): number {
  if (s.spot.type === "open_shove" || s.spot.type === "3bet_shove") return sol.push[i]!;
  return sol.callers.find((c) => c.seat === s.table.heroSeat)?.call[i] ?? 0;
}

/** Solves the scenario's table and extracts hero's strategy. */
export function pushFoldView(s: TrainingScenario): PushFoldView {
  const t = s.table;
  const order = tablePositions(t.size);
  const ctx = s.context;
  const payouts = scenarioPayouts(s);
  const i = ALL_HANDS.indexOf(s.hero.hand);
  const heroShoves = s.spot.type === "open_shove" || s.spot.type === "3bet_shove";
  const pusherSeat = heroShoves ? t.heroSeat : order.indexOf(s.spot.aggressors[0] ?? "BB");
  if (pusherSeat < 0 || (s.spot.type !== "open_shove" && !s.spot.aggressors[0])) throw new Error("Spot sem agressor");
  const pkoChip = s.context.mode === "pko";
  const pko = s.context.mode === "pko_icm" || pkoChip;
  if (pko && t.players.some((p) => p.bounty === null)) throw new Error("Spot PKO sem bounties na mesa");
  // PKO começo/meio: field do torneio + bounties em bounties iniciais (heads = múltiplo × 1), como o HRC.
  const pf = pkoChip ? pkoChipField(s) : null;
  if (pkoChip && !pf) throw new Error("Spot PKO sem stack inicial");
  const unitBb = pkoChip ? 1 : undefined;
  const field = pf ? pf.field : s.tournament.fieldOthers?.length ? { others: s.tournament.fieldOthers, ...(s.tournament.fieldOtherBounty !== undefined ? { otherHead: s.tournament.fieldOtherBounty } : {}) } : undefined;
  const pays = pf ? pf.payouts : payouts;
  const input = pushFoldInputFromTable(t, pusherSeat, pays, pko, ctx.stage, unitBb, field);
  const gtoSol = solvePushFoldCached(input);
  const ex = s.exploit ? exploitSolve(s, input, gtoSol) : null;
  // Exploit (30/10, Eduardo): o EV contra o vilão é um modelo a partir dos stats, não o EV real do spot. A resposta
  // cobrada e o range mostrado são os do equilíbrio; a melhor resposta contra os stats só aparece na leitura dos vilões.
  const sol = gtoSol;
  const sid = s.scenarioId;
  const read = ex ? { lines: ex.lines, exploitFrequency: heroFrequency(s, ex.sol, i), exploitEv: s.spot.type === "vs_open_shove" ? ex.sol.callers.find((c) => c.seat === t.heroSeat)?.callEv[i] ?? 0 : ex.sol.pushEv[i]! } : null;
  // Baseline para comparar: PKO → sem bounty (ICM puro ou chip EV puro); ICM → chip EV.
  const chipEvFrequency = pays || pkoChip ? heroFrequency(s, solvePushFoldCached(pushFoldInputFromTable(t, pusherSeat, pko ? pays : undefined, false, ctx.stage, undefined, field)), i) : null;
  if (s.spot.type === "3bet_shove") {
    const openerSeat = order.indexOf(s.spot.aggressors[0]!);
    // O mesmo range de open que o solver usou (HRC quando há dados para o modelo, senão o de referência).
    const prior = Float64Array.from(input.priors?.[openerSeat] ?? openerPrior(t, ctx, openerSeat));
    const call = sol.callers.find((c) => c.seat === openerSeat)?.call;
    const openHands = toHands(prior);
    const callHands = call ? toHands(Float64Array.from(prior, (p, k) => p * call[k]!)) : {};
    const openPct = rangePercent(openHands);
    const opponents = sol.callers.map((c) => c.effective);
    return {
      solution: sol,
      heroRange: rangeFor("3bet_shove", ctx, s.spot.heroPosition, toHands(sol.push), sid),
      shoverRange: null,
      heroEv: sol.pushEv[i]!,
      effectiveBb: Math.max(...opponents),
      chipEvFrequency,
      opener: { position: s.spot.aggressors[0]!, openPct, callPctOfRange: openPct > 0 ? (rangePercent(callHands) / openPct) * 100 : 0, prior },
      read,
    };
  }
  if (s.spot.type === "open_shove") {
    const behind = t.players.filter((p) => p.seat > t.heroSeat);
    const effectiveBb = Math.min(t.players[t.heroSeat]!.stackBb, Math.max(...behind.map((p) => p.stackBb)));
    return { solution: sol, heroRange: rangeFor("open_shove", ctx, s.spot.heroPosition, toHands(sol.push), sid), shoverRange: null, heroEv: sol.pushEv[i]!, effectiveBb, chipEvFrequency, opener: null, read };
  }
  const me = sol.callers.find((c) => c.seat === t.heroSeat);
  if (!me) throw new Error("Hero não está atrás do shover");
  return {
    solution: sol,
    heroRange: rangeFor("vs_open_shove", ctx, s.spot.heroPosition, toHands(me.call), sid),
    shoverRange: rangeFor("open_shove", ctx, s.spot.aggressors[0]!, toHands(sol.push), sid),
    heroEv: me.callEv[i]!,
    effectiveBb: me.effective,
    chipEvFrequency,
    opener: null,
    read,
  };
}

function pushFoldApplies(s: TrainingScenario): boolean {
  if (s.context.mode && s.context.mode !== "chip_ev" && s.context.mode !== "icm" && s.context.mode !== "pko_icm" && s.context.mode !== "pko") return false;
  if (s.context.mode === "pko" && (s.context.format !== "pko" || isIcmStage(s.context.stage))) return false;
  if ((s.context.mode === "icm" || s.context.mode === "pko_icm") && !isIcmStage(s.context.stage)) return false;
  if (s.context.mode === "pko_icm" && s.context.format !== "pko") return false;
  return s.spot.type === "open_shove" || s.spot.type === "vs_open_shove" || s.spot.type === "3bet_shove";
}

export const pushFoldProvider: StrategyProvider = {
  source: NASH_SOURCE,
  supports: (spot) => spot === "open_shove" || spot === "vs_open_shove" || spot === "3bet_shove",
  // Só a fonte (sem resolver o Nash): a trava de validação precisa saber a família, não a resposta.
  probe(s) {
    if (!pushFoldApplies(s)) return null;
    const pkoChip = s.context.mode === "pko", pko = s.context.mode === "pko_icm" || pkoChip, icm = s.context.mode === "icm" || s.context.mode === "pko_icm";
    return { source: pkoChip ? NASH_PKO_CEV_SOURCE : pko ? NASH_PKO_SOURCE : icm ? NASH_ICM_SOURCE : NASH_SOURCE, rangeId: "", mode: s.context.mode ?? "chip_ev" };
  },
  decide(s): StrategyDecision | null {
    if (!pushFoldApplies(s)) return null;
    const v = pushFoldView(s);
    const action: DecisionAction = s.spot.type === "vs_open_shove" ? "call" : "all_in";
    const f0 = v.heroRange.hands[s.hero.hand] ?? 0;
    // Empate de EV (dentro da margem da régua): mostra as duas ações, nunca "100%" de uma (ex.: 99 fold e 88 shove no
    // mesmo nó, com o 99 a 0,000% do fold). A correção já aceita as duas.
    const tieTol = v.solution.unit === "pct" ? EV_MIX_TOL_PCT : EV_MIX_TOL_BB;
    const evTie = (f0 === 0 || f0 === 1) && Math.abs(v.heroEv) < tieTol;
    const f = evTie ? 0.5 : f0;
    const freqs: ActionFrequency[] = [
      { action, frequency: f },
      { action: "fold" as DecisionAction, frequency: 1 - f },
    ].sort((a, b) => b.frequency - a.frequency);
    const [top, ...rest] = freqs as [ActionFrequency, ...ActionFrequency[]];
    const verb = action === "all_in" ? "Shove" : "Call";
    const pct = rangePercent(v.heroRange.hands).toFixed(1);
    const eff = `${Math.round(v.effectiveBb * 10) / 10}bb efetivos`;
    const what = s.spot.type === "open_shove"
      ? `Range de shove do ${s.spot.heroPosition}: ${pct}% (${eff}).`
      : s.spot.type === "3bet_shove" && v.opener
      ? `${v.opener.position} abre ${RESTEAL_OPEN_SIZE}bb com ${v.opener.openPct.toFixed(1)}% das mãos (range de referência) e paga o seu shove com ${Math.round(v.opener.callPctOfRange)}% desse range. Seu range de resteal do ${s.spot.heroPosition}: ${pct}% (até ${eff}). Modelo fold ou shove (sem flat call).`
      : `${s.spot.heroPosition} paga ${pct}% contra o shove do ${s.spot.aggressors[0]} (que empurra ${rangePercent(v.shoverRange!.hands).toFixed(1)}%; ${eff}).`;
    const mixed = evTie ? ` Empate de EV: ${action === "all_in" ? "shove" : "call"} e fold rendem quase o mesmo (diferença menor que ${v.solution.unit === "pct" ? "0,02% do prize pool" : "0,05bb"}); as duas são aceitas.` : f > 0 && f < 1 ? " Mão praticamente indiferente: as duas ações são aceitas." : "";
    const pkoChip = s.context.mode === "pko";
    const pko = s.context.mode === "pko_icm" || pkoChip;
    const icm = s.context.mode === "icm" || s.context.mode === "pko_icm";
    let compare = "";
    if ((icm || pkoChip) && v.chipEvFrequency !== null) {
      const baseAct = v.chipEvFrequency >= 0.5 ? verb : "Fold";
      const act = f >= 0.5 ? verb : "Fold";
      const base = pko ? "Sem bounty (ICM puro)" : "Em chip EV";
      const cause = pko ? "o bounty" : "o ICM";
      compare = baseAct !== act ? ` ${base} seria ${baseAct}: aqui ${cause} muda a decisão.` : ` ${base} também seria ${baseAct}.`;
    }
    let bountyText = "";
    if (pko) {
      const t = s.table;
      const hero = t.players[t.heroSeat]!;
      const others = s.spot.type === "open_shove" ? t.players.filter((p) => p.seat > t.heroSeat)
        : s.spot.type === "3bet_shove" ? t.players.filter((p) => p.seat > t.heroSeat || p.position === s.spot.aggressors[0])
        : t.players.filter((p) => p.position === s.spot.aggressors[0]);
      const covered = others.filter((p) => hero.stackBb >= p.stackBb - (p.position === "BB" ? t.blinds.ante : 0));
      const unit = s.tournament.startingStackBb;
      const inChips = (p: (typeof t.players)[number]) => {
        const bp = playerBountyPower(s, p);
        const chips = pkoChip && unit !== undefined ? ` = ${(p.bountyMultiplier ?? 0).toFixed(2).replace(".", ",")} bounty inicial` : "";
        return `${chips}${bp !== null ? `; ${describeBountyPower(bp)}` : ""}`;
      };
      bountyText = covered.length
        ? ` Você cobre ${covered.map((p) => `${p.position} (bounty ${p.bounty?.toLocaleString("pt-BR")}${inChips(p)})`).join(", ")}.`
        : " Você não cobre ninguém aqui: só ganha bounty se o outro for eliminado em outra mão.";
    }
    let readText = "";
    let villainRead: VillainRead | undefined;
    if (v.read) {
      const r = v.read;
      const lineTxt = r.lines.map((l) => `${l.position} ${l.name} (${l.profile}, ${l.stat} ${l.value}%) ${l.verb} ${l.exploitPct.toFixed(0)}% do range contra ${l.gtoPct.toFixed(0)}% do equilíbrio`).join("; ");
      const gAct = f >= 0.5 ? verb : "Fold";
      const eAct = r.exploitFrequency >= 0.5 ? verb : "Fold";
      readText = ` Leitura dos vilões: ${lineTxt}. ${gAct === eAct ? `Contra estes perfis também seria ${eAct} (${fmtEv(r.exploitEv, v.solution.unit)}, estimativa).` : `Contra estes perfis o modelo daria ${eAct} (${fmtEv(r.exploitEv, v.solution.unit)}, estimativa pelos stats); a resposta cobrada é a do equilíbrio.`}`;
      villainRead = { lines: r.lines, gto: { frequency: f, ev: v.heroEv }, exploit: { frequency: r.exploitFrequency, ev: r.exploitEv }, action };
    }
    // Mão de raise no jogo completo (HRC): fora do push/fold, qualquer resposta é aceita.
    const rh = s.spot.type === "open_shove" ? raiseHandInfo(s) : null;
    const rhText = rh ? ` Fora do push/fold: no jogo completo (${rh.label}) esta mão é de raise. Raise ${fmtEv(rh.raise, rh.unit)}, shove ${fmtEv(rh.shove, rh.unit)} em relação ao fold (o HRC aumenta ${Math.round(rh.raiseFreq * 100)}% das vezes). Entre shove e fold, ${rh.shove < -(rh.unit === "pct" ? 0.02 : 0.05) ? "o fold perde menos que o shove no jogo real" : "as duas ficam perto"}; por isso esta mão não conta como erro.` : "";
    return {
      ...(villainRead ? { villainRead } : {}),
      ...(rh ? { outsideDrill: rhText.trim() } : {}),
      // Fora do drill: recomenda a melhor das duas no jogo completo (as duas são aceitas na correção).
      recommended: rh ? (rh.shove >= 0 ? action : "fold") : top.action,
      frequency: rh ? 1 : top.frequency,
      alternatives: rh ? [] : rest.filter((a) => a.frequency > 0),
      explanation: `${s.hero.hand}: ${verb} ${fmtEv(v.heroEv, v.solution.unit)} em relação ao fold.${rhText}${readText} ${what}${bountyText}${compare}${mixed} ${pkoChip ? `${PKO_CEV_NOTE} Stack inicial ≈ ${s.tournament.startingStackBb}bb atuais.` : icm ? `${ICM_NOTE}${pko ? ` ${PKO_NOTE}` : " Sem bounty."} ${s.tournament.payouts?.source === "imported" ? "Premiação real informada." : "Premiação modelo."}` : MODEL_NOTE}`,
      range: v.heroRange,
      actionEvs: [{ action, ev: v.heroEv }, { action: "fold", ev: 0 }],
      evUnit: v.solution.unit,
      source: pkoChip ? NASH_PKO_CEV_SOURCE : pko ? NASH_PKO_SOURCE : icm ? NASH_ICM_SOURCE : NASH_SOURCE,
      theoryTags: pkoChip ? ["nash", "chip_ev", "pko", "push_fold"] : pko ? ["nash", "icm", "pko", "push_fold"] : icm ? ["nash", "icm", "push_fold"] : ["nash", "chip_ev", "push_fold"],
    };
  },
};

/** Reference chart for the Ranges page: every player with the same stack (classic "effective stack" chart). */
export function nashChart(ctx: StrategyContext, spot: "open_shove" | "vs_open_shove" | "3bet_shove", hero: Position, shover?: Position, ftPayouts?: number[]): RangeDefinition {
  const order = tablePositions(ctx.players);
  const seats = order.map((p) => ({ stack: ctx.stack, blind: p === "SB" ? 0.5 : p === "BB" ? 1 : 0, ante: p === "BB" ? 1 : 0 }));
  // ICM stage ⇒ ICM chart with the stage's model payouts; otherwise chip EV.
  const prizes = ctx.stage === "ft" && ftPayouts ? ftPayouts.slice(0, ctx.players) : isIcmStage(ctx.stage) ? modelPayouts(ctx.stage, ctx.players)?.prizes : undefined;
  const c: StrategyContext = prizes ? { ...ctx, mode: "icm" } : ctx;
  const base = prizes ? { seats, payouts: prizes } : { seats };
  if (spot === "open_shove") {
    const sol = solvePushFoldCached({ ...base, pusher: order.indexOf(hero) });
    return rangeFor(spot, c, hero, toHands(sol.push), ftPayouts ? "chart-real" : "chart");
  }
  if (!shover) throw new Error("Informe o shover");
  if (spot === "3bet_shove") {
    // Resteal: o opener (shover) abre 2bb com o range de referência; hero dá shove por cima.
    const openerSeat = order.indexOf(shover), heroSeat = order.indexOf(hero);
    const tableSeats = seats.map((x, i) => (i === openerSeat ? { ...x, invested: RESTEAL_OPEN_SIZE } : x));
    const fake = { size: ctx.players, format: ctx.format, players: order.map((position, seat) => ({ seat, position, stackBb: ctx.stack })) } as unknown as TableState;
    const callers = [...order.map((_, i) => i).filter((i) => i > heroSeat), openerSeat];
    const sol = solvePushFoldCached({ ...base, seats: tableSeats, pusher: heroSeat, callers, priors: { [openerSeat]: openerPrior(fake, ctx, openerSeat, !prizes && (ctx.mode ?? "chip_ev") === "chip_ev" ? "chip" : prizes && !ftPayouts && isIcmStage(ctx.stage) ? `icm_${ctx.stage}` : null) }, foldWinner: openerSeat });
    return rangeFor(spot, c, hero, toHands(sol.push), `chart-vs-${shover}${ftPayouts ? "-real" : ""}`);
  }
  const sol = solvePushFoldCached({ ...base, pusher: order.indexOf(shover) });
  const me = sol.callers.find((c) => c.seat === order.indexOf(hero));
  if (!me) throw new Error("Hero precisa estar atrás do shover");
  return rangeFor(spot, c, hero, toHands(me.call), `chart-vs-${shover}${ftPayouts ? "-real" : ""}`);
}
