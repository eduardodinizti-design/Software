# Matriz ampliada: boards, ranges e posição

A rodada amplia o contexto estratégico no laboratório. Não altera inscrições, limites de buy-in,
automação no cliente nem o modelo adversário sintético. Uma busca exata é referência matemática
dentro do modelo/árvore, não referência GTO independente.

## Cobertura planejada antes das execuções

Seis texturas: top pair com overcard no turn, board pareado, draw de flush, flop monotone,
board conectado e quatro cartas do mesmo naipe. Mão do Hero J♥T♥ em todas as células: isto
permite comparar contextos, mas não cobre todas as169classes de mãos.

Cinco confrontos coerentes de posições e ações pré-flop:

| Contexto | Hero | Range adversário utilizado |
| --- | --- | --- |
| BB × BTN | OOP | open-raise BTN |
| BTN × BB | IP | call BB contra BTN |
| BB × CO | OOP | open-raise CO |
| BB × SB | IP | open-raise SB |
| SB × BB | OOP | call BB contra SB |

Os seis nós NVT necessários foram extraídos sem alterar frequências do pacote validado enviado.
`tests/fixtures/nvt_position_excerpt.json` registra SHA256 do arquivo original, versão do motor,
nós e ações. A frequência de chegada de JTs pela ação do Hero também é verificada; todas positivas.
Combos bloqueados pelas cartas são removidos antes de calcular.

Nos cenários IP, o range é condicionado ao check observado antes da ação do Hero conforme o
modelo sintético. Esse detalhe é registrado na proveniência, sem tratar check como informação nula.
OOP continua agindo primeiro e IP depois do adversário nas ruas seguintes.

## Experimentos

- Turn:6boards ×5contextos =30cenários. Uma referência exata e três buscas aproximadas por cenário.
- Total turn:30referências enumeradas +90buscas com seis cartas amostradas e estratificação.
- Flop:6boards ×2contextos (BB/BTN e BTN/BB) ×3seeds =36buscas em12cenários.
- Flop usa grade menor (1/3, pote, all-in), uma carta pública por amostra e200showdowns no all-in.
  Não há referência exata do flop nessa rodada; concordância não comprova qualidade estratégica.

Potes/stacks são controlados (turn10/16BB; flop6/18BB). Não há reconstrução de toda a mão ou de
apostas anteriores além das condições explicitadas. São testes heads-up em chipEV, sem rake/ICM.
O modelo size-sensitive-v1/agressividade0.5 permanece sintético.

## Uma falha de critério identificada

A concordância de três seeds não basta para aceitar uma decisão. Em BTN×BB no board monotone,
as três buscas escolheram bet3.33 enquanto a referência exata preferiu check. A perda dentro do
modelo foi0.077282BB, acima da tolerância laboratorial0.03BB.

`numerical_audit.py` acrescenta uma avaliação separada: compara o EV de referência de cada ação
escolhida com o melhor EV de referência. Assim pode rejeitar três escolhas iguais incorretas e
aceitar escolhas diferentes que estejam próximas em EV. Mesmo um resultado aceito numericamente
permanece com `strategically_validated=False`.

## Reprodução e evidências

```sh
.venv/bin/python -m tools.run_position_matrix
.venv/bin/python -m tools.audit_position_matrix
.venv/bin/python -m tools.build_position_report
.venv/bin/python -m unittest tests.test_scenario_matrix tests.test_numerical_audit -v
.venv/bin/python -m unittest discover -s tests
```

`turn-summary.json`: ações, perdas, erros e tempos individuais.
`*-turn.json.gz`: entrada/proveniência, árvore exata e três buscas de cada célula.
`flop-runs.json.gz`: buscas do flop com seus limites explícitos.
`summary.json`: cobertura efetivamente executada e métricas agregadas.
`numerical-audit.json`: casos aceitos/refinamento e lista das maiores divergências.
`targeted.log`, `audit-tests.log`, `full-suite.log`: testes de software.

O relatório HTML portátil mostra a matriz, seus erros e a comparação de ações. Não executa novas
buscas, não controla mesas e não exige Python no computador do usuário.

## Resultado final

Concluídas156buscas:30referências exatas de turn,90aproximações de turn e36buscas de flop.
No turn,62/90ações ficaram a até0.03BB da melhor referência. A perda média da decisão foi0.092509BB,
com pior caso0.796552BB. Considerando as três execuções de cada célula,14/30passaram pelo critério
numérico e16/30exigem refinamento. Uma célula teve três escolhas iguais fora da tolerância.

No flop,7/12cenários concordaram nas três seeds;5/12não concordaram. Não há referência exata
para validar as escolhas do flop nessa rodada. Concordância não é tratada como aprovação.

Suíte final: **252 testes, 249 aprovados, 3 ignorados, nenhuma falha**. A matriz HTML foi testada
em Chromium:30células acessíveis,14verdes/16amarelas, sem erro JavaScript e sem overflow externo
em390px. Tabelas largas possuem rolagem interna.

O resultado mostra que as melhorias observadas no conjunto anterior não autorizavam generalização.
Prioridade seguinte: aumentar precisão nos boards pareados e de quatro cartas do mesmo naipe,
ampliar mãos do Hero e variar modelos adversários antes de qualquer conclusão estratégica.
