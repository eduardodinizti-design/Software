# Confirmação de números preservando a proporção

Correção limitada: quando a segmentação produz leituras válidas concordantes e leituras vazias, repete OCR nas duas máscaras de tinta, preservando a proporção do símbolo. Exige quatro confirmações iguais e consistentes com as observações anteriores. Não substitui conflitos como 7/9, não reduz limiares e não altera a captura.

Validação: 40 testes descobertos, 39 passaram em Linux, 1 teste GDI Windows ignorado. Seis novos testes de contrato usam OCR simulado e não medem precisão. Reavaliação com OCR real das oito mesas do conjunto de desenvolvimento: 16 cartas corretas, zero incorretas, zero desconhecidas. Conjunto reutilizado, não avaliação independente.

Limitação: o JSON do par 9d/9s mostrou conflito 7/9 à esquerda e leituras vazias/9 à direita. Esta correção pode recuperar concordância incompleta, mas NÃO resolve por decreto o conflito da primeira carta. O PNG original desse caso ainda precisa ser executado e comparado antes de declarar a falha corrigida. Não é necessário capturar outra mão: preservar mesa-01.png e resultado.json existentes.
