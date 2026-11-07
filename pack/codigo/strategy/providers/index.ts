import { manualStore, MANUAL_VERSION } from "../ranges/manual-store";
import { NVT_TEAM_VERSION, nvtOpenRange } from "../ranges/nvt-charts";
import { REFERENCE_VERSION, referenceOrFallbackOpenRange } from "../ranges/reference-data";
import type { StrategyProvider } from "../types";
import { decisionFromRange } from "./range-decision";

/** User-edited ranges. Returns null when the user has no custom range for the spot. */
export const manualProvider: StrategyProvider = {
  source: { id: "manual", label: "Range personalizado", version: MANUAL_VERSION },
  supports: (spot) => spot === "open_raise",
  decide(s) {
    if (s.context.mode && s.context.mode !== "chip_ev") return null;
    const r = manualStore.get(s.spot.type, s.context, s.spot.heroPosition);
    return r ? decisionFromRange(s, r, this.source) : null;
  },
};

/** Tabelas do NVT Poker Team (open 2.5x por posição); onde não há tabela, cai no range de referência. */
export const nvtTeamProvider: StrategyProvider = {
  source: { id: "nvt_team", label: "Tabela NVT (time)", version: NVT_TEAM_VERSION },
  supports: (spot) => spot === "open_raise",
  decide(s) {
    if (s.context.mode && s.context.mode !== "chip_ev") return null;
    if (s.context.format === "bounty") return null;
    const r = nvtOpenRange(s.context, s.spot.heroPosition);
    return r ? decisionFromRange(s, r, this.source) : null;
  },
};

/** Built-in reference ranges. */
export const nvtRangeProvider: StrategyProvider = {
  source: { id: "nvt_range", label: "Range de referência", version: REFERENCE_VERSION },
  supports: (spot) => spot === "open_raise",
  decide(s) {
    if (s.context.mode && s.context.mode !== "chip_ev") return null;
    const range = referenceOrFallbackOpenRange(s.context, s.spot.heroPosition);
    const source = range.source === "pko_reference_fallback" ? PKO_FALLBACK_SOURCE : this.source;
    return decisionFromRange(s, range, source);
  },
};

export const PKO_FALLBACK_SOURCE = {
  id: "pko_reference_fallback",
  label: "Fallback: range PKO de referência",
  version: REFERENCE_VERSION,
} as const;

// Future providers (solver, icm, pko) plug in here implementing StrategyProvider.
