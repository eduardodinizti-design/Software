# Laboratório: métricas e recuperação

Sem exigir PPPoker aberto, esta alteração:
- Registra contagens explícitas de tentativas de leitura de cartas e botões no pipeline.
- Exclui etapas não executadas dos percentis de OCR. Ciclos com OCR e sem OCR têm séries separadas. card_reading inclui uma tentativa que falha, pois houve trabalho executado; não é taxa de acerto.
- Exibe contagem limitada aos últimos 120 resultados/falhas, motivos de rejeição e ciclos que chamaram o leitor. Não armazena pixels ou arquivos adicionais.
- Testa 99 ciclos sem OCR e um com OCR: mediana da leitura corresponde ao único ciclo executado, não zero.
- Testa mudança de geometria durante captura e recuperação no quadro seguinte.
- Testa 1.000 falhas de captura simuladas sem chamar OCR, sem fila de frames.

As métricas de duração mantêm os últimos 120 ciclos analisados; os contadores mantêm as últimas 120 ocorrências, incluindo falhas. São janelas distintas, explicitamente rotuladas. Não medem taxa de FPS do renderizador nem provam integridade visual dos frames.

Limites: não houve ensaio novo de Windows/GDI/PPP real. Não foi alterado o reconhecimento de números: o PNG original de 8h confundido com 3h não está disponível como arquivo local executável. As imagens embutidas no chat não são uma reprodução byte a byte. A rejeição do menu 0.635 também permanece pendente de reprodução nos pixels originais. Não foi reduzido limiar nem adicionada aceitação ad hoc para esses casos.

Próxima investigação: reprodução do par 8h/4h com o PNG original e regressão com capturas previamente rotuladas; depois, confirmação de limites da mesa sem botões. Tamanhos extremos não são prioridade até definir o tamanho real das seis mesas.
