# Correção da validação Windows — etapa 2

Execução de origem: [Windows laboratory 41138441716](https://github.com/eduardodinizti-design/VisualPilot/actions/runs/41138441716),
commit `d4d67c2`. O log fornecido pelo usuário registra 310 testes, três falhas e
três omissões, em 208,498 s. A geração de executáveis foi interrompida corretamente.
Os trechos relevantes estão em `reported-windows-failures.txt`.

## Causa reproduzida

Os três testes integrados exigiam exatamente uma publicação parcial por cenário.
No Windows, a primeira leitura completa chegou cerca de nove segundos após o início
do cenário; as cartas parciais já tinham sido publicadas. Ao vencer o prazo de uma
captura, o runtime descarta seu resultado textual e processa uma captura nova. Essa
nova geração pode publicar novamente as mesmas cartas, com origem e prazo próprios.

A contagem fixa confundia essa recuperação válida com publicação duplicada.
`reproduce-count-assumption.log` reproduz a falha com atraso controlado: geração 1,
sequência 1, instante 100; geração 2, sequência 2, instante 106,08. O texto da geração
1 é rejeitado como `expired_source`; somente a geração 2 publica leitura completa.
Esse registro é uma reprodução Linux da condição, não o histórico bruto do Windows.

## Correção e critérios preservados

- O teste passa a rastrear cada parcial até uma imagem realmente enviada, pela
  mesa, sessão, sequência e hash dos pixels, conferindo cartas, board e fase.
- Cada geração continua podendo publicar uma única parcial. Uma tentativa nova
  exige sequência, geração e instante de origem crescentes.
- Todos os cenários devem aparecer, em ordem, incluindo mudança apenas do board.
  Não se agrupa simplesmente pelo valor das cartas e não se ignora registro extra.
- Prazo de cinco segundos e comprovação do transporte continuam obrigatórios.
- Teste determinístico provoca vencimento após a parcial e exige descarte do texto
  antigo. Também injeta duplicação de geração, sequência antiga, imagem errada,
  sessão errada, ausência de comprovação e idade vencida; a validação deve rejeitá-los.

Nenhum limite de validade foi ampliado e nenhum dos três testes foi removido.
Não houve alteração do leitor ou do comportamento de publicação para satisfazer uma
contagem artificial.

## Diagnóstico de futuras execuções

`tools/run_windows_stage.py` preserva saída, erro, duração, plataforma e código de
saída de cada etapa em `diagnostics/`, antes de existir `dist/`. O workflow publica
esses registros mesmo em falha, no artefato `windows-laboratory-evidence`.
O pacote `windows-laboratory-candidate` só é publicado após sucesso das etapas.
O comando dos testes usa modo detalhado. Mensagens não ASCII e falhas reais de
subprocessos são verificadas por `test_windows_stage_log.py`.

A execução nº 29 da revisão `1660f73` foi concluída com sucesso no Windows, conforme
imagem do GitHub enviada pelo usuário. O job durou 7 min 12 s e os passos de teste,
geração, abertura da Central e publicação dos artefatos aparecem aprovados.
A imagem confirma o resultado do job; não fornece a contagem detalhada de testes.

## Evidências locais

- `targeted.log`: 18 testes de validade e publicação aprovados, incluindo a
  reprodução determinística do OCR vencido após a parcial.
- `full-regression.log`: 313 testes executados em 120,526 s; nenhuma falha e
  três omissões de imagens ausentes (duas variações e um teste completo).
- `real-ocr-delayed.log`: os três cenários afetados passaram em 81,290 s, com
  atraso real injetado, TCP real e OCR real. O tempo até a primeira leitura completa
  chegou a 11,074 s; cada leitura publicada continuou dentro de cinco segundos da
  sua captura de origem. Tempo de recuperação não é idade de um quadro publicado.
- `logger-self-test.log`: registro preserva Unicode, stderr, traceback e código de
  saída sem transformar uma falha em sucesso.

Reprodução com atraso real e OCR real:

```sh
python tools/run_windows_stage.py --name real-ocr-delayed -- tools/check_ocr_retry_lab.py
```

Essa rotina injeta seis segundos no primeiro trabalho textual de cada um dos três
testes afetados e mantém a validade da captura em cinco segundos. A simulação usa
a plataforma onde o comando for executado; não transforma Linux em Windows.

**Estado da correção:** falhas de contagem corrigidas e revisão aprovada pelo job
Windows nº 29. A auditoria posterior identificou que esse job não executava o
Coletor empacotado. Reproduzida uma falha de importação em sua entrada; correção e
nova prova de transporte em `../lab-packaged-collector/README.md`.
A instalação física permanece separada da validação na máquina Windows do GitHub.
