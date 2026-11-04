# Rebuy e add-on: fundação do laboratório

**Esclarecimento posterior do usuário:** a grade enviada era apenas exemplo, não programação
aprovada para aquele dia. O CSV é um rascunho ilustrativo arquivado, sem efeito operacional.
Faixas10–20 ou até50fichas são ideias configuráveis, não regras finais. O foco atual voltou à
inteligência de mesa e às simulações de pré/pós-flop.

`visualpilot/lab/tournament_purchases.py` é isolado do cliente e do sistema operacional. Não clica
em aplicativos. `parse_addon_popup` reconhece somente linhas OCR de um template controlado de
pop-up isolado, com título, custo explícito em fichas fictícias, fichas recebidas e botão.
Não há validação do OCR de um pop-up real do PPPoker; texto incompleto/ambíguo fica pendente.

Regras implementadas:
- Rebuy apenas em torneio cadastrado como bounty, no máximo1por torneio, mínimo50BB recebidos.
- Add-on simples no máximo1por torneio; limite mínimo BB separado e opcional, sem herdar50BB.
- Orçamento total inclui inscrição, compras confirmadas e compras pendentes.
- Reserva persistente SQLite antes da execução simulada, com exclusão concorrente.
- Resultado incerto continua reservado após reiniciar; não autoriza novo clique.
- Recibo explícito identifica torneio, operação, preço e fichas. Pop-up sumir não é confirmação.
- Rejeição explícita libera orçamento; nova tentativa exige novo ID de oferta.
- Pausa/fechamento da oferta impedem novas reservas. Integração de cancelamento de ações já
  disparadas fica fora do módulo; ele não possui executor de cliques.

O orçamento é entrada obrigatória. Ofertas exigem identidade, fonte laboratório e fichas fictícias
comprovadas no contexto. A implementação não identifica moeda a partir do valor numérico.

Validação: oito testes direcionados passaram, incluindo persistência, concorrência, orçamento,
limite50BB, recibos incorretos, pausa, oferta expirada e leitura incompleta. Veja `targeted.log`.
Não foi repetida a suíte inteira: este módulo novo não é importado pelo runtime existente.

## Exemplo da grade diária enviada

`grade_diaria_preselecao.csv` é uma transcrição manual parcial para planejamento, não saída de OCR.
A data-base29/10/2026 usa o contexto de data local da conversa, não uma data impressa na imagem.
A colunaB foi interpretada provisoriamente como entrada; valores/unidades e modalidades precisam
ser confirmados antes de importar regras operacionais. A declaração de fichas fictícias vem do usuário.

A pré-seleção não é a lista definitiva: não contém todos os horários da imagem, não calcula duração
dos torneios, não libera inscrições e não estabelece limite de mesas. Não há horários de add-on nem
fichas recebidas, portanto o critério50BB de rebuy não pode ser avaliado pela grade.
Os eventos00h no fim da lista foram marcados como dia seguinte, sujeitos à convenção da grade.

Uma grade diária não vira programação recorrente. O planejamento final deve incluir orçamento,
modalidades autorizadas, prioridade, horário de entrada, fim de novas inscrições e limite de mesas.
