# vision_yolo — percepção por VISÃO (YOLO)

Decisão estratégica 20/11 (memória `nvt-visao-yolo-decisao`): a percepção **padrão**
do bot passa a ser **visão (YOLO)** em vez de injeção Frida. Motivo: o Frida é a
fonte da fragilidade — crasha o PPPoker (IL2CPP invasivo, fail-fast `0xc0000409`),
travou a Suprema, e precisa de RE por site. Visão lê a tela **de fora**: não injeta,
não crasha, e **um só modelo serve todos os sites** (PPPoker/Suprema/X-Poker).

**O cérebro não muda.** YOLO é só mais um adaptador de percepção que alimenta o
MESMO `table_state` que `protobuf_state`/`suprema_state` já entregam. Troca-se a
fonte, não a estratégia.

## Pipeline
```
screenshot ──▶ YOLO (detecção) ──▶ [Detection,...] ──▶ vision_state ──▶ table_state ──▶ cérebro
                                         │
                                clustering espacial (N mesas tiladas → N clusters)
```

## Arquivos (F0 — pronto)
- `classes.py` — **fonte única** das 64 classes: 52 cartas (`'As'`,`'Td'`… no formato do
  `ppp_cards`) + objetos (`card_back`, botões `btn_*`, `dealer_button`, `hero_indicator`,
  `chip_stack`, `bet_chips`, `pot`). O índice = id do YOLO; não reordenar (teste trava).
- `vision_state.py` — adaptador detecções→`table_state`:
  - `Detection` (caixa+classe+conf);
  - `cluster_by_region` / `cluster_by_proximity` — **multi-mesa** (resolve o
    cruzamento que o protobuf tinha, `nvt-multitable-tiled-bug`);
  - `split_hero_board` — hero = cartas face-up embaixo-centro (regra VisualPilot);
  - `available_actions`, `street_from_board`;
  - `build_table_state` — monta o contrato; **posições** (`resolve_positions`) e
    **números** stack/pote/aposta (`read_number` = OCR no recorte) são INJETADOS
    (F3/F4). Sem resolver → marca `ready=False`/`missing`, **não chuta**.
  - `read_window` — lê a janela inteira (N mesas) de uma vez.
- `make_dataset_yaml.py` → `dataset.yaml` (ultralytics; regenere ao mexer nas classes).
- Testes: `../test_vision_yolo.py` (15, offline).

## Contrato `table_state` (idêntico ao `protobuf_state`)
`{positions:{seat_key→pos,'hero'→pos}, seats:{seat_key→{stack_bb,occupied,source}},
bets:[{seat,bet_bb}], phase, source:'vision', scope, board:['As'...], street,
to_call:{to_call_bb}, pot:{pot_bb}, actions:[...]}`

## Próximas fases
- **F1 — dataset por AUTO-ROTULAGEM (o acelerador):** rodar Frida/rede +
  screenshot **sincronizados**. A verdade do Frida (cartas/board/stacks/posições
  exatos) AUTO-ROTULA cada screenshot — o `protobuf_state`/`suprema_state` vira o
  "professor" do YOLO. Derruba o custo de "dias rotulando à mão" para "algumas
  sessões de captura". + cartas sintéticas p/ cobrir as 52. Semente: ~40 capturas
  Suprema + ~9 PPPoker reais; captura DPI-aware pronta (`research/suprema_cocos/
  capturar_na_vez.py`, `one_shot_grab.py`).
- **F2 — treino:** `yolo detect train data=vision_yolo/dataset.yaml model=yolov8s.pt
  imgsz=1280 epochs=...` (cartas+botões primeiro).
- **F3 — `vision_state` ao vivo:** plugar o modelo + OCR nas regiões recortadas
  (`chip_stack`/`bet_chips`/`pot`) p/ os números; `resolve_positions` pelo
  `dealer_button` + ordem dos assentos.
- **F4 — validação lado-a-lado** com OCR/Frida (concordância), multi-mesa por
  clustering, e plug no operador como fonte de percepção padrão.

Nada aqui injeta no jogo nem clica — percepção pura, crash-free.
