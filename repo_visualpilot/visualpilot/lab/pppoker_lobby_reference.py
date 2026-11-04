"""Read-only calibration of the three user-provided PPPoker v228 references.

Input fields come from individually annotated crops. This module never authorizes
registration, interprets a currency, or converts screenshot points to OS clicks.
"""
from decimal import Decimal
import math
import re
import unicodedata

from .lobby import buyin_total


def normalized(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', text)
                           if not unicodedata.combining(c)).upper().split())


def read_field(fields, key):
    rows = fields.get(key, [])
    if len(rows) != 1:
        raise ValueError(f'{key}: leitura ausente ou ambígua')
    _, text, confidence = rows[0]
    if (not isinstance(text, str) or not text.strip()
            or not math.isfinite(float(confidence)) or not .95 <= float(confidence) <= 1):
        raise ValueError(f'{key}: confiança insuficiente')
    return text.strip()


def price(text):
    """Accept explicit Buy-in labels; reconcile total against every component."""
    match = re.fullmatch(r'BUY[- ]?IN\s*:\s*([0-9.,+\s]+?)(?:\s*\(([0-9.,+\s]+)\))?',
                         normalized(text))
    if not match:
        raise ValueError('Buy-in ausente, ambíguo ou não numérico')
    total = buyin_total(match[1])
    if match[2] is not None:
        if '+' in match[1] or buyin_total(match[2]) != total:
            raise ValueError('Total do buy-in difere da composição')
    return format(total, '.2f')


def start_time(text):
    match = re.fullmatch(r'HORARIO DE INICIO:\s*((?:0[1-9]|1[0-2])/(?:0[1-9]|[12][0-9]|3[01]))'
                         r'\s*((?:[01][0-9]|2[0-3]):[0-5][0-9])', normalized(text))
    if not match:
        raise ValueError('Horário de início ausente ou ambíguo')
    # Validate month/day without inventing the year; a leap year permits Feb 29.
    from datetime import datetime
    datetime.strptime('2000/'+match[1], '%Y/%m/%d')
    return ' '.join(match.groups())


def name_key(text):
    """OCR may omit spaces; never substitute visually similar letters/digits."""
    return normalized(text).replace(' ', '')


def recognize_reference_field(reader, pixels, key):
    """Compare native field recognition with line detection on the same crop.

    No binarization, lexicon correction, resizing of the source, or maximum-score
    search. Conflicting confident readings remain pending. The evidence records
    both methods, including unreliable alternatives.
    """
    text, score = reader.field(pixels)
    direct = [([], text, float(score))]
    detected = reader.detect(pixels)
    lines = [(box, str(value), float(confidence)) for box, value, confidence in detected]
    if key == 'name' and len(lines) > 1:
        # Only a bounded name crop may join multiple lines; never numeric fields.
        lines.sort(key=lambda row: (min(p[1] for p in row[0]), min(p[0] for p in row[0])))
        lines = [([], ' '.join(row[1] for row in lines), min(row[2] for row in lines))]
    evidence = dict(direct=direct, detected=detected, selected=None, reason=None)

    def confident(rows):
        return (len(rows) == 1 and isinstance(rows[0][1], str) and bool(rows[0][1].strip())
                and math.isfinite(float(rows[0][2])) and .95 <= float(rows[0][2]) <= 1)

    def equivalent(value):
        try:
            if key == 'name':return name_key(value)
            if key == 'buyin':return price(value)
            if key == 'start':return start_time(value)
        except ValueError:
            return ('invalid', normalized(value))
        return normalized(value)

    d, l = confident(direct), confident(lines)
    if d and l and equivalent(direct[0][1]) != equivalent(lines[0][1]):
        evidence['reason'] = 'conflicting_confident_readings'
        return [], evidence
    if l:
        evidence['selected'] = 'detected_lines'
        return lines, evidence
    if d:
        evidence['selected'] = 'direct_field'
        return direct, evidence
    evidence['reason'] = 'missing_ambiguous_or_low_confidence'
    return [], evidence


