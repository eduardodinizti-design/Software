# Correção da lacuna K♥ / K♠

A lacuna reproduzida era no reconhecimento do valor, não no naipe. O OCR
retornava K com confiança insuficiente nas duas fixtures sintéticas. O recorte
continha margens e a rota de binarização descartava tons nas bordas suavizadas.

A correção em card_rank.py preserva o glifo em cinza. Otsu localiza o componente
interno dominante, sem transformar os pixels enviados ao OCR. Duas margens
(4 e 8 pixels) precisam produzir o mesmo valor que a leitura original, ambas
com confiança >= max(0.95, limiar solicitado). Componentes tocando a borda e
caracteres fora do baralho não são aceitos por essa rota. Não há tratamento
especial para K nem busca de pixels/nomes de fixtures no código de produção.

## Evidência

- before.log: seis subcasos falharam (Kh/Ks × original/escurecido/desfoque leve).
- after.log: todos passaram; imagem branca e ruído permanecem pendentes.
- production-threshold.json: 36/36 fixtures sintéticas reconhecidas com o leitor
  padrão 0.90. Kh e Ks: confiança 0.988467276096344.
- O teste permanente das 36 cartas foi elevado de 0.75 para o padrão 0.90.
- Não foram alteradas as imagens, o gerador nem o limite de produção.

Escopo: lacuna dessas fixtures no ROI de turn. Variações derivadas não são
amostras reais independentes. Isso não homologa as 52 cartas em todas as
posições/escalas do Hero/board nem a captura no Windows físico. O relatório
anterior permanece como evidência do estado antes da correção.

Suíte final: 157 testes executados em 62,240 segundos, sem falhas, 3 skips.
Inclui fluxo TCP/OCR de uma mesa com flop/turn/river e renderização Streamlit.
