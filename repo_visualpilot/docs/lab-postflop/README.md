# Motor experimental de comparação pós-flop

Implementação executável em `visualpilot/lab/postflop.py`, restrita ao laboratório offline.
Não depende de o usuário escolher uma resposta correta. Recebe cartas, board, range ponderado,
pote, stack efetivo e hipóteses de resposta; calcula e ordena o EV das alternativas.
Não está conectado ao coletor, ao painel ou à execução de ações.

## O que foi implementado

- Avaliador de mãos de sete cartas usando o melhor subconjunto de cinco; wheel e empates.
- Conversão das classes NVT em combos físicos (6 pares, 4 suited, 12 offsuit antes de bloqueadores).
- Frequência da ação pré-flop como peso de cada combo, exclusão de outOfRange e bloqueadores.
- Equidade exata no river; Monte Carlo reproduzível no flop/turn, com erro padrão amostral.
- Comparação fold/call ou check/apostas de diferentes tamanhos.
- Para apostas, reponderação do range que continua conforme a resposta de cada combo.
- Registro de entradas, seed, hash, resultados e hipóteses. O runner acrescenta a origem NVT.

## Convenção de EV

Valores em fichas/BB na mesma unidade de entrada; decisões medidas a partir do momento atual,
sem cobrar investimentos passados. `pot` é o pote atual incluindo uma aposta adversária já feita.
`stack` é o máximo adicional efetivo que o Hero pode investir. Sem rake/ICM.

- Fold: 0.
- Call: equity × (pot + call) − call.
- Check: equity × pot, supondo showdown sem apostas futuras.
- Bet: fold_probability × pot + (1 − fold_probability) ×
  [equity_contra_range_que_paga × (pot + 2 × bet) − bet].

O modelo de aposta não permite raise adversário. Essa restrição é particularmente importante
antes do river: não é um solver de árvore, nem uma estimativa completa de realização de equidade.
Erro padrão amostral não mede erro dessas hipóteses; pequenas diferenças de EV no Monte Carlo
não demonstram superioridade. `best_under_model` significa apenas maior estimativa nesse modelo.

## Experimentos executados

Comando na raiz do projeto:

```sh
.venv/bin/python -m tools.run_postflop_experiments
.venv/bin/python -m unittest discover -s tests
```

Cinco situações, cada uma com três hipóteses de resposta: top pair no flop seco, flush draw,
flush completado no turn, draw perdido no river e full house no river. Compara check e apostas
1/3, 2/3 e pote; 400 amostras nas ruas não terminais, enumeração dos combos no river.

O range é o open-raise BTN chipEV 25BB do trecho autêntico NVT. O contexto experimental de pote
6/stack20 é configurado, não inferido do arquivo. O range pré-flop é mantido sem condicionamento
por apostas anteriores: são testes independentes de sensibilidade, não mãos completas homologadas.
As probabilidades uniformes de fold de 0%, 35%, 70% são hipóteses artificiais para testar cálculos,
não comportamento aprendido de adversários. Nenhuma estratégia pós-flop foi atribuída ao NVT.

Resultado instrutivo: com Ah Jh em Kh 8h 2c 3d 9s, o modelo selecionou check quando todos pagam,
e aposta de 1/3 quando o modelo permite 35% de folds. Isso demonstra sensibilidade ao adversário,
não prova que apostar nessa situação real seja correto. Um teste separado usa respostas diferentes
por combo: mãos piores foldam, melhores pagam; a equidade condicional cai e check supera aposta.

## Evidências e limites

- `experiments.json`: 15 comparações completas, com hipóteses e proveniência.
- `experiments.log`: resultados resumidos.
- `evaluator-audit.json`: contagens das categorias em todas as 2.598.960 mãos de cinco cartas,
  comparadas às contagens combinatórias conhecidas. Isso não valida sozinho todos os desempates.
- `full-suite.log`: resultado da suíte unificada.
- Sete testes novos incluem categorias, wheel, empate, pesos, bloqueadores, EV,
  condicionamento por resposta, reprodutibilidade e importação NVT.

Próximos componentes ainda necessários: histórico de mão e atualização bayesiana dos ranges,
árvore de ações com raises e apostas futuras, estratégia adversária aprendida/calibrada,
comparação com soluções independentes, modelo de ICM e integração visual.
Não há alegação de GTO, de engine pós-flop completa ou de homologação Windows.
