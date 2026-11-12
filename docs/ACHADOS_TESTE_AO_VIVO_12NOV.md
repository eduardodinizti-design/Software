# Achados do teste ao vivo — 12/11/2026 (operar_mesa --arm --auto-arm --overlay)

Postura (regra do Eduardo): **ao achar um erro, NÃO travar — anotar e seguir o fluxo.**
O operador já se comporta assim (abstém e continua; nunca misclica). Lista p/ corrigir depois.

## ✅ Funcionou ao vivo
- FOLD real, correto e verificado (DONE REAL): Q3o, T3o foldados. Travas OK (1 ação/mão, revalida, verifica efeito).
- Auto-arm (--auto-arm) e faixa de status (--overlay) funcionando.

## 🐞 A corrigir (não bloqueiam; operador abstém com segurança)
1. **RAISE/shove não executa — sem preset p/ o alvo.** Erros `SEM_PRESET_PARA_ALVO:32.3` e `PRESET_CANCELADO` no `RaiseSequencer`. O alvo (ex.: 32.3bb ≈ stack = shove) não casa com nenhum preset de aposta do painel. Resultado: o operador NÃO completa o raise e abstém → o hero pode ficar no relógio até timeout. **Fix:** (a) mapear alvo→preset de forma robusta, incl. botão all-in/shove; (b) **fallback seguro** quando o raise falha — se Check disponível, CHECK (grátis); senão FOLD — para o hero NUNCA ficar pendurado.
2. **Possível raise em spot pós-flop por board não lido.** Vimos `BOARD_NOT_CONFIRMED` com frequência; se o board não é lido, o advisor trata como PRÉ-FLOP e pode recomendar raise/shove no que já é pós-flop. Memória diz que o operador NÃO deve executar pós-flop. **Fix:** endurecer a leitura do board (ligado ao [[grade_felt_rois]] / ROI) e/ou travar o raise quando o board é incerto.
3. **Leitura do board/cartas oscila** na mesa REENTRY (hero=None / BOARD_NOT_CONFIRMED em vários frames) → gera ABSTAIN em spots que deveriam ser jogáveis. Base da solução já existe (felt-ROI), falta robustez da leitura interna do crop.

## 🔴 Confirmados pelo Eduardo ao vivo (prioridade)
4. **NÃO identifica LIMP ao vivo** (Eduardo confirmou, 2x). `count_limpers` depende de LER o chip de aposta (~1bb) de cada vilão; a leitura de `bets`/`bet_bb` por assento não está pegando os limps. Consequência: pote tratado como não-aberto → abre/raise mão que devia foldar (ex.: Q9o após limp = FOLD). **Causa = leitura de aposta dos vilões (visão), não a lógica.** Fix real = ler bet_bb por assento de forma confiável.
5. **Raise/Bet não clica o TAMANHO da aposta.** Precisa: abrir painel → clicar no preset/size (2x quando é 2x) → confirmar; e tratar **all-in/shove** (hoje `SEM_PRESET` quando alvo=stack). O leitor do painel (`raise_panel.py`) só vê presets 2x–4x + confirmar; falta botão all-in/slider-máx.
6. **Decisões LENTAS.** Por ciclo faz capture + detect_table_crops + advise_table (OCR pesado) + read_action_buttons. Com `--intervalo 0.8` + latência de OCR, cada decisão leva ~1–1.8s → arrisca timeout no relógio de 20s. Fix: baixar intervalo, cortar trabalho redundante (mesa única não precisa round-robin), e/ou cachear leituras estáveis na mão.

## ✅ CORREÇÃO 1 (12/11): leitura de APOSTAS dos vilões — FEITA e validada ao vivo
Causa: em `read_bets` (table_state.py) a região do valor começava em `cx+cw` (mas `cx`
é o CENTRO do chip → pulava meio chip, cortando dígitos) e tinha altura fixa ±16px
(CORTAVA o texto na vertical). Resultado: perdia/erravas apostas (0,5→1.5; raise de 4bb
não lido). FIX: região a partir da borda direita (`cx+cw//2`), altura ±0.02h, largura
0.16w, upscale 4x + OTSU. Validado: 0,5/0,9/1,0/4,0 → 4/4 no gabarito; ao vivo leu 0,8 e
1,0 com vírgula limpa. Base de `count_limpers`/opener agora confiável. Testes 13+19 OK.
PRÓXIMO da percepção: confirmar limp→spot ao vivo; posições; e `TABLE_6HANDED_USING_9MAX_REF`.

## 🧠 VEREDITO (12/11, após 2ª rodada ao vivo): EXECUÇÃO pronta, PERCEPÇÃO não
- **Execução OK:** FOLD/CALL/CHECK clicam certo e verificam (DONE REAL); raise com preset (lock_hand) e all-in via barra (slider drag) implementados e testados (17 testes). Velocidade 3× melhor. Faixa de status (--overlay) + auto-arm (--auto-arm) funcionando.
- **Percepção NÃO confiável (o gargalo real):** o agente **só lê as apostas dos BLINDS**, nunca as dos vilões → **não vê LIMP nem opener** → classifica quase tudo como `open_raise`/first-in e usa range errado. Erros grotescos ao vivo: **CALL de T2o**, **open de J8o/Q9o** (deviam foldar). Também: `TABLE_6HANDED_USING_9MAX_REF` (ranges 9-max numa mesa 6-max). 
- **Conclusão:** NÃO rodar o operador armado auto-jogando até a LEITURA DE CONTEXTO (bet_bb por assento, posição, spot, limp) ficar robusta. O braço de execução está pronto; o olho não. Próximo trabalho = visão das apostas/posição/spot (base de `count_limpers` e da escolha de nó), em `table_reading/table_state.py`.

## Observação
- Monitor ao vivo afrouxado p/ não pingar a cada raise conhecido (ruído); segue avisando de cliques reais (AGIU), erros/traceback e pausas.
