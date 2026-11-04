# PNG e estado independente — laboratório de 31/10/2026

O transporte continua usando PNG como padrão. Esta rodada implementa heartbeat,
lista de mesas sem depender de imagens e proteção contra resultados de OCR que
chegam depois da retirada de uma mesa. Build: `central-live-20261031-r5-png-control`.
Não é homologação dos executáveis Windows nem dos dois computadores físicos.

## Comportamento implementado

- `stream_control.py`: troca de estado em socket TCP separado, na mesma porta,
  aproximadamente a cada dois segundos. Cabeçalho limitado a 4096 bytes,
  sequência própria, ticket e confirmação correlacionada; leitura com prazo.
- `collector_app.py`: controle em thread própria, diagnóstico de falha/retomada,
  distinção entre descoberta pendente, concluída e com erro. A captura continua
  pelo caminho normal de MSS; não exige um jogador Hero sentado.
- `stream_receiver.py`: aceita lista vazia confirmada, recusa sessões retiradas,
  duplicatas e conflitos; lista antiga não reverte uma descoberta mais recente.
  Um membro não pode retirar mesas de outro por sua lista.
- `multitable.py`: erro ou ausência dos monitores não anuncia zero mesas.
- `observer/runtime.py`, `viz/session.py` e `viz/app.py`: retirada limpa filas,
  prévias e leituras. Uma época por entrada e a revisão da lista impedem OCR ou
  eventos atrasados de recriar entradas retiradas, inclusive quando a chave volta.
  O painel distingue conexão ativa sem mesas de ausência de resposta do Coletor.
- `stream_node.py`: métricas limitadas de bytes, preparo/codificação e escrita
  no socket. Ida/volta do controle e controles aceitos são registrados separadamente.

Heartbeat não renova imagens nem leituras. O painel usa seis segundos para o
estado da conexão; imagens continuam vencendo aos cinco segundos. Pixels iguais
continuam permitidos: uma mesa visualmente parada não comprova travamento.
`sendall` concluído também não comprova reconhecimento pela Central.

PNG preserva os pixels preparados para transporte, sem perdas de codificação.
O redimensionamento **já existente**, para largura máxima de 755 pixels, permanece;
isso não significa resolução original integral. O limite de imagem é 8 MiB.
JPEG permanece opção experimental explícita, desabilitada por padrão. Nenhum
ensaio desta rodada habilitou JPEG ou alterou limiares de reconhecimento.

Detalhes do protocolo e compatibilidade: [STREAM_TRANSPORT.md](../STREAM_TRANSPORT.md).
Para usar o controle, atualizar os dois programas para a revisão correspondente.

## Evidências

### Regressão final

363 testes em 134,348 s, sem falhas; três casos ignorados por imagens de referência
ausentes. [Saída completa](regression.log).

Os casos novos cobrem controles concorrentes com PNG, zero mesas sem frame,
sequências/listas/sessões inválidas, tickets expirados, reconexão, erro de
descoberta, isolamento entre membros e retirada durante a publicação de OCR.
Há teste do painel com conexão ativa sem mesas e posterior expiração do heartbeat.

### Replay TCP/OCR com controle

[Relatório](soak.json), [log](soak.log) e [journal compactado](soak-perception.jsonl.gz).
Uma mesa por 30 s, três por 30 s, seis por 180 s; depois silêncio, lista vazia sem
imagens e recuperação. Usa imagens gravadas e TCP/OCR reais, sem captura do SO.

| Medida | Resultado |
| --- | ---: |
| Imagens verificadas aceitas | 1.911, todas PNG |
| Controles aceitos | 114 |
| Cobertura de leituras por fase | 1/1, 3/3, 6/6; recuperação 1/1 |
| Publicações consolidadas auditadas | 210 |
| Violações dos critérios / erros de execução OCR | 0 / 0 |
| Resultados vencidos / substituídos descartados | 28 / 2 |
| Idade publicada p50 / p95 / máxima | 1,754 / 4,614 / 4,978 s |
| Recuperação | 2,369 s |
| Pico de RSS medido | 829,4 MiB |
| Zero mesas confirmado sem novas imagens | Aprovado |

Esse ensaio ocorreu antes da última proteção para descoberta com erro. A suíte
final e a rodada final de desktop exercitam o código com essa proteção. O ensaio
é curto, de aproximadamente quatro minutos; não equivale ao teste de quatro horas.

### Desktop com entradas normais

O validador passou a exigir 14 verificações, incluindo conexão sem nenhuma mesa,
fechamento de todas as mesas sem novos frames e retorno de uma mesa. O mesmo
conjunto é obrigatório no gate de distribuição Windows; uma execução Linux por
código-fonte não satisfaz esse gate.

A rodada final passou nas **14 verificações**, sem erros JavaScript:
[relatório](desktop-validation.json), [painel após fechar todas as mesas](central-empty-connected.png)
e [três mesas após movimento](central-moved-three-tables.png). A execução Linux
usou desktop 1920×1080, MSS, TCP, OCR e navegador pelas entradas normais dos programas.

## Limites e próximos trabalhos

O p95 de 4,614 s está próximo do limite de cinco segundos: ainda há trabalho de
desempenho. Os resultados vencidos foram descartados, sem aumentar o prazo.
O ensaio não prova ausência de lag, precisão completa dos textos, estabilidade
por horas, desempenho do Wi-Fi ou compatibilidade do pacote Windows.

Continuam abertos o layout físico que detectava uma entre três mesas, a reprodução
das 79 exceções da sessão antiga sem mensagens/imagens suficientes, falhas parciais
de múltiplos monitores e uma API de captura que devolva pixels antigos com tickets
novos. Heartbeat não resolve esses casos por si só. Configuração permanente do IP
e homologação nos dois equipamentos aguardam acesso físico.

## Reprodução

Executar na raiz do checkout, com suas dependências e `PYTHONPATH` apontando para
esse checkout. O teste de desktop exige servidor gráfico e Chromium/Playwright.

```sh
python -m unittest discover -s tests -v
python tools/check_multitable_soak.py --with-control --seconds 180 --output diagnostics/png-control/soak
python tools/validate_desktop_distribution.py --source --output diagnostics/png-control/desktop-final
```
