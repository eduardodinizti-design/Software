# Transporte LAN

O coletor executa `python -m visualpilot.pppoker.stream_node`. Lê IP, porta e membro de `stream_config.ini`, utiliza a descoberta/captura existente (máximo seis mesas) e transmite recortes RGB. PNG sem perdas permanece o padrão. A largura é reduzida para no máximo 755 pixels antes do envio, preservando a proporção e a janela inteira.

Na Central, `await run_remote_session(session, 'stream_config.ini')` inicia o receptor e `PerceptionSession.run(capture=False)` juntos. Frames entram na Mailbox e seguem pelo mesmo ROI/OCR/scheduler local. `session.stop.set()` encerra ambos. O painel Streamlit oferece Iniciar coleta e Parar coleta usando esse inicializador.

TCP usa prefixo de tamanho, cabeçalho JSON e imagem, com limite de 8 MiB. A identidade inclui membro, sessão do transmissor e mesa; sequência duplicada é descartada. A geração do scheduler corresponde a mudanças visuais, não a cada pacote de rede. Há limite de seis identidades por sessão do receptor. A lista ativa retira mesas antigas do mesmo membro/sessão; uma nova sessão pode substituir a anterior após o prazo de ausência. A lista também pode chegar por controle sem imagem, inclusive vazia. O transporte atual destina-se à LAN confiável, sem autenticação ou criptografia.

## Estado independente das imagens (Central r5)

`stream_control.py` envia `collector_status` a cada dois segundos aproximadamente,
em uma thread própria e socket TCP separado, na mesma porta 48735. Cada troca
recebe um ticket, envia um cabeçalho de até 4096 bytes sem payload de imagem,
aguarda `collector_ack` correlacionado à sessão/sequência e fecha o socket.
O ciclo de leitura tem prazo total de quatro segundos; reconexão ocorre no ciclo
seguinte. Dados e controle não compartilham respostas nem bytes intercalados.

O envelope mantém `protocol=2` e usa `control_version=1`. A Central aceita PNG
dos Coletores anteriores; o novo controle exige Central r5. Em uma Central antiga,
o Coletor informa a ausência de confirmação e a necessidade de verificar versões.
Atualize os dois programas juntos para utilizar os estados novos.

O controle transporta membro/sessão, sequência própria, geração e lista ativa.
`active_tables=null` significa descoberta ainda indefinida; `[]` só confirma zero
mesas após descoberta concluída. `discovery_state` distingue `pending`, `ready` e
`error`. Uma descoberta pendente ou com erro não substitui a lista confirmada.
Falha/ausência de monitor não autoriza o Coletor a anunciar lista vazia.

Uma lista antiga não reverte a lista mais recente; conflito na mesma geração,
sequência repetida, ticket vencido e sessão retirada são recusados. Um controle
não retira mesas de outro membro. O receptor limita a seis membros de controle.

O painel considera o heartbeat atrasado após seis segundos, mas cada imagem
continua vencendo aos cinco segundos. Heartbeat não renova preview, leitura,
ticket de uma captura anterior ou decisão. Pixels iguais não são prova de falha.
A lista vazia remove filas/prévias/leituras. Cada entrada remota recebe uma época
de validade; um OCR atrasado não recria a mesa, inclusive se a mesma chave reaparecer.

`collector_status.json` registra bytes por frame e acumulados, tempo de preparo/
codificação, tempo de `sendall` e ida/volta do controle. `sendall` mede entrega ao
socket local, não recebimento ou OCR na Central. A Central conta controles em
`accepted_controls`, separadamente de imagens, e conserva o último erro de pacote
com tipo, mensagem limitada e canal em `metricas.json`. O Coletor registra falha e
retomada do controle em `collector.log`.

## JPEG experimental

Em `[transport]`, `image_codec = jpeg` habilita JPEG e `jpeg_quality = 100` define a qualidade (inteiro de 1 a 100, padrão 100). A ausência da seção mantém PNG. Pare e reinicie a coleta para aplicar mudanças. Salvar endereço/porta/membro pela interface preserva essa seção. A escolha e a qualidade ficam em `collector_status.json`; a Central contabiliza os formatos aceitos em `metricas.json`, `transport.image_codecs`.

JPEG usa amostragem de cor 4:4:4, mas continua sendo um formato com perdas, mesmo na qualidade 100. Não há redução adicional da resolução nem troca automática de qualidade. A opção exige avaliação das cartas e dos textos no layout utilizado antes de substituir o PNG. O laboratório comparativo está em `tools/compare_image_codecs.py`.

O cabeçalho inclui `image_codec` (`png` ou `jpeg`). A Central confere a assinatura do payload, o término do JPEG e as dimensões decodificadas. Cabeçalhos antigos sem esse campo continuam sendo interpretados como PNG. Um erro de formato não consome o ticket nem altera mesas. O ticket é verificado antes e depois da decodificação; o limite temporal continua em cinco segundos.

O hash de observação identifica os pixels RGB **decodificados na Central**, que podem diferir dos pixels antes da compressão. O replay de carga usa essa mesma referência. Pixels idênticos ainda precisam de uma nova captura autorizada, ticket e sequência; JPEG não comprova que o conteúdo da tela está vivo.

Validação de sockets locais não comprova desempenho do Wi-Fi nem captura no Windows físico. Os testes não validam conexão real ao Supabase.
