/**
 * EV de shove (ou call all-in) do herói em potes com vários jogadores, por Monte Carlo:
 * sorteia mãos dos adversários pelos ranges informados (com remoção de cartas), decide quem paga
 * pelo range de call, sorteia o board, monta side pots e distribui. Valor final em fichas (chip EV)
 * ou ICM, mais bounties (PKO). NÃO é equilíbrio: é o EV exato DADOS os ranges assumidos.
 */
import { ALL_HANDS } from "@/domain/cards";
import { icmEquity } from "@/domain/icm";
import { createRng } from "@/domain/rng";
import { comboIds, eval7 } from "@/domain/evaluator";

export interface MultiwayPlayer {
  /** Stack no início da mão (antes do ante), em bb. */
  stack: number;
  /** Já colocado na rua (blinds/apostas), sem o ante. */
  invested: number;
  /** Ante pago (dinheiro morto). */
  ante: number;
  /** folded: fora; allin: já está all-in; active: ainda pode pagar o shove do herói. */
  status: "folded" | "allin" | "active";
  /** Range (169 pesos) das mãos possíveis; null = qualquer mão. */
  range: ArrayLike<number> | null;
  /** Parte do range que paga o shove do herói (só para active). */
  callRange: ArrayLike<number> | null;
  /** Bounty na cabeça (dinheiro no ICM; em bb no chip EV). */
  bounty: number;
  isHero: boolean;
}

export interface MultiwaySpec {
  players: MultiwayPlayer[];
  /** Cartas do herói (ids 0..51). */
  heroCards: [number, number];
  payouts?: number[];
  /** ICM: stacks de quem está em outras mesas (só entram no cálculo do ICM). */
  otherStacks?: number[];
  /** Parte do bounty paga na hora (resto vai para a cabeça). */
  bountyCashShare?: number;
  samples?: number;
  seed?: number;
}

export interface MultiwayResult {
  /** EV(shove) − EV(fold), em bb (chip) ou % do prize pool (ICM). */
  ev: number;
  stdErr: number;
  unit: "bb" | "pct";
  /** Probabilidade de cada jogador pagar o shove (índice = assento). */
  callProb: number[];
  /** Chance de o herói ganhar pelo menos o pote principal quando há showdown. */
  winMain: number;
  samples: number;
}

type Combo = [number, number];
/** Lista ponderada de combos de um range, para sortear rápido. */
function comboTable(range: ArrayLike<number> | null): { combos: Combo[]; cum: Float64Array; hand: number[] } {
  const combos: Combo[] = [], weights: number[] = [], hand: number[] = [];
  ALL_HANDS.forEach((h, i) => {
    const w = range ? Number(range[i] ?? 0) : 1;
    if (w <= 0) return;
    for (const c of comboIds(h)) { combos.push(c); weights.push(w); hand.push(i); }
  });
  const cum = new Float64Array(weights.length);
  let acc = 0;
  weights.forEach((w, k) => { acc += w; cum[k] = acc; });
  return { combos, cum, hand };
}

