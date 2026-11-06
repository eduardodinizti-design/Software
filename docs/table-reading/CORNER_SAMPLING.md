# Confirmação de cantos sem botões — laboratório

Mudança: manter o método atual primeiro; quando ele rejeita, extrair as máscaras verdes diretamente na resolução nativa do recorte e só então normalizar a forma. Os quatro ícones precisam atingir 0.65 no mesmo método. Não mistura os melhores cantos de métodos diferentes, não reduz limite e não aceita três de quatro ícones. As demais verificações do detector permanecem.

Resultado controlado: oito regiões de capturas históricas, faixa inferior de botões removida artificialmente, escalas 1, 0.75 e 0.5, total 24 variantes. Confirmação apenas dos cantos passou de 9 para 15; os 9 acertos prévios foram mantidos. Nove variantes continuam rejeitadas. Não é taxa de precisão geral, nem ensaio integral em 24 mesas independentes. Não significa que o detector completo ou OCR passou em todas elas. As regiões históricas já participaram do desenvolvimento.

Negativos: remoção individual de cada canto rejeitada; região uniforme azul rejeitada. Doze testes preexistentes de pipeline também passaram. O lobby específico do usuário não está disponível em PNG original local; não declarar sua nova validação visual com base nesses negativos.

Diagnóstico adicional: corner_diagnostics contém método, scores originais e scores alternativos quando disponíveis, permitindo investigar o caso menu=0.635 sem adivinhar. O PNG daquele caso também permanece pendente. Nada muda no OCR de ranks; o erro 8h→3h continua aberto.
