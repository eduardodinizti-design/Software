"""Executor de ação — arma o clique real com TRAVAS (passo 3).

Default DRY-RUN (DryRunInput): só clica de verdade quando `armed=True` E o
`BotControl` está RUNNING. Garantias:
- Gate `BotControl` (RUNNING); pausa/takeover por hotkey desarma na hora.
- Só FOLD/CALL/CHECK (clique único). RAISE/BET/all-in ficam de fora (precisam do
  fluxo de sizing multi-etapa) → abstém.
- UMA ação por mão (não reaperta a mesma mão).
- Revalidação na chegada + clique único + verificação de efeito ficam no
  `CursorController` (validator/verifier injetados pelo chamador ao vivo).

Este módulo é o núcleo testável; a captura/revalidação ao vivo entram no CLI.
"""
import time

from action_coordinator import plan_from_buttons
from cursor_controller import CursorController, Intent

SINGLE_CLICK_ACTIONS = ('FOLD', 'CALL', 'CHECK')


class ActionExecutor:
    def __init__(self, *, window_rect, bot_control=None, armed=False,
                 arrival_tol=10.0, clock=time.monotonic):
        self.window_rect = window_rect
        self.bot_control = bot_control
        self.armed = bool(armed)
        self.arrival_tol = float(arrival_tol)
        self._clock = clock
        self._done = set()               # hand_ids que já agiram

    def plan(self, result, buttons_result, *, origin, frame_size):
        """Plano de ação com as travas de alçada: só clique único (Fold/Call/Check)."""
        p = plan_from_buttons(buttons_result, result.get('advice') or {},
                              origin=origin, window_rect=self.window_rect,
                              frame_size=frame_size)
        if not p['ok']:
            return p
        action = p['plan']['action']
        if action not in SINGLE_CLICK_ACTIONS:
            return dict(ok=False, plan=None,
                        reason='ACAO_MULTI_ETAPA_NAO_ARMADA:%s' % action)
        return p

    def execute(self, result, buttons_result, *, origin, frame_size, input_adapter,
                validator, verifier=None, hand_id=None):
        """Decide e (se armado + gated) executa UM clique via o CursorController.

        Retorna {acted, state?, reasons?, reason?, plan?, dry_run}. `acted` = o
        clique foi disparado (DONE ou UNKNOWN); CANCELLED = não clicou.
        """
        plan_res = self.plan(result, buttons_result, origin=origin, frame_size=frame_size)
        if not plan_res['ok']:
            return dict(acted=False, reason=plan_res['reason'], dry_run=not self.armed)
        if hand_id is not None and hand_id in self._done:
            return dict(acted=False, reason='JA_AGIU_NESTA_MAO:%s' % hand_id,
                        dry_run=not self.armed)
        if self.armed and self.bot_control is not None \
                and not self.bot_control.execution_allowed():
            return dict(acted=False, reason='BOT_PAUSADO', dry_run=False)

        plan = plan_res['plan']
        intent = Intent(id='act-%s-%s' % (hand_id, plan['action']),
                        action=plan['action'], source_key=str(hand_id),
                        target_rect=plan['screen_rect'],
                        deadline=self._clock() + 5.0,
                        expected=dict(action=plan['action']))
        ctrl = CursorController(
            input_adapter=input_adapter, validator=validator, verifier=verifier,
            bot_control=(self.bot_control if self.armed else None),
            clock=self._clock, arrival_tol=self.arrival_tol)
        out = ctrl.execute(intent)
        clicked = out['state'] != 'CANCELLED'      # chegou a clicar?
        if clicked and hand_id is not None:
            self._done.add(hand_id)
        return dict(acted=clicked, state=out['state'], reasons=out['reasons'],
                    plan=plan, intent_id=intent.id, dry_run=not self.armed)
