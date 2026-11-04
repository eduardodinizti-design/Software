# VisualPilot — Módulo 4: Auditoria em CSV & Monitoramento Contínuo da Janela

Este plano detalha a implementação do sistema de **registro persistente em arquivo CSV** com rotatividade diária automática e o **monitoramento proativo de integridade da janela do PPPoker**, garantindo rastreabilidade histórica completa de cada ação e proteção imediata contra cliques fora de posição caso a janela seja fechada ou sofra alteração drástica de resolução.

---

### User Review & Critical Decisions

> [!IMPORTANT]
> **Decisões confirmadas pelo usuário:**
> 1. **Política de retenção do CSV:** Arquivo único acumulativo com rotatividade diária automática (`clicks_audit_YYYY-MM-DD.csv`), garantindo que logs antigos não sobrecarreguem o arquivo diário e preservando histórico limpo.
> 2. **Reação a anomalias na janela:** Abortar imediatamente qualquer tentativa de clique pendente, gravar um registro formal de erro no CSV com as coordenadas e dimensões anomalizadas, e entrar em estado de espera até que a janela do PPPoker seja restaurada.

---

### 1. Overview & Core Concept

* **Problema a Resolver:** Durante sessões longas de jogo no Windows, o jogador pode fechar a janela sem querer, arrastá-la bruscamente para outro monitor ou mudar a escala. Se o bot disparar um clique nessa janela inexistente ou deformada, ele pode clicar em programas de terceiros, no desktop ou em botões errados. Além disso, é indispensável auditar cada decisão que o bot tomou ao longo do dia para conferência financeira de fichas.
* **O que Esta Entrega Adiciona:**
  1. `AuditLogger` persistente com escrita imediata (*flush*) em arquivo CSV estruturado com rotação diária.
  2. `WindowMonitor` em thread secundária ou pré-verificação síncrona que mede a taxa de variação de área e proporção da janela do PPPoker ($\Delta \text{dim} > 20\%$) e status de visibilidade (`isMinimized` / `isClosed`).
  3. Abortador de clique com *fail-safe* que cancela o despacho do PyAutoGUI e grava o incidente no CSV.
  4. Visualizador do histórico de auditoria CSV integrado diretamente no painel web interativo.

---

### 2. User Experience & Visual Design

#### Fluxo Operacional de Auditoria & Proteção
```
                  [Tentativa de Ação no Torneio]
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │ 1. Checagem de Integridade da Janela         │
         │    (Existe? Visível? Dimensões estáveis?)    │
         └──────────────┬───────────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
    [Anomalia Detectada]          [Janela Íntegra]
         │                             │
         ├── Aborta clique             ├── Aplica Jitter e Bézier
         ├── Status: ABORTED           ├── Dispara clique mecânico
         └── Loga no CSV               └── Loga no CSV (SUCCESS)
```

#### Estrutura do Arquivo CSV Diário (`logs/clicks_audit_YYYY-MM-DD.csv`)
* `timestamp_iso`: Timestamp ISO-8601 em fuso horário local e UTC.
* `event_type`: `CLICK_ATTEMPT`, `CLICK_SUCCESS`, `CLICK_ABORTED`, `WINDOW_CLOSED`, `RESOLUTION_CHANGED`.
* `status`: `SUCCESS`, `ERROR`, `ABORTED`.
* `tournament_name`: Nome do torneio (ex: "CORUJAO HYPER PKO10K").
* `card_index`: Índice do cartão no lobby.
* `buyin_chips`: Custo do buy-in lido (ex: "50").
* `target_abs_x`, `target_abs_y`: Coordenadas absolutas de clique no desktop.
* `win_left`, `win_top`, `win_width`, `win_height`: Dimensões físicas da janela no momento da ação.
* `duration_ms`: Tempo de deslocamento do mouse em milissegundos.
* `details`: Mensagem descritiva ou causa do erro/abortamento.

---

### 3. Key Product Decisions & Trade-Offs

