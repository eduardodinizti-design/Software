# Armazenamento de diagnóstico

`python ler_mesas.py --hwnd NUMERO` processa em RAM e não salva imagens. Para guardar evidência deliberadamente, acrescente `--save`. O modo de leitura de captura já salva continua exportando resultados para comparação.

Os utilitários ler_mesas e windows_capture_diagnostics compartilham limite padrão de 100 MiB no diretório logs. Arquivos desconhecidos em logs contam no orçamento mas nunca são removidos automaticamente. A rotação apaga conjuntos antigos completos: JSON/PNG de captura ou pasta leitura-* com resultado.json. Não há exclusão por idade sem necessidade de espaço.

Para proteger uma leitura, crie arquivo vazio `.keep` dentro da pasta leitura-*. Para proteger captura, crie capture-NUMERO.keep ao lado do JSON. Evidências protegidas continuam contando no limite; se não houver espaço recuperável, o salvamento falha sem apagar os conjuntos disponíveis. Um pacote maior que o orçamento é recusado antes de exclusões.

O bloqueio de arquivo coordena os dois escritores. Outros componentes que escrevam diretamente no disco não estão submetidos a esse bloqueio: isso não constitui ainda uma cota global de todo o produto, nem controla outros diretórios ou contas. Diretórios de saída personalizados compartilham orçamento apenas se usarem o mesmo pai. Rotação automática reconhece os nomes padrão diagnostics e leitura.

Validação local: 19 testes de armazenamento e integração passaram; não é ensaio prolongado Windows. OCR inalterado nesta correção.
