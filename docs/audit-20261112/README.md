# Auditoria VisualPilot — 12/11/2026

**Resultado: laboratório parcialmente aprovado; operação real não homologada.** A suíte da versão atual tem duas falhas reproduzíveis de leitura de bounty. Há regressões de contexto temporal e bloqueadores anteriores nos fluxos de RAISE e inscrição. Este lote audita e documenta; não modifica o código operacional nem executa apostas ou inscrições.

## Referências e preservação

- Repositório: `eduardodinizti-design/Software`, `main` consultada por `git ls-remote` antes e depois dos ensaios.
- Atual: `205dbc7ffbfb5f103dc342f4dfce407a3a27915c`.
- Base: `f0beee374a694aaf8a06e8ca15c9508bc4652796`.
- Diferença: 34 arquivos, 2.613 inserções, 302 remoções; dez commits, cinco deles registros de CI.
- Executor Linux aceitou comandos; GitHub respondeu ao protocolo Git e `gh auth status` confirmou autenticação, sem registrar credenciais.
- `AGENTS.md` da versão atual e da base foram lidos. As instruções locais do checkout antigo e seus documentos de desenvolvimento também foram consultados.
- `software-review` continua em `e922e33f43e17de351c81d52d78a7c92d593b7a9`, branch `fix/observer-integration`, com modificações e arquivos não rastreados preservados. `software-current-audit` continua em `de60534cfa5d56b344b9a3d3e84d2b7f2e2f0957`, detached e limpo.
- Clone novo e worktree da base sob `work/`; dependências em venv separado. Nenhum reset, clean, stash, checkout ou instalação foi aplicado aos diretórios antigos.

## Testes executados

Python 3.12, Tesseract 5.5.0, pytesseract 0.3.13, OpenCV 4.11.0.86, numpy 2.2.6, Pillow 13.0.0, psutil 6.1.1. Backend OCR: subprocesso, sem tesserocr. As versões Python de projeto foram instaladas a partir de `requirements.txt` no venv isolado.

| Ensaio novo | Base | Atual |
|---|---:|---:|
| `python -m unittest discover -v` | 651: 642 passaram, 9 pulados | 762: 751 passaram, 2 falharam, 9 pulados |
| `test_bounty.RealPkoFixtureTests` isolado | módulo inexistente | 3: 1 passou, 2 falharam novamente |
| Lote `tools/run_lab_batch.py` | 12/12 tarefas passaram | 12/12 tarefas passaram |

Logs integrais em [evidence](evidence). A primeira tentativa com o Python global encontrou `cv2` ausente (40 erros de importação); não foi contada como defeito do produto. A suíte foi então executada nas duas versões com o mesmo venv. Mensagens `FALHA: Captura estrita...` no rodapé vêm de cenários negativos que passaram; não são falhas adicionais da suíte.

Os nove pulados são: Windows GDI nativo (1), Karekas bright-rank (4, dependência tesserocr e capturas de sessão), river Karekas (1, exige tesserocr), lobby real (2, captura de sessão ausente), painel de raise real (1, exige tesserocr). Portanto, “suíte verde” não certifica essas integrações.

Para reduzir essa lacuna sem alterar testes, executei diretamente os leitores com o backend OCR disponível e os PNGs versionados: o river retornou `7d Jh 9d As Jd` corretamente; o painel localizou os quatro presets, mas leu `2.5%x` no segundo, com `mult=None`. O mapeamento de 2,5x fica indisponível nesse replay. Isso é leitura offline em Linux, não comportamento medido no cliente.

## Achados reproduzíveis

Prioridade P1: corrigir antes de considerar execução armada/inscrição operacional. P2: corrigir antes de confiar nas recomendações contínuas ou na cobertura anunciada. As reproduções com mocks validam contratos e transições, não pixels ou cliques Windows.

### A1 — P1 — Inscrição aceita detalhes de outro torneio/clube (anterior à base)

