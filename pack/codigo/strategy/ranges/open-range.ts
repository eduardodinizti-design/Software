/** Range de open de uma posição: tabela do time quando existe, senão a referência (mesma ordem do engine). */
import type { Position } from "@/domain/positions";
import type { StrategyContext } from "@/domain/scenario";
import { nvtOpenRange } from "./nvt-charts";
import { referenceOrFallbackOpenRange } from "./reference-data";
import type { RangeDefinition } from "./types";

export function openRangeFor(ctx: StrategyContext, pos: Position): RangeDefinition {
  return (ctx.format !== "bounty" ? nvtOpenRange(ctx, pos) : null) ?? referenceOrFallbackOpenRange(ctx, pos);
}
