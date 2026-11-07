/**
 * Motor de ICM do NVT Range Lab.
 *
 * - Valor de cada stack (Malmuth–Harville): exato por programação dinâmica sobre subconjuntos, só até
 *   o último lugar pago (até ICM_EXACT_MAX jogadores vivos); acima disso, Monte Carlo exato em distribuição
 *   (corrida exponencial: ordenar por −ln(U)/stack sorteia a ordem de chegada do Malmuth–Harville) com
 *   números aleatórios comuns, para que comparações entre cenários não tenham ruído de sorteio.
 * - Bubble factor e risk premium por pares (A contra B), como as tabelas do HRC / ICMizer / GTO Wizard.
 * - Modelo de field: mesa real + jogadores das outras mesas (stack médio) + premiação real ou curva modelo.
 * - Acordo (deal) por ICM e por fichas.
 */
import { createRng } from "@/domain/rng";

export const ICM_EXACT_MAX = 20;
export const ICM_MC_SAMPLES = 10000;
/** Tamanho padrão do field no cálculo (exato e rápido o bastante para a matriz de risk premium). */
export const ICM_FIELD_DEFAULT = 14;

/** Valor (na moeda da premiação) de cada stack. Stacks zerados dividem os últimos lugares. */
export function icmValues(stacks: number[], payouts: number[], opts: { samples?: number; seed?: number } = {}): number[] {
  const alive = stacks.filter((s) => s > 1e-9).length;
  if (alive <= ICM_EXACT_MAX) return icmExact(stacks, payouts);
  // Field grande com muitos stacks iguais (outras mesas com o stack médio): Malmuth–Harville exato por grupos.
  return icmGrouped(stacks, payouts) ?? icmMonteCarlo(stacks, payouts, opts.samples ?? ICM_MC_SAMPLES, opts.seed ?? 20261017);
}

/** Máximo de jogadores "individuais" (fora do grupo de stacks iguais) no ICM por grupos. */
export const ICM_GROUPED_MAX_INDIVIDUALS = 14;

/**
 * Malmuth–Harville exato quando quase todos têm o mesmo stack (field de MTT: a mesa real + as outras mesas com o
 * stack médio). A ordem de chegada do Malmuth–Harville sorteia o 1º lugar proporcional às fichas, depois o 2º entre
 * os que sobraram, e assim por diante; como os jogadores do grupo são idênticos, basta saber QUANTOS deles já
 * terminaram (não quais): estado = (subconjunto dos individuais já colocados, nº do grupo já colocado), só até o
 * último lugar pago. Mesmo resultado do icmExact (sem compressão nem sorteio), em milissegundos com 180 jogadores.
 * É o que o "Multi Table ICM" do HRC aproxima (Malmuth–Harville sobre o field inteiro, sem comprimir).
 * null = não há grupo grande o bastante (usa Monte Carlo).
 */
export function icmGrouped(stacks: number[], payouts: number[]): number[] | null {
  const n = stacks.length;
  const eq = new Array<number>(n).fill(0);
  const alive = stacks.map((s, i) => (s > 1e-9 ? i : -1)).filter((i) => i >= 0);
  const busted = stacks.map((s, i) => (s > 1e-9 ? -1 : i)).filter((i) => i >= 0);
  const pay = (place: number) => payouts[place] ?? 0;
  if (busted.length) {
    let share = 0;
    for (let k = 0; k < busted.length; k++) share += pay(alive.length + k);
    for (const i of busted) eq[i] = share / busted.length;
  }
  // Grupo = o stack que mais se repete entre os vivos.
  const count = new Map<number, number>();
  for (const i of alive) count.set(stacks[i]!, (count.get(stacks[i]!) ?? 0) + 1);
  let g = 0, m = 0;
  for (const [v, c] of count) if (c > m) { g = v; m = c; }
  const ind = alive.filter((i) => stacks[i] !== g);
  const group = alive.filter((i) => stacks[i] === g);
  const t = ind.length;
  if (t > ICM_GROUPED_MAX_INDIVIDUALS || m < 2) return null;
  const paid = Math.min(alive.length, payouts.length);
  const K = Math.min(m, paid);
  const st = ind.map((i) => stacks[i]!);
  const total = alive.reduce((a, i) => a + stacks[i]!, 0);
  const full = 1 << t;
  const sumMask = new Float64Array(full), pop = new Uint8Array(full);
  for (let mask = 1; mask < full; mask++) { const low = mask & -mask; const j = 31 - Math.clz32(low); sumMask[mask] = sumMask[mask ^ low]! + st[j]!; pop[mask] = pop[mask ^ low]! + 1; }
  const W = K + 1;
  const prob = new Float64Array(full * W);
  prob[0] = 1;
  let eqGroup = 0;
  for (let mask = 0; mask < full; mask++) {
    for (let k = 0; k <= K; k++) {
      const p = prob[mask * W + k]!;
      if (p === 0) continue;
      const place = pop[mask]! + k;
      if (place >= paid) continue; // lugares seguintes pagam zero
      const rem = total - sumMask[mask]! - k * g;
      if (rem <= 1e-12) continue;
      const value = pay(place);
      for (let j = 0; j < t; j++) {
        if (mask & (1 << j)) continue;
        const pj = (p * st[j]!) / rem;
        eq[ind[j]!]! += pj * value;
        prob[(mask | (1 << j)) * W + k]! += pj;
      }
      if (k < m) {
        const pg = (p * (m - k) * g) / rem;
        eqGroup += pg * value;
        if (k + 1 <= K) prob[mask * W + k + 1]! += pg;
      }
    }
  }
  for (const i of group) eq[i] = eqGroup / m;
  return eq;
}

