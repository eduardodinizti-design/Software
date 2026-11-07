# Estado pré-flop e consulta de estudo — primeiro bloco

O leitor operacional continua `ler_mesas.py` → captura estrita → pipeline. Este
bloco acrescenta uma reconstrução de estado **offline**, separada do reconhecedor
e do executor manual. Não habilita recomendações ou cliques na mesa real.

## Resultado e limites

- `preflop_study.py`: participantes, dealer, posições, stacks, apostas, pote,
  valor a pagar e ordem de ações reconstruídos de um histórico completo fornecido.
- `simular_preflop.py`: consulta de estudo ao pacote NVT, com mix, fonte, versão,
  SHA-256, EV disponível e bloqueios explícitos. `execution_allowed` permanece
  falso em todos os caminhos; não importa captura, mouse ou teclado.
- Até seis mesas independentes por chamada, sem cache entre snapshots.
- Dados desconhecidos, não confirmados ou contraditórios resultam em `ABSTAIN`.
- Consulta inicial somente chip EV/regular/mid, `open_raise`, em contexto exato.
  Um limp já tira a mão de pote não aberto. Pós-flop/ICM/PKO ficam bloqueados.
- Os 16 nós consultados têm 9 jogadores: oito posições a 15 BB e oito a 25 BB.
  Seis mesas simultâneas não significam seis jogadores por mesa. Não há fallback
  de 6-max para 9-max, stack aproximado, fase implícita ou spread mais próximo.
- O cenário tem que coincidir com `table.stacks`, posts e pote exportados. Isso
  reproduz uma mesa controlada do exportador; não recalcula estratégia para stacks
  reais e não demonstra que stacks sorteados e modelo HRC são equivalentes.
- Não há sizing estratégico exportado usado aqui. O tamanho em ações anteriores
  não é convertido em tamanho de raise recomendado. Não se sorteia uma ação
  alternativa para contornar um raise sem sizing.

## Origem do material

Arquivo fornecido pelo usuário: `nvt-range-lab-estrategia.zip`, SHA-256
`61ac7c03ebf86ee251301b844b7f1c353306bdaa6cc32e0884e4e1bc16047eb0`.
Dados gerados em `2026-11-06T23:22:51.050Z`, motor `356340d` e validação declarada
`2026-10-30-245refs`. 6.432 nós totais; 5.007 marcados como validados. Todos são
9-max. O subconjunto validado coincide exatamente com os nós correspondentes.
Os 62 arquivos TypeScript enviados coincidem com o RangeLab nesse commit.

O formato v1 usa 169 classes de mãos / 1.326 combinações. Frequências, comprimentos
dos vetores, EVs finitos e somas foram conferidos; mixes zerados explicitamente
`outOfRange` são abstinências, não fold. Não foram encontradas inconsistências
nesses controles estruturais. Isso não comprova GTO, convergência ou lucro.

`validated` é declaração do RangeLab, não validação independente desta integração.
O pacote aplica ajustes do trainer sobre as fontes. Há documentação histórica
com tolerâncias antigas; este bloco não implementa correção/grading por tolerância.
EV não-fold = 0 com frequência = 0 é apresentado como desconhecido, conforme o
documento, sem presumir empate com fold. A fonte bruta permanece no ZIP original.

Os JSON integrais e o ZIP não são publicados novamente neste repositório. Use o
material original; o teste unitário usa uma fonte sintética explicitamente rotulada,
sem afirmar que suas frequências artificiais são uma estratégia de poker.

## Reproduzir

Na raiz do checkout, com Python 3.12. Substitua `CAMINHO` pela pasta `pack` extraída
do ZIP enviado. O comando gera uma observação fictícia usando exatamente a mesa do
nó exportado, mais folds anteriores ao BTN; não representa leitura de imagem:

```cmd
python simular_preflop.py --ranges "CAMINHO/ranges/nvt-ranges-validados.json" --exemplo "chip_ev|mid|25|open_raise|BTN||-" --cartas Ah Kd
python -m unittest test_preflop_study -v
python -m tools.validate_preflop_study --ranges "CAMINHO/ranges/nvt-ranges-validados.json" --output logs/preflop-parity.json
```

