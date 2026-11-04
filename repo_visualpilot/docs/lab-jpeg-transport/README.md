# JPEG no transporte — avaliação de 31/10/2026

## Decisão

JPEG foi implementado como opção experimental, selecionada em `stream_config.ini`.
Se JPEG for escolhido sem qualidade explícita, usa 100; qualidades menores só
entram mediante configuração explícita, devido às regressões observadas abaixo.
**PNG permanece o padrão.** Houve redução de bytes, mas JPEG 95 perdeu leituras
de cartas e botões que estavam disponíveis em PNG. Nenhum executável Windows foi
homologado nesta rodada; estes resultados são de Linux e fontes gravadas.

## Implementação

- `stream_node.py`: seleção `png`/`jpeg`, qualidade validada entre 1 e 100,
  amostragem JPEG 4:4:4 e identificação do formato no cabeçalho. Sem novo resize.
- `stream_receiver.py`: verifica assinatura/formato, término do JPEG e dimensões;
  converte para RGB no mesmo fluxo de filas/OCR. Rejeições não alteram mesas nem
  consomem tickets. Conta formatos aceitos em `transport.image_codecs`.
- `collector_app.py`: lê `[transport]` ao iniciar e registra a escolha no status.
  Salvar conexão pela interface preserva os parâmetros de transporte.
- `compare_image_codecs.py`: comparação reproduzível de codificação, recebimento,
  cartas por ROI, leitura completa e diferenças de texto.
- `check_multitable_soak.py`: aceita codec/qualidade; verifica a identidade pelos
  pixels decodificados, pois compressão com perdas altera o hash original.

Não foram alterados os limiares de reconhecimento, o prazo de cinco segundos,
o heartbeat, a configuração da rede física ou a descoberta de mesas.

## Comparação de imagem e OCR

18 cenários: duas imagens de ação em três escalas, versões com Hero oculto,
recortes produzidos pela descoberta visual e oito imagens gravadas com rótulos
anteriores. Escalas e máscaras são derivações, não mãos independentes. A matriz
não representa cobertura completa das 52 cartas nem dos layouts físicos do usuário.

Cada cenário foi avaliado em PNG e JPEG 85/95/100, sempre 4:4:4. São 72 combinações,
seis verificações de cartas por combinação (Hero, flop, turn, river e duas leituras
completas); verificações de regiões vazias também contam nesse total. Os textos
foram comparados ao PNG, sem tratá-lo como verdade independente para todo campo.

| Formato | Bytes totais dos 18 pacotes | Redução vs. PNG | Verificações de cartas corretas |
|---|---:|---:|---:|
| PNG | 19.630.701 | — | 108/108 |
| JPEG 85 | 3.519.539 | 82,1% | 108/108 |
| JPEG 95 | 6.495.685 | 66,9% | 107/108 |
| JPEG 100 | 15.206.417 | 22,5% | 108/108 |

JPEG 95 deixou o Hero vazio na leitura completa de `left_99-scale-1.5`, cujo rótulo
é `Th, 4d`. O leitor especializado de cartas permaneceu correto nesse cenário;
isso não elimina a regressão no outro caminho usado pelo sistema.

JPEG 85 e 95 também omitiram o botão Call de 2,5 BB em `right_99-scale-1.0`,
`right_99-scale-1.5` e `right_99-masked-hero`, enquanto PNG o leu. A diferença
afeta disponibilidade de ação e valor, não apenas aparência da prévia.

JPEG 100 não perdeu cartas rotuladas neste corpus. Suas nove diferenças de campos
de texto incluem espaços e informações adicionais que PNG deixou pendentes;
**não são nove erros comprovados**. Exigem revisão dos campos antes de aprovação.
Há diferenças também no PNG entre escalas, que esta rodada não procura corrigir.

As medianas por cenário das sete repetições de codificação foram 51,15 ms (PNG),
4,19 ms (JPEG 85), 5,08 ms (JPEG 95) e 7,02 ms (JPEG 100). No recebimento local,
incluindo validação, decodificação e entrada na Mailbox, foram 22,20 / 4,38 / 5,81 /
9,87 ms. O OCR completo mais ROIs foi executado uma vez por combinação, com
medianas 1,22 / 1,21 / 1,40 / 1,26 s. Esses tempos são descritivos: não medem Wi-Fi
nem comprovam redução de latência ponta a ponta. A ordem dos formatos foi alternada.

`comparison.json` contém leituras, hashes das fontes, diferenças e tempos;
`comparison.log` preserva a execução. O comparador terminou com código 1 porque
as opções JPEG não satisfizeram o critério conservador de cartas sem regressão
e textos idênticos ao PNG. A falha foi preservada, sem afrouxar os critérios.

## Transporte e recuperação com OCR real

O replay JPEG 95 passou em 30 s com uma mesa, 30 s com três e 180 s com seis.
As duas imagens conhecidas alternaram a cada 12 s. Depois houve silêncio real de
5,3 s, invalidação das leituras antigas e reconexão com uma mesa substituindo as seis.

- 4.226 frames verificados, todos JPEG; zero frames rejeitados pelo transporte.
- 246 publicações consolidadas verificadas; cobertura 1/1, 3/3, 6/6 e recuperação 1/1.
- Zero erros de execução do OCR e zero violações de cartas, identidade ou validade
  nos critérios do ensaio. O ensaio **não valida botões ou valores de aposta**;
  portanto não elimina as regressões de texto do comparativo anterior.
- Retomada com leitura: 2,28 s. Idade da fonte p50/p95/máxima: 1,94/4,44/4,95 s.
- 37 resultados descartados por vencimento; 22 por geração substituída.
- Pico de RSS somado do processo e filhos: 871,1 MiB.

O teste foi executado sem outra bateria de testes concorrente desta rodada.
Não é uma comparação controlada com o ensaio PNG de outra rodada, nem um teste
de horas. A margem temporal continua curta. Redução de bytes não demonstra, por
si só, resolução de travamentos ou melhora da latência das leituras.

`soak.json`, `soak.log` e `soak-perception.jsonl.gz` preservam métricas e registros.

## Regressão do código final

A suíte completa executou **349 testes em 136,489 s**, sem falhas, com três
omissões preexistentes por imagens ausentes (`regression.log`). Inclui oito testes
novos de compatibilidade PNG, configuração, JPEG 4:4:4 conferido com decoder
independente, RGB, corrupção, validade temporal, ticket/seq repetidos e TCP real
com seis mesas e reconexão. Os testes existentes do pipeline PNG/OCR também passaram.
O comparador de qualidade JPEG reprovado é um experimento separado; não está
escondido nessa contagem nem foi convertido em aprovação de qualidade visual.

## Reprodução

```sh
python -m unittest discover -s tests -p test_jpeg_transport.py -v
python tools/compare_image_codecs.py --output diagnostics/jpeg-transport/comparison.json
python tools/check_multitable_soak.py --image-codec jpeg --jpeg-quality 95 --seconds 180 --output diagnostics/jpeg-transport/soak
python -m unittest discover -s tests -v
```

O comparador é um experimento em processo com o encoder/receptor normais; não usa
socket. O ensaio de carga usa TCP real, runtime e OCR reais, mas imagens gravadas,
sem captura de tela do sistema operacional e sem atuação no jogo.
