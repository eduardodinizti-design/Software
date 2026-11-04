# Etapa 2 — comprovação temporal desde antes da captura

**Resultado no laboratório Linux: aprovado nos cenários documentados.**
**Windows: correção aprovada na execução nº 29, revisão `1660f73`.**
Ver `../lab-windows-diagnostics/README.md` para causa, reprodução e comprovação.
Auditoria do Coletor empacotado em `../lab-packaged-collector/README.md`.
A revisão posterior `17d289d` falhou no prazo do cenário de janela a 150%, antes
da verificação do Coletor empacotado; investigação em `../lab-ocr-cpu-budget/README.md`.
A execução corrigida `acd1351` ficou verde, conforme confirmação textual do usuário,
incluindo a verificação obrigatória do Coletor empacotado. Resta validar o fluxo
entre os dois computadores físicos; roteiro em `../VALIDACAO_DOIS_COMPUTADORES.md`.
Não houve instalação nos computadores do usuário nem aprovação das etapas 1, 3–5.

## Lacuna fechada

O receptor anterior aceitava uma imagem sem comprovar a idade anterior à sua chegada.
O teste de regressão `before.log` reproduz isso. O protocolo v2 passa a exigir:

1. A Central emite um ticket de uso único, vinculado à conexão, e registra o instante
   em seu relógio monotônico.
2. O Coletor recebe esse ticket **antes** de chamar a captura da tela.
3. O quadro devolve o ticket. A Central verifica identidade, uso único e prazo,
   inclusive depois de decodificar a imagem.
4. O instante original acompanha fila, OCR e publicação. Chegar à Central não zera
   a idade. O limite total é de cinco segundos, desde a emissão do ticket.

Se a captura acontece depois da emissão, sua idade real é menor ou igual ao tempo
medido desde essa emissão. Assim, publicação com esse tempo <= 5 s garante o limite
no contrato do coletor. É um **limite superior conservador**, não medição exata da
latência de rede. Espera entre quadros e envio do ticket também consomem o orçamento.
Não depende do relógio civil do notebook estar sincronizado com o PC.

A função real de coleta agora executa `before_capture` antes de `grab`; sem permissão
não captura, e `send` não transmite sem a permissão correspondente. Falha no envio
não provoca reenvio do quadro antigo depois de reconectar.

## Evidências

- `after.log`: **15 testes de transporte** (tickets, ordem de captura, TCP real e
  aviso de incompatibilidade).
- `runtime-deadline.log`: **17 testes de atualização**, incluindo transporte de
  quatro segundos + OCR de 1,2 segundo: resultado rejeitado pelo prazo conjunto.
- `latest/status.json` e `latest/tests.log`: **32 testes direcionados aprovados**,
  com horários, PID, identificação da execução e hashes das fontes testadas.
- `pipeline.log`: TCP e OCR reais com capturas gravadas, passando por troca de mão,
  alteração apenas do board, flop, turn, river e escalas de janela. O teste exige
  comprovação temporal e limite <= 5 s nas leituras publicadas.
- `full-regression.log`: **310 testes executados, nenhuma falha e três omissões**, em 119,191 s.
  As omissões são fixtures antigas ausentes, não aprovações implícitas.
- `browser/browser.json`: Chromium real, TCP e OCR; zero erros de navegador ou de
  envio, sem transbordamento horizontal no celular, marcação manual registrada e
  aviso de congelamento observado após interromper o envio.
- `browser/central-live.png`, `central-mobile.png`, `central-frozen.png`: evidência visual.

Foram exercitados: ticket vencido, reaproveitado, de outra conexão; atraso no socket;
vencimento durante decodificação; relógio civil deslocado; perda de envio; captura
impedida por falta de permissão; protocolo antigo; prazo acumulado até o OCR;
reconexão, troca de sessão e descarte de resultados de gerações anteriores.

Dois testes antigos de identidade do coletor exercitam explicitamente o modo legado
para preservar sua finalidade. Os testes TCP integrados e o receptor normal usam v2.

## Compatibilidade e identificação

Versão da Central: `central-live-20261030-r3-temporal-v2`.
Coletor e Central precisam ser atualizados juntos. O receptor é estrito por padrão:
coletor antigo é recusado e o painel explica a incompatibilidade, em vez de apenas
ficar aguardando imagens. O aviso desaparece após uma captura comprovada.

O modo opcional `allow_legacy_frames=true` serve somente à observação de compatibilidade:
identifica a idade como não comprovada e a ponte de estratégia não considera essa
observação atual. Não é necessário nem recomendado para validar o novo protocolo.

Ao gerar o pacote Windows, o manifesto identifica protocolo 2 e a necessidade de
coletor correspondente. A pasta interna da Central é `VisualPilot_Central_Temporal_V2`,
separada de `VisualPilot_Central_R2`. Nenhum novo executável Windows foi gerado aqui.

## Limites da comprovação

- O contrato pressupõe o coletor que chama a captura após o ticket. Não é prova
  criptográfica contra um cliente malicioso que substitua os pixels.
- O ticket não autentica o cliente nem criptografa a rede; essa revisão de segurança
  continua separada, como combinado.
- Driver que devolva imagem congelada e tratamento de suspensão/retomada das máquinas
  pertencem à etapa 3. O limite descrito pressupõe continuidade do relógio monotônico.
- A precisão das cartas e regiões continua dependendo da etapa 1. Os testes integrados
  usaram as fixtures gravadas já existentes, não validam todo o novo baralho.
- Foram usados Linux, sockets reais de loopback, OCR real e navegador real. Isso não
  é execução nos dois computadores Windows físicos do usuário.
- A consulta via GitHub API retornou `Forbidden`. Posteriormente o usuário forneceu
  o log da execução 41138441716: três falhas na contagem de parciais após a primeira
  leitura textual demorada. A correção e reprodução estão no relatório vinculado
  acima. Uma imagem posterior confirmou sucesso da execução nº 29 (`1660f73`).
  Esse job verificava o executável da Central, mas não abria o Coletor empacotado;
  a prova adicional desse componente está documentada no relatório da auditoria.

## Reproduzir e acompanhar

```sh
python tools/check_freshness_lab.py --include-transport --output docs/lab-transport-freshness/latest
python -m unittest discover -s tests -v
```

`latest/status.json` é atualizado por teste e termina como `completed`. Isso significa
rodada encerrada, não processo contínuo em segundo plano. Os resultados desta revisão
não autorizam ações de jogo: `action_authorized` continua falso.
