import type { DecisionAction, SpotType, TrainingScenario } from "@/domain/scenario";
import type { RangeDefinition } from "./ranges/types";

export type StrategySourceId = "nvt_team" | "nvt_range" | "manual" | "solver" | "icm" | "pko" | "pko_reference_fallback" | "nash_pushfold";

export interface StrategySourceInfo {
  id: StrategySourceId;
  label: string;
  version: string;
}

export interface ActionFrequency {
  action: DecisionAction;
  betSize?: BetSize;
  /** 0..1 */
  frequency: number;
}

export interface StrategyDecision {
  recommended: DecisionAction;
  frequency: number;
  alternatives: ActionFrequency[];
  explanation: string;
  range: RangeDefinition;
  source: StrategySourceInfo;
  recommendedBetSize?: BetSize;
  theoryTags?: string[];
  /** EV de cada ação legal relativo ao fold (só fontes que calculam EV, ex.: Nash push/fold). */
  actionEvs?: { action: DecisionAction; ev: number }[];
  evUnit?: "bb" | "pct";
  /** Leitura dos vilões: como os stats mudaram o range deles e a resposta certa (exploit) contra o equilíbrio. */
  villainRead?: VillainRead;
  /**
   * A decisão certa não está entre as opções do drill (ex.: mão de raise no treino de push/fold). Qualquer resposta
   * é aceita e não soma EV perdido; o texto explica.
   */
  outsideDrill?: string;
}

export interface VillainReadLine {
  seat: number; position: string; name: string; profile: string;
  /** Stat usado ("Fold para 3-Bet", "Steal"), valor do vilão e referência (Regular médio). */
  stat: string; value: number; ref: number;
  /** O que o stat muda: % do range que paga (ou empurra, ou dá 3bet) no equilíbrio e contra este vilão. */
  verb: "paga" | "empurra" | "dá 3bet com"; gtoPct: number; exploitPct: number;
}
export interface VillainRead {
  lines: VillainReadLine[];
  /** Resposta do equilíbrio para a mão do herói (frequência da ação agressiva/call e EV contra o fold). */
  gto: { frequency: number; ev: number };
  exploit: { frequency: number; ev: number };
  action: DecisionAction;
  /** Rótulos prontos quando há mais de uma ação além do fold (vs 3bet: "Call", "All-in", "Fold"). */
  labels?: { gto: string; exploit: string };
  /** EV de cada ação contra o fold: no equilíbrio e contra este vilão (vs 3bet). */
  options?: { action: DecisionAction; label: string; gto: number; exploit: number }[];
  /** Range do vilão por mão (ordem ALL_HANDS): equilíbrio do HRC e o do modelo para este vilão. */
  villainRange?: { title: string; gto: number[]; exploit: number[] };
  /** "A partir de qual mão": para a família da mão do herói, contra cada perfil. */
  profileTable?: { label: string; stat: number; call: string; allIn: string; hero: string }[];
  /** Premissas do cálculo, em uma frase. */
  note?: string;
}

/** Only populated by a strategy that actually supplies a size. */
export type BetSize = { sizeBB: number; sizeOpenMultiplier?: never } | { sizeOpenMultiplier: number; sizeBB?: never };
export type Correctness = "CORRECT" | "ACCEPTABLE_MIXED_ACTION" | "STRATEGIC_ERROR" | "TIMEOUT";

export interface StrategyProvider {
  source: StrategySourceInfo;
  supports(spot: SpotType): boolean;
  /** Return null when this provider has no strategy for the scenario (engine falls through). */
  decide(s: TrainingScenario): StrategyDecision | null;
  /** Opcional: só a fonte que responderia (sem calcular), para a trava de validação. null = este provider não responde. */
  probe?(s: TrainingScenario): SourceProbe | null;
}
/** Fonte de uma decisão sem a decisão: o que `familyOf` precisa (fonte, id do range e modo). */
export interface SourceProbe { source: StrategySourceInfo; rangeId: string; mode: string }

export interface GradeResult {
  correct: boolean;
  chosen: DecisionAction;
  chosenFrequency: number;
  correctness: Exclude<Correctness, "TIMEOUT">;
  sizeCorrect: boolean | null;
}