Em [registration_flow.py](../../registration_flow.py#L119), `check_details()` constrói uma identidade dos detalhes, mas não compara nome/clube com o alvo observado e autorizado. Reproduzi nas duas versões: observar `MINI FREEZE`, Karekas, R$50; conferir detalhes `OTHER EVENT`, Veneza, R$50. Resultado: `DETAILS_CHECKED`, seguido de `AWAITING_CONFIRMATION` na reserva. Esperado: bloquear divergência de identidade antes de reservar.

O módulo permanece sem cliques e exige confirmação humana; o defeito é a oferta errada chegar à etapa de autorização. Corrigir comparando os campos de identidade disponíveis entre alvo, lobby e detalhes, e exigir revalidação fresca na confirmação. `details_from_card()` já declara que deriva detalhes do próprio lobby + operador: isso não constitui conferência independente da tela de detalhes.

### A2 — P1 — RAISE ainda ecoa a identidade e confirma falha de leitura (anterior à base)

[raise_sequencer.py](../../raise_sequencer.py#L124) devolve no validator a identidade recebida, sem reler mão/mesa; `hand=None` não impede a sequência. Com o mundo simulado dos testes e `DryRunInput`, a sequência produziu três cliques simulados e `confirmed=True` com mão desconhecida, nas duas versões. `_verify_bet()` também devolveu `confirmed=True` quando o leitor retornou `INVALID_CROP`.

A correção de [operar_mesa.py](../../operar_mesa.py#L110) relê a mão no caminho de clique único, e seu verifier passou a aceitar apenas estados específicos de linha ausente. Essas correções não foram aplicadas ao sequenciador de RAISE. O gate novo `validated` limita quais conselhos chegam ao sequenciador, mas não elimina troca de mão durante a sequência. Requer bloquear identidade desconhecida e reler identidade em cada etapa; erro de leitura deve permanecer resultado desconhecido.

### A3 — P1 — Bounty 135 aceito como 35 no OCR disponível (funcionalidade nova)

Dois testes novos falharam na suíte e no rerun isolado:

```text
python -m unittest test_bounty.RealPkoFixtureTests -v
test_read_seat_bounties_with_profile: TL=35.0; esperado 135.0
test_reads_135_from_real_pills: 35.0 != 135.0
```

Entrada: `tests/fixtures/bounty_live/machine-pko-bounty-135.png`. São dois caminhos sobre a mesma origem, não dois exemplos independentes. O caminho de votação passou seu teste e não apresentou erro nesse ensaio; não extrapolar o erro do caminho `profile` para uma falha já demonstrada no loop padrão. Entretanto, o contrato de leitura nova não passa com o backend suportado, e números incorretos podem alterar a escala do overlay PKO. Preservar abstenção e testar o mesmo PNG com o backend Windows antes de declarar equivalência.

### A4 — P2 — Participantes vistos em frames diferentes viram heads-up (regressão)

[preflop_context.py](../../preflop_context.py#L53) guarda o máximo da quantidade de vilões com aposta >1,5bb em um único frame, não a união dos assentos observados na mão. Dois frames, primeiro aposta do assento A, depois B (A temporariamente ilegível), resultaram em `heads_up=True`, `raises=1`, com agressor sobrescrito de UTG para BTN. A base retornava `heads_up=False` nesse cenário de três ocupados.

O rastreador deve conservar evidência de participação e de agressão por assento ao longo da mão, sem interpretar ausência momentânea de aposta como fold. Esse resultado pode selecionar range HU e liberar heurística onde deveria abster por contexto incompleto/multiway. A correção de HU em mesa cheia tem utilidade, mas seus testes atuais cobrem participantes simultâneos e não essa sequência.

### A5 — P2 — ID ilegível pode reutilizar contexto da mão anterior (regressão)

[preflop_context.py](../../preflop_context.py#L35) retorna imediatamente o contexto antigo quando `hand_key=None`. Depois de registrar mão 1, um frame já com board e ID ilegível recebeu o contexto HU/single-raised da mão 1. A base criava contexto sem agressor nesse caso. [table_advisor.py](../../table_advisor.py#L182) permite usar esse contexto no recálculo pós-flop.

Preservar memória internamente é útil para falha breve de OCR; disponibilizá-la como contexto confirmado sem evidência de continuidade é a regressão. Não é possível afirmar, só com esses dados, se o frame ainda pertence à mão anterior. Esperado: sinalizar pendência e não aplicar range/iniciativa antigos até confirmar identidade.

### A6 — P2 — Índice de detecção transfere chave de mesa (integração temporal nova)

[assistir_mesa.py](../../assistir_mesa.py#L38) usa `source#índice` como chave. Com mesas A e B, B é `w#2`; no frame seguinte, se A some/rejeita, B vira `w#1`. A reprodução mostra a mesma box `(100,0,50,50)` mudando de chave. A indexação já existia no observador, mas agora também identifica o novo tracker de agressão e cache de HUD/bounty, ampliando o alcance do problema.

Requer identidade persistente da mesa; se indisponível, invalidar contexto em vez de transferir dados por índice. O operador usa HWND + origem, o que melhora isolamento entre janelas, mas origem quantizada em 100px também não prova identidade após rearranjo/troca de mesa.

### A7 — P2 — Cache mantém leitura “high” após refresh sem evidência (novo)

[reader_cache.py](../../reader_cache.py#L43) invalida apenas assentos cuja ocupação mudou e mescla refresh com o valor antigo. Com `hud_every=1`, leitura inicial válida seguida de `{}` retornou o HUD anterior ainda `confidence='high'`, sem idade, identidade do jogador ou indicação de refresh falho. A mesma ocupação não detecta substituição de jogador entre amostras. Bounty também pode mudar por KO sem mudança de ocupação.

É um compromisso de cache reproduzível, não um erro de pixel demonstrado. A saída deveria expor idade/origem e bloquear exploit quando a continuidade não estiver confirmada; troca de jogador/mesa deve invalidar o cache. A cadência em frames não fornece limite de idade em segundos quando há pausas ou falhas de captura.

## Correções revisadas e limites da estratégia

- Clique único: revalidação passou a reler o ID da mão, CALL de referência não validada é bloqueado e o verifier deixou de aceitar qualquer erro como confirmação. Os respectivos testes passaram. Call-off sintetizado mantém exceção por margem mínima de equity; isso é autorização implementada por heurística, não validação estratégica real.
- RAISE: passou a exigir `validated` no operador e a deduplicar por mesa+mão. Os testes de laboratório passaram, com as lacunas A2 ainda abertas.
- Multi-janela: executor/validator/verifier por HWND e chave global para caches reduzem interferência entre janelas. Não houve medição de latência operacional nem demonstração de duas/seis mesas no PPPoker.
- Hero: cache por mesa+mão evita abstenção pontual, mas deriva de uma leitura, não de confirmação temporal independente. A identidade é lida duas vezes no loop; não há demonstração de confiabilidade de OCR de ID em produção neste lote.
- Pré-flop: roteamento de shove, empréstimo de stack, ICM/PKO aproximados e gates foram revisados. Empréstimo sai `validated=False`, corretamente bloqueado para CALL/RAISE armados. Nós `validated=True` referem-se ao pacote e ao contexto modelado; não certificam extração visual, posição, multiway, generalização ou lucro no cliente.
- Pós-flop: testes novos de contribuição do hero ao board, outs no river, outs descontados, range de continuação, implied/reverse implied, potes 3bet e HUD passaram. São heurísticas e Monte Carlo; o pós-flop continua com `execution_allowed=False` e o operador o exclui da execução. O caminho de 3bet usa SPR do stack do hero como proxy e considera SPR desconhecido como baixo; isso merece revisão antes de ampliar cobertura. Não foi identificado como solver nem como estratégia homologada.
- HUD: os sete HUDs/56 campos da fixture de desenvolvimento passaram. Uma captura e atlas calibrado não são holdout. `HUD_UNVALIDATED` lista assentos extrapolados, mas não restringe a emissão de `confidence='high'`; é uma lacuna de cobertura a fechar antes de usar esses assentos em exploit.
- Registro em torneios: reserva, deduplicação, Decimal, persistência e reconciliação foram exercitados pela suíte e passaram nos casos existentes. A1 demonstra um caso ausente. Nenhuma inscrição real foi feita.

## Leitura: cobertura e interpretação do lote

Os sete PNGs/8 recortes do conjunto `development-labels.json` tiveram SHA-256 conferido. Os demais produtores verificam os hashes que declaram. O lote usa fontes de desenvolvimento já reutilizadas, recortes e transformações; não constitui avaliação independente. Não somar suas contagens como mãos independentes.

Na versão atual: Hero development 16 acertos/0 erros/0 desconhecidos; Hero extended em escala original 34/0/0, em 0,75× 33/0/1 e em 0,5× 34/0/0. Board extended: 18 corretos, 5 abstenções, zero incorretos aceitos em 23 casos transformados. Protected-rank: 21 corretos, 5 abstenções, zero incorretos em 26 chamadas. Pipeline integrado: 7/7 contratos. Esses ensaios aprovados preservam as abstenções; não significam cobertura universal.

As cinco métricas acima foram comparadas com execução nova da base e permaneceram iguais. Os campos internos `before/after` do relatório de detector comparam algoritmos do próprio script, não os dois commits desta auditoria. Tempos dos jobs concorrentes não são benchmark de latência por mesa.

O lote legado não inventaria automaticamente todas as novas fixtures de 09–12/11. `COVERAGE.md` é um recorte histórico de um conjunto específico, não a cobertura global atual. O erro conhecido **8h→3h permanece pendente de reprodução e correção no mesmo tema colorido**; passar um oito de outra origem/tema ou uma transformação não encerra esse caso.

## Reprodução

Em cada checkout isolado, com o mesmo venv contendo `requirements.txt`:

```bash
python -m unittest discover -v
OMP_THREAD_LIMIT=1 python tools/run_lab_batch.py --assets public/assets/aistudio --output /tmp/visualpilot-reading-audit
```

O lote contém produtor que escreve `docs/table-reading/board-transition-results.json` mesmo com `--output`. Executar somente em cópia isolada. O resultado gerado foi preservado nas evidências e a cópia auditada foi restaurada desse efeito; diretórios antigos não foram usados para esses ensaios.

Na versão atual, `PYTHONPATH=. python docs/audit-20261112/reproduce.py` reproduz A1/A4/A5/A6/A7 e a extensão do script cobre A2. É uma demonstração observável de falhas, não um teste que as conserta. A3 usa o comando isolado acima; `evidence/fixture-direct.json` registra o replay direto de board/painel.

`common_reproduce.py` pode ser levado a ambos os checkouts e executado com `PYTHONPATH=.` para comparar A1/A2/A4/A5; os resultados estão em `evidence/common-baseline.json` e `evidence/common-current.json`. Nos replays, os autores das fixtures e dos rótulos são os existentes no repositório; esta auditoria não criou uma nova anotação humana independente.

## Bloqueios para uma única rodada Windows

1. Resolver A1/A2 antes de habilitar fluxos operacionais; resolver A4–A7 e rejeitar dados temporais sem continuidade comprovada.
2. Resolver ou explicar por backend A3 e o preset 2,5x ilegível. Acrescentar casos independentes por tema, escala e posição; manter erro aceito separado de abstenção.
3. Reproduzir 8h→3h com original rotulado do mesmo tema e registrar antes/depois. Completar a matriz de cobertura sem usar transformações como novas origens.
4. Agrupar a validação Windows: captura PPPoker/Unity real, IDs de mesa/mão, transições pré/flop/turn/river, obstruções, mudança de janela, ocupação/jogador, 1→2→6 mesas e latência por ciclo. Observação passiva primeiro; qualquer ensaio operacional exige escopo próprio.
5. Confirmar inscrições pelo alvo/custo/moeda e tela de detalhes/recibo independentes, com autorização humana específica; os testes SQLite não substituem isso.

O arquivo de CI Windows versionado registra 201 testes em 6,982s no commit-fonte `38a191b1be72a5752cb64cfcc4fad8c881baa884` (run 43148473454). O workflow usa uma janela Tk controlada; não abre PPPoker e nem inclui toda a suíte nova de estratégia/bounty/registro. É evidência anterior de contratos/GDI, não homologação real Windows/PPPoker. Este lote não teve cliente Windows conectado e não concede aprovação operacional.