/** Malmuth–Harville exato. Só expande estados enquanto ainda há lugar pago a distribuir. */
export function icmExact(stacks: number[], payouts: number[]): number[] {
  const n = stacks.length;
  const eq = new Array<number>(n).fill(0);
  const alive = stacks.map((s, i) => (s > 1e-9 ? i : -1)).filter((i) => i >= 0);
  const busted = stacks.map((s, i) => (s > 1e-9 ? -1 : i)).filter((i) => i >= 0);
  const pay = (place: number) => payouts[place] ?? 0;
  if (busted.length) {
    let share = 0;
    for (let k = 0; k < busted.length; k++) share += pay(alive.length + k);
    for (const i of busted) eq[i] = share / busted.length;
  }
  const m = alive.length;
  if (m === 0) return eq;
  if (m > 24) throw new Error("ICM exato limitado a 24 jogadores vivos");
  const paid = Math.min(m, payouts.length);
  const st = alive.map((i) => stacks[i]!);
  const total = st.reduce((a, b) => a + b, 0);
  const full = 1 << m;
  const prob = new Float64Array(full);
  prob[0] = 1;
  for (let mask = 0; mask < full; mask++) {
    const p = prob[mask]!;
    if (p === 0) continue;
    let place = 0, used = 0;
    for (let j = 0; j < m; j++) if (mask & (1 << j)) { place++; used += st[j]!; }
    if (place >= paid) continue; // lugares seguintes pagam zero
    const rem = total - used;
    if (rem <= 0) continue;
    const value = pay(place);
    for (let j = 0; j < m; j++) {
      if (mask & (1 << j)) continue;
      const pj = (p * st[j]!) / rem;
      eq[alive[j]!]! += pj * value;
      prob[mask | (1 << j)]! += pj;
    }
  }
  return eq;
}

/** Monte Carlo do Malmuth–Harville com semente fixa (mesmos sorteios para cenários comparados). */
/** Sorteios −ln(U) reaproveitados entre chamadas (mesma semente = mesmos sorteios = comparações sem ruído). */
const expCache = new Map<string, Float64Array>();
function exponentials(n: number, samples: number, seed: number): Float64Array {
  const key = `${n}|${samples}|${seed}`;
  let e = expCache.get(key);
  if (!e) {
    const r = createRng(seed);
    e = new Float64Array(n * samples);
    for (let i = 0; i < e.length; i++) e[i] = -Math.log(r.next() || 1e-12);
    expCache.set(key, e);
    if (expCache.size > 8) expCache.delete(expCache.keys().next().value as string);
  }
  return e;
}

