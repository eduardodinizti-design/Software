# Motor de regiões da mesa

O motor em `visualpilot/pppoker/roi_engine.py` usa âncoras calibradas nas capturas reais de 835 × 1485 pixels. As caixas foram conferidas contra as evidências produzidas pelo leitor para Hero, board, ID da mão, pote, stack, botões e ações visíveis.

As coordenadas inicialmente propostas não foram copiadas diretamente. O ID da mão aparece entre aproximadamente `y=983` e `y=1088` nas duas capturas, o pote perto de `y=543`, o Hero perto de `y=1187` e os botões a partir de `y=1380`. O motor converte essas âncoras proporcionalmente quando a captura é normalizada para 755 pixels de largura.

Cada região recebe um BLAKE2 exato dos pixels RGB. Isso evita que uma alteração pequena de valor ou naipe seja tratada como imagem idêntica. Uma alteração no ID da mão invalida todas as regiões. Animações fora das regiões observáveis não provocam uma nova leitura OCR da mesa inteira.

O leitor independente de cartas está implementado em `visualpilot/pppoker/card_reader.py`. Ele segmenta o componente sobreposto do Hero por contornos e localiza as cartas do board geometricamente, reutilizando a validação comprovada de valor e naipe. Nas duas imagens reais ele reconhece `Th 4d`, `5c 2s` e o flop `7h As Ts`; um board vazio permanece pendente. Em 30 leituras aquecidas dos recortes, a mediana observada foi 10,43 ms e o máximo 84,89 ms.

O cache por ROI já decide se a mesa precisa voltar ao OCR. O protocolo dos processos OCR aceita agora trabalhos `card_region`. Cada trabalho exige `table_key`, geração inteira não negativa, nome da região e imagem. A resposta repete essa identidade junto com a leitura, permitindo descartar resultados de uma captura antiga sem confundir mesas. O modelo ONNX continua encapsulado no processo que o criou e não é compartilhado entre threads.

O runtime principal agenda primeiro as regiões de cartas alteradas, grava `PARTIAL_CARDS_READY` no JSONL e atualiza o painel antes do OCR integral. Capturas idênticas mais recentes renovam somente o timestamp do trabalho textual; uma mudança de pixels cria nova geração e invalida o trabalho antigo. Registros parciais usam evidência `deferred` para que a codificação PNG não bloqueie a via rápida.

O consolidator em `visualpilot/pppoker/scheduler.py` implementa essa fusão sem executar estratégia. Ele mantém somente a geração relevante mais nova de cada mesa, espera todas as regiões de cartas programadas, publica `PARTIAL_CARDS` e fecha `CONSOLIDATED` quando o texto da mesma geração chega. Resultados antigos, regiões inesperadas e respostas duplicadas são descartados e contabilizados. Gerações órfãs expiram após 20 segundos por padrão, acima do timeout atual de 15 segundos do OCR.

O teste concorrente inicia seis mesas, bloqueia deliberadamente os seis resultados textuais e comprova que as seis publicações de cartas saem antes deles. No laboratório gráfico, as cinco trocas simultâneas publicaram as cartas corretas das seis mesas entre 0,66 e 0,72 segundo, sem mistura de mesa ou geração.

Os testes de regressão cobrem:

- diferença entre os dois estados reais de mesa;
- mudança de um único byte dentro do naipe do Hero;
- animação fora das regiões;
- invalidação em cascata por mudança do ID da mão;
- escala das coordenadas para a resolução normalizada;
- rejeição de imagens inválidas.
