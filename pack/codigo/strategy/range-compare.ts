/**
 * Comparar ranges lado a lado: o mesmo spot (posição, stack, quem agiu antes) em dois contextos de torneio
 * (chip EV × ICM, bolha × mesa final, ICM × PKO…), com as mãos cuja ação principal muda destacadas.
 *
 * Usa exatamente a resposta que o trainer cobra (strategyGrid sobre um cenário do gerador), então carrega
 * todas as regras do motor (corte de 5%, ordem dos pares, empates de EV, suavização, ICM/PKO). Nas mesas
 * de ICM com stacks diferentes, procura a mesa de stacks iguais (o arquivo "iguais" do HRC), para que a
 * diferença mostrada seja só a do contexto e não a da distribuição de stacks.
 */
import { ALL_HANDS, combos, type HandKey } from "@/domain/cards";
import type { Position } from "@/domain/positions";
import { PUSH_FOLD_STACKS, RESTEAL_STACKS, SB_LIMP_STACKS, VS_3BET_STACKS, VS_OPEN_STACKS, STACK_BUCKETS, type DecisionAction, type SpotType, type StackBucket, type StrategicMode, type StrategyContext, type TrainingScenario } from "@/domain/scenario";
import type { TournamentStage } from "@/domain/tournament";
import { generateScenario } from "@/generator/scenario-generator";
import { strategyEngine } from "./engine";
import { nearestSpread, presetFor } from "./preflop-solver/catalog";
import { strategyGrid, type GridCell, type StrategyGrid } from "./strategy-grid";
import type { StrategyDecision } from "./types";
import { familyOf, isFamilyValidated } from "./validation/status";

export interface CompareContext { id: string; label: string; mode: StrategicMode; format: StrategyContext["format"]; stage: TournamentStage }
/** Contextos comparáveis (9-max, os mesmos do pacote de exportação). */
export const COMPARE_CONTEXTS: CompareContext[] = [
  { id: "chip", label: "Chip EV", mode: "chip_ev", format: "regular", stage: "mid" },
  { id: "preitm", label: "ICM · pré-ITM", mode: "icm", format: "regular", stage: "pre_itm" },
  { id: "bubble", label: "ICM · bolha", mode: "icm", format: "regular", stage: "bubble" },
  { id: "ft", label: "ICM · mesa final", mode: "icm", format: "regular", stage: "ft" },
  { id: "pko", label: "PKO (começo/meio)", mode: "pko", format: "pko", stage: "mid" },
  { id: "pko_preitm", label: "PKO + ICM · pré-ITM", mode: "pko_icm", format: "pko", stage: "pre_itm" },
  { id: "pko_bubble", label: "PKO + ICM · bolha", mode: "pko_icm", format: "pko", stage: "bubble" },
  { id: "pko_ft", label: "PKO + ICM · mesa final", mode: "pko_icm", format: "pko", stage: "ft" },
];

export interface CompareSpot { spot: SpotType; label: string; stacks: readonly StackBucket[]; aggressorLabel?: string }
export const COMPARE_SPOTS: CompareSpot[] = [
  { spot: "open_raise", label: "Open (first in)", stacks: STACK_BUCKETS },
  { spot: "open_shove", label: "Push/fold (first in)", stacks: PUSH_FOLD_STACKS },
  { spot: "vs_open_shove", label: "Call vs shove", stacks: PUSH_FOLD_STACKS, aggressorLabel: "Quem deu shove" },
  { spot: "vs_open", label: "Vs open", stacks: VS_OPEN_STACKS, aggressorLabel: "Quem abriu" },
  { spot: "3bet_shove", label: "Resteal (3bet all-in)", stacks: RESTEAL_STACKS, aggressorLabel: "Quem abriu" },
  { spot: "vs_3bet", label: "Vs 3bet", stacks: VS_3BET_STACKS, aggressorLabel: "Quem deu 3bet" },
  { spot: "limp", label: "Blind War (SB first in)", stacks: SB_LIMP_STACKS },
];

/** Mesas sorteadas por busca (cada uma é só montagem de mesa, sem resolver nada). */
const MAX_SEEDS = 600;
const isIcm = (m: StrategicMode) => m === "icm" || m === "pko_icm";
const contextOf = (c: CompareContext, stack: StackBucket): StrategyContext => ({ mode: c.mode, format: c.format, stage: c.stage, players: 9, stack });

