# Reavaliação das oito capturas antigas

Rótulos conferidos visualmente antes de executar o leitor atual. Os oito recortes usam cartas de fundo branco, diferentes das faces coloridas das capturas recentes. O replay usa recortes já disponíveis: não valida a localização automática dentro do desktop.

| Grupo | Corretas | Erradas aceitas | Não identificadas |
|---|---:|---:|---:|
| Hero, 16 ocorrências | 11 | 0 | 5 |
| Board, 12 ocorrências em três mãos/capturas | 0 | 0 | 12 |

Cinco regiões sem board permaneceram sem cartas identificadas. Os boards presentes incluem flop, turn e river, mas o detector atual não os confirmou; não contam como suporte validado dessas fases. Os tempos/capturas vêm do mesmo vídeo, não de fontes independentes.

O exemplo 48_0 com 8h/Jd foi lido corretamente. Isso NÃO resolve a confusão recente 8h→3h: são pixels e tema diferentes. As abstenções Hero: Th em 82_0; Th/4d em 116_0; 5c/2s em 116_1. As duas últimas capturas mostram estado Fold/escurecimento, mas não foi isolada experimentalmente a causa de cada abstenção.

Decisão: manter suporte inicial ao tema de faces coloridas e registrar fundo branco como cenário separado, sem relaxar filtros para aprová-lo artificialmente. Próximo foco útil no laboratório: ampliar referências de faces coloridas disponíveis e testar mais ranks/naipes no board; deixar a captura de turn/river desse tema na rodada única Windows. Não pedir ao usuário que jogue agora.

Relatório por captura, hash, esperado e resultado: legacy-replay-results.json. Reprodutor: tools/evaluate_legacy_reading.py. Nenhuma alteração do OCR operacional nesta rodada.
