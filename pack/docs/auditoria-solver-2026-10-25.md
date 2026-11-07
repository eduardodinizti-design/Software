# Auditoria do solver (25/10/2026)

Esta auditoria verifica se os dados do solver que o trainer usa são válidos. Os scripts ficaram fora do repositório e as contas foram refeitas sobre `public/solver/preflop/*.json` (commit do solver-data `3c6b074`).

## 1. Consistência interna do catálogo pré-flop
Teste: num equilíbrio convergido, toda ação jogada com 5% ou mais deve render quase o mesmo que a melhor ação da mão (tolerância de 0,05bb no chip EV e de 0,02% do prize pool no ICM). Medimos a fração das ações jogadas que perdem mais que isso.

| Situação | RFI | Respostas ao open | Leitura |
|---|---|---|---|
| chip_25, chip_40 | 0% | 0–0,02% | convergido |
| ICM / PKO+ICM (18 situações) | 0–2,6% | 0–7% (perda média ≤ 0,001% do prize pool) | aceitável |
| pkochip_25 | 0% | 0,6% | convergido, mas degenerado (abaixo) |
| **pkomid_25** | **9,7%** | **15,9%** (AA com 3bet perdendo 5,5bb) | **não convergiu** |

## 2. Problemas encontrados e o que foi feito
- **SB no open raise (chip_25 e as FT e PKO com limp):** o motor limpa parte das mãos na Blind War, mas o trainer não tem limp no open raise. Essa fatia virava "fold correto", inclusive em mãos em que o raise rende +0,4 a +0,6bb sobre o fold (K7o, J9o). No chip_25, 43% dos combos da SB eram afetados.
  - **Corrigido:** quando raise ou all-in rende mais que o fold, a fatia vai para a melhor ação legal pelo EV, e a explicação avisa que o motor limparia.
- **pkochip_25:**
  - Abre 94,6% de UTG a HJ, o BTN dá shove com 85% e a SB com 87%.
  - Usa a convenção antiga de bounty: metade da cabeça pelo valor de face. Isso dá cabeça de 1,3 stack, equivalente a BP ≈ 2,4 na tabela do time.
  - **Desligado.**
- **pkomid_25:** não convergiu (seção 1). **Desligado.**
- Com o PKO chip EV desligado, o PKO 25bb volta para as fontes anteriores: tabela do time no open, referência aproximada no vs open.

## 3. Premissas que limitam a validade (não são bugs)
1. **Pós-flop por realização:**
   - O motor não resolve o pós-flop. Ele usa equity × fator de realização por classe de mão.
   - O fator vem de poucos spots resolvidos: CO vs BB 40bb, SB vs BB, CO vs BTN, pote limpado e 3bet BB vs CO. Ele é reaproveitado em todas as posições, stacks e potes multiway (share3 × realização).
   - No PKO e no ICM, o pote pós-flop é tratado como binário.
   - Por isso, diferenças de EV abaixo de ~0,05–0,1bb estão dentro do erro do modelo, e frequências exatas por mão não são confiáveis. A correção por EV perdido (tolerância de 0,03bb) é a forma certa de usar esses dados.
2. **A mesa é o field inteiro:**
   - No ICM, pré-ITM = 9 restantes com 7 pagos e bolha = 9 restantes com 8 pagos. Isso é um ICM de satélite, bem mais forte que a bolha de um MTT real, com várias mesas.
   - Exemplo: na bolha com stacks iguais, a SB joga 100% das mãos (30,7% raise + 69,3% shove) e o BB folda 52% contra o BTN.
   - O motor de ICM do trainer já modela o field real (`withIcmField`); o catálogo não.
3. **Drill de 3bet:** os dois sizes usam a mesma curva de realização pós-flop. A diferença entre eles vem de pot odds e fold equity, não de jogabilidade.
4. **Pós-flop (drill de c-bet):**
   - Só `co_vs_bb_40_v2` tem a defesa do BB calculada.
   - BTN 40, CO 25 e BTN 25 ainda são v1, com o BB defendendo pelo `reaction.ts` (range capado, folda demais).
   - A amostra é de 45 flops por spot, com árvore reduzida (33/65/100% no flop; 66% ou all-in no turn e no river).
5. **Validação externa:** nenhum resultado foi comparado com um solver comercial (GTO Wizard, HRC, PioSOLVER). A única comparação externa prevista (`check_nash_bubble.ts`, contra o Nash do trainer) não teve o resultado registrado.

## 4. Estado do servidor do solver
- Último commit no `solver-data`: 21/10.
- Os jobs `btn_vs_bb_40__iter_final` (14/45) e `cal100_co_vs_bb` (25/64) ficaram parados.
- O pedido de 24/10 (foco no pré-flop) e o de 22/10 (PKO por bounty power) ainda não foram atendidos.
