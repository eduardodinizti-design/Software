# VisualPilot: leitor Windows de console

Use a branch **fix/strict-client-capture**. A main antiga nao contem o mesmo leitor.

O caminho oficial e `ler_mesas.py` -> `WindowCaptureEngine` -> `table_reading.pipeline.analyze_tables`.
As quatro entradas `bot_standalone.py` agora apenas encaminham argumentos a esse leitor. Nao abrem interface, previa ou debug e nao executam detector alternativo.

## Executar

Na raiz do checkout, com o Python e Tesseract usados nos testes anteriores:

```cmd
python testar_windows.py --listar
python ler_mesas.py --hwnd NUMERO --continuo --botoes --board
```

Substitua NUMERO pelo HWND atual listado. Ctrl+C encerra. O observador trabalha em memoria e nao grava imagens por padrao. Nao executa cliques.

`python bot_standalone.py --hwnd NUMERO --continuo --botoes --board` usa exatamente a mesma entrada. Sem argumentos, mostra ajuda; nao escolhe uma captura antiga automaticamente.

## Orientacao para agentes


Os arquivos do motor e do reconhecimento nao foram alterados nesta limpeza. O executor manual `testar_windows.py --cliques` e separado e nao faz parte do observador validado. Arquivos historicos nao referenciados pelo caminho oficial nao devem ser executados como alternativa.

A limpeza retira as implementacoes GUI das quatro entradas antigas; nao afirma que todo arquivo historico do repositorio seja defeituoso. O funcionamento no PPPoker depende da verificacao no Windows. Testes de laboratorio nao substituem essa verificacao.
