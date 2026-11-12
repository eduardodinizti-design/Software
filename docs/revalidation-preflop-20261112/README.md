# Revalidação do cérebro pré-flop — 12/11/2026

**Veredito:** houve evolução de integração e correções, mas o motor ainda não representa adequadamente limps múltiplos, open com callers e sequências de raises. Não é apenas um problema de OCR. Com leitura perfeita fornecida diretamente à lógica, esses cenários continuam sem uma política específica. Não considero este motor pronto para administrar autonomamente o pré-flop completo de torneios.

## Versão, método e limites

- Branch confirmada pelo usuário: `fix/audit-a1-a2-safety-gates`, HEAD `ace14f6efcb799a277f37bb6c3d901155d08d45b`. A `main` continua em `205dbc7ffbfb5f103dc342f4dfce407a3a27915c`.
- Comparação com a main: dois commits, 24 arquivos, 1.463 inserções e 74 remoções. Em `preflop_advisor.py`, a diferença é apenas a lista de buckets: remove 100 e acrescenta 30. A lógica de decisão com limpers/callers permaneceu igual. `preflop_context.py` recebeu correções temporais, o que é uma evolução distinta.
- Novo worktree isolado, HEAD e status verificados, `AGENTS.md` lido antes de escrever. Checkouts anteriores preservados. Sem alteração de código operacional, apostas ou inscrições.
- Laboratório Linux, Python 3.12.14, dependências do venv da auditoria anterior; OCR Tesseract 5.5.0 por subprocesso. Nenhuma sessão Windows/PPPoker foi executada nesta revalidação.
- Além da suíte completa, forneci estados estruturados controlados, sem OCR, ao advisor: 10 cenários × 169 classes de mão = 1.690 chamadas, mais cinco sondas de profundidade. Não são 1.690 mãos reais nem uma certificação de estratégia ótima.
- Pacote disponível no GitHub: `data/nvt-ranges-356340d`, commit `8c7f585cabf0b53217c9001988de52c387fb5153`, arquivo `strategy_sources/nvt-356340d/nvt-ranges-validados.json`. SHA-256 `c8fc3f0716df16fdeb2cff509814e3ca3c1ec31c05d479da2122db3ec531fcdc`, engine `356340d`, gerado em 06/11/2026.
- O usuário informou que acredita usar arquivos HRC/NVT atualizados hoje, salvos no Windows. **Esse arquivo local não foi identificado nem recebido.** O CLI aponta para caminhos externos ao repositório (`C:\Meus Projetos\Aplicativos\...`). Os resultados numéricos abaixo pertencem ao pacote versionado identificado acima, não a uma cópia presumida do arquivo Windows. A conclusão sobre o roteamento do código independe dessa identidade.

## Resultados executados

| Verificação | Resultado |
|---|---|
| Suíte completa `python -m unittest discover -v` | 774 testes: 762 passaram, 3 falharam, 9 pulados |
| Rerun isolado das três falhas | As três falharam novamente |
| Bounty 135 da auditoria anterior | Os três testes da fixture passaram nesta execução |
| Matriz pré-flop | Resultados completos em `evidence/preflop-matrix.json` e resumo em `evidence/matrix-summary.json` |
| Fallback do operador | Bloco exato extraído por AST, executor substituído por registrador passivo; evidência em `evidence/fallback-probe.json` |

As três falhas estão em `test_preflop_advisor`: `test_bucket_stack` e `test_above_solved_depth_uses_100bb_reference` esperam bucket 100, mas recebem 40; `test_unvalidated_deep_node_is_flagged` espera ADVICE e recebe ABSTAIN. A política de profundidade mudou sem atualizar todos os contratos e testes. As duas primeiras diferenças podem ser intencionais; não são prova de que 100 seja o bucket correto. A inconsistência entre código, teste, documentação e arquivos efetivamente carregados precisa ser resolvida.

Os nove pulados permanecem os da auditoria anterior: GDI Windows, quatro bright-rank Karekas, river Karekas, dois lobby real e painel real. `docs/ACHADOS_TESTE_AO_VIVO_12NOV.md` relata testes anteriores no Windows e problemas de percepção. Esses relatos são contexto; não os contei como validação nova. Mensagens negativas esperadas de captura no rodapé da suíte não são falhas adicionais.

## 1. Dois limps não têm range próprio — confirmado sem OCR

Em BTN, chip EV, stack do hero 25bb, comparei pote não aberto com UTG limp 1bb + HJ limp 1bb. `count_limpers` contou 2 corretamente, mas `infer_live_spot` retornou `first_in`. Nas **169/169 classes**, nó, mix, ação recomendada e `validated` foram iguais aos do pote não aberto. Resultado: 93 classes com raise, 76 com fold e **nenhum limp behind**. Essas contagens são por classe, sem ponderação dos combos.

O sizing de raise sobe de 2bb para 4bb e acrescenta `LIMPERS_PRESENT_OPEN_AS_ISO_APPROX`. Isso não cria um range de isolamento. O nó segue marcado `validated=True` no cenário testado, embora o contexto com limpers não tenha sido resolvido por aquele nó. O operador pode tratar essa validade como autorização para executar o raise.

