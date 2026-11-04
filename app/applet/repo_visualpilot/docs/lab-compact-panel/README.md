# Painel compacto v1

A prévia deixou de usar `width='stretch'`. Miniaturas têm largura máxima ajustável de 120, 150 (padrão), 190 ou 230 pixels, preservando a proporção e reduzindo para caber na coluna. A captura, o OCR e as evidências originais não foram redimensionados por esta alteração.

Modo automático: uma/duas mesas usam duas colunas; quatro mesas usam 2×2; três/cinco/seis usam três colunas, até 3×2. Uma mesa não ocupa toda a largura. Em telas estreitas, as colunas se empilham. O menu lateral permite escolher duas ou três mesas por linha e tamanho da miniatura.

Cada cartão exibe miniatura e resumo lado a lado, com alertas de imagem/leitura desatualizada, cartas, board, etapa, botões e marcação manual. Pote, stack, ações dos jogadores, qualidade e evidências ficam recolhidos. Ampliar abre uma janela de inspeção com imagem de 400 pixels (limitada pela tela), em vez de esticar o cartão. A inspeção usa a prévia recebida, não aumenta sua resolução original.

## Atualização no notebook sem recompilar

Clique Parar coleta antes de atualizar. Baixe e extraia `Atualizar_Painel_Compacto.zip`, abra `ATUALIZAR_PAINEL.bat` e selecione a pasta onde estão `VisualPilot_Central.exe` e `_internal`.

O script confere o hash do painel, encerra somente processos da Central cujo executável está nessa pasta, salva backup e substitui apenas `_internal/visualpilot/viz/app.py`. Atualiza o hash correspondente no manifesto quando presente e reabre a Central. Não altera IP/porta, Coletor, dependências, registros ou código compilado do motor. Não exige executar o build.

O título identifica `painel compacto v1`. O identificador do launcher continua o anterior, pois seu executável não mudou. Para desfazer, restaurar o backup de app.py e do manifesto criado na mesma pasta, com a Central fechada.

## Validação

Três testes do painel Streamlit: leitura de river, alerta de desatualização e marcação manual. Auditoria Chromium com seis prévias de fixture, ampliação, quatro mesas em 2×2 e largura móvel de 390 pixels. Os cenários visuais são controlados: essa auditoria não comprova OCR/captura simultânea de seis mesas.

O pacote foi conferido por hash. BAT/PowerShell não executados em Windows neste laboratório Linux. O mecanismo depende do app.py distribuído como arquivo pelo spec atual, conferido no repositório. A execução física e a aparência final no notebook ainda precisam ser verificadas.

Compatibilidade: após relato de BUILD_ID ausente em outra pasta, o painel deixou de exigir essa constante. Se a sessão não possui o monitor necessário, mostra uma mensagem explícita de incompatibilidade sem traceback. O atualizador agora exige manifesto central-live-20261030-r2 antes de modificar qualquer arquivo. Teste de regressão remove BUILD_ID e monitor; quatro testes do painel passaram. Não se afirma que isso modernize o motor de um executável antigo; deve-se abrir o pacote completo R2 já validado.
