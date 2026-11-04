# Checklist de evolução — Coletor e Central

Referência inicial: `4a9261f`; atualização de laboratório: Central r5 PNG/controle,
31/10/2026. Evidências novas em [lab-png-control](lab-png-control/README.md).
Os itens pendentes abaixo não foram implementados por sua inclusão nesta lista.

`[x]` significa implementado e verificado no escopo explicitado, não homologação
global. `[ ]` significa trabalho ou validação pendente. A Central continua
observacional; ações automáticas/manuais são testadas exclusivamente no simulador.

## 1. Preservar as bases que já funcionam

- [x] Captura MSS em array NumPy RGB, com cópia do buffer, DPI e coordenadas:
  `visualpilot/pppoker/capture.py`. Preservar essa interface; converter tudo para
  PIL acrescentaria conversões sem benefício demonstrado.
- [x] Encoder/decoder OpenCV, com PNG padrão e JPEG experimental 4:4:4:
  `visualpilot/pppoker/stream_node.py` e `stream_receiver.py`.
- [x] Prefixo binário de tamanho, cabeçalho JSON limitado e leitura completa do
  payload. Preservar membro, sessão, mesa, sequência e prova temporal. Não trocar
  isso por um cabeçalho fixo que omita campos ou reduza arbitrariamente os IDs.
- [x] Ticket de uso único emitido antes da captura e verificado após decodificação:
  `transport_freshness.py`. Preservar prazo de cinco segundos, relógio monotônico
  da Central e o descarte de capturas antigas após reconexão. Timestamp do PC pode
  servir a diagnóstico, mas não substituir essa prova entre relógios distintos.
- [x] Filas limitadas, trabalho em processos de OCR, cache, ROIs e descarte de
  resultados substituídos: `observer/runtime.py`, `scheduler.py`, `roi_engine.py`
  e `replay/service.py`. Preservar identidade, geração e validade ao reutilizar cache.
- [x] Preview e leitura vencida sinalizados no painel; pausa/retomada e bloqueio
  de decisões antigas no simulador. Não mover o atuador do simulador para o painel.

## 2. PNG mantido como padrão; JPEG experimental sem promoção prevista

- [x] Escolha `image_codec` e `jpeg_quality` em `[transport]` de `stream_config.ini`.
  Sem seção, usa PNG. Se JPEG for escolhido sem qualidade explícita, usa 100.
- [x] Decodificação para RGB no receptor, validação de formato e dimensões,
  compatibilidade com PNG antigo e contagem dos formatos aceitos.
- [x] Comparativo de 18 cenários em quatro formatos, com rótulos de cartas e
  comparação textual: `tools/compare_image_codecs.py`.
- [x] Replay JPEG 95 via TCP/OCR com uma, três e seis mesas e reconexão.
- [ ] Investigar perda de Hero no JPEG 95 a 150% e perda de Call de 2,5 BB no
  JPEG 85/95. Preservar o exemplo que falha; não baixar a confiança para escondê-lo.
- [ ] Rotular/revisar diferenças de texto do JPEG 100, separando espaços,
  recuperação de informações ausentes e valores incorretos.
- [ ] Ampliar cobertura independente de cartas, botões, valores e layouts antes
  de aprovar JPEG como padrão. Qualidade 75 não foi avaliada nesta rodada.

Evidência: [laboratório JPEG](lab-jpeg-transport/README.md). JPEG 95 reduziu bytes
em 66,9%, mas falhou em reconhecimento; JPEG 100 reduziu 22,5% e preservou as cartas
avaliadas, com diferenças de texto pendentes. Não há justificativa para forçar
JPEG 75–85 ou alterar leitores apenas para aceitar o formato: eles já recebem RGB.
O preview também já aceita os pixels decodificados, sem nova dependência de imagem.

## 3. Estado da conexão e mesas sem depender de imagens — implementado em laboratório

Arquivos: `stream_node.py`, `stream_receiver.py`, `collector_app.py`,
`multitable.py`, `table_registry.py`, `visualpilot/viz/session.py` e `monitor.py`.

- [x] Lista de mesas ativas e geração de descoberta em cada frame; retirada de
  registros antigos do mesmo membro/sessão. Movimento e reconexão passaram em
  cenários de laboratório. O problema no layout físico do usuário segue aberto.
- [x] Definir mensagens de controle versionadas, pequenas e limitadas, com
  sequência própria e confirmação correlacionada. Preservar compatibilidade ou
  apresentar erro claro de versão; não confundir respostas com tickets de captura.
- [x] Enviar estado/lista ativa independentemente dos frames, inclusive lista
  vazia. Zero mesas precisa retirar as entradas antigas mesmo sem novo JPEG/PNG.
