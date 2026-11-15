# Plano de evolução do cérebro VisualPilot

Data: 12/11/2026. Base operacional analisada: `fix/audit-a1-a2-safety-gates`, commit `ace14f6efcb799a277f37bb6c3d901155d08d45b`.

**Objetivo:** transformar conhecimento de referência em decisões rastreáveis para cenários explicitamente suportados. Primeiro provar que o motor consulta a fonte correta para o estado correto; depois expandir a estratégia. O projeto não precisa simular décadas de aprendizado humano para isso: pode reutilizar soluções existentes, reconstrução de estado e testes exaustivos dos contextos declarados. Aprendizado automático não é pré-requisito para corrigir o roteamento atual.

Este documento é um plano proposto, com backlog e critérios de conclusão. Não implementa as mudanças nem habilita ações. O código operacional e os ambientes anteriores permanecem preservados.

Diretriz adicional do usuário: priorizar funcionamento na máquina local, leitura antes da vez, preparação de decisões, fila para mesas simultâneas e menus discretos de sizing. O detalhamento, as condições para pré-seleção e os critérios de capacidade estão no [adendo de antecipação e presets](ANTECIPACAO_E_PRESETS.md). A meta 12/16 mesas permanece futura e não homologada.

## 1. Diagnóstico que orienta o investimento

