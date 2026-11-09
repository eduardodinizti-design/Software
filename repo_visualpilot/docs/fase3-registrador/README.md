# Fase 3A — Registrador supervisionado (sem clique)

Implementa a spec `ESTRATÉGIA DE INSCRIÇ.txt` como **lógica pura + SQLite**, no
modo que a própria spec manda fazer primeiro (§2): o bot seleciona, confere,
reserva e concilia uma inscrição, mas **nunca envia o clique de confirmação** —
quem clica no cliente é o usuário. Risco operacional zero: nenhum input é
enviado ao PPPoker (não há `SendInput`/`SetCursorPos`/`mouse_event` em lugar
nenhum deste bloco).

## Módulos

- **`registration_ledger.py`** — livro-razão de reservas.
  - Reserva de **custo + vaga atômica** (`BEGIN IMMEDIATE`) e **persistente**
    (SQLite em arquivo). Reiniciar o programa **não** apaga reservas.
  - **Dedup** por identidade via índice único parcial sobre os estados ativos:
    dois processos não reservam a mesma oferta duas vezes nem passam do limite
    numa corrida (§6).
  - Dinheiro **sempre Decimal exato em centavos**; `None` nunca vira zero (§3/§5).
  - **Identidade verificável** (`make_identity`): token interno de
    `clube+nome+modalidade+buy-in+início`. Nome sozinho **não** estabelece
    identidade (§4) — exige nome + buy-in ou horário. Não é um ID lido da tela.
  - Conciliação (§9): `confirm` (reserva→gasto, sem contar duas vezes),
    `release` (só falha provada antes do envio / recusa sem cobrança),
    `mark_unknown` (timeout/exceção pós-envio: mantém custo+vaga, não reenvia).

- **`registration_flow.py`** — máquina de estados supervisionada (uma rodada,
  um alvo). `execution_allowed` é **sempre False**.
  - Estados (§7): `OBSERVATION → CANDIDATE → DETAILS_CHECKED → RESERVED →
    AWAITING_CONFIRMATION → CONFIRMATION_SENT → CONFIRMED`.
  - Saídas: `BLOCKED`, `REJECTED`, `CANCELLED_BEFORE_SEND`, `UNKNOWN_RESULT`.
  - Reusa `evaluate_card` (política/bankroll) como filtro e o `BotControl` (F2)
    como gate de segurança (sem `RUNNING`, não cria nova intenção).
  - §5: exige as **três restrições de custo juntas** (≤ teto por inscrição,
    == oferta autorizada, ≤ orçamento disponível) e confere soma de parcelas
    contra o total. §10: divergência de custo/identidade/oferta entre telas
    bloqueia; a autorização **não se transfere** para outro torneio/custo.
  - **Uma tentativa por rodada**; um alvo. Se o alvo fica inelegível, para e
    explica — não troca por evento parecido.

- **`registrar_supervisionado.py`** — demo (modo observação) que percorre a
  máquina e **para em AGUARDANDO CONFIRMAÇÃO**.

## Como rodar

```bash
# demo (dados de exemplo, não lê a tela; para antes de qualquer envio)
python registrar_supervisionado.py
python registrar_supervisionado.py --db reservas.db   # persistir entre runs

# testes (18 cenários do §11 + ledger + máquina de estados)
python -m unittest test_registration
```

## Mapa dos 18 cenários (§11) → testes

| # | Cenário | Teste |
|---|---------|-------|
| 1 | Alvo correto confirma | `test_full_confirm_real_mode` |
| 2 | Evento fora da lista | `test_2_event_not_in_list` |
| 3 | Mesmo nome, identidades diferentes | `test_3_same_name_different_identity` |
| 4 | Valor acima do teto | `test_4_above_entry_cap` |
| 5 | Orçamento insuficiente | `test_5_insufficient_remaining_budget` |
| 6 | Limite de vagas (incl. reservas) | `test_6_seat_limit_reached` |
| 7 | Custo composto: soma e divergência | `test_7_*` |
| 8 | Moeda/preço desconhecido | `test_8_*` |
| 9 | Inscrição não aberta | `test_9_registration_not_open` |
| 10 | Custo/identidade mudam entre telas | `test_10_*` |
| 11 | Dois pedidos concorrentes / repetição | `test_11_*`, `test_atomic_dedup_across_connections` |
| 12 | Pausa antes da confirmação | `test_12_*` |
| 13 | Confirmação explícita do evento certo | `test_full_confirm_real_mode` |
| 14 | Confirmação ausente ou de outro evento | `test_14_*` |
| 15 | Exceção pós-envio + reinício com reserva | `test_persists_across_restart` |
| 16 | Falha provada antes do envio libera | `test_16_*` |
| 17 | Confirmação válida após pausa, sem reenvio | `test_17_*` |
| 18 | Rebuy/add-on bloqueado no piloto | `test_18_rebuy_blocked_in_pilot` |

