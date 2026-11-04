# Pós-flop: ranges condicionais, raises e antecipação do river

Esta evolução é offline e experimental. Não modifica o coletor, não envia ações a aplicativos e
não transforma o modelo adversário em uma estratégia GTO. Não é homologação de Windows.

## Implementação

`visualpilot/lab/range_state.py` mantém o range de uma mão fictícia: origem NVT, pesos iniciais,
cartas conhecidas, observações e probabilidades usadas. Cada ação atualiza os pesos por Bayes:
posterior(combo) = prior(combo) × probabilidade(ação | combo) / probabilidade(ação).
Novas cartas removem combos bloqueados. Eventos repetidos, probabilidades ausentes/inválidas,
boards incompatíveis e evidências de probabilidade zero são rejeitados sem alterar o estado.
Não há fallback silencioso para um range genérico. Este objeto rastreia o range; não é um ledger
completo de apostas ou uma implementação de todas as regras de poker.

`visualpilot/lab/river_tree.py` calcula a melhor resposta contra um modelo adversário fixo numa
árvore finita. Hero fora de posição, heads-up, chip EV, stacks efetivos iguais disponíveis no
início do river. Inclui check, bets, fold/call e um raise por linha. Hero pode fazer check-raise;
adversário pode dar raise contra bet do Hero. Raises são para um investimento total no river,
e respeitam mínimo de duas vezes a aposta inicial, exceto short all-in. Sem reraises.

O cálculo maximiza o EV do Hero sobre o range condicionado no nó público. Não maximiza
separadamente para cada mão escondida, o que produziria uma estratégia impossível de executar.
O modelo adversário recebe suas próprias cartas, board, ações públicas e opções legais; não recebe
as cartas reais do Hero. A integração atual não estima esse modelo a partir de tracker.

Payoffs relativos ao início do river:
- Hero vence por fold: pote inicial + investimento do adversário.
- Hero folda: negativo do investimento já feito pelo Hero.
- Showdown: equidade × (pote inicial + ambos investimentos) − investimento do Hero.

`plan_rivers` enumera a chance do river após o encerramento das apostas do turn. Para cada combo
adversário há 44 cartas possíveis. A chance de cada river e o range posterior respeitam esses
bloqueadores; não assume 46 cartas uniformes independentemente do range. Resolve a árvore para
cada river. **Ainda não compara apostas no turn nem joga o flop inteiro.**

## Experimento reproduzido

Range inicial real do NVT: open-raise BTN, chipEV, 25BB, extraído do fixture autêntico existente.
Hero Ah Jh; flop Kh 8h 2c. Linha controlada: pote inicial 6BB, check / bet2 / call2; turn3d,
check / check; river9s. Pote final para decisão10BB, stack efetivo restante18BB.
O range é condicionado pelo bet no flop, check no turn e cartas novas. A linha de chegada foi
fixada pelo experimento; não alegamos que ela tenha sido escolhida pela nova engine.

Cinco modelos sintéticos usam força de mão e agressividade diferentes. Foram escritos para testar
a sensibilidade da engine. Não são estratégias do NVT, não foram treinados em dados de jogadores
e não constituem recomendações aprovadas. O runner não pede ao usuário respostas corretas.

| Perfil sintético | Melhor ação inicial sob o modelo | EV incremental BB |
| --- | --- | --- |
| agressividade0.10 | bet3 | 5.9767 |
| agressividade0.25 | bet3 | 5.2312 |
| agressividade0.50 | bet3 | 4.0562 |
| agressividade0.75 | check | 4.2801 |
| agressividade0.90 | check | 4.6844 |

O perfil0.50 contém também 46 rivers possíveis com planos condicionais. EVs entre perfis não
medem a rentabilidade de uma mudança da engine: o oponente e os ranges posteriores diferem.

## Uso e evidências

```sh
.venv/bin/python -m tools.run_postflop_tree
.venv/bin/python -m tools.build_postflop_report
.venv/bin/python -m unittest tests.test_postflop_tree -v
.venv/bin/python -m unittest discover -s tests
```

- `experiments.json.gz`: rastros completos comprimidos sem perdas; respostas por combo, posterior,
  opções/EV em cada decisão, source NVT e hashes. Abrir com gzip + JSON.
- `experiments.log`: resultados resumidos e tempo do experimento.
- `full-suite.log`: 205 testes, 202 aprovados, 3 skips, nenhuma falha.
- `targeted.log`: 11 testes novos aprovados; executados novamente após expandir o registro dos pesos.
- `browser.json`: cinco perfis, seleção de nós/river, autoplay/pausa e largura390px em Chromium,
  nenhum erro JavaScript. O teste usou servidor HTTP local para verificar o HTML portátil.
- `VisualPilot_Posflop_Experimentos.zip`: HTML sem dependências com visualização dos resultados
  pré-calculados; não roda OCR nem calcula novos cenários dentro do navegador.

Testes analíticos incluem: Bayes3:1 com likelihood0.1:0.9 resultando1:3; empate devolvendo metade
do pote; fold após bet perdendo só o investimento já feito; check-raise vencendo o pote mais a
aposta adversária; escolha sem conhecimento da mão escondida; atualização após raise; probabilidades
dos rivers somando1; royal flush vencendo em todos os rivers elegíveis; limites de raise e all-in.

## Lacunas restantes

Árvore completa de flop/turn com apostas futuras, reraises e multiway; estratégia adversária
calibrada; verificação contra soluções independentes; ICM/rake; integração ao simulador interativo
existente com manutenção completa do pote, stacks e ações manuais. Os novos testes não certificam
qualidade estratégica em cenários reais ou resolução completa do pós-flop.