**Conclusão:** mesmo que a percepção passe a ler todos os limps, a política de raise/overlimp/fold continuará incompleta. Q9o não é universalmente fold após limp: posição, stacks, jogadores restantes e perfil importam. A falha demonstrada é a ausência dessa diferenciação, não a afirmação de uma ação ótima universal para Q9o.

## 2. Open + dois calls usa o mesmo range de enfrentar apenas o opener

Comparei UTG open 2,5bb com UTG open 2,5bb + HJ call + CO call, hero BTN 25bb. A lógica detecta `callers=2`, mas consulta o mesmo nó `vs_open` contra UTG. Nas **169/169 classes**, nó, mix, recomendação e `validated` foram idênticos aos do cenário sem callers: 13 classes com three_bet, 26 call, 7 all_in e 123 fold.

O aviso `MULTIWAY_2_CALLERS_APPROX_VS_OPEN` não modifica a política nem revoga `validated=True`. Também não há ajuste do tamanho da 3bet pela quantidade de callers no caminho de sizing. Não é um motor de squeeze/overcall/reshove multiway; é uma referência HU aplicada a outro cenário.

O pacote examinado tem 5.007 nós, mas somente nove famílias de spot: open_raise, open_shove, vs_open_shove, 3bet_shove, vs_open, vs_3bet, limp, limp_call e vs_limp. Quantidade de nós não equivale a cobertura de sequências. Não há família explícita de squeeze ou overlimp no arquivo. Os nós limp/limp_call não são selecionados pelo roteamento observado desses dois limps; `vs_limp` está reservado à batalha BB contra limp do SB.

## 3. Muitas ações exigem histórico, não só apostas de um frame

Open 2,5bb seguido de 3bet 8bb, sem contribuição do hero: 169/169 classes abstiveram com `MULTIWAY_OR_3BET_NOT_COVERED` na sonda. Isso é uma lacuna honesta de cobertura, não uma recomendação poker errada.

Hero já apostou 8bb e enfrenta 20bb: o classificador chamou o cenário de `vs_3bet`, mesmo quando a sequência fornecida como hipótese era hero 3bet → vilão 4bet. Um frame com valores atuais não prova a sequência; não é possível reconstruí-la corretamente em todos os casos. O motor precisa distinguir contexto desconhecido de histórico confirmado.

Há ainda um trade-off novo: o fast-path do operador pula `advise_table` quando não é a vez do hero. Isso economiza trabalho, mas também deixa de alimentar o tracker com ações intermediárias. O comentário do próprio código reconhece essa perda. Não removê-lo simplesmente para rodar OCR pesado sempre: separar observação leve e persistente de cálculo estratégico pesado.

## 4. O fallback premium transforma ausência de solução em CALL “validado”

O operador contém uma regra de contingência: se faltar recomendação e a mão for TT+, AK ou AQ, substituir fold por call. O novo dicionário recebe `validated=True`, sem nó/range/EV que sustente essa decisão.

Extraí e executei o bloco exato por AST, sem iniciar o CLI e com um executor passivo. Entrada: AQo, ABSTAIN por cenário fora da cobertura, botão CALL de 100bb e ausência de CHECK. Saída produzida pelo bloco: `ADVICE / call / validated=True / fallback=True`. Nenhum clique foi enviado.

O bloco não avalia valor do call, ranges, número de jogadores, stacks efetivos ou ICM. A prova não estabelece que AQo deve sempre foldar naquele custo; demonstra que o call é autorizado sem resolver o contexto que provocou a abstenção. “Nunca foldar premium” não é uma política estratégica válida para todo torneio. Anti-timeout precisa ser uma política explicitamente limitada, e não fabricar validação.

## 5. Profundidade, tamanho de mesa e stack efetivo ainda são aproximações fortes

O arquivo versionado usado na sonda só tem stacks 5/8/10/12/15/20/25bb e todos os 5.007 nós assumem 9 jogadores. Não há nós 30/40 nesse arquivo. Acrescentar buckets no Python não cria soluções HRC correspondentes.

Com AA, 30/40/60/100bb, o advisor buscou o nó de 25bb por empréstimo e retornou `validated=False`, corretamente sinalizado. Portanto, não consegui reproduzir a afirmação de “range 40bb validado” com o pacote disponível. Um arquivo local diferente pode conter esses nós; é necessário registrar seu hash e conteúdo antes de concluir.

Também permanecem comentários e caveat `STACK_ABOVE_SOLVED_DEPTH_100BB_REFERENCE` mesmo quando o bucket máximo virou 40 e o nó veio de 25. Essa mensagem pode induzir diagnóstico incorreto.

Mudar 9 para 6 ocupados na sonda preservou nó/mix/recomendação nas 169 classes, com aviso de referência 9-max. Isso não prova que cada decisão seja errada — especialmente em posições finais —, mas mostra que não existe um modelo específico por tamanho de mesa nessa rota.

