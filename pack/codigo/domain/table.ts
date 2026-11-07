import type { Position, TableSize } from "./positions";
import type { TournamentFormat } from "./tournament";

/** Blinds are expressed in big blinds (bb = 1). Chip values are only set when a real structure is configured. */
export interface Blinds {
  sb: number;
  bb: number;
  /** Total ante in BB (BB-ante model: paid by the BB). */
  ante: number;
  anteType: "bb-ante" | "none";
  /** Chip value of 1 BB, or null when no real blind level is configured. */
  bbChips: number | null;
}

export type ActionType = "post_ante" | "post_sb" | "post_bb" | "fold" | "call" | "limp" | "raise" | "all_in" | "check" | "bet";

export interface ActionRecord {
  seat: number;
  position: Position;
  type: ActionType;
  /** BB put in by this action (0 for fold/check). */
  amount: number;
  street: "preflop";
}

export interface PlayerState {
  seat: number;
  position: Position;
  name: string;
  /** Chips, or null when no real chip structure is configured. */
  stackChips: number | null;
  stackBb: number;
  /** Current bounty value (same currency as the payouts), or null when not configured / not applicable. */
  bounty: number | null;
  /** PKO model: bounty in units of the starting bounty (bounty = multiplier × startingBounty). */
  bountyMultiplier?: number;
  isHero: boolean;
  status: "active" | "folded" | "all_in";
}

export interface TableState {
  size: TableSize;
  format: TournamentFormat;
  blinds: Blinds;
  players: PlayerState[];
  heroSeat: number;
  /** Preflop history up to the current decision. Single source for playback. */
  actions: ActionRecord[];
  pot: number;
}

export type Coverage = "hero_covers" | "hero_covered" | "equal";

export function getHero(t: TableState): PlayerState {
  return t.players.find((p) => p.seat === t.heroSeat)!;
}

/** Whether hero covers (has at least as many chips as) the given player. */
export function coverageVs(t: TableState, seat: number): Coverage | null {
  if (seat === t.heroSeat) return null;
  const hero = getHero(t);
  const other = t.players.find((p) => p.seat === seat);
  if (!other) return null;
  if (hero.stackBb === other.stackBb) return "equal";
  return hero.stackBb > other.stackBb ? "hero_covers" : "hero_covered";
}

/** Stacks within this relative difference are considered "similar". */
export const SIMILAR_STACK_TOLERANCE = 0.1;

export function isSimilarStack(t: TableState, seat: number): boolean {
  const hero = getHero(t);
  const other = t.players.find((p) => p.seat === seat);
  if (!other || other.isHero) return false;
  return Math.abs(hero.stackBb - other.stackBb) / Math.max(hero.stackBb, other.stackBb) <= SIMILAR_STACK_TOLERANCE;
}

/** Effective stack (BB) between hero and the deepest still-active opponent. */
export function effectiveStackBb(t: TableState): number {
  const hero = getHero(t);
  const others = t.players.filter((p) => !p.isHero && p.status !== "folded");
  const deepest = Math.max(0, ...others.map((p) => p.stackBb));
  return Math.round(Math.min(hero.stackBb, deepest) * 10) / 10;
}
