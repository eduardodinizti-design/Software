# Engine de ranges no laboratório

## Implementado neste ciclo

`visualpilot/agent/laboratory.py` fornece `LaboratoryRangeBook`: importa um JSON
versionado e consulta apenas contextos exatos. Não treina um modelo, não aprende
sozinho e não executa ações. O adaptador de exportação do NBT Track/PokerTrack
depende do código ou esquema real desses sistemas, ainda não disponível aqui.

Fluxo suportado pela interface de estratégia:

imagem → leitura → contexto validado → consulta da política → recomendação
com identidade da observação e versão da política.

Instanciação: `RangeCoachStrategy(connector, laboratory_book=LaboratoryRangeBook(path))`.
A ponte assíncrona existente pode chamar essa estratégia, mas o painel não foi
conectado automaticamente a ranges fictícios. Posição, stack efetivo e histórico
completo ainda não são produzidos com confiabilidade pelo leitor atual.

## Contrato provisório de importação (não é o esquema do tracker)

```json
{
  "schema_version": 1,
  "source": "exemplo-ficticio-de-teste",
  "version": "lab-1",
  "entries": [{
    "state": {
      "street": "flop",
      "hero": ["As", "Ks"],
      "board": ["2h", "3d", "4s"],
      "position": "BTN",
      "effective_stack_bb": 30,
      "pot_bb": 4,
      "action_history": []
    },
    "options": [{"action": "check", "frequency": 1}]
  }]
}
```

Esse exemplo é um dado de teste, não uma recomendação estratégica. Call/bet/raise
exigem `sizing_bb`; as frequências devem somar 1. Board, posição, pote, stack e
histórico precisam corresponder ao registro. Nenhuma aproximação por textura,
interpolação de stacks, equivalência de naipes ou solução GTO está implementada.

O contexto da consulta exige `laboratory=true`, `fictional=true` e
`observation={table, generation, frame_sha256}`. O resultado contém esses dados,
a origem, versão, SHA-256 do arquivo de política e SHA-256 do contexto consultado.
Campos incompletos ou ausência de correspondência devolvem `pending`.

## Correção na consulta remota existente

O endpoint atual consulta somente cartas e posição. Agora ele só é consultado
quando a leitura informa pré-flop e nenhum board: flop/turn/river ou etapa
desconhecida não recebem mais uma resposta de range pré-flop indevidamente.
Cartas duplicadas também são rejeitadas na normalização da mão.

## Ciclo de aprimoramento proposto

1. Guardar observação e gabarito revisado, com imagem e contexto completo.
2. Importar uma versão identificada da política exportada pelo tracker.
3. Reproduzir as mesmas mãos contra a versão atual e a candidata.
4. Medir diferenças de recomendação e cobertura separadas dos erros visuais.
5. Promover uma candidata somente após comparar os resultados revisados.

Esse ciclo evita usar o próprio palpite do OCR como verdade de treinamento.
Não há avaliação de lucratividade implementada nem prova de equivalência à
lógica do tracker: para isso são necessários exportação/esquema e casos de
referência pré-flop e pós-flop do sistema original.
