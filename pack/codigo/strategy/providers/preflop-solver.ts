/**
 * Fonte "solver pré-flop" (motor do time, branch solver-data): vs open, vs 3bet e open raise com ICM/PKO,
 * quando existe uma situação do catálogo carregada para o contexto (ver `preflop-solver/catalog.ts`).
 * Sem situação carregada, devolve null e o spot fica com a fonte anterior (referência aproximada / ICM calibrado).
 *
 * Frequências abaixo de MIN_FREQ são descartadas (ruído do equilíbrio) e o resto é renormalizado: assim
 * "call 0,06%" não vira mix válido. EV de cada ação relativo ao fold, na unidade do catálogo (bb ou % do prize pool).
 */
import { ALL_HANDS, combos, type HandKey } from "@/domain/cards";
import type { DecisionAction, TrainingScenario } from "@/domain/scenario";
import { describeBountyPower, relevantBountyPower } from "@/domain/pko";
import { at, describePreset, isHrcPreset, limpPresetFor, MIN_LIMP_FREQ, presetFor, toRecord, type LimpAct, type PreflopPreset } from "../preflop-solver/catalog";
import { rangeId, type RangeDefinition } from "../ranges/types";
import { nvtOpenRange } from "../ranges/nvt-charts";
import { rangePercent } from "../ranges/stats";
import type { ActionFrequency, StrategyDecision, StrategyProvider, StrategySourceInfo, VillainRead } from "../types";
import { profileLabel } from "@/domain/villain";
import { EV_MIX_TOL_BB, EV_MIX_TOL_PCT } from "../tolerances";
import { REF_3BET, threeBetPct, threeBettor, vs3betModel, type Vs3betModel } from "../exploit/vs3bet";

export const MIN_FREQ = 0.05;
export const PREFLOP_SOLVER_SOURCE: StrategySourceInfo = { id: "solver", label: "Solver pré-flop NVT", version: "catalog" };

const PT: Partial<Record<DecisionAction, string>> = { fold: "Fold", call: "Call", three_bet: "3Bet", raise: "Raise", all_in: "All-in", four_bet: "4Bet", limp: "Limp", check: "Check" };
const num = (v: number, d = 2) => `${v < 0 ? "−" : v > 0 ? "+" : ""}${Math.abs(v).toFixed(d).replace(".", ",")}`;
const pct = (v: number) => `${(v * 100).toFixed(v >= 0.995 || v < 0.005 ? 0 : 1).replace(".", ",")}%`;

/** Mix da mão: ações legais, ruído descartado, renormalizado. */
function cleanMix(raw: Partial<Record<DecisionAction, number>>, legal: DecisionAction[]): ActionFrequency[] {
  const kept = legal.map((a) => ({ action: a, frequency: raw[a] ?? 0 })).filter((x) => x.frequency >= MIN_FREQ);
  const tot = kept.reduce((s, x) => s + x.frequency, 0);
  if (!kept.length || tot <= 0) {
    const best = legal.map((a) => ({ action: a, frequency: raw[a] ?? 0 })).sort((a, b) => b.frequency - a.frequency)[0]!;
    return [{ action: best.action, frequency: 1 }];
  }
  return kept.map((x) => ({ action: x.action, frequency: x.frequency / tot })).sort((a, b) => b.frequency - a.frequency);
}

/**
 * A mão está no range de open (de 2bb) do herói? Pela frequência do HRC (≥ 5%) ou pelo EV: quando abrir rende o
 * mesmo que foldar (dentro da margem do mix aceito), o HRC escolhe qualquer um dos dois e a frequência sai arbitrária (ex.: UTG
 * pré-ITM 25bb abre 88 95% e 99 0,1%, todos com EV ~0). Nesses casos a mão conta como aberta.
 */
export function opensHand(p: PreflopPreset, pos: string, h: HandKey): boolean {
  const n = p.rfi[pos]; if (!n) return false;
  if (at(p, n.raise, h) >= MIN_FREQ) return true;
  return !!n.ev && at(p, n.ev.raise, h) - at(p, n.ev.fold, h) >= -tieTolOf(p);
}
/**
 * Empate de EV: quando duas ações rendem o mesmo (dentro da margem) mas o mix do HRC ficou num lado só, as ações
 * empatadas entram em partes iguais. É um mix de verdade (as duas são certas) e evita incoerências como 88 raise e
 * 99 fold na mesma fronteira.
 */
function tieMix(mix: ActionFrequency[], evMap: Partial<Record<DecisionAction, number>>, legal: DecisionAction[], tol: number): { mix: ActionFrequency[]; tie: DecisionAction[] | null } {
  const acts = legal.filter((a) => evMap[a] !== undefined && Number.isFinite(evMap[a]!));
  if (acts.length < 2) return { mix, tie: null };
  const best = Math.max(...acts.map((a) => evMap[a]!));
  const near = acts.filter((a) => evMap[a]! >= best - tol).sort((a, b) => evMap[b]! - evMap[a]!);
  if (near.length < 2 || near.every((a) => mix.some((m) => m.action === a))) return { mix, tie: null };
  return { mix: near.map((a) => ({ action: a, frequency: 1 / near.length })), tie: near };
}
const tieTxt = (tie: DecisionAction[] | null, p: PreflopPreset) => (tie ? ` Empate de EV: ${tie.map((a) => PT[a] ?? a).join(" e ")} rendem o mesmo (diferença menor que ${p.unit === "pct" ? "0,02% do prize pool" : "0,05bb"}, a margem da régua); as duas são aceitas.` : "");
/** Empate = mesma margem da correção (mix aceito): o que aparece como empate nunca é cobrado como erro. */
const tieTolOf = (p: PreflopPreset) => (p.unit === "pct" ? EV_MIX_TOL_PCT : EV_MIX_TOL_BB);

