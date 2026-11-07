/**
 * Reference ("NVT Range") open-raise profile as pure data.
 * Approximations for study — NOT solver output. Replace by importing real ranges.
 */
import { combos, TOTAL_COMBOS, type HandKey } from "@/domain/cards";
import { isLatePosition, type Position } from "@/domain/positions";
import type { StrategyContext } from "@/domain/scenario";
import { rangeId, type RangeDefinition } from "./types";

export const REFERENCE_VERSION = "nvt-approx-0.2";

export const OPEN_PROFILE = {
  basePct: { UTG: 15, "UTG+1": 17, "UTG+2": 19, LJ: 22, HJ: 27, CO: 34, BTN: 48, SB: 45, BB: 0 } as Record<Position, number>,
  headsUp: { default: 80, shortStack: 60, shortStackMaxBb: 15 },
  formatMult: { regular: 1, pko: 1.1 },
  stageMult: {
    early: { early: 1, late: 1 },
    mid: { early: 1, late: 1.05 },
    pre_itm: { early: 0.85, late: 0.92 },
    bubble: { early: 0.75, late: 0.85 },
    ft: { early: 0.8, late: 0.9 },
  },
  // 12bb e abaixo não são treinados como open raise (viram push/fold); valores só por completude de tipo.
  stackMult: { 100: 1, 40: 1, 25: 0.92, 20: 0.86, 15: 0.8, 12: 0.75, 10: 0.7, 8: 0.65, 5: 0.6 },
  clamp: { min: 5, max: 90 },
} as const;

/**
 * Open-raise priority: the 169 hands ordered by how early they enter a
 * first-in raising range. Hand-authored from the nesting seen in common
 * MTT chip-EV RFI charts (BB ante, 100bb): pairs and suited aces enter
 * early, suited connectors before weak offsuit broadways, offsuit trash last.
 * Each line is roughly one positional step (UTG → … → BTN → HU).
 * Approximation for study, NOT solver output.
 */
const OPEN_PRIORITY_ROWS = [
  "AA KK QQ AKs JJ AQs AKo TT AJs KQs AQo ATs 99 KJs",
  "88 AJo KQo A5s QJs KTs A9s 77 JTs QTs A8s A4s A7s",
  "66 A3s A6s K9s T9s ATo 55 KJo A2s J9s Q9s",
  "44 98s K8s QJo 33 87s 22",
  "KTo K7s T8s A9o 76s 65s",
  "K6s Q8s J8s QTo 97s 54s K5s JTo A8o 86s",
  "Q7s A7o K4s A5o T7s K9o 75s K3s A6o Q6s 64s K2s A4o Q9o J9o T9o",
  "A3o Q5s K8o J7s 96s A2o 53s Q4s T6s 85s Q8o 74s K7o Q3s J8o 98o 43s Q2s T8o K6o J6s 63s K5o 87o J5s J4s",
  "K4o 95s Q7o 52s T5s K3o 76o 84s J7o 42s T4s K2o 97o 73s Q6o T7o 86o J3s 65o 32s T3s Q5o 62s J2s 94s 75o T2s Q4o 54o J6o 93s 96o Q3o 64o 85o 92s J5o T6o Q2o 83s 82s 53o J4o 72s 74o 43o T5o J3o 95o 63o J2o 84o T4o 52o T3o 42o 94o 73o 93o T2o 62o 32o 92o 83o 82o 72o",
];

export const OPEN_PRIORITY: HandKey[] = OPEN_PRIORITY_ROWS.join(" ").split(" ");

/** Kept for compatibility: hands ordered from first to last to enter an open range. */
export const HANDS_BY_STRENGTH = OPEN_PRIORITY;

/** Smallest frequency kept for the boundary hand; below this it is dropped. */
const MIN_BOUNDARY_FREQ = 0.1;

export function topPercent(pct: number): Set<HandKey> {
  const target = (pct / 100) * TOTAL_COMBOS;
  const set = new Set<HandKey>();
  let acc = 0;
  for (const h of HANDS_BY_STRENGTH) {
    if (acc >= target) break;
    set.add(h);
    acc += combos(h);
  }
  return set;
}

/**
 * Top-X% range with an exact size: every hand fully in, except the boundary
 * hand, which gets the fractional frequency (step 0.05) needed to hit the
 * target. That boundary hand is a genuine mixed spot (both actions accepted).
 */
export function weightedTopPercent(pct: number): Record<HandKey, number> {
  const target = (pct / 100) * TOTAL_COMBOS;
  const hands: Record<HandKey, number> = {};
  let acc = 0;
  for (const h of OPEN_PRIORITY) {
    const c = combos(h);
    if (acc + c <= target + 1e-9) {
      hands[h] = 1;
      acc += c;
      continue;
    }
    const f = Math.round(((target - acc) / c) * 20) / 20;
    if (f >= MIN_BOUNDARY_FREQ) hands[h] = Math.min(1, f);
    break;
  }
  return hands;
}

/** Contexts that have their own reference data (Bounty does not). */
export type ReferenceContext = StrategyContext & { format: "regular" | "pko" };

export function referenceOpenPercent(ctx: ReferenceContext, pos: Position): number {
  const P = OPEN_PROFILE;
  if (ctx.players === 2) return ctx.stack <= P.headsUp.shortStackMaxBb ? P.headsUp.shortStack : P.headsUp.default;
  const late = isLatePosition(pos) ? "late" : "early";
  const p = P.basePct[pos] * P.formatMult[ctx.format] * P.stageMult[ctx.stage][late] * P.stackMult[ctx.stack];
  return Math.min(P.clamp.max, Math.max(P.clamp.min, Math.round(p * 10) / 10));
}

export function referenceOpenRange(ctx: ReferenceContext, pos: Position): RangeDefinition {
  const hands = weightedTopPercent(referenceOpenPercent(ctx, pos));
  return {
    id: rangeId("open_raise", ctx, pos),
    spot: "open_raise",
    action: "raise",
    position: pos,
    context: ctx,
    hands,
    source: "nvt_range",
    version: REFERENCE_VERSION,
    notes: "Aproximação de referência, não saída de solver.",
  };
}

/**
 * Range for any context. Bounty has no reference data yet, so it temporarily
 * uses the PKO reference, explicitly tagged as PKO_REFERENCE_FALLBACK.
 */
export function referenceOrFallbackOpenRange(ctx: StrategyContext, pos: Position): RangeDefinition {
  if (ctx.format !== "bounty") return referenceOpenRange(ctx as ReferenceContext, pos);
  const pko = referenceOpenRange({ ...ctx, format: "pko" }, pos);
  return {
    ...pko,
    id: rangeId("open_raise", ctx, pos),
    context: ctx,
    source: "pko_reference_fallback",
    notes: "Bounty sem range próprio: usando range PKO de referência como fallback temporário.",
  };
}
