# Controlador integrado de inscrição — laboratório

O fluxo une lobby, detalhes, modal de preço fixo e recibo. Executa uma navegação
por ciclo e usa `LobbyHistory`, `RegistrationLedger` e `LabControl` existentes.
Não cria um segundo histórico de inscrições nem marca sucesso pelo fechamento
do modal. Não executa comandos no desktop ou no PPPoker.

## Componentes

- `visualpilot/lab/registration_controller.py`: `RegistrationController` com
  `execute_cycle()` e `set_mode('paused'|'manual'|'automatic')`.
- `registration_flow_gui.py`: adaptador que captura PNG e faz OCR real; localiza
  Registrar/Confirmar pelos limites do texto reconhecido, verifica imagem,
  geometria, idade e revisão antes de consumir cada coordenada uma única vez.
- `registration_flow_simulator.html`: página isolada de torneios fictícios,
  com detalhes, modal fixo, rejeição e recibo. O DOM valida estado e ponto atingido;
  não fornece coordenadas nem campos de decisão ao OCR.
- `tools/check_registration_flow.py`: ensaio visual reproduzível em Chromium.
- `tests/test_registration_controller.py`: regras de fluxo e falhas injetadas.

## Transições e persistência

1. Conferir controle automático e obter nova captura do lobby.
2. Filtrar até 50 por inscrição, alvos e tipos configurados; abrir um único cartão
   não visitado/reservado/inscrito. Conferir detalhes pelo fluxo existente.
3. Recapturar detalhes, conferir nome, ID, tipo, custo, stack, início e estado de
   inscrição; ler oferta e bounty explicitamente na página de laboratório.
4. Abrir modal e comparar novamente todo esse contexto. Nenhum ajuste de custo
   é feito: as referências do usuário não mostram seletor mais/menos.
5. Reservar custo e vaga atomicamente no SQLite, fora do lock do controle manual.
   Máximo de quatro vagas. Reservas sem resultado também ocupam vaga e orçamento.
6. Revalidar controle e frescor depois da reserva e antes de Confirmar.
7. Registrar resultado somente com recibo legível, token correlacionado e
   torneio/oferta/custo iguais aos reservados. Contabilizar um recibo válido mesmo
   que o usuário pause após o envio.

O adaptador espera a etapa da página por até dois segundos, sem clicar após um
`sleep` fixo. Capturas devem ter no máximo cinco segundos. As esperas/OCR ficam
fora do lock de controle; um comando alterado invalida a observação anterior.

Resultados: `confirmed`, `rejected`, `blocked`, `unknown` ou `empty`. Exceção,
recibo ausente, custo divergente ou correlação errada depois de reservar mantêm
o registro como `reserved`, nunca como sucesso. Se o adaptador retorna `False`,
seu contrato garante que nenhum clique ocorreu: essa reserva vira `rejected`.
Exceções do adaptador não são tratadas como prova de que não houve clique.

Uma segunda execução concorrente no mesmo controlador é bloqueada. A proteção
entre instâncias vem das transações e identidades únicas dos históricos existentes.
O histórico de visitas também persiste: ciclos interrompidos após a seleção não
repetem automaticamente a mesma visita. Retomar exige nova observação; uma oferta
incerta requer revisão/reconciliação explícita, cuja interface ainda não foi criada.
Para repetir um ensaio do laboratório, use uma nova pasta/banco, sem apagar evidências.

## Limites

O banco de inscrições existente aceita valores inteiros de fichas. A composição
`28.34 + 14.16 + 7.50` soma 50 e é aceita; um total de 49,99 fica bloqueado, sem
arredondar ou mudar a unidade do banco. O orçamento acumulado vem de
`RegistrationRules.max_session_cost` (200 na configuração padrão de laboratório).

A página fictícia exibe ID e oferta no modal e fornece correlação com o recibo.
Esses campos **não estão presentes dessa forma nas imagens reais do PPPoker**.
Ainda faltam PNGs originais para ensaio de OCR real, comprovação da continuidade
da navegação no cliente, identificação de um recibo real e homologação Windows.
O parser de referência real permanece observacional, com `can_register=False`.
Este controlador não transforma aquelas imagens em autorização executável e não
implementa cliques entre os dois computadores.

## Executar

```sh
PYTHONPATH=. python -m unittest discover -s tests -p test_registration_controller.py -v
PYTHONPATH=. python tools/check_registration_flow.py --output diagnostics/registration-flow/nova-rodada
```

Dependências do projeto e de `requirements-lab.txt`, mais Chromium. A pasta de
saída precisa estar vazia. Cada cenário guarda PNGs, OCR, ações, SQLite e resultado.

## Evidência inicial e resultados

O primeiro ensaio com oferta `O1` chegou a Confirmar, mas o OCR leu `01` em uma
tela. O recibo divergente deixou a reserva pendente. Esse ensaio está preservado
em `initial-o1/`; não houve correção automática de letras/números nem redução de
confiança. Os cenários positivos seguintes usam `P1`. Isso não certifica a leitura
de identificadores ambíguos, nem deve ser usado para escondê-los em produção.

Os testes unitários cobrem persistência, custo fracionário, limite de vagas,
controle manual durante OCR/espera no banco, expiração após reserva, rejeição,
recibo divergente/ausente, correlação errada e contabilização após pausa.

A rodada visual final passou nos **dez cenários em 45,728 s**, sem erros JavaScript.
[Relatório e evidências](browser/report.json). Os 15 testes novos do controlador
passaram em 0,048 s. A rodada inicial com O1 permanece em
[initial-o1/report.json](initial-o1/report.json).

A [regressão completa](regression.log) executou **422 testes em 134,037 s**, sem
falhas, com três casos ignorados por imagens de referência ausentes.

Os auxiliares de seleção, validação e clique foram extraídos e integrados ao fluxo.
Veja [contratos e validação da atualização](HELPERS.md).
