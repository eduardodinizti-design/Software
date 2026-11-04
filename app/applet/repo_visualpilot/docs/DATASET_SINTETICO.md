# Baralho sintético de regressão

O gerador em `visualpilot/pppoker/dataset_generator.py` cria 36 combinações ausentes em `tests/fixtures/synthetic_deck`. Cada arquivo preserva a captura real de 835 × 1485 como fundo e insere uma carta na região calibrada do turn, com sombra, suavização, valor e naipe.

Os glifos de 11 valores são extraídos das caixas aceitas nas evidências reais. Os valores 6 e 9 não aparecem em nenhum arquivo recebido e usam `cv2.FONT_HERSHEY_DUPLEX`; o manifesto marca esses oito casos como `synthetic_font`. Os quatro naipes usam os moldes de forma e as cores RGB do leitor PPPoker.

O conjunto é destinado a regressão de segmentação, combinação valor/naipe e protocolo regional. Ele não demonstra acerto sobre cartas reais que ainda não foram capturadas. Essa comprovação depende de exemplos reais das 52 combinações no Windows e no PPPoker usados no ensaio final.

Para regenerar os arquivos:

```bash
.venv/bin/python -m visualpilot.pppoker.dataset_generator
```

A suíte cria um teste independente para cada uma das 36 cartas e exige leitura correta com confiança mínima de 0,75. O caminho real mantém o limite padrão de 0,90.
