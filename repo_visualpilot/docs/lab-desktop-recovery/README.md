# Captura e reorganização de mesas — trabalho de 30/10/2026

Evidência recebida do usuário: o notebook estava em `192.168.68.102`, enquanto
o Coletor apontava para o endereço de exemplo. Após corrigir o endereço, o usuário
confirmou uma prévia atualizando por 30 segundos. Três mesas estavam visíveis,
mas só uma era recebida inicialmente. Reorganizar as janelas deixou registros
congelados e duplicados. A captura enviada da Central mostra idades de 141 e
94 segundos. O ZIP inicial, da sessão 22:53:26, possui zero quadros recebidos;
foi substituído pelo arquivo correto descrito abaixo.

Atualização: a sessão correta, 22:57:36, recebeu 2.377 quadros verificados sem
rejeições de transporte. Foram registradas 105 publicações parciais e quatro
chaves de mesa, mas nenhuma publicação consolidada. Há 79 erros de processamento
contabilizados, sem suas mensagens no formato antigo. As rejeições registradas
foram 34 por idade, 159 por geração substituída e 72 por uma imagem nova pendente.
Esses dados não permitem determinar a exceção original dos 79 erros. O runtime
passa a preservá-la em `erros_ocr.jsonl`, inclusive quando o resultado é descartado.

O teste adicional de parada revelou espera pela conexão TCP antes de fechá-la.
A Central agora encerra os clientes antes de aguardar o fechamento do servidor,
permitindo parar a coleta enquanto o Coletor ainda está conectado.

O log de inicialização confirmou outro problema: porta 8501 ocupada. O launcher
agora verifica a porta antes de consultar a saúde do servidor e informa o motivo
na mensagem de erro, evitando confundir a instância antiga com a nova.

## Alterações

- Coletor com configuração visível, mensagens de conexão/captura e contadores.
  Os estados são persistidos em `collector_status.json` e `collector.log`.
- Configuração de exemplo exige preenchimento. A conexão é verificada mesmo
  quando não há mesas detectadas. Erros finais do observador são consumidos.
- Cada quadro pode informar a lista de mesas da descoberta e sua geração.
  A Central retira registros substituídos somente após validar a imagem e seu
  ticket. Listas atrasadas, conflitantes ou de quadros expirados são recusadas.
  Uma lista de um membro não remove mesas de outro membro.
- Uma mesa identificada apenas pela posição pode receber uma nova chave após
  se mover. A lista substitui o registro anterior sem fingir que houve prova de
  identidade. O vínculo nativo existente continua preservando chaves quando
  identifica a mesma janela.
- A lista enviada contém somente recortes detectados na descoberta atual.
  Manter uma janela compartilhada aberta não mantém recortes antigos no painel;
  um teste reorganiza três regiões dentro do mesmo host e verifica essa retirada.
- O laboratório revelou bordas de cartas escurecidas com componentes separados
  cujas caixas se sobrepõem por um pixel. Ambos os leitores aceitam essa geometria
  mantendo os critérios de valor e naipe. A busca do board também tolera um pequeno
  deslocamento vertical no recorte visual estimado.

## Verificação e limite de entrega

`tools/validate_desktop_distribution.py` abre uma mesa gravada em uma janela real,
executa os pontos de entrada normais e confere captura do sistema operacional,
TCP, OCR, diário e painel no navegador. Inclui configuração incompleta, Central
desligada, desktop vazio, Hero ausente, mudança de mão, reinício, três mesas,
movimento e retirada das duplicatas. Não injeta frames no Coletor.

O build Windows exige esse teste antes de publicar o candidato. A selagem exige
resultado Windows aprovado para o hash de ambos os executáveis e de seus arquivos
internos. A validação local Linux não equivale à validação Windows, nem comprova
a conexão entre os dois computadores físicos. Não recomendar uma nova instalação
até a execução Windows correspondente passar.

Resultados detalhados e capturas são gravados em `diagnostics/desktop*/` e
publicados como evidências pelo workflow. A validade temporal de cinco segundos
permanece inalterada.

Resultados locais finais: 333 testes em 133,273 s, sem falhas, com três omissões
por imagens ausentes já documentadas. Após ajustar o encerramento do launcher
para evitar uma segunda janela de erro do PyInstaller, seus seis testes passaram
novamente. O percurso de desktop passou nos 11 critérios em código-fonte Linux
e nos executáveis Linux finais em 1920×1080. O teste usa captura MSS, TCP e OCR
reais; as mesas exibidas são fixtures gravadas. Não é uma execução Windows.

- [Relatório resumido do código-fonte](source-linux.json)
- [Relatório resumido dos executáveis finais](frozen-linux.json)
- [Desktop com três mesas](desktop-three-tables.png)
- [Painel após movimentar as três mesas](central-three-tables-after-move.png)

A execução Windows do novo build ainda precisa ser confirmada. O acesso à API
do GitHub continua retornando `Forbidden` neste ambiente.

O ZIP correto não inclui as capturas das três mesas do usuário. Os cenários
locais usam imagens de referência do repositório; ainda não demonstram por que
o layout físico inicial dele detectou apenas uma mesa. A captura de todos os
monitores com esse layout continua necessária para reproduzir essa parte.