- [x] Implementar heartbeat. Parâmetros verificados em laboratório: intervalo de 2 s
  e conexão considerada indisponível após 6 s sem resposta, com prazos documentados
  e testáveis. Esse prazo de conexão não amplia a validade de cinco segundos da imagem.
- [x] Correlacionar controles a membro/sessão/geração. Mensagens antigas, outra
  sessão ou outra origem não podem retirar mesas atuais. Ordem e duplicatas
  precisam de testes próprios; não reiniciar a geração das imagens com cada ping.
- [x] Isolar controles em socket/thread próprios: uma troca por vez, mensagem
  limitada e leitura com prazo. Não intercalar bytes ou respostas com imagens.
- [x] Separar no status: conexão acessível, descoberta concluída, ausência de
  mesas, captura falhou, imagem atrasada e OCR pendente/expirado.
- [x] Ao confirmar zero mesas, limpar previews, filas e leituras dessas mesas.
  Em silêncio de rede, mostrar desconexão/atraso; silêncio não prova que a mesa fechou.
- [ ] Testar movimento rápido, redimensionamento, fechamento, reaparecimento,
  troca de monitores, reinício e listas fora de ordem. Preservar identidade quando
  houver vínculo suficiente; na ambiguidade, retirar o registro antigo sem atribuir
  a uma mesa nova o histórico de outra. Coordenada isolada não é identidade.

**Critério de saída:** nenhum controle pode publicar/revalidar imagem, prolongar
leitura antiga ou afetar mesas de outra sessão. Lista vazia confirmada limpa o
estado; reconexão exige captura nova e não deixa duplicatas nos cenários conhecidos.
O laboratório verifica zero mesas sem frames e bloqueio de OCR atrasado, incluindo
reaparecimento da mesma chave. Continuam pendentes medições extensas de retirada
e os layouts físicos. Uma única troca de controle fica em andamento por Coletor.

## 4. Congelamento: distinguir conexão de conteúdo

- [x] Hash identifica pixels e ajuda cache/proveniência; ticket limita a idade
  do fluxo de captura cooperante. Nenhum dos dois é detector universal de tela travada.
- [ ] Testar separadamente: conexão morta, captura sem progresso, OCR bloqueado,
  tela legitimamente parada e API que devolve pixels antigos com tickets novos.
- [ ] Registrar progresso de captura, envio, recebimento e OCR separadamente.
  Heartbeat pode indicar conexão ativa enquanto uma dessas etapas falha.
- [ ] Projetar evidência adicional de vivacidade antes de afirmar que pixels
  repetidos representam congelamento. Se a distinção não puder ser feita, expor
  a incerteza. Não invalidar automaticamente uma mesa parada só pelo hash igual.

## 5. Instrumentação e diagnóstico

- [x] `collector.log` com rotação e `collector_status.json` com estado/contagem.
- [x] `central_startup.log` e `central_status.json` para inicialização.
- [x] `erros_ocr.jsonl` com tipo, mensagem e contexto do trabalho, incluindo
  erro que chegou depois do vencimento. Registro atual é limitado; não é um log ilimitado.
- [x] Métricas de sessão, rejeições temporais e contagem PNG/JPEG na Central.
- [x] Medir bytes, preparo/codificação combinados, escrita no socket e ida/volta
  do controle; contagens de controles e imagens aceitas ficam separadas.
- [ ] Completar medidas separadas de captura, resize, compressão, espera de confirmação,
  decodificação, fila, OCR e publicação; definir claramente o início/fim de cada medida.
- [ ] Separar `enviado`, `aceito`, `substituído`, `expirado` e `publicado`. Um
  `sendall` bem-sucedido não prova que o OCR recebeu/processou a imagem. Não chamar
  descarte da aplicação de perda de pacote TCP sem evidência de transporte.
- [ ] Publicar resumo periódico atômico e manter memória/arquivos limitados por
  rotação/amostragem. Incluir p50/p95/máximo, cobertura por mesa e reconexões.
- [ ] Registrar causa de falhas de transporte em log próprio; manter o log de
  inicialização voltado a startup. Evitar log pesado por frame na thread da interface.
- [ ] Reproduzir as 79 exceções da sessão antiga quando houver material suficiente.
  A sessão não guardou as mensagens: o novo journal não prova que foram corrigidas.

## 6. Desempenho e precisão

- [ ] Comparar PNG/JPEG no mesmo ambiente e carga, com rótulos, rede controlada e
  tempos por etapa. Redução de bytes não implica redução da latência do OCR.
