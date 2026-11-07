/**
 * Tabelas do NVT Poker Team (transcritas das imagens enviadas pelo time, célula por célula;
 * cada tabela com legenda visível conferida contra os percentuais da própria legenda).
 * Grade 13×13: linha i, coluna j (A..2); i<j suited, i>j offsuit, i=j par.
 */
import { cellHand, type HandKey } from "@/domain/cards";
import type { Position } from "@/domain/positions";
import type { StackBucket, StrategyContext } from "@/domain/scenario";
import type { RangeDefinition } from "./types";
import { rangeId } from "./types";

export const NVT_TEAM_VERSION = "nvt-team-1";

export type NvtGroup = "open" | "pko_shove" | "sb_limp";
export interface NvtChart {
  id: string;
  group: NvtGroup;
  /** Conjunto das tabelas de open (A, B, C = do mais largo ao mais apertado). */
  set: "A" | "B" | "C" | null;
  label: string;
  /** Posições do trainer cobertas por esta tabela. */
  positions: Position[];
  rows: string[];
}

export interface NvtLegendItem { code: string; label: string; color: string; frequency?: number }

/** Legendas (cores parecidas com as tabelas originais). */
export const NVT_LEGENDS: Record<NvtGroup, NvtLegendItem[]> = {
  open: [
    { code: "S", label: "Open 2.5x", color: "#e53935", frequency: 1 },
    { code: "m", label: "Conferir (mista)", color: "#fb8c00", frequency: 0.5 },
  ],
  pko_shove: [
    { code: "S", label: "Shove", color: "#1b8a1b" },
    { code: "r", label: "Shove KO baixo", color: "#e53935" },
    { code: "x", label: "Exploit: shove KO baixo", color: "#f2716b" },
    { code: "y", label: "Shove KO muito alto", color: "#f5e663" },
    { code: "c", label: "Fold KO alto", color: "#7ff3f3" },
    { code: "b", label: "Fold KO muito alto", color: "#1e40ff" },
    { code: "l", label: "Limp exploit vs passivo", color: "#f2716b" },
  ],
  sb_limp: [
    { code: "R", label: "Raise 2.5x", color: "#1e40ff" },
    { code: "k", label: "Limp/Call", color: "#f5e663" },
    { code: "j", label: "Limp/Jam", color: "#1b8a1b" },
    { code: "f", label: "Limp/Fold", color: "#f2716b" },
  ],
};

export const NVT_GROUP_INFO: Record<NvtGroup, { title: string; note: string }> = {
  open: { title: "Open 2.5x", note: "Três conjuntos do mais largo ao mais apertado: A = 100bb e 40bb, B = 25bb, C = 15bb (com stack menor as posições iniciais apertam, pela ameaça de reshove). \"Conferir\" = mão mista (as duas ações valem)." },
  pko_shove: { title: "Shove PKO", note: "Stack: o tamanho dos ranges bate com o Nash de ~15–17bb → treino no stack 15bb do PKO. KO = seu bounty (metade em dinheiro, em fichas) ÷ seu stack: baixo < 40%, normal 40–60%, alto 60–100%, muito alto > 100%. \"Shove KO muito alto\" da SB olha o bounty do BB. Exploits não são cobrados. EP = UTG/UTG+1, MP = UTG+2/LJ." },
  sb_limp: { title: "SB 25bb", note: "SB contra BB, todos foldaram. Treinável em Blind War: 1º raise ou limp; depois do limp, contra o iso-raise do BB (3bb, o size padrão da teoria), call, jam ou fold conforme a cor." },
};

/** Stacks do trainer cobertos por cada conjunto de open (ajustável quando o time confirmar). */
export const NVT_OPEN_SET_STACKS: Record<"A" | "B" | "C", StackBucket[]> = { A: [100, 40], B: [25], C: [15] };

