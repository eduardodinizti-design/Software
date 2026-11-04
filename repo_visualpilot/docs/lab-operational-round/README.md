# Rodada de confiabilidade — laboratório, 31/10/2026 UTC

O usuário autorizou continuar sem acesso ao PC ou notebook. Esta rodada desenvolve
e testa as etapas seguintes sem aprovar globalmente a etapa de reconhecimento nem
a instalação física. A Central de observação continua sem enviar ações ao jogo.

## Reprodução, correções e critérios

O ensaio inicial da fronteira de ações do simulador falhou: decisões com mais de
cinco segundos e decisões de outra imagem eram aplicadas. Uma exceção de OCR
também escapava sem resposta estruturada. Ver `failure-boundary-before.log`.

O servidor do simulador agora:

- Mede o prazo desde a solicitação de captura, incluindo espera e processamento.
  Uma leitura que termina vencida não recebe token; ação automática ou manual
  vencida é recusada. O prazo de cinco segundos não foi ampliado.
- Confere o hash da imagem recebida e o vínculo da decisão à mesa, geração e
  imagem antes de aplicar a ação simulada.
- Registra exceções e invalida a observação anterior ao iniciar uma nova leitura.
- Cancela trabalhos na fila após pausa ou substituição; mantém o controle livre
  durante OCR e impede que pedidos simultâneos apliquem duas ações.
- Oferece **Atualizar leitura manual** e explica o bloqueio por expiração na tela.

Os 42 testes direcionados passaram, incluindo oito testes novos da fronteira de
ações, controle manual, lista de mesas, reconexão, registro de erros e lógica de
múltiplas janelas/monitores. A bateria temporal e de transporte passou em 33 testes.
Contagens dessas baterias não devem ser somadas à suíte completa: há sobreposição.

O navegador executou OCR real via servidor HTTP: esperou a leitura vencer,
confirmou o bloqueio, atualizou a captura manual, aplicou uma ação humana e retomou
os quatro cenários automáticos. Também verificou pausa antes do envio, retomada
manual e bloqueio automático com Hero oculto. Os quatro critérios passaram,
sem erros JavaScript. As ações afetam exclusivamente o simulador.

A regressão geral terminou com **341 testes em 142,218 segundos**, sem falhas e
com três omissões preexistentes por imagens ausentes (`full-regression.log`).
O percurso normal em código-fonte, com captura de desktop MSS, Coletor, TCP,
Central, OCR e navegador, passou novamente nos **11 critérios**, em 1920×1080,
incluindo três mesas após movimento (`desktop.json`). Esse percurso usa imagens
gravadas exibidas em uma janela real; não injeta os frames no Coletor.

## Carga com uma, três e seis mesas

`check_multitable_soak.py` enviou imagens gravadas por TCP real para o runtime
normal. Foram 30 segundos com uma mesa, 30 com três e 180 com seis, alternando
duas imagens conhecidas a cada 12 segundos. Depois interrompeu a conexão por
5,3 segundos e retomou com uma única mesa, retirando os seis registros anteriores.
Esse cliente de replay não executa captura de tela do sistema operacional.

| Medição | Resultado |
|---|---:|
| Quadros aceitos e verificados | 1.891 |
| Erros de OCR | 0 |
| Publicações consolidadas verificadas | 210 |
| Violações de cartas, identidade ou validade nas publicações verificadas | 0 |
| Cobertura de mesas em cada fase | 1/1, 3/3, 6/6; recuperação 1/1 |
| Retomada com leitura consolidada | 2,35 s |
| Idade da fonte na publicação, p50 / p95 / máxima | 1,84 / 4,48 / 4,96 s |
| Processamento textual sem cache, p50 / p95 / máximo | 2,07 / 2,52 / 2,92 s |
| Pico de RSS somado do processo e filhos | 747,5 MiB |
| Resultados descartados por vencimento | 32 |
| Resultados descartados por geração substituída | 2 |

As duas mãos foram lidas em todas as mesas. Cada uma das seis mesas teve 30 ou
31 publicações consolidadas durante essa fase. Descartes impediram publicar fontes
vencidas, e capturas novas permitiram continuar. O p95 próximo do limite indica
margem curta; não representa aprovação de desempenho em qualquer computador.
Tempos de processamento são do trabalho textual, não a soma de todos os ROIs.
CPU e memória por amostra estão em `soak.json`; CPU usa 100% por núcleo.
O ambiente tinha quota de quatro CPUs. Duas baterias curtas de regressão rodaram
durante o ensaio: os números são descritivos, não um benchmark de capacidade isolado.

## Limites da aprovação

1. Reconhecimento: cobertura independente das 52 cartas e do layout físico do
   usuário continua pendente. Nenhuma nova captura real foi adicionada.
2. Atualização: os cenários de laboratório acima passaram; Windows físico pendente.
3. Falhas: os casos injetados passaram. Pixels congelados fornecidos por uma API
   defeituosa com tickets novos continuam sendo uma lacuna: pixels iguais também
   podem representar uma mesa legitimamente parada. Não inferimos vivacidade deles.
4. Controle manual: comportamento validado no simulador; não existe prova de um
   atuador do PPPoker real nem foi conectado um nesta rodada.
5. Integração: os percursos de observação e de ações simuladas têm evidências
   separadas. O ensaio de carga tem quatro minutos, não horas ou dias de estabilidade.
   A validação Windows e a instalação em dois computadores não foram executadas aqui.

## Reproduzir

```sh
python -m pip install -r requirements-lab.txt
python tools/check_freshness_lab.py --include-transport --output diagnostics/freshness
python tools/check_multitable_soak.py --seconds 180 --output diagnostics/soak
python tools/check_control_failure_lab.py --output diagnostics/control
python -m unittest discover -s tests -v
python tools/validate_desktop_distribution.py --source --output diagnostics/desktop
```

O teste de desktop exige sessão gráfica. Para os programas empacotados, omitir
`--source` e informar `--dist`; a aprovação do pacote Windows exige Windows e os
hashes dos dois pacotes. Os relatórios desta pasta não aprovam executáveis Windows.
