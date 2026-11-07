/**
 * Chip-EV Nash equilibrium for a first-in all-in (push/fold) subgame.
 *
 * Model (stated, not hidden):
 * - Everyone before the pusher has folded. The pusher shoves; players behind call or fold in order.
 * - Overcalls: after the first call, each player behind may overcall (one strategy per seat); at most
 *   three players see the flop all-in (a fourth caller folds). Side pots and bounties are exact.
 *   Three-way equity is approximated from heads-up equities (`share3`, fitted by Monte Carlo).
 * - Card removal is exact between each pair of players in the hand-vs-range sums, ignored between
 *   third parties (range-level reach and equity).
 * - Chip EV by default; with `payouts`, outcomes are valued by table ICM (Malmuth–Harville).
 *   ICM fold value of the first-in shover: the hand goes on without him (the next seat may shove, and so on;
 *   each later subgame is solved the same way, from the last seat back), because under ICM other players'
 *   all-ins and busts change the folder's equity. Only the SB's fold ends the hand (walk to the BB). In a resteal
 *   (`foldWinner` = opener) the next seat behind hero may resteal the same open; the last fold gives the pot to the opener.
 *   Calibrated against HRC Enumerated ICM (validation/references/nash_icm_*). When a caller folds, the
 *   shover is assumed to take the blinds unless someone behind calls.
 * Solved by alternating, linearly-averaged fictitious play; hands whose EV is within `MIX_EPS_BB` of indifference keep their
 * averaged (mixed) frequency, every other hand is pure.
 */
import { icmEquity } from "@/domain/icm";
import { equityMatrix, N_HANDS, pairWeights, tieMatrix } from "../equity/preflop-equity";

import { ALL_HANDS, combos } from "@/domain/cards";
import { SHARE3_PARAMS } from "./share3-params";

/** Combos per hand class in grid order. */
const HAND_COMBOS = Float64Array.from(ALL_HANDS, combos);

export interface PushFoldSeat {
  /** Starting stack for the hand, in BB (before posting). */
  stack: number;
  /** Blind posted by this seat (0.5 SB, 1 BB, 0 otherwise). */
  blind: number;
  /** Dead ante posted by this seat (BB-ante model). */
  ante: number;
  /** Live chips already in the pot beyond the ante, replacing `blind` (e.g. an open raise of 2bb). */
  invested?: number;
}

export interface PushFoldInput {
  /** Seats in preflop action order (seat index = position in this array). */
  seats: PushFoldSeat[];
  /** Index of the first-in shover. Everyone before has folded. */
  pusher: number;
  /**
   * Prize structure for ICM (relative values, 1st place first). Absent = chip EV.
   * With payouts, every outcome is valued by Malmuth–Harville ICM over the table's stacks.
   */
  payouts?: number[];
  /**
   * PKO: bounty on each seat's head and the share paid in cash on elimination (the rest goes to the
   * eliminator's head). With payouts (ICM) heads are money in the payouts' currency and every bounty still on
   * the table is won in proportion to chips (HRC's PKO model). Without payouts (chip EV) heads are in chips/bb and only the cash share counts
   * (the progressive half is ignored early in the tournament).
   */
  bounties?: { heads: number[]; cashShare: number };
  /**
   * Players who may call the shove, in the order they act. Default: every seat after the pusher.
   * Resteal: the seats behind hero, then the opener.
   */
  callers?: number[];
  /** Range prior per seat (169 weights); absent = random hand. Resteal: the opener's open range. */
  priors?: Record<number, ArrayLike<number>>;
  /** Who collects the pot when the pusher folds (ICM only). Default: the BB; resteal: the opener. */
  foldWinner?: number;
  /**
   * Value of every seat when the pusher folds (ICM only). Absent in a first-in ICM shove: computed by solving
   * the rest of the hand (next seat first-in, recursively). `false` = old model (the hand ends, walk to the BB).
   */
  foldValue?: number[] | false;
  /** Diagnostics/validation: hold the pusher's strategy fixed (169 frequencies) and solve only the callers. */
  fixedPush?: ArrayLike<number>;
  /**
   * Exploit: call (first caller) and overcall frequencies held fixed per caller seat (169 each), e.g. a villain's
   * range read from his stats. Those seats stop adapting; the pusher (and any free caller) best-respond to them.
   */
  fixedCalls?: Record<number, { call: ArrayLike<number>; overcall: ArrayLike<number> }>;
}

export interface PushFoldSolution {
  /** Shove frequency per hand class (169, grid order). */
  push: Float64Array;
  /** EV(shove) − EV(fold) for the pusher per hand class, in `unit`. */
  pushEv: Float64Array;
  /** For each seat behind the pusher: call frequency and EV(call) − EV(fold) in `unit`. */
  callers: { seat: number; call: Float64Array; callEv: Float64Array; overcall: Float64Array; effective: number }[];
  iterations: number;
  /** Expected value of every seat (in `unit`) from the moment the pusher acts, playing the equilibrium. */
  value: number[];
  /** "bb" = chip EV in big blinds; "pct" = ICM equity in % of the prize pool. */
  unit: "bb" | "pct";
}

