# Uma mesa: tamanho da captura e ciclo da Central

## Defeito corrigido no transmissor

A captura base 835×1485 escalada a 125% e 150% excedia os limites do envelope
(altura 1800, largura 1200). FrameSender recusava as imagens antes do envio.
prepare_capture agora reduz a janela inteira para largura 755 antes da
codificação, preservando a proporção e sem recortar bordas. É a largura já
usada pelo runtime; limites do protocolo permanecem intactos.

before.log reproduz a falha. O teste CaptureSizeTests valida envio e recepção
em 100%, 125% e 150%, com a mesma identidade e proporção.

## Leitura óptica: resultados separados do transporte

O teste TCP/OCR foi ampliado com river em 125% e 150%. São redimensionamentos
sintéticos de imagens, não a escala DPI real do Windows. Em 125%, Hero e board
foram reconhecidos. Em 150%, o board foi reconhecido, mas o Hero foi rejeitado:
o coração de Th teve semelhança 0.642, abaixo do limite 0.68. O log after.log
preserva essa falha. Não reduzimos o limite.

O cenário 150% testa agora a rejeição segura (Hero pendente), explicitamente
não conta como reconhecimento aprovado nessa escala. O objetivo é garantir
que o defeito conhecido não vire cartas inventadas. Ainda é necessário resolver
esse caso com evidência adicional, antes de homologar a variação de tamanho.

## Encerrar e reiniciar

RemoteLifecycleTests usa o controlador real, receptor TCP real e runtime real.
Inicia e para duas sessões na mesma porta, verifica encerramento da thread,
porta liberada e pastas distintas com diário e métricas. Não alimenta cartas
nesse teste de ciclo de vida; o teste integrado separado cobre leituras.
Resultado em lifecycle.log. Não usa mocks de processo/runtime.

Não houve teste físico do Windows, captura de monitor nem entrega de exe.

Suíte final: 159 testes executados, sem falhas, 3 skips. Esse resultado inclui
a rejeição esperada de Hero no cenário 150%, não aprovação de sua leitura.
