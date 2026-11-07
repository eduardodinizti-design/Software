import type { Card, HandKey } from "./cards";
import { openingPositions, tablePositions, type Position, type TableSize } from "./positions";
import type { TableState } from "./table";
import type { TournamentContext, TournamentFormat, TournamentStage } from "./tournament";

export type SpotType =
  | "open_raise"
  | "open_shove"
  | "vs_open_shove"
  | "limp"
  | "vs_limp"
  | "limp_call"
  | "limp_reraise"
  | "3bet_shove"
  | "4bet_shove"
  | "check_raise"
  | "postflop"
  | "vs_open"
  | "vs_3bet"
  | "3bet"
  | "4bet"
  | "squeeze"
  | "bb_defense"
  | "sb_vs_bb"
  | "push_fold";

export const SPOT_TYPES: { v: SpotType; label: string; implemented: boolean }[] = [
  { v: "open_raise", label: "Open Raise", implemented: true },
  { v: "open_shove", label: "Open Shove", implemented: true },
  { v: "vs_open_shove", label: "Vs Open Shove", implemented: true },
  { v: "limp", label: "SB Limp/Raise (Blind War)", implemented: true },
  { v: "vs_limp", label: "BB vs Limp (Blind War)", implemented: true },
  { v: "limp_call", label: "SB Limp vs Iso (Blind War)", implemented: true },
  { v: "limp_reraise", label: "Limp/Reraise", implemented: false },
  { v: "3bet_shove", label: "Resteal (3Bet Shove)", implemented: true },
  { v: "4bet_shove", label: "4Bet Shove", implemented: false },
  { v: "check_raise", label: "Check-Raise", implemented: false },
  { v: "postflop", label: "Pós-flop", implemented: false },
  { v: "vs_open", label: "Vs Open (fold, call, 3bet)", implemented: true },
  { v: "vs_3bet", label: "Vs 3Bet (fold, call, 4bet)", implemented: true },
  { v: "3bet", label: "3Bet", implemented: false },
  { v: "4bet", label: "4Bet", implemented: false },
  { v: "squeeze", label: "Squeeze", implemented: false },
  { v: "bb_defense", label: "BB Defense", implemented: false },
  { v: "sb_vs_bb", label: "SB vs BB", implemented: false },
  { v: "push_fold", label: "Push/Fold", implemented: false },
];

export interface Spot {
  type: SpotType;
  heroPosition: Position;
  /** Positions of players who already acted aggressively (empty for open raise). */
  aggressors: Position[];
}

/** Stack buckets the strategy layer has ranges for. */
export type StackBucket = 100 | 40 | 25 | 20 | 15 | 12 | 10 | 8 | 5;
/** Open raise (reference ranges). Also the legacy default for random contexts. */
export const STACK_BUCKETS: StackBucket[] = [100, 40, 25, 15];
/** Push/fold spots (Nash chip EV). */
export const PUSH_FOLD_STACKS: StackBucket[] = [15, 12, 10, 8, 5];
export const ALL_STACK_BUCKETS: StackBucket[] = [100, 40, 25, 20, 15, 12, 10, 8, 5];
/** Resteal (3bet shove vs open): stacks where shove-or-fold over an open is standard. */
export const RESTEAL_STACKS: StackBucket[] = [25, 20, 15, 12];
/** Open size used by the opener in resteal spots (BB). */
export const RESTEAL_OPEN_SIZE = 2;
/** Blind War com limp: 25bb (ranges do HRC; sem eles, tabela NVT da SB 25bb). */
export const SB_LIMP_STACKS: StackBucket[] = [25];
/** Iso-raise do BB contra o limp da SB (BB total): 3x, o size mais comum na teoria (Reg Life, Blind War). */
export const BB_ISO_SIZE = 3;
/** Vs Open: stacks com referência (100/40 deep, 25/15 com shove calculado pelo Nash). */
export const VS_OPEN_STACKS: StackBucket[] = [100, 40, 25, 15];
/** Vs 3Bet: o herói abriu e tomou 3bet (com 15bb não existe 3bet não all-in). */
export const VS_3BET_STACKS: StackBucket[] = [100, 40, 25];
/**
 * Tamanho do open (BB total) nos spots de reação: 2,5x com 100bb; 2x com 40bb ou menos, o mesmo open do
 * solver pré-flop (assim a 3bet e a resposta mostradas na mesa são as que o solver resolveu).
 */
export function openSizeFor(stack: number): number {
  return stack >= 100 ? 2.5 : 2;
}
/**
 * Tamanho da 3bet em múltiplos do open (teoria de MTT): em posição menor, fora de posição maior,
 * do BB maior ainda; com 15bb a 3bet é all-in.
 */
export function threeBetMultiplier(stack: number, who: "ip" | "sb" | "bb"): number {
  const t = stack >= 100 ? { ip: 3.75, sb: 4.75, bb: 5.1 } : stack >= 40 ? { ip: 3.1, sb: 3.6, bb: 4.6 } : { ip: 2.5, sb: 2.9, bb: 3.4 };
  return t[who];
}
/** Spots de reação com range de referência (vs open, vs 3bet). */
export const isReactionSpot = (spot: SpotType) => spot === "vs_open" || spot === "vs_3bet";
/** Spots da SB com limp (Blind War). */
export const isSbLimpSpot = (spot: SpotType) => spot === "limp" || spot === "limp_call";
/** Spots da Blind War com limp (SB e BB contra o limp): 25bb, ranges do HRC. */
export const isLimpTreeSpot = (spot: SpotType) => isSbLimpSpot(spot) || spot === "vs_limp";

