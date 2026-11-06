# Turn e naipes: rodada de laboratório

Usamos o river real 4s/2s/Qd/Kh/4h e substituímos artificialmente a quinta face por um trecho de fundo da mesma imagem. Não é captura real de turn e não aumenta o número de mãos independentes.

Antes: nas larguras 702 e 835 pixels o turn controlado foi reconhecido; em 575 pixels os números 4 e 2 foram reconhecidos, mas seus naipes de espadas retornaram SUIT_UNREADABLE, bloqueando todo o board. Depois: quando a extração normal do naipe não identifica nada, o leitor tenta o mesmo trecho diretamente nos pixels nativos. Mesmos limiares do leitor de naipes; resultados já identificados não são substituídos.

Após a mudança, 4s/2s/Qd/Kh foi reconhecido como TURN nas três larguras. Caso com quinta carta parcialmente encoberta continua BOARD_PARTIAL_OR_OBSTRUCTED. Cinco boards coloridos anteriores foram reexecutados: 17 ocorrências corretas mantidas (quatro flops e um river). Testes contratuais verificam que o retry só ocorre após SUIT_UNREADABLE e não substitui um naipe já reconhecido.

85 testes na suíte: 84 passaram, 1 exclusivo Windows ignorado. Não é validação da faixa completa de resoluções nem correção do erro Hero 8h→3h. Falta turn real de face colorida, ampliar referências com 8 e mais exemplos independentes.

Reprodução: tools/evaluate_turn_variants.py --assets DIRETORIO. Resultados: turn-variants.json; regressão real: turn-regression.txt. Sem cliques, testes novos do Windows ou armazenamento contínuo.
