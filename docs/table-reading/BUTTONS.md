# Leitor experimental de botões — somente observação

Execute `python ler_mesas.py --hwnd 264430 --continuo --intervalo 1 --botoes`.
Para uma evidência pontual: `python ler_mesas.py --hwnd 264430 --botoes --save`.

A faixa de busca é relativa ao recorte atual da mesa azul. Três regiões coloridas alinhadas precisam ser encontradas; sua cor/posição nunca determina a ação. Dois modos de OCR precisam concordar no rótulo e valor. Reconhece Fold, Check, Call, Bet, Raise e valores decimais opcionais em BB. F/C é marcado PRESELECT; não é prova de ação disponível. Pagar e textos desconhecidos permanecem não identificados, com o texto bruto no JSON. Não há cliques nem confirmação da vez do Hero. Não identifica street/board.

Botões são opcionais para preservar o desempenho do leitor atual. O custo adicional aparece em button_reading. A região é comum a pré e pós-flop neste layout, mas outros temas/idiomas/tamanhos precisam de validação. Dois OCRs concordantes ainda podem errar; status experimental.

Verificação de desenvolvimento: seis das oito regiões históricas produziram fileira de botões. Uma mostrou Fold/Call 1,0 BB/Raise; cinco mostraram F/C e Check ou Call, deixando Pagar sem ação atribuída. Duas regiões não produziram fileira. Esses resultados são observações de OCR, não taxa de acerto independente. Resultados completos em button-development-observations.json. Testes de contrato incluem conflito de valor, ausência de botões, pré-seleção, redução de escala, falha OCR e encaminhamento do recorte pelo pipeline.

As novas imagens do usuário foram vistas na conversa, mas seus PNGs originais não estão disponíveis no filesystem para executar OCR local: não declarar validação automática de Fold/Call 2,2 BB/Raise ou Fold/Check/Bet nesses arquivos. O JSON pós-flop 2026-11-06 enviado pelo usuário revelou ainda um erro do leitor Hero: retornou 3h/4h onde a imagem mostra 8h/4h. Permanece pendente e independente deste módulo.
