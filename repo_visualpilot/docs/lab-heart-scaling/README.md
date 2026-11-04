# Copas após redimensionamento — 29/10/2026

## Causa e correção

A máscara antiga `assets/suit_h.png` tem fragmentos desconectados. A normalização
selecionava o maior fragmento, que não representava o coração inteiro. O Hero Th
do frame `left_99.png`, aumentado a 150% e normalizado para largura 755, obtinha
similaridade 0,6424, abaixo do mínimo 0,68.

Adicionada `assets/suit_h_clean.png`, extraída do coração grande do **7h do board**
de `tests/fixtures/actions/left_99.png`, sem usar o recorte do Th que falhava.
É outra carta do mesmo frame, não uma captura independente nem validação física.
Proveniência reproduzível: RGB `[645:711,205:269]`; máscara
`r>130 & r>1.5*g & r>1.5*b`; maior componente conexo e boundingRect.

A referência antiga permanece para compatibilidade com dados sintéticos
existentes. A nova só participa da classificação se atingir **0,85** de
similaridade. O limiar anterior e a margem entre candidatos não foram reduzidos.
Similaridade do Hero com a referência limpa: 0,9104 (100%), 0,9422 (125%) e
0,9148 (150%). Similaridade geométrica não é probabilidade de acerto.

## Verificação

- Duas mãos reais (Th/4d e 5c/2s), nas escalas 100%, 110%, 125%, 150%, 175% e 200%:
  12 combinações lidas corretamente com o leitor de produção.
- Retângulo, círculo, linha, ruído vermelho e imagem vazia continuam pendentes.
- O teste integrado TCP/OCR/diário agora exige Th/4d em 150%; não aceita mais
  uma lista vazia como resultado esperado nesse cenário.
- Suíte completa: 161 testes executados em 40,823 s, sem falhas, 3 skips.
  Evidência em `full-suite.log`.
- Nos sete cenários integrados, cartas parciais em 0,253–0,563 s e resultado
  consolidado em 1,289–2,178 s. Medições locais de uma execução, não promessa
  de latência de Wi-Fi ou Windows físico.

Os aumentos foram produzidos por interpolação de imagens gravadas. Não equivalem
a capturar novos pixels no Windows em diferentes configurações de DPI. Ainda
faltam homologação do executável físico e imagens reais adicionais; este ciclo
não comprova todas as 52 cartas em todas as posições, temas ou resoluções.
