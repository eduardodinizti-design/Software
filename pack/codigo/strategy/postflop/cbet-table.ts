/**
 * Mesa do drill de c-bet no mesmo formato da mesa pré-flop (TableState + TableView), só para exibir:
 * 8-max, stacks iguais ao spot, BB-ante (1bb). As posições saem do id do spot (`<herói>_vs_<defensor>_<stack>`,
 * ex.: co_vs_bb_40, sb_vs_bb_25, co_vs_btn_40): o herói abriu, todos foldaram até o defensor, que pagou.
 * Tamanho do open: `open_bb` do arquivo quando vier; senão sai do pote do solver:
 * open = (pote − ante − blinds de quem foldou) / 2 (co_vs_bb_40: 6,5 → 2,5bb; 25bb: 5,9 → 2,2bb).
 * No flop: agressor em posição → o defensor deu check e é a vez do herói; fora de posição → o herói age primeiro.
 */
import { tablePositions, type Position } from "@/domain/positions";
import type { ActionRecord, PlayerState, TableState } from "@/domain/table";
import type { TableView } from "@/playback/table-view";
import { betAmountBb, type CbetAction, type CbetFlop, type CbetSpotData } from "./cbet";

const ANTE = 1;
const SB = 0.5;
const r2 = (n: number) => Math.round(n * 100) / 100;
const POS: Record<string, Position> = { utg: "UTG", "utg1": "UTG+1", "utg+1": "UTG+1", "utg2": "UTG+2", "utg+2": "UTG+2", lj: "LJ", hj: "HJ", mp: "LJ", co: "CO", btn: "BTN", bu: "BTN", sb: "SB", bb: "BB" };
/** 8-max; 9-max quando o spot envolve o UTG (no 8-max do trainer a primeira posição é UTG+1). */
const seatsFor = (a: Position, b: Position): Position[] => tablePositions(a === "UTG" || b === "UTG" ? 9 : 8);
const ALL = tablePositions(9);
/** Ordem de ação pós-flop (SB primeiro, BTN por último). */
const POSTFLOP_ORDER: Position[] = ["SB", "BB", "UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN"];

export function cbetPositions(data: Pick<CbetSpotData, "spot">): { hero: Position; villain: Position } {
  const m = data.spot.toLowerCase().match(/^([a-z0-9+]+)_vs_([a-z0-9+]+)/);
  const hero = (m && POS[m[1]!]) || "BTN";
  const villain = (m && POS[m[2]!]) || "BB";
  return { hero: ALL.includes(hero) ? hero : "BTN", villain: ALL.includes(villain) && villain !== hero ? villain : "BB" };
}
export const cbetHeroPosition = (data: CbetSpotData): Position => cbetPositions(data).hero;
export const cbetVillainPosition = (data: CbetSpotData): Position => cbetPositions(data).villain;
/** O herói é o último a agir no flop (aposta depois do check do defensor)? */
export const cbetHeroInPosition = (data: CbetSpotData) => {
  const { hero, villain } = cbetPositions(data);
  return POSTFLOP_ORDER.indexOf(hero) > POSTFLOP_ORDER.indexOf(villain);
};
/** Blinds de quem não está na mão (dinheiro morto no pote). */
const deadBlinds = (hero: Position, villain: Position) => (hero !== "SB" && villain !== "SB" ? SB : 0) + (hero !== "BB" && villain !== "BB" ? 1 : 0);
export const cbetOpenSize = (data: CbetSpotData) => {
  if (typeof data.open_bb === "number" && data.open_bb > 0) return r2(data.open_bb);
  const { hero, villain } = cbetPositions(data);
  return r2((data.pot_bb - ANTE - deadBlinds(hero, villain)) / 2);
};
export const cbetStartStack = (data: CbetSpotData) => r2(data.stack_bb + cbetOpenSize(data));

export function cbetTable(data: CbetSpotData): TableState {
  const { hero: heroPos, villain } = cbetPositions(data);
  const open = cbetOpenSize(data);
  const start = cbetStartStack(data);
  const SEATS = seatsFor(heroPos, villain);
  const players: PlayerState[] = SEATS.map((position, seat) => {
    const inHand = position === heroPos || position === villain;
    return { seat, position, name: position, stackChips: null, bounty: null, stackBb: inHand ? data.stack_bb : start, isHero: position === heroPos, status: inHand ? "active" : "folded" };
  });
  const seatOf = (p: Position) => SEATS.indexOf(p);
  const posted: Partial<Record<Position, number>> = { SB, BB: 1 };
  const act = (position: Position, type: ActionRecord["type"], amount = 0): ActionRecord => ({ seat: seatOf(position), position, type, amount, street: "preflop" });
  const actions: ActionRecord[] = [act("BB", "post_ante", ANTE), act("SB", "post_sb", SB), act("BB", "post_bb", 1)];
  let opened = false;
  for (const p of SEATS) {
    if (p === heroPos) { actions.push(act(p, "raise", r2(open - (posted[p] ?? 0)))); opened = true; }
    else if (p === villain && opened) actions.push(act(p, "call", r2(open - (posted[p] ?? 0))));
    else if (opened || p !== villain) actions.push(act(p, "fold"));
  }
  return { size: SEATS.length as 8 | 9, format: "regular", blinds: { sb: SB, bb: 1, ante: ANTE, anteType: "bb-ante", bbChips: null }, players, heroSeat: seatOf(heroPos), actions, pot: data.pot_bb };
}

/** Estado visual no flop: antes da resposta (vez do herói; em posição, o defensor já deu check) ou depois. */
export function cbetView(data: CbetSpotData, table: TableState, _flop: CbetFlop, choice: CbetAction | null): TableView {
  const v = table.players.find((p) => p.position === cbetVillainPosition(data))!.seat;
  const ip = cbetHeroInPosition(data);
  const folded = table.players.filter((p) => p.status === "folded").map((p) => p.seat);
  const view: TableView = { dealt: true, bets: {}, pot: data.pot_bb, folded, lastAction: ip ? { [v]: "check" } : {}, actingSeat: table.heroSeat };
  if (choice && choice !== "check") { view.bets = { [table.heroSeat]: betAmountBb(data, choice) }; view.lastAction[table.heroSeat] = "bet"; view.actingSeat = v; }
  if (choice === "check") { view.lastAction[table.heroSeat] = "check"; view.actingSeat = ip ? null : v; }
  return view;
}

/** Stacks depois da aposta (só exibição). */
export function cbetTableAfter(table: TableState, data: CbetSpotData, _flop: CbetFlop, choice: CbetAction | null): TableState {
  if (!choice || choice === "check") return table;
  const amt = betAmountBb(data, choice);
  return { ...table, players: table.players.map((p) => (p.isHero ? { ...p, stackBb: r2(p.stackBb - amt) } : p)) };
}
