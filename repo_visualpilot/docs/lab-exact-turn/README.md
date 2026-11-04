# Refinamento de precisão no laboratório

## Mudança implementada

`SearchConfig(exact_turn=True)` faz o motor enumerar todos os rivers elegíveis, incluindo
showdowns após all-in no turn. Cada combo adversário tem44 rivers possíveis; suas probabilidades
e os pesos do range são preservados. Vitória e empate são contabilizados separadamente para PKO.
O prêmio de eliminação não é atribuído a empates.

Foi acrescentado cache de equidade por combo/turn e o cache de ranking usa as cartas em ordem
canônica. A mesma mão não precisa ser reavaliada por aparecer numa ordem diferente. A enumeração
não depende da seed; o flop ainda pode usar amostragem dos turns e dos all-ins no flop. O relatório
expõe `exact_under_model` e `requires_independent_seed_validation`, sem declarar exatidão indevida.

A opção não altera o padrão anterior nem liga decisões a captura ou cliques. Continua laboratório
heads-up, uma única elevação por rua, contra um modelo adversário sintético. Precisão numérica
não equivale a estratégia GTO ou correção do modelo de oponente.

## Caso de turn que estava pendente

Hero Ah Jh, board Kh 8h 2c 3d, pote10BB, stack efetivo16BB. Range inicial BTN do trecho autêntico
NVT; sem condicionamento por apostas anteriores neste cenário independente. Modelo sintético
size-sensitive-v1, agressividade0.5. Todos os rivers e ações da árvore foram calculados.

| Ação atual | EV incremental BB |
| --- | ---: |
| Check |8.463668|
| Bet3.33 |9.205682|
| Bet6.67 |9.179312|
| Bet10 |9.067593|
| All-in16 |8.147384|

Seeds11,23,47 retornaram os mesmos EVs. Cada busca visitou9021nós, em aproximadamente7.6–8.6s
no ambiente desta execução, concorrendo parcialmente com outros testes. A diferença entre as
apostas3.33 e6.67 é somente0.026370BB; não constitui uma vantagem estratégica ampla.
A incerteza numérica deste cenário foi resolvida dentro do modelo, não a validação estratégica.

## Evidências

- `targeted.log`: testes de enumeração independente de payoffs com empates/PKO, invariância por
  seed, preservação do aviso de amostragem no flop, limite de orçamento e regressões anteriores.
- `full-suite.log`: suíte unificada, resultado final no próprio arquivo.
- `summary.json` e `experiments.log`: custo e comparações de três buscas do turn e três do flop.
- `turn_draw-*.json.gz`, `flop_draw-*.json.gz`: rastros reproduzíveis com entradas, fonte NVT,
  decisões, chance, caches e hashes.
- `model-sensitivity.json.gz`: alterações das hipóteses adversárias mantendo cálculo exato no turn.

```sh
.venv/bin/python -m tools.run_exact_turn_lab
.venv/bin/python -m tools.check_postflop_sensitivity
.venv/bin/python -m unittest tests.test_exact_turn -v
.venv/bin/python -m unittest discover -s tests
```

Não há aprendizado a partir de lucro/prejuízo realizado. A comparação usa valores esperados
sob hipóteses explícitas e mantém as versões anteriores disponíveis para inspeção.

## Otimização validada

O avaliador direto `hand_rank.py` substitui, apenas no planejador e no modelo sintético, a seleção
do melhor subconjunto entre21mãos de cinco cartas. O avaliador anterior permanece disponível como
referência. A validação em `evaluator-audit.json` comparou o ranking completo, incluindo desempates,
de todas as2.598.960mãos de cinco cartas e10.000amostras de sete cartas. Nenhuma divergência.
O benchmark isolado de CPU para10.000mãos de sete cartas ficou aproximadamente10vezes mais rápido.
Isso não é uma aceleração10vezes da busca inteira, que também atualiza ranges e percorre ações.

Na busca de flop seed11, os EVs foram preservados exatamente; o tempo passou de194.37s para120.87s.
As medições foram feitas no ambiente compartilhado, com concorrência de outros testes, e não
constituem benchmark de produção. O custo do flop continua alto para decisões ao vivo.

## Sensibilidade ao adversário

Mantendo a enumeração exata no turn e alterando somente a agressividade sintética:

| Hipótese adversária | Sizing escolhido | EV BB |
| --- | --- | ---: |
| agressividade0.25 | bet6.67 |9.383691|
| agressividade0.50 | bet3.33 |9.205682|
| agressividade0.75 | bet3.33 |9.153155|

Esses valores não comparam desempenho contra um mesmo adversário. Mostram que remover o ruído
numérico não resolve a incerteza estratégica sobre o comportamento do oponente.

Suíte final: **232 testes executados, 229 aprovados, 3 ignorados; nenhuma falha**.

## Conclusão das buscas completas

As seis buscas planejadas terminaram. `conclusions.json` verifica automaticamente a paridade dos
EVs antes/depois da otimização (diferença máxima0) e separa os resultados:

- Turn: três resultados idênticos; aproximadamente19.3s no total após otimização.
- Flop: uma busca escolheu bet4 e duas escolheram check; permanece pendente. Aproximadamente350.5s
  para as três buscas, com turns amostrados e rivers enumerados. Não há decisão consolidada liberada.

O relatório portátil `VisualPilot_Precisao_Posflop.zip` apresenta essas evidências sem instalação.
Foi verificado em Chromium, incluindo largura390px; não executa novas buscas ou ações em mesas.
