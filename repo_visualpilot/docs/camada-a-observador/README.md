# Camada A — Observador de estado integrado (sem cliques)

Primeira camada da "próxima frente": provar que as leituras de um frame pertencem
à **mesma mesa, mesma mão e ao momento atual**, amarrando-as pelo `HandTracker`.
Zero execução — é observação/diagnóstico.

Saída por frame:

```
mesa identificada → mão identificada → campos confirmados
→ contexto reconhecido → consulta de estratégia OU abstenção
```

...explicando **o que sabe**, **o que mudou** e **por que ficou pendente**.

## Princípio: ausência nunca é inventada

- ID da mão ilegível → **mantém** a mão atual (`pending_id`), não troca.
- ID que regride → `suspect_id` (ids só crescem), ignorado.
- `to_call` None → PENDENTE, nunca vira 0; aposta ausente ≠ "ninguém apostou".
- Stack ocluído → PENDENTE, nomeando o assento; não chuta.
- Board detectado-mas-ilegível → não vira "pré-flop".
- `table_ref` muda na mesma tela → sinaliza possível troca de mesa/torneio.

## Módulo

`state_observer.py` — `StateObserver.observe(result, table_key=...)` recebe a
saída de `table_advisor.advise_table` + uma chave estável de mesa, e devolve uma
`StateView` com: `table` (key/ref/número da mão), `hand` (evento/número/frame),
`fields` (cada campo com valor/confiança/origem/confirmado), `context`, `advice`,
`changed` (delta vs. frame anterior) e `pending` (por quê). `render(view)` dá o
texto humano. Puro em relação à visão (não captura, não clica).

Ligado no `assistir_mesa` (substitui o dedup por assinatura): imprime o estado só
quando muda. O gate de pausa/takeover (F2) e a ausência de cliques seguem iguais.

## Pré-requisito verificado (passo 0)

O ID da mão é o âncora do rastreamento. Confirmado que lê no skin **Karekas**
(`read_hand_id` na banda 0.70–0.74): `000001` → mão 1771, `000032` → 1802,
`table_ref` estável `261108184808-14146017`, confiança high.

## Validado com dado REAL (2 frames Karekas em sequência)

```
MESA karekas#1 ref=261108184808-14146017 | MAO #1771 [new_table] frame 1
  confirmados: hero_cards=['8s','3c'], pot=4.5, dealer=left_up, hero_position=BB
  pendente: TO_CALL_PENDENTE; STACKS_PENDENTES: right_low,left_low
MESA karekas#1 ref=261108184808-14146017 | MAO #1802 [new_hand] frame 1
  mudou: MAO_NOVA #1802; hero_cards ['8s','3c']->['2h','4d']; pot 4.5->2.5;
         dealer left_up->top_right; hero_position BB->HJ
  pendente: TO_CALL_PENDENTE; STACKS_PENDENTES: left_low
```

`test_state_observer.py` (11 testes): transições de mão, ID ilegível segura a
mão, ID regredido = suspeito, troca de `table_ref`, campos confirmados, ausência
não inventada (to_call/stacks pendentes), abstenção, multi-mesa independente.

## O que fica para a Camada B

Reconciliação de **ações entre frames** (stacks/pote/apostas ao longo da mão):
a amostragem periódica PERDE ações intermediárias → marcar PENDENTE, nunca
inventar. A espinha (identidade de mesa/mão + proveniência + saída integrada) é
o que a Camada A entrega.