export const NVT_CHARTS: NvtChart[] = [
  { id: "open-A-UTG", group: "open", set: "A", label: "UTG", positions: ["UTG"], rows: ["SSSSSSSm.S...", "SSSSSm.......", "SmSSS........", "m..SS........", "....SS.......", ".....S.......", "......S......", ".......S.....", "........S....", ".............", ".............", ".............", "............."] },
  { id: "open-A-UTG+1", group: "open", set: "A", label: "UTG+1", positions: ["UTG+1"], rows: ["SSSSSSSSSSS..", "SSSSSS.......", "SSSSSm.......", "S..SSm.......", "....SS.......", ".....S.......", "......S......", ".......S.....", "........S....", ".........m...", ".............", ".............", "............."] },
  { id: "open-A-MP", group: "open", set: "A", label: "MP", positions: ["UTG+2"], rows: ["SSSSSSSSSSSm.", "SSSSSS.......", "SSSSSS.......", "S..SSS.......", "S...SS.......", ".....S.......", "......S......", ".......S.....", "........S....", ".........S...", "..........m..", ".............", "............."] },
  { id: "open-A-LJ", group: "open", set: "A", label: "LJ", positions: ["LJ"], rows: ["SSSSSSSSSSSSm", "SSSSSSS......", "SSSSSS.......", "Sm.SSS.......", "S...SSm......", ".....Sm......", "......S......", ".......S.....", "........S....", ".........S...", "..........S..", ".............", "............."] },
  { id: "open-A-HJ", group: "open", set: "A", label: "HJ", positions: ["HJ"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSSS...", "SSSSSSS......", "SSSSSSS......", "SSmmSSS......", "S....SSS.....", "......SS.....", ".......SS....", "........Sm...", ".........Sm..", "..........S..", "...........S.", "............S"] },
  { id: "open-A-CO", group: "open", set: "A", label: "CO", positions: ["CO"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSSSSS.", "SSSSSSSSSm...", "SSSSSSSS.....", "SSSSSSSS.....", "SS..mSSS.....", "S.....SSS....", "m......SS....", "........SS...", ".........SS..", "..........S..", "...........S.", "............S"] },
  { id: "open-A-BTN", group: "open", set: "A", label: "BTN", positions: ["BTN"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSSSSSS", "SSSSSSSSSSSSS", "SSSSSSSSSSSm.", "SSSSSSSSSSm..", "SSSSSSSSSS...", "SSSSSSSSSS...", "SS.....SSS...", "SS......SSS..", "S........SSS.", "S.........S..", "S..........S.", "m...........S"] },
  { id: "open-B-UTG", group: "open", set: "B", label: "UTG", positions: ["UTG"], rows: ["SSSSSSS..S...", "SSSSSm.......", "S.SSS........", "...SS........", "....Sm.......", ".....S.......", "......S......", ".......S.....", "........m....", ".............", ".............", ".............", "............."] },
  { id: "open-B-UTG+1", group: "open", set: "B", label: "UTG+1", positions: ["UTG+1"], rows: ["SSSSSSS..Sm..", "SSSSSS.......", "S.SSS........", "...SS........", "....SS.......", ".....S.......", "......S......", ".......S.....", "........S....", ".............", ".............", ".............", "............."] },
  { id: "open-B-MP", group: "open", set: "B", label: "MP", positions: ["UTG+2"], rows: ["SSSSSSSSSSS..", "SSSSSS.......", "SSSSSS.......", "S..SSS.......", "....SS.......", ".....S.......", "......S......", ".......S.....", "........S....", ".............", ".............", ".............", "............."] },
  { id: "open-B-LJ", group: "open", set: "B", label: "LJ", positions: ["LJ"], rows: ["SSSSSSSSSSSS.", "SSSSSSm......", "SSSSSS.......", "S..SSS.......", "S...SSm......", ".....SS......", "......S......", ".......S.....", "........S....", ".........S...", ".............", ".............", "............."] },
  { id: "open-B-HJ", group: "open", set: "B", label: "HJ", positions: ["HJ"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSSm...", "SSSSSSS......", "SSmSSSS......", "Sm..SSS......", "m....SSm.....", "......SS.....", ".......SS....", "........SS...", ".........Sm..", "..........S..", ".............", "............."] },
  { id: "open-B-CO", group: "open", set: "B", label: "CO", positions: ["CO"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSSSSm.", "SSSSSSSSSm...", "SSSSSSSS.....", "SSSSSSSS.....", "Sm...SSSm....", "S.....SSS....", ".......SS....", "........SS...", ".........SS..", "..........S..", "...........S.", "............S"] },
  { id: "open-B-BTN", group: "open", set: "B", label: "BTN", positions: ["BTN"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSSSSSS", "SSSSSSSSSSSSS", "SSSSSSSSSSSm.", "SSSSSSSSSSm..", "SSSSSSSSSS...", "SSSSSSSSSS...", "SS.....SSSm..", "Sm......SSS..", "S........SSS.", "S.........Sm.", "S..........S.", "m...........S"] },
  { id: "open-C-UTG", group: "open", set: "C", label: "UTG", positions: ["UTG"], rows: ["SSSSSSm..S...", "SSSSSm.......", "SmSSS........", "...SS........", "....S........", ".....S.......", "......S......", ".......S.....", ".............", ".............", ".............", ".............", "............."] },
  { id: "open-C-UTG+1", group: "open", set: "C", label: "UTG+1", positions: ["UTG+1"], rows: ["SSSSSSS..S...", "SSSSSS.......", "SSSSS........", "...SS........", "....SS.......", ".....S.......", "......S......", ".......S.....", "........S....", ".............", ".............", ".............", "............."] },
  { id: "open-C-MP", group: "open", set: "C", label: "MP", positions: ["UTG+2"], rows: ["SSSSSSSSSSS..", "SSSSSS.......", "SSSSSm.......", "S..SSm.......", "m...SS.......", ".....S.......", "......S......", ".......S.....", "........S....", ".............", ".............", ".............", "............."] },
  { id: "open-C-LJ", group: "open", set: "C", label: "LJ", positions: ["LJ"], rows: ["SSSSSSSSSSSS.", "SSSSSSS......", "SSSSSS.......", "Sm.SSS.......", "S...SSm......", ".....Sm......", "......S......", ".......S.....", "........S....", ".........S...", ".............", ".............", "............."] },
  { id: "open-C-HJ", group: "open", set: "C", label: "HJ", positions: ["HJ"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSSm...", "SSSSSSS......", "SSSSSSS......", "SSmmSSS......", "m....SS......", "......S......", ".......S.....", "........S....", ".........S...", "..........S..", ".............", "............."] },
  { id: "open-C-CO", group: "open", set: "C", label: "CO", positions: ["CO"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSSSSm.", "SSSSSSSSSm...", "SSSSSSSS.....", "SSSSSSSS.....", "Sm..mSSS.....", "S.....SSS....", ".......SS....", "........Sm...", ".........Sm..", "..........S..", "...........S.", "............S"] },
  { id: "open-C-BTN", group: "open", set: "C", label: "BTN", positions: ["BTN"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSSSSSS", "SSSSSSSSSSSSS", "SSSSSSSSSSSSm", "SSSSSSSSSSS..", "SSSSSSSSSS...", "SSSSSSSSSS...", "SS.....SSS...", "SS......SSS..", "S........SSS.", "S.........S..", "S..........S.", "m...........S"] },
  { id: "pko-EP", group: "pko_shove", set: null, label: "EP", positions: ["UTG", "UTG+1"], rows: ["SSSSSSSb.b...", "SSSSSr.......", "SSSbc........", "S..Sc........", "S...Sr.......", ".....S.......", "......S......", ".......S.....", "........S....", ".........S...", "..........r..", ".............", "............."] },
  { id: "pko-MP", group: "pko_shove", set: null, label: "MP", positions: ["UTG+2", "LJ"], rows: ["SSSSSSSSbbb..", "SSSSSr.......", "SSSSb........", "S..Sr........", "S...Sr.......", "S....S.......", "......S......", ".......S.....", "........S....", ".........S...", "..........b..", "...........r.", "............."] },
  { id: "pko-HJ", group: "pko_shove", set: null, label: "HJ", positions: ["HJ"], rows: ["SSSSSSSSSSSSS", "SSSSSScx.....", "SSSSSc.......", "SScSSr.......", "SSr.Sr.......", "S....Sx......", "S.....S......", "S......S.....", "c.......S....", "c........S...", "x.........S..", "...........b.", "............c"] },
  { id: "pko-CO", group: "pko_shove", set: null, label: "CO", positions: ["CO"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSbx...", "SSSSSSx......", "SSSSSSx......", "SSbxSSx......", "SS...Sx......", "S.....Sx.....", "S......S.....", "S.......S....", "S........S...", "S.........S..", "S..........S.", "b...........b"] },
  { id: "pko-BTN", group: "pko_shove", set: null, label: "BTN", positions: ["BTN"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSSSSSc", "SSSSSSScc....", "SSSSSSSx.....", "SSSSSSSx.....", "SScx.SSr.....", "SSx...Sr.....", "SS.....Sx....", "Sx......S....", "S........S...", "S.........S..", "S..........S.", "S...........S"] },
  { id: "pko-SB", group: "pko_shove", set: null, label: "SB", positions: ["SB"], rows: ["SSSSSSSSSSSSS", "SSSSSSSSSSSSS", "SSSSSSSSSSSSS", "SSSSSSSSSSSSS", "SSSSSSSSSrlll", "SSSSSSSSSrlll", "SSSSSSSSSrlll", "SSSSyrrSSrlll", "SSSyllllSrlll", "SSSllllllSrll", "SSS......lSll", "SSS........Sl", "SSr.........S"] },
  { id: "sb-25bb", group: "sb_limp", set: null, label: "SB 25bb", positions: ["SB"], rows: ["RRRRRRRRRkkkk", "jRkkkkkkkkkkk", "jkRkkkkkkkkkk", "jkkRkkkkRRRRR", "jkkkRkkkRRRRR", "jRRRRjkkRRRRR", "jRRRRRjkRRRRR", "jRRRRRRjkRRRR", "jRRRRRRRjRRRR", "jRfffffffjRRR", "jRffffffffjRR", "jRfffffffffjR", "jRffffffffffj"] },
];

/** Código de cada mão numa tabela. */
export function chartCodes(c: NvtChart): Record<HandKey, string> {
  const out: Record<HandKey, string> = {};
  c.rows.forEach((row, i) => [...row].forEach((code, j) => { out[cellHand(i, j)] = code; }));
  return out;
}

/** Mãos (frequência) que a tabela joga com os códigos indicados. */
export function chartHands(c: NvtChart, codes: Record<string, number>): Record<HandKey, number> {
  const out: Record<HandKey, number> = {};
  for (const [h, code] of Object.entries(chartCodes(c))) { const f = codes[code]; if (f) out[h] = f; }
  return out;
}

export function nvtOpenChart(stack: StackBucket, pos: Position): NvtChart | null {
  const set = (Object.keys(NVT_OPEN_SET_STACKS) as ("A" | "B" | "C")[]).find((k) => NVT_OPEN_SET_STACKS[k].includes(stack));
  if (!set) return null;
  return NVT_CHARTS.find((c) => c.group === "open" && c.set === set && c.positions.includes(pos)) ?? null;
}

/** Range de open do time para o contexto (null se não há tabela para essa posição/stack). */
export function nvtOpenRange(ctx: StrategyContext, pos: Position): RangeDefinition | null {
  const chart = nvtOpenChart(ctx.stack, pos);
  if (!chart) return null;
  return {
    id: `${rangeId("open_raise", ctx, pos)}|nvt-${chart.id}`, spot: "open_raise", action: "raise", position: pos, context: ctx,
    hands: chartHands(chart, { S: 1, m: 0.5 }), source: "nvt_team", version: NVT_TEAM_VERSION,
    notes: `Tabela NVT ${chart.set} · ${chart.label}. ${NVT_GROUP_INFO.open.note}`,
  };
}

/** Tabela da SB 25bb (Blind War com limp). */
export const SB_LIMP_CHART = () => NVT_CHARTS.find((c) => c.id === "sb-25bb")!;
let sbCodes: Record<HandKey, string> | null = null;
/** Código da mão na tabela da SB 25bb: R raise, k limp/call, j limp/jam, f limp/fold. */
export function sbLimpCode(hand: HandKey): string {
  sbCodes ??= chartCodes(SB_LIMP_CHART());
  return sbCodes[hand] ?? ".";
}
export const isSbLimpHand = (hand: HandKey) => ["k", "j", "f"].includes(sbLimpCode(hand));