CLI: saída 0 indica consulta
de estudo produzida; saída 2 indica abstinência. Saída 0 nunca autoriza execução.
O relatório de paridade sai com código 1 se não houver casos ou houver divergência.

Alternativamente, `--cenario arquivo.json` aceita `{"tables": [cena, ...]}`.
`exported_example(book, node_id, cards)` gera uma cena de referência para estudar
esse contrato. Não se deve editar uma captura real para rotulá-la `SIMULATION`.

## Contrato de observação

Todos os campos abaixo são declarados pelo cenário controlado, não pelo OCR:

| Grupo | Campos e semântica |
|---|---|
| Identidade | `source_key`, `table_id`, `snapshot_id`, `hand_id` não vazios; mesa identificada por fonte + table_id |
| Evidência | `evidence: SIMULATION`; `confirmed_fields` inclui participants, dealer, stacks, pot, bets, history, turn, hero, board |
| Mão | `street: preflop`, `board: []`, duas `hero_cards` físicas distintas |
| Assentos | `players[].seat` inteiro 0–8, crescente no sentido horário, apenas participantes da mão; não remover quem foldou |
| Dealer/turno | `dealer_seat`, `hero_seat`, `turn_seat`; turno deve coincidir com a sequência reconstruída |
| Fichas | `start_stack_bb`, `stack_bb`, `bet_bb` por participante; `in_hand` explícito; `pot_bb` e `to_call_bb` conciliados |
| Histórico | `history_complete: true`; `actions` com `seq` consecutivo, seat, type e `amount_bb` incremental pago, nunca raise-to |
| Contexto | `strategy_context` com mode, format, stage, players e stack, sem defaults |

Aceita posts SB 0,5 BB / BB 1 BB e ante explícito. Ante entra no pote, não no valor
apostado para pagar. Reproduz fold/check/call/raise e confere ordem e conservação
de fichas. A estratégia permanece indisponível após uma ação que abriu o pote.
Underraises all-in, straddles, side pots, novos streets e históricos incompletos
não fazem parte deste primeiro bloco. O estado não infere ações entre frames.

## Validação executada

- Linux: 201 testes descobertos, 200 passaram e 1 ignorado por exigir Windows.
  Inclui 19 novos testes de estado, contexto, paridade sintética, abstinência,
  turnos, limites de mesas, isolamento e CLI.
- Fonte real enviada: 16 nós × 169 mãos = **2.704 consultas**, nenhuma divergência
  de mix; nenhum tamanho inventado ou execução habilitada.
- Corrigido escape de `%` no texto de ajuda de `coletar_sessao.py`; `--help`
  anteriormente lançava TypeError. Não altera cotas, duração ou armazenamento.
- Executor manual existente revisado: mantém seleção explícita de um botão,
  recaptura, geometria/identidade e pixels. Não foi alterado nem executado em
  Windows nesta entrega. Bet/Raise pode abrir só o painel, sem preencher valor.
- CI inclui a nova suíte. Os resultados acima são locais Linux, não resultado
  antecipado do GitHub Actions nem evidência de funcionamento no PPPoker real.

## Próximo marco dependente de evidência Windows

Dealer, participantes, stacks, pote, apostas e histórico ainda não são decodificados
pelo leitor real. Hero/board/botões mantêm os reconhecedores atuais. A camada nova
não é ligada ao pipeline enquanto esses dados e a identidade de cada mesa não forem
verificados em amostras reais com gabarito. Ver botões não prova turno nem ação tomada.

Para obter uma amostra única na geometria atual, sem coleta contínua de superfície:

```cmd
python testar_windows.py --listar
python coletar_amostras.py --hwnd NUMERO
```

Use o HWND listado e envie os recortes nativos com os valores corretos de dealer,
participantes, stacks, pote e apostas visíveis. Não é necessário repetir uma sessão
longa nem salvar superfície inteira por ciclo. Uma rodada Windows posterior deverá
verificar conjuntamente campos novos, identificação entre mesas e executor manual;
integração de sizing/confirmacão permanece um marco separado. C-bet, turn e river
dependem dos estados pós-flop e de estratégia explicitamente fundamentada.