export function icmMonteCarlo(stacks: number[], payouts: number[], samples = ICM_MC_SAMPLES, seed = 20261017): number[] {
  const n = stacks.length;
  const eq = new Array<number>(n).fill(0);
  const E = exponentials(n, samples, seed);
  const keys = new Float64Array(n);
  const idx = new Uint16Array(n);
  const paid = Math.min(payouts.length, n);
  const inv = stacks.map((s) => (s > 1e-9 ? 1 / s : Infinity));
  for (let k = 0; k < samples; k++) {
    const off = k * n;
    for (let i = 0; i < n; i++) { keys[i] = E[off + i]! * inv[i]!; idx[i] = i; }
    // Ordenação por inserção (n pequeno, tipado): mais rápida que sort com comparador.
    for (let a = 1; a < n; a++) {
      const v = idx[a]!, kv = keys[v]!;
      let b = a - 1;
      while (b >= 0 && keys[idx[b]!]! > kv) { idx[b + 1] = idx[b]!; b--; }
      idx[b + 1] = v;
    }
    for (let place = 0; place < paid; place++) eq[idx[place]!]! += payouts[place]!;
  }
  // Empates de stack zerado: os eliminados dividem os últimos lugares igualmente.
  const busted = stacks.map((s, i) => (s > 1e-9 ? -1 : i)).filter((i) => i >= 0);
  if (busted.length > 1) {
    const avg = busted.reduce((t, i) => t + eq[i]!, 0) / busted.length;
    for (const i of busted) eq[i] = avg * samples;
  }
  return eq.map((v) => v / samples);
}

export interface PairRisk {
  /** Quanto se perde ao perder o all-in ÷ quanto se ganha ao vencer (1 = chip EV). */
  bubbleFactor: number;
  /** Equity extra necessária num all-in contra este jogador: BF/(1+BF) − 50%. */
  riskPremium: number;
}

/**
 * PKO: bounty na cabeça de cada jogador (na moeda da premiação) e a parte paga em dinheiro na eliminação
 * (o resto vai para a cabeça de quem eliminou). Todos os bounties que ainda estão na mesa são ganhos na proporção
 * das fichas (o modelo do Bounty Mode PKO do HRC, conferido contra os números dele em 26/10; o mesmo do solver).
 */
export interface PkoSpec {
  heads: number[];
  cashShare: number;
  /** Fichas do torneio inteiro (para a chance de título da cabeça quando o field foi comprimido). */
  chipTotal?: number;
}

/** Valor de cada jogador: ICM + fatia de fichas × bounties na mesa (+ dinheiro já ganho em bounties, se informado). */
export function playerValues(stacks: number[], payouts: number[], pko?: PkoSpec | null, cash?: number[]): number[] {
  const icm = icmValues(stacks, payouts);
  if (!pko) return icm;
  const total = pko.chipTotal ?? (stacks.reduce((a, b) => a + Math.max(0, b), 0) || 1);
  const pool = pko.heads.reduce((a, b) => a + (b ?? 0), 0);
  return icm.map((v, i) => v + (cash?.[i] ?? 0) + pool * (Math.max(0, stacks[i]!) / total));
}

/** Estado depois de um all-in: quem perde tudo entrega o bounty (parte em dinheiro, parte na cabeça). */
function afterAllIn(stacks: number[], winner: number, loser: number, eff: number, pko?: PkoSpec | null): { stacks: number[]; pko: PkoSpec | null; cash: number[] } {
  const st = [...stacks]; st[winner]! += eff; st[loser]! -= eff;
  const cash = stacks.map(() => 0);
  if (!pko || st[loser]! > 1e-9) return { stacks: st, pko: pko ?? null, cash };
  const heads = [...pko.heads];
  const b = heads[loser] ?? 0;
  cash[winner] = b * pko.cashShare;
  heads[winner] = (heads[winner] ?? 0) + b * (1 - pko.cashShare);
  heads[loser] = 0;
  return { stacks: st, pko: { ...pko, heads }, cash };
}

/**
 * Bubble factor / risk premium de `i` contra `j` num all-in pelo stack efetivo.
 * Com PKO, o bounty de quem é eliminado entra na conta: risk premium negativo = desconto (equity drop).
 */
export function pairRisk(stacks: number[], payouts: number[], i: number, j: number, base?: number[], pko?: PkoSpec | null): PairRisk {
  const eff = Math.min(stacks[i]!, stacks[j]!);
  if (eff <= 0) return { bubbleFactor: 1, riskPremium: 0 };
  const now = base ?? playerValues(stacks, payouts, pko);
  const w = afterAllIn(stacks, i, j, eff, pko);
  const l = afterAllIn(stacks, j, i, eff, pko);
  const gain = playerValues(w.stacks, payouts, w.pko, w.cash)[i]! - now[i]!;
  const loss = now[i]! - playerValues(l.stacks, payouts, l.pko, l.cash)[i]!;
  if (gain <= 1e-12) return { bubbleFactor: Infinity, riskPremium: 0.5 };
  const bf = loss / gain;
  return { bubbleFactor: bf, riskPremium: bf / (1 + bf) - 0.5 };
}

