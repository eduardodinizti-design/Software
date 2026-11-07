/**
 * Malmuth–Harville ICM (valor de cada stack na moeda da premiação). Implementação no motor de ICM
 * (`src/icm/engine.ts`): exato até 20 jogadores vivos, Monte Carlo com semente fixa acima disso.
 * Stacks zerados dividem os últimos lugares.
 */
export { icmValues as icmEquity } from "@/icm/engine";
