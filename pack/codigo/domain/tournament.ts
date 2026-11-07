/** Tournament-level context. ICM stages carry a clearly labelled model payout structure (see modelPayouts). */
export type TournamentFormat = "regular" | "pko" | "bounty";
export type TournamentStage = "early" | "mid" | "pre_itm" | "bubble" | "ft";

export const FORMATS: { v: TournamentFormat; label: string }[] = [
  { v: "regular", label: "Regular" },
  { v: "pko", label: "PKO" },
  { v: "bounty", label: "Bounty" },
];
export const STAGES: { v: TournamentStage; label: string }[] = [
  { v: "early", label: "Early game" },
  { v: "mid", label: "Middle stage" },
  { v: "pre_itm", label: "Pré-ITM (ICM)" },
  { v: "bubble", label: "Bolha (ICM)" },
  { v: "ft", label: "Mesa final (ICM)" },
];

/** Stages used by legacy random contexts (kept fixed so old seeds reproduce). */
export const LEGACY_STAGES: TournamentStage[] = ["early", "mid", "bubble", "ft"];
export const ICM_STAGES: TournamentStage[] = ["pre_itm", "bubble", "ft"];
export const isIcmStage = (s: TournamentStage) => ICM_STAGES.includes(s);

export const formatLabel = (f: TournamentFormat) => FORMATS.find((x) => x.v === f)?.label ?? f;
export const stageLabel = (s: TournamentStage) => STAGES.find((x) => x.v === s)?.label ?? s;
export const hasBounties = (f: TournamentFormat) => f !== "regular";

export interface PayoutStructure {
  prizePool: number | null;
  /** prizes[0] = 1st place. */
  prizes: number[];
  /** "imported" = real data; "model" = illustrative structure used to train ICM (always shown as such). */
  source: "imported" | "model";
  /** Human-readable description of how the structure was built. */
  label?: string;
}

/**
 * Model payouts for table-ICM training, relative values (only ratios matter for ICM).
 * One top-heavy MTT curve, cut at the number of paid places:
 * - Mesa final: n players, n paid.
 * - Bolha: n players, n−1 paid (one more bust and everyone left cashes).
 * - Pré-ITM: n players, n−2 paid (pressure exists but is softer than on the bubble).
 * The top-heavy curve stands in for the tournament's remaining upside, so the min-cash jump is
 * not exaggerated as it would be with a flat ladder. Training models, not a real event's payouts.
 */
const MTT_CURVE = [20, 14, 10, 7.5, 5.8, 4.5, 3.5, 2.7, 2.1];

/** PKO rules used by the trainer: buy-in split 50/50 and half of an eliminated bounty paid in cash. */
export const PKO_CASH_SHARE = 0.5;
/**
 * Model ratio between the 1st prize and the starting bounty, taken from a real 50/50 PKO
 * (PPPoker/Broka: 1st prize 345,86 with buy-in 30,40 → starting bounty 15,20 ≈ 1/23 of 1st).
 * Used only when no real starting bounty is given.
 */
export const FIRST_PRIZE_IN_STARTING_BOUNTIES = 23;
export const modelStartingBounty = (prizes: number[]) => Math.round(((prizes[0] ?? 0) / FIRST_PRIZE_IN_STARTING_BOUNTIES) * 100) / 100;
/** How much bounties have grown on average at each stage (in starting bounties, for an average stack). */
export const PKO_GROWTH: Partial<Record<TournamentStage, number>> = { early: 0.3, mid: 0.8, pre_itm: 1, bubble: 1.2, ft: 2 };
/**
 * PKO fora do ICM (early/mid): bounty vale fichas. Num PKO 50/50 um bounty inicial vale um stack
 * inicial (metade em dinheiro = meio stack inicial). Aqui: quantos big blinds ATUAIS vale o stack
 * inicial do torneio em cada fase (ex.: 20k de stack inicial com blinds 400/800 = 25bb). Editável na sessão.
 */
export const PKO_START_STACK_BB: Partial<Record<TournamentStage, number>> = { early: 25, mid: 8 };
/** Bounty inicial exibido quando não há premiação na mesma moeda: perfil PKO Broka (R$ 106,40 → R$ 53,20). */
export const DEFAULT_STARTING_BOUNTY = 53.2;

export function modelPayouts(stage: TournamentStage, players: number): PayoutStructure | null {
  if (!isIcmStage(stage)) return null;
  const paid = Math.max(1, players - (stage === "ft" ? 0 : stage === "bubble" ? 1 : 2));
  const name = stage === "ft" ? "Mesa final" : stage === "bubble" ? "Bolha" : "Pré-ITM";
  return {
    prizePool: null,
    prizes: MTT_CURVE.slice(0, paid),
    source: "model",
    label: `${name} modelo: ${players} jogadores na mesa, ${paid} pagos, curva MTT top-heavy`,
  };
}
/**
 * Tournament data. Every field is null until real data is configured/imported, except on ICM
 * stages, where playersRemaining/paidPlaces/payouts carry the labelled model structure
 * (payouts.source === "model") used by the ICM solver. Null fields never influence the engine.
 */
export interface TournamentContext {
  format: TournamentFormat;
  stage: TournamentStage;
  initialField: number | null;
  playersRemaining: number | null;
  paidPlaces: number | null;
  startingStackChips: number | null;
  averageStackChips: number | null;
  startingBounty: number | null;
  payouts: PayoutStructure | null;
  /** PKO chip EV (early/mid): how many current big blinds the tournament's starting stack is worth. */
  startingStackBb?: number;
  /** PKO com setup informado na sessão: buy-in total (prêmio + bounty), na moeda do torneio. */
  buyIn?: number;
  /** Fase informada pelo usuário: stacks (bb) dos jogadores das outras mesas, que entram só no ICM. */
  fieldOthers?: number[];
  /** PKO: bounty médio dos jogadores das outras mesas (mesma moeda da premiação). */
  fieldOtherBounty?: number;
}
