/**
 * Navegador da árvore de ações de um arquivo do HRC (puro).
 *
 * Os arquivos importados (scripts/import-hrc.py) guardam os nós pré-flop que o trainer usa:
 *   Raiz → open de cada posição (todos foldaram) → resposta de cada posição atrás ao open de 2bb
 *        → resposta do opener à 3bet;
 *   Raiz → Blind War (SB first in) → BB contra o limp → SB contra o iso (→ BB contra o limp/jam)
 *                                                    → SB contra o all-in do BB.
 * Cada nó traz frequência e EV de cada ação por mão. Aqui eles viram uma árvore navegável: id de cada nó,
 * pai, filhos (pela ação que leva até eles), ações na ordem ALL_HANDS com EV relativo à base (fold ou check),
 * e o alcance do jogador no nó (quanto de cada mão chega até ali pelas ações dele mesmo antes).
 */
import { ALL_HANDS, combos, type HandKey } from "@/domain/cards";
import type { Position } from "@/domain/positions";
import type { DecisionAction } from "@/domain/scenario";
import type { GridCell } from "../strategy-grid";
import type { IslandFix } from "./island-smooth";
import type { PairFix } from "./pair-order";
import { POS9, type LimpAct, type PreflopPreset } from "./catalog";

/** Abaixo disto a mão não chega ao nó (fica hachurada na matriz). */
export const REACH_MIN = 0.005;

export interface TreeAction { key: string; action: DecisionAction; label: string; freq: number[]; ev: number[] | null }
export interface TreeChild { id: string; via: DecisionAction; label: string }
export interface TreeNode {
  id: string;
  /** Quem decide neste nó. */
  actor: Position;
  /** Título curto para a trilha ("Open CO", "BTN vs open CO"). */
  title: string;
  /** O que aconteceu antes ("Todos foldaram até o CO, que abriu 2bb; o BTN decide"). */
  situation: string;
  actions: TreeAction[];
  /** Base do EV mostrado ("fold" ou "check"). */
  evBase: "fold" | "check";
  /** Alcance de cada mão (ordem ALL_HANDS); null = todas chegam. */
  reach: number[] | null;
  /** Rótulo das mãos que não chegam ("Não abre", "Não limpa"…). */
  outLabel: string;
  children: TreeChild[];
  /** Nome do nó nos ajustes do trainer (pairFixes / islandFixes). */
  fixNode: string;
}

type Arr = number[];
type P = Pick<PreflopPreset, "idx" | "rfi" | "resp" | "opv3" | "limp" | "unit">;
const arr = (p: P, a: Arr | undefined) => ALL_HANDS.map((_, i) => a?.[p.idx[i]!] ?? 0);
const minus = (a: Arr, b: Arr) => a.map((x, i) => x - (b[i] ?? 0));
const rest = (...fs: Arr[]) => fs[0]!.map((_, i) => Math.max(0, 1 - fs.reduce((s, f) => s + (f[i] ?? 0), 0)));
const sz = (x: number | null | undefined) => (x == null ? "" : `${String(Math.round(x * 100) / 100).replace(".", ",")}bb`);

/** Preset cru (sem a ordem dos pares nem a suavização que o trainer aplica): só o índice das mãos. */
export function rawHrcPreset(raw: unknown): P & { name: string } {
  const d = raw as Omit<PreflopPreset, "idx">;
  const pos = new Map(d.hands.map((h, i) => [h, i]));
  return { ...d, idx: ALL_HANDS.map((h) => pos.get(h) ?? -1) };
}

/** Nós da Blind War no arquivo (inclui o BB contra o limp/jam, que o tipo LimpData não lista). */
type LimpNodes = { sb?: Record<string, LimpAct>; bbVsLimp?: Record<string, LimpAct>; sbVsIso?: Record<string, LimpAct>; sbVsJam?: Record<string, LimpAct>; bbVsLimpJam?: Record<string, LimpAct>; raiseSize?: number | null; isoSize?: number | null };
const limpOf = (p: P) => p.limp as LimpNodes | undefined;

