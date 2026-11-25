"""DESPACHANTE do .exe standalone (PyInstaller). Um unico executavel que roda
sub-comandos, pra o launcher poder abrir os processos filhos SEM precisar de
python.exe (que nao existe no .exe). UNIFICADO: PPPoker + Suprema no MESMO .exe.
    NVTBot.exe                  -> auto-detecta a sala aberta e sobe o launcher certo
    NVTBot.exe iniciar      ... -> iniciar_bot.main   (launcher PPPoker)
    NVTBot.exe operar       ... -> operar_mesa.main   (PPPoker)
    NVTBot.exe emitir       ... -> emitir_seats.main  (PPPoker)
    NVTBot.exe capturar     ... -> capturar_maos.main (PPPoker)
    NVTBot.exe alerta       ... -> alerta_ft.main     (PPPoker)
    NVTBot.exe suprema      ... -> iniciar_suprema.main (launcher Suprema/Wizard)
    NVTBot.exe suprema-agente...-> suprema_agente.main  (AGENTE da Suprema, 1 hook)
No FONTE (sem frozen) nao e usado — os .py rodam direto.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in (_HERE, os.path.join(_HERE, 'research', 'ppp_il2cpp')):
    if _d not in sys.path:
        sys.path.insert(0, _d)


def _detecta_e_sobe():
    """Sem subcomando: delega ao LAUNCHER ÚNICO MULTI-PLATAFORMA (iniciar_multi) — ele detecta Suprema
    e/ou PPPoker abertos e sobe AS DUAS (ou a que estiver aberta), com o árbitro de clique coordenando
    o cursor. É o 'clicou-abriu' da era multi-plataforma (Eduardo 24/11)."""
    import iniciar_multi
    iniciar_multi.main()


def main():
    args = sys.argv[1:]
    sub = args[0] if args else ''          # sem argumento -> AUTO-DETECTA a sala aberta
    rest = args[1:]
    # os submodulos usam argparse sobre sys.argv -> deixa so o resto p/ eles
    sys.argv = [sys.argv[0]] + rest
    if sub == 'operar':
        import operar_mesa
        operar_mesa.main(rest or None)
    elif sub == 'emitir':
        import emitir_seats
        emitir_seats.main()
    elif sub == 'capturar':
        import capturar_maos
        capturar_maos.main()
    elif sub == 'alerta':
        import alerta_ft
        alerta_ft.main()
    elif sub == 'iniciar':
        import iniciar_bot
        iniciar_bot.main()
    elif sub == 'suprema':                 # launcher/Wizard da Suprema
        import iniciar_suprema
        iniciar_suprema.main()
    elif sub == 'suprema-agente':          # AGENTE da Suprema (1 hook) — filho do Wizard quando frozen
        import suprema_agente
        suprema_agente.main()
    elif sub == 'multi':                   # LAUNCHER ÚNICO: sobe Suprema + PPPoker juntos (árbitro de clique)
        import iniciar_multi
        iniciar_multi.main()
    elif sub == 'painel':
        import painel
        painel.main()
    else:                                  # sem subcomando -> auto-detecta
        _detecta_e_sobe()


if __name__ == '__main__':
    main()
