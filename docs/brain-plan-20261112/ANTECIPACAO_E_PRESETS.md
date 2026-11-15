# Antecipação de leitura, preparação de decisões e presets

Diretriz do usuário em 12/11/2026: priorizar a máquina local; adiar nuvem e Suprema. Meta de escala: primeiro comprovar 1/2/4/6 mesas; 12/16 são etapas futuras, não capacidade demonstrada.

Estado: plano de implementação. Nenhuma nova pré-seleção, aposta ou entrada de mouse habilitada por este documento.

## Causa confirmada e evidência disponível

No commit `ace14f6`, `operar_mesa.py` verifica a linha de botões antes de chamar `advise_table` e executa `continue` quando ela não é `EXPERIMENTAL_BUTTON_ROW`. Assim, não faz a leitura completa das cartas/estado fora da vez do hero nesse caminho. O comentário registra também perda de observação intermediária do agressor. O código deve economizar processamento sem adiar todo o trabalho para a vez do hero.

Os testes desta conversa foram de laboratório. A última suíte completa teve 774 testes, 762 passaram, três falharam nos contratos deep e nove foram pulados. Foram executadas 2.704 consultas de paridade do estudo e sondas de cobertura documentadas nos PRs #3/#4. Não houve medição nova na máquina do usuário nem certificação de latência em seis mesas. Os tempos citados em comentários não substituem instrumentação local de ponta a ponta.

## Fluxo proposto

```text
Captura local por mesa
    → detectar mudança de mão, cartas, board, apostas ou geometria
    → ler/confirmar campos que mudaram
    → atualizar estado e preparar consultas compatíveis
    → guardar resultado com identidade e dependências

Chegou a vez do hero
    → priorizar a mesa pelo prazo disponível
    → conferir identidade, estado, valor a pagar e alvo frescos
    → reaproveitar a parte ainda válida da preparação
    → executar uma intenção serializada ou explicar a pendência
```

Captura, leitura e estratégia não devem parar globalmente enquanto outra mesa movimenta o cursor. O cursor continua tendo um coordenador por desktop; não executar vários movimentos simultâneos.

### 1. Cartas antes da ação

Detectar o início de uma mão e ler as cartas assim que estiverem disponíveis com evidência suficiente. Guardar resultado por identidade da mesa+mão, com origem, confiança e horário. Uma leitura ambígua não vira certeza por estar em cache. Novo ID, identidade pendente, conflito de cartas ou troca de mesa impedem reuso indevido.

Não reler todos os campos de todas as mesas em todos os frames. Usar uma varredura leve e trabalhos acionados por mudança, com concorrência limitada e prioridade aos prazos. ROI visual inalterada pode economizar OCR, mas sua validade depende de identidade, geometria e tempo, não apenas de pixels iguais.

### 2. Preparar políticas, sem presumir ações futuras

Enquanto os adversários agem, preparar consultas para os contextos já conhecidos e, onde útil, ramos possíveis: pote não aberto, limps, open/callers etc. Uma ação nova invalida as dependências afetadas, não necessariamente as cartas já confirmadas da mão.

Chave de preparação: hash do pacote e versão da política, mesa/mão/street, assinatura da história, participantes/posições, stacks relevantes, regras e menu de sizes. Acrescentar board no pós-flop. Valor a pagar e apostas observados precisam ser revalidados na chegada.

Conservar a escolha de um mix pela identidade da decisão, evitando novo sorteio a cada frame. Uma nova ação legítima na mesma mão cria nova decisão. Nenhuma preparação pode transformar contexto aproximado/desconhecido em validado.

### 3. Auto-fold antecipado: política separada

Separar três capacidades:

- Preparar uma recomendação de fold antes da vez: ganho de latência sem input antecipado.
- Executar fold na vez, usando preparação ainda válida e alvo fresco.
- Marcar pré-seleção do cliente: exige implementação e validação específicas da semântica do controle.

O leitor atual identifica `F/C`, `Fold/Check` e `Check/Fold` como `PRESELECT`, com `action=None`. Isso não é um botão de FOLD comum nem está autorizado como se fosse a vez do hero. Implementar auto-fold exige reconhecer marcado/desmarcado, duração da pré-seleção, cancelamento e comportamento quando a ação/mesa/mão mudam. Não reapertar um toggle sem conhecer seu estado.

“Não entra no range de open nem no de call” não basta para justificar um fold irreversível: o cenário pode permitir check grátis, squeeze, reshove ou outra política coberta. Para antecipar esse clique, precisaríamos provar que fold permanece a política aprovada em todos os desdobramentos relevantes ainda alcançáveis no domínio suportado e que a pré-seleção não será transferida a outra mão. Caso contrário, preparar e esperar a vez.

BB com 7–2 suited não implica CALL automático: check quando grátis é diferente de pagar um raise/shove; o valor, os oponentes, os stacks e o contexto importam. SB, BTN e mãos fracas também dependem da configuração; não criar lista universal de mãos descartáveis nem impor abertura mínima de 50% ao BTN. O conjunto elegível vem da política específica, não de uma regra nominal de “lixo”.

