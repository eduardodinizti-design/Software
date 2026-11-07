import { cellHand, combos, TOTAL_COMBOS, type HandKey } from "@/domain/cards";

/** % of all 1326 combos covered, weighted by frequency. */
export function rangePercent(hands: Record<HandKey, number>): number {
  let c = 0;
  for (const [h, f] of Object.entries(hands)) c += combos(h) * f;
  return (c / TOTAL_COMBOS) * 100;
}

export const setToHands = (set: Iterable<HandKey>): Record<HandKey, number> =>
  Object.fromEntries([...set].map((h) => [h, 1]));

/**
 * "Range edge": hands where the decision flips. A hand is on the edge when it is
 * mixed (0 < f < 1) or when a neighbouring cell of the 13x13 grid (up/down/left/right)
 * is in the range while it is not, or vice versa. Works for any range (reference or manual).
 */
export function rangeEdgeHands(hands: Record<HandKey, number>): Set<HandKey> {
  const inRange = (i: number, j: number) => (hands[cellHand(i, j)] ?? 0) > 0;
  const edge = new Set<HandKey>();
  for (let i = 0; i < 13; i++) {
    for (let j = 0; j < 13; j++) {
      const h = cellHand(i, j);
      const f = hands[h] ?? 0;
      if (f > 0 && f < 1) { edge.add(h); continue; }
      const me = f > 0;
      const neighbours: [number, number][] = [[i - 1, j], [i + 1, j], [i, j - 1], [i, j + 1]];
      if (neighbours.some(([a, b]) => a >= 0 && a < 13 && b >= 0 && b < 13 && inRange(a, b) !== me)) edge.add(h);
    }
  }
  return edge;
}
