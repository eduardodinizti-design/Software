/**
 * EV perdido abaixo disso conta como mix válido e aparece como empate. Igual à margem da régua de validação
 * (0,05bb / 0,02% do prize pool; 30/10, auditoria): abaixo dela a diferença está no ruído do solver (o HRC é
 * validado contra o motor com essa margem), então o trainer não cobra como erro uma escolha que a própria régua
 * considera concordância. Antes: 0,03bb / 0,01%.
 */
export const EV_MIX_TOL_BB = 0.05;
export const EV_MIX_TOL_PCT = 0.02;

/**
 * Mix válido por EV relativo (30/10, Eduardo): uma ação +EV em relação ao fold que perde até 10% do EV da melhor ação,
 * e no máximo 0,3bb (0,06% do prize pool), também é aceita. Ex.: 77 na SB com 10bb, limp +2,87 e shove +2,65: o shove
 * perde 0,22bb (7,7%) e é mix válido; o erro ali seria foldar. AA perdendo 1bb continua erro (passa do teto).
 */
export const EV_MIX_REL = 0.1;
export const EV_MIX_CAP_BB = 0.3;
export const EV_MIX_CAP_PCT = 0.06;
/** A ação escolhida conta como mix válido pelo EV (tolerância absoluta ou relativa). */
export function evMixAccepted(evs: { action: string; ev: number }[], chosen: string, unit: "bb" | "pct" | null | undefined): boolean {
  const pick = evs.find((e) => e.action === chosen); if (!pick) return false;
  const best = Math.max(...evs.map((e) => e.ev));
  const loss = best - pick.ev;
  if (loss < (unit === "pct" ? EV_MIX_TOL_PCT : EV_MIX_TOL_BB)) return true;
  // Relativa: só ação que rende mais que o fold (base 0 dos EVs) e perto da melhor.
  return pick.ev > 0 && loss <= EV_MIX_REL * best && loss <= (unit === "pct" ? EV_MIX_CAP_PCT : EV_MIX_CAP_BB);
}
