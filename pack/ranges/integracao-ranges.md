# Integração dos ranges do NVT Range Lab com outro sistema

Há dois jeitos de levar a lógica dos ranges para outro sistema.

| | A. Pacote de ranges (recomendado) | B. Motor como biblioteca |
|---|---|---|
| O que vai | Um JSON com a estratégia de cada spot para as 169 mãos | O código do motor (`src/strategy`, `src/domain`, `src/icm`) |
| Linguagem do outro sistema | Qualquer uma (é só ler JSON) | TypeScript/JavaScript |
| Spots | Os nós exportados (mesas-padrão de cada spot) | Qualquer mesa, com os stacks reais |
| Exploit contra stats do vilão | Não (é equilíbrio) | Sim |
| Atualização | Gerar o pacote de novo e substituir o arquivo | Atualizar o código |

## A. Pacote de ranges

### Gerar

```bash
bun scripts/export-ranges.ts                      # tudo → dist/export/nvt-ranges.json
bun scripts/export-ranges.ts --only-validated     # só o que entra nos treinos (famílias validadas)
bun scripts/export-ranges.ts --modes chip_ev,icm --spots open_raise,vs_open,vs_3bet --stacks 25,40
```

O script roda o próprio motor do trainer para as 169 mãos de cada spot, como a matriz colorida do feedback. Por isso o pacote já vem com tudo o que o trainer aplica por cima dos arquivos do HRC:

- frequências abaixo de 5% descartadas;
- pares na ordem natural;
- empates de EV viram mix;
- quando a frequência do HRC contradiz o EV dele, vale a ação de maior EV;
- no vs 3bet, as mãos fora do seu range de open ficam marcadas;
- ajustes de ICM e PKO.

O outro sistema não precisa refazer nenhuma dessas contas.

### Copiar para o outro sistema

1. `nvt-ranges.json`, o pacote.
2. `integration/nvt-ranges-client.ts`, o cliente de exemplo, sem dependências. Em outra linguagem, ele serve de referência: são ~100 linhas.

### O que está no pacote

```jsonc
{
  "format": "nvt-range-export", "version": 1,
  "generatedAt": "2026-10-29T…", "engineCommit": "5d8b8b7",
  "validation": { "version": "…", "gate": true },
  "hands": ["AA", "AKs", "AQs", …],          // 169 mãos; todos os arrays por mão seguem esta ordem
  "combos": [6, 4, 4, …],                     // combos de cada mão (para pesar % de range)
  "actionLabels": { "fold": "Fold", "call": "Call", "all_in": "All-in", "three_bet": "3bet", … },
  "nodes": [ … ]
}
```

Cada nó é um spot:

| Campo | O que é |
|---|---|
| `id` | Chave única: `modo\|fase\|stack\|spot\|herói\|quem agiu\|spread` |
| `context` | `mode` (`chip_ev`, `icm`, `pko`, `pko_icm`), `format`, `stage` (`mid`, `pre_itm`, `bubble`, `ft`), `players` (9), `stack` (bb) |
| `spot` | `open_raise`, `open_shove`, `vs_open_shove`, `3bet_shove` (resteal), `vs_open`, `vs_3bet`, `limp`, `limp_call`, `vs_limp` |
| `hero` | Posição do herói (`UTG`, `UTG+1`, `UTG+2`, `LJ`, `HJ`, `CO`, `BTN`, `SB`, `BB`) |
| `vs` | Quem agiu antes de forma agressiva, em ordem (opener, 3bettor, shover) |
| `spread` | Só ICM/PKO + ICM: distribuição de stacks (`iguais`, `curtos_ini`, `curtos_fim`) |
| `table` | Mesa usada: stack de cada posição, ações antes do herói (posts, open, 3bet…) e pote |
| `source` | De onde veio a resposta (ex.: "HRC (chip EV, todos com 25bb)", "Nash (push/fold)") |
| `family`, `validated` | Família de validação e se ela está validada (só as validadas entram nos treinos) |
| `evUnit` | `bb` (chip EV) ou `pct` (% do prize pool; no PKO, prêmios + bounties) |
| `legalActions` | Ações que o jogador pode escolher no spot |
| `actions` | Ações que aparecem na estratégia (mais agressiva primeiro, fold por último) |
| `freq[ação]` | 169 frequências (0–1) |
| `ev[ação]` | 169 EVs contra o fold (`null` quando a fonte não calcula EV; fold = 0) |
| `outOfRange` | Índices das mãos que não chegam ao spot (vs 3bet: você não abre) |
| `totals` | % dos combos em cada ação |

Exemplo (chip EV 25bb, UTG abriu e tomou 3bet do CO):

```jsonc
{
  "id": "chip_ev|mid|25|vs_3bet|UTG|CO|-",
  "spot": "vs_3bet", "hero": "UTG", "vs": ["CO"],
  "source": { "id": "solver", "label": "HRC (chip EV, todos com 25bb)" },
  "validated": true, "evUnit": "bb",
  "actions": ["all_in", "call", "fold"],
  "totals": { "all_in": 18.5, "call": 56.6, "fold": 24.8 },
  "freq": { "all_in": [0, 1, …], "call": [1, 0, …], "fold": [0, 0, …] },
  "ev":   { "all_in": [15.19, 4.37, …], "call": [15.33, 3.52, …], "fold": [0, 0, …] }
}
```

