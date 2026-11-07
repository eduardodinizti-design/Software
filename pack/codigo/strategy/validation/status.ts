/**
 * Validação dos ranges: só fica no ar o que passou na comparação com uma referência externa (HRC, GTO Wizard).
 *
 * - Cada decisão do motor pertence a uma "família" (de onde veio a resposta): `familyOf`.
 * - O arquivo `public/validation/status.json` (gerado por `scripts/validate-ranges.ts` a partir das referências em
 *   `validation/references/`) diz quais famílias estão validadas e se a trava está ligada (`gate`).
 * - Com a trava ligada, os treinos só sorteiam spots de famílias validadas; um treino sem nenhum spot validado
 *   aparece como "Em validação" e não começa.
 * Famílias que nunca podem ser validadas (referência aproximada, ICM calibrado, chart de limp) retornam null.
 */
import { isPushFoldSpot, type TrainingScenario } from "@/domain/scenario";
import type { SourceProbe, StrategyDecision } from "../types";

export interface FamilyStatus {
  status: "validado" | "reprovado" | "em_validacao";
  /** Resumo da evidência: referência usada, nós comparados, concordância. */
  evidence?: string;
  at?: string;
}
export interface ValidationStatus {
  version: string;
  /** Trava ligada: só famílias validadas entram nos treinos. */
  gate: boolean;
  families: Record<string, FamilyStatus>;
}

const EMPTY: ValidationStatus = { version: "none", gate: false, families: {} };
let current: ValidationStatus = EMPTY;
let loading: Promise<ValidationStatus> | null = null;

export const getValidationStatus = () => current;
export function setValidationStatus(s: ValidationStatus) { current = s; }
export function clearValidationStatus() { current = EMPTY; loading = null; }
export const gateEnabled = () => current.gate;
export const isFamilyValidated = (f: string | null) => !!f && current.families[f]?.status === "validado";

/** Carrega o status publicado (uma vez por sessão do navegador). Sem arquivo: trava desligada. */
export function loadValidationStatus(fetchJson: (path: string) => Promise<unknown> = async (p) => (await fetch(p)).json()): Promise<ValidationStatus> {
  if (!loading) {
    loading = fetchJson("/validation/status.json")
      .then((raw) => { const v = raw as ValidationStatus; if (v && typeof v.gate === "boolean" && v.families) current = v; return current; })
      .catch(() => current);
  }
  return loading;
}

/** Agrupamento das situações do catálogo pré-flop em famílias (as variações de stacks de uma fase contam juntas). */
export function solverFamily(preset: string): string {
  if (preset.startsWith("hrc_")) return `hrc:${preset.slice(4)}`;
  if (preset.startsWith("chip_")) return `solver:${preset}`;
  if (preset.startsWith("pko")) return "solver:pko_chip";
  const [phase, ...rest] = preset.split("_");
  const fmt = rest[rest.length - 1];
  return `solver:${phase}_${fmt}`;
}

/** Família da decisão (de onde veio a resposta), ou null quando a fonte não é validável. */
export function familyOf(d: StrategyDecision, s: TrainingScenario): string | null {
  return familyOfSource({ source: d.source, rangeId: d.range?.id ?? "", mode: s.context.mode ?? "chip_ev" }, s);
}
/** Família a partir só da fonte (ver `strategyEngine.probe`): mesma regra de `familyOf`. */
export function familyOfSource(d: SourceProbe, s: TrainingScenario): string | null {
  const mode = s.context.mode ?? "chip_ev";
  if (d.source.id === "solver") {
    const m = /\|solver-([a-z0-9_]+)/.exec(d.rangeId);
    return m ? solverFamily(m[1]!) : null;
  }
  // Resteal (3bet all-in) depende do range de open de quem abriu: família própria, validada à parte.
  // Validado (26/10) só com o range de open do HRC (chip EV, 9-max regular); fora disso o opener usa o range de referência.
  if (s.spot.type === "3bet_shove" && d.source.label.startsWith("Nash push/fold")) return mode === "chip_ev" && (s.context.players !== 9 || s.context.format !== "regular") ? "nash_resteal:chip_ev_ref" : `nash_resteal:${mode}`;
  if (isPushFoldSpot(s.spot.type) && d.source.label.startsWith("Nash push/fold")) return `nash:${mode}`;
  if (d.source.id === "nvt_team" && s.spot.type === "open_raise") return `team:open:${s.context.stack}`;
  if (d.source.id === "nvt_team" && s.spot.type === "open_shove") return "team:pko_shove";
  return null;
}