export const NASH_ITERATIONS = 120;
/** ICM equilibria with many tight callers oscillate longer: 9-max 10bb UTG on the bubble needs ~1000 to match HRC. */
export const NASH_ICM_ITERATIONS = 1000;
/** The rest of the hand after a fold only feeds an expected value (an aggregate), which settles sooner. */
export const NASH_SUBGAME_ITERATIONS = 300;
/** Early stop for ICM solves: minimum iterations and tolerance (% prize pool gained by deviating, per hand). */
export const ICM_MIN_ITERATIONS = 150;
export const ICM_EXPLOIT_TOL = 0.0005;
const defaultIterations = (input: PushFoldInput) => (input.payouts?.length ? NASH_ICM_ITERATIONS : NASH_ITERATIONS);
export const MIX_EPS_BB = 0.02;

export function solvePushFold(input: PushFoldInput, iterations = defaultIterations(input)): PushFoldSolution {
  const { seats, pusher } = input;
  const P = seats[pusher];
  if (!P) throw new Error("Pusher inválido");
  const EQ = equityMatrix();
  const W = pairWeights();
  const N = N_HANDS;
  // WE[a*N+b] = W * equity(a vs b)
  const WE = new Float64Array(N * N);
  for (let i = 0; i < N * N; i++) WE[i] = W[i]! * EQ[i]!;
  // WT[a*N+b] = W * P(split pot). Under ICM a split pot (nobody busts) is not worth half a win.
  const TIE = tieMatrix();
  const WT = new Float64Array(N * N);
  for (let i = 0; i < N * N; i++) WT[i] = W[i]! * TIE[i]!;

  const S = seats.map((x) => x.stack);
  const posted = seats.map((x) => (x.invested ?? x.blind) + x.ante);
  const totalPosted = posted.reduce((a, b) => a + b, 0);
  const payouts = input.payouts && input.payouts.length ? input.payouts : null;
  const prizeTotal = payouts ? payouts.reduce((a, b) => a + b, 0) : 1;
  const totalChips = S.reduce((a, b) => a + b, 0);
  // Value of a final stack vector for one seat: chips (chip EV) or % of prize pool (ICM).
  // PKO: with payouts (ICM) heads are money; without payouts (chip EV) heads are already in chips (bb).
  const bounty = input.bounties ?? null;
  const heads0 = bounty ? seats.map((_, i) => bounty.heads[i] ?? 0) : null;
  /** Unit base: prizes, plus every bounty on the table in PKO (like HRC's table equity %). */
  const valueTotal = prizeTotal + (payouts && heads0 ? heads0.reduce((a, b) => a + b, 0) : 0);
  /**
   * Value of a final state for every seat: chips (chip EV) or % of the prize pool (ICM),
   * plus, in PKO, cash bounties won and the ICM value of the bounty on one's own head.
   */
  const valueOf = (stacks: number[], heads: number[] | null = heads0, cash: number[] | null = null): number[] => {
    if (!payouts) return cash ? stacks.map((v, i) => v + (cash[i] ?? 0)) : stacks;
    const icm = icmEquity(stacks, payouts);
    const total = stacks.reduce((a, b) => a + Math.max(0, b), 0) || 1;
    // PKO (same model as HRC's Bounty Mode PKO, matched to its numbers 26/10): every bounty still on the table is
    // won in proportion to chips (stack share), on top of cash already collected; % of prizes + bounties.
    const pool = heads ? heads.reduce((a, b) => a + (b ?? 0), 0) : 0;
    return icm.map((v, i) => {
      let money = v;
      if (heads) money += (cash?.[i] ?? 0) + pool * (Math.max(0, stacks[i]!) / total);
      return (money / valueTotal) * 100;
    });
  };
  /** Heads/cash after a showdown where `winner` may bust `loser`. */
  const bountyAfter = (stacks: number[], winner: number, loser: number): [number[] | null, number[] | null] => {
    if (!heads0 || !bounty || stacks[loser]! > 1e-9) return [heads0, null];
    const heads = [...heads0];
    const cash = seats.map(() => 0);
    const b = heads[loser] ?? 0;
    cash[winner] = b * bounty.cashShare;
    heads[winner] = (heads[winner] ?? 0) + b * (1 - bounty.cashShare);
    heads[loser] = 0;
    return [heads, cash];
  };

  const after = () => S.map((x, i) => x - posted[i]!);
  const bbSeat = seats.reduce((best, x, i) => (x.blind >= (seats[best]?.blind ?? 0) ? i : best), 0);
  // Pusher folds: assume the blinds/antes end with the BB (walk). Only matters for ICM.
  const pFold = after();
  pFold[input.foldWinner ?? bbSeat]! += totalPosted;
  // Everyone folds to the shove: pusher collects everything posted.
  const allFold = after();
  allFold[pusher]! += totalPosted;

  const callerSeats = input.callers ?? seats.map((_, i) => i).filter((i) => i > pusher);
  const callers = callerSeats.map((seat) => {
    const c = seats[seat]!;
    // Antes are dead money from every seat that posted one (BB-ante or ante for all players).
    const effective = Math.max(0, Math.min(P.stack - P.ante, c.stack - c.ante));
    const showdown = (pusherWins: boolean) => {
      const st = S.map((x, i) => x - posted[i]!);
      st[pusher] = S[pusher]! - effective - P.ante;
      st[seat] = S[seat]! - effective - c.ante;
      const pot = totalPosted - posted[pusher]! - posted[seat]! + 2 * effective + c.ante + P.ante;
      st[pusherWins ? pusher : seat]! += pot;
      return st;
    };
    const w = showdown(true), l = showdown(false);
    // Split pot: each gets half of the pot back (no bust, no bounty).
    const t = S.map((x, i) => x - posted[i]!);
    t[pusher] = S[pusher]! - effective - P.ante;
    t[seat] = S[seat]! - effective - c.ante;
    const half = (totalPosted - posted[pusher]! - posted[seat]! + 2 * effective + c.ante + P.ante) / 2;
    t[pusher]! += half;
    t[seat]! += half;
    return { seat, effective, win: valueOf(w, ...bountyAfter(w, pusher, seat)), lose: valueOf(l, ...bountyAfter(l, seat, pusher)), tie: valueOf(t) };
  });
  // ICM: folding does not end the hand; the next seat is first-in (solved recursively, from the last seat back).
  // Resteal (foldWinner = opener): after hero folds, the next seat behind may resteal the same open.
  const restealGame = input.foldWinner !== undefined && callerSeats.includes(input.foldWinner);
  const rest = restealGame ? callerSeats.filter((c) => c !== input.foldWinner) : callerSeats;
  const chain = !!payouts && input.foldValue === undefined && (restealGame ? rest.length >= 1 : !input.priors && input.foldWinner === undefined && rest.length >= 2);
  const { fixedPush: _fixed, fixedCalls: _fixedCalls, ...sub } = input;
  void _fixed; void _fixedCalls;
  const next: PushFoldInput | null = !chain ? null : restealGame
    ? { ...sub, pusher: rest[0]!, callers: [...rest.slice(1), input.foldWinner!] }
    : { ...sub, pusher: rest[0]!, callers: rest.slice(1) };
  const foldVec: number[] = Array.isArray(input.foldValue)
    ? input.foldValue
    : next ? solvePushFoldCached(next, NASH_SUBGAME_ITERATIONS).value : valueOf(pFold);
  const vPFold = foldVec[pusher]!;
  const vAllFold = valueOf(allFold);
  const K = callers.length;
  // Pusher payoffs relative to folding; caller payoffs relative to folding (pusher steals).
  const pAll = vAllFold[pusher]! - vPFold;
  const pWin = callers.map((c) => c.win[pusher]! - vPFold);
  const pLose = callers.map((c) => c.lose[pusher]! - vPFold);
  const pSplit = callers.map((c) => c.tie[pusher]! - vPFold);
  const cSplit = callers.map((c) => c.tie[c.seat]! - vAllFold[c.seat]!);
  const cWin = callers.map((c) => c.lose[c.seat]! - vAllFold[c.seat]!); // caller wins = pusher loses
  const cLose = callers.map((c) => c.win[c.seat]! - vAllFold[c.seat]!);
  const eps = payouts ? MIX_EPS_BB * ((100 / totalChips) || 0) : MIX_EPS_BB;

  /**
   * Three-way all-ins (pusher, first caller j, overcaller k): exact side pots and bounties for each of
   * the 6 finishing orders. Roles: 0 = pusher, 1 = caller j, 2 = overcaller k.
   */
  const threeWay = (j: number, k: number): number[][] => {
    const who = [pusher, callers[j]!.seat, callers[k]!.seat];
    const allIn = who.map((i) => S[i]! - seats[i]!.ante);
    const put = allIn.map((a, r) => Math.max(0, Math.min(a, Math.max(...allIn.filter((_, x) => x !== r)))));
    const dead = totalPosted - who.reduce((t, i) => t + posted[i]!, 0) + who.reduce((t, i) => t + seats[i]!.ante, 0);
    const levels = [...new Set(put)].sort((a, b) => a - b);
    return PERMS.map((perm) => {
      const st = after();
      who.forEach((i, r) => { st[i] = S[i]! - seats[i]!.ante - put[r]!; });
      // Pot layers: each level is won by the best-ranked player who reached it.
      const topWinner = [-1, -1, -1];
      let prev = 0;
      levels.forEach((lv, li) => {
        const elig = [0, 1, 2].filter((r) => put[r]! >= lv);
        const amount = (lv - prev) * elig.length + (li === 0 ? dead : 0);
        const winner = perm.find((r) => elig.includes(r))!;
        st[who[winner]!]! += amount;
        for (const r of elig) topWinner[r] = winner;
        prev = lv;
      });
      if (!heads0 || !bounty) return valueOf(st);
      const heads = [...heads0];
      const cash = seats.map(() => 0);
      for (let r = 0; r < 3; r++) {
        const i = who[r]!;
        if (st[i]! > 1e-9 || topWinner[r]! === r) continue;
        const e = who[topWinner[r]!]!;
        const b = heads[i] ?? 0;
        cash[e]! += b * bounty.cashShare;
        heads[e] = (heads[e] ?? 0) + b * (1 - bounty.cashShare);
        heads[i] = 0;
      }
      return valueOf(st, heads, cash);
    });
  };
  // v3[j][k][perm] = value per seat; only pairs j < k (k acts after j).
  const v3: number[][][][] = callers.map((_, j) => callers.map((__, k) => (k > j ? threeWay(j, k) : [])));

  const avgPush = input.fixedPush ? Float64Array.from({ length: N }, (_, i) => Number(input.fixedPush![i] ?? 0)) : new Float64Array(N).fill(1);
  const fixedC = callers.map((c) => input.fixedCalls?.[c.seat] ?? null);
  const avgCall = callers.map((_, k) => (fixedC[k] ? Float64Array.from({ length: N }, (__, i) => Number(fixedC[k]!.call[i] ?? 0)) : new Float64Array(N).fill(0.5)));
  const avgOver = callers.map((_, k) => (fixedC[k] ? Float64Array.from({ length: N }, (__, i) => Number(fixedC[k]!.overcall[i] ?? 0)) : new Float64Array(N).fill(0.25)));
  const brPush = new Float64Array(N);
  const brCall = callers.map(() => new Float64Array(N));
  const brOver = callers.map(() => new Float64Array(N));
  const pushEv = new Float64Array(N);
  const callEv = callers.map(() => new Float64Array(N));
  const overEv = callers.map(() => new Float64Array(N));

  // Caller hand priors (random = 1). The opener in a resteal holds only hands from its open range.
  const given = callers.map((c) => {
    const p = input.priors?.[c.seat];
    return p ? Float64Array.from({ length: N }, (_, i) => Number(p[i] ?? 0)) : null;
  });
  // Card removal by a caller with a known range (the opener in a resteal): the other callers' hands come from what
  // that range leaves in the deck. g(c) = combos of the known range compatible with one combo of class c (normalized). Without
  // it, a premium-heavy open makes the blinds look likelier to wake up than they are (HRC/exact: P(nobody calls)
  // 0.734 vs 0.730 for BTN 72o vs an LJ open on the PKO bubble, ≈0.05% of prize pool in EV).
  const known: Float64Array[] = [];
  for (const p of given) if (p) known.push(p);
  const removal = known.length
    ? (() => {
        const g = new Float64Array(N).fill(1);
        for (const p of known) {
          let mx = 0;
          const row = new Float64Array(N);
          // per combo of c: W counts combo pairs, and the callers' sums already weight by combos of c
          for (let c = 0; c < N; c++) { let t = 0; for (let o = 0; o < N; o++) t += W[c * N + o]! * p[o]!; row[c] = t / HAND_COMBOS[c]!; mx = Math.max(mx, row[c]!); }
          if (mx > 0) for (let c = 0; c < N; c++) g[c]! *= row[c]! / mx;
        }
        return g;
      })()
    : null;
  const priors = given.map((p) => p ?? removal);
  // wsum[k][h] = combos of caller k's prior compatible with hand h.
  const wsum = priors.map((p) => {
    const out = new Float64Array(N);
    for (let h = 0; h < N; h++) {
      let t = 0;
      const row = h * N;
      for (let c = 0; c < N; c++) t += W[row + c]! * (p ? p[c]! : 1);
      out[h] = t;
    }
    return out;
  });

  /** For a range (169 weights): per hand h, compatible combos (den) and equity-weighted combos (num). */
  // Sparse pass over the range: weights below 1e-4 (leftovers of the averaging) are skipped.
  const idx = new Int32Array(N);
  const versus = (range: Float64Array, den: Float64Array, num: Float64Array, tie?: Float64Array) => {
    let n = 0;
    for (let c = 0; c < N; c++) if (range[c]! > 1e-4) idx[n++] = c;
    for (let h = 0; h < N; h++) {
      let d = 0, e = 0, t = 0;
      const row = h * N;
      for (let x = 0; x < n; x++) {
        const c = idx[x]!;
        const f = range[c]!;
        d += W[row + c]! * f;
        e += WE[row + c]! * f;
        if (tie) t += WT[row + c]! * f;
      }
      den[h] = d;
      num[h] = e;
      if (tie) tie[h] = t;
    }
  };
  const pDen = new Float64Array(N), pNum = new Float64Array(N), pTie = new Float64Array(N);
  const cDen = callers.map(() => new Float64Array(N)), cNum = callers.map(() => new Float64Array(N)), cTie = callers.map(() => new Float64Array(N));
  const oDen = callers.map(() => new Float64Array(N)), oNum = callers.map(() => new Float64Array(N));
  const cRange = callers.map(() => new Float64Array(N)), oRange = callers.map(() => new Float64Array(N));
  /** Range vs range equity from precomputed per-hand sums: sum_a A[a]·num(a) / sum_a A[a]·den(a). */
  const rangeEq = (a: Float64Array, num: Float64Array, den: Float64Array) => {
    let n0 = 0, d0 = 0;
    for (let h = 0; h < N; h++) { const f = a[h]!; if (f) { n0 += f * num[h]!; d0 += f * den[h]!; } }
    return d0 > 0 ? n0 / d0 : 0.5;
  };
  /** Probability of an action given the pusher's range (card removal with the pusher's hand). */
  const reachVsPush = (push: Float64Array, den: Float64Array, k: number) => {
    let n0 = 0, d0 = 0;
    for (let h = 0; h < N; h++) { const f = push[h]!; if (f) { n0 += f * den[h]!; d0 += f * wsum[k]![h]!; } }
    return d0 > 0 ? n0 / d0 : 0;
  };
  const prob = new Float64Array(6);
  let last: { qBar: number[]; rBar: number[]; ePC: number[]; tPC: number[]; ePO: number[]; eCO: number[][] } | null = null;

  const iterate = (push: Float64Array, calls: Float64Array[], overs: Float64Array[]) => {
    versus(push, pDen, pNum, pTie);
    for (let k = 0; k < K; k++) {
      const pr = priors[k];
      for (let c = 0; c < N; c++) {
        cRange[k]![c] = pr ? calls[k]![c]! * pr[c]! : calls[k]![c]!;
        oRange[k]![c] = pr ? overs[k]![c]! * pr[c]! : overs[k]![c]!;
      }
      versus(cRange[k]!, cDen[k]!, cNum[k]!, cTie[k]!);
      if (k > 0) versus(oRange[k]!, oDen[k]!, oNum[k]!); // the first caller can never overcall
    }
    // Range-level quantities (card removal between third parties ignored).
    const qBar = callers.map((_, k) => reachVsPush(push, cDen[k]!, k));
    const rBar = callers.map((_, k) => reachVsPush(push, oDen[k]!, k));
    const ePC = callers.map((_, k) => rangeEq(push, cNum[k]!, cDen[k]!)); // pusher range vs k's call range
    const tPC = callers.map((_, k) => (qBar[k]! > 0 ? rangeEq(push, cTie[k]!, cDen[k]!) : 0)); // split-pot rate, pusher range vs k's call range
    const ePO = callers.map((_, k) => rangeEq(push, oNum[k]!, oDen[k]!)); // pusher range vs k's overcall range
    const eCO = callers.map((_, j) => callers.map((__, k) => (k > j ? rangeEq(cRange[j]!, oNum[k]!, oDen[k]!) : 0.5)));
    last = { qBar, rBar, ePC, tPC, ePO, eCO };

    // Value of folding for a would-be first caller j: the hand goes on (a player behind may call the shove,
    // someone may bust), which under ICM is worth more than "the shover takes the blinds". Range level.
    const foldGain = callers.map((cj, j) => {
      if (!payouts) return 0;
      const seatJ = cj.seat;
      let reach = 1, v = 0;
      for (let k = j + 1; k < K; k++) {
        const q = qBar[k]!;
        if (q > 0) {
          let reachO = 1, x = 0;
          for (let m = k + 1; m < K; m++) {
            const r = rBar[m]!;
            if (r > 0) {
              orderProbs(prob, 0, 1, 2, share3(ePC[k]!, ePO[m]!), eCO[k]![m]!, ePO[m]!, ePC[k]!);
              const vals = v3[k]![m]!;
              for (let o = 0; o < 6; o++) x += reachO * r * prob[o]! * vals[o]![seatJ]!;
            }
            reachO *= 1 - r;
          }
          const hu = callers[k]!;
          x += reachO * ((ePC[k]! - tPC[k]! / 2) * hu.win[seatJ]! + tPC[k]! * hu.tie[seatJ]! + (1 - ePC[k]! - tPC[k]! / 2) * hu.lose[seatJ]!);
          v += reach * q * (x - vAllFold[seatJ]!);
        }
        reach *= 1 - q;
      }
      return v;
    });

    // First caller j (nobody called yet): heads-up, or three-way if an overcaller k behind wakes up.
    for (let j = 0; j < K; j++) {
      const out = brCall[j]!, ev = callEv[j]!;
      const seatJ = callers[j]!.seat;
      const base = vAllFold[seatJ]!;
      for (let c = 0; c < N; c++) {
        if (pDen[c]! <= 0) { ev[c] = 0; out[c] = 0; continue; }
        const e = pNum[c]! / pDen[c]!;
        let reach = 1, v = 0;
        for (let k = j + 1; k < K; k++) {
          const r = rBar[k]!;
          if (r > 0) {
            const eo = oDen[k]![c]! > 0 ? oNum[k]![c]! / oDen[k]![c]! : 0.5;
            orderProbs(prob, 1, 0, 2, share3h(c, e, eo), ePO[k]!, eo, e);
            const vals = v3[j]![k]!;
            let x = 0;
            for (let m = 0; m < 6; m++) x += prob[m]! * vals[m]![seatJ]!;
            v += reach * r * (x - base);
          }
          reach *= 1 - r;
        }
        const t = pTie[c]! / pDen[c]!;
        v += reach * ((e - t / 2) * cWin[j]! + t * cSplit[j]! + (1 - e - t / 2) * cLose[j]!);
        ev[c] = v - foldGain[j]!;
        out[c] = ev[c]! > 0 ? 1 : 0;
      }
    }

    // Overcaller k: someone j < k called first and nobody between them overcalled.
    const firstCall = callers.map((_, j) => { let p = qBar[j]!; for (let i = 0; i < j; i++) p *= 1 - qBar[i]!; return p; });
    for (let k = 0; k < K; k++) {
      const out = brOver[k]!, ev = overEv[k]!;
      const seatK = callers[k]!.seat;
      const wj: number[] = [];
      let wTot = 0;
      for (let j = 0; j < k; j++) {
        let w = firstCall[j]!;
        for (let i = j + 1; i < k; i++) w *= 1 - rBar[i]!;
        wj.push(w);
        wTot += w;
      }
      if (wTot <= 0) { ev.fill(0); out.fill(0); continue; }
      for (let c = 0; c < N; c++) {
        if (pDen[c]! <= 0) { ev[c] = 0; out[c] = 0; continue; }
        const e = pNum[c]! / pDen[c]!;
        let v = 0;
        for (let j = 0; j < k; j++) {
          const w = wj[j]!;
          if (w <= 0) continue;
          const ec = cDen[j]![c]! > 0 ? cNum[j]![c]! / cDen[j]![c]! : 0.5;
          orderProbs(prob, 2, 0, 1, share3h(c, e, ec), ePC[j]!, ec, e);
          const vals = v3[j]![k]!;
          let x = 0;
          for (let m = 0; m < 6; m++) x += prob[m]! * vals[m]![seatK]!;
          // Folding leaves pusher vs j heads-up; k's value then depends on who wins.
          const hu = callers[j]!;
          const tj = last!.tPC[j]!;
          const fold = (ePC[j]! - tj / 2) * hu.win[seatK]! + tj * hu.tie[seatK]! + (1 - ePC[j]! - tj / 2) * hu.lose[seatK]!;
          v += w * (x - fold);
        }
        ev[c] = v / wTot;
        out[c] = ev[c]! > 0 ? 1 : 0;
      }
    }

    // Pusher: walk through who calls first, then whether someone behind overcalls.
    for (let h = 0; h < N; h++) {
      let reach = 1, ev = 0;
      for (let j = 0; j < K; j++) {
        const ws = wsum[j]![h]!;
        const q = ws > 0 ? cDen[j]![h]! / ws : 0;
        if (q > 0) {
          const eqC = cDen[j]![h]! > 0 ? cNum[j]![h]! / cDen[j]![h]! : 0.5;
          let reachO = 1, v = 0;
          for (let k = j + 1; k < K; k++) {
            const wk = wsum[k]![h]!;
            const r = wk > 0 ? oDen[k]![h]! / wk : 0;
            if (r > 0) {
              const eqO = oDen[k]![h]! > 0 ? oNum[k]![h]! / oDen[k]![h]! : 0.5;
              orderProbs(prob, 0, 1, 2, share3h(h, eqC, eqO), eCO[j]![k]!, eqO, eqC);
              const vals = v3[j]![k]!;
              let x = 0;
              for (let m = 0; m < 6; m++) x += prob[m]! * vals[m]![pusher]!;
              v += reachO * r * (x - vPFold);
            }
            reachO *= 1 - r;
          }
          const tC = cDen[j]![h]! > 0 ? cTie[j]![h]! / cDen[j]![h]! : 0;
          v += reachO * ((eqC - tC / 2) * pWin[j]! + tC * pSplit[j]! + (1 - eqC - tC / 2) * pLose[j]!);
          ev += reach * q * v;
        }
        reach *= 1 - q;
      }
      ev += reach * pAll;
      pushEv[h] = ev;
      brPush[h] = ev > 0 ? 1 : 0;
    }
  };

  // Alternating fictitious play with linear averaging (weight ∝ t): converges in ~100 iterations
  // where plain FP needs thousands (measured on 9-max 10bb UTG: <5 combos off after 120 its).
  // ICM: stop early once no seat gains more than ICM_EXPLOIT_TOL (% of the prize pool, average per hand) by
  // deviating from the averaged strategies; chip EV keeps the fixed count (results unchanged).
  const gain = (avg: Float64Array, ev: Float64Array) => {
    let g = 0;
    for (let h = 0; h < N; h++) { const e = ev[h]!; g += HAND_COMBOS[h]! * (Math.max(0, e) - avg[h]! * e); }
    return g / 1326;
  };
  let used = iterations;
  // Field com outras mesas (assentos que não agem): o EV vem em % do torneio inteiro, então a tolerância encolhe na
  // proporção da mesa no field (180 jogadores, mesa de 9: 1/20); sem outras mesas a escala é 1 (nada muda).
  const tableSeats = Math.max(pusher + 1, ...callerSeats.map((c) => c + 1), ...(input.foldWinner !== undefined ? [input.foldWinner + 1] : []));
  const exploitTol = ICM_EXPLOIT_TOL * Math.min(1, tableSeats / seats.length);
  for (let t = 1; t <= iterations; t++) {
    const step = 2 / (t + 1);
    iterate(avgPush, avgCall, avgOver);
    if (payouts && t >= ICM_MIN_ITERATIONS && t % 50 === 0) {
      let worst = gain(avgPush, pushEv);
      for (let k = 0; k < K; k++) if (!fixedC[k]) worst = Math.max(worst, gain(avgCall[k]!, callEv[k]!), k > 0 ? gain(avgOver[k]!, overEv[k]!) : 0);
      if (worst < exploitTol) { used = t; break; }
    }
    for (let k = 0; k < K; k++) {
      if (fixedC[k]) continue;
      const a = avgCall[k]!, b = brCall[k]!, o = avgOver[k]!, bo = brOver[k]!;
      for (let i = 0; i < N; i++) { a[i]! += (b[i]! - a[i]!) * step; o[i]! += (bo[i]! - o[i]!) * step; }
    }
    if (!input.fixedPush) for (let i = 0; i < N; i++) avgPush[i]! += (brPush[i]! - avgPush[i]!) * step;
  }

  // Final EVs against the averaged (equilibrium) strategies; snap clear decisions to pure.
  iterate(avgPush, avgCall, avgOver);
  const snap = (avg: Float64Array, ev: Float64Array) => {
    const out = new Float64Array(N);
    for (let i = 0; i < N; i++) {
      const e = ev[i]!;
      if (e > eps) out[i] = 1;
      else if (e < -eps) out[i] = 0;
      else {
        const f = Math.round(avg[i]! * 20) / 20;
        out[i] = f < 0.1 ? 0 : f > 0.9 ? 1 : f;
      }
    }
    return out;
  };
  // Expected value of every seat at the pusher's decision (range level: card removal between players ignored).
  const value = foldVec.map((v) => v);
  if (last) {
    const { qBar, rBar, ePC, tPC, ePO, eCO } = last;
    let pp = 0;
    for (let h = 0; h < N; h++) pp += avgPush[h]! * HAND_COMBOS[h]!;
    pp /= 1326;
    const shove = vAllFold.map(() => 0);
    const add = (vec: number[], w: number) => { if (w > 0) for (let i = 0; i < shove.length; i++) shove[i]! += w * vec[i]!; };
    let reach = 1;
    for (let j = 0; j < K; j++) {
      const q = qBar[j]! * reach;
      if (q > 0) {
        let reachO = 1;
        for (let k = j + 1; k < K; k++) {
          const r = rBar[k]!;
          if (r > 0) {
            orderProbs(prob, 0, 1, 2, share3(ePC[j]!, ePO[k]!), eCO[j]![k]!, ePO[k]!, ePC[j]!);
            const vals = v3[j]![k]!;
            for (let m = 0; m < 6; m++) add(vals[m]!, q * reachO * r * prob[m]!);
          }
          reachO *= 1 - r;
        }
        add(callers[j]!.win, q * reachO * (ePC[j]! - tPC[j]! / 2));
        add(callers[j]!.tie, q * reachO * tPC[j]!);
        add(callers[j]!.lose, q * reachO * (1 - ePC[j]! - tPC[j]! / 2));
      }
      reach *= 1 - qBar[j]!;
    }
    add(vAllFold, reach);
    for (let i = 0; i < value.length; i++) value[i] = pp * shove[i]! + (1 - pp) * foldVec[i]!;
  }
  return {
    value,
    push: snap(avgPush, pushEv),
    pushEv: Float64Array.from(pushEv),
    callers: callers.map((c, k) => ({
      seat: c.seat,
      call: fixedC[k] ? Float64Array.from(avgCall[k]!) : snap(avgCall[k]!, callEv[k]!),
      callEv: Float64Array.from(callEv[k]!),
      overcall: k > 0 ? (fixedC[k] ? Float64Array.from(avgOver[k]!) : snap(avgOver[k]!, overEv[k]!)) : new Float64Array(N),
      effective: c.effective,
    })),
    iterations: used,
    unit: payouts ? "pct" : "bb",
  };
}

