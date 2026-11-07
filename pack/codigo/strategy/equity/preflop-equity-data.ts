/**
 * GENERATED — do not edit by hand.
 * Preflop all-in equity between the 169 hand classes (row-major 13x13 grid order, see cellHand()).
 * Monte Carlo: 250,000 samples per class pair (uniform over non-overlapping combo pairs and boards),
 * standard error ≈ 0.1 pp. Evaluator validated against exact 7-card category frequencies.
 * Encoding: upper triangle (a < b) as little-endian uint16, value = equity(a vs b) * 65535, base64.
 */
import { PREFLOP_EQUITY_B64_A } from "./preflop-equity-data-a";
import { PREFLOP_EQUITY_B64_B } from "./preflop-equity-data-b";

export const EQUITY_SAMPLES_PER_PAIR = 250000;
/** Dividido em duas partes só para caber em mensagens/edições menores (ex.: chat do Lovable). */
export const PREFLOP_EQUITY_B64 = PREFLOP_EQUITY_B64_A + PREFLOP_EQUITY_B64_B;
