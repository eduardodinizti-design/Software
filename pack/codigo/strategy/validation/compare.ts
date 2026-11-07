/**
 * Comparação de um nó do motor com a referência externa (HRC, GTO Wizard, PioSOLVER…).
 *
 * Régua de liberação (decidida pelo Eduardo em 25/10/2026):
 * - pelo menos 95% dos combos com a mesma ação principal da referência;
 * - nas mãos que divergem, a ação da referência perde menos de 0,05bb (ou 0,02% do prize pool) no nosso EV,
 *   ou seja, a divergência é uma mão quase indiferente, não um erro;
 * - (nas situações do solver) o cálculo convergiu: no máximo 3% das ações jogadas perdem EV — checado à parte.
 */
import { ALL_HANDS, combos, type HandKey } from "@/domain/cards";

export const AGREEMENT_MIN = 0.95;
export const DIVERGENCE_EV_MAX = { bb: 0.05, pct: 0.02 } as const;

const RANKS = "AKQJT98765432";
const ri = (r: string) => RANKS.indexOf(r);

/** Mãos (classe de 169) de um token sem peso: "AA", "AKs", "TT+", "A2s+", "KTo-K8o", "22-55", "AK" (s + o). */
function expandToken(tok: string): HandKey[] {
  const t = tok.trim();
  if (!t) return [];
  const pair = /^([AKQJT2-9])\1$/;
  const one = /^([AKQJT2-9])([AKQJT2-9])([so]?)$/;
  const mk = (a: string, b: string, s: string): HandKey[] => (a === b ? [`${a}${b}` as HandKey] : s ? [`${a}${b}${s}` as HandKey] : [`${a}${b}s` as HandKey, `${a}${b}o` as HandKey]);
  const norm = (h: string) => { const [a, b, s = ""] = [h[0]!, h[1]!, h.slice(2)]; return ri(a) <= ri(b) ? { a, b, s } : { a: b, b: a, s }; };
  if (t.endsWith("+")) {
    const base = t.slice(0, -1);
    if (pair.test(base)) { const k = ri(base[0]!); return RANKS.slice(0, k + 1).split("").map((r) => `${r}${r}` as HandKey); }
    const m = one.exec(base); if (!m) return [];
    const { a, b, s } = norm(base);
    const out: HandKey[] = [];
    for (let k = ri(b); k > ri(a); k--) out.push(...mk(a, RANKS[k]!, s));
    return out;
  }
  if (t.includes("-")) {
    const [x, y] = t.split("-").map((v) => v.trim());
    if (!x || !y) return [];
    if (pair.test(x) && pair.test(y)) { const [hi, lo] = [Math.min(ri(x[0]!), ri(y[0]!)), Math.max(ri(x[0]!), ri(y[0]!))]; return RANKS.slice(hi, lo + 1).split("").map((r) => `${r}${r}` as HandKey); }
    const nx = norm(x), ny = norm(y);
    if (nx.a !== ny.a || nx.s !== ny.s) return [];
    const [hi, lo] = [Math.min(ri(nx.b), ri(ny.b)), Math.max(ri(nx.b), ri(ny.b))];
    const out: HandKey[] = [];
    for (let k = hi; k <= lo; k++) out.push(...mk(nx.a, RANKS[k]!, nx.s));
    return out;
  }
  if (pair.test(t)) return [t as HandKey];
  if (one.test(t)) { const { a, b, s } = norm(t); return mk(a, b, s); }
  return [];
}

/**
 * Lê um range em texto nos formatos comuns: "AA,AKs:0.5,KQo:50", "[50]AKs,AQs[/50]", "TT+,A2s+,KTo-K8o".
 * Peso > 1 é lido como porcentagem. Mãos repetidas: vale a última. Retorna frequência 0..1 por classe.
 * Combos específicos ("AhKh") entram como fração da classe.
 */
