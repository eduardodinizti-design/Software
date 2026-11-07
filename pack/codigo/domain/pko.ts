/**
 * Modelo PKO (progressive knockout) do trainer.
 *
 * - Setup do torneio: buy-in total, fatia do bounty (50/50 padrão), stack inicial em fichas e o big blind atual
 *   → stack inicial em BBs atuais e bounty inicial em dinheiro.
 * - Cada jogador tem uma cabeça (bounty) em múltiplos do bounty inicial, que cresce com os KOs:
 *   ao eliminar alguém com cabeça h, metade (h/2) vai em dinheiro e metade soma na própria cabeça.
 * - Bounty Power (BP) de um jogador = nº de bounties iniciais na cabeça ÷ nº de stacks iniciais que ele tem.
 *   É o que diz quanto o bounty dele pesa num all-in contra ele (equity drop de quem o cobre).
 * - Conversão bounty → fichas (fora do ICM): cada bounty inicial eliminado vale PKO_BOUNTY_CHIP_VALUE stacks
 *   iniciais em fichas na hora. O valor 0,27 é o que reproduz a tabela BP → equity drop do material do time
 *   (BP 1 → 5,5%; BP 2 → 9,3%; BP 3 → 12,3%) em shoves de 10 a 25bb; o modelo antigo (0,5: metade do bounty
 *   pelo valor de face) dava 8–9% com BP 1 e deixava os calls largos demais.
 */
import type { Rng } from "./rng";
import type { TrainingScenario } from "./scenario";
import type { PlayerState } from "./table";
import { PKO_GROWTH, PKO_START_STACK_BB, type TournamentContext, type TournamentStage } from "./tournament";

export interface PkoSetup {
  /** Buy-in total (prêmio + bounty), na moeda do torneio. */
  buyIn: number;
  /** Fatia do buy-in que vira bounty (0,5 = PKO 50/50). */
  bountyShare: number;
  /** Stack inicial em fichas. */
  startingStackChips: number;
  /** Big blind atual em fichas. */
  bigBlindChips: number;
}

/** Fichas imediatas por bounty inicial eliminado, em stacks iniciais (calibrado pela tabela de bounty power). */
export const PKO_BOUNTY_CHIP_VALUE = 0.27;
/** Fatia do bounty eliminado paga em dinheiro na hora (o resto vai para a cabeça de quem eliminou). */
export const PKO_KO_CASH = 0.5;

/** Tabela Bounty Power → equity drop (%) ao pagar all-in cobrindo o adversário (material do time; valores aproximados). */
export const BP_EQUITY_DROP_TABLE: [number, number][] = [
  [0, 0], [0.1, 0.4], [0.2, 1.2], [0.3, 1.8], [0.4, 2.3], [0.5, 3], [0.6, 3.7], [0.7, 4.2], [0.8, 4.6], [0.9, 5], [1, 5.5],
  [1.1, 5.9], [1.2, 6.4], [1.3, 6.7], [1.4, 7.2], [1.5, 7.5], [1.6, 8.1], [1.7, 8.2], [1.8, 8.6], [1.9, 8.7], [2, 9.3],
  [2.1, 9.7], [2.2, 10.1], [2.3, 10.3], [2.4, 10.6], [2.5, 10.9], [2.6, 11.2], [2.7, 11.3], [2.8, 12], [2.9, 12.2], [3, 12.3],
];
/** Equity drop (pontos percentuais) da tabela para um BP (interpolado; acima de 3 fica em 12,3). */
export function tableEquityDrop(bp: number): number {
  const t = BP_EQUITY_DROP_TABLE;
  if (!(bp > 0)) return 0;
  if (bp >= t[t.length - 1]![0]) return t[t.length - 1]![1];
  for (let i = 1; i < t.length; i++) if (bp <= t[i]![0]) { const [x0, y0] = t[i - 1]!, [x1, y1] = t[i]!; return y0 + ((bp - x0) / (x1 - x0)) * (y1 - y0); }
  return 0;
}

export const DEFAULT_PKO_SETUP: PkoSetup = { buyIn: 106.4, bountyShare: 0.5, startingStackChips: 20000, bigBlindChips: 800 };

export const setupStartStackBb = (s: PkoSetup) => Math.round((s.startingStackChips / s.bigBlindChips) * 100) / 100;
export const setupStartingBounty = (s: PkoSetup) => Math.round(s.buyIn * s.bountyShare * 100) / 100;
export function pkoSetupError(s: PkoSetup): string | null {
  if (!(s.buyIn > 0)) return "Buy-in do PKO precisa ser maior que zero.";
  if (!(s.bountyShare > 0 && s.bountyShare < 1)) return "A fatia do bounty precisa ficar entre 1% e 99% do buy-in.";
  if (!(s.startingStackChips > 0) || !(s.bigBlindChips > 0)) return "Informe o stack inicial e o big blind atual em fichas.";
  const bb = setupStartStackBb(s);
  if (!(bb >= 1 && bb <= 300)) return "Stack inicial em BBs atuais deve ficar entre 1 e 300 (confira as fichas e o big blind).";
  return null;
}