- [ ] Otimizar o gargalo medido e a justiça entre mesas; manter filas limitadas
  e preferência pela captura recente. Não aumentar o prazo para disfarçar atraso.
- [ ] Medir crescimento de RAM, threads, processos, sockets e arquivos após cada
  ciclo de reconexão; definir orçamentos para o equipamento alvo antes da homologação.
- [ ] Tratar envio delta como etapa posterior: requer referência/base explícita,
  reconstrução verificada e frame completo após perda da base ou reconexão.

Referência atual do ensaio JPEG: p95 da idade publicada 4,44 s; 37 resultados
expirados descartados. Não aprova operação sem lag. O resultado precisa ser
avaliado junto à frequência de leituras úteis e à cobertura, não apenas ausência
de exceções ou média de processamento.

## 7. Rede física — depende de acesso posterior

- [ ] Reservar IPv4 por DHCP no roteador ou configurar endereço estático fora de
  conflito com o DHCP. Decisão e alteração dependem da rede real disponível.
- [ ] Avaliar nome local/DNS com resolução dinâmica válida. Entrada `hosts` que
  aponta para IP antigo não resolve mudança de endereço.
- [ ] Verificar conectividade e porta 48735, firewall, Wi-Fi/cabo e reconexão
  após reinício dos dois computadores. Não atribuir toda falha de OCR à rede.

A mudança do endereço foi identificada e corrigida pelo usuário; ele confirmou
prévia em movimento. A configuração permanente foi adiada e não é realizável no
laboratório remoto sem acesso à rede dos computadores.

## 8. Testes, build e liberação

- [x] Dependências OpenCV e Pillow já declaradas. Não adicionar Pillow novamente
  nem alterar `.spec` por suposição; conferir recursos no executável efetivamente gerado.
- [x] Pipeline Windows existente: testes, build, startup, Coletor empacotado,
  captura de desktop e validação dos pacotes antes de disponibilizar candidato.
- [x] Suíte da revisão `4a9261f`: 349 testes executados, sem falhas, três omitidos
  por imagens ausentes. Isso não cancela a reprovação de qualidade do comparativo JPEG.
- [x] Ensaios TCP/OCR curtos com seis mesas; pausa/retomada e falhas no simulador
  possuem evidências anteriores. `check_control_failure_lab.py` trata a fronteira
  de ações simuladas, não substitui testes de rede ou captura física.
- [x] Integrar controle/heartbeat ao caminho normal e testar sessão, ordem,
  expiração, reconexão, erro de descoberta e retirada durante OCR. Suíte final:
  363 testes, sem falhas, três omitidos por imagens ausentes.
- [ ] Executar ensaio contínuo de pelo menos quatro horas, com até seis mesas,
  mudanças rotuladas, movimentos, listas vazias, erros de OCR, desconexões e
  reinícios programados. O script atual aceita até uma hora na fase de seis mesas;
  ampliar o executor e limitar seus registros antes do teste de quatro horas.
- [ ] No ensaio prolongado, verificar todas as mesas, resultados antigos/duplicados,
  precisão, evolução de recursos e recuperação. Definir critérios antes de executar;
  preservar a falha e o checkpoint para reprodução. Tempo transcorrido não basta.
- [ ] Confirmar o workflow Windows da revisão candidata exata. A última confirmação
  fornecida pelo usuário foi `acd1351`, anterior às correções recentes.
- [ ] Validar executáveis finais em ambos os computadores: três mesas do layout
  real, movimento, mais mesas até o limite, observar sem Hero, abrir/fechar,
  parar/iniciar e queda de conexão. Conferir a revisão e os hashes dos pacotes.
- [ ] Obter captura do desktop inteiro para reproduzir o caso físico de uma mesa
  detectada entre três visíveis quando o usuário voltar a ter acesso ao PC.
- [ ] Liberar somente com evidências e limitações explicitadas. Não transformar
  aprovação Linux em aprovação Windows, nem simulador em atuação no PPPoker real.

## Ordem de execução

1. Controle independente, heartbeat e zero mesas, com testes negativos de sessão/ordem.
2. Diagnósticos por etapa e correções de identidade/retirada reproduzíveis em laboratório.
3. Precisão e desempenho medidos com PNG; JPEG permanece opção experimental inativa.
4. Ensaios prolongados e validação dos pacotes Windows.
5. Configuração da rede e homologação física quando os equipamentos estiverem disponíveis.

Fluxo preservado: captura RGB → PNG padrão/JPEG experimental → TCP com identidade
e ticket → validação e RGB decodificado → filas/ROI/OCR → painel e diário.
Controles de conexão/lista ativa usam um caminho separado das imagens. O fluxo
de ações continua restrito ao laboratório.
