# Uma mesa: interrupção e recuperação — 29/10/2026

## Objetivos e resultado

1. Interromper o envio sem encerrar a Central: cartas antigas devem deixar de
   aparecer como leitura atual. Defeito reproduzido em `before.log` com o
   controlador anterior: não havia expiração no painel.
2. Corrigir a apresentação: depois de cinco segundos da observação, o controlador
   troca o snapshot exibido por campos pendentes e remove confirmações. A tela
   mostra idade da leitura e aviso. A atualização visual ocorre no próximo ciclo
   do painel (intervalo de um segundo). Não se afirma que a causa é necessariamente
   rede: OCR travado também pode causar ausência de leitura recente.
3. Reconectar sem reiniciar a Central, alternando 5c/2s → Th/4d → 5c/2s:
   três ciclos passaram com servidor TCP, OCR e controlador reais. Entre ciclos,
   o socket é fechado e o teste espera 5,3 s reais antes de verificar expiração.
4. Preservar o diário: teste exige uma identidade de mesa, sequência correta das
   mãos parciais no JSONL, arquivo de métricas e zero erros de processamento.
5. Verificar a interface: Streamlit AppTest confirma aviso e remoção das cartas
   antigas, além do teste existente de exibição de river.

## Evidências

- `before.log`: regressão falha contra o controlador do commit anterior.
- `targeted.log`: primeira execução dos dois testes de recuperação, 21,820 s.
  Leituras completas nos três ciclos em 2,367 / 1,736 / 1,543 s.
- `full-suite.log`: 164 testes executados em 59,618 s, sem falhas, 3 skips,
  após incluir verificações do diário e da UI. Na repetição integrada, os três
  ciclos entregaram leituras completas em 1,810 / 1,321 / 1,452 s.

O histórico gravado não é apagado nem alterado pela expiração visual. A expiração
é do painel, não um novo registro de desconexão no diário. Uma observação nova
reativa a exibição automaticamente.

## Limites

Teste em loopback no Linux com imagens reais gravadas; não mede Wi-Fi físico,
descoberta de janelas nem execução do binário Windows. Reconexão conserva a
identidade de sessão e a sequência crescente, como faz o transmissor ao perder
um socket. Reiniciar o executável do coletor com outra identidade de sessão é
outro cenário e não está homologado por este teste. Não houve build de `.exe`.
