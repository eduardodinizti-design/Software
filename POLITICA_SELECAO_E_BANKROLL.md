# VISUALPILOT — POLÍTICA DE SELEÇÃO E GESTÃO DE BANKROLL
Versão: 0.1 · Natureza: política estratégica (camada de DECISÃO, não de execução).

> Esta política é a camada que a `ESTRATÉGIA DE INSCRIÇ.txt` deixou **fora de
> escopo** (seleção por EV/field/estrutura e bankroll). Ela **decide o quê/quando**;
> a spec de inscrição governa **como clicar com segurança** (supervisionado).
>
> **O bot não executa inscrição.** Não há registrador no código. Tudo abaixo é
> **recomendação para o operador (você) executar manualmente**, de forma
> supervisionada. Valores absolutos em moeda/fichas são preenchidos por você;
> esta política trabalha em **unidades de buy-in (BI)** e **% da banca**, nunca
> inventa número financeiro (campo em branco = BLOQUEADO, igual à spec).

---

## 0. PERFIL DECLARADO (base desta versão)
- **Banca:** 100–200 BI do stake típico.
- **Risco:** moderado.
- **Modalidades liberadas:** Freezeout, MKO (Mystery), PKO, Rebuy/Add-on.
- **Volume alvo:** 7+ torneios/dia, 4–6 mesas.
- **Clubes autorizados:** Karekas e Veneza (liga Evolution) — únicos com leitura validada.

### Alerta de risco (CEO)
Volume alto + modalidades de alta variância (PKO/Rebuy) + banca na borda inferior
para PKO + perfil moderado = **agressivo na prática**. Os guardas abaixo (PKO só
com banca ≥150 BI, teto de 4 mesas simultâneas no início, regra fixa de rebuy,
orçamento diário de 10%) existem para compensar. Rever a cada subida/descida de faixa.

---

## 1. ENCAIXE COM A CAPACIDADE ATUAL DO BOT
O bot é um **conselheiro pré-flop** (observação, sem pós-flop, sem execução), com
leitura validada na Evolution e **consciência de torneio (ICM/PKO/MKO) ativa**.
Logo o edge é **maior onde o pré-flop decide** (fases média/curta, push-fold,
bolha/ITM) e **menor em jogo deep pós-flop**.

| Modalidade | Fit com o bot hoje | Observação |
|---|---|---|
| **Freezeout** | ✅ Melhor | Menor variância; edge pré-flop + ICM compõem bem. |
| **MKO (Mystery)** | ✅ Bom | Vanilla até o ITM (bot trata o timing); bounty só no dinheiro. |
| **PKO** | ⚠️ OK com banca | Motor PKO ajuda, mas variância alta → exige ≥150 BI. |
| **Rebuy / Add-on** | 🔴 Cautela | **Bot não tem lógica de rebuy nem pós-flop.** Ver §4. |

---

## 2. REGRA DE BANKROLL (moderado)

### 2.1 Mínimo de buy-ins por formato (escalado por variância)
Só jogar um formato se a banca atual ≥ o mínimo dele:

| Formato | Mínimo (BI) | Com turbo/hyper |
|---|---|---|
| Freezeout | 75 | 110 |
| MKO | 120 | 180 |
| PKO | 150 | 200 |
| Rebuy/Add-on | aplicar o mínimo do tipo-base ao **buy-in efetivo** (§4) | — |

Com banca de 100–200 BI: **Freezeout e MKO sempre liberados; PKO só na metade
superior (≥150 BI); turbo-PKO só ≥200 BI.**

### 2.2 Teto por inscrição
- **Custo total de uma entrada ≤ 2% da banca atual** (moderado), incluindo
  entrada + taxa + bounty + (orçamento de rebuy/add-on, se aplicável).
- Nunca ajustar buy-in pra "encaixar" no teto (igual à spec).

### 2.3 Subir / descer de faixa
- **Descer:** se a banca < mínimo-BI do stake atual, cair pro stake onde o
  mínimo é satisfeito. Sem exceção.
