# NVT Range Lab: pacote de estratégia para outro agente

Este pacote é para um agente de IA entender a estratégia pré-flop de MTT do NVT Range Lab: os números (frequência e EV de cada mão em cada spot) e a lógica (de onde vem cada range, que ajustes o trainer faz, como se corrige uma resposta e o que está validado).

Gerado em 06/11/2026 a partir do commit `356340d`: 6.432 nós, 5.007 deles validados. Já inclui os arquivos do HRC recalculados entre 31/10 e 01/11.

**Comece por aqui:**
1. Este arquivo.
2. `ranges/integracao-ranges.md`: o formato do pacote de ranges.
3. `ranges/nvt-ranges-validados.json` para responder sobre o que o trainer cobra.

Para entender o porquê de cada decisão, use o resto.

## O que tem em cada pasta

| Pasta / arquivo | O que é | Quando usar |
|---|---|---|
| `ranges/nvt-ranges.json` | Todos os nós exportados pelo motor: modo (chip EV, ICM, PKO, PKO+ICM) × fase × stack × spot × posição × quem agiu antes, com frequência e EV das 169 mãos, fonte e se está validado. | Responder "o que fazer com a mão X no spot Y". |
| `ranges/nvt-ranges-validados.json` | Só os nós das famílias validadas, que são os que entram nos treinos. | Quando a resposta precisa ser a "oficial". |
| `ranges/integracao-ranges.md` | Formato dos JSON (campos, ordem das mãos, ações, unidades de EV). | Antes de ler os JSON. |
| `ranges/nvt-ranges-client.ts` | Cliente de exemplo (~100 linhas) que lê o pacote e responde por mão. | Para programar em cima do pacote. |
| `docs/validacao-ranges.md` | Regra de validação: o que precisa bater com uma referência externa para entrar no ar. | Para saber o quanto confiar num nó. |
| `docs/auditoria-ranges.md` | Auditoria mão a mão de todas as fontes: mãos que destoam das vizinhas, pares fora de ordem e o custo em EV. | Para avaliar a qualidade de um range. |
| `docs/auditoria-hrc.md` | Auditoria dos arquivos do HRC: contradições entre frequência e EV por nó. | Para saber onde o HRC é menos confiável. |
| `docs/auditoria-ranges-solver.md`, `docs/auditoria-solver-2026-10-25.md` | Auditorias anteriores do solver. | Histórico. |
| `AGENTS.md` | Notas de engenharia do projeto: cada decisão tomada, com o porquê (em inglês). | Para entender o motor a fundo. |
| `codigo/strategy`, `codigo/domain`, `codigo/icm` | O código-fonte do motor de estratégia (TypeScript). | Quando a documentação não basta. |

## Como o trainer chega numa resposta

1. **Fonte.** Cada spot tem uma fonte, nesta ordem de preferência:
   - **HRC (Holdem Resources Calculator):** solver pré-flop. Arquivos em chip EV (25bb e Blind War 8–15bb), ICM de 9 jogadores (pré-ITM, bolha e mesa final, cada um com stacks iguais, curtos nas primeiras posições e curtos nas últimas), PKO + ICM nas mesmas fases, e PKO de começo e meio de torneio (Multi Table ICM + bounty).
   - **Nash:** push/fold e call vs shove até 15bb, em chip EV e ICM.
   - **Tabelas do time:** opens por stack, decididas pelo time.
   - **Referências calibradas:** onde ainda não há solver. Elas não são validadas.
2. **Ajustes que o trainer aplica por cima da fonte** (o pacote já vem com tudo aplicado):
   - Mixes abaixo de 5% são descartados.
   - Pares ficam na ordem natural: um par maior nunca folda quando um menor joga.
   - Uma mão que destoa das vizinhas da mesma família de kicker é suavizada quando o EV do HRC mostra que é ruído: jogar como as vizinhas custa no máximo 0,05bb, ou 0,02% do prize pool no ICM.
   - Quando a frequência do HRC contradiz o EV dele, vale a ação de maior EV.
   - Empate de EV vira mix: as duas ações são aceitas.
3. **Correção de uma resposta:**
   - Está certa se for a ação principal ou uma ação do mix.
   - Também está certa se perder no máximo 0,05bb / 0,02% de EV para a melhor ação.
   - Regra relativa: também está certa se perder até 10% do EV da melhor ação, com teto de 0,3bb / 0,06%.
   - Fora disso, é erro.
4. **Validação:** um range só entra no treino se a família dele passou na comparação com uma referência externa. Os nós do pacote trazem o campo `validated`, e o resto aparece como "Em validação".

## Regras para o agente

- **Não invente números.** Toda frequência ou EV citado deve sair dos JSON. Se o spot não está no pacote, diga que não está.
- **Diga a fonte.** Diga a fonte do nó e se ele está validado. Um nó com `validated: false` é referência, não a resposta oficial.
- **Atenção ao ICM com stacks diferentes.** Os nós de ICM têm o campo `spread`, que é a distribuição de stacks da mesa. A mesma mão pode mudar de ação entre "iguais", "curtos_ini" e "curtos_fim".
- **EV em unidades diferentes.** O campo `evUnit` diz a unidade: `bb` (chip EV e PKO) ou `pct` (% do prize pool, no ICM). Não compare números de unidades diferentes. Quando `evUnit` é `null`, a fonte não tem EV (tabelas do time, referências) e só as frequências valem.
- **Pacote parado no tempo.** Ele foi gerado na data e no commit que estão em `generatedAt` e `engineCommit`, no topo de `nvt-ranges.json`. Se os ranges do app mudarem, peça um pacote novo.