/** Bounty Power: bounties iniciais na cabeça ÷ stacks iniciais no stack. */
export function bountyPower(headMultiplier: number, stackBb: number, startStackBb: number): number {
  if (!(stackBb > 0) || !(startStackBb > 0)) return 0;
  return headMultiplier / (stackBb / startStackBb);
}

/** Valor da cabeça em fichas para o Nash (com metade em dinheiro: KO rende cabeça × PKO_KO_CASH). */
export const bountyChipsPerUnit = (startStackBb: number) => (startStackBb * PKO_BOUNTY_CHIP_VALUE) / PKO_KO_CASH;


function poisson(r: Rng, lambda: number): number {
  const L = Math.exp(-lambda); let k = 0, p = 1;
  do { k++; p *= r.next(); } while (p > L && k < 60);
  return k - 1;
}

/**
 * Cabeças acumuladas (bounties iniciais) de cada jogador: nº de KOs ~ Poisson (mais provável para quem tem mais
 * fichas, mas um stack curto também pode ter eliminado gente antes de perder fichas); cada cabeça eliminada vale
 * 1 + até "crescimento da fase"; metade de cada uma soma na cabeça de quem eliminou.
 */
export function sampleHeads(r: Rng, stacksBb: number[], stage: TournamentStage): number[] {
  const growth = PKO_GROWTH[stage] ?? 1;
  const avg = stacksBb.reduce((a, b) => a + b, 0) / Math.max(1, stacksBb.length);
  const meanH = 1 + growth / 2;
  const lambdaAvg = (2 * growth) / meanH;
  return stacksBb.map((s) => {
    const k = poisson(r, lambdaAvg * (0.4 + 0.6 * (s / avg)));
    let m = 1;
    for (let i = 0; i < k; i++) m += PKO_KO_CASH * (1 + r.next() * growth);
    return Math.round(m * 100) / 100;
  });
}

export const n2 = (v: number) => v.toFixed(1).replace(".", ",");
/** Texto curto do BP com a leitura da tabela ("BP 1,4 → equity drop ≈ 7,2% pela tabela"). */
export function describeBountyPower(bp: number): string {
  return `BP ${n2(bp)} → equity drop ≈ ${n2(tableEquityDrop(bp))}% pela tabela${bp > 3 ? " (acima de 3 a tabela para em 12,3%)" : ""}`;
}

/**
 * Stack inicial em BBs atuais do cenário: o do torneio (early/mid, ou o informado na sessão) ou, nas fases com ICM,
 * uma referência por fase só para mostrar o BP (no ICM o bounty entra em dinheiro pelo motor, não por esta conversão).
 */
const ICM_STAGE_START_BB: Partial<Record<TournamentStage, number>> = { pre_itm: 4, bubble: 3.5, ft: 2.5 };
export function tournamentStartStackBb(t: TournamentContext): number | null {
  if (t.format !== "pko") return null;
  return t.startingStackBb ?? PKO_START_STACK_BB[t.stage] ?? ICM_STAGE_START_BB[t.stage] ?? null;
}
export const scenarioStartStackBb = (s: TrainingScenario) => tournamentStartStackBb(s.tournament);
/** BP de um jogador da mesa (null fora do PKO ou sem cabeça). */
export function playerBountyPower(s: TrainingScenario, p: PlayerState): number | null {
  const start = scenarioStartStackBb(s);
  if (s.context.format !== "pko" || p.bountyMultiplier === undefined || start === null) return null;
  return bountyPower(p.bountyMultiplier, p.stackBb, start);
}
/**
 * BP que pesa na decisão do herói: o do agressor (vs open, vs 3bet, call de shove) ou, quando o herói abre,
 * a média dos jogadores que ainda falam depois dele.
 */
export function relevantBountyPower(s: TrainingScenario): number | null {
  const t = s.table;
  const ag = s.spot.aggressors[0];
  const pool = ag ? t.players.filter((p) => p.position === ag) : t.players.filter((p) => p.seat > t.heroSeat);
  const bps = pool.map((p) => playerBountyPower(s, p)).filter((v): v is number => v !== null);
  return bps.length ? bps.reduce((a, b) => a + b, 0) / bps.length : null;
}