def lobby_card(fields, *, complete=True, max_buyin='50'):
    limit = buyin_total(max_buyin)
    if not 0 <= limit <= 50:
        raise ValueError('Limite máximo autorizado: 50 por inscrição')
    result = dict(name=None, buyin=None, start=None, registration='unknown',
                  currency='unknown', can_inspect_details=False, can_register=False)
    if not complete:
        return dict(result, reason='partial_card')
    try:
        # Closed is evidence even if other fields are unreadable.
        status = fields.get('status', [])
        if status and normalized(read_field(fields, 'status')) == 'REGISTROS ENCERRADOS':
            result['registration'] = 'closed'
        result['buyin'] = price(read_field(fields, 'buyin'))
        if result['registration'] == 'closed':
            return dict(result, reason='registration_closed')
        if Decimal(result['buyin']) > limit:
            return dict(result, reason='buyin_limit')
        result['name'] = normalized(read_field(fields, 'name'))
        result['start'] = start_time(read_field(fields, 'start'))
        # This permits read-only inspection, not a commitment or an open status.
        return dict(result, can_inspect_details=True, reason='details_required')
    except (ValueError, TypeError) as exc:
        return dict(result, reason=str(exc))


def compare_details(selection, fields):
    result = dict(matches=False, can_register=False, currency='unknown')
    try:
        result['name'] = normalized(read_field(fields, 'name'))
        result['buyin'] = price(read_field(fields, 'buyin'))
        result['start'] = start_time(read_field(fields, 'start'))
        # The reference uses English thousands notation: "20,000".
        stack = re.fullmatch(r'FICHAS INICIAIS:\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)',
                             normalized(read_field(fields, 'stack')))
        if not stack:
            raise ValueError('Stack inicial ilegível')
        result['initial_stack'] = int(stack[1].replace(',', ''))
        result['register_text_visible'] = normalized(read_field(fields, 'register')) == 'REGISTRAR'
        result['matches'] = (selection.get('can_inspect_details') is True
                             and name_key(selection.get('name') or '') == name_key(result['name'])
                             and all(selection.get(k) == result[k] for k in ('buyin', 'start')))
        result['reason'] = 'details_match' if result['matches'] else 'details_mismatch'
    except (ValueError, TypeError) as exc:
        result['reason'] = str(exc)
    return result


def compare_modal(details, fields):
    result = dict(matches=False, can_register=False, adjustable_amount=False)
    try:
        result['buyin'] = price(read_field(fields, 'buyin'))
        result['start'] = start_time(read_field(fields, 'start'))
        result['confirm_text_visible'] = normalized(read_field(fields, 'confirm')) == 'CONFIRMAR'
        result['matches'] = (details.get('matches') is True
                             and all(details.get(k) == result[k] for k in ('buyin', 'start')))
        # The modal lacks a tournament ID/name: matching values alone do not
        # establish continuity from the previously observed details screen.
        result['reason'] = 'matching_values_need_live_continuity' if result['matches'] else 'modal_mismatch'
    except (ValueError, TypeError) as exc:
        result['reason'] = str(exc)
    return result


def checked_rect(rect, size):
    if (len(rect) != 4 or any(type(v) is not int for v in rect)
            or min(rect[:2]) < 0 or min(rect[2:]) <= 0
            or rect[0]+rect[2] > size[0] or rect[1]+rect[3] > size[1]):
        raise ValueError('Região fora da imagem de referência')
    return tuple(rect)


def annotated_crops(rgb, view):
    """Manual reference regions, never automatic segmentation or live tracking."""
    if list(rgb.shape) != [view['size'][1], view['size'][0], 3] or str(rgb.dtype) != 'uint8':
        raise ValueError('Dimensões diferentes da referência; recalibre sem redimensionar')
    result = []
    for item in view['items']:
        x, y, width, height = checked_rect(item['box'], view['size'])
        fields = {}
        for name, rect in item['fields'].items():
            fx, fy, fw, fh = checked_rect(rect, view['size'])
            if fx < x or fy < y or fx+fw > x+width or fy+fh > y+height:
                raise ValueError('Campo fora do cartão anotado')
            fields[name] = rgb[fy:fy+fh, fx:fx+fw].copy()
        result.append(dict(id=item['id'], complete=item['complete'], fields=fields,
                           image_point=[x+width/2, y+height/2]))
    return result