Reduzir apenas o stack atrás do opener de 25bb para 3bb, sem caracterizar all-in, preservou o mesmo nó/mix/recomendação nas 169 classes. A busca usa principalmente o stack do hero. O vetor de stacks e o stack efetivo por oponente precisam integrar o contexto de seleção; não basta um único stack médio ou do hero.

## O que melhorou e o que a evidência não permite concluir

Passaram os testes existentes das correções de alvo da inscrição, mão desconhecida no RAISE, contexto pendente, união dos participantes e cache. Houve correções reais em relação à auditoria anterior. Bounty passou o replay disponível. O RAISE ganhou caminhos de preset/barra, e o operador ganhou logs e fast-path.

Esses resultados não justificam “execução pronta” para todos os cenários: testes são contratos de laboratório, os ranges Windows não estão identificados e não houve ensaio novo de latência/confiabilidade no cliente. O motor não é um solver geral e as frequências do pacote são convertidas em recomendação pela ação de maior frequência. Esse argmax não reproduz uma estratégia mista ao longo das mãos; deve ser decisão explícita de produto, não equivalência presumida com o range HRC.

Não medi EV real, lucro, perda de BB/100 nem taxa de erro estratégica. Para isso, são necessárias soluções de referência para os mesmos contextos e avaliação por mão/situação, com divergências de ação e custo em EV separadas. Não atribuí ao cérebro erros relatados em capturas que não pude reproduzir.

## Implementação recomendada, em ordem

1. **Contrato de contexto e validade.** Criar estrutura que registre jogadores, posição, stacks por assento, apostas, ações confirmadas, origem/idade da observação, confiança e se a ação reabre. Separar `node_validated` de `context_supported` e `execution_allowed`. Avisos de limpers/multiway não podem preservar autorização indevida.
2. **Histórico pré-flop por mesa/mão.** Eventos open/limp/call/raise/fold/all-in, participantes ainda ativos, tamanho de cada aumento, iniciativa e limper que volta a agir. Não inferir certeza onde um frame perdido admite várias sequências. Observação leve continua mesmo fora da vez do hero.
3. **Matriz explícita de cenários.** Pote não aberto; 1/2/3+ limps; BB vs SB limp; open HU; open+1/+2 callers; limp→iso; squeeze; hero open→3bet; cold 3bet; 4bet; shove multiway. Cada célula precisa ter política própria ou ficar declaradamente sem suporte. Essa é a frente central do cérebro.
4. **Ranges HRC/NVT com manifesto.** Versionar ou referenciar artefatos com hash, versão do engine/solver, tamanho de mesa, stacks, antes, posições, sizings e sequência resolvida. No startup e no log de cada decisão, registrar arquivo/hash/nó/contexto. Confirmar o arquivo extraído hoje antes de discutir porcentagens ótimas.
5. **Separar ranges de tamanhos.** Iso/squeeze/overcall/overlimp/reshove precisam de conjuntos de ações e contexto próprios. Alterar size de um open first-in não valida um range de isolamento. No HRC/NVT, resolver as células prioritárias com árvores e sizings declarados; heurísticas residuais precisam permanecer rotuladas e fora da execução automática até avaliação.
6. **Retirar a promoção artificial do fallback.** Não converter ausência de nó em `validated=True`. Tratar falta de cobertura, identidade e leitura como causas diferentes. CHECK só quando a UI provar que é grátis; decisões que comprometem fichas exigem política de contingência com critérios e validação próprios.
7. **Regressão e uma confirmação Windows.** Primeiro testar a lógica com estados corretos, depois pixels rotulados e replay temporal, depois homologação passiva no cliente. O critério não é apenas “não travou”: é classificar o contexto certo, escolher uma política compatível e explicar toda abstenção.

### Critérios mínimos do próximo lote

- Dois limps jamais são apresentados como contexto confirmado de pote não aberto.
- Open+callers não herda validade de execução de nó HU só por acrescentar um caveat.
- 3bet e 4bet usam sequência confirmada ou contexto desconhecido explícito.
- AQ/TT+ não recebem autorização automática de call por ausência de cobertura.
- Buckets/testes/manifesto concordam; falta de range não é mascarada por mensagem de solução inexistente.
- Testes incluem cenários de duas/três ações e regressões por origem, não só mãos isoladas em packs sintéticos.

## Reprodução

Com as dependências de `requirements.txt` em ambiente isolado, a partir da raiz do checkout `ace14f6`:

```bash
python -m unittest discover -v
PYTHONPATH=. python docs/revalidation-preflop-20261112/probe_preflop.py --pack /caminho/nvt-ranges-validados.json --output /tmp/preflop-matrix.json
```

O script preserva o hash do pacote recebido. Reexecutá-lo com o arquivo HRC de hoje identifica o quanto as contagens mudam, sem esconder que o roteamento continua compartilhando nós nesses cenários. As evidências publicadas acompanham a versão identificada, sem incluir ou presumir o arquivo privado do Windows.

**Recomendação final:** priorizar representação do contexto, cobertura de cenários e procedência dos ranges antes de ampliar HUD, pós-flop ou velocidade de clique. Há gargalos de percepção, mas a tese de que basta melhorar o olho e o cérebro já está bom não é sustentada por esta revalidação.
