# Cartas comunitárias: módulo experimental

Habilitar com --board na leitura única ou contínua. Exemplo de futura rodada Windows:
`python ler_mesas.py --hwnd 264430 --continuo --intervalo 1 --botoes --board`
Não é preciso executar agora. O HWND precisa ser o atual.

Localiza contornos de faces na faixa central relativa ao recorte da mesa azul, exige 3/4/5 retângulos alinhados e espaçados. Número e naipe são lidos separadamente. Só apresenta FLOP/TURN/RIVER quando todas as cartas são identificadas, sem duplicatas internas nem conflito com as cartas Hero já reconhecidas. Não atribui PREFLOP automaticamente a ausência de detecção: poderia ser falha visual. Sem GTO, cliques ou confirmação de vez do Hero.

Medições em board_reading são chamadas ao módulo (detecção + OCR quando necessário), e não comprovam que Tesseract rodou em toda chamada. O módulo é opcional e acrescenta latência; até cinco cartas podem exigir múltiplas chamadas OCR. Não promete frequência de 1 Hz.

Laboratório: uma captura histórica real de flop, Jc/5d/3c, comparada com transcrição visual antes de executar OCR; sete regiões históricas sem cartas não enviadas ao OCR. É conjunto de desenvolvimento reutilizado e usado na calibração, não avaliação independente. Turn/river, fila incompleta, duplicatas e conflitos cobertos apenas por cenas sintéticas/OCR simulado. Registros: board-development-results.json. Exemplos recentes embutidos no chat não foram executados como PNGs originais.

Pendências acumuladas para uma rodada real:
1. Uma captura pré-flop: ausência de board deve permanecer não confirmada, sem cartas inventadas.
2. Flop, turn, river: comparar valores, naipes, quantidade e ordem esquerda-direita.
3. Fold/Check/Bet e Fold/Call/ Raise: comparar rótulos e valor.
4. Mesa sem ação e lobby: checar aceitação/rejeição e razões.
5. Movimento e tamanho operacional: nenhuma reutilização de board anterior.
6. Tempos finais com board habilitado. Salvar apenas evidência pontual de falha com --save (fora do modo contínuo).

As falhas de Hero 8h→3h e a limitação da mesa pequena continuam pendentes. O board reutiliza o leitor de ranks experimental, portanto também pode errar: não serve como validação de prontidão operacional.
