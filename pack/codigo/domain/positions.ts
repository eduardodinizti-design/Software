export type Position = "UTG" | "UTG+1" | "UTG+2" | "LJ" | "HJ" | "CO" | "BTN" | "SB" | "BB";
export type TableSize = 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2;
export const TABLE_SIZES: TableSize[] = [9, 8, 7, 6, 5, 4, 3, 2];

const PREFLOP_ORDER: Position[] = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB"];

/** Seats that can open (everyone but the BB), in preflop action order. */
export function openingPositions(players: TableSize): Position[] {
  if (players === 2) return ["SB"];
  return PREFLOP_ORDER.slice(PREFLOP_ORDER.length - (players - 1));
}

/** Every seat at the table in preflop action order (BB last). */
export function tablePositions(players: TableSize): Position[] {
  return [...openingPositions(players), "BB"];
}

export const isLatePosition = (p: Position) => p === "CO" || p === "BTN" || p === "SB";