export const FAMILY_LABEL: Record<string, string> = {
  "nash:chip_ev": "Push/fold Nash (chip EV)",
  "nash:icm": "Push/fold Nash (ICM)",
  "nash_resteal:chip_ev": "Resteal Nash (chip EV, 9-max)",
  "nash_resteal:chip_ev_ref": "Resteal Nash (chip EV, outras mesas: range de open de referência)",
  "nash_resteal:icm": "Resteal Nash (ICM)",
  "nash_resteal:pko_icm": "Resteal Nash (PKO + ICM)",
  "nash_resteal:pko": "Resteal Nash (PKO, começo/meio do torneio)",
  "nash:pko": "Push/fold Nash (PKO, começo/meio do torneio)",
  "nash:pko_icm": "Push/fold Nash (PKO + ICM)",
  "team:open:100": "Open raise 100bb (tabelas do time)",
  "team:open:40": "Open raise 40bb (tabelas do time)",
  "team:open:25": "Open raise 25bb (tabelas do time)",
  "team:open:15": "Open raise 15bb (tabelas do time)",
  "team:pko_shove": "Shove PKO (tabelas do time)",
  "solver:chip_25": "Solver pré-flop, chip EV 25bb",
  "solver:chip_40": "Solver pré-flop, chip EV 40bb",
  "solver:preitm_icm": "Solver pré-flop, pré-ITM (ICM)",
  "solver:bubble_icm": "Solver pré-flop, bolha (ICM)",
  "solver:ft_icm": "Solver pré-flop, mesa final (ICM)",
  "solver:preitm_pko": "Solver pré-flop, pré-ITM (PKO + ICM)",
  "solver:bubble_pko": "Solver pré-flop, bolha (PKO + ICM)",
  "solver:ft_pko": "Solver pré-flop, mesa final (PKO + ICM)",
  "solver:pko_chip": "Solver pré-flop, PKO chip EV",
  "hrc:chip_25": "Ranges do HRC, chip EV 25bb",
  "hrc:chip_40": "Ranges do HRC, chip EV 40bb",
  "hrc:chip_15": "Ranges do HRC, chip EV 15bb",
  "hrc:ft_iguais_icm": "Ranges do HRC, mesa final ICM (stacks iguais 25bb)",
  "hrc:bubble_iguais_icm": "Ranges do HRC, bolha ICM (stacks iguais 25bb)",
  "hrc:preitm_iguais_icm": "Ranges do HRC, pré-ITM ICM (stacks iguais 25bb)",
  "hrc:preitm_curtos_fim_icm": "Ranges do HRC, pré-ITM ICM (curtos nas posições finais)",
  "hrc:preitm_curtos_ini_icm": "Ranges do HRC, pré-ITM ICM (curtos nas primeiras posições)",
  "hrc:bubble_curtos_fim_icm": "Ranges do HRC, bolha ICM (curtos nas posições finais)",
  "hrc:bubble_curtos_ini_icm": "Ranges do HRC, bolha ICM (curtos nas primeiras posições)",
  "hrc:ft_curtos_fim_icm": "Ranges do HRC, mesa final ICM (curtos nas posições finais)",
  "hrc:ft_curtos_ini_icm": "Ranges do HRC, mesa final ICM (curtos nas primeiras posições)",
};