/** Frequência agregada de um nó sobre um range de entrada (pesos por combo). */
function aggregate(p: PreflopPreset, prior: number[] | null, nodes: Record<string, number[]>): Record<string, number> {
  const out: Record<string, number> = {}; let den = 0;
  ALL_HANDS.forEach((h, i) => { const w = combos(h) * (prior ? prior[p.idx[i]!] ?? 0 : 1); den += w; for (const [k, a] of Object.entries(nodes)) out[k] = (out[k] ?? 0) + w * (a[p.idx[i]!] ?? 0); });
  for (const k of Object.keys(out)) out[k] = den > 0 ? out[k]! / den : 0;
  return out;
}

function build(s: TrainingScenario, p: PreflopPreset, mix: ActionFrequency[], cont: Record<HandKey, number>, action: RangeDefinition["action"], evs: { action: DecisionAction; ev: number }[] | null, text: string, tag: string): StrategyDecision {
  const [top, ...rest] = mix as [ActionFrequency, ...ActionFrequency[]];
  const range: RangeDefinition = { id: `${rangeId(s.spot.type, s.context, s.spot.heroPosition)}|solver-${p.name}${s.spot.aggressors[0] ? `|vs-${s.spot.aggressors[0]}` : ""}`, spot: s.spot.type, action, position: s.spot.heroPosition, context: s.context, hands: cont, source: "solver", version: p.version, notes: `Solver pré-flop NVT · ${describePreset(p.name)}` };
  const source: StrategySourceInfo = { ...PREFLOP_SOLVER_SOURCE, label: isHrcPreset(p.name) ? `HRC (${describePreset(p.name).replace(/^ranges do HRC, /, "")})` : `Solver pré-flop NVT (${describePreset(p.name)})`, version: p.version };
  return {
    recommended: top.action, frequency: top.frequency, alternatives: rest, explanation: text, range, source,
    theoryTags: ["solver", tag, ...(s.context.mode === "icm" || s.context.mode === "pko_icm" ? ["icm"] : []), ...(s.context.mode === "pko" || s.context.mode === "pko_icm" ? ["pko"] : [])],
    ...(evs ? { actionEvs: evs, evUnit: p.unit } : {}),
  };
}

const unitTxt = (p: PreflopPreset) => (p.unit === "pct" ? "% do prize pool" : "bb");
const mixTxt = (m: ActionFrequency[]) => m.map((x) => `${PT[x.action] ?? x.action} ${pct(x.frequency)}`).join(" / ");
const footer = (p: PreflopPreset, s: TrainingScenario) => `${isHrcPreset(p.name) ? " Ranges do HRC (solver de referência, árvore completa com modelo de pós-flop), conferidos e importados para o trainer." : " Solver pré-flop NVT (motor do time, árvore completa com pós-flop por realização medida nos solves de flop)."} Situação de referência: mesa de 9, ${describePreset(p.name)}, open de 2bb. Sua mesa: ${s.table.size}-max, ${s.context.stack}bb.${pkoLine(p, s)}`;
/** PKO chip EV: BP de quem pesa na decisão e a situação do solver escolhida por ele. */
function pkoLine(p: PreflopPreset, s: TrainingScenario): string {
  if (!p.name.startsWith("pko")) return "";
  // Ranges do HRC para o PKO de começo/meio: uma situação por fase (cabeça média do torneio de referência).
  if (isHrcPreset(p.name)) return "";
  const bp = relevantBountyPower(s);
  if (bp === null) return "";
  const who = s.spot.aggressors[0] ? `do ${s.spot.aggressors[0]}` : "médio de quem fala depois de você";
  return ` Bounty power ${who}: ${describeBountyPower(bp)} quando você cobre; o solver tem as situações com BP ≈ 1,1 e ≈ 2,4 e usa a mais próxima.`;
}