/** Matriz de risk premium entre os jogadores indicados (linha = quem arrisca, coluna = adversário). */
export function riskMatrix(stacks: number[], payouts: number[], players: number[] = stacks.map((_, i) => i), pko?: PkoSpec | null): PairRisk[][] {
  const base = playerValues(stacks, payouts, pko);
  return players.map((i) => players.map((j) => (i === j ? { bubbleFactor: 1, riskPremium: 0 } : pairRisk(stacks, payouts, i, j, base, pko))));
}

/** Curva modelo top-heavy de MTT para N pagos (em unidades relativas). */
export function modelPrizes(paid: number): number[] {
  const base = [20, 14, 10, 7.5, 5.8, 4.5, 3.5, 2.7, 2.1];
  const out: number[] = [];
  for (let i = 0; i < paid; i++) out.push(i < base.length ? base[i]! : Math.max(1.2, out[i - 1]! * 0.88));
  return out;
}

export interface FieldInput {
  /** Stacks dos jogadores da mesa (qualquer unidade, a mesma para todos). */
  table: number[];
  /** Jogadores restantes no torneio (≥ jogadores da mesa). Ausente = só a mesa. */
  remaining?: number | null;
  /** Lugares pagos. Ausente = premiação informada ou todos da mesa pagos. */
  paid?: number | null;
  /** Prêmios reais do 1º lugar para baixo. Ausente = curva modelo. */
  prizes?: number[] | null;
  /** Stack médio dos jogadores das outras mesas (mesma unidade). Ausente = média da mesa. */
  otherAvg?: number | null;
  /** Teto de jogadores no cálculo (o field é comprimido na mesma proporção acima disso). */
  maxField?: number;
  /** Sem premiação real: total que falta pagar (a curva modelo é escalada para este valor). */
  prizePool?: number | null;
  /** PKO: bounty de cada jogador da mesa (moeda da premiação). */
  bounties?: number[] | null;
  /** PKO: bounty médio de quem está nas outras mesas. Ausente = média da mesa. */
  otherBounty?: number | null;
  /** PKO: parte do bounty paga em dinheiro (0,5 no PKO padrão; 1 no KO normal). */
  cashShare?: number;
}
export interface FieldModel {
  stacks: number[];
  payouts: number[];
  /** Índices dos jogadores da mesa dentro de `stacks` (os primeiros). */
  table: number[];
  others: number;
  compressed: boolean;
  prizeSource: "informada" | "modelo";
  label: string;
  pko: PkoSpec | null;
}

/**
 * Comprime a premiação de `remaining` jogadores para `total` assentos mantendo o valor médio por assento
 * (o valor de cada ficha não muda, o que importa para comparar com bounties):
 * - perto da bolha: os últimos lugares pagos ficam um a um (o salto imediato) e o topo vira 3 blocos médios;
 * - longe dela: cada assento representa um bloco de lugares (média dos prêmios do bloco).
 */
export function compressPrizes(real: number[], remaining: number, total: number, nearBubble: boolean): number[] {
  const gap = remaining - real.length;
  if (nearBubble) {
    // Mantém os assentos fora do dinheiro (o salto da bolha) e comprime os lugares pagos em blocos médios.
    const paid = Math.max(1, total - gap);
    return Array.from({ length: paid }, (_, k) => {
      const a = Math.floor((k * real.length) / paid), b = Math.max(a + 1, Math.floor(((k + 1) * real.length) / paid));
      const xs = real.slice(a, b);
      return xs.reduce((t, x) => t + x, 0) / xs.length;
    });
  }
  const g = remaining / total;
  const out: number[] = [];
  for (let k = 0; k < total; k++) {
    const a = Math.floor(k * g), b = Math.max(a + 1, Math.floor((k + 1) * g));
    let s = 0;
    for (let r = a; r < b; r++) s += real[r] ?? 0;
    const v = s / (b - a);
    if (v <= 0) break;
    out.push(v);
  }
  return out.length ? out : [real[0] ?? 1];
}