/** Finishing orders of the three all-in players (roles 0 = pusher, 1 = first caller, 2 = overcaller). */
const PERMS = [[0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]] as const;
const PERM_INDEX = (a: number, b: number) => PERMS.findIndex((p) => p[0] === a && p[1] === b);
const PERM_LOOKUP = [0, 1, 2].map((a) => [0, 1, 2].map((b) => (a === b ? -1 : PERM_INDEX(a, b))));

/**
 * Three-way equity of a hand from its two heads-up equities (Bradley–Terry with a fitted exponent).
 * Fitted by Monte Carlo on 595 hand-vs-two-ranges spots (top 5–69% ranges): RMSE 1.7 points, against
 * 10 points for the naive product of equities.
 */
export const THREE_WAY_BETA = 0.85;
const G_STEPS = 2000;
const G_TABLE = Float64Array.from({ length: G_STEPS + 1 }, (_, i) => {
  const e = Math.min(0.999, Math.max(0.001, i / G_STEPS));
  return Math.pow((1 - e) / e, THREE_WAY_BETA);
});
const g = (e: number) => G_TABLE[Math.round(Math.min(1, Math.max(0, e)) * G_STEPS)]!;
/**
 * Three-way share of a specific hand class: the same form with a beta and an offset fitted per hand
 * (`SHARE3_PARAMS`, scripts/fit-share3.py): cross-validated RMSE 0.66 points vs 1.67 for the global fit.
 * Pairs and suited hands keep more of a three-way pot, offsuit aces less (domination by both opponents).
 */
