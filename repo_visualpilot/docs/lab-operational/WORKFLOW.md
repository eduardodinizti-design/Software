# Fluxo autorizado de confiabilidade operacional

Checklist consolidado por módulo, com implementado/pendente e critérios de saída:
[`CHECKLIST_EVOLUCAO.md`](../CHECKLIST_EVOLUCAO.md). O histórico abaixo preserva as
decisões e evidências de cada rodada; uma lista de tarefas não aprova uma etapa.

Escopo: uma mesa fictícia em laboratório. Executar, revisar resultados, corrigir e
repetir sem solicitar autorização entre tarefas rotineiras. Não aprovar etapas por
quantidade de testes executados. Revisão pelo mesmo executor não é auditoria independente.

## Etapas e critérios

1. Reconhecimento: cartas, naipes, posições, valores e fase vinculados a imagens
   rotuladas. Incluir cartas claras/escurecidas, ausência, oclusão e ambiguidade.
   Exigir resultado exato nos casos obrigatórios, nenhum reconhecimento incorreto
   aceito e cobertura documentada. Abstenção em carta legível é falha de cobertura;
   abstenção em região ilegível é comportamento esperado. Cobrir todos os valores
   e naipes com material representativo; simulações não substituem capturas reais.
2. Atualização: injetar resultado atrasado, troca de mão, mesa e reconexão. Nenhum
   resultado antigo pode autorizar ação. Registrar captura, geração e publicação;
   idade do quadro não substitui duração de processamento.
3. Falhas: desconexão, imagem congelada, erros de OCR e leituras conflitantes devem
   impedir atuação. Recuperação requer estado recente coerente. Testar a fronteira
   de envio de ações, não apenas o aviso visual.
4. Controle manual: pausa invalida fila pendente; retomada exige nova observação.
   Testar pausa durante cálculo e imediatamente antes do envio. Separar simulação
   de validação no dispositivo real.
5. Integração: repetir cenários anteriores de ponta a ponta, preservar evidências,
   exigir ausência de regressões. Registrar limitações de ambiente e cobertura.

Cada ciclo: hipótese -> reprodução -> correção -> teste direcionado -> regressão
pertinente -> revisão do diff e evidências -> resultado APROVADO/REPROVADO/BLOQUEADO.
Uma etapa reprovada impede aprovação das seguintes. Não reduzir requisitos para
obter aprovação. Pedir intervenção apenas para recursos indisponíveis, decisões de
escopo ou ações que realmente dependam do usuário.

## Estado inicial (preservado como referência)

Etapa 1: REPROVADA. Sem alteração do leitor de produção neste ciclo.

- Sete testes existentes do leitor: passaram (card-baseline.log).
- Novo benchmark real colorido: 18 casos, derivados de três quadros e três variantes
  (original, brilho 70%, escala 75%). Não são 18 mãos independentes.
- Seis casos positivos falharam; 12 casos negativos não inventaram cartas.
- Não há cobertura completa de 52 cartas, posições, turn e river neste conjunto.
- Próximo trabalho: corrigir localização/recorte e reconhecimento de glifos claros
  sobre fundo colorido; manter recusas conservadoras e o leitor anterior sem regressão.
- Não há executor autônomo persistente deste fluxo configurado por este documento.
  O benchmark é executável; este arquivo é especificação e registro, não um serviço.

Reprodução:

```sh
python tools/check_colored_deck.py CAMINHO_DA_SESSAO --output resultado.json
python -m unittest discover -s tests -p test_pppoker_card_reader.py -v
```

O benchmark retorna código 1 quando algum caso falha, guarda hashes dos quadros,
expectativa, saída, diagnósticos e variantes. Imagens originais permanecem locais.

## Evolução executada

Consultar README.md e colored-stress.json: candidato implementado, 60/60 casos
derivados e oito testes específicos aprovados. Etapa 1 segue não aprovada por
cobertura incompleta e ausência de validação independente; etapas 2–5 pendentes.
O benchmark possui registro automático de execução; não há trabalhador autônomo
de desenvolvimento instalado em segundo plano.

## Etapa 2 iniciada por autorização posterior

O usuário autorizou avançar à verificação temporal mesmo com a cobertura visual
pendente. Executadas correções de validade, descarte, cache, painel e retorno
assíncrono da estratégia; evidências em `../lab-freshness/README.md`.
Essa evolução não aprova a etapa 1 nem a confiabilidade de ponta a ponta. A validade
entre a captura remota e a entrada na Central, imagens congeladas e validação no
Windows físico permanecem explicitamente pendentes.

## Etapa 2 — transporte v2