function vsOpen(s: TrainingScenario, p: PreflopPreset): StrategyDecision | null {
  const agg = s.spot.aggressors[0]; if (!agg) return null;
  const node = p.resp[`${agg}>${s.spot.heroPosition}`]; if (!node) return null;
  const h = s.hero.hand;
  const raw = { call: at(p, node.call, h), three_bet: at(p, node.three, h), all_in: at(p, node.shove, h) };
  const mix0 = cleanMix({ ...raw, fold: Math.max(0, 1 - raw.call - raw.three_bet - raw.all_in) }, s.legalActions);
  const evF = at(p, node.ev.fold, h);
  const evMap: Partial<Record<DecisionAction, number>> = { fold: 0, call: at(p, node.ev.call, h) - evF, three_bet: at(p, node.ev.three, h) - evF, all_in: at(p, node.ev.shove, h) - evF };
  const { mix, tie } = tieMix(mix0, evMap, s.legalActions, tieTolOf(p));
  const evs = s.legalActions.filter((a) => evMap[a] !== undefined).map((a) => ({ action: a, ev: evMap[a]! }));
  const cont = toRecord(p, node.call.map((c, i) => c + node.three[i]! + node.shove[i]!));
  const R = node.resumo;
  const f1 = (v: number | undefined) => `${(v ?? 0).toFixed(1).replace(".", ",")}%`;
  const all = R ? `Range todo do ${s.spot.heroPosition} contra o open do ${agg}: fold ${f1(R["fold"])} · call ${f1(R["call"])} · 3bet ${f1(R["three"])} · all-in ${f1(R["shove"])}.` : "";
  const evTxt = evs.filter((e) => e.action !== "fold").map((e) => `${PT[e.action]} ${num(e.ev, p.unit === "pct" ? 3 : 2)}`).join(" · ");
  const text = `${h}: ${mixTxt(mix)}.${tieTxt(tie, p)} ${all} EV contra o fold (${unitTxt(p)}): ${evTxt}.${footer(p, s)}`;
  return build(s, p, mix, cont, "call", evs, text, "vs_open");
}

function vs3bet(s: TrainingScenario, p: PreflopPreset): StrategyDecision | null {
  const agg = s.spot.aggressors[0]; if (!agg) return null;
  const node = p.opv3[`${s.spot.heroPosition}>${agg}`]; const rfi = p.rfi[s.spot.heroPosition];
  if (!node || !rfi) return null;
  const h = s.hero.hand;
  // O motor só define a resposta para mãos que ele abriria; fora disso a fonte anterior responde.
  if (!opensHand(p, s.spot.heroPosition, h)) return null;
  const raw: Partial<Record<DecisionAction, number>> = { call: at(p, node.call, h), all_in: at(p, node.shove, h) };
  raw.fold = Math.max(0, 1 - raw.call! - raw.all_in!);
  // EV do HRC (contra o fold). Mesma régua do Blind War: se a frequência contradiz o EV que o próprio HRC calculou
  // por mais que a margem (0,05bb / 0,02% do prize pool), vale a ação de maior EV.
  let evs: { action: DecisionAction; ev: number }[] | null = null, evTxt = "", evNote = "", mix = cleanMix(raw, s.legalActions);
  if (node.ev) {
    const evF = at(p, node.ev.fold, h);
    const evMap: Partial<Record<DecisionAction, number>> = { fold: 0, call: at(p, node.ev.call, h) - evF, all_in: at(p, node.ev.shove, h) - evF };
    const legal = s.legalActions.filter((x) => evMap[x] !== undefined);
    evs = legal.map((x) => ({ action: x, ev: evMap[x]! }));
    const main = legal.reduce((x, y) => ((raw[y] ?? 0) > (raw[x] ?? 0) ? y : x));
    const best = legal.reduce((x, y) => (evMap[y]! > evMap[x]! ? y : x));
    const tol = p.unit === "pct" ? 0.02 : 0.05;
    const t = tieMix(mix, evMap, legal, tieTolOf(p));
    if (t.tie) { mix = t.mix; evNote = tieTxt(t.tie, p); }
    if (evMap[best]! - evMap[main]! > tol) {
      mix = [{ action: best, frequency: 1 }];
      evNote = ` O HRC joga ${PT[main]} ${pct(raw[main] ?? 0)} aqui, mas pelo EV que ele mesmo calculou ${PT[best]} rende ${num(evMap[best]! - evMap[main]!, p.unit === "pct" ? 3 : 2)} ${unitTxt(p)} a mais: vale a ação de maior EV (frequência não convergiu).`;
    }
    evTxt = ` EV contra o fold (${unitTxt(p)}): ${evs.filter((e) => e.action !== "fold").map((e) => `${PT[e.action]} ${num(e.ev, p.unit === "pct" ? 3 : 2)}`).join(" · ")}.`;
  }
  const cont = toRecord(p, node.call.map((c, i) => (c + node.shove[i]!) * (opensHand(p, s.spot.heroPosition, p.hands[i]!) ? 1 : 0)));
  const a = aggregate(p, rfi.raise, { call: node.call, shove: node.shove }); const aC = a["call"] ?? 0, aS = a["shove"] ?? 0;
  // Exploit: o "3-Bet" do vilão muda o range dele; a melhor resposta contra esse range só informa (ver exploit/vs3bet.ts):
  // a nota segue o equilíbrio, porque o EV contra o vilão é uma estimativa a partir dos stats.
  const ex = s.exploit && evs ? vs3betExploit(s, p, rfi.raise, mix, evs) : null;
  const text = `${h}: ${mixTxt(mix)}.${evNote}${ex ? ex.text : ""} Seu range de open contra a 3bet do ${agg}: call ${pct(aC)} · all-in ${pct(aS)} · fold ${pct(Math.max(0, 1 - aC - aS))} (equilíbrio).${evTxt}${footer(p, s)}`;
  const d = build(s, p, mix, cont, "call", evs, text, "vs_3bet");
  return ex ? { ...d, villainRead: ex.read } : d;
}

