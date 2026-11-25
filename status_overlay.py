"""Faixa de status SEMPRE-NO-TOPO do agente (feedback visível do estado).

Resolve a reclamação: sem isto, armar/pausar é "às cegas" — não há informação na
tela. Mostra, por cima de tudo, o ESTADO (ARMADO=verde / PAUSADO=amarelo /
OFF=vermelho) e a ÚLTIMA AÇÃO/leitura por mesa.

Roda o loop do Tk numa THREAD própria (daemon) com uma fila thread-safe, então o
operador (loop na main thread) só chama `set_state()` / `set_table()` — nunca toca
no Tk direto. Falha de GUI nunca derruba o operador (tudo em try/except).

Uso:
    ov = StatusOverlay(); ov.start()
    ov.set_state('RUNNING')                      # verde ARMADO
    ov.set_table('MINI FREEZE', 'AgTs SB -> FOLD')
    ...
    ov.stop()
"""
import queue
import threading

_COLORS = {
    'RUNNING':  ('#12351f', '#39d353', 'ARMADO'),
    'PAUSED':   ('#3a3410', '#ffd43b', 'PAUSADO'),
    'DISABLED': ('#3a1414', '#ff6b6b', 'DESABILITADO'),
}


class StatusOverlay:
    def __init__(self, *, title='NVT Agente', width=520, height=150):
        self._q = queue.Queue()
        self._thread = None
        self._w, self._h = width, height
        self._title = title
        self._state = 'PAUSED'
        self._tables = {}          # nome -> texto da última ação/leitura

    # ---- API pública (thread-safe) --------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def set_state(self, state):
        self._q.put(('state', state))

    def set_table(self, name, text):
        self._q.put(('table', (name, text)))

    def note(self, text):
        self._q.put(('note', text))

    def stop(self):
        self._q.put(('quit', None))

    # ---- interno (thread do Tk) -----------------------------------------
    def _run(self):
        try:
            import tkinter as tk
        except Exception:
            return                 # sem Tk: silencioso, não derruba o operador
        self._tk = tk
        root = tk.Tk()
        root.title(self._title)
        root.overrideredirect(True)                 # sem barra de título
        try:
            root.attributes('-topmost', True)
            root.attributes('-alpha', 0.92)
        except Exception:
            pass
        sw = root.winfo_screenwidth()
        root.geometry('%dx%d+%d+%d' % (self._w, self._h, (sw - self._w) // 2, 8))
        self._root = root

        self._state_lbl = tk.Label(root, text='', font=('Segoe UI', 22, 'bold'),
                                   anchor='center')
        self._state_lbl.pack(fill='x', ipady=6)
        self._keys_lbl = tk.Label(root, text='Ctrl+Alt+R arma   Ctrl+Alt+P pausa   Ctrl+Alt+D off',
                                  font=('Segoe UI', 9), fg='#aaaaaa', bg='#111111')
        self._keys_lbl.pack(fill='x')
        self._tables_lbl = tk.Label(root, text='', font=('Consolas', 11), justify='left',
                                    anchor='w', fg='#dddddd', bg='#111111')
        self._tables_lbl.pack(fill='both', expand=True, padx=8)
        self._note_lbl = tk.Label(root, text='', font=('Segoe UI', 9), fg='#8ab4f8', bg='#111111')
        self._note_lbl.pack(fill='x')

        # arrastar a faixa com o mouse (caso cubra algo)
        def _drag_start(e): root._dx, root._dy = e.x, e.y
        def _drag(e): root.geometry('+%d+%d' % (root.winfo_pointerx() - root._dx,
                                                root.winfo_pointery() - root._dy))
        for wdg in (root, self._state_lbl, self._keys_lbl):
            wdg.bind('<Button-1>', _drag_start); wdg.bind('<B1-Motion>', _drag)

        self._render()
        root.after(120, self._pump)
        try:
            root.mainloop()
        except Exception:
            pass

    def _pump(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == 'quit':
                    try: self._root.destroy()
                    except Exception: pass
                    return
                if kind == 'state':
                    self._state = payload
                elif kind == 'table':
                    name, text = payload
                    self._tables[name] = text
                elif kind == 'note':
                    self._note = payload
                    self._note_lbl.config(text=payload)
            self._render()
        except queue.Empty:
            self._render()
        except Exception:
            pass
        try:
            self._root.after(120, self._pump)
        except Exception:
            pass

    def _render(self):
        bg, fg, label = _COLORS.get(self._state, _COLORS['PAUSED'])
        try:
            self._root.config(bg=bg)
            self._state_lbl.config(text='● %s' % label, bg=bg, fg=fg)
            self._keys_lbl.config(bg=bg)
            lines = '\n'.join('%-16s %s' % (k[:16], v) for k, v in self._tables.items())
            self._tables_lbl.config(text=lines or '(aguardando leitura das mesas…)', bg=bg)
            self._note_lbl.config(bg=bg)
        except Exception:
            pass


if __name__ == '__main__':
    import time
    ov = StatusOverlay().start()
    seq = [('PAUSED', 'MINI FREEZE', 'AsTs SB -> ABSTAIN'),
           ('RUNNING', 'MINI FREEZE', 'AsKs BTN -> RAISE 2.2x'),
           ('RUNNING', 'REENTRY', '7h7d CO -> CALL'),
           ('PAUSED', 'REENTRY', '(você assumiu)')]
    for st, tb, tx in seq:
        ov.set_state(st); ov.set_table(tb, tx); time.sleep(1.5)
    time.sleep(2); ov.stop(); time.sleep(0.5)