export function simulateMultiway(spec: MultiwaySpec): MultiwayResult {
  const { players, heroCards } = spec;
  const n = players.length;
  const hero = players.findIndex((p) => p.isHero);
  if (hero < 0) throw new Error("Sem herói");
  const rng = createRng(spec.seed ?? 12345);
  const N = spec.samples ?? 20000;
  const tables = players.map((p, i) => (i === hero || p.status === "folded" ? null : comboTable(p.range)));
  const callSets = players.map((p) => (p.callRange ? Float64Array.from({ length: 169 }, (_, i) => Number(p.callRange![i] ?? 0)) : null));
  const prizes = spec.payouts && spec.payouts.length ? spec.payouts : null;
  const prizeTotal = prizes ? prizes.reduce((a, b) => a + b, 0) : 1;
  const cashShare = spec.bountyCashShare ?? 0.5;
  const otherStacks = spec.otherStacks ?? [];
  const start = players.map((p) => p.stack);
  const deadAntes = players.reduce((s, p) => s + p.ante, 0);

  const value = (final: number[], cash: number[], heads: number[]): number => {
    if (!prizes) return final[hero]! + cash[hero]!;
    const all = otherStacks.length ? [...final, ...otherStacks] : final;
    const icm = icmEquity(all, prizes);
    const tot = all.reduce((a, b) => a + b, 0) || 1;
    return ((icm[hero]! + cash[hero]! + heads[hero]! * (final[hero]! / tot)) / prizeTotal) * 100;
  };

  /** Resolve o pote dado o investimento final de cada um e quem está no showdown. */
  const settle = (inv: number[], live: boolean[], score: number[], cash: number[], heads: number[]): number[] => {
    const final = start.map((s, i) => s - players[i]!.ante - inv[i]!);
    const levels = [...new Set(inv.filter((x, i) => x > 0 && live[i]))].sort((a, b) => a - b);
    let prev = 0;
    let dead = deadAntes;
    const bustedBy: number[][] = players.map(() => []);
    for (const lvl of levels) {
      let pot = 0;
      for (let i = 0; i < n; i++) pot += Math.max(0, Math.min(inv[i]!, lvl) - prev);
      pot += dead; dead = 0;
      const contenders = players.map((_, i) => i).filter((i) => live[i] && inv[i]! >= lvl);
      let best = -1; let winners: number[] = [];
      for (const i of contenders) { if (score[i]! > best) { best = score[i]!; winners = [i]; } else if (score[i] === best) winners.push(i); }
      for (const w of winners) final[w]! += pot / winners.length;
      // Quem ficou sem fichas foi eliminado pelos vencedores do maior pote em que estava.
      for (const i of contenders) bustedBy[i] = winners;
      prev = lvl;
    }
    // Sobra acima do maior nível disputado (só acontece com quem já saiu): fica com o maior investidor vivo.
    const total = inv.reduce((a, b) => a + b, 0) + deadAntes;
    const paid = final.reduce((a, b, i) => a + b - (start[i]! - players[i]!.ante - inv[i]!), 0);
    if (total - paid > 1e-9) {
      const top = players.map((_, i) => i).filter((i) => live[i]).sort((a, b) => inv[b]! - inv[a]!)[0];
      if (top !== undefined) final[top]! += total - paid;
    }
    // Dinheiro de quem foldou acima do último nível ativo volta para quem levou o último pote (já incluso via níveis).
    for (let i = 0; i < n; i++) {
      if (!live[i] || final[i]! > 1e-9 || !players[i]!.bounty) continue;
      const by = bustedBy[i]!.filter((w) => w !== i);
      for (const w of by) {
        cash[w]! += (players[i]!.bounty * cashShare) / by.length;
        heads[w]! += (players[i]!.bounty * (1 - cashShare)) / by.length;
      }
      heads[i] = 0;
    }
    return final;
  };

  let sum = 0, sum2 = 0, winMain = 0, showdowns = 0;
  const calls = new Array(n).fill(0);
  const used = new Uint8Array(52);
  const hands: (Combo | null)[] = new Array(n).fill(null);
  const handIdx = new Array(n).fill(-1);
  const seven = new Array(7).fill(0);
  let done = 0;
  for (let it = 0; it < N * 4 && done < N; it++) {
    used.fill(0);
    used[heroCards[0]] = 1; used[heroCards[1]] = 1;
    hands[hero] = heroCards;
    let ok = true;
    for (let i = 0; i < n && ok; i++) {
      const t = tables[i];
      if (!t) continue;
      let tries = 0, pick: Combo | null = null, hi = -1;
      while (tries++ < 30) {
        const r = rng.next() * t.cum[t.cum.length - 1]!;
        let lo = 0, up = t.cum.length - 1;
        while (lo < up) { const mid = (lo + up) >> 1; if (t.cum[mid]! < r) lo = mid + 1; else up = mid; }
        const c = t.combos[lo]!;
        if (!used[c[0]] && !used[c[1]]) { pick = c; hi = t.hand[lo]!; break; }
      }
      if (!pick) { ok = false; break; }
      used[pick[0]] = 1; used[pick[1]] = 1; hands[i] = pick; handIdx[i] = hi;
    }
    if (!ok) continue;
    const board: number[] = [];
    while (board.length < 5) { const c = Math.floor(rng.next() * 52); if (!used[c]) { used[c] = 1; board.push(c); } }
    const score = players.map((_, i) => {
      const h = hands[i];
      if (!h || (players[i]!.status === "folded" && i !== hero)) return -1;
      seven[0] = h[0]; seven[1] = h[1];
      for (let k = 0; k < 5; k++) seven[2 + k] = board[k]!;
      return eval7(seven);
    });
    // --- Shove do herói ---
    const invS = players.map((p) => p.invested);
    const liveS = players.map((p, i) => i === hero || p.status === "allin");
    invS[hero] = start[hero]! - players[hero]!.ante;
    for (let i = 0; i < n; i++) {
      const p = players[i]!;
      if (i === hero || p.status !== "active") continue;
      const w = callSets[i] ? callSets[i]![handIdx[i]]! : 0;
      if (w > 0 && rng.next() < w) {
        calls[i]++;
        liveS[i] = true;
        invS[i] = Math.min(start[i]! - p.ante, Math.max(p.invested, invS[hero]!));
      }
    }
    // O excedente do herói que ninguém cobre forma um pote só dele (volta pelo próprio settle).
    const cashS = new Array(n).fill(0), headsS = players.map((p) => p.bounty);
    let finalS: number[];
    if (liveS.filter(Boolean).length === 1) {
      finalS = start.map((s, i) => s - players[i]!.ante - invS[i]!);
      finalS[hero]! += invS.reduce((a, b) => a + b, 0) + deadAntes;
    } else {
      finalS = settle(invS, liveS, score, cashS, headsS);
      showdowns++;
      if (score[hero]! >= Math.max(...score.filter((_, i) => liveS[i]))) winMain++;
    }
    // --- Fold do herói: quem já está all-in disputa com o último agressor ativo (que paga). ---
    const invF = players.map((p) => p.invested);
    const liveF = players.map((p, i) => i !== hero && p.status === "allin");
    const aggressors = players.map((p, i) => ({ p, i })).filter(({ p, i }) => i !== hero && p.status === "active" && p.invested > 0).sort((a, b) => b.p.invested - a.p.invested);
    const lead = aggressors[0];
    if (lead) {
      liveF[lead.i] = true;
      const need = Math.max(...players.map((p, i) => (liveF[i] ? p.invested : 0)));
      invF[lead.i] = Math.min(start[lead.i]! - lead.p.ante, Math.max(lead.p.invested, need));
    }
    const cashF = new Array(n).fill(0), headsF = players.map((p) => p.bounty);
    let finalF: number[];
    if (liveF.filter(Boolean).length <= 1) {
      finalF = start.map((s, i) => s - players[i]!.ante - invF[i]!);
      const w = liveF.findIndex(Boolean);
      finalF[w >= 0 ? w : (lead?.i ?? 0)]! += invF.reduce((a, b) => a + b, 0) + deadAntes;
    } else finalF = settle(invF, liveF, score, cashF, headsF);
    const d = value(finalS, cashS, headsS) - value(finalF, cashF, headsF);
    sum += d; sum2 += d * d; done++;
  }
  const mean = sum / Math.max(1, done);
  const variance = Math.max(0, sum2 / Math.max(1, done) - mean * mean);
  return {
    ev: mean,
    stdErr: Math.sqrt(variance / Math.max(1, done)),
    unit: prizes ? "pct" : "bb",
    callProb: calls.map((c) => c / Math.max(1, done)),
    winMain: showdowns ? winMain / showdowns : 0,
    samples: done,
  };
}