const LABEL: Partial<Record<DecisionAction, string>> = { call: "Call", all_in: "All-in", fold: "Fold" };
const RANKS = "AKQJT98765432";
/** Mãos da mesma família da mão do herói (mesma carta alta e mesmo naipe/offsuit), do kicker maior ao menor. */
function family(h: HandKey): HandKey[] {
  if (h.length === 2) return [...RANKS].map((r) => `${r}${r}` as HandKey);
  const hi = h[0]!, suf = h[2]!;
  return [...RANKS.slice(RANKS.indexOf(hi) + 1)].map((k) => `${hi}${k}${suf}` as HandKey);
}
/** "KQs–K9s, K5s": trechos seguidos da família. */
function runs(fam: HandKey[], ok: (h: HandKey) => boolean): string {
  const out: string[] = []; let start: HandKey | null = null, prev: HandKey | null = null;
  for (const h of [...fam, null]) {
    if (h && ok(h)) { start ??= h; prev = h; continue; }
    if (start) out.push(start === prev ? start : `${start}–${prev}`);
    start = null;
  }
  return out.join(", ") || "nenhuma";
}
function bestOf(m: Vs3betModel, i: number, gto = false): { action: DecisionAction; ev: number } {
  const c = gto ? m.gtoEvCall[i]! : m.evCall[i]!, ai = gto ? m.gtoEvAllIn[i]! : m.evAllIn[i]!;
  return [{ action: "fold" as DecisionAction, ev: 0 }, { action: "call" as DecisionAction, ev: c }, { action: "all_in" as DecisionAction, ev: ai }].reduce((x, y) => (y.ev > x.ev ? y : x));
}

function vs3betExploit(s: TrainingScenario, p: PreflopPreset, open: number[], gtoMix: ActionFrequency[], gtoEvs: { action: DecisionAction; ev: number }[]) {
  const v = threeBettor(s); if (!v) return null;
  const m = vs3betModel(p, s, v); if (!m) return null;
  const i = ALL_HANDS.indexOf(s.hero.hand);
  const legal = s.legalActions.filter((x) => x === "fold" || x === "call" || x === "all_in");
  const evMap: Partial<Record<DecisionAction, number>> = { fold: 0, call: m.evCall[i]!, all_in: m.evAllIn[i]! };
  const evs = legal.map((x) => ({ action: x, ev: evMap[x]! }));
  const best = evs.reduce((x, y) => (y.ev > x.ev ? y : x));
  const gtoBest = gtoEvs.reduce((x, y) => (y.ev > x.ev ? y : x));
  const agg = s.spot.aggressors[0]!;
  // Unidade do HRC: bb (chip EV) ou % do prize pool (ICM, 3 casas como no resto do app).
  const pctU = m.unit === "pct";
  const fmt = (x: number) => `${num(x, pctU ? 3 : 2)}${pctU ? "%" : "bb"}`;
  // Tabela "a partir de qual mão" contra cada perfil (stat do meio da faixa de cada um).
  void open;
  const opened = (h: HandKey) => opensHand(p, s.spot.heroPosition, h);
  const fam = family(s.hero.hand).filter(opened);
  const profiles = [{ label: "Tight", stat: 4 }, { label: "Regular", stat: 8 }, { label: "Agressivo", stat: 12 }, { label: "Maníaco", stat: 18 }];
  const profileTable = profiles.map((pr) => {
    const mm = vs3betModel(p, s, { ...v, stats: { ...v.stats, threeBet: pr.stat } });
    if (!mm) return { label: pr.label, stat: pr.stat, call: "—", allIn: "—", hero: "—" };
    const b = (h: HandKey) => bestOf(mm, ALL_HANDS.indexOf(h));
    const hb = b(s.hero.hand);
    return { label: pr.label, stat: pr.stat, call: runs(fam, (h) => b(h).action === "call"), allIn: runs(fam, (h) => b(h).action === "all_in"), hero: `${LABEL[hb.action]} ${fmt(hb.ev)}` };
  });
  const changed = best.action !== gtoBest.action;
  const read: VillainRead = {
    lines: [{ seat: v.seat, position: agg, name: v.name, profile: profileLabel(v.profile), stat: "3-Bet", value: v.stats.threeBet, ref: REF_3BET, verb: "dá 3bet com", gtoPct: threeBetPct(m.gtoThree), exploitPct: threeBetPct(m.three) }],
    gto: { frequency: gtoMix[0]!.action === "fold" ? 0 : 1, ev: gtoBest.ev },
    exploit: { frequency: best.action === "fold" ? 0 : 1, ev: best.ev },
    action: best.action === "fold" ? gtoBest.action : best.action,
    labels: { gto: `${LABEL[gtoBest.action]} · ${fmt(gtoBest.ev)}`, exploit: `${LABEL[best.action]} · ${fmt(best.ev)}` },
    options: legal.filter((x) => x !== "fold").map((x) => ({ action: x, label: LABEL[x]!, gto: gtoEvs.find((e) => e.action === x)?.ev ?? 0, exploit: evMap[x]! })),
    villainRange: { title: `Range de 3bet do ${agg}`, gto: Array.from(m.gtoThree), exploit: Array.from(m.three) },
    profileTable,
    note: "Range do vilão: o 3-Bet dele muda o tamanho do range de 3bet do equilíbrio (8% = Regular médio), com as mãos mais fortes primeiro. All-in: ele paga com o que tem equity contra o seu range de continuação. Call: a realização de equity do HRC aplicada ao range novo. EV = HRC + a diferença que o vilão causa (estimativa)." + (pctU ? " Com ICM, cada resultado (fold, all-in ganho ou perdido, call) vale pelo ICM do stack final, então o risk premium entra na conta dos dois: você precisa de mais equity para ir all-in, e ele também para pagar." : ""),
  };
  const text = ` Contra ${v.name} (${profileLabel(v.profile)}, 3-Bet ${v.stats.threeBet}%), que dá 3bet com ~${threeBetPct(m.three).toFixed(1).replace(".", ",")}% das mãos aqui (equilíbrio ${threeBetPct(m.gtoThree).toFixed(1).replace(".", ",")}%): ${evs.filter((e) => e.action !== "fold").map((e) => `${LABEL[e.action]} ${fmt(e.ev)}`).join(" · ")} (estimativa${pctU ? ", com ICM: cada resultado vale pelo ICM do stack final" : ""}). ${changed ? `No equilíbrio seria ${LABEL[gtoBest.action]} (${fmt(gtoBest.ev)}): contra este vilão o modelo muda a decisão (estimativa pelos stats; a resposta cobrada é a do equilíbrio).` : `No equilíbrio também seria ${LABEL[gtoBest.action]} (${fmt(gtoBest.ev)}).`}`;
  return { mix: [{ action: best.action, frequency: 1 }] as ActionFrequency[], evs, read, text };
}

