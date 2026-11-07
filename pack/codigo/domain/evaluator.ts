/**
 * Avaliador de 7 cartas (mesma lógica do script C que gerou a matriz de equity).
 * Cartas como inteiros 0..51: rank = c >> 2 (0 = 2 … 12 = A), naipe = c & 3. Maior valor = mão melhor.
 */
import type { Card } from "./cards";

const STRAIGHT = new Int8Array(8192);
const TOP5 = new Uint32Array(8192);
(() => {
  for (let m = 0; m < 8192; m++) {
    STRAIGHT[m] = -1;
    for (let top = 12; top >= 4; top--) {
      const need = 0x1f << (top - 4);
      if ((m & need) === need) { STRAIGHT[m] = top; break; }
    }
    if (STRAIGHT[m]! < 0 && (m & 0x100f) === 0x100f) STRAIGHT[m] = 3;
    let v = 0, n = 0;
    for (let r = 12; r >= 0 && n < 5; r--) if (m & (1 << r)) { v = v * 16 + r; n++; }
    while (n < 5) { v *= 16; n++; }
    TOP5[m] = v;
  }
})();

const popcount = (x: number) => { let c = 0; while (x) { x &= x - 1; c++; } return c; };
const highBit = (x: number) => 31 - Math.clz32(x);
const CAT = 1 << 20;

/** Valor de 7 cartas (array de 7 inteiros). */
export function eval7(c: ArrayLike<number>): number {
  const sm = [0, 0, 0, 0];
  const cnt = new Int8Array(13);
  let all = 0;
  for (let i = 0; i < 7; i++) {
    const r = c[i]! >> 2, s = c[i]! & 3;
    sm[s]! |= 1 << r; cnt[r]!++; all |= 1 << r;
  }
  for (let s = 0; s < 4; s++) {
    if (popcount(sm[s]!) >= 5) {
      const st = STRAIGHT[sm[s]!]!;
      return st >= 0 ? 8 * CAT + st : 5 * CAT + TOP5[sm[s]!]!;
    }
  }
  let quad = -1, t1 = -1, t2 = -1, p1 = -1, p2 = -1;
  for (let r = 12; r >= 0; r--) {
    const k = cnt[r]!;
    if (k === 4) quad = r;
    else if (k === 3) { if (t1 < 0) t1 = r; else if (t2 < 0) t2 = r; }
    else if (k === 2) { if (p1 < 0) p1 = r; else if (p2 < 0) p2 = r; }
  }
  if (quad >= 0) return 7 * CAT + quad * 16 + highBit(all & ~(1 << quad));
  if (t1 >= 0 && (t2 >= 0 || p1 >= 0)) return 6 * CAT + t1 * 16 + Math.max(t2, p1);
  const st = STRAIGHT[all]!;
  if (st >= 0) return 4 * CAT + st;
  if (t1 >= 0) return 3 * CAT + t1 * 256 + Math.floor(TOP5[all & ~(1 << t1)]! / 4096);
  if (p1 >= 0 && p2 >= 0) return 2 * CAT + p1 * 256 + p2 * 16 + highBit(all & ~(1 << p1) & ~(1 << p2));
  if (p1 >= 0) return 1 * CAT + p1 * 4096 + Math.floor(TOP5[all & ~(1 << p1)]! / 256);
  return TOP5[all]!;
}

const RANKS = "23456789TJQKA";
const SUITS = "shdc";
/** "As" → inteiro 0..51. */
export function cardId(card: Card): number {
  const r = RANKS.indexOf(card[0]!.toUpperCase()), s = SUITS.indexOf(card[1]!.toLowerCase());
  if (r < 0 || s < 0) throw new Error(`Carta inválida: ${card}`);
  return r * 4 + s;
}

/** Combos concretos (pares de cartas 0..51) de uma mão de 169 ("AKs"). */
export function comboIds(hand: string): [number, number][] {
  const r1 = RANKS.indexOf(hand[0]!), r2 = RANKS.indexOf(hand[1]!);
  const out: [number, number][] = [];
  if (hand.length === 2) { for (let a = 0; a < 4; a++) for (let b = a + 1; b < 4; b++) out.push([r1 * 4 + a, r1 * 4 + b]); }
  else if (hand.endsWith("s")) { for (let s = 0; s < 4; s++) out.push([r1 * 4 + s, r2 * 4 + s]); }
  else { for (let a = 0; a < 4; a++) for (let b = 0; b < 4; b++) if (a !== b) out.push([r1 * 4 + a, r2 * 4 + b]); }
  return out;
}
