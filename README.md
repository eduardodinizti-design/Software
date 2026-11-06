# VisualPilot — observador Windows de console

O caminho operacional unico e `ler_mesas.py` → `window_capture_engine.py` → `table_reading/pipeline.py`. Sem interface grafica, previa de debug ou servidor web. A branch main recebe o mesmo codigo operacional de fix/strict-client-capture nesta consolidacao.

## Executar no Windows

Use Python 3.12 e Tesseract com idioma English. Se o ambiente dos testes anteriores ja funciona, reutilize-o. Para instalar as dependencias Python: `python -m pip install -r requirements.txt`.

Na raiz do checkout completo:

```cmd
python testar_windows.py --listar
python ler_mesas.py --hwnd NUMERO --continuo --botoes --board
```

Substitua NUMERO pelo HWND atual. Ctrl+C encerra. O observador nao clica e nao salva imagens por padrao. `bot_standalone.py` e apenas um alias desse mesmo leitor; sem argumentos, mostra ajuda.

`testar_windows.py --hwnd NUMERO --cliques` e um executor MANUAL separado. Nao faz parte da reproducao do observador e nao decide jogadas.

## Estrutura preservada

- `table_reading/`: detector, leitores e templates.
- Captura, observador, metricas e armazenamento limitado na raiz.
- `test_*.py`, `tools/`, `scripts/`, `public/assets/aistudio/`: laboratorio e testes atuais.
- `docs/` e `repo_visualpilot/docs/`: evidencias e documentos historicos; instrucoes antigas nao substituem este README.
- `coletar_amostras.py` e `windows_capture_diagnostics.py`: coleta explicita e limitada.

Nao copiar arquivos para distribuicoes antigas. Nao recriar GUI, preview, filtros globais ou outro reconhecedor. Use os modulos deste checkout completo. A captura e leitura reais precisam ser verificadas no Windows; resultados de laboratorio nao sao prova de desempenho ao vivo.