export function parseRange(text: string): Record<HandKey, number> {
  const out: Partial<Record<HandKey, number>> = {};
  const combosSeen = new Map<HandKey, number>();
  const src = text.replace(/\s+/g, " ").trim();
  // Grupos [w]...[/w]
  const parts: { body: string; w: number | null }[] = [];
  let rest = src;
  const re = /\[(\d+(?:\.\d+)?)\]([^[]*)\[\/\1\]/g;
  rest = rest.replace(re, (_m, w: string, body: string) => { parts.push({ body, w: Number(w) }); return ","; });
  parts.push({ body: rest, w: null });
  for (const { body, w: groupW } of parts) {
    for (const raw of body.split(/[,;\s]+/)) {
      if (!raw) continue;
      const [tok, wTxt] = raw.split(":");
      let w = wTxt !== undefined ? Number(wTxt) : groupW ?? 1;
      if (!Number.isFinite(w)) continue;
      if (w > 1) w /= 100;
      const c = /^([AKQJT2-9])([shdc])([AKQJT2-9])([shdc])$/.exec(tok!.trim());
      if (c) {
        const [a, sa, b, sb] = [c[1]!, c[2]!, c[3]!, c[4]!];
        const [hi, lo] = ri(a) <= ri(b) ? [a, b] : [b, a];
        const key = (hi === lo ? `${hi}${lo}` : `${hi}${lo}${sa === sb ? "s" : "o"}`) as HandKey;
        combosSeen.set(key, (combosSeen.get(key) ?? 0) + w);
        continue;
      }
      for (const h of expandToken(tok!)) out[h] = w;
    }
  }
  for (const [h, sum] of combosSeen) out[h] = Math.min(1, (out[h] ?? 0) + sum / combos(h));
  return Object.fromEntries(ALL_HANDS.map((h) => [h, Math.max(0, Math.min(1, out[h] ?? 0))])) as Record<HandKey, number>;
}

export type NodeStrategy = Record<string, Record<HandKey, number>>;
export interface NodeComparison {
  /** Fração dos combos (ponderada) com a mesma ação principal. */
  agreement: number;
  /** Similaridade de frequência: 1 − ½ Σ|f_nosso − f_ref| (média por combo). */
  overlap: number;
  /** Mãos com ação principal diferente, com o EV que a ação da referência perde no nosso modelo. */
  divergent: { hand: HandKey; ours: string; ref: string; evGap: number | null }[];
  /** Maior perda de EV entre as divergentes (null = sem EV do nosso lado). */
  worstGap: number | null;
  passed: boolean;
}

/** Ação principal de uma mão (a de maior frequência; "fold" = o que sobra). */
function mainAction(st: NodeStrategy, h: HandKey): string {
  let best = "fold", bestF = Math.max(0, 1 - Object.values(st).reduce((a, r) => a + (r[h] ?? 0), 0));
  for (const [a, r] of Object.entries(st)) if ((r[h] ?? 0) > bestF + 1e-9) { best = a; bestF = r[h] ?? 0; }
  return best;
}

/**
 * Compara a estratégia do motor com a da referência no mesmo nó. `oursEv[action][hand]` = EV relativo ao fold
 * (fold = 0), na unidade `unit`; serve para medir se uma divergência é quase indiferente.
 */
export function compareNode(ours: NodeStrategy, ref: NodeStrategy, oursEv: Record<string, Partial<Record<HandKey, number>>> | null, unit: "bb" | "pct", inRange?: Partial<Record<HandKey, number>>): NodeComparison {
  const actions = [...new Set([...Object.keys(ours), ...Object.keys(ref)])];
  let w = 0, same = 0, ov = 0;
  const divergent: NodeComparison["divergent"] = [];
  for (const h of ALL_HANDS) {
    const reach = inRange ? (inRange[h] ?? 0) : 1;
    if (reach <= 0) continue;
    const c = combos(h) * reach;
    w += c;
    const a = mainAction(ours, h), b = mainAction(ref, h);
    if (a === b) same += c;
    else {
      const ev = (act: string) => (act === "fold" ? 0 : oursEv?.[act]?.[h] ?? null);
      const ea = ev(a), eb = ev(b);
      divergent.push({ hand: h, ours: a, ref: b, evGap: ea !== null && eb !== null ? Math.max(0, ea - eb) : null });
    }
    const fo = (st: NodeStrategy, act: string) => st[act]?.[h] ?? 0;
    const foldO = Math.max(0, 1 - actions.reduce((s, x) => s + fo(ours, x), 0)), foldR = Math.max(0, 1 - actions.reduce((s, x) => s + fo(ref, x), 0));
    const diff = actions.reduce((s, x) => s + Math.abs(fo(ours, x) - fo(ref, x)), 0) + Math.abs(foldO - foldR);
    ov += c * (1 - diff / 2);
  }
  const gaps = divergent.map((d) => d.evGap).filter((g): g is number => g !== null);
  const worstGap = gaps.length ? Math.max(...gaps) : divergent.length ? null : 0;
  const agreement = w ? same / w : 1;
  const passed = agreement >= AGREEMENT_MIN && worstGap !== null && worstGap < DIVERGENCE_EV_MAX[unit];
  return { agreement, overlap: w ? ov / w : 1, divergent: divergent.sort((x, y) => (y.evGap ?? 9) - (x.evGap ?? 9)), worstGap, passed };
}

/** Range em texto ("AA:1,AKs:0.5,…"), o mesmo formato que `parseRange` lê. */
export const formatRange = (r: Partial<Record<HandKey, number>>) => ALL_HANDS.filter((h) => (r[h] ?? 0) > 0.0005).map((h) => `${h}:${Number((r[h] ?? 0).toFixed(3))}`).join(",");
