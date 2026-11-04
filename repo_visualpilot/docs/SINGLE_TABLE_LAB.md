# Laboratório de uma mesa — 25/10/2026

## Falha reproduzida e corrigida

O novo teste usa imagens reais gravadas e um cenário controlado de alteração
somente do board. Envia PNG por TCP local, decodifica no receptor, alimenta
PerceptionSession, executa os subprocessos OCR reais e verifica eventos e JSONL.
Não substitui OCR por mocks nem reduz o limiar de confiança.

Antes da correção, a terceira geração devolvia `hero=[]` em vez de `Th,4d`.
O runtime agendava apenas as regiões alteradas, mas publicava o resultado como
um snapshot de todas as cartas, confundindo "não processado" com "ausente".
Agora cada nova geração revalida as quatro regiões de cartas. Frames idênticos
continuam sendo deduplicados. Isso privilegia correção no piloto de uma mesa;
o custo em seis mesas precisa ser medido antes de ampliar a carga.

Cenários: Hero 5c/2s sem board; mudança para Th/4d com flop 7h/As/Ts;
alteração controlada do board com Hero inalterado. O teste exige leituras
parciais e completas, uma identidade de mesa, gerações crescentes e registro
JSONL. Com imagens continuamente reenviadas, as leituras completas não podem
ser publicadas como expiradas. A remoção controlada do board é um teste de
invalidação visual, não uma afirmação sobre uma sequência legal de poker.

## Geometria de campo

O teste HostGeometryTests reproduz as coordenadas recebidas: mesa
893×1587 indevidamente vinculada a uma janela hospedeira 5760×2160.
A correção preserva o recorte visual nesse caso, mantendo vínculo nativo para
janelas de tamanho compatível.

## Limites da evidência

Este teste usa TCP local e replay de imagens, não captura de um desktop Windows
nem Wi-Fi físico. Não comprova o frontend Streamlit, todos os 52 valores/naipes
em todas as posições, turn/river, desempenho sustentado, nem os executáveis.
As evidências recebidas do campo estavam reduzidas/cortadas: não reconstituem
os pixels perdidos do frame original de A♥/4♠. Não declaramos esse caso resolvido.
O bloqueio visual pela janela hospedeira e o snapshot parcial vazio têm causas
reproduzidas; os demais portões de docs/LAB_RELEASE_GATE.md seguem pendentes.

Execução: `.venv/bin/python -m unittest discover -s tests -p test_single_table_pipeline.py -v`

## Resultado desta execução

- Regressão de mudança somente no board: falhou antes e passou depois.
- Teste integrado ampliado, exigindo também leitura completa: passou em 10,409 s
  no total dos três cenários. Esse número é duração de teste, não latência por frame.
- Suíte final: 151 testes executados, OK (3 skips), em 52,270 s no Linux.
- O teste antigo de integração agora alimenta frames continuamente durante o
  carregamento do OCR; a expiração de uma imagem única antiga continua válida.
- Não houve validação física Windows nesta execução; nenhuma nova instalação
  foi solicitada ao usuário.