### Como usar (lógica de correção do trainer)

1. **Achar o nó**: modo, stack, spot, posição do herói e quem agiu antes. No ICM, informe também a fase e o spread. Se o outro sistema tiver os stacks reais da mesa, `nearestSpread(stacks)` escolhe o spread com a mesma conta do trainer.
2. **Ler a mão**: `freq[ação][i]`, sendo `i` o índice da mão em `hands`. Para converter cartas em mão, use `handKey("AhKd") → "AKo"`.
3. **Corrigir uma resposta**:
   - certa se a ação tem frequência > 0 no nó;
   - também certa se o nó tem EV e a ação perde menos que **0,03bb** (chip EV) ou **0,01% do prize pool** (ICM) para a melhor. É o "quase indiferente".
   - Mão em `outOfRange`: não pergunte (ela não chega ao spot).
4. **Mostrar o porquê**: os EVs de `ev[ação]` dão o "quanto perde" de cada erro.

```ts
import { NvtRanges } from "./nvt-ranges-client";
const ranges = NvtRanges.fromJson(await (await fetch("/nvt-ranges.json")).json());
const node = ranges.find({ mode: "icm", stage: "bubble", stack: 25, spot: "vs_open", hero: "BB", vs: ["BTN"],
                           stacks: { UTG: 35, "UTG+1": 35, /* … */ BB: 20 } });
ranges.strategy(node!, "A5s");      // { mix: [{ action: "three_bet", frequency: 1 }], ev: { three_bet: 0.21, call: 0.05, … } }
ranges.grade(node!, "A5s", "call");  // { correct: false, correctness: "STRATEGIC_ERROR", evLoss: 0.16, best: "three_bet" }
ranges.matrix(node!, "three_bet");   // 13×13 para desenhar a grade
```

### Limites do pacote

- **Mesas-padrão.** No chip EV, os ranges do HRC são de 25bb para todos (40bb no catálogo do time, e por aí vai). Os stacks em `table` são da mesa que gerou o nó, mas a resposta não depende deles.
- **ICM e PKO + ICM.** Existe um nó por distribuição de stacks (o arquivo do HRC daquele spread). O trainer, com os stacks reais, faz o mesmo, exceto nos spots calculados na hora (push/fold e resteal com ICM, vs open com shove). Nesses, o pacote traz a mesa usada na exportação. Para responder com os stacks reais, use a opção B.
- **Exploit** (resposta contra o 3-Bet, Fold para 3-Bet ou Steal do vilão): não está no pacote, porque depende do vilão. Use a opção B, ou leve o modelo:
  - vs 3bet: range de 3bet do vilão = equilíbrio × (3-Bet ÷ 8), limitado a 0,4–2,2×, mãos mais fortes primeiro;
  - all-in: calls = equilíbrio × (100 − Fold para 3-Bet) ÷ 44; shoves = equilíbrio × Steal ÷ 40.
  
  Detalhes em `AGENTS.md` (Villain exploit, Exploit stage 3, Exploit vs 3bet with ICM).
- **EV 0 com frequência 0** (cerca de 0,2% dos valores, fora o fold): é ação que o HRC praticamente não joga naquele nó e para a qual não exportou EV. Trate como "não calculado", não como empate com o fold.
- **Validação.** Com `--only-validated` saem só os nós que o trainer usa nos treinos. Sem a opção, o pacote traz também os spots com referência aproximada, marcados com `validated: false`.

## B. Motor como biblioteca (TypeScript)

Copie `src/domain`, `src/strategy`, `src/icm` e `src/generator` (ou importe o repositório como pacote). Carregue os dados de `public/solver` e `public/validation`, como faz o `scripts/export-ranges.ts`, e chame:

```ts
import { strategyEngine } from "@/strategy/engine";
const d = strategyEngine.decide(scenario);   // scenario: mesa, stacks, ações, mão, contexto (TrainingScenario)
d.recommended; d.alternatives;               // mix
d.actionEvs; d.evUnit;                       // EVs
d.explanation;                               // texto do "por quê"
d.villainRead;                               // exploit (com scenario.exploit = true)
strategyEngine.grade(d, "call");             // mesma correção do trainer
```

O `TrainingScenario` (`src/domain/scenario.ts`) é o formato de entrada: `context` (modo, formato, fase, stack, jogadores), `table` (jogadores com posição, stack e bounty; ações; blinds), `spot` (tipo, posição do herói, agressores), `hero.hand` e, no ICM, `tournament.payouts.prizes`.

## Manter sincronizado

Sempre que os ranges mudarem (novo cálculo do HRC, correção no motor), gere o pacote de novo. `engineCommit` e `generatedAt` dizem de qual versão ele veio, e `validation.version`, de qual status de validação.
