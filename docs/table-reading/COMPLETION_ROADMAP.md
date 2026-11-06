# Roteiro de conclusão do leitor observador

## Resultado desta rodada
Replay de oito estados derivados de uma captura real: original, board removido, carta central removida, recuperação, brilho 70%, desfoque moderado, número obstruído e recuperação final. Cinco retornaram Jc/5d/3c; três recusaram corretamente. Não houve board incorreto aceito nesses oito casos. Não são oito mãos independentes. Testes adicionais de contrato verificam sequência 3/0/2/4/0/5/3 cartas, erro OCR seguido de recuperação e entradas inválidas.

## Sequência e critérios

| Etapa | Trabalho | Critério para avançar | Ambiente |
|---|---|---|---|
| 1 — corpus e cobertura | Inventariar exemplos por rank/naipe, posição Hero/board, tamanho operacional e fase; separar calibração de avaliação | Cada amostra com PNG original, rótulo humano e hash; faltas explícitas | Laboratório |
| 2 — erros conhecidos | Reproduzir 8h→3h; 9d/9s não identificado; Ks reduzido quando dentro da faixa operacional | Caso antes/depois reproduzível, sem trocar erro por outro nas regressões | Laboratório com evidências originais |
| 3 — mesa sem ação | Rever capturas de espectador e lobby, geometrias e cantos | Mesa confirmada ou rejeição explicada; lobby não enviado ao OCR no conjunto rotulado | Laboratório, confirmação Windows |
| 4 — board e botões | Flop/turn/river reais, 52 identidades de carta quando disponíveis, quantidades/ordem, valores e pré-seleções | Relatório separado de acertos, erros aceitos e abstenções; zero erro aceito no conjunto de aceitação acordado, sem ocultar baixa cobertura | Laboratório |
| 5 — rodada Windows única | Uma mesa, fases 0/3/4/5, botões, sem ação, mover/redimensionar na faixa operacional, minimizar/restaurar, falha de OCR | Comparação visual/JSON e tempos por etapa, registros pontuais de divergências | Windows com PPPoker |
| 6 — escala 1→2→6 | Separação entre mesas, limites globais, obstrução e perda de identidade | Nenhuma transferência de cartas entre fontes; falhas bloqueadas, memória e latência mensuradas | Laboratório + Windows |
| 7 — estabilidade | Sessão prolongada, recursos GDI, RAM, armazenamento e recuperação | Limites definidos antes do ensaio e relatório sem crescimento persistente inexplicado | Windows |

Não há prazo confiável para concluir sem o corpus de avaliação e os PNGs dos erros conhecidos. Cronograma orientado por marcos: etapas 1–4 primeiro; preparar uma sessão Windows para etapa 5 após revisão dos resultados; ampliar para 6 e 7 somente após resolver falhas bloqueantes. Não solicitar sessões reais repetidas sem objetivo definido.

## Pendências da próxima sessão Windows (agrupar)

- Cartas Hero e comunitárias: valores e naipes, inclusive 8 e 3, sem exigir jogar uma mão específica.
- Flop, turn e river reais; board vazio não deve ser confundido com leitura válida.
- Fold/Call/ Raise e Fold/Check/Bet; valor em BB; F/C e outras pré-seleções.
- Mesa sem botões + lobby; tamanho operacional previamente definido para até seis mesas.
- Movimento, perda/retorno da janela e métricas finais; evidência apenas em divergências.

## Escopo e limites

Concluir observador não significa concluir estratégia GTO ou execução de apostas. Não existe garantia universal de 100% de OCR. Os erros devem ser medidos com cobertura e tamanho da amostra; uma taxa em exemplos reutilizados não substitui conjunto independente. A primeira entrega não precisa suportar mesas extremamente pequenas; definir e informar a faixa validada.
