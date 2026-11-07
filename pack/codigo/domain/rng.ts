/** Deterministic PRNG (mulberry32) so every exercise is reproducible from its seed. */
export interface Rng {
  next(): number;
  int(maxExclusive: number): number;
  pick<T>(arr: readonly T[]): T;
  range(min: number, max: number): number;
}

export function createRng(seed: number): Rng {
  let a = seed >>> 0;
  const next = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    int: (n) => Math.floor(next() * n),
    pick: (arr) => arr[Math.floor(next() * arr.length)]!,
    range: (min, max) => min + next() * (max - min),
  };
}

export function newSeed(): number {
  return Math.floor(Math.random() * 2 ** 32) >>> 0;
}

/** Derives an independent stream from a seed (e.g. scenario context vs. table). */
export const deriveSeed = (seed: number, salt: number) => (Math.imul(seed ^ salt, 0x9e3779b1) >>> 0);
