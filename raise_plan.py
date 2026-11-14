"""A4 — contrato DISCRETO do menu de aumento (presets como árvore).

Hoje a decisão do tamanho do raise está espalhada: `map_multiplier_to_preset`
(preset dentro da tolerância) + `is_shove_target` (shove via barra) + o branching
inline do RaiseSequencer. Este módulo consolida isso num PLANO único, explícito e
VERIFICÁVEL — uma árvore discreta de opções:

    plan_raise(target, presets, slider_available) -> {kind, ...}
      kind='PRESET'  : clica o preset (carrega expected_mult/label p/ conferir depois)
      kind='SHOVE'   : alvo acima do maior preset + barra disponível -> all-in
      kind='ABSTAIN' : nenhum tamanho SEGURO e conferível -> não clica (com razão)

Princípio (igual ao resto do operador): NUNCA aproxima à força — fora da tolerância
é ABSTAIN, não "clica o mais perto e torce". Reusa a semântica exata de raise_panel
(mesma tolerância, mesmo critério de shove) para não divergir do que já foi validado.

`verify_selected_preset(panel, expected_mult)` fecha o laço: antes de CONFIRMAR, o
sequencer relê o painel e confirma que o preset pretendido ainda está lá (pega painel
trocado / rótulo mis-OCR entre etapas). Só pode BARRAR um confirmar, nunca adiciona
clique. PURO: sem OCR, sem captura, sem clique. Ver [[nvt-adendo-antecipacao-a0]]."""
from raise_panel import map_multiplier_to_preset, is_shove_target


def plan_raise(target_mult, presets, *, slider_available=True, tol=None):
    """Plano discreto do aumento. Explicável (sempre tem `reason` quando abstém) e
    verificável (PRESET carrega `expected_mult`/`label`). Nunca levanta; entradas
    ruins viram ABSTAIN com razão."""
    if target_mult is None:
        return dict(kind='ABSTAIN', reason='SEM_ALVO', target_mult=None)
    usable = [p for p in (presets or []) if isinstance(p, dict) and p.get('mult') is not None]
    if not usable:
        return dict(kind='ABSTAIN', reason='SEM_PRESET_LEGIVEL', target_mult=target_mult)
    preset = map_multiplier_to_preset(target_mult, usable, tol=tol)
    if preset is not None:
        return dict(kind='PRESET', preset=preset, expected_mult=preset['mult'],
                    label=preset.get('label'), target_mult=target_mult)
    # Sem preset na tolerância: distingue SHOVE (acima do maior preset) de alvo
    # intermediário sem preset compatível (abstém — não há tamanho conferível).
    if is_shove_target(target_mult, usable):
        if slider_available:
            return dict(kind='SHOVE', target_mult=target_mult,
                        over=round(target_mult - max(p['mult'] for p in usable), 2))
        return dict(kind='ABSTAIN', reason='SHOVE_SEM_SLIDER', target_mult=target_mult)
    return dict(kind='ABSTAIN', reason='SEM_PRESET_NA_TOLERANCIA', target_mult=target_mult)


def verify_selected_preset(panel, expected_mult, *, tol=0.01):
    """Confere, no painel RELIDO, que o preset esperado ainda está disponível (mesma
    mult, dentro de `tol`). Pega painel que mudou/sumiu ou rótulo relido diferente
    entre a escolha e o confirmar. Retorna (ok: bool, reason: str|None)."""
    if expected_mult is None:
        return False, 'SEM_ALVO_ESPERADO'
    usable = [p for p in ((panel or {}).get('presets') or [])
              if isinstance(p, dict) and p.get('mult') is not None]
    if not usable:
        return False, 'PAINEL_SEM_PRESET'
    if not any(abs(p['mult'] - expected_mult) <= tol for p in usable):
        return False, 'PRESET_ESPERADO_SUMIU'
    return True, None
