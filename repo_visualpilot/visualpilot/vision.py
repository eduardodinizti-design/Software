from __future__ import annotations

import json
import re
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pytesseract


@dataclass
class Profile:
    path: Path
    data: dict
    anchor: np.ndarray
    cards: dict[str, np.ndarray]
    empty_slots: dict[str, np.ndarray]

    @classmethod
    def load(cls, path: str | Path) -> 'Profile':
        path = Path(path).resolve()
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('version') != 1:
            raise ValueError('Versão de perfil não suportada')
        width, height = data['table_size']
        if width <= 0 or height <= 0:
            raise ValueError('Dimensões de mesa inválidas')
        if not 0.9 <= data.get('anchor_threshold', 0.97) <= 1:
            raise ValueError('anchor_threshold deve estar entre 0.9 e 1')
        for name, rect in data['regions'].items():
            if len(rect) != 4:
                raise ValueError(f'Região inválida: {name}')
            x, y, w, h = rect
            if min(x, y) < 0 or min(w, h) <= 0 or x + w > width or y + h > height:
                raise ValueError(f'Região fora da mesa: {name}')
        if len(data.get('hero_cards', [])) != 2 or len(data.get('board_cards', [])) != 5:
            raise ValueError('Informe duas regiões do Hero e cinco do board')
        references = data['hero_cards'] + data['board_cards']
        references += list(data.get('text_fields', {}).values())
        references += [v['region'] for v in data.get('hero_buttons', [])]
        for seat in data.get('players', []):
            references += [seat['name_region'], seat['action_region']]
        if any(name not in data['regions'] for name in references):
            raise ValueError('Perfil referencia região não declarada')

        def read(relative):
            image = cv2.imread(str(path.parent / relative), cv2.IMREAD_GRAYSCALE)
            if image is None or image.std() < 2:
                raise ValueError(f'Modelo ausente ou sem contraste: {relative}')
            return image

        cards = {}
        for card, filename in data.get('card_templates', {}).items():
            if not re.fullmatch(r'[2-9TJQKA][cdhs]', card):
                raise ValueError(f'Carta inválida: {card}')
            cards[card] = read(filename)
        empty_slots = {name: read(filename) for name, filename in data.get('empty_slot_templates', {}).items()}
        if any(name not in data['regions'] for name in empty_slots):
            raise ValueError('Modelo vazio referencia região inexistente')
        return cls(path, data, read(data['anchor_image']), cards, empty_slots)


def gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def detect_tables(image: np.ndarray, profile: Profile):
    """Âncora com posição fixa relativa à mesa; sem detecção por cor ou palpites."""
    anchor = profile.anchor
    if image.shape[0] < anchor.shape[0] or image.shape[1] < anchor.shape[1]:
        return []
    scores = cv2.matchTemplate(gray(image), anchor, cv2.TM_CCOEFF_NORMED)
    width, height = profile.data['table_size']
    ax, ay = profile.data['anchor_offset']
    boxes = []
    # Busca mais de seis para detectar e sinalizar excesso, sem misturar mesas.
    for _ in range(32):
        _, confidence, _, (x, y) = cv2.minMaxLoc(scores)
        if confidence < profile.data.get('anchor_threshold', 0.97):
            break
        left, top = x - ax, y - ay
        if left >= 0 and top >= 0 and left + width <= image.shape[1] and top + height <= image.shape[0]:
            box = (left, top, width, height)
            if not any(abs(left - b[0]) < width * .7 and abs(top - b[1]) < height * .7 for b in boxes):
                boxes.append(box)
        # Suprime repetições da mesma âncora, não outras mesas adjacentes.
        radius_x, radius_y = max(anchor.shape[1] // 2, 1), max(anchor.shape[0] // 2, 1)
        scores[max(0, y-radius_y):y+radius_y+1, max(0, x-radius_x):x+radius_x+1] = -1
    return sorted(boxes)


def pending(reason='leitura incompleta'):
    return {'status': 'pending', 'value': None, 'reason': reason}


def read_card(image, templates=None, threshold=.98, margin=.04, use_yolo=True):
    """
    Reconhecimento de cartas com arquitetura de Redes Neurais YOLOv8 Nano (~8ms na CPU).
    Resiliente a skins customizadas, cartas em animação/movimento e resoluções arbitrárias.
    Fallback automático para Template Matching tradicional se YOLO desabilitado.
    """
    if use_yolo:
        try:
            from yolo_card_detector import YOLOv8CardDetector
            # Instanciação singleton ou detector rápido
            detector = getattr(read_card, '_yolo_detector', None)
            if detector is None:
                detector = YOLOv8CardDetector()
                setattr(read_card, '_yolo_detector', detector)
            
            res = detector.detect(image)
            if res.status == 'SUCCESS' and len(res.cards) > 0:
                top_card = max(res.cards, key=lambda c: c.confidence)
                if top_card.confidence >= 0.70:
                    return {
                        'status': 'recognized',
                        'value': top_card.class_name,
                        'confidence': top_card.confidence,
                        'engine': 'YOLOv8_Nano',
                        'latency_ms': res.inference_time_ms
                    }
        except Exception:
            pass

    # Fallback: Template Matching Tradicional
    if not templates:
        return pending('modelos de cartas ausentes')
    sample = gray(image)
    matches = []
    for label, template in templates.items():
        # Sem redimensionar: uma escala não calibrada deve ficar pendente.
        if template.shape != sample.shape or sample.std() < 2:
            continue
        score = float(cv2.matchTemplate(sample, template, cv2.TM_CCOEFF_NORMED)[0, 0])
        matches.append((score, label))
    matches.sort(reverse=True)
    if len(matches) < 2:
        return pending('modelos insuficientes ou escala diferente')
    score, label = matches[0]
    if score < threshold or score - matches[1][0] < margin:
        return pending('carta ambígua')
    return {'status': 'recognized', 'value': label, 'confidence': round(score, 4), 'engine': 'Template_Matching'}


def read_text(image, numeric=False):
    sample = gray(image)
    return json.loads(_read_text_cached(sample.tobytes(), sample.shape, numeric))


@lru_cache(maxsize=256)
def _read_text_cached(pixels, shape, numeric):
    result = _read_text_uncached(np.frombuffer(pixels, dtype=np.uint8).reshape(shape), numeric)
    return json.dumps(result)


def _read_text_uncached(image, numeric=False):
    enlarged = cv2.resize(gray(image), None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    try:
        data = pytesseract.image_to_data(enlarged, config='--psm 7', output_type=pytesseract.Output.DICT, timeout=2)
    except RuntimeError:
        return pending('OCR excedeu o tempo disponível')
    words = [(t.strip(), float(c)) for t, c in zip(data['text'], data['conf']) if t.strip()]
    if not words or min(c for _, c in words) < 85:
        return pending('OCR sem confiança suficiente')
    value = ' '.join(t for t, _ in words)
    if numeric and not re.fullmatch(r'[$€R\s]*\d[\d.,]*(?:\s*(?:BB|bb))?', value):
        return pending('valor ilegível')
    return {'status': 'recognized', 'value': value, 'confidence': min(c for _, c in words) / 100}


ACTIONS = re.compile(r'^(fold|check|call|bet|raise)(?:\s+([$€R\s]*\d[\d.,]*(?:\s*(?:BB|bb))?))?$', re.I)


def read_action(image):
    result = read_text(image)
    if result['status'] != 'recognized':
        return result
    match = ACTIONS.fullmatch(result['value'])
    if not match:
        return pending('ação não reconhecida')
    return {**result, 'value': {'action': match[1].lower(), 'amount': match[2]}}


def infer_stage(board, explicit):
    values = [c['value'] for c in board]
    # Slots vazios precisam de modelo visual próprio; uma leitura falha não prova ausência.
    count = sum(c['status'] == 'recognized' and c['value'] is not None for c in board)
    if all(c['status'] in ('recognized', 'empty') for c in board):
        expected_order = [c['status'] == 'recognized' for c in board]
        if expected_order == [True] * count + [False] * (5 - count):
            stage = {0: 'preflop', 3: 'flop', 4: 'turn', 5: 'river'}.get(count)
            if stage:
                return {'status': 'recognized', 'value': stage, 'source': 'verified_cards_and_empty_slots'}
    if explicit.get('status') == 'recognized':
        stage = explicit['value'].lower().replace('-', '').replace(' ', '')
        expected = {'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}
        if stage in expected and sum(v is not None for v in values) == expected[stage]:
            return {'status': 'recognized', 'value': stage, 'source': 'stage_label_and_board'}
    if all(values) and len(set(values)) == 5:
        return {'status': 'recognized', 'value': 'river', 'source': 'five_board_cards'}
    return pending('etapa sem evidência suficiente')


def observe(table, profile):
    d = profile.data

    def crop(name):
        x, y, w, h = d['regions'][name]
        return table[y:y+h, x:x+w]

    def card_slot(name):
        templates = dict(profile.cards)
        if name in profile.empty_slots:
            templates['empty'] = profile.empty_slots[name]
        result = read_card(crop(name), templates)
        if result['value'] == 'empty':
            result.update(status='empty', value=None)
        return result

    hero = [card_slot(name) for name in d['hero_cards']]
    # Ausência de cartas do Hero é exibida como pendente, sem inferir cartas.
    for card in hero:
        if card['status'] == 'empty':
            card.update(pending('Hero sem cartas visíveis'))
    board = [card_slot(name) for name in d['board_cards']]
    all_cards = hero + board
    values = [c['value'] for c in all_cards if c['value']]
    if len(values) != len(set(values)):
        for card in all_cards:
            if card['value'] and values.count(card['value']) > 1:
                card.update(pending('carta duplicada: leitura inconsistente'))
    text = {key: read_text(crop(region), key in ('pot', 'stack')) for key, region in d.get('text_fields', {}).items()}
    buttons = []
    for button in d.get('hero_buttons', []):
        value = read_action(crop(button['region']))
        buttons.append({'region': button['region'], **value})
    players = []
    for player in d.get('players', []):
        name = read_text(crop(player['name_region']))
        action = read_action(crop(player['action_region']))
        # Sem nome legível não atribuir uma ação a uma identidade inventada.
        players.append({'seat': player['seat'], 'name': name, 'action': action,
                        'association': 'recognized' if name['value'] and action['value'] else 'pending'})
    return {'hero_cards': hero, 'board': board, 'stage': infer_stage(board, text.get('stage', pending())),
            'context': {key: text.get(key, pending('região não configurada')) for key in ('hand_id', 'pot', 'stack', 'table_name')},
            'hero_buttons': buttons, 'players': players}