## Plug no lobby real (09/11)

Liga o fluxo 3A à leitura REAL do lobby, sem clique.

- **`lobby_runner.py`** — ponte:
  - `find_lobby_crop` / `read_lobby`: entre os crops que `detect_table_crops`
    propõe, o **lobby é o que tem badges de buy-in** (a mesa tem zero). Lê os
    cartões com `grade_reader.read_grade`.
  - `session_state_from_ledger`: reconstrói o `SessionState` a partir das
    reservas do **ledger** (fonte de verdade), para o pré-filtro `evaluate_card`
    ver orçamento/vagas reais — resolve a nota de "duas fontes" da 3A.
  - `select_lobby`: `(elegíveis, bloqueados)` via `select_from_grade`.
  - `details_from_card`: detalhes derivados do cartão + moeda do operador,
    marcados `details_source='lobby+operator'`. A moeda **nunca** é inventada.
- **`plugar_lobby.py`** — CLI: captura (`--hwnd`) ou carrega (`--image`) o lobby,
  lê, seleciona e, para `--target`, percorre o fluxo até AGUARDANDO CONFIRMAÇÃO.
- **`test_lobby_runner.py`** — fakes + **teste end-to-end no lobby REAL** do
  Karekas com OCR in-process (pula se faltar tesserocr/imagem).

**Validado no lab com dado REAL** (crop `sessao-20261108-200315/sample-000001-mesa-1.png`,
lobby Karekas, OCR in-process): 5 cartões lidos; seletor marca DEEP FREEZEOUT
elegível e bloqueia BOX MISTERY/FREEZEOUT (reg. não aberta), CRAZY REBUY (rebuy)
e o cartão parcial; o fluxo leva DEEP FREEZEOUT a AGUARDANDO CONFIRMAÇÃO (orç.
500→450) e para antes de qualquer clique.

```bash
python plugar_lobby.py --image logs/.../sample-000001-mesa-1.png --is-crop \
  --club Karekas --currency BRL --max-entry 100 --budget 500 --bankroll 200 \
  --target "DEEP FREEZEOUT" --authorized-cost 50 --now 20:00
```

## Limitações (honestas)

- **Não há validação no PPPoker real.** Tudo foi exercitado no lab (SQLite +
  lógica pura). Os dados da demo são de exemplo, não leitura de tela.
- O filtro de política (`evaluate_card`) usa o `SessionState` em memória como
  pré-filtro grosso; a **fonte de verdade** de orçamento/vaga no fluxo é o
  **ledger** (confirmados + pendentes). Mantenha-os em sincronia quando ligar ao
  lobby real.
- **Leitura do lobby real: coberta** (ver "Plug no lobby real"), validada em
  crop de lobby. Falta a extração do painel do lobby a partir do **frame inteiro
  do canvas ao vivo** (`--hwnd`): usa a heurística de badges, mas só foi provada
  no fato de o crop conhecido ter 5 badges — precisa de uma rodada ao vivo na
  máquina do Eduardo.
- **Detalhes degradados:** a 3A não abre a tela de detalhes (seria um clique),
  então a conferência lobby×detalhes do §C vem da mesma fonte (flag
  `details_source='lobby+operator'`). Um leitor de detalhes validado é trabalho
  futuro. O horário de início fica `None` quando o cartão não o mostra (a
  identidade usa nome+buy-in, suficiente).
- Este bloco **não** habilita registro autônomo. A próxima fronteira (Fase 3B /
  F4) é o controlador de cursor — e só ele, validado, autoriza o bot a clicar.
