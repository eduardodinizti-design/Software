/** Preflop all-in equity lookups between the 169 hand classes, plus exact card-removal weights. */
import { ALL_HANDS, type HandKey } from "@/domain/cards";
import { PREFLOP_EQUITY_B64 } from "./preflop-equity-data";
import { PREFLOP_TIES_B64 } from "./preflop-ties-data";

export const N_HANDS = 169;
export const HAND_INDEX: Record<HandKey, number> = Object.fromEntries(ALL_HANDS.map((h, i) => [h, i]));

let eqTable: Float64Array | null = null;
let weightTable: Float64Array | null = null;
let tieTable: Float64Array | null = null;

function decodeBase64(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** Full 169x169 matrix: eq[a*169+b] = equity of class a vs class b (ties split). */
export function equityMatrix(): Float64Array {
  if (eqTable) return eqTable;
  const bytes = decodeBase64(PREFLOP_EQUITY_B64);
  const m = new Float64Array(N_HANDS * N_HANDS);
  let k = 0;
  for (let a = 0; a < N_HANDS; a++) {
    m[a * N_HANDS + a] = 0.5;
    for (let b = a + 1; b < N_HANDS; b++) {
      const v = ((bytes[2 * k] ?? 0) | ((bytes[2 * k + 1] ?? 0) << 8)) / 65535;
      m[a * N_HANDS + b] = v;
      m[b * N_HANDS + a] = 1 - v;
      k++;
    }
  }
  eqTable = m;
  return m;
}

/** Full 169x169 matrix: tie[a*169+b] = probability of a split pot between class a and class b (symmetric). */
export function tieMatrix(): Float64Array {
  if (tieTable) return tieTable;
  const bytes = decodeBase64(PREFLOP_TIES_B64);
  const m = new Float64Array(N_HANDS * N_HANDS);
  let k = 0;
  for (let a = 0; a < N_HANDS; a++) {
    for (let b = a; b < N_HANDS; b++) {
      const v = ((bytes[2 * k] ?? 0) | ((bytes[2 * k + 1] ?? 0) << 8)) / 65535;
      m[a * N_HANDS + b] = v;
      m[b * N_HANDS + a] = v;
      k++;
    }
  }
  tieTable = m;
  return m;
}

const RANKS = "AKQJT98765432";
/** Concrete combos (card ids 0..51) of a hand class. */
function combosOf(hand: HandKey): [number, number][] {
  const r1 = RANKS.indexOf(hand[0] ?? ""), r2 = RANKS.indexOf(hand[1] ?? "");
  const out: [number, number][] = [];
  if (hand.length === 2) {
    for (let a = 0; a < 4; a++) for (let b = a + 1; b < 4; b++) out.push([r1 * 4 + a, r1 * 4 + b]);
  } else if (hand.endsWith("s")) {
    for (let s = 0; s < 4; s++) out.push([r1 * 4 + s, r2 * 4 + s]);
  } else {
    for (let a = 0; a < 4; a++) for (let b = 0; b < 4; b++) if (a !== b) out.push([r1 * 4 + a, r2 * 4 + b]);
  }
  return out;
}

/** w[a*169+b] = number of non-overlapping concrete combo pairs (class a, class b). Exact card removal. */
export function pairWeights(): Float64Array {
  if (weightTable) return weightTable;
  const combos = ALL_HANDS.map(combosOf);
  const w = new Float64Array(N_HANDS * N_HANDS);
  for (let a = 0; a < N_HANDS; a++) {
    for (let b = a; b < N_HANDS; b++) {
      let n = 0;
      for (const [x1, x2] of combos[a]!) for (const [y1, y2] of combos[b]!) if (x1 !== y1 && x1 !== y2 && x2 !== y1 && x2 !== y2) n++;
      w[a * N_HANDS + b] = n;
      w[b * N_HANDS + a] = n;
    }
  }
  weightTable = w;
  return w;
}

/** Equity of one hand class vs another, e.g. equity("AKs", "QQ") ≈ 0.46. */
export function handEquity(a: HandKey, b: HandKey): number {
  const i = HAND_INDEX[a], j = HAND_INDEX[b];
  if (i === undefined || j === undefined) throw new Error(`Mão inválida: ${a} / ${b}`);
  return equityMatrix()[i * N_HANDS + j]!;
}