let G_HAND: Float64Array | null = null;
export function share3h(hand: number, e1: number, e2: number): number {
  if (!G_HAND) {
    G_HAND = new Float64Array(169 * (G_STEPS + 1));
    for (let h = 0; h < 169; h++) {
      const [b, c] = SHARE3_PARAMS[h] ?? [THREE_WAY_BETA, 0];
      for (let i = 0; i <= G_STEPS; i++) {
        const e = Math.min(0.999, Math.max(0.001, i / G_STEPS));
        G_HAND[h * (G_STEPS + 1) + i] = Math.exp(b * Math.log((1 - e) / e) + c);
      }
    }
  }
  const row = hand * (G_STEPS + 1);
  const gi = (e: number) => G_HAND![row + Math.round(Math.min(1, Math.max(0, e)) * G_STEPS)]!;
  return 1 / (1 + gi(e1) + gi(e2));
}
export function share3(e1: number, e2: number): number {
  return 1 / (1 + g(e1) + g(e2));
}
/**
 * Probability of each finishing order (indexed like PERMS) seen by role x against roles y and z:
 * x wins with `sx`; otherwise y beats z with `eYZ` (range vs range); x beats the other with eXZ / eXY.
 */
function orderProbs(out: Float64Array, x: number, y: number, z: number, sx: number, eYZ: number, eXZ: number, eXY: number) {
  out[PERM_LOOKUP[x]![y]!] = sx * eYZ;
  out[PERM_LOOKUP[x]![z]!] = sx * (1 - eYZ);
  out[PERM_LOOKUP[y]![x]!] = (1 - sx) * eYZ * eXZ;
  out[PERM_LOOKUP[y]![z]!] = (1 - sx) * eYZ * (1 - eXZ);
  out[PERM_LOOKUP[z]![x]!] = (1 - sx) * (1 - eYZ) * eXY;
  out[PERM_LOOKUP[z]![y]!] = (1 - sx) * (1 - eYZ) * (1 - eXY);
}

