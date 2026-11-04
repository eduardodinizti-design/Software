# Uso de CPU no OCR e evidência de falhas — etapa 2

**Atualização:** o usuário confirmou que a execução Windows da revisão
`acd13517527f6071539f31aeed4f80d4b376760a` ficou verde. O workflow dessa revisão
exige suíte, geração dos executáveis, inicialização da Central e transporte do
Coletor empacotado antes de publicar o candidato. A confirmação é textual;
número da execução, duração e relatórios internos não foram fornecidos.
Registro em `confirmed-windows.json`. Próximo passo: `../VALIDACAO_DOIS_COMPUTADORES.md`.

O log Windows da revisão `17d289d`, fornecido pelo usuário, registra **316 testes,
uma falha e três omissões**, em 350,014 s. A leitura completa de `window-1.5` não
chegou nos 35 segundos do cenário. As reconexões e os três testes do Coletor em
código-fonte passaram. O build parou antes da geração dos executáveis e da nova
verificação do Coletor empacotado. Trechos em `reported-windows-failure.txt`.

## Investigação e ajuste

O log recebido contém atrasos e avisos de tarefas lentas do asyncio, mas não
contém o diário de rejeições da sessão. Portanto, ele não comprova sozinho a causa
do atraso. No Linux, restringimos a afinidade do processo e dos filhos a um ou
dois núcleos, com TCP e OCR reais, as mesmas sete imagens e as mesmas asserções.
Isso mede restrição de CPU; não emula o Windows.

Com um núcleo e a configuração anterior, oito trabalhos textuais ultrapassaram
a validade de cinco segundos. O runtime os descartou corretamente e precisou de
novas capturas. O primeiro cenário só completou a leitura após 33,870 s. Esse
ensaio terminou aprovado, mas mostrou pouca margem e repetição de trabalho.

O runtime já usa dois processos de OCR. Cada processo também criava pools
internos do ONNX Runtime e do OpenCV. Agora, cada filho usa **uma thread de
inferência ONNX e uma de OpenCV**, mantendo o paralelismo entre os processos.
O ajuste do OpenCV fica no filho; leitores independentes mantêm seu padrão.
Nenhum modelo, pixel, limiar de reconhecimento ou regra de publicação mudou.

Resultados de uma execução por configuração, na mesma máquina Linux:

| CPU disponível | Antes: teste inteiro | Depois: teste inteiro | Antes: descartes por vencimento | Depois: descartes por vencimento |
| --- | ---: | ---: | ---: | ---: |
| Um núcleo | 77,278 s | 24,226 s | 8 | 0 |
| Dois núcleos | 16,986 s | 17,708 s | 0 | 0 |

Com um núcleo, a janela a 150% passou de 9,356 s até a primeira leitura completa
para 3,463 s. A maior idade de uma leitura publicada depois do ajuste foi
4,4173 s. Tempo até a recuperação inclui tentativas descartadas e não equivale
à idade da imagem publicada. Estes ensaios sustentam o ajuste de concorrência.
O resultado verde posterior encerra a falha do teste nessa execução Windows,
sem identificar sozinho todos os fatores que causaram o atraso anterior.

Os limites continuam em **cinco segundos por captura** e **35 segundos por
cenário**. Os testes continuam exigindo cartas e fase corretas, parcial e leitura
completa, protocolo 2, sequência/sessão/hash de origem e ausência de duplicação
por geração. Resultados tardios não ganham validade por receber pixels iguais.

## Diagnósticos preservados

Os três testes de integração com OCR agora copiam a sessão em caso de falha para
`diagnostics/integration/` antes da limpeza temporária. Guardam diários, métricas,
rejeições e evidências disponíveis. O pipeline também registra tempos e hashes
por cenário, inclusive no vencimento da espera. A saída imprime as métricas e as
dez últimas rejeições, além da plataforma, Python, CPU e commit do CI.

O workflow já publica `diagnostics/` no artefato `windows-laboratory-evidence`
mesmo quando falha. Dois testes verificam a preservação dos arquivos e que uma
falha ao copiá-los não substitui a falha original. `VISUALPILOT_LAB_KEEP_EVIDENCE=1`
permite guardar também uma execução aprovada, como nos ensaios abaixo.

## Reprodução e evidências

Na raiz do repositório, em Linux, usando um núcleo pertencente à afinidade
disponível:

```sh
VISUALPILOT_LAB_KEEP_EVIDENCE=1 taskset -c 0 python -m unittest discover -s tests -p test_single_table_pipeline.py -v
```

Para dois núcleos, use `taskset -c 0,1`. No Windows, o teste normal não depende
de `taskset`; `build_windows.ps1` executa a suíte completa.

- `before-*.log` e respectivas pastas: código de OCR da revisão `17d289d`,
  com apenas a instrumentação de retenção de evidências adicionada.
- `after-*.log` e respectivas pastas: implementação definitiva com o ajuste.
  Cada pasta contém os cenários, métricas e diário; rejeições só existem quando
  houve descarte. As imagens são os fixtures já versionados, com as composições
  explícitas do teste; os arquivos de imagem da sessão não foram duplicados aqui.
- `full-regression.log` e `.json`: 318 testes em 136,597 s, nenhuma falha e três
  omissões já conhecidas por imagens ausentes.
- `real-ocr-delayed.log` e `.json`: três testes com atraso de seis segundos no
  primeiro trabalho textual, aprovados em 89,952 s. Cada teste registrou um
  descarte por vencimento e recuperou com captura nova; nenhuma leitura publicada
  ultrapassou cinco segundos. Métricas e rejeições estão nas pastas `delayed/`.
- `result.json`: hashes das fontes, resultados e pendências.

**Validação automática Windows concluída, conforme confirmação do usuário.**
A etapa 2 permanece em validação nos dois computadores físicos. O teste do
Coletor empacotado usa um receptor em código-fonte e imagens sintéticas em
loopback; o fluxo de captura no PC até a Central empacotada no notebook é o
próximo teste.
