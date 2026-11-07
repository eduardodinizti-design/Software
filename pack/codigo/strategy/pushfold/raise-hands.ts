/**
 * Mãos de raise no treino de push/fold. O drill de open shove só tem shove ou fold, mas onde temos o HRC com a
 * árvore completa (open de 2bb, shove e fold; hoje chip EV 15bb e 25bb e ICM 25bb) dá para ver quando a mão, no
 * jogo de verdade, é de raise ou fold: o raise rende mais que o shove (pela margem da régua), não perde para o fold, e
 * o shove não dá lucro no jogo completo.
 * Essas mãos não entram no treino de push/fold e, se aparecerem (revisão antiga), nenhuma das duas respostas
 * conta como erro: a decisão certa não está entre as opções.
 *
 * Exemplo que motivou (28/10): T9o no BTN com 15bb. Nash push/fold: shove +0,07bb. HRC árvore completa:
 * raise −0,002bb (mix 47%), shove −0,16bb.
 */
import type { TrainingScenario } from "@/domain/scenario";
import { at, describePreset, isHrcPreset, presetFor } from "@/strategy/preflop-solver/catalog";

export interface RaiseHandInfo { preset: string; label: string; unit: "bb" | "pct"; raise: number; shove: number; raiseFreq: number }

/** Leitura do HRC (árvore completa) para o open da mão do herói, quando a mão é de raise. Null caso contrário. */
export function raiseHandInfo(s: Pick<TrainingScenario, "context" | "table" | "spot" | "hero">): RaiseHandInfo | null {
  if (s.spot.type !== "open_shove") return null;
  let p;
  try { p = presetFor(s as TrainingScenario); } catch { return null; }
  if (!p || !isHrcPreset(p.name)) return null;
  const node = p.rfi[s.spot.heroPosition];
  if (!node?.ev) return null;
  const h = s.hero.hand;
  const evF = at(p, node.ev.fold, h);
  const raise = at(p, node.ev.raise, h) - evF, shove = at(p, node.ev.shove, h) - evF;
  const tol = p.unit === "pct" ? 0.02 : 0.05;
  // Raise melhor que o shove, raise não perde para o fold, e o shove não é lucrativo no jogo completo. Mãos fortes em
  // que o raise só rende um pouco mais que um shove também lucrativo (AA, AK…) seguem no drill: o shove está certo.
  if (!(raise > shove + tol && raise >= -tol && shove < tol)) return null;
  return { preset: p.name, label: describePreset(p.name), unit: p.unit, raise, shove, raiseFreq: at(p, node.raise, h) };
}
export const isRaiseHand = (s: Pick<TrainingScenario, "context" | "table" | "spot" | "hero">) => raiseHandInfo(s) !== null;
