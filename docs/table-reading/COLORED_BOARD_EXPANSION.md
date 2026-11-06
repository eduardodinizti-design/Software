# Ampliação de evidência: faces coloridas

Varredura de 54 PNGs locais do diretório aistudio, usando propostas geométricas e busca de contornos sem OCR de valores para selecionar candidatos. Cinco regiões com pelo menos três faces foram localizadas. Quatro são adicionais ao flop já usado. Rótulos transcritos visualmente antes de executar leitura de ranks/naipes.

Resultados: quatro flops e um river, 17 ocorrências de cartas, todas corretas nesses recortes. 16 identidades distintas: 2h, 2s, 3c, 3d, 3s, 4h, 4s, 5d, 6h, 7d, Ad, Jc, Jd, Kd, Kh, Qd. Nenhum turn real neste conjunto. A ocorrência repetida é 2s. Nenhuma alteração do leitor foi necessária nesta rodada.

O river real é 4s/2s/Qd/Kh/4h. Os flops adicionais são 3d/Ad/3s, Kd/Jd/2s e 2h/7d/6h. O flop Jc/5d/3c é repetido do conjunto anterior e NÃO deve ser contado como evidência nova.

Limites: seleção automatizada favorece boards já localizáveis. Não demonstra recall de todos os 54 PNGs, nem que não há outros boards perdidos. São imagens históricas do acervo de desenvolvimento, sem independência de origem comprovada. O replay usa os recortes detectados e não simula estabilidade temporal/Windows. Não resolve o erro Hero 8h→3h.

Reprodutor: tools/evaluate_colored_boards.py; esperado, resultado e hashes em colored-board-expansion.json. Próximas lacunas: turn real, 8 nas comunitárias e maior variedade de naipes/tamanhos operacionais; reunir na rodada única Windows quando houver disponibilidade, sem abrir novas mesas agora.
