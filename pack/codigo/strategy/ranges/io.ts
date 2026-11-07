/** Import/export of ranges. JSON = array of RangeDefinition; CSV = one row per hand. */
import type { RangeDefinition } from "./types";

export const exportRangesJson = (ranges: RangeDefinition[]) => JSON.stringify(ranges, null, 2);

export function importRangesJson(text: string): RangeDefinition[] {
  const data = JSON.parse(text);
  const arr = Array.isArray(data) ? data : [data];
  return arr.filter((r): r is RangeDefinition => r && typeof r.id === "string" && typeof r.hands === "object");
}

/** CSV columns: hand,frequency — for a single range. */
export function handsFromCsv(text: string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const line of text.split(/\r?\n/)) {
    const [h, f] = line.split(",").map((x) => x.trim());
    if (!h || h.toLowerCase() === "hand") continue;
    const n = f === undefined || f === "" ? 1 : Number(f);
    if (!Number.isNaN(n) && n > 0) out[h] = Math.min(1, n);
  }
  return out;
}

export const handsToCsv = (hands: Record<string, number>) =>
  ["hand,frequency", ...Object.entries(hands).map(([h, f]) => `${h},${f}`)].join("\n");