function openRaise(s: TrainingScenario, p: PreflopPreset): StrategyDecision | null {
  const node = p.rfi[s.spot.heroPosition]; if (!node) return null;
  const h = s.hero.hand;
  const raw = { raise: at(p, node.raise, h), all_in: at(p, node.shove, h) };
  const evF = at(p, node.ev.fold, h);
  const evMap: Partial<Record<DecisionAction, number>> = { fold: 0, raise: at(p, node.ev.raise, h) - evF, all_in: at(p, node.ev.shove, h) - evF };
  const evs = s.legalActions.filter((x) => evMap[x] !== undefined).map((x) => ({ action: x, ev: evMap[x]! }));
  // Na SB o motor também limpa (Blind War), mas o open raise do trainer não tem limp: a fatia que o motor limpa
  // não é fold. Quando raise ou all-in rende mais que o fold, essa fatia vai para a melhor ação legal pelo EV.
  const tol = tieTolOf(p);
  const bestCont = evs.filter((e) => e.action !== "fold").sort((a, b) => b.ev - a.ev)[0];
  const rest = Math.max(0, 1 - raw.raise - raw.all_in);
  const limpHand = s.spot.heroPosition === "SB" && rest >= MIN_FREQ && !!bestCont && bestCont.ev > tol;
  const freq: Partial<Record<DecisionAction, number>> = { ...raw, fold: limpHand ? 0 : rest };
  if (limpHand) freq[bestCont!.action] = (freq[bestCont!.action] ?? 0) + rest;
  const { mix, tie } = tieMix(cleanMix(freq, s.legalActions), evMap, s.legalActions, tieTolOf(p));
  const cont = toRecord(p, node.raise.map((r, i) => r + node.shove[i]!));
  const evTxt = evs.filter((e) => e.action !== "fold").map((e) => `${PT[e.action]} ${num(e.ev, p.unit === "pct" ? 3 : 2)}`).join(" · ");
  const limpTxt = limpHand ? ` O motor limpa ${pct(rest)} desta mão na Blind War; sem limp entre as opções, a melhor ação aqui é ${PT[bestCont!.action]} (rende mais que o fold).` : "";
  const text = `${h}: ${mixTxt(mix)}.${tieTxt(tie, p)}${limpTxt} Open do ${s.spot.heroPosition}: raise ${rangePercent(toRecord(p, node.raise)).toFixed(1).replace(".", ",")}% + all-in ${rangePercent(toRecord(p, node.shove)).toFixed(1).replace(".", ",")}% das mãos. EV contra o fold (${unitTxt(p)}): ${evTxt}.${footer(p, s)}`;
  return build(s, p, mix, cont, "raise", evs, text, "open_raise");
}

/**
 * Blind War com limp pelos ranges do HRC. Nó a nó vale a frequência do HRC; quando ela contradiz o EV que o próprio
 * HRC calculou por mais que a margem da régua (0,05bb / 0,02% do prize pool), vale a ação de maior EV do HRC
 * (mesma leitura das referências de validação: nós com pouco alcance, como o SB vs iso com 15bb, não convergem na
 * frequência mas convergem no EV).
 */
