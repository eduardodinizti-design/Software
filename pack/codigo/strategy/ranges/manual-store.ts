/** User-edited ("manual") ranges persisted in this browser. */
import type { Position } from "@/domain/positions";
import type { SpotType, StrategyContext } from "@/domain/scenario";
import { rangeId, type RangeDefinition } from "./types";

const KEY = "poker-trainer-ranges-v2";
const LEGACY_KEY = "poker-trainer-ranges-v1";
export const MANUAL_VERSION = "manual-1";

type Store = Record<string, RangeDefinition>;

function migrateLegacy(): Store {
  const out: Store = {};
  try {
    const old = JSON.parse(localStorage.getItem(LEGACY_KEY) || "{}") as Record<string, string[]>;
    for (const [k, hands] of Object.entries(old)) {
      const [fmt, players, stage, stack, pos] = k.split("|");
      const ctx: StrategyContext = {
        format: fmt === "pku" ? "pko" : "regular",
        players: Number(players) as StrategyContext["players"],
        stage: stage as StrategyContext["stage"],
        stack: Number(stack) as StrategyContext["stack"],
      };
      const def = build("open_raise", ctx, pos as Position, Object.fromEntries(hands.map((h) => [h, 1])));
      out[def.id] = def;
    }
  } catch { /* ignore */ }
  return out;
}

function read(): Store {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw);
    const migrated = migrateLegacy();
    localStorage.setItem(KEY, JSON.stringify(migrated));
    return migrated;
  } catch {
    return {};
  }
}

const write = (s: Store) => localStorage.setItem(KEY, JSON.stringify(s));

function build(spot: SpotType, ctx: StrategyContext, pos: Position, hands: Record<string, number>): RangeDefinition {
  return { id: rangeId(spot, ctx, pos), spot, action: "raise", position: pos, context: ctx, hands, source: "manual", version: MANUAL_VERSION };
}

export const manualStore = {
  get(spot: SpotType, ctx: StrategyContext, pos: Position): RangeDefinition | null {
    return read()[rangeId(spot, ctx, pos)] ?? null;
  },
  save(spot: SpotType, ctx: StrategyContext, pos: Position, hands: Record<string, number>) {
    const s = read();
    const def = build(spot, ctx, pos, hands);
    s[def.id] = def;
    write(s);
    return def;
  },
  put(def: RangeDefinition) {
    const s = read();
    s[def.id] = { ...def, source: "manual" };
    write(s);
  },
  remove(spot: SpotType, ctx: StrategyContext, pos: Position) {
    const s = read();
    delete s[rangeId(spot, ctx, pos)];
    write(s);
  },
  all: (): RangeDefinition[] => Object.values(read()),
};
