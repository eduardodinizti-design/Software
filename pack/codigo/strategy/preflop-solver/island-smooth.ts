/**
 * Mãos que destoam das vizinhas nos arquivos do HRC (ruído do Monte Carlo).
 *
 * Numa família de kicker (Q9o, Q8o, …, Q2o; A9s…A2s), mãos vizinhas têm equity e jogabilidade parecidas. Quando o
 * HRC devolve para uma mão uma ação que quase não aparece nas vizinhas (ex.: pré-ITM 25bb, SB first-in: Q5o mistura
 * limp/shove, Q3o limp 66%, e Q4o shove 100%), e o EV que o próprio HRC calculou mostra que a ação das vizinhas custa
 * no máximo a margem da régua de validação (0,05bb / 0,02% do prize pool) para essa mão, a escolha do HRC é ruído:
 * a mão passa a jogar a média das vizinhas. A ação de maior EV continua aceita na correção (perde 0 de EV).
 * Quando a ação das vizinhas custa mais que a margem, o HRC tem certeza: a mão fica como está e entra na lista de
 * "destoa com EV" da auditoria (scripts/audit-ranges.ts), para revisão humana.
 * Pares ficam com a regra própria (pair-order.ts). Cada mudança fica registrada (o painel de fonte mostra).
 */
export interface IslandFix { node: string; hand: string; from: string; to: string; cost: number }

const RANKS = "AKQJT98765432";
/** Famílias de kicker na ordem do kicker (maior → menor): suited e offsuit de cada carta alta. */
export const KICKER_FAMILIES: string[][] = [...RANKS.slice(0, 12)].flatMap((hi, i) => (["s", "o"] as const).map((suf) => [...RANKS.slice(i + 1)].map((k) => `${hi}${k}${suf}`)));

/** Ação: frequência e EV relativo à base (fold, ou check no BB contra o limp) por mão, na ordem `hands`. */
export type SmoothActs = Record<string, { freq: number[]; ev: number[] }>;

/** Média das frequências das vizinhas abaixo disto = a ação da mão é rara na vizinhança. */
const RARE = 0.25;
/** Ações das vizinhas com pelo menos esta frequência média precisam caber na margem de EV. */
const RELEVANT = 0.2;

/**
 * Suaviza um nó (in place nas frequências). `acts` inclui a base (frequência explícita, EV 0).
 * Devolve as mudanças feitas e as mãos que destoam mas que o EV confirma (não mexe).
 */
export function smoothIslands(node: string, hands: readonly string[], acts: SmoothActs, margin: number): { fixes: IslandFix[]; confident: IslandFix[] } {
  const keys = Object.keys(acts);
  const pos = new Map(hands.map((h, i) => [h, i]));
  const freq0 = Object.fromEntries(keys.map((k) => [k, acts[k]!.freq.slice()]));
  const fixes: IslandFix[] = [], confident: IslandFix[] = [];
  const main = (i: number, f: Record<string, number[]>) => keys.reduce((a, b) => (f[b]![i]! > f[a]![i]! ? b : a));
  for (const fam of KICKER_FAMILIES) {
    const idx = fam.map((h) => pos.get(h)).filter((i): i is number => i !== undefined);
    idx.forEach((i, j) => {
      const nb = [idx[j - 1], idx[j + 1]].filter((x): x is number => x !== undefined);
      if (!nb.length) return;
      // Ponta da família (só uma vizinha): precisa de duas vizinhas seguidas concordando.
      if (nb.length === 1) { const far = idx[j === 0 ? 2 : j - 2]; if (far === undefined || main(far, freq0) !== main(nb[0]!, freq0)) return; }
      const avg = Object.fromEntries(keys.map((k) => [k, nb.reduce((a, n) => a + freq0[k]![n]!, 0) / nb.length]));
      const m = main(i, freq0);
      if (avg[m]! >= RARE) return;
      const best = Math.max(...keys.map((k) => acts[k]!.ev[i]!));
      const rel = keys.filter((k) => avg[k]! >= RELEVANT);
      if (!rel.length) return;
      const cost = Math.max(...rel.map((k) => best - acts[k]!.ev[i]!));
      const to = keys.reduce((a, b) => (avg[b]! > avg[a]! ? b : a));
      const fix = { node, hand: hands[i]!, from: m, to, cost };
      if (cost > margin) { confident.push(fix); return; }
      const tot = keys.reduce((a, k) => a + avg[k]!, 0) || 1;
      for (const k of keys) acts[k]!.freq[i] = avg[k]! / tot;
      fixes.push(fix);
    });
  }
  return { fixes, confident };
}