function* scenarios(c: CompareContext, spot: SpotType, stack: StackBucket, hero: Position): Generator<TrainingScenario> {
  for (let seed = 1; seed <= MAX_SEEDS; seed++) {
    let s: TrainingScenario;
    try { s = generateScenario({ seed, context: contextOf(c, stack), spot, position: hero }); } catch { return; }
    if (s.spot.heroPosition === hero) yield s;
  }
}

/** Quem pode ter agido antes do herói neste spot (opener, 3bettor ou shover), na ordem da mesa. */
export function aggressorOptions(c: CompareContext, spot: SpotType, stack: StackBucket, hero: Position): Position[] {
  const seen = new Set<Position>();
  for (const s of scenarios(c, spot, stack, hero)) { const a = s.spot.aggressors.at(-1); if (a) seen.add(a); }
  return [...seen];
}

/**
 * Mesa do spot pedido: herói, stack e agressor; no ICM, a de stacks iguais quando existe (o arquivo do HRC
 * escolhido pela distribuição mais próxima), senão a primeira encontrada.
 */
export function findScenario(c: CompareContext, spot: SpotType, stack: StackBucket, hero: Position, aggressor?: Position | null): TrainingScenario | null {
  let first: TrainingScenario | null = null;
  for (const s of scenarios(c, spot, stack, hero)) {
    if (aggressor && s.spot.aggressors.at(-1) !== aggressor) continue;
    if (!isIcm(c.mode) || !presetFor(s) || nearestSpread(s) === "iguais") return s;
    first ??= s;
  }
  return first;
}

export interface CompareSide { scenario: TrainingScenario; grid: StrategyGrid; source: string; validated: boolean }

/** Marcador de "mão sem estratégia neste spot" (o motor não responde por ela). */
const NO_SPOT = { recommended: "fold", frequency: 0, alternatives: [], explanation: "", source: { id: "none", label: "" } } as unknown as StrategyDecision;

/** Lado da comparação, ou null quando o trainer não tem estratégia para o spot nesse contexto. */
export function compareSide(s: TrainingScenario): CompareSide | null {
  let d: StrategyDecision;
  try { d = strategyEngine.decide(s); } catch { return null; }
  const grid = strategyGrid(s, (x) => { try { return strategyEngine.decide(x); } catch { return NO_SPOT; } });
  for (const h of ALL_HANDS) if (grid.cells[h].mix.length === 0 && !grid.cells[h].outOfRange) grid.cells[h].outOfRange = true;
  return { scenario: s, grid, source: d.source.label, validated: isFamilyValidated(familyOf(d, s)) };
}

/** Ação principal da mão (a de maior frequência), ou null se a mão não chega ao spot. */
export function mainAction(c: GridCell): DecisionAction | null {
  if (c.outOfRange || !c.mix.length) return null;
  return c.mix.reduce((a, b) => (b.frequency > a.frequency ? b : a)).action;
}
/** Frequência de jogar (tudo que não é fold). */
export const playFreq = (c: GridCell) => (c.outOfRange ? 0 : c.mix.filter((m) => m.action !== "fold").reduce((a, m) => a + m.frequency, 0));

export interface HandChange { hand: HandKey; from: DecisionAction | null; to: DecisionAction | null; playDelta: number }
export interface RangeDiff {
  changes: HandChange[];
  /** Combos (de 1326) cuja ação principal muda. */
  changedCombos: number;
  /** % de combos jogados (não fold) em cada lado. */
  playA: number; playB: number;
}

/**
 * Diferença entre dois lados: mãos cuja ação principal muda (ordenadas pela variação de frequência de jogo,
 * maior primeiro) e o % do range jogado em cada lado. Mãos que não chegam ao spot nos dois lados ficam de fora.
 */
export function diffGrids(a: StrategyGrid, b: StrategyGrid): RangeDiff {
  const changes: HandChange[] = [];
  let changed = 0, wa = 0, wb = 0, den = 0;
  for (const h of ALL_HANDS) {
    const ca = a.cells[h], cb = b.cells[h];
    if (ca.outOfRange && cb.outOfRange) continue;
    const k = combos(h); den += k;
    const pa = playFreq(ca), pb = playFreq(cb);
    wa += pa * k; wb += pb * k;
    const fa = mainAction(ca), fb = mainAction(cb);
    if (fa !== fb) { changes.push({ hand: h, from: fa, to: fb, playDelta: pb - pa }); changed += k; }
  }
  changes.sort((x, y) => Math.abs(y.playDelta) - Math.abs(x.playDelta));
  return { changes, changedCombos: changed, playA: den ? (wa / den) * 100 : 0, playB: den ? (wb / den) * 100 : 0 };
}
