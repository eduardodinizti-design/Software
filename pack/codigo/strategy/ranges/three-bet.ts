import type { Position } from "@/domain/positions";

/**
 * Frequência de 3bet (% das mãos) contra um open, por posição de quem abre e de quem dá 3bet.
 * Aproximação de frequências típicas de MTT com ante (não solver): 3bet cresce contra opens tardios
 * e nas blinds.
 */
export function threeBetPct(openerPos: Position, threeBettorPos: Position): number {
  const late = ["CO", "BTN", "SB"].includes(openerPos);
  const mid = ["LJ", "HJ"].includes(openerPos);
  const blinds = threeBettorPos === "SB" || threeBettorPos === "BB";
  if (openerPos === "SB") return 15; // BB contra open do SB
  if (openerPos === "BTN") return blinds ? 12.5 : 8;
  if (late) return blinds ? 10 : 8;
  if (mid) return blinds ? 8 : 6.5;
  return blinds ? 6 : 5; // contra open de posição inicial
}
