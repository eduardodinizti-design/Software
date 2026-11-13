# Auditoria da atualização 5a14169

**Conclusão:** a atualização avançou na organização e nos diagnósticos, mas ainda não cumpre integralmente os Lotes 1 e 2 do plano. A suíte passou; sondas adicionais reproduziram falhas em validade de contexto, replay, roteamento e execução. Leitura antecipada, preparação de decisões e política de presets ainda não foram integradas. Não há homologação nova na máquina local/PPPoker Windows ou capacidade comprovada para seis, doze ou dezesseis mesas.

## Base e escopo

- Repositório `eduardodinizti-design/Software`, branch `fix/audit-a1-a2-safety-gates`, commit auditado `5a1416904d4229bad87995227c226688d8c6fc50`.
- Base da revalidação anterior: `ace14f6efcb799a277f37bb6c3d901155d08d45b`. Nove commits novos, 24 arquivos alterados, 1.785 inserções e 109 remoções.
- `main` permanece em `205dbc7ffbfb5f103dc342f4dfce407a3a27915c`; ela não contém a atualização examinada.
- Critérios: [plano do cérebro, PR #4](https://github.com/eduardodinizti-design/Software/pull/4), [antecipação e presets](https://github.com/eduardodinizti-design/Software/blob/2210101e07df01d28d6506b69505e8d85f059d2d/docs/brain-plan-20261112/ANTECIPACAO_E_PRESETS.md) e [revalidação anterior, PR #3](https://github.com/eduardodinizti-design/Software/pull/3).
- Executor e acesso GitHub confirmados. HEAD, status e `AGENTS.md` lidos antes das alterações. Worktree isolado; nenhuma mudança no motor operacional ou nos checkouts anteriores. `software-review` continua no HEAD `e922e33` com seu trabalho local preservado; `software-current-audit` permanece detached/limpo.
- Ambiente: Linux, Python 3.12.14, venv isolado já utilizado na auditoria anterior, Tesseract 5.5.0 por subprocesso. Não foi aberta sessão Windows/PPPoker.

## Testes e fontes

| Ensaio novo | Resultado |
|---|---|
| `python -m unittest discover -v` | **848 testes: 839 passaram, 9 pulados, nenhuma falha**; 41,087s neste executor |
| Núcleo estrito de estudo | **16 nós / 2.704 consultas / zero divergências** de mix contra o exportado |
| Matriz do advisor | 10 cenários × 169 classes = **1.690 chamadas**, mais cinco sondas de stacks |
| Sondas específicas desta revisão | Falhas descritas abaixo reproduzidas com estados controlados, predicados puros ou adaptadores passivos |

Os nove pulados continuam envolvendo Windows GDI, quatro casos bright-rank Karekas, river Karekas, dois casos de lobby real e painel real. Não interpretar suíte verde como validação de todas as integrações. As mensagens negativas esperadas de captura ao final do log não representam falhas adicionais.

Pacote das sondas: `strategy_sources/nvt-356340d/nvt-ranges-validados.json`, branch `data/nvt-ranges-356340d`, commit `8c7f585cabf0b53217c9001988de52c387fb5153`; SHA-256 `c8fc3f0716df16fdeb2cff509814e3ca3c1ec31c05d479da2122db3ec531fcdc`. Tem 5.007 nós, todos 9-max, stacks 5/8/10/12/15/20/25bb. O arquivo HRC/NVT atualizado no Windows do usuário continua sem identificação por hash nesta sessão. Os números desta auditoria não são atribuídos àquele arquivo local.

Logs, matrizes e JSONs em [evidence](evidence). O script `probe_update.py` é passivo: mocks, predicados e arquivos temporários; não controla cliente nem mouse real. As mãos e cenas sintéticas não são novas amostras de produção.

## Atendimento às orientações anteriores

| Frente | Situação observada | Avaliação |
|---|---|---|
| B01 — arquivos e hashes | `manifest()` informa caminhos, SHA-256, engine e contagens; startup os exibe | **Avanço real**, falta associar cada nó ao pacote proprietário |
| B02 — conflitos | Conflitos registrados; validado vence referência; `strict=True` rejeita ambiguidade | **Parcial:** merge usado pelo operador tem `strict=False` e mantém a primeira fonte no empate |
| B03 — explicar consulta | Novo `explicar_preflop.py` e `explain()` | **Parcial:** explica `advise()`, não a decisão completa após adaptações de limpers/fallback; lista hashes de todos os arquivos |
| B04 — contrato | Campos separados e autoridades explícitas; fallback não fabrica mais `validated=True` | **Parcial:** `context_match` não compara os contextos; premium ainda pode pagar sem solução; RAISE segue caminho separado |
| B05 — ligação à fonte | Testes de alteração, conflitos, empréstimo e nó ausente | **Passaram no escopo testado**, faltam casos pelo caminho completo de decisão |
| B06/B07 — estado e sequência | Classes novas com identidade e replay | **Laboratório parcial**, sem integração no operador; regras ainda aceitam eventos inválidos |
| B08 — cenário único | `classify()` discrimina limps/callers e é chamado pelo adaptador | **Parcial:** o adaptador volta a colapsar esses cenários na consulta antiga |
| B09 — observação contínua | `ContinuousObserver` existe com cinco testes | **Não integrada:** não há uso fora do módulo e dos testes; estado perde callers em uma sonda |
| Leitura antes da vez | Fast-path continua pulando `advise_table` fora da vez | **Pendente** |
| Presets como árvore validada | Ajuste da base do multiplicador foi feito; nearest preset e slider persistem | **Parcial**, sem menu pós-flop por fração e sem paridade estratégica do arredondamento |

Portanto, os títulos de commits “fecha Lote 1/2” descrevem entregas de componentes; ainda não demonstram cumprimento de todos os critérios funcionais e de integração daqueles lotes.

## Achados priorizados

### F1 — P1 — Contexto multiway ainda recebe autorização de nó HU

Em [preflop_advisor.py](../../preflop_advisor.py#L101), `classify()` reconhece `open_with_callers`, mas `infer_live_spot()` o converte em `vs_open`. A consulta usa somente a posição do opener; dois callers entram como aviso.

Na sonda BTN/25bb, UTG open 2,5bb + HJ call + CO call, as 169 classes mantiveram o mesmo nó/mix/recomendação do cenário sem callers. Para AQs, o retorno foi CALL; [decision_contract.py](../../decision_contract.py#L68) marcou `context_match=True`, autoridade `VALIDATED` e `execution_allowed=True`.

O contrato deriva correspondência de `status=ADVICE` e ausência de flags de fallback/empréstimo, sem comparar o cenário solicitado à árvore da fonte. Ler duas cartas válidas também não confirma sozinho posições, apostas, histórico ou número de jogadores.

**Implementar:** correspondência explícita de contexto e evidência por campo; nó HU não autoriza cenário multiway. Separar referência válida, suporte estratégico do cenário e prontidão operacional. Unificar os requisitos no CALL e no sequenciador de RAISE, que hoje só verifica `validated` no operador.

### F2 — P1 — Size fora dos presets pode virar all-in

[raise_panel.py](../../raise_panel.py#L127) considera shove qualquer alvo sem preset compatível que exceda o maior preset ×1,15. A função não recebe o stack nem a intenção all-in. Com presets 2/2,5/3/4x, alvo **6x** foi classificado como shove. Um raise de 6bb com 60bb atrás é um exemplo de intenção que não corresponde a all-in; a função não dispõe dos dados para distingui-lo. O sequenciador usa esse predicado para decidir arrastar a barra ao máximo.

É uma pendência herdada da base `ace14f6`, agora reproduzida, e não uma regressão introduzida nestes nove commits. A prova foi do predicado; não enviamos arrasto nem medimos o comportamento no cliente.

**Implementar:** all-in explícito na intenção, size/stack efetivo e valor final conferíveis. Size sem preset não deve virar shove por magnitude. Usar árvore de referência compatível com o menu discreto.

### F3 — P1 — Rotina “Sair” ignora pausa e transforma falha de captura em sucesso

A função nova [_close_tournament_table](../../operar_mesa.py#L58) usa `move_to`/`click_once` diretamente, condicionada a `args.arm`. O caminho não consulta `BotControl`, não passa pelo controlador de intenção e não relê alvo/identidade imediatamente antes do clique. O loop pode chamá-la mesmo pausado.

Reprodução passiva: controle em `PAUSED`, adaptador registrador, `armed=True` e recaptura devolvendo `None`. Resultado: **um clique simulado e `closed=True`**. Perder a captura não prova que a mesa fechou. O conjunto `tourneys_closed` ainda marca a origem como consumida mesmo quando o fechamento falha e não inclui identidade do torneio; reutilizar a mesma origem pode omitir eventos posteriores.

O detector também aceitou uma cena sintética sem textos Ranking/Sair — apenas banner azul e dois retângulos verdes. Isso demonstra que a confirmação textual descrita no docstring não é exigida; não mede taxa real de falso positivo.

**Implementar:** gate de pausa/disable também para rotinas auxiliares, intenção e revalidação de alvo, identidade do torneio, evidência suficiente de tela final e resultado desconhecido quando a recaptura falha. Não repetir automaticamente clique com resultado desconhecido. Acrescentar testes negativos realistas de outros painéis.

### F4 — P2 — Limps agora recebem cap heurístico, mas não política própria

`classify()` retorna `limped`, porém o adaptador o transforma em `first_in`. A nova regra `_iso_worthy()` restringe raises aos que aparecem no open UTG. Na matriz, o cenário com dois limps mudou de 93 raises/76 folds na base para **48 raises/121 folds**, sem overlimp. Isso é mudança de política, mas não solução de isolamento validada.

Para **K6s**, a saída final foi `recommended=fold`, conservando `mix=[raise 1.0]` e `validated=True`. EV, nó e mix continuam descrevendo a fonte anterior à intervenção. Portanto, o diagnóstico não representa fielmente a recomendação executada.

**Implementar:** política de iso/overlimp por cenário; quando uma heurística modifica a recomendação, preservar fonte original e registrar política derivada sem manter validade de solver. O CLI explicável precisa percorrer o mesmo caminho que produz a recomendação operacional.

### F5 — P2 — Novo replay não implementa as invariantes anunciadas

[strategy/action_sequence.py](../../strategy/action_sequence.py#L30) não reutiliza a reconstrução estrita existente: é outra implementação, que reutiliza apenas utilitários como `amount()` e posições. As sondas retornaram `status=OK` para:

- BTN agir antes de UTG/CO sem folds anteriores;
- pagar 0,1bb quando devia pagar 1bb;
- raise não all-in para 1,2bb após BB de 1bb;
- evento `all_in` pagando 5bb de um stack de 40bb;
- posts + ante de 0,1bb: pote retornou 1,5bb em vez de 1,6bb, `chip_conservation=False`, ainda com `status=OK`.

Ante é descontado do stack e não entra nas contribuições usadas para calcular pote/conservação. As regras de ordem, call, reabertura e tipo all-in também estão incompletas. Os testes novos cobrem rótulos positivos, mas não esses contratos negativos.

**Implementar:** reaproveitar o núcleo estrito de regras e ampliá-lo com testes; separar total contribuído de aposta da street, incluindo antes; rejeitar ou manter pendente inconsistência. Validar ação do próximo jogador e direitos de reabertura por jogador, não só um booleano global.

### F6 — P2 — Dados ausentes podem ser apresentados como pote não aberto

`classify({})` retornou `scenario=unopened`, `hero_position=None` e `supported=True`. `from_table_state()` substitui apostas ausentes por zero, apagando a distinção entre “nenhuma aposta voluntária” e “não foi possível ler”.

O advisor tem algumas travas adicionais, como posição desconhecida, portanto isso não demonstra execução real a partir de uma observação vazia. Demonstra que o classificador não cumpre o contrato de pendência por evidência ausente.

**Implementar:** máscara de campos conhecidos/confirmados, identidade e turno; ausente não é zero. Separar suporte da estrutura de suporte da estratégia. Não usar nomes de “ações legais” para opções cuja legalidade ainda não foi reconciliada.

### F7 — P2 — Módulos de estado e observação não alimentam a operação

Pesquisa de usos no código Python encontrou `HandState`/replay apenas no módulo e testes, e `ContinuousObserver` apenas no módulo e testes. Não são instanciados por `operar_mesa.py`, `table_advisor.py`, `assistir_mesa.py` ou `observar_estado.py`.

Além disso, em uma mão: `open_with_callers` com dois callers → frame seguinte só com opener. O observer trocou para `open` e zero callers, sem `retained_history`. Seu escore dá o mesmo peso aos dois cenários e permite perder informação. Retenção monotônica de um rótulo também não substitui história de eventos com confiança e confirmação.

**Implementar:** adaptar observação leve ao estado por mesa/mão e demonstrar o caminho integrado. Enquanto faltar essa integração, “B09 implementado” significa componente de laboratório, não leitura contínua durante o turno dos adversários.

### F8 — P2 — Rastreabilidade melhorou, mas ainda não identifica o proprietário exato do nó

O manifesto e o modo estrito são avanços. Entretanto, `from_files()` usa `strict=False` por padrão, e o operador não o altera. Dois nós validados conflitantes ainda mantêm a primeira fonte; agora existe registro de colisão, portanto não é mais um descarte totalmente silencioso. A sonda sintética confirmou esse comportamento; não confirma colisão nos arquivos Windows reais.

`explain()` lista hashes de todos os pacotes e procura o primeiro nó pelo ID na lista, em vez de carregar a associação entre nó escolhido e arquivo proprietário. A explicação direta não inclui todas as adaptações feitas por `advise_from_reading()` e pelo operador. O startup registra resumos, mas não substitui trilha de proveniência por decisão.

**Implementar:** proprietário por nó/chave, resolução de conflito configurada e auditável, diffs de política e suporte de contexto. Fonte HRC bruta, exportador NVT e suas transformações continuam requisitos separados da paridade com o arquivo exportado.

### F9 — P2 — Premium mantém exceção de CALL; a validade agora é mais honesta

O fallback deixou de fabricar `validated=True`: passou a usar `validated=False` e `safety_premium=True`, com autoridade `SAFETY_PREMIUM`. Isso corrige a rotulagem anterior. Porém, o contrato ainda autoriza CALL por essa autoridade, exigindo apenas cartas válidas/botão e caminho single-click, sem resolver o contexto estratégico, custo, ICM ou range adversário.

O código registra essa escolha como “Opção A do usuário”. Esta auditoria não altera uma preferência eventualmente estabelecida fora desta conversa; registra que a exceção persiste e não constitui cobertura estratégica validada. `CALL_OFF` também continua como autoridade separada por margem, sem tornar a aproximação de equity uma solução exata.

**Implementar:** política de contingência explícita, limitada e configurável, com razões e limites verificáveis; não contar esses calls como acertos de nós validados. Uma classificação nominal TT+/AQ/AK não comprova a qualidade do call em todo cenário.

### F10 — P2 — Métrica ITM usa percentual fixo inventado

[tournament_metrics.py](../../tournament_metrics.py#L37) define ITM por `placed <= field // 5`, equivalente a aproximadamente 20% do field, sem consultar quantos lugares são pagos. Na sonda `40/272`, `itm=True` sem payout ou evidência de premiação. Isso pode contaminar a análise futura do próprio cérebro. O ranking pode ser útil; posição no dinheiro exige estrutura real de premiação.

**Implementar:** `itm=None` enquanto não houver lugares pagos ou recibo de premiação; guardar método/origem e não inferir ROI sem buy-in/custos/retorno. O registro atual também precisa de identificador persistente do torneio e deduplicação por evento, não só por coordenada de mesa.

## Antecipação e presets: o que falta implementar

O foco continua a máquina local. Nuvem e adaptação Suprema são frentes futuras.

| Etapa | Situação atual | Próxima entrega verificável |
|---|---|---|
| A0 — medir | Logs funcionais; sem distribuição de latência local de ponta a ponta | Tempo de cartas observáveis, leitura pronta, início da vez, fila, revalidação e efeito; p50/p95/p99 e prazos perdidos |
| A1 — ler antes da vez | **Não integrado:** `continue` do fast-path permanece antes de `advise_table` | Confirmar cartas/identidade assim que disponíveis; observar mudanças sem rodar toda a estratégia sempre |
| A2 — preparar e invalidar | Cache de cartas/HUD não é cache de política contextual | Resultado preparado por mão/street/história/stacks/hash/menu; aposta nova invalida dependências, não necessariamente cartas |
| A3 — atender simultaneidade | Round-robin sequencial; cursor único | Observação/cálculo seguem durante atendimento de outra mesa; fila por prazo/idade com cancelamento de intenção vencida |
| A4 — presets aprovados | Multiplicadores x; correção da base do open; aproximação nearest com tolerância | Menu real por fase/unidade, política resolvida/exportada com esses sizes, leitura do valor final e nenhuma conversão indevida em all-in |
| A5 — pré-seleção | F/C ainda é PRESELECT, não FOLD comum | Fixtures de toggle marcado/desmarcado, persistência, cancelamento e troca de mão; liberar só após critério independente |

**Presets pré-flop:** documentar os 2/2,5/3/4x efetivamente presentes e a unidade do multiplicador; plano para sizes de iso/squeeze e shove explícito. A correção nova do divisor evita usar um blind lido abaixo de 1bb como base do open, mas não valida automaticamente toda equivalência de sizing.

**Presets pós-flop:** o leitor atual não interpreta 1/3, 1/2, 2/3 e pote como frações; o regex reconhece multiplicadores x. Implementar rótulos, unidades, valor escolhido e árvores de estratégia correspondentes. Não arredondar um size de solver e continuar chamando a execução de paridade exata. O pós-flop operacional permanece desabilitado e heurístico; nenhum arquivo pós-flop mudou nesta atualização.

**Fold antecipado:** primeiro preparar cedo e conferir na vez. Marcar pré-seleção é capacidade separada. Fora do range de open não significa fold universal; BB pode ter check grátis e outros cenários podem permitir call/squeeze. “Mão lixo” não dispensa política contextual nem identidade.

**Escala:** provar 1 → 2 → 4 → 6 mesas na máquina local, incluindo ações simultâneas e mudanças durante preparação. 12/16 seguem como objetivo, sem throughput certificado nesta auditoria.

## Sequência recomendada de correção e implementação

1. **Conter execução indevida:** F1/F2/F3; contrato central também no RAISE e nas rotinas auxiliares. Testes passivos negativos antes de qualquer nova execução Windows.
2. **Concluir o núcleo do Lote 2:** replay correto, informação ausente preservada e eventos/observação ligados ao estado. Revalidar 3bet/4bet e perder frames sem inventar certeza.
3. **Concluir diagnóstico e cobertura:** fonte proprietária por nó, política derivada separada da fonte; referências específicas para limps/callers/iso/squeeze. O cap UTG atual não encerra essas células.
4. **Implementar A0–A3:** instrumentação, leitura antecipada, cache contextual e fila. Medir melhoria em replay e depois observação passiva local.
5. **Implementar A4:** menus discretos e soluções com sizings compatíveis. A5, auto-fold, vem depois da prova de pré-seleção e não bloqueia ganhos de antecipação.
6. **Pós-flop e Hand2Note:** importação offline pequena e contínua, aliases de heroes, deduplicação e máscara da informação futura; construir casos de teste e referências correspondentes. Nesta atualização não há importador Hand2Note nem referência pós-flop nova demonstrada.
7. **Uma sessão Windows organizada:** conferir percepção, identidade, menús, pausa/takeover e latência com carga progressiva. Não transformar os 848 testes Linux em declaração de homologação real.

Critério de saída: redução de erro aceito **e** crescimento de cobertura exata, com explicação auditável da decisão final. Acrescentar nomes de módulos e passar testes que só repetem os rótulos não encerra os critérios do plano.

## Reprodução

Na raiz do checkout `5a14169`, com dependências do projeto em venv:

```bash
python -m unittest discover -v
python -m tools.validate_preflop_study --ranges /caminho/nvt-ranges-validados.json --output /tmp/parity.json
PYTHONPATH=. python docs/audit-update-5a14169/probe_update.py --pack /caminho/nvt-ranges-validados.json
PYTHONPATH=. python docs/audit-update-5a14169/probe_matrix.py --pack /caminho/nvt-ranges-validados.json --output /tmp/matrix.json
```

Os scripts de sondagem imprimem o comportamento observado; não corrigem os defeitos nem certificam decisões de poker. A matriz compara classes no mesmo pacote; rótulos sintéticos de ordem/regra testam contratos e não a exatidão da visão. Nenhuma falha reproduzida aqui foi corrigida silenciosamente nesta auditoria.
