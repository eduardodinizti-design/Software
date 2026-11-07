# Auditoria dos ranges pré-flop × solver pré-flop NVT (21/10/2026)

Comparação mão a mão entre a fonte antiga do trainer e o catálogo do motor pré-flop do solver (branch `solver-data`, `preflop/catalog`, mesa de 9, open de 2bb). "Acordo" = % das combinações em que a ação principal é a mesma.

## O que passou a usar o solver

- **Vs Open** (fold/call/3bet/all-in): chip EV 25 e 40bb, PKO 25bb (early e mid), ICM/PKO+ICM 25bb em pré-ITM, bolha e mesa final.
- **Vs 3Bet** (fold/call/all-in): mesmos contextos, para as mãos que o solver abre (as outras continuam na referência aproximada).
- **Open com ICM/PKO** 25bb (com all-in) e **open da SB** em chip EV (não havia tabela do time; era o range de referência genérico).
- Open dos spots de reação com 25/40bb passou a 2bb (o mesmo do solver); a 3bet mostrada na mesa é a do solver (2,5× em posição, 2,9× na SB, 3,4× no BB com 25bb; 3,1×/3,6×/4,6× com 40bb).

## Vs Open: referência antiga × solver (chip EV, frequências do range todo, %)

| Spot | Stack | Acordo | Antigo (fold/call/3bet/all-in) | Solver (fold/call/3bet/all-in) |
|---|---|---|---|---|
| BB vs UTG | 25bb | 69.8% | 50.7/46.1/1.5/1.7 | 23.8/70.4/4.4/1.3 |
| BB vs HJ | 25bb | 76.8% | 31.7/55.4/1.3/11.6 | 18.4/71.2/5.2/5.3 |
| BB vs CO | 25bb | 80.8% | 26.2/61.8/1.3/10.6 | 17.2/69.4/4.7/8.7 |
| BB vs BTN | 25bb | 81.9% | 17.2/59.3/1.3/22.2 | 13.6/66.6/4/15.8 |
| BB vs SB | 25bb | 21.9% | 60.3/13.7/1.3/24.7 | 0/78.1/14/7.8 |
| BTN vs CO | 25bb | 66.7% | 55.2/37.3/1.3/6.2 | 75.7/6.3/0/18 |
| CO vs HJ | 25bb | 73.3% | 65.5/28.7/1.3/4.5 | 81.7/4/1.6/12.6 |
| SB vs BTN | 25bb | 80.7% | 59.1/20.7/1.3/18.9 | 70/3.4/1.7/25 |
| SB vs CO | 25bb | 87% | 68.8/17.9/1.3/12 | 71.5/10/2.2/16.4 |
| BTN vs HJ | 25bb | 78.9% | 62.1/30.4/1.3/6.2 | 75.1/11.4/1.4/12.1 |
| BTN vs UTG | 25bb | 84.3% | 81.7/15.2/1.5/1.5 | 73.8/19.4/4/2.9 |
| CO vs LJ | 25bb | 83% | 77.5/19/1.3/2.2 | 83.4/5.3/3/8.3 |
| BB vs UTG | 40bb | 76.5% | 45.2/47.2/7.5/0 | 28.6/65.3/6/0 |
| BB vs HJ | 40bb | 80.1% | 29.9/60.9/9.2/0 | 17.2/72.7/10.2/0 |
| BB vs CO | 40bb | 84.5% | 22.6/65.5/11.9/0 | 17.2/71.6/11.2/0 |
| BB vs BTN | 40bb | 82.8% | 15.4/70.7/13.9/0 | 13/71.4/14.6/1 |
| BB vs SB | 40bb | 39.8% | 48/35/17/0 | 0/80.4/17.1/2.5 |
| BTN vs CO | 40bb | 67% | 56.4/34.5/9/0 | 73.2/10.5/7.9/8.4 |
| CO vs HJ | 40bb | 71.5% | 64.6/27.6/7.8/0 | 81.1/6.2/8.9/3.8 |
| SB vs BTN | 40bb | 72.9% | 63/23.1/13.9/0 | 67.5/7.4/15.1/10 |
| SB vs CO | 40bb | 77.7% | 75.1/13/11.9/0 | 66.6/17.8/12.5/3.1 |
| BTN vs HJ | 40bb | 76.9% | 60.9/31.2/7.8/0 | 71.5/16.5/9.1/2.9 |
| BTN vs UTG | 40bb | 81.1% | 81.4/12.7/5.9/0 | 70.6/22.7/6.7/0 |
| CO vs LJ | 40bb | 83.1% | 76.9/15.2/7.8/0 | 80.9/8.6/8.8/1.7 |

