"""Parse only visible Hero button text; never infer an illegible amount."""
import re

def parse_button(text, confidence, box):
    if confidence < .90:
        return None
    match=re.fullmatch(r'\s*(fold|check|call|bet|raise)(.*)',text,re.I)
    if not match:return None
    action,tail=match.groups();tail=tail.strip()
    # A word containing an action prefix is not a button.
    if tail and tail[0].isalpha() and not tail.upper().startswith('BB'):return None
    amount=None;unit=None
    value=re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(BB)?',tail,re.I)
    if value:
        amount=float(value[1].replace(',','.'));unit='BB' if value[2] else 'chips'
    return dict(action=action.lower(),amount=amount,unit=unit,raw_text=text,
                confidence=float(confidence),box=box,
                amount_status='read' if value else 'not_shown' if not tail else 'pending')
