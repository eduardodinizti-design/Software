# Base pré-flop do NVT Range Lab

Pacote recebido: `nvt-ranges.zip`, exportado em 2026-10-29T23:56:40.052Z,
motor `ea758d9`, validação declarada `2026-10-29-223refs`.
Os documentos recebidos foram tratados como especificação de integração, não
como instruções para executar instalação, modificar permissões ou publicar dados.

## O que chegou

| Arquivo | Conteúdo |
| --- | --- |
| nvt-ranges.json | 6.349 nós, 4.547 validados e 1.802 não validados |
| nvt-ranges-validados.json | Exatamente o subconjunto validado, com conteúdo idêntico |
| nvt-ranges-client.ts | Consulta, matriz, frequências e correção de respostas |
| integracao-ranges.md | Contrato, regras e limites declarados pelo exportador |

Cada nó tem 169 classes de mãos, representando 1.326 combinações de cartas.
Todas as mesas exportadas são 9-max. Modos no pacote completo: chip EV, ICM, PKO
e PKO+ICM. No subconjunto validado, há chip EV (490), ICM (2.024) e PKO+ICM
(2.033); não há nós PKO puro validados. Stacks validados: 5, 8, 10, 12, 15, 20
e 25 BB. Os nós de 40 e 100 BB estão apenas no pacote completo não validado.

Os spots são todos **pré-flop**: abertura, shove, defesa contra abertura/shove,
resteal, resposta a 3bet e limps. `mid`, `pre_itm`, `bubble` e `ft` são fases
do torneio, não flop/turn/river. Pós-flop está fora desta integração, conforme
a orientação do usuário; não é necessário enviá-lo agora.

## O que foi implementado

`visualpilot/agent/nvt_ranges.py` lê diretamente `nvt-range-export` v1.
`RangeCoachStrategy(..., nvt_ranges=book)` passa a consultar essa base.

- Somente nós com `validated=true` entram no índice.
- Mão física → classe da mão; ordem de cartas não muda o resultado.
- Seleção exata de modo, stack, posição, spot, agressores, fase e spread.
- No ICM, seleção de spread pelos nove stacks completos, com a fórmula enviada.
- Sem aproximação de stack ou escolha de uma fase ausente; fica pendente.
- Frequências mistas preservadas; não se reduz um mix à ação mais frequente.
- `outOfRange` impede recomendar uma mão que não chega ao spot.
- Toda resposta traz nó, fonte, versão do motor e SHA-256 do pacote.
- Pós-flop e etapa desconhecida são rejeitados por esta base.
- Sizing fica `not_exported`; não se inventa tamanho de raise/3bet/4bet.

Exemplo real conferido: chip EV, 25 BB, BB contra abertura do BTN, AKs →
**three_bet com frequência 1**, EV de 5,7936 BB no arquivo. Isso é uma consulta
ao nó exportado, não uma avaliação nova da mesa atual nem um clique automático.

## Auditoria e testes

`audit.json`: contagens, hashes, campos, vetores de 169 posições, frequências
finitas entre 0 e 1, soma por mão (tolerância 0,002), ações legais e índices
outOfRange. Nenhuma inconsistência estrutural nesses controles.

`parity.json`: **768.443 consultas**, abrangendo os 4.547 nós × 169 mãos, sem
divergência de mix/status outOfRange. Dessas consultas, 71.478 estavam marcadas
fora do range. Isso prova reprodução dos dados exportados, não correção de um
solver, lucratividade, sizings ou fidelidade de um motor não enviado.

`tests.log`: regressões com um pequeno trecho autêntico do pacote. O JSON
integral permanece no material recebido; não foi incorporado ao ZIP público
da demonstração visual. O simulador portátil continua rotulado como demo-1,
não como execução dos ranges NVT; esta entrega constrói a base de consulta.

## Divergência confirmada entre cliente e documentação

A documentação manda tratar EV=0 e frequência=0, fora fold, como EV não
calculado. O `grade()` do cliente TypeScript não faz isso. Executei o cliente
enviado com o pacote real e confirmei:

- Nó `icm|pre_itm|8|open_shove|UTG+2||-`, mão A5o.
- Mix exportado: fold 100%.
- EV exportado: all_in=0, fold=0.
- Cliente recebido: all_in é `ACCEPTABLE_MIXED_ACTION`, com `correct=true`.

No adaptador Python, o EV bruto fica preservado, mas esse placeholder é
convertido para desconhecido antes de corrigir a resposta. All-in não ganha
aprovação por um EV ausente. Essa diferença é intencional e segue o documento;
não afirmamos paridade com esse comportamento específico do cliente.

Há 3.035 células não-fold com EV=0/frequência=0 no subconjunto validado. Isso
não significa 3.035 decisões erradas: a aprovação indevida depende do EV das
outras ações e da tolerância. Recomenda-se ao exportador representar ausência
como `null`, para não exigir interpretação de zeros.

O cliente também escolhe um primeiro nó quando faltam fase/spread e pode cair
em outro spread se o solicitado não existir. O adaptador exige correspondência
e fica pendente nessas situações, para não usar silenciosamente outro contexto.

## Limites da base

Não vieram o motor completo TypeScript, exploração de estatísticas do vilão,
cálculo dinâmico com stacks/payouts/bounties reais nem sizings recomendados.
`table.actions.amount` descreve ações anteriores, não o sizing da recomendação.
Marcação `validated` é a declaração do Range Lab; não repetimos aqui sua
validação matemática. O próximo acoplamento ao simulador deve fornecer o
contexto pré-flop e mapear ações/sizings disponíveis sem improvisar esses dados.

Reproduzir:

```bash
python -m tools.audit_nvt_ranges /caminho/do/pacote
python -m tools.verify_nvt_preflop /caminho/nvt-ranges-validados.json
```
