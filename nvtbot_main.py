"""DESPACHANTE do .exe standalone (PyInstaller). Um unico executavel que roda
sub-comandos, pra o launcher poder abrir os processos filhos SEM precisar de
python.exe (que nao existe no .exe):
    NVTBot.exe              -> iniciar  (o launcher: sobe operador+captura+emissor)
    NVTBot.exe operar  ...  -> operar_mesa.main
    NVTBot.exe emitir  ...  -> emitir_seats.main
    NVTBot.exe capturar...  -> capturar_maos.main
No FONTE (sem frozen) nao e usado — os .py rodam direto.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in (_HERE, os.path.join(_HERE, 'research', 'ppp_il2cpp')):
    if _d not in sys.path:
        sys.path.insert(0, _d)


def main():
    args = sys.argv[1:]
    sub = args[0] if args else 'painel'   # sem argumento -> PAINEL (central de gestao)
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
    else:                                  # painel (default)
        import painel
        painel.main()


if __name__ == '__main__':
    main()
