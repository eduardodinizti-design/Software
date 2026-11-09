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

## 4. REBUY / ADD-ON (regra obrigatória, pois o bot não cobre)
O bot **não** tem lógica de rebuy nem pós-flop. Enquanto não houver uma regra
codificada, jogar rebuy **só** com uma **decisão fixa pré-definida**, orçada
dentro do buy-in efetivo:

- **Buy-in efetivo = entrada inicial + rebuys planejados + add-on.** É esse
  número que entra no teto (§2.2) e no mínimo-BI (§2.1), não a entrada inicial.
- **Regra fixa sugerida (moderada):** no máximo **1 rebuy** ao bustar dentro do
  período, **+ add-on sempre** que a estrutura torná-lo claramente +fichas/EV.
  Buy-in efetivo ≈ 2–3× a entrada.
- **Recomendação CEO:** **adiar** Rebuy/Add-on até codificarmos a regra, ou
  jogar com alocação menor e essa regra fixa. É a modalidade de maior exposição.

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
  enabled: false               # adiar até regra codificada (§4)
  effective_buyin_multiplier: 3
supervised_confirmation_required: true
```

Nenhum valor absoluto de moeda é preenchido aqui: campo financeiro em branco =
BLOQUEADO, conforme a spec de inscrição.

---

## 8. PRÓXIMOS PASSOS
1. Você valida/ajusta estes guardas (especialmente: PKO só ≥150 BI, 4 simultâneas,
   adiar rebuy).
2. Quando houver executor de inscrição (spec de inscrição), esta política vira o
   filtro de elegibilidade dele.
3. Evoluções: regra codificada de rebuy/add-on; seleção por EV/estrutura com dados
   reais; late-reg com critério explícito de stack recebido.
