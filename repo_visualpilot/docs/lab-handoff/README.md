# Automático, pausa e controle manual

Implementado no HTML portátil e no servidor local com OCR:

1. **Iniciar simulação**: avança automaticamente.
2. **Pausar**: suspende o avanço, invalida a captura/decisão pendente e bloqueia ações.
3. **Assumir controle**: carrega nova observação e libera os botões reconhecidos.
4. Escolha manualmente Fold/Call/Raise/Check/Bet disponíveis, sem depender da
   recomendação automática. Valor não reconhecido não vira sizing inventado.
5. **Retomar automático**: faz nova leitura; se você já agiu, começa o próximo
   cenário. Uma decisão anterior não é reaproveitada.

Cada ação registra ator (`human` ou `engine`), horário, revisão do controle e
referência à imagem. Uma ação já confirmada antes da pausa não é desfeita.

O servidor não mantém o lock de controle durante o OCR. A troca de modo invalida
o resultado de uma captura em andamento. Token, revisão, ator e cenário resolvido
são verificados no backend; a proteção não depende apenas de desabilitar botões.

O replay não executa OCR novo: ao retomar, recarrega a evidência gravada. A ação
manual é uma interação nova no simulador e fica identificada como humana.

**Limite:** são situações independentes de um roteiro, não uma árvore completa
de poker. Sua ação manual encerra aquele cenário; não recalcula as apostas,
adversários ou estratégia das etapas seguintes. O fold não continua a mesma mão:
a retomada abre a próxima situação de teste. A política ainda é demonstrativa.

Testes: cancelamento durante OCR, troca de ator, decisão antiga, duplo clique,
botão indisponível, retomada com nova captura, manual com Hero oculto e registro.
No Chromium, em replay e ao vivo: pausei antes do Call, escolhi Raise manualmente
e retomei; o motor executou Check/Bet/Raise/Fold nas situações seguintes.
Sem erros JavaScript e sem overflow horizontal em largura 390.

Evidências: `targeted.log`, `browser.json`, `full-suite.log` e screenshots.

Suíte unificada após incluir a base pré-flop NVT: **183 testes executados em
100,100 s, sem falhas, três skips**. A conferência exaustiva do pacote NVT está
separada em `../nvt-ranges-review/parity.json`; não infla essa contagem.