const cache = new Map<string, PushFoldSolution>();
const CACHE_MAX = 256;

/** Quem quer saber dos solves novos (o worker de pré-cálculo repassa as soluções para a página). */
const solveListeners = new Set<(key: string, sol: PushFoldSolution) => void>();
export function onPushFoldSolve(fn: (key: string, sol: PushFoldSolution) => void): () => void { solveListeners.add(fn); return () => solveListeners.delete(fn); }
/** Coloca no cache soluções calculadas fora da página (worker). Mesma chave de `solvePushFoldCached`. */
export function primePushFoldCache(entries: [string, PushFoldSolution][]) {
  for (const [k, sol] of entries) {
    if (cache.has(k)) continue;
    cache.set(k, sol);
    if (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value as string);
  }
}

/** Memoized solve: identical tables (same stacks, blinds, pusher) reuse the equilibrium. */
export function solvePushFoldCached(input: PushFoldInput, iterations = defaultIterations(input)): PushFoldSolution {
  const key = `${input.fixedCalls ? Object.entries(input.fixedCalls).map(([k, v]) => `${k}:${Array.from(v.call).join(",")}/${Array.from(v.overcall).join(",")}`).join(";") : ""}#${input.fixedPush ? Array.from(input.fixedPush).join(",") : ""}|${iterations}|${input.foldValue === false ? "walk" : Array.isArray(input.foldValue) ? input.foldValue.join(",") : ""}|${input.callers?.join(",") ?? ""}|${input.foldWinner ?? ""}|${input.seats.map((x) => x.invested ?? "").join(",")}|${input.priors ? Object.entries(input.priors).map(([k, v]) => `${k}:${Array.from(v).join(",")}`).join(";") : ""}|${input.pusher}|${input.seats.map((s) => `${s.stack}/${s.blind}/${s.ante}`).join(",")}|${input.payouts?.join("/") ?? "chip"}|${input.bounties ? `${input.bounties.heads.join("/")}@${input.bounties.cashShare}` : ""}`;
  const hit = cache.get(key);
  if (hit) {
    cache.delete(key);
    cache.set(key, hit);
    return hit;
  }
  const sol = solvePushFold(input, iterations);
  cache.set(key, sol);
  if (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value as string);
  for (const fn of solveListeners) fn(key, sol);
  return sol;
}