const PUSH_FOLD_SPOTS: SpotType[] = ["open_shove", "vs_open_shove", "3bet_shove"];
export const isPushFoldSpot = (spot: SpotType) => PUSH_FOLD_SPOTS.includes(spot);
/** Stack buckets a spot can be trained at. */
export function spotStacks(spot: SpotType): StackBucket[] {
  if (spot === "vs_open") return VS_OPEN_STACKS;
  if (spot === "vs_3bet") return VS_3BET_STACKS;
  return isLimpTreeSpot(spot) ? SB_LIMP_STACKS : spot === "3bet_shove" ? RESTEAL_STACKS : isPushFoldSpot(spot) ? PUSH_FOLD_STACKS : STACK_BUCKETS;
}
/** Seats hero can occupy in this spot (vs_open_shove: anyone who can face a first-in shove, incl. BB). */
export function heroPositions(spot: SpotType, players: TableSize): Position[] {
  if (isSbLimpSpot(spot)) return players >= 3 ? ["SB"] : [];
  if (spot === "vs_limp") return players >= 3 ? ["BB"] : [];
  if (spot === "vs_3bet") return players >= 2 ? openingPositions(players) : [];
  return spot === "vs_open_shove" || spot === "3bet_shove" || spot === "vs_open" ? tablePositions(players).slice(1) : openingPositions(players);
}
/** Who can be the first-in aggressor before hero (shover in vs_open_shove, opener in 3bet_shove). */
export function shoverPositions(players: TableSize, hero: Position): Position[] {
  const order = tablePositions(players);
  return openingPositions(players).filter((p) => order.indexOf(p) < order.indexOf(hero));
}
/** Agressor do spot: antes do herói (shove/open) ou, no vs 3bet, quem fala depois dele e deu a 3bet. */
export function aggressorPositions(spot: SpotType, players: TableSize, hero: Position): Position[] {
  if (spot === "vs_3bet") {
    const order = tablePositions(players);
    return order.slice(order.indexOf(hero) + 1);
  }
  return shoverPositions(players, hero);
}
/** Hero's legal actions per spot. */
/** Open raise com stack até este tamanho oferece também o all-in (estratégia mista raise + shove). */
export const OPEN_SHOVE_MAX_STACK = 15;
export function spotLegalActions(spot: SpotType, stack?: number, mode?: StrategicMode, position?: string): DecisionAction[] {
  if (spot === "limp") return ["fold", "limp", "raise", "all_in"];
  if (spot === "open_raise" && stack !== undefined && stack <= OPEN_SHOVE_MAX_STACK) return ["fold", "raise", "all_in"];
  // Com 25bb em ICM/PKO o solver pré-flop também dá open shove.
  if (spot === "open_raise" && stack !== undefined && stack <= 25 && ((mode && mode !== "chip_ev") || position === "SB")) return ["fold", "raise", "all_in"];
  if (spot === "limp_call") return ["fold", "call", "all_in"];
  if (spot === "vs_limp") return ["check", "raise", "all_in"];
  if (spot === "vs_open") return stack !== undefined && stack <= 15 ? ["fold", "call", "all_in"] : stack !== undefined && stack <= 40 ? ["fold", "call", "three_bet", "all_in"] : ["fold", "call", "three_bet"];
  if (spot === "vs_3bet") return stack !== undefined && stack >= 100 ? ["fold", "call", "four_bet"] : ["fold", "call", "all_in"];
  return spot === "open_shove" || spot === "3bet_shove" ? ["fold", "all_in"] : spot === "vs_open_shove" ? ["fold", "call"] : ["fold", "raise"];
}
/** Spots where an earlier player already acted aggressively (encoded in the scenario ID). */
export const hasAggressor = (spot: SpotType) => spot === "vs_open_shove" || spot === "3bet_shove" || spot === "vs_open" || spot === "vs_3bet";

/** Coarse key used to look up a strategy. Kept separate from the full table state. */
export interface StrategyContext {
  /** Absent only on legacy scenarios/ranges; those represent reference chip EV. */
  mode?: StrategicMode;
  format: TournamentFormat;
  stage: TournamentStage;
  players: TableSize;
  stack: StackBucket;
}

export const STRATEGIC_MODES = ["chip_ev", "icm", "pko", "pko_icm"] as const;
export type StrategicMode = typeof STRATEGIC_MODES[number];
export type DecisionAction = "fold" | "call" | "raise" | "all_in" | "three_bet" | "three_bet_shove" | "four_bet" | "four_bet_shove" | "limp" | "check";

export interface TrainingScenario {
  scenarioId: string;
  seed: number;
  spot: Spot;
  table: TableState;
  hero: { cards: [Card, Card]; hand: HandKey };
  tournament: TournamentContext;
  context: StrategyContext;
  /** Actions hero may choose here. */
  legalActions: DecisionAction[];
  /**
   * Exploit: a resposta certa é a melhor resposta aos vilões da mesa (perfil e stats, `domain/villain.ts`), não o
   * equilíbrio. Marcado pela sessão na hora de decidir; não faz parte do scenarioId (a mão é a mesma).
   */
  exploit?: boolean;
}
