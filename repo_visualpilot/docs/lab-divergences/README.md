# Investigação das divergências da rodada ampliada

A fila original foi retomada por mais até seis horas, preservando código, configuração e checkpoints. Os experimentos abaixo são separados da fila: `python -m tools.diagnose_divergences`. Eles não alteram os resultados anteriores nem aprovam automaticamente os demais casos.

Na fotografia dos primeiros 1.543 candidatos, 195 casos permaneceram fora da tolerância numérica. Desses, 22 tiveram pelo menos uma escolha incorreta de all-in nas três sementes finais. O problema de all-in não explica sozinho as 195 divergências. Contagens por ação em `failure-breakdown.json` contam sementes e podem exceder o número de casos.

O refinamento da fila aumenta `chance_samples` (cartas públicas futuras), mas mantém `all_in_samples=500` (showdowns em all-in). Portanto, aumentar o primeiro orçamento não reduz diretamente o erro do segundo. Essa distinção foi identificada na inspeção do código e motivou um experimento controlado.

Dois casos de alta divergência são repetidos em três sementes, mantendo os mesmos ranges, modelo e sizings:

- baseline: 24 amostras de cartas públicas / 500 showdowns;
- somente mais cartas públicas: 96 / 500;
- somente mais showdowns: 24 / 5.000.

O julgamento usa os EVs da referência exata já salva, com tolerância de 0,03 BB. `results.json` contém resultados por orçamento; os arquivos individuais preservam ações, EVs, sementes e tempos. Tempos são medidos com a fila executando simultaneamente e não constituem benchmark isolado.

Mesmo uma melhora nesses dois casos não comprova correção para todos os casos, nem validade estratégica do modelo sintético. O próximo passo depende do resultado: ampliar a precisão de all-in resolve apenas parte das fontes de erro; escolhas entre sizings próximos também exigem investigação.

## Resultado: 18 buscas concluídas

| Caso | 24 cartas / 500 showdowns | 96 cartas / 500 showdowns | 24 cartas / 5.000 showdowns |
| --- | ---: | ---: | ---: |
| 55, SB × BB, monotone | 0,890120 BB | 0,890120 BB | 0 BB |
| ATo, BB × SB, conectado | 0,763826 BB | 0,073913 BB | 0 BB |

Os valores são a pior perda de EV das escolhas de três sementes, avaliada na referência exata do modelo, não erro absoluto das estimativas de EV. A tolerância é 0,03 BB. Com 5.000 showdowns os dois casos passaram nas três sementes. Os EVs estimados ainda podem divergir da referência; acertar a ação não significa estimativa exata.

A evidência apoia refinar também o orçamento de showdown, em vez de somente o de cartas públicas. Não foi alterado o executor ativo: os resultados antigos e o lote retomado permanecem comparáveis. Antes de promover a configuração, repetir o teste no conjunto dos 22 casos com all-in incorreto e depois nos outros tipos de divergência. Essa amostra de dois casos foi selecionada pelo erro alto, portanto não estima a taxa geral de melhoria.