Fechada a lacuna de idade anterior à chegada na Central, com ticket emitido antes da
captura e prazo único até a publicação. Ver `../lab-transport-freshness/README.md`:
32 testes direcionados, 310 executados na suíte ampla (nenhuma falha, três omissões), TCP/OCR e
navegador reais no Linux. Prova Windows ainda pendente; não avançar essa aprovação
por inferência. A precisão do baralho e a detecção de congelamento seguem separadas.

## Retorno do Windows — execução 41138441716

O usuário forneceu o log: três falhas de contagem de parciais em testes integrados.
Reproduzida a condição de OCR textual vencido após publicar cartas: a nova captura
é lida em outra geração e pode repetir as mesmas cartas. Os testes agora conferem
proveniência e unicidade por geração, mantendo o prazo de cinco segundos. Ver
`../lab-windows-diagnostics/README.md`. A etapa 2 segue sem aprovação Windows até
verificação da execução corrigida e dos executáveis.

## Revisão Windows nº 29 e auditoria de empacotamento

Imagem fornecida pelo usuário confirma sucesso da revisão `1660f73`, job de 7 min
12 s, incluindo testes, geração e abertura da Central. Essa evidência encerra a
falha de contagem dos três testes. A auditoria encontrou uma lacuna: o Coletor era
gerado, mas não executado pela validação. Sua entrada como script falhava no import
relativo do protocolo v2. A nova verificação exige execução e envio de duas imagens
pelo Coletor empacotado a um receptor real v2, com identidade, pixels e prazo
conferidos. Ver `../lab-packaged-collector/README.md`. Etapa 2 permanece em validação
até confirmação desse teste adicional no Windows; sem aprovação da instalação física.

## Retorno Windows da revisão `17d289d` — prazo do OCR

O log fornecido pelo usuário mostra uma falha entre 316 testes: a janela a 150%
não produziu leitura completa nos 35 segundos do cenário. A suíte interrompeu o
build antes de executar o Coletor empacotado. Reconexões e transporte do Coletor
em código-fonte passaram. Ensaios Linux com afinidade limitada a um núcleo
mostraram oito descartes por vencimento com os pools internos anteriores; limitar
ONNX e OpenCV a uma thread por processo de OCR eliminou esses descartes nesse
ensaio, mantendo os dois processos e a validade de cinco segundos.

A suíte local após o ajuste executou 318 testes sem falhas, com três omissões já
conhecidas. Os testes integrados agora preservam sessões e rejeições em falha.
Ver `../lab-ocr-cpu-budget/README.md`. A causa específica no Windows ainda precisa
ser confirmada pela nova execução; etapa 2 e Coletor empacotado Windows pendentes.

## Execução Windows `acd1351` confirmada

O usuário respondeu “ficou verde” à consulta sobre essa revisão. O workflow
exige suíte, build, inicialização da Central, transporte do Coletor empacotado
e preparação do pacote antes de publicar o candidato. A validação automática
Windows está concluída segundo esse retorno; não há número de execução, duração
ou relatório bruto adicional. Registro em `../lab-ocr-cpu-budget/confirmed-windows.json`.

Próximo passo: usar os dois programas do artefato dessa execução e validar uma
mesa fictícia do PC até o notebook, seguindo `../VALIDACAO_DOIS_COMPUTADORES.md`.
A etapa 2 aguarda essa instalação física; as etapas 1 e 3–5 não são aprovadas por
esse resultado. A atualização do registro é documental e não requer outro build.

## Continuação autorizada exclusivamente em laboratório — 31/10/2026 UTC

Após o teste físico revelar registros congelados/duplicados ao reorganizar mesas,
foi enviada a revisão `b73f6b9`, com lista de mesas ativas e verificação de desktop
dos executáveis. Evidências em `../lab-desktop-recovery/README.md`; a execução
Windows dessa revisão ainda não foi confirmada neste ambiente.

Sem acesso ao PC ou notebook, o usuário autorizou continuar as etapas 2, 3, 4 e 5
em laboratório. Isso autoriza desenvolvimento e ensaios, sem converter cobertura
incompleta da etapa 1 ou pendências físicas em aprovação global.

Rodada em `../lab-operational-round/README.md`: replay TCP/OCR com 1/3/6 mesas,
interrupção e recuperação; correção de validade e vínculo da imagem na fronteira
de ação do simulador; pausa, retomada e duplicidade via servidor e navegador.
Preservados resultados anteriores à correção, relatórios, imagens e registros.
A observação de mesas continua sem acionar um cliente de jogo.

Próximos critérios ainda abertos: margem de desempenho com seis mesas, sessões
mais longas, cobertura visual independente, congelamento da origem com tickets
novos, resultado Windows e instalação física. O cronograma não está homologado
por uma única rodada local nem pelo total de testes aprovados.

