# Perfis do PPPoker

Ainda não há um perfil real calibrado. Não utilizar o perfil sintético como detector do PPPoker.

Um perfil descreve **um tamanho de mesa, tema e escala de pixels**. Para obter leituras reais precisamos de capturas PNG sem redimensionamento do desktop nos dois monitores, com exemplos de Hero, board em cada etapa, nomes, pote, stack e botões. Cartas com aparência diferente exigem modelos próprios; este primeiro motor suporta uma imagem por carta. DPI, zoom e tema diferentes exigem nova calibração. Ele detecta várias mesas pela mesma âncora visual, nunca pela posição fixa na tela, mas as regiões internas são relativas à mesa.

Estrutura de `pppoker.json` (coordenadas ilustrativas; substituir após medir as capturas):

```json
{
  "version": 1,
  "table_size": [800, 600],
  "anchor_image": "assets/anchor.png",
  "anchor_offset": [20, 20],
  "anchor_threshold": 0.97,
  "regions": {
    "hero_1": [330, 430, 30, 40],
    "hero_2": [365, 430, 30, 40],
    "board_1": [290, 260, 30, 40],
    "board_2": [325, 260, 30, 40],
    "board_3": [360, 260, 30, 40],
    "board_4": [395, 260, 30, 40],
    "board_5": [430, 260, 30, 40],
    "hand_id": [20, 50, 180, 25],
    "pot": [330, 220, 100, 25],
    "stack": [320, 490, 130, 25],
    "table_name": [200, 20, 200, 25],
    "button_1": [100, 540, 180, 40],
    "seat_1_name": [20, 120, 140, 25],
    "seat_1_action": [20, 150, 140, 25]
  },
  "hero_cards": ["hero_1", "hero_2"],
  "board_cards": ["board_1", "board_2", "board_3", "board_4", "board_5"],
  "card_templates": {"As": "assets/As.png", "Kh": "assets/Kh.png"},
  "empty_slot_templates": {
    "board_1": "assets/empty1.png",
    "board_2": "assets/empty2.png",
    "board_3": "assets/empty3.png",
    "board_4": "assets/empty4.png",
    "board_5": "assets/empty5.png"
  },
  "text_fields": {"hand_id": "hand_id", "pot": "pot", "stack": "stack", "table_name": "table_name"},
  "hero_buttons": [{"region": "button_1"}],
  "players": [{"seat": "1", "name_region": "seat_1_name", "action_region": "seat_1_action"}]
}
```

Usar os 52 modelos para cobrir o baralho: valores `23456789TJQKA`, naipes `c` paus, `d` ouros, `h` copas e `s` espadas. O recorte de cada slot deve incluir valor e naipe e ter exatamente o tamanho do modelo. Dois modelos neste exemplo apenas ilustram o formato, não dão cobertura ao baralho. Modelos vazios devem representar o fundo real de cada posição; leitura não reconhecida não significa slot vazio. Não incluir número da mão, pote ou outro conteúdo variável na âncora.

O OCR atual usa texto em inglês: `fold`, `check`, `call`, `bet`, `raise`; os valores preservam o texto observado, sem conversão monetária. Botões e ações de jogadores usam regiões distintas. Um nome ilegível impede a atribuição da ação ao jogador. Não há leitura de popup.

O modo atual rejeita tamanhos diferentes e mesas parcialmente fora da tela. Sobreposição/oclusão pode gerar pendências e perda da detecção. Uma mesa movida ou que desapareceu recebe novo rastreamento para evitar uma associação não comprovada. Não promete manter identidade ao reorganizar janelas. O ID visível da mão fica no registro quando legível; não há reconstrução de mãos.
