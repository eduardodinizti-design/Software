/**
 * Mesa do drill de 3bet no mesmo formato da mesa pré-flop (TableState + TableView), só para exibir:
 * 9-max com os stacks do contexto (`stacks.table`, UTG…BB, antes de postar), SB 0,5, BB 1 e BB-ante 1bb
 * (as mesmas premissas do motor). Todos foldam até o opener, que abre `open_bb`; foldam até o herói.
 */
import { tablePositions, type Position } from "@/domain/positions";
import type { ActionRecord, PlayerState, TableState } from "@/domain/table";
import { viewAfterAll, type TableView } from "@/playback/table-view";
import { heroPos, openerPos, parseContext, type ThreeBetAction, type ThreeBetContext, type ThreeBetSpotData } from "./threebet";

const ANTE = 1, SB = 0.5, BB = 1;
const r2 = (n: number) => Math.round(n * 100) / 100;
const SEATS = tablePositions(9);
const posted = (p: Position) => (p === "SB" ? SB : p === "BB" ? BB : 0);

export function threeBetTable(d: ThreeBetSpotData, ctx: string): TableState {
  const c = d.contexts[ctx]!;
  const hero = heroPos(d), opener = openerPos(d);
  const stacks = c.stacks.table ?? SEATS.map((p) => (p === hero ? c.stacks.hero : p === opener ? c.stacks.opener : null) ?? d.stack);
  const players: PlayerState[] = SEATS.map((position, seat) => ({
    // Stack do início da mão (antes de postar), como no resto do trainer.
    seat, position, name: position, stackChips: null, bounty: null, stackBb: r2(stacks[seat] ?? d.stack),
    isHero: position === hero, status: "active",
  }));
  const seatOf = (p: Position) => SEATS.indexOf(p);
  const act = (position: Position, type: ActionRecord["type"], amount = 0): ActionRecord => ({ seat: seatOf(position), position, type, amount, street: "preflop" });
  const actions: ActionRecord[] = [act("BB", "post_ante", ANTE), act("SB", "post_sb", SB), act("BB", "post_bb", BB)];
  let opened = false;
  for (const p of SEATS) {
    if (p === hero) break;
    if (p === opener) { actions.push(act(p, "raise", r2(c.open_bb - posted(p)))); opened = true; }
    else actions.push(act(p, "fold"));
  }
  if (!opened) throw new Error(`${d.spot}: o opener age depois do herói`);
  return {
    size: 9, format: parseContext(ctx).mode === "pko" ? "pko" : "regular",
    blinds: { sb: SB, bb: BB, ante: ANTE, anteType: "bb-ante", bbChips: null },
    players, heroSeat: seatOf(hero), actions, pot: SB + BB + ANTE,
  };
}

/** Total que o herói tem na frente depois da ação (bb, incluindo o blind já postado). */
export function heroTotalAfter(t: TableState, c: ThreeBetContext, a: ThreeBetAction): number {
  const hero = t.players[t.heroSeat]!;
  // Fichas que o herói pode pôr na frente (o ante do BB já foi para o pote).
  const cap = r2(hero.stackBb - (hero.position === "BB" ? ANTE : 0));
  if (a === "fold") return posted(hero.position);
  if (a === "call") return Math.min(c.open_bb, cap);
  if (a === "allin") return cap;
  return Math.min(c.sizes[a], cap);
}

/** Estado visual: vez do herói, ou depois da escolha (a ficha do herói na frente dele). */
export function threeBetView(t: TableState, c: ThreeBetContext, choice: ThreeBetAction | null): TableView {
  const v = viewAfterAll(t);
  const view: TableView = { ...v, bets: { ...v.bets }, lastAction: { ...v.lastAction }, folded: [...v.folded], actingSeat: t.heroSeat };
  if (!choice) return view;
  const hs = t.heroSeat;
  if (choice === "fold") { view.folded.push(hs); view.lastAction[hs] = "fold"; }
  else { view.bets[hs] = heroTotalAfter(t, c, choice); view.lastAction[hs] = choice === "call" ? "call" : choice === "allin" ? "all_in" : "raise"; }
  view.actingSeat = null;
  return view;
}

/** Mesa depois da escolha (só exibição: all-in marca o herói). */
export function threeBetTableAfter(t: TableState, choice: ThreeBetAction | null): TableState {
  if (choice !== "allin") return t;
  return { ...t, players: t.players.map((p) => (p.isHero ? { ...p, status: "all_in" } : p)) };
}
