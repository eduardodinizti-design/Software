# Cinco ciclos — laboratório de uma mesa

Escopo: Linux, replay de imagens gravadas, TCP local, OCR real com limiar de
produção, scheduler, eventos do painel e persistência JSONL. Não é ensaio do
executável Windows nem validação visual do frontend no navegador.

Cada ciclo inclui teste integrado de uma mesa com três cenários: 5c/2s sem
board; Th/4d com flop 7h/As/Ts; mudança controlada do board com Hero inalterado.
O terceiro cenário testa invalidação visual, não simula uma sequência legal.

## Ciclo 1 — referência e recorte

Teste integrado e geometria do host 5760×2160 versus mesa 893×1587.
Resultado: passou; repetição também passou. Nenhuma mudança funcional necessária.
Arquivos: cycle-1.log, cycle-1-repeat.log.

## Ciclo 2 — pacote incompleto

Falha reproduzida em três subcasos de cabeçalho truncado: struct.error.
Ajuste: validar tipo e comprimento antes de interpretar o cabeçalho.
Repetição: pacote rejeitado com ValueError e nenhum estado de mesa alterado;
fluxo integrado passou. Esse caso focal usa entrada direta no parser; o teste
TCP do ciclo 4 cobre conexão inválida pela rede.
Arquivos: cycle-2-before.log, cycle-2-after.log.

## Ciclo 3 — nova sessão sem resultados antigos

Falha reproduzida: mensagem da sessão encerrada permanecia na fila e reaparecia
no painel após start. Ajuste: nova fila e limpeza da pasta da sessão anterior.
O teste de controle isola a criação da thread, não afirma validar UI Windows.

Na primeira repetição, o teste integrado acusou leitura de mão anterior. A
mensagem tinha captura anterior à troca e já estava publicada; corrigimos o
oráculo do teste para comparar capturas do cenário atual, sem relaxar a
verificação das cartas. A repetição final passou nos dois testes.
Arquivos: cycle-3-before.log, cycle-3-after.log, cycle-3-repeat.log.

## Ciclo 4 — reconexão e duplicatas

Socket TCP real: tamanho inválido, reconexão válida, repetição da sequência 1 e
avanço para sequência 2. Verifica identidade única, pixels RGB e fila limitada.
Fluxo integrado repetido junto. Duas execuções aprovadas; sem mudança funcional.
Arquivos: cycle-4.log, cycle-4-repeat.log.

## Ciclo 5 — regressão completa e medição

Ajuste de instrumentação: registrar tempo entre início do cenário e consumo
no teste do primeiro evento parcial/completo. Inclui codificação, TCP local,
decodificação, OCR, filas e polling; não inclui captura de monitor nem navegador.
Não confundir duração da suíte com latência e não inferir p95 de três amostras.
Arquivos: cycle-5-full.log, cycle-5-repeat.log e results.json.

## Critério de interpretação

Passar estes ciclos não homologa o piloto. Ainda faltam execução Windows,
frontend, captura real em diferentes escalas, cobertura de todas as cartas em
Hero/board, turn/river e reconexão entre duas máquinas. Os testes sintéticos
antigos usam 0.75 e não substituem o limiar de produção 0.90 deste teste integrado.
Não foi solicitada atualização nem nova tentativa física ao usuário.

## Fechamento

Suíte completa executada duas vezes: 154 testes em cada execução, sem falhas,
com 3 skips. Durações: 55,193 s e 49,313 s. Os skips incluem subtestes;
a contagem não deve ser apresentada como 154 casos aprovados.

Foram preservados os logs das falhas antes das correções e da repetição
intermediária do ciclo 3. Não foram apagados para produzir aparência de
aprovação contínua. Dois defeitos funcionais corrigidos: rejeição controlada
de cabeçalho truncado e limpeza da sessão do painel. Houve também ajuste
do oráculo temporal do teste e instrumentação dos tempos de entrega.
