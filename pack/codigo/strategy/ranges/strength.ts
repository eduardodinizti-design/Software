/**
 * Ordem de força das 169 mãos para ranges "top X%" de valor (3bet, shove, call):
 * equity all-in contra uma mão aleatória, ponderada por combos (a ordem clássica do PokerStove).
 */
import { ALL_HANDS, combos, TOTAL_COMBOS, type HandKey } from "@/domain/cards";
import { equityMatrix, N_HANDS } from "../equity/preflop-equity";

let order: HandKey[] | null = null;
export function strengthOrder(): HandKey[] {
  if (order) return order;
  const m = equityMatrix();
  const eqVsRandom = ALL_HANDS.map((_, a) => {
    let s = 0, w = 0;
    for (let b = 0; b < N_HANDS; b++) { const c = combos(ALL_HANDS[b]!); s += m[a * N_HANDS + b]! * c; w += c; }
    return s / w;
  });
  order = [...ALL_HANDS].sort((x, y) => eqVsRandom[ALL_HANDS.indexOf(y)]! - eqVsRandom[ALL_HANDS.indexOf(x)]!);
  return order;
}

/** Range com os X% mais fortes (169 pesos, mão de fronteira fracionada). */
export function topRange(pct: number): Float64Array {
  const target = (Math.max(0, Math.min(100, pct)) / 100) * TOTAL_COMBOS;
  const out = new Float64Array(N_HANDS);
  let acc = 0;
  for (const h of strengthOrder()) {
    const c = combos(h);
    const i = ALL_HANDS.indexOf(h);
    if (acc + c <= target + 1e-9) { out[i] = 1; acc += c; continue; }
    out[i] = Math.max(0, (target - acc) / c);
    break;
  }
  return out;
}

/** Os X% mais fortes DENTRO de um range (para "paga o shove com a parte de cima do range"). */
export function topOfRange(range: ArrayLike<number>, pctOfRange: number): Float64Array {
  const total = ALL_HANDS.reduce((s, h, i) => s + combos(h) * Number(range[i] ?? 0), 0);
  const target = (Math.max(0, Math.min(100, pctOfRange)) / 100) * total;
  const out = new Float64Array(N_HANDS);
  let acc = 0;
  for (const h of strengthOrder()) {
    const i = ALL_HANDS.indexOf(h);
    const w = Number(range[i] ?? 0);
    if (w <= 0) continue;
    const c = combos(h) * w;
    if (acc + c <= target + 1e-9) { out[i] = w; acc += c; continue; }
    out[i] = w * Math.max(0, (target - acc) / c);
    break;
  }
  return out;
}
