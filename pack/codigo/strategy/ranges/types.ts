import type { HandKey } from "@/domain/cards";
import type { Position } from "@/domain/positions";
import type { SpotType, StrategyContext } from "@/domain/scenario";
import type { BetSize, StrategySourceId } from "../types";

/**
 * Serializable range: hand -> frequency (0..1) of the range's action.
 * Hands not listed have frequency 0. Designed to be imported from JSON/CSV/API.
 */
export interface RangeDefinition {
  id: string;
  spot: SpotType;
  /** Action this range represents (e.g. "raise" for an open range). */
  action: "raise" | "call" | "all_in" | "three_bet" | "three_bet_shove" | "four_bet" | "four_bet_shove" | "limp";
  betSize?: BetSize;
  position: Position;
  context: StrategyContext;
  hands: Record<HandKey, number>;
  source: StrategySourceId;
  version: string;
  notes?: string;
}

export function rangeId(spot: SpotType, ctx: StrategyContext, pos: Position) {
  const legacyKey = `${spot}|${ctx.format}|${ctx.players}|${ctx.stage}|${ctx.stack}|${pos}`;
  return !ctx.mode || ctx.mode === "chip_ev" ? legacyKey : `${legacyKey}|${ctx.mode}`;
}
