# Comparação controlada de amostragem de cartas

O foco permanece na inteligência da mesa. Grades, modalidades e faixas de buy-in discutidas
anteriormente são exemplos de planejamento, sem alterar a operação do laboratório.

## Hipótese e implementação

`chance_sampling.py` oferece amostragem estratificada: divide a distribuição acumulada de cartas
públicas em faixas de mesma probabilidade e sorteia um ponto em cada faixa. Mantém os pesos e
bloqueadores; não classifica cartas como favoráveis ao Hero para selecioná-las. `chance_method`
é registrado no resultado. O método aleatório anterior continua como padrão.

A estratificação não torna uma busca exata, não resolve o modelo do adversário e não elimina o
viés de maximizar valores estimados. Enumeração exata no turn continua disponível e independente
do método de amostragem. All-ins amostrados usam a mesma seed nas duas alternativas do experimento.

Uma proteção numérica impede que o arredondamento do último ponto selecione uma cauda com peso
zero. O teste cobre o maior valor possível do gerador antes de1. Essa condição não ocorreu nos
experimentos, cujos candidatos já excluem probabilidades zero.

## Desenho do teste

Três turns: draw de flush, flush completado, top pair. Range inicial do trecho NVT openBTN25BB,
modelo adversário sintético size-sensitive-v1, agressividade0.5, pote10BB/stack16BB.
Cada cenário possui referência enumerada exata dentro da árvore/modelo, incluindo os all-ins.

Comparação pareada: dois métodos × duas quantidades de cartas (3/6) × cinco seeds × três cenários
=60buscas. Todos os resultados, incluindo pioras, entram nos agregados. Não houve escolha de seeds
após observar o resultado. Não houve ajuste de estratégia pelo lucro/prejuízo de mãos jogadas.

“Perda de decisão” significa EV da melhor ação na referência menos EV da ação escolhida pela
busca aproximada, ambos avaliados na referência exata. Isso não é prejuízo financeiro observado.
“RMSE” mede erro das estimativas de EV das ações; concordância de rótulo da ação não basta.

| Cartas por amostra | Método | Erro médio RMSE (BB) | Perda média da decisão (BB) | Decisões a até0,03BB da melhor |
| ---: | --- | ---: | ---: | ---: |
|3|Aleatório|0.722429|0.352330|7/15|
|3|Estratificado|0.572516|0.080637|11/15|
|6|Aleatório|0.380712|0.044516|12/15|
|6|Estratificado|0.342648|0.011882|13/15|

Com6cartas, os tempos agregados foram15.68s e15.91s respectivamente no ambiente compartilhado.
Não há alegação de superioridade universal: são apenas três cenários e um modelo sintético.
Por isso a nova técnica é uma opção experimental; o padrão anterior não foi substituído.

## Flop e limites

Também foram executadas seis buscas de flop (três seeds por método) para Ah Jh em Kh 8h 2c.
Não existe referência exata desse flop neste experimento. `flop-summary.json` informa apenas
estabilidade entre seeds, não qualidade estratégica. Os rivers também são amostrados nesse
comparativo, diferentemente do experimento anterior de enumeração completa após o turn.
Resultados não devem ser comparados como se tivessem a mesma precisão ou custo dos testes anteriores.

## Reprodução e evidências

```sh
.venv/bin/python -m tools.run_sampling_lab
.venv/bin/python -m unittest tests.test_chance_sampling -v
.venv/bin/python -m unittest discover -s tests
```

`paired-results.json`: resultados individuais, erros e custos.
`references.json.gz`: três árvores exatas e origem do range.
`summary.json`: agregados e decisão explícita de não alterar o padrão.
`flop-runs.json.gz` e `flop-summary.json`: rastros e consistência das escolhas no flop.
`targeted.log` e `full-suite.log`: validações de software.

Ainda faltam referências estratégicas independentes, ampliação de boards/ranges/posições e teste
de estratégias em amostras separadas. Nenhuma decisão deste módulo é enviada ao aplicativo de poker.

## Resultado final desta rodada

Foram concluídas60buscas comparativas de turn, três referências exatas e seis buscas de flop.
No flop, o método aleatório escolheu bet4/check/check; o estratificado escolheu bet2/check/check.
Ambos continuam instáveis: não foi consolidada uma ação para esse cenário.

Suíte unificada: **245 testes, 242 aprovados e 3 ignorados, nenhuma falha**. Os20testes direcionados
foram executados novamente após a proteção contra arredondamento na cauda de probabilidade zero.