A revalidação anterior está em [PR #3](https://github.com/eduardodinizti-design/Software/pull/3). Com entradas estruturadas corretas, dois limps foram encaminhados ao mesmo nó/mix de first-in; open com dois calls recebeu o mesmo nó/mix de enfrentar um opener. A contagem de 169/169 refere-se às classes testadas no BTN 25bb com o pacote versionado identificado, não ao arquivo atualizado no Windows nem à prova de que todas as ações coincidentes seriam ruins. A lacuna é aplicar um contexto como se fosse outro.

Há três causas que precisam ser medidas separadamente: percepção incorreta, cenário sem representação/cobertura e consulta/uso inadequado da fonte. Corrigir somente OCR ou acrescentar arquivos de ranges não resolve as três.

O pacote usado na avaliação está no commit `8c7f585cabf0b53217c9001988de52c387fb5153`, branch `data/nvt-ranges-356340d`, caminho `strategy_sources/nvt-356340d/nvt-ranges-validados.json`. SHA-256 `c8fc3f0716df16fdeb2cff509814e3ca3c1ec31c05d479da2122db3ec531fcdc`. O arquivo HRC/NVT atualizado hoje e salvo no computador do usuário ainda não foi identificado por hash. Não tratar esses dois arquivos como equivalentes.

Não descartar os ranges existentes nem concluir que o HRC está errado sem comparar o mesmo nó, configuração e transformação. O plano precisa localizar em qual ponto se perde a fidelidade:

```text
Fonte HRC → transformações NVT → arquivo ativo → estado da mão
          → contexto solicitado → nó selecionado → mix/sizing → recomendação
```

## 2. Base já existente que será reaproveitada

- [preflop_study.py](../../preflop_study.py): `reconstruct()` valida ações fornecidas, turno, fichas, pote e pagamentos. `RangeBook` exige contexto exato, identifica arquivo por hash, rejeita nó ambíguo e separa validação da fonte de validação independente. Hoje é simulação, chip EV e pote não aberto; não liberar ao vivo simplesmente removendo essas restrições.
- [tools/validate_preflop_study.py](../../tools/validate_preflop_study.py): verificador de paridade com o exportado. Reexecutado neste planejamento: **16 nós × 169 classes = 2.704 consultas, zero divergências**. São exemplos derivados da própria fonte, úteis para fidelidade de consulta, não holdout nem validação do solver.
- [test_preflop_study.py](../../test_preflop_study.py): 19 testes reexecutados, todos passaram.
- [state_observer.py](../../state_observer.py) e [table_reading/hand_reconcile.py](../../table_reading/hand_reconcile.py): aproveitar identidade, evidência e pendências; o reconciliador já reconhece que diferenças entre snapshots não provam uma sequência completa de ações.

A arquitetura será consolidada gradualmente: extrair contratos compartilhados do estudo e ampliar suas capacidades em testes, preservando a separação de evidência simulada e observação real. Não criar um terceiro caminho de decisão divergente.

### Novo achado: atualização pode ser ocultada por conflito de pacotes

[preflop_advisor.py](../../preflop_advisor.py) concatena nós em `from_files()`, mas `_index.setdefault()` conserva o primeiro nó de cada chave. Reproduzido com dois nós sintéticos conflitantes: `[OLD, NEW]` selecionou OLD/raise; ordem invertida selecionou NEW/fold. Carregou dois nós, indexou uma chave, sem erro. O `engine_commit` global também permanece o do primeiro pacote.

Isso demonstra um mecanismo que pode fazer uma atualização parecer ignorada. **Não prova que os arquivos atuais do usuário têm essa colisão.** O inventário do primeiro lote resolve a dúvida. Script e resultado estão em `evidence/lookup_collision_probe.py` e `evidence/lookup-collision.json`.

## 3. Primeira entrega: provar que os ranges são usados corretamente

**Este é o primeiro lote de implementação recomendado. Não depende de resolver milhares de novos cenários.**

| Tarefa | Entrega | Critério de conclusão |
|---|---|---|
| B01 — identificar fontes | Manifesto dos arquivos realmente carregados: caminho, SHA-256, engine/exportador, ordem de carga, origem por nó, cobertura de stacks/posições/cenários | O log mostra qual arquivo atende cada nó; arquivo de hoje só é chamado de ativo após confirmar seu hash |
| B02 — resolver colisões | Inventário de chaves e política explícita de conflitos | Nós divergentes para a mesma chave não são escolhidos silenciosamente; duplicatas equivalentes têm deduplicação registrada; precedência configurada é explícita |
| B03 — consulta explicável | Comando offline de diagnóstico, evoluindo `simular_preflop.py`: contexto solicitado, nó encontrado, contexto da fonte, diferenças, mix, EV disponível e motivo da resposta | Cada recomendação possui fonte, hash e nó; toda aproximação mostra exatamente a diferença |
| B04 — separar validade | Contrato com `source_validated`, `context_match`, `observation_confirmed`, `action_legal`, `sizing_supported` e autorização de execução separada | O operador não pode transformar ABSTAIN em decisão validada; margem de call-off ou rótulo premium não substituem os demais requisitos |
| B05 — provar ligação da fonte | Testes de paridade, conflito, atualização e ausência de cenário | Nó conhecido reproduz a linha da fonte; mudança controlada da política em fixture aparece na consulta; conflito é explícito; nó inexistente não recebe validade emprestada |

Uma atualização pode manter a mesma ação recomendada legitimamente. A prova de atualização usa hash, nó e mix, não exige que todo arquivo novo mude raise para fold. Os testes com políticas conflitantes usam fontes artificiais rotuladas e não ensinam poker.

O arquivo Windows ausente bloqueia a identificação do que foi usado naquela sessão, mas não bloqueia a implementação dos contratos, testes de conflito e replay com a referência versionada.

## 4. Segundo lote: o cérebro precisa representar a situação

Dependência: contratos B01–B05 definidos. Estado e preparação de fontes podem avançar em tarefas independentes.

| Tarefa | Entrega | Critério de conclusão |
|---|---|---|
| B06 — estado por mão | Identidade persistente de mesa/mão; participantes iniciais; jogadores ainda ativos; stacks iniciais/atuais; contribuições; pote; ordem; eventos confirmados | Fichas conciliadas; jogadores que foldaram não desaparecem da história; snapshot de outra mão não contamina o estado |
| B07 — sequência de ações | Replay de limp/call/raise/fold/check/all-in, quantidade de aumentos e direito de reabrir | Diferencia open, 3bet e 4bet com histórico confirmado; sequência ausente/ambígua permanece pendente, sem inventar quem agiu |
| B08 — classificador único | Cenário explícito, posição dos envolvidos, quantidade de limpers/callers, sizes, vetor de stacks, regras e fase | Dois limps não se tornam pote não aberto; callers não desaparecem da consulta; ações legais são consistentes com o estado |
| B09 — observação contínua leve | Separar detecção de mudanças e atualização de estado do cálculo pesado da estratégia | A otimização de pular cálculo fora da vez do hero não descarta automaticamente a história observável |

Não assumir que um vídeo amostrado permite recuperar todas as ações. Se duas sequências explicarem os mesmos pixels, o resultado não é contexto confirmado. Underraise all-in, reabertura incompleta, side pots, antes e blinds especiais precisam de testes de regras próprios; casos ainda sem implementação ficam explicitamente fora do suporte.

## 5. Terceiro lote: cobertura estratégica por cenário

Dependência: classificador e consulta auditável. Preparar/exportar referências pode ocorrer enquanto o estado é implementado, sem integrar política sem contexto.

| Prioridade | Estado enfrentado pelo hero | Ações a avaliar na política, conforme as regras |
|---|---|---|
| P0 | Pote não aberto | fold, open raise, open shove; limp onde a árvore o contempla |
| P0 | Um, dois e três ou mais limps | fold, overlimp, iso raise, iso shove; check no BB quando grátis |
| P0 | Open sem caller, com um caller e com dois ou mais | fold, call/overcall, 3bet/squeeze, reshove |
| P1 | Limp seguido de raise de isolamento | fold, call, reraise/shove; considerar limpers que ainda podem agir |
| P1 | Hero abriu e enfrenta 3bet; hero não entrou e enfrenta open+3bet | políticas distintas, sem confundir defesa de open e cold action |
| P1 | Hero fez 3bet e enfrenta 4bet; shove HU/multiway | call/fold/raise quando legais, stacks efetivos e cobertura por oponente |
| P2 | ICM/PKO e variações deep/short-handed | cenários com payouts/bounties, antes e stacks correspondentes |

Squeeze e overlimp são ações possíveis de cenários, não substitutos da descrição da sequência. Duas situações diferentes podem ter a mesma ação ótima; o requisito é justificar a ação com contexto e política compatíveis.

O primeiro exemplo de desenvolvimento será: BTN, 25bb, chip EV, dois limpers identificados, comparado com a mesma configuração sem limpers. Ele aproveita a reprodução já disponível e deve retornar política específica ou `UNSUPPORTED`, nunca validade first-in. Em seguida: UTG open 2,5bb + HJ call + CO call, hero BTN 25bb. Esses exemplos são testes de referência, não a afirmação de que todos os torneios operacionais são 9-max/25bb.

Antes de produzir a expansão inteira, fixar o recorte operacional a partir dos torneios usados: tamanho de mesa, stacks frequentes, antes, fases e sizings. Ausência de métricas de uso não vira frequência inventada. No início, priorizar as situações relatadas pelo usuário e coletar contagens de decisões sem salvar imagens continuamente.

Para cada célula: referência HRC/NVT identificada, árvore e tamanhos conhecidos, ações legais, 169 classes ou resolução de combos quando a fonte exigir, mix, EV quando disponível e condições de aplicação. O sizing deve ser compatível com a árvore; adicionar 1bb por limper não cria um range de isolamento. Usar o stack efetivo e a distribuição dos stacks do modelo, não simplesmente o stack do hero.

Heurísticas e aproximações podem continuar como ferramentas de estudo, com política explícita e avaliação própria. Não herdam autorização operacional de um nó resolvido em outro contexto. Células ainda sem solução são registradas, sem impedir a evolução das células independentes.

O marco de ganho funcional não será apenas abster mais ou impedir cliques: os dois cenários P0 relatados precisam chegar a uma política própria sustentada pela referência, com comparação para as 169 classes. Se faltar solução no RangeLab/HRC, essa ausência gera tarefa de produção de referência, e não declaração de que o cérebro está concluído. Medir simultaneamente redução de erro aceito e crescimento de cobertura exata.

## 6. Duas fidelidades diferentes: NVT e HRC

Há documentação de que o exportado NVT aplica ajustes sobre suas fontes; portanto, igualdade com o NVT e igualdade com o HRC bruto são verificações diferentes. O histórico do projeto cita filtros de frequências, ajustes por EV e regras de ICM/PKO. Não presumir que o exportador atual mantém as mesmas transformações.

| Porta de qualidade | O que comparar | O que a aprovação significa |
|---|---|---|
| Q1 — integridade | schema, ordem das mãos, unidades, frequências, somas, EVs ausentes, chaves e arquivos | O pacote é legível e não tem inconsistência estrutural aceita silenciosamente |
| Q2 — paridade com NVT | consulta vs linha do exportado no mesmo contexto | O motor aplica o conteúdo exportado corretamente |
| Q3 — procedência HRC | exportado vs saída HRC bruta e transformações documentadas | As diferenças são explicadas por política versionada; aprovação não se presume pelo nome HRC |
| Q4 — contexto | estado reconstruído/classificado vs histórico e rótulos independentes | A política é consultada para a situação correta |
| Q5 — qualidade estratégica | política vs referência correspondente, com EVs comparáveis quando existentes | A decisão respeita o padrão declarado naquele domínio; não prova lucro universal |
| Q6 — integração | replay temporal/pixels, depois observação Windows | O caminho real preserva identidade, estado e decisão sob condições efetivamente testadas |

Manifesto mínimo: hash da fonte HRC; solver/versão; jogadores; stacks do modelo; antes; árvore/sizings; payouts/bounties quando aplicáveis; caminho do nó; versão NVT/exportador; transformações aplicadas e seus diffs; hash do exportado; unidade e semântica de EV; origem por nó. Um cenário `table.stacks` presente no JSON não prova que aquele vetor de stacks foi resolvido na fonte; conferir compatibilidade com o modelo HRC original.

Misturas: distinguir apresentar o mix, recomendar a ação mais frequente e amostrar a política. A implementação atual escolhe argmax; isso não reproduz o mix ao longo das mãos. Se a política escolhida exigir amostragem, usar gerador reproduzível e fixar a escolha por identidade da decisão, sem sortear novamente a cada frame. Uma nova ação legítima na mesma mão gera nova identidade; não confundir deduplicação com limite universal de uma ação por mão.

## 7. Medidas de evolução e critérios de aprovação

- **Seleção:** contexto solicitado, contexto encontrado, hash/nó e status `EXACT`, `APPROXIMATE`, `UNSUPPORTED`, `AMBIGUOUS` ou fonte inválida. `EXACT` significa correspondência com o contrato do artefato, não validação independente do solver.
- **Cobertura:** proporção de requisições elegíveis com suporte exato, aproximação e abstenção, com denominadores explícitos. Separar contextos desconhecidos por percepção de contextos conhecidos sem range. Sem logs representativos, publicar cobertura da matriz de teste e não taxa de produção.
- **Fidelidade:** divergências de mix/EV/sizing contra a mesma referência. Meta de paridade é nenhuma divergência inexplicada nos casos declarados; tolerâncias numéricas documentadas quando houver transformação/arredondamento.
- **Erro crítico:** contexto incorreto aceito como exato, ação ilegal, fonte conflitante escolhida silenciosamente ou fallback promovido a validado: nenhum caso aceito no conjunto obrigatório. Aprovar esse conjunto não equivale a garantir erro zero em produção.
- **Qualidade estratégica:** perda de EV somente quando ações e EVs são comparáveis na mesma árvore/modelo. EV ausente permanece desconhecido. Não usar taxa de acerto, lucro de poucas mãos ou contagem de testes verdes como substituto.
- **Operação:** idade do snapshot, latência de ponta a ponta, caudas p95/p99, fila, timeouts e resultados desconhecidos. Definir orçamento a partir do relógio disponível e testar simultaneidade; não certificar seis mesas a partir do tempo de uma consulta.

Conjunto de provas em camadas: exemplos sintéticos de regras e contratos; paridade exaustiva nos nós cobertos; históricos rotulados independentemente; pixels e sequências de desenvolvimento; fontes separadas de avaliação; uma sessão Windows passiva organizada. Uma captura com variações de tamanho não se torna várias mãos independentes.

## 8. Integração e entrega em lotes

1. **Lote 1: B01–B05.** Diagnóstico reproduzível do arquivo realmente utilizado e da seleção de nó; conflitos explícitos; contrato de validade definido e nenhum fallback fabricando aprovação. Fonte Windows identificada é requisito para explicar aquela sessão, não para concluir os testes genéricos.
2. **Lote 2: B06–B09.** Estado e classificação dos cenários P0; regressões dos dois limps e open com callers; testes de 3bet/4bet e ambiguidade. Cenários sem referência permanecem sem suporte estratégico.
3. **Lote 3: referências P0.** Importar/resolver apenas as células prioritárias ausentes; testar HRC→NVT e NVT→consulta separadamente. Incrementar o mesmo caminho compartilhado do estudo, sem habilitar o caminho de simulação no cliente.
4. **Lote 4: integração passiva.** Leitor → estado → consulta em modo de observação, sem entrada de jogo; comparar com rótulos independentes e relatório de divergências. Corrigir percepção com gabaritos, sem alterar a estratégia apenas para fazer uma imagem passar.
5. **Lote 5: desempenho e revisão operacional.** Medir 1/2/6 mesas, decisões simultâneas, perda de frames e recuperação. Qualquer habilitação de execução é decisão separada, limitada aos cenários aprovados, com contratos e evidências Windows próprios.

Cada lote termina com diff revisável, teste específico, regressões afetadas, relatório de suporte/limites e uma publicação consolidada. São lotes de desenvolvimento, não promessas de prazo. Inventário da fonte e tempos de exportação/solução permitem estimar esforço antes de marcar datas. Preparação de referências e testes de regras podem ocorrer em paralelo; integração do mesmo núcleo continua sequencial.

## 9. Organização proposta do código e responsabilidades

Nomes propostos, a confirmar na implementação: `strategy/contracts.py`, `strategy/hand_state.py`, `strategy/scenarios.py`, `strategy/range_repository.py`, `strategy/policy.py` e `strategy/decision_gate.py`. Extrair/reutilizar funções existentes e manter adaptadores temporários com testes de equivalência; não duplicar a lógica em uma versão V2 permanente.

- Engenharia: estado, consulta, manifestos, contratos e observabilidade.
- Laboratório RangeLab/HRC: arquivos de referência, configurações, transformações e cobertura por cenário.
- Validação: expectativas independentes, divergência, cobertura e replay. O mesmo classificador não gera seu próprio gabarito.
- Usuário: confirmar quais artefatos/torneios representam o uso pretendido e revisar diferenças de política explícitas. Localizar arquivos e calcular hashes deve ser automatizado, sem depender de recordar flags de uma sessão antiga.

O critério de maturidade será: **para cada situação suportada, o sistema mostra o estado, a fonte, o nó, a política aplicada e a prova de que pertencem ao mesmo contexto; para o restante, explica o que falta.** Não é necessário resolver todos os cenários de poker para concluir a primeira melhoria útil, mas é necessário parar de apresentar cenários diferentes como se fossem a mesma solução.

## Evidências deste planejamento

Novas execuções: 19 testes do núcleo estrito, 2.704 consultas de paridade com a referência versionada e reprodução sintética de conflito de índice. A suíte completa de 774 testes e as 1.690 sondas do advisor são resultados da revalidação anterior, disponíveis no PR #3, e não foram contados como novas execuções aqui. Não houve teste Windows/PPPoker nem mudança do motor operacional neste lote.

Para reproduzir a base e o novo achado, em checkout `ace14f6`, a partir da raiz:

```bash
python -m unittest test_preflop_study -v
python -m tools.validate_preflop_study --ranges /caminho/nvt-ranges-validados.json --output /tmp/parity.json
PYTHONPATH=. python docs/brain-plan-20261112/evidence/lookup_collision_probe.py
```

A fonte versionada usada nas 2.704 consultas tem o hash informado no início; outro arquivo pode ter cobertura e contagens diferentes. O código de colisão é passivo e artificial, sem recomendação de poker ou acesso ao cliente.
