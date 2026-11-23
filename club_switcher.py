"""Troca o LOBBY do PPPoker para um clube-alvo, antes de registrar — o passo que
o runner mestre chama entre inscrições de clubes diferentes (ver grade_do_dia.club).

COORDENADOR PURO (como o grind_planner): toda a LÓGICA de decisão é testável sem
Windows. As duas primitivas VIVAS são injetadas:
  read_current_club() -> str | None   lê o clube mostrado AGORA no lobby (None=não deu)
  do_switch(target)   -> qualquer      executa a troca na tela (achar+clicar o seletor)

Invariantes (fail-safe, metodologia do piloto — nunca agir às cegas, nunca mentir
sucesso):
  - Idempotente: se JÁ está no clube-alvo, NÃO clica (NOOP). Evita toque inútil.
  - Se não consegue LER onde está (None), BLOQUEIA (CLUB_DESCONHECIDO) — não assume.
  - Verifica DEPOIS: só reporta sucesso relendo o clube e confirmando == alvo.
  - Gate: troca REAL (dry_run=False) exige bot_control.execution_allowed() (RUNNING).
  - Sem executor ligado (do_switch=None) e troca necessária -> BLOQUEIA (SEM_EXECUTOR):
    marca honesto de que a primitiva viva ainda não foi validada/capturada.

A troca é AÇÃO AO VIVO EM CONTA REAL: default dry_run=True (planeja, não executa);
a execução real passa pelo gate e pela captura real do seletor (pendente).
"""
import re


def normalize_club_name(s):
    """Nome canônico p/ comparar: sem espaços nas pontas, espaços internos colapsados,
    casefold (case/acentos-insensível ao máximo que o Python puro permite). None/''->''."""
    if not isinstance(s, str):
        return ''
    return re.sub(r'\s+', ' ', s).strip().casefold()


def same_club(a, b):
    na, nb = normalize_club_name(a), normalize_club_name(b)
    return bool(na) and na == nb


class ClubSwitcher:
    def __init__(self, *, read_current_club, do_switch=None, max_attempts=2,
                 bot_control=None):
        if not callable(read_current_club):
            raise TypeError('read_current_club deve ser callable() -> str|None')
        self._read = read_current_club
        self._switch = do_switch
        self.max_attempts = max(1, int(max_attempts))
        self._control = bot_control

    def _result(self, **kw):
        base = dict(ok=False, action=None, target=kw.get('target'), from_club=None,
                    attempts=0, verified=False, reason=None)
        base.update(kw)
        return base

    def ensure_club(self, target, *, dry_run=True):
        """Garante que o lobby está no clube `target`. Devolve dict(ok, action,
        from_club, target, attempts, verified, reason). NÃO levanta por falha de
        troca — devolve ok=False com motivo."""
        if not isinstance(target, str) or not target.strip():
            return self._result(target=target, action='ALVO_INVALIDO',
                                 reason='clube-alvo ausente ou vazio')

        current = self._read_safe()
        if current is None:
            return self._result(target=target, action='CLUB_DESCONHECIDO',
                                 reason='não foi possível ler o clube atual do lobby')

        if same_club(current, target):
            return self._result(target=target, from_club=current, action='NOOP_JA_NO_CLUBE',
                                 ok=True, verified=True, reason='já estava no clube-alvo')

        # Troca é necessária.
        if dry_run:
            return self._result(target=target, from_club=current, action='PLANO_TROCAR',
                                 ok=True, verified=False,
                                 reason='DRY-RUN: trocaria de %r para %r (NÃO executado)'
                                        % (current, target))

        if self._switch is None:
            return self._result(target=target, from_club=current, action='SEM_EXECUTOR',
                                 reason='executor de troca (do_switch) não está ligado — '
                                        'primitiva viva pendente de captura/validação')

        if self._control is not None and not self._control.execution_allowed():
            return self._result(target=target, from_club=current, action='GATE_FECHADO',
                                 reason='Henrique não está RUNNING (gate fechado) — não executa')

        # Executa com verificação pós-troca e re-tentativa limitada.
        last = current
        notes = []
        for attempt in range(1, self.max_attempts + 1):
            # Re-checa o gate a cada tentativa: pausa é instantânea e sempre vence.
            if self._control is not None and not self._control.execution_allowed():
                return self._result(target=target, from_club=last, action='GATE_FECHADO',
                                    attempts=attempt - 1,
                                    reason='gate fechou durante a troca (pausa venceu)')
            try:
                self._switch(target)
            except Exception as ex:                      # executor falhou nesta tentativa
                notes.append('tentativa %d: erro no executor: %s' % (attempt, ex))
            cur = self._read_safe()
            last = cur if cur is not None else last
            if cur is not None and same_club(cur, target):
                return self._result(target=target, from_club=current, action='TROCADO',
                                    ok=True, verified=True, attempts=attempt,
                                    reason='trocado e confirmado por releitura')
            notes.append('tentativa %d: releitura=%r (não confirmou)' % (attempt, cur))

        return self._result(target=target, from_club=last, action='TROCA_NAO_CONFIRMADA',
                            attempts=self.max_attempts,
                            reason='; '.join(notes) or 'troca não confirmada')

    def _read_safe(self):
        try:
            v = self._read()
        except Exception:
            return None
        return v if (isinstance(v, str) and v.strip()) else None


def describe(result):
    """Linha humana do resultado (deixa claro quando NÃO executou)."""
    a = result.get('action')
    tgt = result.get('target')
    frm = result.get('from_club')
    if a == 'NOOP_JA_NO_CLUBE':
        return 'CLUBE: já em %r — nada a fazer.' % frm
    if a == 'PLANO_TROCAR':
        return 'CLUBE: [DRY-RUN] trocaria %r -> %r (NÃO enviado).' % (frm, tgt)
    if a == 'TROCADO':
        return 'CLUBE: trocado %r -> %r e confirmado.' % (frm, tgt)
    return 'CLUBE: (sem troca) ação=%s alvo=%r — %s' % (a, tgt, result.get('reason'))
