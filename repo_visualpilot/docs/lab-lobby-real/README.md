# Referências reais do lobby PPPoker v228

**Atualização:** os PNGs de `imagens.rar` foram recebidos e testados. A leitura
offline do CORUJAO foi conferida entre as três telas; quatro outros campos ainda
ficaram pendentes. Veja [calibração dos originais, testes e limites](REAL_IMAGES.md).
O texto abaixo registra a etapa anterior, baseada nas imagens inline.

Fonte: três imagens exibidas pelo usuário nesta conversa, na ordem lobby,
detalhes do CORUJAO e modal Registrar. As imagens inline puderam ser examinadas
visualmente, mas seus bytes PNG não estão disponíveis no workspace. O conector
marcado na mensagem não disponibilizou ferramenta para recuperá-los.

**Estado: mapeamento manual preliminar; OCR das imagens reais, segmentação
automática e clique no Windows ainda não homologados.** Nenhum clique foi executado.
As coordenadas abaixo pertencem às imagens, não ao desktop do PC. As três imagens
têm dimensões distintas; não se presume que compartilham origem ou escala.

## Leitura visual

| Cartão | Evidência | Resultado para limite 50 |
|---|---|---|
| TORNEIO DIAMANTE | Premiação 10,000; início 10/31 16:00; buy-in não visível | Pendente, não usar premiação como custo |
| FREEZEOUT 30K GTD | Buy-in 200; início 10/31 18:00 | Fora do limite |
| CORUJAO HYPER PKO10K | Buy-in 50; início 10/31 22:00 | Candidato à inspeção dos detalhes |
| SEXTA S. NIGHT 30K | Buy-in 75; Registros encerrados | Fora do limite e encerrado |
| OMAHA - 6 | Blinds 1/2, PLO6; cartão cortado no rodapé | Não tratar como inscrição em torneio |

O lobby não prova inscrição aberta para CORUJAO nem identifica a moeda como
fictícia. Abrir detalhes é uma navegação de inspeção, distinta de registrar.
O número 75 no cabeçalho não é usado como limite autorizado ou custo do torneio.

Detalhes: `Buy-in: 50 (28.34+14.16+7.5)`, stack inicial `20,000`, nome e início
coincidem com o cartão. A soma é exatamente 50,00. Não somar novamente o total
50 aos componentes, nem interpretar 20,000 fichas iniciais como custo.

Modal: `Buy-in: 28.34+14.16+7.5`, mesmo início, botões Confirmar/Cancelar.
**Não existe seletor mais/menos visível.** O fluxo de ajustar custo do simulador
anterior não se aplica a este modal. Seu aviso informa que não se pode cancelar
o registro a menos de 75 segundos do início. O desaparecimento do modal não
constitui recibo de inscrição confirmada.

O modal não mostra um identificador próprio do torneio. Valores iguais precisam
ser associados à navegação observada ao vivo; três imagens isoladas não provam
essa continuidade. Datas não têm ano nem fuso, portanto não inferimos se o evento
está futuro/passado ou se inscrições estão abertas pelo horário.

## Mapeamento

[reference.json](reference.json) contém retângulos manuais por campo, em pixels
locais de cada imagem: lobby 623×1115, detalhes 617×1141, modal 600×1141.
Os IDs `corujao`, `details` etc. são rótulos locais de anotação, não IDs do servidor.

No lobby, o retângulo aproximado do CORUJAO é `(25, 708, 580, 130)`;
centro `(315, 773)`. É apenas um ponto para conferir a anotação na imagem.
Não é enviado a mouse ou teclado, não vale após rolagem/movimento e não autoriza
clique no desktop. A região da lista começa aproximadamente em `(25, 427)`.

O analisador rejeita imagens com dimensões diferentes, campos fora dos cartões
e cartões parciais. Não redimensiona para fazer uma captura diferente parecer
calibrada. Ainda são necessários testes de origem da janela, DPI, outros tamanhos,
rolagem, oclusão e mudanças do conteúdo.

## Código e execução

- `visualpilot/lab/pppoker_lobby_reference.py`: leitura conservadora de campos,
  custo composto, comparação lobby/detalhes/modal e recortes manuais.
- `tools/inspect_pppoker_lobby.py`: recebe PNG original, salva recortes e usa
  RapidOCR nos campos. Não usa o parser com rótulos fictícios do simulador.
- `tests/test_pppoker_lobby_reference.py`: transcrições manuais identificadas
  como tal; não são resultados de OCR das imagens do usuário.

```sh
PYTHONPATH=. python tools/inspect_pppoker_lobby.py lobby.png --view lobby --output diagnostics/real-lobby/lobby
PYTHONPATH=. python tools/inspect_pppoker_lobby.py detalhes.png --view details --output diagnostics/real-lobby/details
PYTHONPATH=. python tools/inspect_pppoker_lobby.py modal.png --view modal --output diagnostics/real-lobby/modal
PYTHONPATH=. python -m unittest discover -s tests -p '*lobby*.py' -v
```

Cada saída exige pasta vazia. O relatório preserva texto/confiança por campo e
retorna candidatos à inspeção apenas para lobby. Detalhes/modal são exportados
sem inventar uma observação anterior; as funções de comparação recebem essa
observação explicitamente. Todos os resultados permanecem `can_register=False`.

## Validação desta rodada

23 testes de lobby passaram, incluindo nove novos. Cobertura: soma integral,
total divergente, custo acima de 50, texto ausente/duplicado ou pouco confiável,
distinção entre premiação/blinds/stack/buy-in, datas inválidas, comparação de nome,
horário e custo, cartões parciais e rejeição de escala diferente. Nenhum módulo
de captura, transporte, OCR de mesas ou atuação existente foi alterado.

O [ensaio do utilitário](cli-smoke.json) executou OCR real sobre texto **sintético**
em dois tamanhos de fonte (16 e 20). Reconheceu o custo, mas
a confiança do nome ficou abaixo de 0,95 nos dois casos; ambos foram bloqueados.
Não se declara leitura positiva do nome nem acurácia das imagens reais. O teste
também confirmou rejeição de dimensões diferentes e zero cliques. O primeiro
ensaio esperava seleção positiva e falhou por essa confiança insuficiente; o
limiar foi preservado e a limitação ficou registrada.

Falta executar OCR sobre os PNGs originais e confrontar suas saídas com estas
anotações, ajustar regiões conforme resultado, conectar a seleção à navegação
verificada e homologar clique/retorno dos detalhes no PC. A referência manual
não altera o resultado da homologação física nem resolve os bugs multimesa.
