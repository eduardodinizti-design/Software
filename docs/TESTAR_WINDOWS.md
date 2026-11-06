# Teste integrado no Windows

Atualize a branch fix/strict-client-capture no GitHub Desktop (Fetch origin / Pull origin). Abra CMD na pasta do repositorio. Use o mesmo Python e Tesseract dos testes anteriores.

1. `python testar_windows.py --listar`
2. Copie o HWND atual do PPPoker.
3. `python testar_windows.py --hwnd NUMERO --cliques`

O programa mostra Hero, board, botoes e a lista numerada. Enter atualiza; q encerra. Digitar um numero solicita exatamente um clique no botao reconhecido. Sem --cliques, somente observa. Nenhuma imagem e gravada.

A janela e ativada e uma nova leitura verifica mesa, cartas, rotulo e valor. Uma captura final verifica pixels do botao, identidade e geometria; acima de 250 ms cancela. A janela precisa estar em primeiro plano e o ponto nao pode pertencer a outra janela. Alteracoes ou duvidas cancelam o clique. Nao mova janelas nem o mouse durante o envio.

Este e um executor manual de teste, nao um agente que decide jogadas. Bet/Raise pode abrir um painel: nao configura valores nem confirma automaticamente. O loop e interativo, nao continuo. A captura e o clique nao sao atomicos no Windows; ainda existe uma pequena janela de corrida, e elementos Unity internos podem compartilhar HWND. Comece em uma mesa de dinheiro ficticio.

Validacao: 28 testes focados passaram em Linux, cobrindo mudanca de identidade, geometria, valor/cartas, pixels, preselection e falha de captura. Envio real de cliques no PPPoker ainda precisa ser confirmado nesta sessao Windows; nao foi executado no laboratorio.