function limpNode(s: TrainingScenario, p: PreflopPreset, node: Record<string, LimpAct>, keyOf: Partial<Record<DecisionAction, string>>, base: DecisionAction = "fold") {
  const h = s.hero.hand;
  const legal = s.legalActions.filter((a) => keyOf[a] && node[keyOf[a]!]);
  const baseKey = keyOf[base]!;
  const evF = node[baseKey] ? at(p, node[baseKey].ev, h) : 0;
  const raw: Partial<Record<DecisionAction, number>> = {}; const evMap: Partial<Record<DecisionAction, number>> = {};
  for (const a of legal) { raw[a] = at(p, node[keyOf[a]!]!.freq, h); evMap[a] = at(p, node[keyOf[a]!]!.ev, h) - evF; }
  const evs = legal.map((a) => ({ action: a, ev: evMap[a]! }));
  const main = legal.reduce((x, y) => ((raw[y] ?? 0) > (raw[x] ?? 0) ? y : x));
  const best = legal.reduce((x, y) => (evMap[y]! > evMap[x]! ? y : x));
  const tol = p.unit === "pct" ? 0.02 : 0.05;
  const byEv = evMap[best]! - evMap[main]! > tol;
  const mix0 = byEv ? [{ action: best, frequency: 1 }] : cleanMix(raw, legal);
  // Empate de EV (dentro da margem da correção): mostra as ações empatadas como mix, nunca "100%" de uma delas. Na Blind
  // com ICM quase todo o range da SB fica com as três ações a menos de 0,01% do prize pool (o HRC escolhe uma por ruído).
  const { mix, tie } = tieMix(mix0, evMap, legal, tieTolOf(p));
  const evTxt = evs.filter((e) => e.action !== base).map((e) => `${PT[e.action]} ${num(e.ev, p.unit === "pct" ? 3 : 2)}`).join(" · ");
  const evNote = tie ? tieTxt(tie, p) : byEv ? ` O HRC joga ${PT[main]} ${pct(raw[main] ?? 0)} aqui, mas pelo EV que ele mesmo calculou ${PT[best]} rende ${num(evMap[best]! - evMap[main]!, p.unit === "pct" ? 3 : 2)} ${unitTxt(p)} a mais: vale a ação de maior EV (frequência não convergiu).` : "";
  return { mix, evs, evTxt, evNote };
}

const sz = (v: number | null | undefined) => (v ?? 0).toFixed(1).replace(".0", "").replace(".", ",");

function limpFirst(s: TrainingScenario, p: PreflopPreset): StrategyDecision | null {
  const L = p.limp!; const h = s.hero.hand;
  const { mix, evs, evTxt, evNote } = limpNode(s, p, L.sb, { fold: "fold", limp: "call", raise: "raise", all_in: "allin" });
  const r = (k: string) => (L.sb[k] ? rangePercent(toRecord(p, L.sb[k]!.freq)) : 0).toFixed(1).replace(".", ",");
  const cont = toRecord(p, L.sb["raise"]!.freq.map((x, i) => x + (L.sb["allin"]?.freq[i] ?? 0)));
  const text = `${h}: ${mixTxt(mix)}.${evNote} A SB na Blind War (todos foldaram): fold ${r("fold")}% · limp ${r("call")}% · raise ${sz(L.raiseSize)}bb ${r("raise")}% · all-in ${r("allin")}%. EV contra o fold (${unitTxt(p)}): ${evTxt}. Se você limpar, o BB dá iso para ${sz(L.isoSize)}bb ou vai all-in com parte do range.${footer(p, s)}`;
  return { ...build(s, p, mix, cont, "raise", evs, text, "blind_war"), theoryTags: ["solver", "blind_war", "limp", ...(p.unit === "pct" ? ["icm"] : [])] };
}

function limpCall(s: TrainingScenario, p: PreflopPreset): StrategyDecision | null {
  const L = p.limp!; const node = L.sbVsIso; const h = s.hero.hand;
  if (!node?.["call"] || at(p, L.sb["call"]!.freq, h) < MIN_LIMP_FREQ) return null; // mão que o HRC não limpa: nunca chega aqui
  const { mix, evs, evTxt, evNote } = limpNode(s, p, node, { fold: "fold", call: "call", all_in: "allin" });
  const limpF = L.sb["call"]!.freq;
  const a = aggregate(p, limpF, { call: node["call"]!.freq, allin: node["allin"]!.freq });
  const aC = a["call"] ?? 0, aS = a["allin"] ?? 0;
  const cont = toRecord(p, node["call"]!.freq.map((c, i) => (c + node["allin"]!.freq[i]!) * (limpF[i]! >= MIN_LIMP_FREQ ? 1 : 0)));
  const text = `${h}: ${mixTxt(mix)} contra o iso do BB para ${sz(L.isoSize)}bb.${evNote} Range de limp da SB contra o iso: call ${pct(aC)} · all-in ${pct(aS)} · fold ${pct(Math.max(0, 1 - aC - aS))}. EV contra o fold (${unitTxt(p)}): ${evTxt}.${footer(p, s)}`;
  return { ...build(s, p, mix, cont, "call", evs, text, "blind_war"), theoryTags: ["solver", "blind_war", "limp", ...(p.unit === "pct" ? ["icm"] : [])] };
}

