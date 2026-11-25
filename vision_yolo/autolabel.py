"""AUTO-ROTULAGEM (F1): transforma (VALORES da mesa + LAYOUT de caixas) -> labels YOLO.

A ideia (nvt-visao-yolo-decisao): não rotular à mão. Um PERCEPTOR-PROFESSOR (Frida/rede, ou
OCR) diz O QUE está na mesa (cartas do herói, board, ações legais). O LAYOUT (fixo por
cliente) diz ONDE cada coisa aparece (caixa em fração do frame). Cruzando os dois, saem os
rótulos YOLO (class_id cx cy w h) automaticamente, p/ cada screenshot.

`layout` = {
  'hero_card_slots': [ (cx,cy,w,h), (cx,cy,w,h) ],      # 2 slots do herói
  'board_slots':     [ (cx,cy,w,h) ] * 5,               # até 5 slots do board
  'buttons':         { 'fold': (cx,cy,w,h), 'call': ..., 'raise': ... },
}
`values` = saída de um perceptor (ex. suprema_state.to_table_state / protobuf_state):
  {'hero_cards': ['As','Kd'], 'board': ['9c','6d','2h'], 'legal_actions': ['fold','call','raise']}

READ-ONLY: só gera texto; não toca em tela/jogo.
"""
from __future__ import annotations

from vision_yolo.classes import NAME_TO_ID

# ação do cérebro -> classe de botão do detector
ACTION_TO_BUTTON = {
    'fold': 'btn_fold', 'check': 'btn_check', 'call': 'btn_call',
    'raise': 'btn_raise', 'bet': 'btn_raise', 'all_in': 'btn_allin',
}


def to_yolo_labels(values, layout):
    """Lista de (class_id, cx, cy, w, h) (frações 0..1) p/ o frame. Só emite o que tem VALOR
    E slot no layout — nunca inventa caixa sem valor nem valor sem caixa."""
    labels = []
    for card, box in zip(values.get('hero_cards') or [], layout.get('hero_card_slots') or []):
        cid = NAME_TO_ID.get(card)
        if cid is not None:
            labels.append((cid, *box))
    for card, box in zip(values.get('board') or [], layout.get('board_slots') or []):
        cid = NAME_TO_ID.get(card)
        if cid is not None:
            labels.append((cid, *box))
    buttons = layout.get('buttons') or {}
    for act in values.get('legal_actions') or []:
        cls = ACTION_TO_BUTTON.get(act)
        box = buttons.get(act)
        if cls and box and cls in NAME_TO_ID:
            labels.append((NAME_TO_ID[cls], *box))
    return labels


def format_yolo(labels):
    """Labels -> texto no formato ultralytics (uma linha por objeto)."""
    return '\n'.join('%d %.6f %.6f %.6f %.6f' % (c, cx, cy, w, h)
                     for (c, cx, cy, w, h) in labels)


def write_example(stem, image_bytes_or_path, values, layout, images_dir, labels_dir):
    """Grava um par (imagem .png em images_dir, rótulo .txt em labels_dir) com o MESMO stem.
    `image_bytes_or_path` = caminho de PNG já salvo OU bytes. Devolve (img_path, lbl_path)."""
    import os
    import shutil
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)
    img_path = os.path.join(images_dir, stem + '.png')
    if isinstance(image_bytes_or_path, (bytes, bytearray)):
        with open(img_path, 'wb') as fh:
            fh.write(image_bytes_or_path)
    elif os.path.abspath(image_bytes_or_path) != os.path.abspath(img_path):
        shutil.copyfile(image_bytes_or_path, img_path)
    lbl_path = os.path.join(labels_dir, stem + '.txt')
    with open(lbl_path, 'w', encoding='utf-8') as fh:
        fh.write(format_yolo(to_yolo_labels(values, layout)))
    return img_path, lbl_path
