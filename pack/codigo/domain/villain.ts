/**
 * Vilões com estilo e stats (HUD do PPPoker): cada adversário da mesa recebe um perfil (Tight, Regular, Agressivo,
 * Maníaco), um nick, um avatar e um quadro de stats coerente com o perfil, como o jogador vê no app.
 *
 * Etapa 1 (27/10, pedido do Eduardo): só o visual. A estratégia do trainer ainda não muda com o perfil; a etapa 2 vai
 * derivar o range do vilão dos stats (ex.: 3-Bet % → range de 3bet) e calcular a resposta do herói contra ele.
 *
 * As faixas de cada perfil são uma premissa explícita e editável (valores típicos de MTT online), não saída de solver.
 * Tudo é determinístico pela seed da mão e pelo assento, com um RNG derivado: a mão (cartas, posições, stacks) não muda.
 */
import { createRng, deriveSeed } from "./rng";
import type { Position } from "./positions";
import type { SpotType, TrainingScenario } from "./scenario";
import type { TableState } from "./table";

export type VillainProfile = "tight" | "regular" | "aggressive" | "maniac";

export const VILLAIN_PROFILES: { v: VillainProfile; label: string; hint: string; weight: number }[] = [
  { v: "tight", label: "Tight", hint: "Joga poucas mãos e 3beta pouco (3-Bet ~4%): range forte e previsível.", weight: 25 },
  { v: "regular", label: "Regular", hint: "Perfil médio de MTT (3-Bet ~8%).", weight: 40 },
  { v: "aggressive", label: "Agressivo", hint: "Rouba e 3beta bastante (3-Bet ~12%): range com mais blefes.", weight: 25 },
  { v: "maniac", label: "Maníaco", hint: "Joga muitas mãos e 3beta muito (3-Bet 16%+).", weight: 10 },
];

/** Os campos do quadro de stats do PPPoker (perfil do jogador). Percentuais inteiros. */
export interface VillainStats {
  vpip: number; pfr: number; steal: number; checkRaise: number;
  threeBet: number; foldTo3Bet: number; cbet: number; foldToCbet: number;
  itm: number; titles: number; hands: number;
  wtsd: number; wsd: number;
}

type Range = readonly [number, number];
/** Faixa [mín, máx] de cada stat por perfil. */
export const PROFILE_STATS: Record<VillainProfile, Record<keyof VillainStats, Range>> = {
  tight: { vpip: [14, 19], pfr: [11, 15], steal: [24, 32], checkRaise: [5, 8], threeBet: [3, 5], foldTo3Bet: [62, 72], cbet: [55, 64], foldToCbet: [44, 54], itm: [14, 22], titles: [0, 2], hands: [1200, 9000], wtsd: [24, 29], wsd: [52, 58] },
  regular: { vpip: [21, 27], pfr: [16, 21], steal: [36, 44], checkRaise: [8, 11], threeBet: [7, 9], foldTo3Bet: [52, 60], cbet: [60, 68], foldToCbet: [34, 44], itm: [16, 30], titles: [0, 4], hands: [2000, 15000], wtsd: [28, 33], wsd: [50, 56] },
  aggressive: { vpip: [28, 35], pfr: [22, 28], steal: [45, 55], checkRaise: [11, 15], threeBet: [11, 13], foldTo3Bet: [42, 50], cbet: [66, 75], foldToCbet: [28, 36], itm: [14, 28], titles: [0, 5], hands: [1500, 12000], wtsd: [30, 35], wsd: [48, 54] },
  maniac: { vpip: [38, 55], pfr: [28, 40], steal: [55, 70], checkRaise: [15, 22], threeBet: [15, 22], foldTo3Bet: [30, 42], cbet: [72, 85], foldToCbet: [20, 30], itm: [8, 22], titles: [0, 3], hands: [600, 6000], wtsd: [33, 40], wsd: [44, 50] },
};

export interface VillainInfo {
  seat: number;
  position: Position;
  profile: VillainProfile;
  name: string;
  /** ID e nível como no app (decorativos). */
  id: number;
  level: number;
  club: string;
  /** Parâmetros do avatar desenhado (sem imagens de terceiros). */
  avatar: { hue: number; skin: number; hair: number; style: number; accessory: number };
  stats: VillainStats;
}