const LIMP_ACTION: Record<string, DecisionAction> = { fold: "fold", call: "call", check: "check", raise: "raise", allin: "all_in" };
function limpActions(p: P, n: Record<string, LimpAct>, base: "fold" | "check", labels: Record<string, string>, callAs: DecisionAction = "call"): TreeAction[] {
  const b = n[base] ? arr(p, n[base]!.ev) : null;
  return ["allin", "raise", "call", "check", "fold"].filter((k) => n[k]).map((k) => ({
    key: k, action: k === "call" ? callAs : LIMP_ACTION[k]!, label: labels[k] ?? k,
    freq: arr(p, n[k]!.freq), ev: b ? minus(arr(p, n[k]!.ev), b) : null,
  }));
}
const freqOf = (n: TreeNode | null, key: string) => n?.actions.find((a) => a.key === key)?.freq ?? null;

/** Pai do nó na árvore (null na raiz). Com o arquivo, a resposta ao raise da SB fica abaixo da Blind War. */
export function parentId(id: string, p?: P): string | null {
  if (id === "root") return null;
  const [kind, arg = ""] = id.split(":");
  if (kind === "open" || id === "limp:sb") return "root";
  if (kind === "resp") { const X = arg.split(">")[0]!; return X === "SB" && p ? sbEntry(p) : `open:${X}`; }
  if (kind === "opv3") return `resp:${arg}`;
  if (id === "limp:bb") return "limp:sb";
  if (id === "limp:iso" || id === "limp:jam") return "limp:bb";
  if (id === "limp:limpjam") return "limp:iso";
  return "root";
}
/** Caminho da raiz até o nó (inclusive). */
export function pathTo(id: string, p?: P): string[] {
  const out: string[] = [];
  for (let cur: string | null = id; cur; cur = parentId(cur, p)) out.unshift(cur);
  return out;
}

/** Id do primeiro nó da SB: Blind War com limp quando o arquivo tem, senão o open da SB. */
export const sbEntry = (p: P) => (limpOf(p)?.sb ? "limp:sb" : "open:SB");