- **Subir:** só quando a banca ≥ mínimo-BI (escalado por variância) do stake maior.

---

## 3. GESTÃO DIÁRIA (volume alto)

1. **Orçamento diário de inscrição ≤ 10% da banca** em BI comprometidos no dia
   (um dia sem cash perde ≤10%, recuperável). Ao atingir, **parar de registrar**.
2. **Máx. simultâneas = 4 torneios rodando** no início (não 6), até a leitura
   multi-mesa ser validada nessa carga; depois subir pra 6. (A spec limita o
   piloto de *inscrição* a 1 compromisso; isto é a meta operacional de jogo.)
3. **Sem stop-loss por perda intradiária** em MTT (resultado é "lumpy"): o
   **orçamento diário É o controle**. Stop de disciplina: se notar erro de
   leitura ou se você desviar do conselho do bot, **parar**.
4. **Horário-limite de registro:** definir um relógio de corte diário para não
   iniciar torneio que você não termina na sessão.
5. **Revisão semanal:** reavaliar stake vs. banca e as faixas da §2.

---

## 4. REBUY / ADD-ON (regra decidida pelo operador)
O bot ainda não tem pós-flop; a decisão de rebuy é uma **regra fixa**, não um
julgamento do bot. Decisão do Eduardo (08/11/2026) para a versão final:

- **Rebuy liberado SOMENTE em PKO.** Freezeout/MKO: sem rebuy (são o default).
- **Gatilho:** fazer rebuy **quando o stack cair a ≤ 40 BB** (re-entrada/rebuy
  dentro do período), enquanto o torneio for PKO e estiver no período de rebuy.
- **Buy-in efetivo = entrada inicial + rebuys orçados.** É esse número que entra
  no teto por inscrição (§2.2) e no mínimo-BI do formato (§2.1), não a inicial.
- **Limite:** o orçamento de rebuy de cada PKO conta no orçamento diário (§3.1);
  ao estourar, sem novos rebuys no dia.
- Add-on: avaliar por torneio (regra a definir quando houver estrutura concreta).

Essa regra é **codificável** e vira um parâmetro de sessão (`rebuy: {pko_only:
true, trigger_bb: 40}`) no contrato da §7, consumido pelo futuro operador.

---

## 5. QUANDO REGISTRAR
- **Em lote, no início da sessão**, para as mesas rodarem concorrentes (terminam
  mais cedo, menos fadiga) e dentro do teto de simultâneas (§3.2).
- **No início ou late-reg cedo** para pegar estrutura — o edge pré-flop compõe
  em mais mãos.
- **Late-reg curto (entrar em ~15–20 BB) é aceitável/bom pro bot**: vira
  push-fold, a força dele. Evitar reg deep onde o pós-flop pesa.
- **Corte duro:** nada depois do late-reg fechar; **não perseguir** por nome
  parecido, prêmio maior ou buy-in baixo (igual à spec, §4).

---

## 6. CRITÉRIO DE SELEÇÃO (quais jogar)
Um torneio é elegível **somente se todos**:
1. Clube autorizado (Karekas/Veneza, Evolution).
2. Modalidade na lista liberada (§0).
3. Custo total ≤ teto por inscrição (§2.2) **e** banca ≥ mínimo-BI do formato (§2.1).
4. Inscrição aberta e dentro do período/corte autorizado.
5. Sem inscrição/reserva duplicada para a mesma identidade (igual à spec, §4/§6).
6. Orçamento diário e vaga disponíveis após reservas (§3).
7. Estrutura preferencialmente onde o pré-flop/ICM decide; cautela com deep-slow.

Não usar garantia, overlay, field ou buy-in baixo como "prova de lucro"
(igual à spec, §4). Identidade verificável, não inventada.

---

