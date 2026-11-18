"""PAINEL DE GESTAO do NVT Bot (Tkinter, estilo NVT Mesas). 3 abas:
  - Grade do Dia: define quais torneios jogar e quando (grava grade_do_dia.json).
  - Desempenho: metricas reais de logs/metrics/torneios.jsonl (nº torneios, buy-in
    medio, ITM%, posicao media, resultado).
  - Controle: liga/desliga o agente (iniciar_bot).
Le/grava dados que o bot ja usa; portatil (app_paths). Roda do fonte ou do .exe.
"""
import json
import os
import subprocess
import sys

import tkinter as tk
from tkinter import ttk, messagebox

try:
    from app_paths import base_dir, find_data
except Exception:
    def base_dir():
        return os.path.dirname(os.path.abspath(__file__))

    def find_data(name, **k):
        return os.path.join(base_dir(), name)

BG, FG, ACCENT = '#111111', '#f5f5f5', '#ff7a00'
GRADE_FILE = os.path.join(base_dir(), 'grade_do_dia.json')
METRICS_FILE = os.path.join(base_dir(), 'logs', 'metrics', 'torneios.jsonl')


# ----------------------------- dados ------------------------------------------
def load_grade():
    for p in (GRADE_FILE, find_data('grade_do_dia.json')):
        try:
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            continue
    return []


def save_grade(rows):
    os.makedirs(os.path.dirname(GRADE_FILE) or '.', exist_ok=True)
    with open(GRADE_FILE, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def load_metrics():
    rows = []
    for p in (METRICS_FILE, find_data('torneios.jsonl', subdirs=('', 'logs', os.path.join('logs', 'metrics')))):
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding='utf-8') as f:
                for ln in f:
                    ln = ln.strip()
                    if ln:
                        rows.append(json.loads(ln))
            break
        except Exception:
            continue
    return rows


def summarize(rows):
    n = len(rows)
    buyins = [r['buyin'] for r in rows if isinstance(r.get('buyin'), (int, float))]
    itms = [r['itm'] for r in rows if r.get('itm') is not None]
    poss = [(r['placed'], r['field']) for r in rows
            if isinstance(r.get('placed'), int) and isinstance(r.get('field'), int) and r['field'] > 0]
    avg_buyin = sum(buyins) / len(buyins) if buyins else None
    itm_pct = 100.0 * sum(1 for x in itms if x) / len(itms) if itms else None
    avg_pos = 100.0 * sum(p / f for p, f in poss) / len(poss) if poss else None  # % do campo (menor=melhor)
    from collections import Counter
    res = Counter(r.get('result') or '?' for r in rows)
    return dict(n=n, avg_buyin=avg_buyin, itm_pct=itm_pct, avg_pos=avg_pos, res=dict(res))