Primeiro ganho recomendado: leitura antecipada + fold preparado e conferido na vez. Auto-fold fica em etapa posterior, depois dos testes próprios de pré-seleção.

### 4. Presets como árvore estratégica disponível

Adotar um menu discreto e verificado por cliente/configuração. Exemplos pedidos: pré-flop com 3x/4x onde o menu realmente oferecer; pós-flop com 1/3, 1/2, 2/3 e pote. Esses são candidatos, não presets já comprovados em todas as mesas.

O fluxo deve ser: identificar o menu → restringir a árvore de referência aos sizes aprovados → escolher política compatível → executar o preset → conferir o valor efetivamente selecionado. A política precisa distinguir BB, múltiplo do open, fração do pote e raise-to; o mesmo rótulo não tem necessariamente a mesma unidade em todas as fases.

Não converter automaticamente 3,5bb para 4x nem 6,7bb para o preset mais próximo e manter a declaração de paridade HRC. Resolver/exportar a política com a árvore discreta pretendida, ou avaliar a aproximação separadamente e registrar seu alcance. Uma mão/linha pode mudar de preferência quando o size muda.

O leitor atual `raise_panel.py` interpreta multiplicadores `x`; a existência dessa leitura não comprova leitura de frações do pote no pós-flop. Adicionar contratos e fixtures para esses rótulos, estado do painel, valor selecionado e confirmação. Preset ausente ou ilegível produz pendência, nunca substituição silenciosa por shove. O slider fino deixa de ser caminho padrão apenas onde o preset atende à árvore aprovada.

### 5. Pós-flop preparado por mudança de board

Ao confirmar flop/turn/river, atualizar textura, mão, draws e cálculos reaproveitáveis. Completar range e plano de ação conforme sequência, jogadores ativos, iniciativa, posição e stacks. O board sozinho não determina “c-bet range” nem size; uma aposta/check/call posterior pode invalidar o plano preparado.

No projeto atual, pós-flop continua heurístico e fora da execução operacional homologada. A antecipação melhora o momento do cálculo, não sua validação estratégica. Só chamar uma linha de validada quando houver referência compatível com a árvore de sizes e com aquele contexto.

## Ordem de implementação e aprovação

| Etapa | Entrega | Prova exigida |
|---|---|---|
| A0 | Instrumentação local de captura, leitura, consulta, fila, revalidação e confirmação | Separar tempo ativo de CPU, idade do snapshot, espera e latência de resposta; comparar mesma carga antes/depois |
| A1 | Observação leve + leitura antecipada por mão, sem novos cliques | Ler antes da vez nos replays que permitem isso; ausência de transferência de cartas/contexto em troca de mesa/mão |
| A2 | Cache de preparação com dependências e invalidadores | Mudança de open, caller, stack, board, pacote ou geometria invalida o resultado afetado; cartas confirmadas podem persistir só na mesma mão |
| A3 | Fila de decisões por prazo/idade | Duas/quatro/seis mesas exigindo atenção juntas não perdem observação; um cursor, sem repetir ação vencida |
| A4 | Políticas e execução por presets discretos | Menu, unidades e valor selecionado casam com a referência; casos de size ausente/ilegível não recebem equivalência falsa |
| A5 | Pré-seleção antecipada, se aprovada separadamente | Toggle, persistência, cancelamento, check grátis, mudança de mão e semântica do F/C comprovados em fixtures e cliente |

Construir A1/A2 sobre os contratos de estado, origem e validade do plano principal; não adicionar outro caminho de decisão. Instrumentação e fixtures podem avançar enquanto os ranges P0 são preparados. A4 depende de referências com menus compatíveis; A5 não bloqueia os ganhos de A1–A3.

Cenários obrigatórios: mãos chegando simultaneamente; apostas mudando durante preparação; duas decisões na mesma mão; ID ilegível; intervalo; reconexão; resize; painel aberto; flop chegando antes da primeira observação; board incompleto; novo pacote; pré-seleção já marcada; BB podendo dar check. Usar rótulos independentes e registrar acertos, desconhecidos e decisões incorretas aceitas separadamente.

## Medição na máquina do usuário e escala

Medir: instante em que as cartas se tornam observáveis; confirmação da leitura; início da vez do hero; política disponível; entrada e saída da fila; revalidação; clique/efeito. Publicar percentual de decisões com preparação reaproveitável, invalidações corretas, p50/p95/p99 da resposta, prazos perdidos e contexto incorreto aceito. Ausência de relógio legível significa prazo desconhecido, sem inventar segundos restantes.

Provar primeiro em replay, depois observação passiva na máquina local, com 1 → 2 → 4 → 6 mesas. Orçamento de resposta depende do relógio real e de margem de segurança definida antes do ensaio. 12/16 mesas exigem outra medição de capacidade; aumentar threads ou CPU não elimina a serialização do cursor. Testes sintéticos aprovados não certificam throughput Windows.

O resultado desejado é chegar à vez com cartas e parte do cálculo prontos e fazer somente o trabalho que ainda depende do estado fresco. O relatório deve mostrar melhora de latência sem aumento de contexto errado ou redução oculta de cobertura. Este adendo não afirma que esses mecanismos já estão implementados.
