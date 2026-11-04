# Calibração com os PNGs de imagens.rar

O arquivo enviado contém três PNGs originais, preservados sem redimensionamento
em `tests/fixtures/lobby_real/`. O [manifesto](../../tests/fixtures/lobby_real/source.json)
registra nomes originais e SHA-256. Não são as mesmas capturas inline anteriores:
o lobby tem cinco cartões completos, incluindo duas mesas OMAHA, e não tem SEXTA.

| Tela | Dimensões originais |
|---|---|
| Lobby | 787 × 1470 |
| Detalhes | 791 × 1497 |
| Modal | 786 × 1479 |

[Mapa visual das regiões](overlay.html) · [Relatório final](recorded-images/comparison.json)

## Resultados verificados

Com recortes manuais do [perfil específico destas capturas](uploaded-reference.json),
o OCR reconheceu os campos necessários para inspecionar o CORUJAO:

- Nome completo, comparado entre lobby e detalhes removendo somente espaços e
  normalizando caixa/acentos; nenhuma troca entre O/0 ou I/1.
- Horário `10/31 22:00`, sem inferir ano/fuso ou abertura da inscrição.
- Buy-in 50 no lobby, `50 (28.34+14.16+7.5)` nos detalhes e
  `28.34+14.16+7.5` no modal. Total conferido: **50,00**, sem duplicar o total.
- Stack inicial **20.000**, separado do custo de inscrição.
- Textos Registrar, Confirmar e Cancelar. Nenhum seletor mais/menos está visível.

O centro do cartão CORUJAO é `(405, 992)` **nessa imagem de lobby**, cujo retângulo
anotado é `(31, 908, 748, 168)`. A origem da janela no desktop e o DPI não são
conhecidos; essas coordenadas não foram usadas para clicar.

FREEZEOUT foi excluído pelo buy-in 200. DIAMANTE e as duas mesas OMAHA não têm
buy-in legível no campo de inscrição. Premiação e blinds nunca preenchem esse
campo. A moeda e a disponibilidade real de inscrição permanecem desconhecidas;
o resultado é candidato à inspeção, não autorização de registro.

## OCR e limitações observadas

A leitura direta por campo confundiu O com 0. O probe também mostrou que a
binarização pode produzir erro com confiança alta: não selecionamos a variante
que simplesmente teve a maior pontuação. Os resultados iniciais, OCR de tela
inteira e [probe](recorded-images/preprocess-probe.json) estão preservados.

O modo `--ocr-mode paired` compara duas rotinas no mesmo recorte original:
reconhecimento de campo e detecção de linhas. Exige confiança mínima 0,95;
leituras confiantes divergentes ficam pendentes. Sem busca por nomes conhecidos,
correção O/0 ou limiar reduzido. Os dois resultados e o método escolhido são
registrados. Somente campos de nome podem unir linhas; números separados não
são concatenados. Data/hora com espaços omitidos pelo OCR é aceita apenas com
os formatos fixos MM/DD e HH:MM, validando mês, dia, hora e minuto.

Quatro campos seguem pendentes: premiação do DIAMANTE e nomes de FREEZEOUT e
das duas mesas OMAHA. Os nomes dessas entradas são rótulos da anotação manual;
não foram declarados como reconhecidos pelo OCR. Os respectivos cartões são
excluídos por custo ou buy-in ausente, independentemente desses nomes.

As regiões foram anotadas manualmente; **não houve validação da segmentação
automática**, de outras resoluções, rolagem ou reposicionamento. A correspondência
de dados entre três imagens não comprova continuidade de navegação, estado do
botão ao vivo ou recibo de inscrição. Não há clique nem integração de atuação
com PPPoker/Windows nesta rodada. Os resultados preservam `can_register=False`.

## Reprodução e testes

```sh
PYTHONPATH=. python tools/check_real_lobby.py --output diagnostics/lobby-real/nova-rodada
PYTHONPATH=. python -m unittest discover -s tests -p '*lobby*.py' -v
```

O utilitário verifica os hashes dos originais, usa o perfil desta remessa, salva
os recortes e relatórios, compara as três telas e declara zero cliques. A pasta
precisa estar vazia. O modo direto do utilitário anterior continua disponível
para reproduzir a primeira tentativa; o perfil inline anterior foi preservado.

**36 testes passaram em 23,903 s**, incluindo três testes de regressão com OCR
sobre estes PNGs originais e cinco novos testes de rejeição de leituras conflitantes.
[Log](recorded-images/tests.log). A suíte global não foi repetida: as mudanças
se restringem ao analisador observacional de referências reais e aos utilitários.
O controlador de registro do laboratório e seus adaptadores não foram alterados.

Próximas validações: segmentar cartões sem regiões pré-anotadas, generalizar a
leitura dos campos pendentes, medir posição/DPI da janela e verificar navegação
e recibo no PC. Este resultado certifica somente as conferências descritas sobre
estas três imagens gravadas, não uma instalação pronta para operar.