# ----------------------------- UI ---------------------------------------------
class Painel:
    def __init__(self, root):
        self.root = root
        root.title('NVT Bot — Painel de Gestão')
        root.geometry('900x600')
        root.minsize(760, 520)
        try:
            root.configure(bg=BG)
            st = ttk.Style(); st.theme_use('clam')
            st.configure('.', background=BG, foreground=FG, fieldbackground='#1b1b1b')
            st.configure('TNotebook', background=BG)
            st.configure('TNotebook.Tab', background='#222', foreground=FG, padding=(14, 6))
            st.map('TNotebook.Tab', background=[('selected', ACCENT)], foreground=[('selected', '#000')])
            st.configure('Accent.TButton', background=ACCENT, foreground='#000', font=('Segoe UI', 10, 'bold'))
            st.configure('Treeview', background='#1b1b1b', fieldbackground='#1b1b1b', foreground=FG)
        except Exception:
            pass
        nb = ttk.Notebook(root); nb.pack(fill='both', expand=True, padx=8, pady=8)
        self._tab_grade(nb)
        self._tab_desempenho(nb)
        self._tab_controle(nb)

    # --- aba Grade do Dia ---
    def _tab_grade(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text='🗓️ Grade do Dia')
        ttk.Label(f, text='Torneios do dia (o bot registra/entra na hora):',
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        cols = ('name', 'start', 'buyin_bb', 'reg_opens')
        self.gtree = ttk.Treeview(f, columns=cols, show='headings', height=12)
        for c, t, w in (('name', 'Torneio', 300), ('start', 'Início', 90),
                        ('buyin_bb', 'Buy-in (BB)', 110), ('reg_opens', 'Insc. abre', 110)):
            self.gtree.heading(c, text=t); self.gtree.column(c, width=w)
        self.gtree.pack(fill='both', expand=True, pady=6)
        form = ttk.Frame(f); form.pack(fill='x')
        self.e_name = ttk.Entry(form, width=30); self.e_start = ttk.Entry(form, width=8)
        self.e_buyin = ttk.Entry(form, width=10); self.e_reg = ttk.Entry(form, width=8)
        for lbl, w in (('Torneio', self.e_name), ('Início HH:MM', self.e_start),
                       ('Buy-in BB', self.e_buyin), ('Insc. abre HH:MM', self.e_reg)):
            ttk.Label(form, text=lbl).pack(side='left', padx=(6, 2)); w.pack(side='left')
        ttk.Button(form, text='＋ Adicionar', command=self._grade_add).pack(side='left', padx=8)
        bar = ttk.Frame(f); bar.pack(fill='x', pady=(6, 0))
        ttk.Button(bar, text='Remover selecionado', command=self._grade_del).pack(side='left')
        ttk.Button(bar, text='💾 Salvar grade', style='Accent.TButton', command=self._grade_save).pack(side='right')
        self.grade_status = ttk.Label(bar, text='', foreground=ACCENT); self.grade_status.pack(side='right', padx=8)
        for r in load_grade():
            self.gtree.insert('', 'end', values=(r.get('name', ''), r.get('start', ''),
                              r.get('buyin_bb', ''), r.get('reg_opens', '')))

    def _grade_add(self):
        name = self.e_name.get().strip()
        if not name:
            return
        self.gtree.insert('', 'end', values=(name, self.e_start.get().strip(),
                          self.e_buyin.get().strip(), self.e_reg.get().strip()))
        for w in (self.e_name, self.e_start, self.e_buyin, self.e_reg):
            w.delete(0, 'end')

    def _grade_del(self):
        for i in self.gtree.selection():
            self.gtree.delete(i)

    def _grade_save(self):
        rows = []
        for i in self.gtree.get_children():
            name, start, buyin, reg = self.gtree.item(i, 'values')
            row = {'name': name, 'start': start}
            try:
                row['buyin_bb'] = float(buyin)
            except Exception:
                row['buyin_bb'] = 0
            if str(reg).strip():
                row['reg_opens'] = reg
            rows.append(row)
        try:
            save_grade(rows)
            self.grade_status.config(text='Grade salva (%d torneios).' % len(rows))
        except Exception as e:
            messagebox.showerror('Erro', 'Não salvou: %s' % e)

    # --- aba Desempenho ---
    def _tab_desempenho(self, nb):
        f = ttk.Frame(nb, padding=10); nb.add(f, text='📊 Desempenho')
        top = ttk.Frame(f); top.pack(fill='x')
        ttk.Button(top, text='↻ Atualizar', command=self._desemp_refresh).pack(side='left')
        self.kpis = ttk.Frame(f); self.kpis.pack(fill='x', pady=10)
        self.dtree = ttk.Treeview(f, columns=('torneio', 'buyin', 'pos', 'itm', 'result'),
                                  show='headings', height=12)
        for c, t, w in (('torneio', 'Torneio', 280), ('buyin', 'Buy-in', 90),
                        ('pos', 'Posição', 100), ('itm', 'ITM', 60), ('result', 'Resultado', 110)):
            self.dtree.heading(c, text=t); self.dtree.column(c, width=w)
        self.dtree.pack(fill='both', expand=True)
        self._desemp_refresh()

    def _kpi(self, parent, label, value):
        card = tk.Frame(parent, bg='#1b1b1b', padx=14, pady=10)
        card.pack(side='left', padx=6)
        tk.Label(card, text=value, bg='#1b1b1b', fg=ACCENT, font=('Segoe UI', 18, 'bold')).pack()
        tk.Label(card, text=label, bg='#1b1b1b', fg='#aaa', font=('Segoe UI', 9)).pack()

    def _desemp_refresh(self):
        for w in self.kpis.winfo_children():
            w.destroy()
        for i in self.dtree.get_children():
            self.dtree.delete(i)
        rows = load_metrics()
        s = summarize(rows)
        self._kpi(self.kpis, 'Torneios jogados', str(s['n']))
        self._kpi(self.kpis, 'Buy-in médio', '%.1f BB' % s['avg_buyin'] if s['avg_buyin'] is not None else '--')
        self._kpi(self.kpis, 'ITM%', '%.0f%%' % s['itm_pct'] if s['itm_pct'] is not None else '--')
        self._kpi(self.kpis, 'Posição média', '%.0f%% do campo' % s['avg_pos'] if s['avg_pos'] is not None else '--')
        for r in rows[-200:][::-1]:
            self.dtree.insert('', 'end', values=(
                r.get('tournament') or r.get('table_key') or '?',
                r.get('buyin') if r.get('buyin') is not None else '--',
                r.get('ranking') or '--',
                'Sim' if r.get('itm') else ('Não' if r.get('itm') is not None else '--'),
                r.get('result') or '--'))

    # --- aba Controle ---
    def _tab_controle(self, nb):
        f = ttk.Frame(nb, padding=16); nb.add(f, text='🎛️ Controle')
        ttk.Label(f, text='Controle do Agente', font=('Segoe UI', 13, 'bold')).pack(anchor='w')
        ttk.Label(f, text='Liga o bot (operador + exploit do field + captura de mãos + fecha '
                  'bustada). Precisa do PPPoker aberto na mesa.', foreground='#aaa',
                  wraplength=700, justify='left').pack(anchor='w', pady=(4, 12))
        self.ctl_proc = None
        ttk.Button(f, text='▶ INICIAR AGENTE', style='Accent.TButton',
                   command=self._ctl_start).pack(anchor='w', ipadx=10, ipady=6)
        ttk.Button(f, text='■ Parar agente', command=self._ctl_stop).pack(anchor='w', pady=(8, 0))
        self.ctl_status = ttk.Label(f, text='parado.', foreground=ACCENT)
        self.ctl_status.pack(anchor='w', pady=12)

    def _ctl_start(self):
        if self.ctl_proc and self.ctl_proc.poll() is None:
            self.ctl_status.config(text='já está rodando.'); return
        frozen = getattr(sys, 'frozen', False)
        cmd = [sys.executable, 'iniciar'] if frozen else [sys.executable, 'iniciar_bot.py']
        try:
            self.ctl_proc = subprocess.Popen(cmd, cwd=base_dir(),
                                             creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
            self.ctl_status.config(text='AGENTE RODANDO (veja as janelas do bot).')
        except Exception as e:
            self.ctl_status.config(text='erro ao iniciar: %s' % e)

    def _ctl_stop(self):
        if self.ctl_proc and self.ctl_proc.poll() is None:
            try:
                self.ctl_proc.terminate()
            except Exception:
                pass
            self.ctl_status.config(text='parado (feche as janelas do bot se sobraram).')
        else:
            self.ctl_status.config(text='não estava rodando.')


def main():
    root = tk.Tk()
    Painel(root)
    root.mainloop()


if __name__ == '__main__':
    main()