## 7. CONTRATO DE CONFIGURAÇÃO (futuro — extensão da spec)
Espelha o contrato da `ESTRATÉGIA DE INSCRIÇ.txt` acrescentando a camada de
seleção/bankroll. **Ainda não consumido por código. `enabled: false`.**

```yaml
enabled: false
profile:
  risk: moderate
  bankroll_bi: null            # banca atual em buy-ins (você preenche)
  currency: null               # unidade confirmada (você preenche)
selection:
  allowed_clubs: [Karekas, Veneza]
  allowed_types: [freezeout, mko, pko, rebuy]   # rebuy c/ regra §4
  prefer_push_fold_late_reg: true
bankroll_rules:
  max_entry_pct: 0.02          # teto por inscrição = 2% da banca
  min_bi_by_format: { freezeout: 75, mko: 120, pko: 150 }
  turbo_multiplier: 1.5
daily:
  max_registration_pct: 0.10   # orçamento diário = 10% da banca
  max_simultaneous_running: 4  # subir p/ 6 após validar leitura multi-mesa
  registration_cutoff_at: null # você define o relógio de corte
rebuy:
  pko_only: true               # rebuy só em PKO (§4)
  trigger_bb: 40               # faz rebuy quando o stack cai a <=40 BB
  effective_buyin_multiplier: 3
session:
  registration_cutoff_at: null # até que horas registrar (você define)
  last_tournament: null        # até qual torneio da grade registrar
  grid_preset: []              # grade pré-estabelecida antes do grind
supervised_confirmation_required: true   # true no início; vira autônomo por fases (§8)
```

Nenhum valor absoluto de moeda é preenchido aqui: campo financeiro em branco =
BLOQUEADO, conforme a spec de inscrição.

---

## 8. VISÃO FINAL — OPERADOR AUTÔNOMO (roadmap por fases)
Objetivo (Eduardo): iniciar o bot → ele lê a **grade** (pré-estabelecida antes do
grind nas primeiras operações reais) → **registra sozinho** conforme as regras
(buy-in máx do dia, nº de torneios, rebuy PKO≤40bb, horário/torneio limite) →
**abre as mesas registradas** e **opera** → com **PAUSA/TAKEOVER** a qualquer
momento (você assume ao vivo; depois reativa ou desabilita o bot).

Construção incremental, por risco crescente (cada fase valida antes da próxima):

- **Fase 0 (feito):** leitura de mesa + conselho pré-flop (observação), ICM/PKO.
- **Fase 1 — Grade + Config de sessão (risco ZERO, só leitura):** ler o lobby
  (nome, buy-in, tipo, horário, status de inscrição); schema de config desta
  política (§7). Localizar/avaliar os módulos históricos de lobby antes de reusar.
- **Fase 2 — Controle PAUSA/TAKEOVER (segurança, antes de qualquer execução):**
  hotkey que para o envio de input e devolve as telas a você; reativar/desabilitar.
- **Fase 3 — Registrador SUPERVISIONADO:** fluxo da `ESTRATÉGIA DE INSCRIÇ.txt`
  (reserva atômica custo+vaga, sem duplicidade, confirmação por inscrição),
  cursor humano (spec de movimento). Abre as mesas registradas.
- **Fase 4 — Execução de ações (MAIOR RISCO: conta/ToS):** detectar a vez, clicar
  fold/call/raise pelo conselho, via cursor humano, envio único, revalidação na
  chegada; rebuy PKO≤40bb. Pausa sempre disponível.
- **Fase 5 — Autonomia:** registro autônomo com guardas (sem confirmação por
  inscrição) + agendador (corte por horário/torneio).
- **Futuro:** HUD por ID de vilão + base de mãos jogadas → estudo de linhas com
  perda de EV. (Ver [[visualpilot-hud-vip]].)

**Risco (uma vez, sem rodeios):** registro e execução autônomos num cliente real
de poker contra o ToS têm risco de banimento de conta. Por isso a ordem acima é
observação→supervisionado→autônomo, com PAUSA/TAKEOVER construído ANTES da execução.