function vsLimp(s: TrainingScenario, p: PreflopPreset): StrategyDecision | null {
  const L = p.limp!; const node = L.bbVsLimp; const h = s.hero.hand;
  if (!node["check"] || !node["raise"]) return null;
  const { mix, evs, evTxt, evNote } = limpNode(s, p, node, { check: "check", raise: "raise", all_in: "allin" }, "check");
  const r = (k: string) => (node[k] ? rangePercent(toRecord(p, node[k]!.freq)) : 0).toFixed(1).replace(".", ",");
  const cont = toRecord(p, node["raise"]!.freq.map((x, i) => x + (node["allin"]?.freq[i] ?? 0)));
  const text = `${h}: ${mixTxt(mix)} contra o limp da SB.${evNote} O BB contra o limp: check ${r("check")}% · iso para ${sz(L.isoSize)}bb ${r("raise")}% · all-in ${r("allin")}% das mãos. EV contra o check (${unitTxt(p)}): ${evTxt}. Contra o iso, a SB paga, vai all-in ou folda.${footer(p, s)}`;
  return { ...build(s, p, mix, cont, "raise", evs, text, "blind_war"), theoryTags: ["solver", "blind_war", "limp", ...(p.unit === "pct" ? ["icm"] : [])] };
}

export const preflopSolverProvider: StrategyProvider = {
  source: PREFLOP_SOLVER_SOURCE,
  supports: (spot) => spot === "vs_open" || spot === "vs_3bet" || spot === "open_raise" || spot === "open_shove" || spot === "limp" || spot === "limp_call" || spot === "vs_limp",
  decide(s) {
    // Open (raise ou shove) da SB com o limp entre as opções: a Blind War do HRC responde inteira (fold/limp/raise/all-in).
    if ((s.spot.type === "open_raise" || s.spot.type === "open_shove") && s.spot.heroPosition === "SB" && s.legalActions.includes("limp")) {
      const p = limpPresetFor(s);
      return p ? limpFirst(s, p) : null;
    }
    if (s.spot.type === "open_shove") return null;
    if (s.spot.type === "vs_limp") {
      // BB contra o limp da SB: só existe nos ranges do HRC (sem a situação, o spot não tem fonte).
      const p = limpPresetFor(s);
      return p && s.spot.heroPosition === "BB" ? vsLimp(s, p) : null;
    }
    if (s.spot.type === "limp" || s.spot.type === "limp_call") {
      // Blind War com limp: ranges do HRC (tabela síncrona, ver hrc-limp.ts); sem a situação no HRC, a tabela NVT da SB responde.
      const p = limpPresetFor(s);
      if (!p || s.spot.heroPosition !== "SB") return null;
      return s.spot.type === "limp" ? limpFirst(s, p) : limpCall(s, p);
    }
    // Open raise em chip EV continua com as tabelas do time (referência escolhida pelo time); o solver só
    // entra onde não há tabela (ex.: open da SB), no lugar do range de referência genérico. No PKO o open muda
    // com o bounty power da mesa: usa a situação PKO do solver.
    const p = presetFor(s);
    // Com ranges do HRC (referência) para a situação, eles valem também no open (no lugar da tabela do time).
    if (s.spot.type === "open_raise" && !(p && isHrcPreset(p.name)) && s.context.format !== "pko" && (s.context.mode ?? "chip_ev") === "chip_ev" && nvtOpenRange(s.context, s.spot.heroPosition)) return null;
    if (!p) return null;
    return s.spot.type === "vs_open" ? vsOpen(s, p) : s.spot.type === "vs_3bet" ? vs3bet(s, p) : openRaise(s, p);
  },
};

// ---- Fonte crua do HRC (estudo e conferência) ----
export interface HrcSourceAction { action: DecisionAction; label: string; freq: number[]; ev: number[] | null }
export interface HrcSourceView {
  preset: string; file: string; version: string; note: string; unit: "bb" | "pct"; stacks: number[];
  /** Descrição do nó ("BTN responde ao open de 2bb do CO"). */
  node: string;
  /** Ações do nó com frequência e EV (relativo ao fold, ou ao check no BB vs limp) por mão, na ordem ALL_HANDS. */
  actions: HrcSourceAction[];
  /** Base do EV ("fold" ou "check"). */
  evBase: DecisionAction;
  /** % de mãos por ação no nó, como o HRC resume (quando o arquivo traz). */
  resumo: Partial<Record<DecisionAction, number>> | null;
}
const arr = (p: PreflopPreset, a: number[]) => ALL_HANDS.map((_, i) => a[p.idx[i]!] ?? 0);
const minus = (a: number[], b: number[]) => a.map((x, i) => x - (b[i] ?? 0));

/**
 * O nó do HRC que responde a este cenário, cru: frequências exatamente como o HRC exportou (sem o descarte de
 * mixes < 5% nem a troca pela ação de maior EV que o trainer aplica). Null quando a fonte do spot não é o HRC.
 */
