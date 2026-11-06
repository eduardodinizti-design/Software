# Cobertura auditável do corpus local

7 arquivos de imagem distintos; 8 recortes rotulados. Nenhum conjunto independente de avaliação. Arquivos verificados por SHA-256. Não equivalem necessariamente a mãos independentes.

| Grupo | Ocorrências rotuladas | Identidades distintas de 52 | Ranks ausentes |
|---|---:|---:|---|
| Hero | 16 | 13 | 4, 8, A |
| Board | 3 | 3 | 2, 4, 6, 7, 8, 9, T, Q, K, A |

## Frequência por carta (Hero / board)

| Carta | Hero | Board |
|---|---:|---:|
| 2c | 0 | 0 |
| 2d | 1 | 0 |
| 2h | 0 | 0 |
| 2s | 1 | 0 |
| 3c | 0 | 1 |
| 3d | 0 | 0 |
| 3h | 1 | 0 |
| 3s | 0 | 0 |
| 4c | 0 | 0 |
| 4d | 0 | 0 |
| 4h | 0 | 0 |
| 4s | 0 | 0 |
| 5c | 1 | 0 |
| 5d | 0 | 1 |
| 5h | 1 | 0 |
| 5s | 0 | 0 |
| 6c | 0 | 0 |
| 6d | 0 | 0 |
| 6h | 2 | 0 |
| 6s | 0 | 0 |
| 7c | 1 | 0 |
| 7d | 0 | 0 |
| 7h | 0 | 0 |
| 7s | 0 | 0 |
| 8c | 0 | 0 |
| 8d | 0 | 0 |
| 8h | 0 | 0 |
| 8s | 0 | 0 |
| 9c | 0 | 0 |
| 9d | 1 | 0 |
| 9h | 0 | 0 |
| 9s | 0 | 0 |
| Tc | 1 | 0 |
| Td | 0 | 0 |
| Th | 0 | 0 |
| Ts | 0 | 0 |
| Jc | 0 | 1 |
| Jd | 1 | 0 |
| Jh | 0 | 0 |
| Js | 0 | 0 |
| Qc | 0 | 0 |
| Qd | 2 | 0 |
| Qh | 0 | 0 |
| Qs | 2 | 0 |
| Kc | 1 | 0 |
| Kd | 0 | 0 |
| Kh | 0 | 0 |
| Ks | 0 | 0 |
| Ac | 0 | 0 |
| Ad | 0 | 0 |
| Ah | 0 | 0 |
| As | 0 | 0 |

## Lacunas prioritárias

- Board real: só um flop rotulado (Jc/5d/3c); nenhum turn ou river real rotulado neste corpus.
- Hero: ampliar os ranks ausentes e pares que geraram erro (8/3, 9 e K), com exemplos novos separados da calibração.
- Botões: saídas OCR disponíveis, mas faltam rótulos humanos completos por captura e exemplos independentes de Check/Bet e valores.
- Geometria: os tamanhos listados são tamanhos existentes, não faixa certificada; ainda falta definir a disposição operacional de seis mesas.
- Mesa sem ação e lobby: adicionar exemplos originais rotulados, incluindo a rejeição conhecida do menu.
- Imagens embutidas no chat e confirmações do usuário são evidência qualitativa; não entram como PNGs reproduzíveis nem como novas amostras independentes.
- Transformações de uma imagem contam como testes de robustez, nunca como novas cartas/mãos reais.

## Tamanhos presentes

570x1004, 575x1014, 699x1244, 703x1237

Este inventário mede presença de exemplos, não precisão de reconhecimento. Não inferir 100% por testes aprovados nem combinar cobertura Hero com board: são regiões e extrações diferentes.

## Conjunto legado localizado (não revalidado)

8 PNGs disponíveis, 4 entradas de rótulo sem PNG. 10 cartas Hero distintas e 8 comunitárias distintas nos rótulos herdados. Mesmo vídeo, não fonte independente. Não somados à cobertura validada do leitor atual.

Hero: 2s, 3s, 4d, 5c, 7d, 8h, Jd, Js, Kd, Th

Board: 5d, 7h, As, Kc, Kd, Qh, Th, Ts

Próximo trabalho: inspecionar rótulos e executar estes recortes no leitor atual, especialmente os exemplos com 8h. Não são a captura exata que produziu 8h→3h no Windows.