export function treeNode(p: P, id: string): TreeNode | null {
  const [kind, arg = ""] = id.split(":");
  const L = limpOf(p);
  if (kind === "open") {
    const X = arg as Position; const n = p.rfi[X]; if (!n) return null;
    const raise = arr(p, n.raise), shove = arr(p, n.shove), evF = arr(p, n.ev.fold);
    const children = POS9.filter((Y) => p.resp[`${X}>${Y}`]).map((Y) => ({ id: `resp:${X}>${Y}`, via: "raise" as DecisionAction, label: `${Y} responde` }));
    return {
      id, actor: X, title: `Open ${X}`, situation: `Todos foldaram até o ${X}.`, evBase: "fold", reach: null, outLabel: "Não chega", fixNode: `open ${X}`, children,
      actions: [
        { key: "shove", action: "all_in", label: "All-in", freq: shove, ev: minus(arr(p, n.ev.shove), evF) },
        { key: "raise", action: "raise", label: "Raise 2bb", freq: raise, ev: minus(arr(p, n.ev.raise), evF) },
        { key: "fold", action: "fold", label: X === "SB" ? "Fold / limp" : "Fold", freq: rest(raise, shove), ev: evF.map(() => 0) },
      ],
    };
  }
  if (kind === "resp") {
    const [X, Y] = arg.split(">") as [Position, Position]; const n = p.resp[arg]; if (!n) return null;
    const call = arr(p, n.call), three = arr(p, n.three), shove = arr(p, n.shove), evF = arr(p, n.ev.fold);
    return {
      id, actor: Y, title: `${Y} vs open ${X}`, situation: `O ${X} abriu 2bb e todos foldaram até o ${Y}.`, evBase: "fold", reach: null, outLabel: "Não chega", fixNode: `vs open ${arg}`,
      children: p.opv3[arg] ? [{ id: `opv3:${arg}`, via: "three_bet", label: `${X} responde à 3bet` }] : [],
      actions: [
        { key: "shove", action: "all_in", label: "All-in", freq: shove, ev: minus(arr(p, n.ev.shove), evF) },
        { key: "three", action: "three_bet", label: "3Bet", freq: three, ev: minus(arr(p, n.ev.three), evF) },
        { key: "call", action: "call", label: "Call", freq: call, ev: minus(arr(p, n.ev.call), evF) },
        { key: "fold", action: "fold", label: "Fold", freq: rest(call, three, shove), ev: evF.map(() => 0) },
      ],
    };
  }
  if (kind === "opv3") {
    const [X, Y] = arg.split(">") as [Position, Position]; const n = p.opv3[arg]; if (!n) return null;
    const call = arr(p, n.call), shove = arr(p, n.shove), evF = n.ev ? arr(p, n.ev.fold) : null;
    return {
      id, actor: X, title: `${X} vs 3bet ${Y}`, situation: `O ${X} abriu 2bb e o ${Y} deu 3bet.`, evBase: "fold", outLabel: "Não abre", fixNode: `vs 3bet ${arg}`, children: [],
      reach: freqOf(treeNode(p, `open:${X}`), "raise"),
      actions: [
        { key: "shove", action: "all_in", label: "All-in", freq: shove, ev: n.ev && evF ? minus(arr(p, n.ev.shove), evF) : null },
        { key: "call", action: "call", label: "Call", freq: call, ev: n.ev && evF ? minus(arr(p, n.ev.call), evF) : null },
        { key: "fold", action: "fold", label: "Fold", freq: rest(call, shove), ev: evF ? evF.map(() => 0) : null },
      ],
    };
  }
  if (kind === "limp" && L) {
    if (arg === "sb" && L.sb) return {
      id, actor: "SB", title: "Blind War SB", situation: "Todos foldaram até a SB (Blind War).", evBase: "fold", reach: null, outLabel: "Não chega", fixNode: "Blind War SB",
      children: [
        ...(p.resp["SB>BB"] ? [{ id: "resp:SB>BB", via: "raise" as DecisionAction, label: "BB contra o raise" }] : []),
        ...(L.bbVsLimp ? [{ id: "limp:bb", via: "limp" as DecisionAction, label: "BB contra o limp" }] : []),
      ],
      actions: limpActions(p, L.sb, "fold", { allin: "All-in", raise: `Raise ${sz(L.raiseSize)}`, call: "Limp", fold: "Fold" }, "limp"),
    };
    if (arg === "bb" && L.bbVsLimp) {
      const base = L.bbVsLimp["check"] ? "check" : "fold";
      return {
        id, actor: "BB", title: "BB vs limp", situation: "A SB completou (limp).", evBase: base, reach: null, outLabel: "Não chega", fixNode: "BB vs limp",
        children: [
          ...(L.sbVsIso ? [{ id: "limp:iso", via: "raise" as DecisionAction, label: "SB contra o iso" }] : []),
          ...(L.sbVsJam ? [{ id: "limp:jam", via: "all_in" as DecisionAction, label: "SB contra o all-in" }] : []),
        ],
        actions: limpActions(p, L.bbVsLimp, base, { allin: "All-in", raise: `Iso ${sz(L.isoSize)}`, check: "Check", fold: "Fold" }),
      };
    }
    const sbLimp = () => freqOf(treeNode(p, "limp:sb"), "call");
    if (arg === "iso" && L.sbVsIso) return {
      id, actor: "SB", title: "SB vs iso", situation: `A SB limpou e o BB deu iso para ${sz(L.isoSize)}.`, evBase: "fold", reach: sbLimp(), outLabel: "Não limpa", fixNode: "SB vs iso",
      children: L.bbVsLimpJam ? [{ id: "limp:limpjam", via: "all_in", label: "BB contra o all-in" }] : [],
      actions: limpActions(p, L.sbVsIso, "fold", { allin: "All-in", call: "Call", fold: "Fold" }),
    };
    if (arg === "jam" && L.sbVsJam) return {
      id, actor: "SB", title: "SB vs all-in", situation: "A SB limpou e o BB foi all-in.", evBase: "fold", reach: sbLimp(), outLabel: "Não limpa", fixNode: "SB vs jam", children: [],
      actions: limpActions(p, L.sbVsJam, "fold", { call: "Call", fold: "Fold" }),
    };
    if (arg === "limpjam" && L.bbVsLimpJam) return {
      id, actor: "BB", title: "BB vs limp/jam", situation: `A SB limpou, o BB deu iso para ${sz(L.isoSize)} e a SB foi all-in.`, evBase: "fold",
      reach: freqOf(treeNode(p, "limp:bb"), "raise"), outLabel: "Não dá iso", fixNode: "BB vs limp/jam", children: [],
      actions: limpActions(p, L.bbVsLimpJam, "fold", { call: "Call", fold: "Fold" }),
    };
  }
  return null;
}

