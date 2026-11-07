# Validação dos ranges

Decisão do Eduardo (25/10/2026): só fica no ar o range que passou na comparação com uma referência externa. O que não passou aparece como "Em validação" e não pode ser treinado.

## Como funciona
1. **Família:** cada resposta do trainer pertence a uma família (`src/strategy/validation/status.ts`, `familyOf`). Exemplos: `nash:chip_ev`, `solver:chip_25`, `solver:bubble_icm`, `team:open:25`.
   - A referência aproximada (`reaction.ts`), o ICM calibrado e o chart de limp não têm família: nunca entram com a trava ligada.
   - Blind War com limp (desde 26/10): respondida pelo ramo de limp das próprias exportações do HRC (família `hrc:<situação>`); o chart de limp só fica no PKO + ICM, onde o HRC ainda não tem a situação.
2. **Referência:** cada nó copiado do HRC ou do GTO Wizard vira um arquivo em `validation/references/<nome>.json`, no formato `ReferenceFile` (`src/strategy/validation/nodes.ts`):
   ```json
   { "family": "solver:chip_25", "source": "HRC 3.x Pro, postflop model, 9-max 25bb, BB ante 1bb, open 2bb",
     "author": "…", "date": "2026-10-28",
     "node": { "type": "solver", "preset": "chip_25", "kind": "rfi", "key": "CO" },
     "ranges": { "raise": "22+,A2s+,…", "allin": "" } }
   ```
   Tipos de nó:
   - `solver`: `kind` é `rfi` (chave = posição), `resp` (chave = `"CO>BB"`, quem abriu > quem responde) ou `opv3` (chave = `"CO>BTN"`, quem abriu > quem deu 3bet).
   - `nash`: os 9 stacks de UTG a BB, `pusher` e, se for o caso, `caller` e `payouts`.
   - `team_open`: `stack` e `position`.

   Ações aceitas: `raise`, `allin`, `call`, `3bet`, `push`.
3. **Comparação:** `bun scripts/validate-ranges.ts` compara cada referência com o motor (`compareNode`) e grava `public/validation/status.json`.
4. **Trava:** `validation/config.json` → `"gate": true` liga. Com ela ligada:
   - os treinos só sorteiam mãos de famílias validadas;
   - um treino sem nenhuma família validada mostra "Em validação";
   - os drills de c-bet e de 3bet ficam fora.

## Régua (por nó)
- Pelo menos 95% dos combos com a mesma ação principal da referência.
- Nas mãos que divergem, a ação da referência perde menos de 0,05bb (ou 0,02% do prize pool) no EV do nosso motor, ou seja, são mãos quase indiferentes.

## Régua (por família)
- Todos os nós comparados aprovados, com um mínimo de nós: solver 10, Nash 4, tabelas do time 6.
- Nas famílias do solver, cada situação também precisa ter convergido: no máximo 3% das ações jogadas perdendo EV (`solverInconsistency`).
- Um nó reprovado deixa a família `reprovado`. Poucos nós deixam a família `em_validacao`.

## Limites
- **Vs 3bet:** o catálogo atual não traz o EV desse nó, então qualquer divergência reprova. Esses nós só entram depois que o solver exportar o EV.
- **SB no open:** o motor também limpa e o nó não traz o limp, então o open da SB não é comparado. Ele fica para a Blind War do solver.
