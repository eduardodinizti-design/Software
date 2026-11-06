# Uma rodada Windows após a regressão integrada

Não executar agora por obrigação. Este é o roteiro consolidado para quando houver mesa disponível, sem induzir aposta ou ação específica.

1. Atualizar a branch `fix/strict-client-capture` pelo GitHub Desktop.
2. Confirmar o HWND atual; identificador antigo pode expirar.
3. Executar `python ler_mesas.py --hwnd NUMERO --continuo --intervalo 1 --botoes --board`.
4. Comparar quando os estados ocorrerem naturalmente: Hero, board vazio/flop/turn/river, botões ativos e pré-seleção. Não assumir que botão visível confirma vez do Hero.
5. Testar uma mudança de tamanho operacional e posição, minimizar/restaurar. Manter seis mesas como expansão posterior, após uma mesa passar.
6. Ctrl+C; guardar o resumo do console. Não há salvamento contínuo de imagens.
7. Somente se ocorrer divergência ainda visível: `python ler_mesas.py --hwnd NUMERO --botoes --board --save`. Anexar PNG e JSON exatos da pasta impressa, não a pasta antiga.

Prioridades da evidência: 8h confundido com 3h, 9/9, board real de turn, mesa sem botões rejeitada. Não é preciso buscar uma mão específica nem jogar para obter prova; capturas previamente disponíveis também servem.

Ensaios prolongados GDI/RAM, identidade entre várias mesas e DPI 125/150% permanecem separados. Linux e cenas transformadas não homologam esses itens.