* **Decisão 1: Gravação Imediata com *Flush* de Arquivo**
  * *Abordagem Escolhida:* Toda linha no CSV é escrita e sofre `file.flush()` + `os.fsync()` imediatamente após o evento.
  * *Por quê:* Se o computador travar, faltar luz ou o processo do Python for encerrado pelo gerenciador de tarefas, nenhuma linha de auditoria é perdida no buffer do sistema operacional.
* **Decisão 2: Tolerância Dinâmica a Redimensionamento vs. Abortamento por Deformação**
  * *Abordagem Escolhida:* Variações suaves de redimensionamento proporcional ($W/H \in [0.40, 0.75]$) são aceitas e reescaladas. Mudanças drásticas (ex: colapso de altura, janela esticada fora da proporção, ou redução $> 35\%$) são tratadas como deformação e disparam abortamento imediato.

---

### 4. Technical Architecture & Data Strategy

```
┌────────────────────────────────────────────────────────────────────────┐
│                        MODULE 4: AUDIT & MONITOR                       │
├────────────────────────────────────────────────────────────────────────┤
│ 1. WINDOW INTEGRITY GUARDIAN                                           │
│    ├── get_window_snapshot() ─────────> [left, top, width, height]     │
│    ├── validate_aspect_ratio() ───────> 0.38 <= W/H <= 0.80            │
│    ├── detect_closure_or_minimize() ──> isMinimized / isClosed         │
│    └── guard_click() ─────────────────> Aborta se inválido             │
├────────────────────────────────────────────────────────────────────────┤
│ 2. ROTATING CSV AUDIT LOGGER                                           │
│    ├── current_log_path() ────────────> logs/clicks_audit_YYYY-MM-DD.csv│
│    ├── log_action(event, status, meta)> Append com thread-safe lock   │
│    └── export_records() ──────────────> Leitura para o painel web      │
├────────────────────────────────────────────────────────────────────────┤
│ 3. WINDOWS PACKAGING & INTEGRATION                                     │
│    ├── Atualização de lobby_clicker.py                                │
│    ├── delivery/lobby_click/ contendo logs/ de exemplo                │
│    └── Pacote ZIP VisualPilot_Modulo4_AutomacaoCliques.zip             │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 5. Plano de Entrega e Verificação

1. **Implementação de `AuditLogger` e `WindowIntegrityGuardian`** em `repo_visualpilot/visualpilot/pppoker/lobby_clicker.py`.
2. **Suíte de Testes Automatizados:**
   * Teste de criação e escrita no CSV com cabeçalhos padronizados.
   * Teste de rotatividade diária automática por data.
   * Teste de detecção de fechamento de janela e gravação de evento `WINDOW_CLOSED`.
   * Teste de detecção de deformação de resolução e gravação de evento `RESOLUTION_CHANGED`.
   * Teste de persistência e *flush* sem corrupção.
3. **Pacote Autônomo Windows:**
   * Regeneração do ZIP `VisualPilot_Modulo4_AutomacaoCliques.zip` incluindo a pasta `logs/` e os novos recursos de monitoramento.
4. **Atualização do Dashboard Web:**
   * Tabela visual em tempo real no applet exibindo as últimas linhas do arquivo CSV de auditoria com filtros por status (`SUCCESS`, `ABORTED`, `ERROR`).
5. **Cinemática Motora Humana (Bézier Cúbica + Jitter via pyautogui.moveTo):**
   * Curva customizada `human_bezier_ease` / `humanBezierEase` modelando aceleração neuromuscular assimétrica (Fase balística rápida até 35% e desaceleração inercial amortecida até 100%).
   * Trajetória não retilínea com pontos de controle $P_1$ e $P_2$ defletidos perpendicularmente e micro-jitter ($\pm 1.5\text{ px}$), eliminando velocidade constante e assinaturas de detecção robótica.
   * Telemetria fisiológica integrada nos registros de auditoria em CSV e no painel de visualização do dashboard.