const NICK_A = ["Ace", "River", "Shark", "Lucky", "Bluff", "Tilt", "Nuts", "Fold", "Push", "Grind", "Snap", "Cooler", "Donk", "Fish", "Rock", "Maverick", "Viper", "Ghost", "Joker", "Raven"];
const NICK_B = ["King", "Queen", "Hunter", "Master", "Boy", "Girl", "Pro", "Kid", "Lord", "Machine", "Zero", "BR", "77", "99", "_x", "Jr", "Dealer", "Storm", "Wolf", "Fox"];
const CLUBS = ["NVT Team", "No-Limit Ninjas", "Ace_High_Society", "Royal Flush Club", "Final Table BR", "Deep Stack Union"];

const SALT = 0x51a7_0000;

/** Vilão de um assento, determinístico pela seed da mão. */
export function villainFor(seed: number, seat: number, position: Position): VillainInfo {
  const r = createRng(deriveSeed(seed, SALT + seat));
  const total = VILLAIN_PROFILES.reduce((a, p) => a + p.weight, 0);
  let x = r.next() * total, profile: VillainProfile = "regular";
  for (const p of VILLAIN_PROFILES) { if ((x -= p.weight) < 0) { profile = p.v; break; } }
  const ranges = PROFILE_STATS[profile];
  const pick = ([lo, hi]: Range) => Math.round(lo + r.next() * (hi - lo));
  const stats = Object.fromEntries((Object.keys(ranges) as (keyof VillainStats)[]).map((k) => [k, pick(ranges[k])])) as unknown as VillainStats;
  stats.pfr = Math.min(stats.pfr, stats.vpip - 2);
  const name = `${NICK_A[r.int(NICK_A.length)]}${NICK_B[r.int(NICK_B.length)]}`;
  return {
    seat, position, profile, name,
    id: 13_000_000 + r.int(900_000), level: 1 + r.int(5), club: CLUBS[r.int(CLUBS.length)]!,
    avatar: { hue: r.int(360), skin: r.int(4), hair: r.int(6), style: r.int(3), accessory: r.int(4) },
    stats,
  };
}

/** Spots com vilão em destaque. Open raise é o mais básico: sem quadro de stats. */
export const showsVillains = (spot: SpotType) => spot !== "open_raise";

/** Assentos dos vilões em destaque: quem agrediu (open, shove, 3bet); senão quem limpou; senão o BB (first-in). */
export function focusVillainSeats(s: Pick<TrainingScenario, "spot" | "table">): number[] {
  const t = s.table;
  const bySeat = (pos: Position) => t.players.find((p) => p.position === pos)?.seat;
  const agg = s.spot.aggressors.map(bySeat).filter((x): x is number => x !== undefined);
  if (agg.length) return agg;
  const limper = t.actions.find((a) => a.type === "limp" && a.seat !== t.heroSeat)?.seat;
  if (limper !== undefined) return [limper];
  if (s.spot.type === "limp" || s.spot.type === "limp_call") { const bb = bySeat("BB"); return bb !== undefined ? [bb] : []; }
  // First-in (open shove): quem fala depois do herói decide se paga; o BB é o principal.
  const bb = bySeat("BB");
  return bb !== undefined && bb !== t.heroSeat ? [bb] : [];
}

/** Vilões de todos os adversários da mesa (avatar + stats), para a mesa e o painel. */
export function tableVillains(seed: number, table: TableState): VillainInfo[] {
  return table.players.filter((p) => !p.isHero).map((p) => villainFor(seed, p.seat, p.position));
}

export const profileLabel = (p: VillainProfile) => VILLAIN_PROFILES.find((x) => x.v === p)!.label;

/** Seed estável a partir de um texto (rotas de treino sem seed própria, ex.: 3bet e c-bet). FNV-1a 32 bits. */
export function seedFromText(text: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return h >>> 0;
}

/** Assentos das posições pedidas (vilão em destaque quando o spot já diz quem é). */
export const seatsOf = (table: TableState, positions: Position[]) =>
  positions.map((pos) => table.players.find((p) => p.position === pos)?.seat).filter((x): x is number => x !== undefined);
