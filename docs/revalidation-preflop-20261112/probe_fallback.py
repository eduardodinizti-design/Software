"""Execute only the exact fallback AST block; record advice, never send input."""
import ast
import contextlib
import io
import json
from pathlib import Path
from operar_mesa import _is_premium

src = Path('operar_mesa.py').read_text()
node = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.If)
            and "startswith('SEM_ACAO_RECOMENDADA')" in ast.get_source_segment(src, n.test))

class Recorder:
    def execute(self, result, *args, **kwargs):
        self.seen = result
        return {'acted': False, 'reason': 'RECORDED_NO_INPUT'}

recorder = Recorder()
scope = dict(out={'acted': False, 'reason': 'SEM_ACAO_RECOMENDADA:ABSTAIN'},
             br={'status': 'EXPERIMENTAL_BUTTON_ROW', 'buttons': [
                 {'action': 'FOLD'}, {'action': 'CALL', 'amount': 100, 'unit': 'BB'}]},
             result={'hero_cards': ['As', 'Qd'], 'advice': {
                 'status': 'ABSTAIN', 'reason': 'MULTIWAY_OR_3BET_NOT_COVERED'}},
             executor=recorder, x=0, y=0, fw=100, fh=100, adapter=None,
             validator=None, verifier=None, hid='H1', tkey_local='T1', n=1,
             overlay=None, _is_premium=_is_premium)
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(ast.Module(body=[node], type_ignores=[]),
                 '<operator-fallback-extracted>', 'exec'), scope)
print(json.dumps({'method': 'Exact AST block from operar_mesa.main; passive recorder',
                  'input': scope['result'], 'call_amount': 100,
                  'generated_advice': recorder.seen['advice']}, indent=2))
