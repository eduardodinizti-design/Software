/** Real payout structures typed or pasted by the user (final table). Pure helpers, no storage. */
import type { PayoutStructure } from "./tournament";

/**
 * Exemplo real informado pelo time: mesa final de um PKO 50/50 no PPPoker (clube Broka),
 * valores do clube × 3,5 (R$). Buy-in 30,40 × 3,5 = R$ 106,40 → bounty inicial R$ 53,20.
 */
export const BROKA_PKO = {
  payouts: [1210.51, 680.82, 472.78, 397.11, 313.91, 276.08, 234.5, 196.66],
  startingBounty: 53.2,
} as const;

export type ParsedPayouts = { prizes: number[]; error: null } | { prizes: null; error: string };

/** Parses one value: "R$ 25.000,50", "25000", "25,000.50", "25.000" → number. */
export function parseMoney(raw: string): number | null {
  let t = raw.replace(/[^\d.,]/g, "");
  if (!t) return null;
  const lastDot = t.lastIndexOf("."), lastComma = t.lastIndexOf(",");
  if (lastDot >= 0 && lastComma >= 0) {
    // The later separator is the decimal one.
    t = lastComma > lastDot ? t.replace(/\./g, "").replace(",", ".") : t.replace(/,/g, "");
  } else if (lastComma >= 0) {
    // "25,000" (thousands) vs "25,5" (decimal)
    t = /^\d{1,3}(,\d{3})+$/.test(t) ? t.replace(/,/g, "") : t.replace(",", ".");
  } else if (lastDot >= 0 && /^\d{1,3}(\.\d{3})+$/.test(t)) {
    t = t.replace(/\./g, ""); // "25.000" (pt-BR thousands)
  }
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

/**
 * One prize per line (or separated by ";"), 1st place first. Optional "1º:" / "1st -" prefixes are ignored.
 * Requires at least 2 positive, non-increasing values.
 */
export function parsePayouts(text: string, maxPlaces = 9): ParsedPayouts {
  const items = text.split(/[\n;]+/).map((l) => l.trim()).filter(Boolean);
  const prizes: number[] = [];
  for (const line of items) {
    // Strip a leading place marker: "1º", "1º:", "2nd -", "3)", "4 lugar:" (a bare "4 9000" stays ambiguous → invalid order).
    const value = line.replace(/^\s*\d+\s*(º|°|st|nd|rd|th|lugar)\s*[:\-–)]?\s*/i, "").replace(/^\s*\d+\s*[:\-–)]\s*/, "");
    const n = parseMoney(value);
    if (n === null || n <= 0) return { prizes: null, error: `Valor inválido: "${line}"` };
    prizes.push(n);
  }
  if (prizes.length < 2) return { prizes: null, error: "Informe pelo menos 2 prêmios (1º e 2º lugar)." };
  if (prizes.some((p, i) => i > 0 && p > prizes[i - 1]!)) return { prizes: null, error: "Os prêmios devem estar em ordem: do 1º lugar para baixo." };
  if (prizes.length > maxPlaces) return { prizes: null, error: maxPlaces === 9 ? "Use só os prêmios da mesa final (até 9 lugares)." : `Informe no máximo ${maxPlaces} prêmios.` };
  return { prizes, error: null };
}

export function validPayouts(prizes: number[] | undefined): boolean {
  return !!prizes && prizes.length >= 2 && prizes.length <= 9 && prizes.every((p, i) => p > 0 && (i === 0 || p <= prizes[i - 1]!));
}

/** Real final-table structure for a table with `players` left: places 1..players. */
export function realFinalTable(prizes: number[], players: number): PayoutStructure {
  const paid = prizes.slice(0, players);
  return {
    prizePool: paid.reduce((a, b) => a + b, 0),
    prizes: paid,
    source: "imported",
    label: `Premiação real da mesa final: ${players} jogadores, ${Math.min(players, prizes.length)} pagos`,
  };
}
