/**
 * Ordem natural dos pares nos arquivos do HRC.
 *
 * Num mesmo nó, um par maior nunca rende menos que um par menor na mesma ação (call, 3bet, all-in, open): tem mais
 * equity contra qualquer range e a mesma jogabilidade. O Monte Carlo do HRC, em nós de pouco alcance, devolve EVs com
 * ruído que quebram essa ordem (ex.: bolha 25bb, UTG vs 3bet da SB: call 99 −0,074% e 77 +0,023%), e a frequência
 * acompanha o ruído (99 fold, 77 e 88 call). Correção, só nos pares:
 * - o EV de cada ação (contra o fold) é ajustado para cair de AA a 22 (regressão isotônica: a menor mudança que
 *   respeita a ordem);
 * - só nos pares que estavam fora de ordem: o par passa a jogar pelo EV ajustado (a melhor ação, ou as ações
 *   empatadas dentro da margem do mix aceito, 0,05bb / 0,02% do prize pool, em partes iguais).
 * Cada correção fica registrada em `pairFixes` (o painel de fonte mostra o que mudou).
 */
import type { PreflopPreset } from "./catalog";

const PAIRS = ["AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22"];
export interface PairFix { node: string; hand: string; from: string; to: string }

/** Regressão isotônica não crescente (pesos iguais), algoritmo PAVA. */
export function isotonicDecreasing(y: number[]): number[] {
  const blocks: { sum: number; n: number }[] = [];
  for (const v of y) {
    blocks.push({ sum: v, n: 1 });
    while (blocks.length > 1) {
      const b = blocks[blocks.length - 1]!, a = blocks[blocks.length - 2]!;
      if (a.sum / a.n >= b.sum / b.n) break;
      blocks.splice(blocks.length - 2, 2, { sum: a.sum + b.sum, n: a.n + b.n });
    }
  }
  return blocks.flatMap((b) => Array(b.n).fill(b.sum / b.n) as number[]);
}

type Node = { [k: string]: unknown; ev?: Record<string, number[]> };
/** Corrige um nó: `acts` = chave da frequência → chave do EV. Devolve as correções feitas. */
function fixNode(name: string, node: Node, acts: Record<string, string>, idx: number[], tol: number): PairFix[] {
  const ev = node.ev; const fold = ev?.["fold"]; if (!ev || !fold) return [];
  const fixes: PairFix[] = [];
  const freqKeys = Object.keys(acts).filter((k) => Array.isArray(node[k]) && Array.isArray(ev[acts[k]!]));
  if (!freqKeys.length) return [];
  const smooth: Record<string, number[]> = {};
  for (const k of freqKeys) smooth[k] = isotonicDecreasing(idx.map((i) => ev[acts[k]!]![i]! - fold[i]!));
  idx.forEach((i, j) => {
    const freq = Object.fromEntries(freqKeys.map((k) => [k, (node[k] as number[])[i]!]));
    const foldF = Math.max(0, 1 - Object.values(freq).reduce((a, b) => a + b, 0));
    const main = [...freqKeys, "fold"].reduce((a, b) => ((b === "fold" ? foldF : freq[b]!) > (a === "fold" ? foldF : freq[a]!) ? b : a), "fold");
    const evOf = (k: string) => (k === "fold" ? 0 : smooth[k]![j]!);
    const best = [...freqKeys, "fold"].reduce((a, b) => (evOf(b) > evOf(a) ? b : a), "fold");
    // Só mexe no par que estava fora de ordem (o ajuste mudou o EV dele).
    const moved = freqKeys.some((k) => Math.abs(ev[acts[k]!]![i]! - fold[i]! - smooth[k]![j]!) > 1e-9);
    // Também o par cuja frequência contradiz o próprio EV por mais que a margem (ex.: 55 call 93% com EV −0,044%
    // contra o fold, enquanto 99–66 foldam): joga pelo EV, como o resto do bloco.
    const contra = evOf(best) - evOf(main) > tol;
    if (!moved && !contra) return;
    // EV ajustado entra no arquivo em memória (o painel e a matriz mostram o mesmo número que decide).
    for (const k of freqKeys) ev[acts[k]!]![i] = fold[i]! + smooth[k]![j]!;
    // Par fora de ordem joga pelo EV ajustado: a melhor ação, ou as empatadas em partes iguais (dentro da margem
    // do mix aceito), para que o bloco de pares que o ajuste igualou receba a mesma resposta.
    const near = [...freqKeys, "fold"].filter((k) => evOf(k) >= evOf(best) - tol);
    for (const k of freqKeys) (node[k] as number[])[i] = near.includes(k) ? 1 / near.length : 0;
    const to = near.length > 1 ? near.join("/") : best;
    if (to !== main) fixes.push({ node: name, hand: PAIRS[j]!, from: main, to });
  });
  return fixes;
}

/** Aplica a ordem dos pares em todos os nós do arquivo (in place). */
export function fixPairOrder(p: Omit<PreflopPreset, "idx"> & { idx: number[] }, tol: number): PairFix[] {
  const pos = new Map(p.hands.map((h, i) => [h, i]));
  const idx = PAIRS.map((h) => pos.get(h as never)!);
  const out: PairFix[] = [];
  // SB fora: o resto do open da SB inclui limp (Blind War), não é fold.
  for (const [k, n] of Object.entries(p.rfi)) if (k !== "SB") out.push(...fixNode(`open ${k}`, n as unknown as Node, { raise: "raise", shove: "shove" }, idx, tol));
  for (const [k, n] of Object.entries(p.resp)) out.push(...fixNode(`vs open ${k}`, n as unknown as Node, { call: "call", three: "three", shove: "shove" }, idx, tol));
  for (const [k, n] of Object.entries(p.opv3)) out.push(...fixNode(`vs 3bet ${k}`, n as unknown as Node, { call: "call", shove: "shove" }, idx, tol));
  return out;
}
