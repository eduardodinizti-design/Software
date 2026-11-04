# Laboratório fictício do Visual Pilot

## Resultado atual

O laboratório abre seis janelas de mesa em uma grade 3 × 2, no tamanho original de 835 × 1485 pixels. Ele executa o mesmo caminho usado pelo aplicativo: descoberta visual, vínculo com janela, captura, fila multimesas, processos OCR, validação, confirmação, interface de registros e imagens de evidência.

As mesas alternam entre dois estados reais do material recebido:

- `Th 4d`, board `7h As Ts`, flop, quatro ações visíveis e pote/stack;
- `5c 2s`, etapa desconhecida, botões Fold/Call 2,5 BB/Raise, cinco ações visíveis e pote/stack.

Depois que as seis leituras iniciais são confirmadas, todas as janelas trocam de estado simultaneamente cinco vezes. Isso testa mudança de mão, cartas, board, etapa, ID, pote, stack, botões e jogadores sem reaproveitar dados da mão anterior. O laboratório aceita uma leitura como pertencente ao ciclo novo somente quando a captura ocorreu depois da mudança visual.

Resultado reproduzido em Linux:

| Medida | Resultado |
| --- | ---: |
| Descoberta das seis mesas | 3,74 s |
| Primeira mesa completamente lida | 8,24 s |
| Cartas das seis mesas no ciclo frio | 8,67 s |
| Seis mesas inicialmente lidas e confirmadas | 20,38 s |
| Trocas simultâneas concluídas | 5/5 |
| Cartas das seis mesas após aquecimento | 0,66–0,72 s |
| Pior estado completo após troca | 20,44 s |
| Mediana do estado completo | 14,20 s |
| Erros do runtime | 0 |
| Mesas misturadas | 0 |
| Registros estruturados validados | 108 |
| JSONs e evidências PNG inválidos | 0 |

O relatório completo, inclusive tempo por mesa e idade de cada captura, está em [pppoker-desktop-lab.json](pppoker-desktop-lab.json).

Também foi executado um teste com três mesas reais em cada um de dois monitores simulados. O localizador retornou seis mesas, preservou o monitor de origem e traduziu corretamente as coordenadas negativas do segundo monitor. Isso valida a lógica multimonitor; captura em dois monitores físicos e APIs Win32 continuam pendentes.

## Falhas encontradas pelo laboratório

O primeiro ensaio usou mesas de 450 px. O Hero do cenário de flop ficou pendente e uma ação no topo foi cortada. Em 600 px, cartas e board foram recuperados, mas o valor `Call 2,5 BB` não foi lido. O modo aprovado do laboratório mantém os pixels no tamanho original.

O localizador visual também produzia um recorte alguns pixels menor que a janela. O board continuava legível, mas o Hero e o valor do Call podiam desaparecer. A captura agora usa a geometria nativa completa quando uma janela PPPoker tem vínculo único. Regiões compartilhadas ou sem vínculo continuam usando o recorte visual conservador.

O aquecimento dos dois processos OCR começa em paralelo com a descoberta das mesas. O cache por ROI também evita OCR quando somente animações fora dos campos observáveis mudam. No benchmark com animação irrelevante contínua, as seis mesas foram confirmadas com sete execuções OCR e 22 respostas de cache.

O runtime agora agenda as regiões de cartas antes da leitura integral, identifica cada trabalho por mesa e geração e publica `PARTIAL_CARDS_READY` no JSONL e no painel. Nas cinco trocas simultâneas, as cartas corretas das seis mesas ficaram disponíveis em 0,67 s, 0,66 s, 0,69 s, 0,69 s e 0,72 s. O leitor individual aquecido continua na faixa de milissegundos; o valor acima mede captura, fila, 24 trabalhos regionais e publicação das seis mesas.

O estado textual completo continua mais lento: 12,54 s, 12,09 s, 13,78 s, 14,62 s e 20,44 s. Um resultado estável é revalidado periodicamente para que uma leitura textual incompleta não permaneça indefinidamente no cache. A meta de 15 s ainda não é garantida para o snapshot completo, mas já não bloqueia Hero e board.

Uma execução intermediária encerrou o processo Python/ONNX com falha nativa de segmentação. A repetição completa em processo limpo passou, mas esse evento permanece como risco de estabilidade a investigar em um ensaio mais longo e, principalmente, no Windows de destino.

## Cobertura real disponível

O conjunto real cobre 16 das 52 cartas distintas: `2s 3s 4d 5c 5d 7d 7h 8h As Jd Js Kc Kd Qh Th Ts`. Todos os quatro naipes aparecem, mas faltam 36 combinações e não há exemplos reais dos valores 6 e 9. Um conjunto sintético cobre as 36 combinações restantes para regressão do software; ele não substitui a comprovação com cartas reais.

As ações cobertas são fold, check, call e raise. Falta uma imagem real de bet. Os botões do Hero cobrem Fold, Call com valor e Raise sem valor; ainda faltam Check, Bet e Raise com valor legível. Para concluir a premissa de cobertura total, precisamos montar um corpus rotulado com as 52 cartas, cada etapa, todos os botões e variações de valor, animação, escala e tema.

## Melhorias priorizadas

1. Separar o OCR por regiões. Cartas, board, botões e ações devem ser agendados independentemente para evitar reler a mesa inteira quando muda apenas um campo.
2. Aquecer os dois processos OCR antes de iniciar a sessão e publicar a prontidão somente após os modelos carregarem.
3. Processar primeiro regiões que mudaram, mantendo justiça entre mesas. O hash atual detecta a mudança da mesa inteira.
4. Gravar PNGs em uma fila assíncrona limitada para reduzir disputa de CPU e disco durante transições.
5. Adicionar evidência positiva de pré-flop. Ausência de board continua corretamente como etapa desconhecida.
6. Criar o corpus completo e medir acerto, erro e pendência por carta/campo. A meta deve limitar erros; pendência é preferível a uma carta inventada.
7. Executar o mesmo roteiro no Windows com dois monitores físicos, DPI diferentes e seis janelas nativas.

## Como repetir

O laboratório gráfico Linux requer Xorg e o driver `dummy`. Esses componentes servem somente ao ambiente de teste; não são necessários no Windows.

```bash
./tools/run_pppoker_lab.sh
```

O comando grava sessões em `sessions/lab` e o relatório em `docs/pppoker-desktop-lab.json`. Para reexecutar somente a suíte automatizada:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

No Windows, permanecem necessárias apenas as dependências travadas em `requirements.lock`; RapidOCR e ONNX são instalados pelo `pip`. Tesseract é usado somente pelo modo experimental de templates, não pelo modo PPPoker padrão.
