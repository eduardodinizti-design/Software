# Gabarito da GRADE DE CLUBES do PPPoker (seletor de clube)

Captura real do lobby PPPoker (client v228), janela do app (NÃO uma mesa), em
17/11/2026. Recorte da janela esquerda do desktop ao vivo (capturado em 5760×2160,
DPI 1.5×; recorte x[1900:2660] y[15:1430] -> 760×1415).

É a tela onde o usuário TROCA DE CLUBE: uma grade de 2 colunas de tiles, cada um
com o nome do clube embaixo (o usuário clica no NOME). Serve para calibrar/validar
o leitor da grade (`club_grid`) e o executor de troca (`do_switch` do club_switcher).

- `club-grid-live-1.png` — 4 clubes visíveis + menu de contexto "Trocar exibição /
  Pesquisar" aberto no canto inferior direito.

## Ground truth (nomes como o OCR lê, com ruído real)
Tiles visíveis (ordem de leitura: TL, TR, BL, BR):
- TL: "AK AMAKHA cl..."   (nome TRUNCADO pelo tile; nome completo só aparece DENTRO do clube)
- TR: ") Karekas Yellow"   (o ")" é o ícone do clube coladinho; aparar ruído à esquerda)
- BL: "LALINHA\ufffd"       (os emojis ♦ ♥ viram caractere inválido; aparar)
- BR: ") AK Amakha Club"

## Constraints de domínio (do operador, 17/11)
- A GRADE ROLA: há mais clubes do que cabe na tela (arrastar com o mouse, click-and-hold).
- A ORDEM DOS CLUBES MUDA entre aberturas -> NÃO confiar em posição fixa; sempre
  RE-LER após rolar, e buscar pelo NOME.
- Nomes truncam ("...") e há clubes parecidos ("AK AMAKHA cl..." vs "AK Amakha Club")
  -> o match na grade é best-effort; a VERIFICAÇÃO é ler o nome COMPLETO dentro do
  clube (ver tests/fixtures/lobby_live, caixa "Karekas Yellow / ID do clube: ...").

## OCR
Lê com `table_reading.pipeline.configure_ocr()` + `ocr_runtime.image_to_string`
(Tesseract 5.5, `C:\Program Files\Tesseract-OCR`). Sem Tesseract no PATH, os testes
de OCR pulam (convenção do repo).
