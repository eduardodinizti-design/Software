# Etapa 2 — atualização, identidade e descarte de leituras antigas

Foi executada a segunda etapa por autorização do usuário, sem aprovar a etapa 1,
que permanece com cobertura incompleta do baralho colorido. Esta rodada trata da
consistência temporal do software, não da precisão do OCR nem de segurança de rede.

## Falhas reproduzidas e corrigidas

1. O consolidador aceitava resultados vencidos se a limpeza periódica não tivesse
   sido chamada. Agora confere a validade na entrada de cada resultado.
2. Uma captura nova na Mailbox ainda podia não ter incrementado a geração quando
   o último resultado parcial chegava. O resultado antigo podia ser publicado.
   Agora a fila é conferida antes de consolidar e novamente na publicação; entrada
   de quadros e emissão compartilham uma seção crítica curta.
3. Leituras parciais não tinham a mesma barreira de cinco segundos da leitura
   completa. Ambas agora rejeitam uma fonte vencida. Uma captura idêntica mais nova
   não renova artificialmente a data do trabalho OCR que ainda está em andamento.
4. O cache atingia o limite de 20 reusos, mas o marcador `scheduled` impedia o novo
   OCR. Agora o limite realmente dispara revalidação. Reuso de cache exige igualdade
   dos pixels completos, além da assinatura das regiões.
5. O painel podia substituir uma leitura nova por um evento antigo. Agora compara
   geração e instante observado. Uma leitura parcial não rebaixa a consolidada da
   mesma fonte. Uma nova geração invalida os dados apresentados e o intervalo de
   botões do monitor até haver uma leitura atualizada.
6. A resposta assíncrona da estratégia precisava ser filtrada tanto no evento quanto
   no Future retornado ao chamador. Ambos agora retornam pendência se a observação
   tiver vencido, sido substituída, removida ou estiver ausente. Uma resposta válida
   continua sendo apenas consultiva: `action_authorized=False`.

## Rastreabilidade adicionada

Leituras e diários identificam mesa, geração, época da mesa, SHA-256 dos pixels,
instante monotônico da entrada na fila, sequência do transporte e sessão do coletor
(quando disponíveis). Os hashes usam a mesma definição do arquivo de evidências.
Contexto externo pode enriquecer um snapshot, mas não substituir seus campos observados.

Tempos registrados separadamente:

- `queue_seconds`: espera do trabalho até começar;
- `processing_seconds`: execução daquele trabalho, incluindo espera pelo serviço OCR;
- `source_age_seconds`: idade da fonte original;
- `observed` / `validated_observed`: quadro usado ou quadro idêntico que revalidou o cache.

Nas leituras parciais, `timing.job_kind` e `timing.region` identificam o último
trabalho que completou o lote; não representam a soma do OCR de todas as regiões.
O arquivo `rejeicoes.jsonl` registra identidade, motivo e idade dos trabalhos recusados.
A métrica antiga `latencies` permanece compatível e mede entrada/publicação, não
somente tempo computacional do OCR.

## Evidências da rodada

- `before.log`: sete testes iniciais; seis falhas e um erro de metadados ausentes.
- `cache-before-fix.log`: reprodução da revalidação de cache que não acontecia.
- `strategy-future-before.log`: reprodução do resultado obsoleto retornado diretamente.
- `latest/tests.log` e `latest/status.json`: 16 testes direcionados, com resultados
  por teste, horários, identificação da execução e hashes dos arquivos testados.
- `full-regression.log`: resultado da suíte completa na versão final.
- `full-regression-initial.log`: primeira suíte ampla, antes dos últimos testes e
  da proteção do retorno direto da estratégia.

Os testes direcionados usam relógio e serviço OCR controlados para reproduzir os
atrasos de forma determinística. A suíte ampla também executa TCP local e OCR reais
com capturas gravadas do padrão anterior: troca de mão, mudança só do board, turn,
river, escalas 1,25/1,5, silêncio de 5,3 segundos e reconexão em três ciclos por caso.
Isso não equivale a validação ponta a ponta do novo baralho colorido.

## Como executar e acompanhar

```sh
python tools/check_freshness_lab.py --output docs/lab-freshness/latest
python -m unittest discover -s tests -v
```

O primeiro comando atualiza `status.json` durante a execução e termina ao concluir
uma rodada. `completed` significa execução encerrada; não significa um trabalhador
continuando em segundo plano. Processo encerrado abruptamente pode deixar um estado
`running` antigo; o horário e o PID permitem investigar. Não foi criado agendamento
contínuo nem um agente que altere o código sozinho fora desta sessão.

## Limites e pendências

- A idade é medida **a partir da fila da Central**. O protocolo atual não comprova
  quanto tempo decorreu entre a captura no coletor e essa entrada. Para autorizar
  ações futuras será necessário um mecanismo de validade de ponta a ponta.
- A assinatura de mudança em trabalhos em andamento usa as regiões calibradas;
  regiões mal calibradas continuam dependendo da etapa 1. Cache completo usa todos
  os pixels, mas isso não corrige automaticamente uma calibração incorreta do OCR.
- Uma leitura parcial pode não ter `hand_id`; ela permanece explicitamente sem
  identidade de mão verificada e sem autorização para ação.
- Uma imagem congelada retransmitida com novas sequências exige teste específico
  da etapa 3. Igualdade de pixels não comprova que o jogo ao vivo está parado.
- O filtro da estratégia foi validado com uma estratégia controlada. A integração
  remota real não foi habilitada nem usada nestes testes.
- Não houve execução no Windows físico, instalação no notebook ou emissão de
  aprovação irrestrita da etapa 2. As etapas 3, 4 e 5 não foram concluídas aqui.

## Resultado final desta rodada

- **16 testes direcionados aprovados.**
- **294 testes na suíte completa: 291 aprovados, três ignorados**, em 122,131 s.
- As três omissões são imagens ausentes das fixtures anteriores, não aprovação
  implícita desses casos.
- Testes de atualização local aprovados no escopo documentado; etapa operacional
  completa permanece pendente de validade ponta a ponta e validação física.
- Rodada encerrada. O registro automático não deixa um processo em segundo plano.
