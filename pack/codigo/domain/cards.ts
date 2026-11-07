/** Cards, hand keys and combinatorics. Pure, UI-agnostic. */
export const RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"] as const;
export const SUITS = ["s", "h", "d", "c"] as const;
export type Rank = (typeof RANKS)[number];
export type Suit = (typeof SUITS)[number];
/** Two-char card, e.g. "As", "Td". */
export type Card = string;
/** Canonical 169-hand key, e.g. "AKs", "72o", "QQ". */
export type HandKey = string;

const VAL: Record<string, number> = { A: 14, K: 13, Q: 12, J: 11, T: 10, "9": 9, "8": 8, "7": 7, "6": 6, "5": 5, "4": 4, "3": 3, "2": 2 };
export const rankValue = (r: string | undefined) => VAL[r ?? ""] ?? 0;
const R = (i: number) => RANKS[i] ?? "";

/** Hand key at grid cell (row i, col j). Upper triangle suited, lower offsuit. */
export function cellHand(i: number, j: number): HandKey {
  if (i === j) return R(i) + R(j);
  return i < j ? R(i) + R(j) + "s" : R(j) + R(i) + "o";
}

export const ALL_HANDS: HandKey[] = (() => {
  const out: string[] = [];
  for (let i = 0; i < 13; i++) for (let j = 0; j < 13; j++) out.push(cellHand(i, j));
  return out;
})();

export const TOTAL_COMBOS = 1326;

export function combos(hand: HandKey): number {
  if (hand.length === 2) return 6;
  return hand.endsWith("s") ? 4 : 12;
}

export function fullDeck(): Card[] {
  const d: Card[] = [];
  for (const r of RANKS) for (const s of SUITS) d.push(r + s);
  return d;
}

/** Orders two cards high-first and returns the canonical hand key. */
export function toHandKey(a: Card, b: Card): { cards: [Card, Card]; key: HandKey } {
  const [hi, lo]: [Card, Card] = rankValue(a[0]) >= rankValue(b[0]) ? [a, b] : [b, a];
  let key = hi.slice(0, 1) + lo.slice(0, 1);
  if (hi[0] !== lo[0]) key += hi[1] === lo[1] ? "s" : "o";
  return { cards: [hi, lo], key };
}

export type HandCategory =
  | "pares_altos" | "pares_medios" | "pares_baixos"
  | "ases_suited" | "ases_offsuit"
  | "broadway_suited" | "broadway_offsuit"
  | "conectores_suited" | "suited_outros" | "offsuit_outros";

export const HAND_CATEGORY_LABEL: Record<HandCategory, string> = {
  pares_altos: "Pares altos (TT+)",
  pares_medios: "Pares médios (66–99)",
  pares_baixos: "Pares baixos (22–55)",
  ases_suited: "Ases suited",
  ases_offsuit: "Ases offsuit",
  broadway_suited: "Broadways suited",
  broadway_offsuit: "Broadways offsuit",
  conectores_suited: "Conectores/gappers suited",
  suited_outros: "Outras suited",
  offsuit_outros: "Outras offsuit",
};

/** Coarse study category of a 169-hand key (e.g. "A5s" → ases_suited). */
export function handCategory(hand: HandKey): HandCategory {
  const a = rankValue(hand[0]), b = rankValue(hand[1]);
  if (hand.length === 2) return a >= 10 ? "pares_altos" : a >= 6 ? "pares_medios" : "pares_baixos";
  const suited = hand.endsWith("s");
  if (a === 14) return suited ? "ases_suited" : "ases_offsuit";
  if (b >= 10) return suited ? "broadway_suited" : "broadway_offsuit";
  if (suited) return a - b <= 2 ? "conectores_suited" : "suited_outros";
  return "offsuit_outros";
}