Padrões do erro antigo: SB e cold call em posição pagavam demais (o solver quase só dá all-in ou fold com 25bb); o BB contra a SB foldava 48–60% (o solver defende ~100%); a 3bet de valor/blefe usava Axs que o solver prefere pagar.

## Vs 3Bet: referência antiga × solver (seu range de open, %)

| Spot | Stack | Acordo | Antigo (fold/call/all-in) | Solver (fold/call/all-in) |
|---|---|---|---|---|
| CO vs 3bet do BTN | 25bb | 20,4% | 62/14/24 | 0/81/20 |
| HJ vs 3bet do CO | 25bb | 41,4% | 59/12/30 | 16/57/27 |
| BTN vs 3bet do BB | 25bb | 71,2% | 65/0/35 | 43/31/26 |
| CO vs 3bet do BTN | 40bb | 49,5% | 72/12/15 | 27/49/25 |
| BTN vs 3bet do BB | 40bb | 80,3% | 69/1/30 | 56/20/24 |

O modelo antigo foldava demais contra 3bet e quase nunca pagava fora das blinds.

## Open raise: tabelas do time × solver (não alterado, decisão do time)

| Posição | Stack | Acordo | Tabela do time | Solver (raise + all-in) |
|---|---|---|---|---|
| UTG | 25bb | 95.6% | 9.9% (tabela NVT) | 14.7% |
| LJ | 25bb | 95.5% | 16% (tabela NVT) | 19.3% |
| HJ | 25bb | 94.9% | 21.9% (tabela NVT) | 23.4% |
| CO | 25bb | 96.7% | 30% (tabela NVT) | 29.5% |
| BTN | 25bb | 88.2% | 49.3% (tabela NVT) | 38.9% (all-in 2.4%) |
| SB | 25bb | 67% | 43.5% (referência genérica → agora solver) | 29.3% (all-in 14.3%) |
| UTG | 40bb | 97.1% | 11.3% (tabela NVT) | 15.4% |
| LJ | 40bb | 94% | 17% (tabela NVT) | 23.4% |
| HJ | 40bb | 96.7% | 25.2% (tabela NVT) | 27.5% |
| CO | 40bb | 96.1% | 31.4% (tabela NVT) | 34.7% |
| BTN | 40bb | 90% | 49.5% (tabela NVT) | 47.4% |
| SB | 40bb | 72.9% | 47.3% (referência genérica → agora solver) | 74% |

As tabelas do time ficam como estão (94–97% de acordo). Maior diferença: **BTN com 25bb** (tabela 49%, solver 39% com open de 2bb). O open da SB não tinha tabela do time e passou para o solver.

## Open com ICM (referência calibrada antiga × solver, stacks iguais)

Acordo de 82–95% nas posições UTG–BTN e de 44–61% na SB: perto do dinheiro o solver troca boa parte do open por all-in (BTN na bolha: 24,5% raise + 41,6% all-in; a referência antiga só tinha raise). Agora vem do solver, com o botão de all-in.

## Ainda sem solver (continua a fonte anterior, com o rótulo dela)

- Vs Open/Vs 3Bet com **100bb** e Vs Open com **15bb** (o catálogo tem 25 e 40bb).
- ICM e PKO com **40bb** (o catálogo de ICM é de 25bb).
- Blind War (limp/iso) e shove PKO: tabelas do time; push/fold, resteal e call de shove: Nash (já calculado).
- Pedido ao solver em aberto: sizes de 3bet (`solver-requests/2026-10-21-sizes-de-3bet.md`). Para cobrir o resto, vale pedir também 100bb e 15bb no catálogo e ICM com 40bb.