export function hrcSourceView(s: TrainingScenario): HrcSourceView | null {
  const t = s.spot.type;
  const limpSpot = t === "limp" || t === "limp_call" || t === "vs_limp";
  const p = limpSpot ? limpPresetFor(s) : presetFor(s);
  if (!p || !isHrcPreset(p.name)) return null;
  const base = { preset: p.name, file: `/solver/hrc/${p.name}.json`, version: p.version, note: p.note || describePreset(p.name), unit: p.unit, stacks: p.stacks };
  const agg = s.spot.aggressors[0];
  if (t === "vs_open" && agg) {
    const n = p.resp[`${agg}>${s.spot.heroPosition}`]; if (!n) return null;
    const call = arr(p, n.call), three = arr(p, n.three), shove = arr(p, n.shove), evF = arr(p, n.ev.fold);
    const fold = call.map((c, i) => Math.max(0, 1 - c - three[i]! - shove[i]!));
    const R = n.resumo;
    return { ...base, node: `${s.spot.heroPosition} responde ao open de 2bb do ${agg}`, evBase: "fold",
      actions: [
        { action: "all_in", label: "All-in", freq: shove, ev: minus(arr(p, n.ev.shove), evF) },
        { action: "three_bet", label: "3Bet", freq: three, ev: minus(arr(p, n.ev.three), evF) },
        { action: "call", label: "Call", freq: call, ev: minus(arr(p, n.ev.call), evF) },
        { action: "fold", label: "Fold", freq: fold, ev: fold.map(() => 0) },
      ].filter((a) => a.freq.some((x) => x > 0) || s.legalActions.includes(a.action as DecisionAction)) as HrcSourceAction[],
      resumo: R ? { fold: R["fold"] ?? 0, call: R["call"] ?? 0, three_bet: R["three"] ?? 0, all_in: R["shove"] ?? 0 } : null };
  }
  if (t === "open_raise") {
    const n = p.rfi[s.spot.heroPosition]; if (!n) return null;
    const raise = arr(p, n.raise), shove = arr(p, n.shove), evF = arr(p, n.ev.fold);
    const fold = raise.map((r, i) => Math.max(0, 1 - r - shove[i]!));
    return { ...base, node: `Open do ${s.spot.heroPosition} (todos foldaram)${s.spot.heroPosition === "SB" ? "; na SB o resto inclui limp" : ""}`, evBase: "fold", resumo: null,
      actions: [
        { action: "all_in", label: "All-in", freq: shove, ev: minus(arr(p, n.ev.shove), evF) },
        { action: "raise", label: "Raise 2bb", freq: raise, ev: minus(arr(p, n.ev.raise), evF) },
        { action: "fold", label: s.spot.heroPosition === "SB" ? "Fold / limp" : "Fold", freq: fold, ev: fold.map(() => 0) },
      ] };
  }
  if (t === "vs_3bet" && agg) {
    const n = p.opv3[`${s.spot.heroPosition}>${agg}`]; if (!n) return null;
    const call = arr(p, n.call), shove = arr(p, n.shove);
    const evF = n.ev ? arr(p, n.ev.fold) : null;
    return { ...base, node: `${s.spot.heroPosition} abriu e tomou 3bet do ${agg}`, evBase: "fold", resumo: null,
      actions: [
        { action: "all_in", label: "All-in", freq: shove, ev: n.ev && evF ? minus(arr(p, n.ev.shove), evF) : null },
        { action: "call", label: "Call", freq: call, ev: n.ev && evF ? minus(arr(p, n.ev.call), evF) : null },
        { action: "fold", label: "Fold", freq: call.map((c, i) => Math.max(0, 1 - c - shove[i]!)), ev: evF ? evF.map(() => 0) : null },
      ] };
  }
  if (limpSpot && p.limp) {
    const L = p.limp;
    const spec = t === "limp" ? { node: L.sb, keys: [["allin", "all_in", "All-in"], ["raise", "raise", `Raise ${sz(L.raiseSize)}bb`], ["call", "limp", "Limp"], ["fold", "fold", "Fold"]], base: "fold", label: "SB na Blind War (todos foldaram)" }
      : t === "limp_call" ? { node: L.sbVsIso, keys: [["allin", "all_in", "All-in"], ["call", "call", "Call"], ["fold", "fold", "Fold"]], base: "fold", label: `SB limpou e o BB deu iso para ${sz(L.isoSize)}bb` }
      : { node: L.bbVsLimp, keys: [["allin", "all_in", "All-in"], ["raise", "raise", `Iso ${sz(L.isoSize)}bb`], ["check", "check", "Check"]], base: "check", label: "BB contra o limp da SB" };
    const node = spec.node; if (!node) return null;
    const baseEv = node[spec.base === "check" ? "check" : "fold"]?.ev;
    const actions = spec.keys.filter(([k]) => node[k!]).map(([k, a, label]) => ({ action: a as DecisionAction, label: label!, freq: arr(p, node[k!]!.freq), ev: baseEv ? minus(arr(p, node[k!]!.ev), arr(p, baseEv)) : null }));
    return { ...base, file: `/solver/hrc/${p.name}.json`, node: spec.label, evBase: spec.base as DecisionAction, resumo: null, actions };
  }
  return null;
}