/** Monta o field do cálculo: mesa + outras mesas + premiação. */
export function fieldModel(f: FieldInput): FieldModel {
  const n = f.table.length;
  const remaining = Math.max(n, f.remaining ?? n);
  // Perto da bolha a compressão distorce o salto de premiação: usa o field real (Monte Carlo) até 40.
  const nearMoney = remaining - Math.min(remaining, f.paid ?? remaining) <= ICM_FIELD_DEFAULT / 2;
  const maxField = Math.max(n, f.maxField ?? (nearMoney ? 40 : ICM_FIELD_DEFAULT));
  const total = Math.min(remaining, maxField);
  const compressed = remaining > maxField;
  const paidRaw = Math.min(remaining, f.paid ?? (f.prizes?.length ? f.prizes.length : n));
  // Comprimir: perto da bolha preserva quantos faltam para o dinheiro (o salto imediato é o que pesa);
  // longe dela, mantém a proporção de pagos.
  const gap = remaining - paidRaw;
  let realPrizes = f.prizes?.length ? f.prizes.slice(0, paidRaw) : modelPrizes(paidRaw);
  if (!f.prizes?.length && f.prizePool && f.prizePool > 0) {
    const s = realPrizes.reduce((a, b) => a + b, 0);
    realPrizes = realPrizes.map((x) => (x / s) * f.prizePool!);
  }
  let prizes = compressed ? compressPrizes(realPrizes, remaining, total, gap <= total / 2) : realPrizes;
  const paid = prizes.length;
  const avg = f.otherAvg && f.otherAvg > 0 ? f.otherAvg : f.table.reduce((a, b) => a + b, 0) / n;
  const others = total - n;
  const stacks = [...f.table, ...Array.from({ length: others }, () => avg)];
  if (compressed) {
    // Mesmo valor por ficha do torneio real: a premiação comprimida vale a fatia de fichas do field comprimido.
    const tableChips = f.table.reduce((a, b) => a + b, 0);
    const realChips = tableChips + (remaining - n) * avg;
    const compChips = tableChips + others * avg;
    const realTotal = realPrizes.reduce((a, b) => a + b, 0);
    const compTotal = prizes.reduce((a, b) => a + b, 0) || 1;
    const k = ((compChips / realChips) * realTotal) / compTotal;
    prizes = prizes.map((x) => x * k);
  }
  const bubble = remaining > paidRaw ? `faltam ${remaining - paidRaw} para o dinheiro` : "todos no dinheiro";
  const label = `${remaining} restantes, ${paidRaw} pagos (${bubble}); premiação ${f.prizes?.length ? "informada" : "modelo"}${others ? `; ${remaining - n} jogadores de outras mesas com stack ${Math.round(avg * 10) / 10} cada` : ""}${compressed ? `; field comprimido para ${total} jogadores e ${paid} pagos` : ""}.`;
  let pko: PkoSpec | null = null;
  if (f.bounties?.length) {
    const tb = f.table.map((_, i) => f.bounties![i] ?? 0);
    const ob = f.otherBounty && f.otherBounty > 0 ? f.otherBounty : tb.reduce((a, b) => a + b, 0) / n;
    pko = { heads: [...tb, ...Array.from({ length: others }, () => ob)], cashShare: f.cashShare ?? 0.5, chipTotal: f.table.reduce((a, b) => a + b, 0) + (remaining - n) * avg };
  }
  return { stacks, payouts: prizes, table: f.table.map((_, i) => i), others, compressed, prizeSource: f.prizes?.length ? "informada" : "modelo", label, pko };
}

/** Acordo: valor de ICM e divisão proporcional às fichas (chip chop) para quem está na mesa. */
export function dealValues(stacks: number[], prizes: number[]): { icm: number[]; chipChop: number[] } {
  const icm = icmValues(stacks, prizes);
  const n = stacks.length;
  const pool = prizes.slice(0, n).reduce((a, b) => a + b, 0);
  const minPrize = prizes[n - 1] ?? 0;
  const chips = stacks.reduce((a, b) => a + b, 0) || 1;
  // Chip chop clássico: todos garantem o último prêmio e o resto é dividido pelas fichas.
  const chipChop = stacks.map((s) => minPrize + ((pool - minPrize * n) * s) / chips);
  return { icm, chipChop };
}

/** Faixa de intensidade do risk premium (para cores e textos). */
export function riskBand(rp: number): "chip" | "leve" | "moderado" | "forte" | "extremo" | "desconto" {
  if (rp < -0.005) return "desconto";
  if (rp < 0.02) return "chip";
  if (rp < 0.06) return "leve";
  if (rp < 0.1) return "moderado";
  if (rp < 0.2) return "forte";
  return "extremo";
}
