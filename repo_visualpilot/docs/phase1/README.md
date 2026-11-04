# Fase 1 — captura, calibração e clique no lobby

As entregas seguem a ordem solicitada pelo usuário, uma por vez. O código e as
evidências experimentais anteriores serão aproveitados, sem tratar aprovação em
imagens gravadas como homologação no PC.

| Módulo | Entrega | Estado nesta rodada |
|---|---|---|
| 1 | Captura PNG configurável + metadados + orientação do retângulo | Captura básica validada em cinco imagens Windows; ver revisão abaixo |
| 2 | Segmentação visual dos cartões + mapa das regiões | Próxima entrega; ainda não implementada nesta fase |
| 3 | OCR por cartão + texto bruto e confiança | Entrega após validação do módulo 2 |
| 4 | Conversão das coordenadas da captura para o desktop | Entrega após validação do módulo 3 |
| 5 | Clique no cartão selecionado + verificação da próxima tela | Entrega após validação do módulo 4 |

## Módulo 1

[Guia completo de instalação, uso e validação](../../delivery/lobby_capture/LEIA_ME.md).
Implementação: `visualpilot/pppoker/lobby_capture.py`, reutilizando `ScreenCapture`
e a configuração DPI existentes. Não altera captura/transporte do Coletor atual.

[Nove testes](module1/tests.log) passaram. O [ensaio MSS no Linux](module1/desktop-capture/capture.json)
gravou a região `(20, 30, 640, 480)` sem redimensionamento; o desktop estava vazio
e o PNG foi marcado como uniforme. O ensaio não é prova visual do lobby Windows.

Pacote de código Python: gerado com
`python tools/package_lobby_capture.py --output /caminho/Modulo1_CapturaLobby.zip`.
Inclui somente captura e dependências diretas, sem OCR/Streamlit. As dependências
são instaladas por `preparar.cmd`; não é um EXE nem pacote offline.

O [ensaio do pacote extraído](module1/package-validation.json) verificou os nove
arquivos do manifesto, importação a partir da pasta extraída, listagem de monitores,
captura PNG/JSON de 640×480 e saída com erro para região inválida. Foi executado
no Linux com dependências já instaladas; não valida instalação limpa ou scripts
`.cmd` no Windows. ZIP entregue em
`/workspace/entregas/VisualPilot_Modulo1_CapturaLobby.zip`.

## Referências novas e organização de mesas

O segundo `imagens.rar` contém uma captura de 3756×2128 com lobby e duas mesas,
mais uma barra de 1050×154 com botões MTT NLH, acesso ao lobby e ícone de grade.
[Manifesto](module1/uploaded-references.json). As imagens foram inspecionadas;
não se presumiu que a origem da captura coincide com a origem do desktop.

Organizar mesas, abrir e minimizar o lobby fica como integração posterior. Será
necessário localizar os controles e verificar o efeito, incluindo a preservação
da identidade das mesas após movimento. Nenhuma coordenada estimada nem rotina
de `LayoutManager` foi ativada nesta entrega. Para o Módulo 1, o usuário abre e
posiciona o lobby manualmente e o mantém visível durante a captura.

## Revisão após capturas do usuário — 31/10/2026

Cinco capturas Windows 3840×2160 conferidas com hashes correspondentes; tempos
de 0,219 a 0,625 s. Captura básica aprovada neste ambiente, com cartão superior
parcialmente cortado na lista. Outras escalas DPI, OCR automático, cliques e
operação por 14 horas não foram validados por este ensaio.

[Dados da revisão](module1/user-repeat-review.json) ·
[Estado consolidado e regras atuais](../ESTADO_ATUAL_EXPORTACAO.md).