## JPEG experimental — 31/10/2026 UTC

A pedido do usuário, foi iniciado o módulo de compressão: JPEG configurável no
Coletor, validação do formato na Central e comparação com PNG. Resultados em
`../lab-jpeg-transport/README.md`. JPEG 95 reduziu bytes em 66,9%, mas perdeu uma
leitura completa de Hero e leituras do botão Call em cenários conhecidos.
PNG permanece padrão; JPEG não foi aprovado como substituição geral. O replay
TCP/OCR de quatro minutos passou nos critérios de cartas, proveniência e
recuperação, sem certificar botões nem corrigir as regressões do comparativo.
Heartbeat, zero mesas sem frame, rede física e homologação Windows permanecem
pendentes; a compressão não substitui essas etapas.


## PNG e controle independente — 31/10/2026 UTC

Central r5 mantém PNG e acrescenta heartbeat/lista ativa sem depender de frames.
Lista vazia confirmada limpa filas, prévias e leituras; resultados de OCR de uma
entrada retirada não podem recriá-la, mesmo quando a chave reaparece. Descoberta
com erro não é evidência de zero mesas.

Evidências e limites em `../lab-png-control/README.md`: suíte de 363 testes
(sem falhas, três omitidos), replay TCP/OCR curto com 1/3/6 mesas e verificação
do desktop Linux. Essas evidências atualizam as pendências de heartbeat e zero
mesas citadas na rodada anterior. Permanecem pendentes ensaio de quatro horas,
Windows da revisão exata e homologação física; IP fixo continua adiado.


## Inscrição fictícia e ajuste incremental — 31/10/2026

O usuário confirmou limite de 50 fichas fictícias **por inscrição**, separado do
stack recebido, com até quatro torneios simultâneos. O novo módulo de laboratório
`visualpilot/lab/registration.py` cobre seleção incremental, reserva persistente
de orçamento/vaga e confirmação correlacionada. Integra a entrada confirmada ao
ledger existente de rebuy/add-on, incluindo o custo e o indicador bounty lido.

O navegador simula somente seu próprio popup: PNG → OCR → ajuste → nova leitura
→ reserva → inscrição → recibo. Pausa e tomada manual invalidam trabalho anterior.
Evidências, configuração e limites em `../lab-registration/README.md`. Essa etapa
não acrescenta cliques remotos ao Coletor/Central nem comprova layouts do PPPoker.


## Integração visual da inscrição — 31/10/2026

O fluxo de laboratório agora localiza Registrar/Mais/Menos por template matching
no PNG, sem posições fixas ou busca do botão por ID para obter coordenadas.
A origem do recorte e a razão entre pixels nativos e viewport entram na conversão.
Nova captura/OCR é obrigatória após cada ajuste; desaparecimento sem recibo deixa
a inscrição pendente. O simulador confere modo, revisão e alvo sob a coordenada.

Evidências em `../lab-registration-locator/README.md`. Alta densidade de pixels e
escalas não reconhecidas continuam bloqueadas quando falham nos limiares. Não há
homologação geral de layouts nem controle de entradas no cliente PPPoker real.


## Lobby observacional e abertura de detalhes — 31/10/2026

Novo módulo `visualpilot/lab/lobby.py`: segmentação de cartões do layout de
laboratório, OCR por cartão, soma exata das parcelas do buy-in e filtros explícitos.
Registro desconhecido não significa aberto; custo sem moeda fictícia ou campos
ambíguos não é elegível. O máximo permanece em 50, sem escalada automática.

`lobby_gui.py` abre um cartão por captura, confere novamente pixels/idade/controle
e compara nome, identidade, tipo, custo, stack, horário e registro nos detalhes.
Histórico SQLite evita repetir visitas, inclusive depois de reinício ou resposta
incerta. Evidências e escopo em `../lab-lobby/README.md`. A etapa termina nos
detalhes conferidos; modal, inscrição e entrada em mesa ainda não são ligados a
esse novo caminho. Nenhum comando é enviado ao cliente PPPoker real.

## Controlador integrado de inscrições — laboratório

`RegistrationController` conecta o lobby a detalhes, modal fixo e recibo, usando
os históricos existentes. Reserva antes de confirmar, limita a 50 por inscrição
e quatro vagas, mantém resultados incertos pendentes e respeita pausa/manual.
A confirmação exige recibo correlacionado; fechar o modal não indica sucesso.
Dez cenários de navegador com OCR real passaram; a ambiguidade O1/01 da rodada
inicial está preservada. O fluxo real do PPPoker continua não homologado.
Veja [implementação, evidências e limites](../lab-registration-flow/README.md).
