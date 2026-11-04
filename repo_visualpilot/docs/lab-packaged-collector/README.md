# Auditoria do Coletor empacotado — etapa 2

## Evidência Windows recebida

O usuário forneceu imagens da execução **Windows laboratory nº 29**, revisão
`1660f739f29c1a7fa6cf4a750ad10cadbbfa82a1`, com o job `windows-build` aprovado em
**7 min 12 s**. Testes, geração dos programas, abertura da Central e publicação de
artefatos aparecem concluídos. A imagem não mostra a contagem dos testes nem o
conteúdo do único aviso. A consulta automática ao GitHub continua indisponível
(`Forbidden`); essa confirmação vem das imagens fornecidas pelo usuário.

## Falha encontrada e correção

O job abria a Central, mas apenas compilava o Coletor. O arquivo
`build/VisualPilot_Coletor.spec` usa `stream_node.py` diretamente como entrada.
O import relativo de `transport_freshness` falha nesse contexto, antes de `main`:

```text
ImportError: attempted relative import with no known parent package
```

`before-entry.log` e `before-entry.json` preservam a reprodução com `runpy.run_path`
na revisão anterior, em Linux. O import agora usa o nome completo do pacote.

A opção explícita de laboratório `--lab-transport-probe` exercita a entrada real
do Coletor. Ela usa o `FrameSender` de produção, recebe o ticket antes de produzir
cada imagem sintética e transmite duas imagens distintas. Receber o próximo ticket
confirma que o receptor aceitou o quadro anterior; escrever no socket não basta.
O modo usa somente `127.0.0.1` e não captura a tela.

`tools/validate_collector_distribution.py` inicia um receptor TCP v2 real e o
processo do Coletor em um diretório temporário limpo. Para o executável, remove
`PYTHONPATH` do ambiente. Exige código de saída zero, relatório desta execução,
duas imagens efetivamente recebidas, sequências 1 e 2, sessão/mesa corretas,
hashes exatos dos pixels e comprovação temporal dentro do prazo de cinco segundos.
O hash do executável é conferido antes e depois da execução.

O build Windows executa essa verificação depois de gerar os programas. Falha
interrompe a entrega; os diagnósticos são preservados em `diagnostics/collector/`
e enviados no artefato `windows-laboratory-evidence`. A preparação do pacote exige
relatório aprovado para o hash do executável atual.

## Evidências locais

- `collector-tests.log`: três testes aprovados: importação como script, processo
  transmissor real e rejeição de um processo que declara sucesso sem enviar imagens.
- `build-linux-collector.log`: geração real com PyInstaller 6.16.0 e o mesmo spec
  do Coletor utilizado pelo build Windows.
- `frozen-linux-transport.log` e `frozen-linux/collector-transport-validation.json`:
  executável Linux aberto com sucesso, duas imagens recebidas, protocolo 2
  comprovado, nenhum quadro legado e nenhuma rejeição. Hash do executável e
  identidade das imagens estão no relatório.
- `full-regression.log`: 316 testes executados em 126,940 s, nenhuma falha e três
  omissões já existentes por imagens ausentes (duas variações e um teste completo).
- `result.json`: resumo, hashes das fontes verificadas e distinção entre as
  verificações locais e os resultados recebidos do Windows.

Reproduzir a verificação da entrada em código-fonte:

```sh
python tools/validate_collector_distribution.py --source
```

No Windows, após gerar a distribuição, executar sem `--source` ou usar
`build_windows.ps1`, que inclui a verificação obrigatoriamente.

## Limites e estado

O teste empacotado local foi executado em **Linux**. O receptor desse teste roda
do código-fonte; a verificação não executa o receptor dentro da Central empacotada,
não valida OCR ou captura da tela e não substitui a comunicação entre os dois
computadores físicos. O job Windows nº 29 é anterior a esta correção e não contém
esse teste do Coletor. O log da revisão `17d289d`, fornecido depois pelo usuário,
mostra os três testes do Coletor em código-fonte aprovados, mas a suíte parou com
uma falha na leitura completa da janela a 150% (316 testes, uma falha, três
omissões). A geração e a execução do Coletor empacotado não foram alcançadas.
A investigação e o ajuste de uso de CPU estão em
`../lab-ocr-cpu-budget/README.md`.

Depois, o usuário confirmou que a execução da revisão `acd1351` ficou verde.
Essa revisão exige a execução do Coletor empacotado e o transporte verificado
antes de publicar o candidato. A lacuna de execução no Windows está encerrada
para esse job, conforme confirmação textual do usuário. Não foram fornecidos
número da execução ou relatório bruto; não se atribuem duração ou hash de
executável a essa confirmação. Registro em `../lab-ocr-cpu-budget/confirmed-windows.json`.

**Etapa 2 aguarda validação nos dois computadores físicos.** Procedimento em
`../VALIDACAO_DOIS_COMPUTADORES.md`. As evidências de atualização já existentes
continuam em `../lab-transport-freshness/README.md`; a aprovação geral das etapas
de confiabilidade não é concedida por esta verificação.