/** % dos combos que chegam ao nó e escolhem cada ação (chave da ação → %). */
export function nodeShares(n: TreeNode): Record<string, number> {
  let den = 0; const w: Record<string, number> = {};
  ALL_HANDS.forEach((h, i) => {
    const r = n.reach ? n.reach[i]! : 1; if (r < REACH_MIN) return;
    const k = combos(h) * r; den += k;
    for (const a of n.actions) w[a.key] = (w[a.key] ?? 0) + a.freq[i]! * k;
  });
  return Object.fromEntries(n.actions.map((a) => [a.key, den ? ((w[a.key] ?? 0) / den) * 100 : 0]));
}

/** Matriz do nó no formato do StrategyMatrix (mãos fora do alcance hachuradas; totais sobre quem chega). */
export function nodeMatrix(n: TreeNode, unit: "bb" | "pct") {
  const cells = {} as Record<HandKey, GridCell>;
  let reached = 0;
  ALL_HANDS.forEach((h, i) => {
    const r = n.reach ? n.reach[i]! : 1;
    const mix = n.actions.map((a) => ({ action: a.action, frequency: a.freq[i]! })).filter((m) => m.frequency > 0.0005).sort((a, b) => b.frequency - a.frequency);
    const evs = n.actions.every((a) => a.ev) ? n.actions.map((a) => ({ action: a.action, ev: a.ev![i]! })) : null;
    cells[h] = r < REACH_MIN ? { mix, evs, outOfRange: true } : { mix, evs };
    if (r >= REACH_MIN) reached += combos(h) * r;
  });
  const shares = nodeShares(n);
  return {
    cells, evUnit: unit, actions: n.actions.map((a) => a.action),
    totals: Object.fromEntries(n.actions.map((a) => [a.action, shares[a.key] ?? 0])) as Partial<Record<DecisionAction, number>>,
    labels: Object.fromEntries(n.actions.map((a) => [a.action, a.label])) as Partial<Record<DecisionAction, string>>,
    ...(n.reach ? { outOfRangePct: 100 - (reached / 1326) * 100, outLabel: n.outLabel } : {}),
  };
}

export interface RootEntry { id: string; position: Position; title: string; shares: { label: string; pct: number }[] }
/** Visão da raiz: o primeiro nó de cada posição (open, ou Blind War na SB) com o % de cada ação que não é fold. */
export function rootEntries(p: P): RootEntry[] {
  const ids = POS9.filter((X) => X !== "SB" && p.rfi[X]).map((X) => `open:${X}`);
  if (limpOf(p)?.sb || p.rfi["SB"]) ids.push(sbEntry(p));
  return ids.flatMap((id) => {
    const n = treeNode(p, id); if (!n) return [];
    const s = nodeShares(n);
    return [{ id, position: n.actor, title: n.title, shares: n.actions.filter((a) => a.action !== "fold").map((a) => ({ label: a.label, pct: s[a.key] ?? 0 })) }];
  });
}

/** Ajustes do trainer neste nó: pares corrigidos, mãos suavizadas e destoantes confirmadas pelo EV. */
export function nodeFixes(p: Pick<PreflopPreset, "pairFixes" | "islandFixes" | "islandConfident">, n: TreeNode): { pairs: PairFix[]; smoothed: IslandFix[]; confident: IslandFix[] } {
  const of = <T extends { node: string }>(l: T[] | undefined) => (l ?? []).filter((f) => f.node === n.fixNode);
  return { pairs: of(p.pairFixes), smoothed: of(p.islandFixes), confident: of(p.islandConfident) };
}

/** Mãos cuja frequência difere entre dois lados do mesmo nó (trainer × HRC original), na ordem ALL_HANDS. */
export function changedHands(a: TreeNode, b: TreeNode, tol = 0.0005): HandKey[] {
  return ALL_HANDS.filter((_, i) => a.actions.some((x) => Math.abs(x.freq[i]! - (b.actions.find((y) => y.key === x.key)?.freq[i] ?? 0)) > tol));
}
