# Laboratório de inscrição e seleção de fichas

Data: 31/10/2026. Implementado com o limite confirmado pelo usuário: **50 fichas
fictícias por inscrição**, separado do stack recebido, e até quatro torneios
simultâneos. O fluxo funciona no simulador de navegador criado nesta rodada.
Não foi conectado a cliques no PPPoker nem ao transporte de comandos entre PCs.

## Atualização: localização visual integrada

A rodada seguinte remove a localização por ID do botão do caminho de execução:
coordenadas vêm de templates no PNG, com correção da origem do recorte e da escala
entre pixels e viewport. O simulador só confere o alvo atingido antes de aplicar
a ação. Evidências e limitações de DPI/escala em
[lab-registration-locator](../lab-registration-locator/README.md). Os números e
capturas abaixo permanecem como histórico da primeira rodada.

## Mapeamento

| Arquivo | Responsabilidade |
| --- | --- |
| `visualpilot/lab/registration.py` | Parser estrito, filtros, limites, ajuste incremental, pausa/manual, reserva SQLite e recibo |
| `visualpilot/lab/registration_gui.py` | Captura PNG do popup próprio, OCR real, evidências e ação condicionada à revisão da interface |
| `visualpilot/lab/registration_simulator.html` | Popup fictício com Mais/Menos/Registrar, confirmação, pausa e controle manual |
| `tools/check_registration_lab.py` | Ensaio automatizado de navegador, OCR e inscrições simuladas |
| `tests/test_registration.py` | Casos negativos, concorrência, persistência e fronteiras de controle |

`RegistrationLedger` reutiliza o ledger de compras já existente. Uma entrada
confirmada registra custo e bounty explicitamente lidos; rebuy e add-on continuam
com suas políticas anteriores. Antes, o ledger dependia de registro prévio feito
por código; agora há um fluxo de inscrição simulada com evidência visual.

## Contrato do fluxo

1. Ler identidade do torneio e oferta, tipo, bounty, custo, stack, limites e passo
   do seletor. Todos os campos obrigatórios exigem confiança mínima de 0,95.
2. Verificar torneios alvo, tipo, stack mínimo e custo permitido. O alvo deve ser
   alcançável pelo passo informado. O seletor recebe valores inteiros positivos.
3. Aplicar um incremento/decremento e capturar novamente. Se o resultado não for
   exatamente o esperado, parar; não insistir em clique sem progresso.
4. Ao ler o valor alvo, reservar orçamento e vaga em transação SQLite antes da
   inscrição. Revalidar idade da observação e revisão do popup antes da ação.
5. Confirmar apenas mediante recibo explícito com torneio, oferta e custo iguais,
   correlacionado ao pedido no simulador. Sumir o popup não é confirmação.

O orçamento de sessão aqui contabiliza **inscrições**, incluindo reservas sem
resultado conhecido. O padrão de demonstração é 200 fichas, configurável por
`max_session_cost`; não substitui o orçamento de entrada/rebuy/add-on por torneio
em `tournament_purchases.py`. O limite por inscrição é `max_entry_cost=50` e o de
vagas `max_simultaneous=4`. Também há `targets` (até quatro IDs), `allowed_types`
e `minimum_stack`. `target` é o custo a selecionar, que pode ser menor que 50.

Resultado desconhecido mantém vaga e custo reservados após reinício. Uma oferta
já vista não é reenviada; recusa explícita permite nova oferta com novo ID.
`finish(token)` representa encerramento explícito no laboratório: libera vaga,
mas não devolve o custo gasto ao orçamento da sessão. Não há reset automático.

Pausa, tomada manual ou retomada alteram a revisão de controle, invalidando OCR
em andamento. A espera pelo banco não mantém o bloqueio do controle; uma mudança
durante a reserva impede a ação seguinte. A próxima execução exige nova observação. Um recibo de ação já
enviada ainda é contabilizado se a pausa ocorrer depois do envio. Os botões
manuais do HTML são controles do simulador, sem integração de compras manuais ao
ledger. O fluxo automatizado usa o adaptador para reservar e contabilizar.

O adaptador só carrega a sua página em branco e altera o DOM dessa página. Não
usa mouse/teclado do SO, coordenadas do PPPoker ou conteúdo de outra URL. Uma
mudança de revisão do popup entre OCR e ação bloqueia o clique simulado.
Capturas vencem após cinco segundos; existe limite de 20 ajustes por execução
(configurável até 100), com uma leitura final para conferir o último ajuste.

## OCR: falhas preservadas e correções

As primeiras leituras estão em `probe/` e `probe-28/`. A linha do passo ficou
abaixo de 0,95. O adaptador passou a reler o recorte desse campo: só aceita a
confirmação se o texto coincidir, desconsiderando espaços, e a confiança aumentar.
Não reduz o limiar nem troca dígitos conflitantes. O diário guarda as duas leituras.
O popup sintético final usa fonte de 28 px; isso não certifica outras escalas.

A rodada em [before-spacing-fix/report.json](before-spacing-fix/report.json)
parou em 25 fichas, sem registrar, porque o OCR produziu `Custo:25fichas ficticias`.
O parser agora tolera espaço ausente junto ao rótulo e à unidade, preservando a
estrutura numérica. `5 0`, `50/100`, `5O`, valores negativos/decimais e campos
duplicados ou pouco legíveis continuam bloqueados.

## Resultados de validação

- Regressão geral: **375 testes**, sem falhas, três ignorados por imagens ausentes
  ([log](regression.log)).
- Depois das últimas proteções para campos duplicados e tomada manual durante a
  reserva: **15 testes direcionados**, todos aprovados ([log](targeted-final.log)).
  Esse conjunto inclui os 12 casos de inscrição já presentes na regressão geral
  e três casos adicionais; as contagens não devem ser somadas como casos distintos.
- Navegador com PNG e OCR reais: oito cenários, com relatório e capturas na pasta
  `browser/`. Conferir [relatório](browser/report.json) e
  [recibo de 50 fichas](browser/increase-10-to-50/final.png).

Os oito cenários cobrem incremento 10→50, decremento 60→50, seletor sem progresso,
custo malformado, tomada manual durante OCR, popup substituído antes da ação,
recusa explícita e quatro inscrições com bloqueio da quinta. Os testes direcionados
acrescentam reserva concorrente, orçamento, recibos incompatíveis, expiração,
persistência sem confirmação, limites/filtros e pausa após envio com contabilização.

## Executar no laboratório

Na raiz deste checkout, com dependências do projeto e de `requirements-lab.txt`:

```sh
PYTHONPATH=. python -m unittest discover -s tests -p test_registration.py -v
PYTHONPATH=. python tools/check_registration_lab.py --output diagnostics/registration/nova-rodada
```

O segundo comando exige Chromium e Playwright. `--chromium` permite indicar o
executável; o padrão do laboratório Linux é `/usr/bin/chromium`. Usar pasta de
saída vazia. São salvos PNGs, textos/confianças OCR, SQLite e relatório de ações.
O HTML pode ser aberto para explorar manualmente o seletor; o fluxo automático
com OCR é executado pelo script. Nenhuma captura do PC do usuário é necessária.

## Limites de validação

O valor é ajustável neste popup fictício. Isso não pressupõe que um torneio real
permita alterar o seu buy-in. Ainda faltam layouts independentes, outras escalas,
integração visual com o painel principal, comandos distribuídos e validação no
Windows. A rodada não comprova registro em software externo nem jogabilidade
autônoma. Transporte PNG, observação de mesas e motores pré/pós-flop permanecem
nos caminhos anteriores; o novo fluxo é exclusivo de laboratório.
