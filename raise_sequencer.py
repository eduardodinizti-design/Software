"""Fluxo MULTI-ETAPA do aumento (spec cursor §11): abrir painel → escolher preset
→ confirmar, cada etapa REVALIDADA por recaptura (nunca às cegas).

Sequência:
  0) captura → acha a mesa + o botão RAISE (vez ativa do hero).
  A) clica RAISE → recaptura → confirma que o PAINEL abriu (read_raise_panel).
  B) mapeia o multiplicador-alvo → PRESET (2×/2.5×/3×/4×) e clica nele.
  C) recaptura → clica no CONFIRMAR (amarelo) → verifica que a linha de botões
     sumiu (aposta entrou).

Reusa o MESMO retângulo da mesa nas etapas (o detect_table_crops falha com o
painel aberto; a janela não se move). `capture`/leitores/`input_adapter` são
injetáveis → testável sem Windows. Clique único com soltura garantida via o
adaptador; gate por BotControl antes de CADA clique (pausa desarma na hora).
"""
import time

import cv2

from table_reading.automatic_table_crops import detect_table_crops
from table_reading.action_buttons import read_action_buttons
from raise_panel import read_raise_panel, map_multiplier_to_preset
from screen_coords import frame_to_screen


class RaiseSequencer:
    def __init__(self, *, capture, window_rect, input_adapter, target_mult,
                 bot_control=None, max_tables=6, sleep=time.sleep,
                 read_actions=read_action_buttons, read_panel=read_raise_panel,
                 detect=detect_table_crops):
        self.capture = capture
        self.window_rect = window_rect
        self.input = input_adapter
        self.target_mult = target_mult
        self.bot = bot_control
        self.max_tables = max_tables
        self._sleep = sleep
        self._ra = read_actions
        self._rp = read_panel
        self._detect = detect
        self.log = []
        self._crop_box = None

    def _armed(self):
        return self.bot is None or bool(self.bot.execution_allowed())

    def _fail(self, reason):
        self.log.append(('FAIL', reason))
        return dict(ok=False, reason=reason, log=self.log)

    def _table(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        for p in self._detect(rgb, max_tables=self.max_tables):
            x, y, w, h = map(int, p.box)
            return frame[y:y + h, x:x + w], (x, y)
        return None, None

    def _click(self, box_crop, origin, frame_size, what):
        """Gate → move → clique único no centro do botão (coords de tela)."""
        if not self._armed():
            self.log.append((what, 'BOT_PAUSADO'))
            return False
        ox, oy = origin
        x, y, w, h = box_crop
        cx, cy = ox + x + w / 2.0, oy + y + h / 2.0
        sx, sy = frame_to_screen((cx, cy), window_rect=self.window_rect,
                                 frame_size=frame_size)
        self.input.move_to(sx, sy)
        r = self.input.click_once(sx, sy)
        self.log.append((what, (round(sx), round(sy)),
                         'ok' if r.get('released') else 'NAO_SOLTO'))
        return bool(r.get('released', True))

    def _recap_crop(self):
        frame, _ = self.capture()
        if frame is None or self._crop_box is None:
            return None, None, None
        x, y, w, h = self._crop_box
        return frame[y:y + h, x:x + w], (frame.shape[1], frame.shape[0]), (x, y)

    def run(self):
        # 0) mesa + botão RAISE
        frame, _ = self.capture()
        if frame is None:
            return self._fail('SEM_CAPTURA')
        fsize = (frame.shape[1], frame.shape[0])
        table, origin = self._table(frame)
        if table is None:
            return self._fail('SEM_MESA')
        self._crop_box = (origin[0], origin[1], table.shape[1], table.shape[0])
        br = self._ra(table)
        if br['status'] != 'EXPERIMENTAL_BUTTON_ROW':
            return self._fail('NAO_E_VEZ_DO_HERO')
        rb = next((b for b in br['buttons'] if b.get('action') == 'RAISE'), None)
        if rb is None:
            return self._fail('SEM_BOTAO_RAISE')
        if not self._armed():
            return self._fail('BOT_PAUSADO')

        # A) abrir o painel
        if not self._click(rb['box'], origin, fsize, 'ABRIR'):
            return self._fail('CLICK_ABRIR_FALHOU')
        self._sleep(0.3)
        crop, fs, org = self._recap_crop()
        panel = self._rp(crop) if crop is not None else None
        if not panel or panel.get('status') != 'EXPERIMENTAL_RAISE_PANEL':
            return self._fail('PAINEL_NAO_ABRIU')

        # B) escolher o preset
        preset = map_multiplier_to_preset(self.target_mult, panel['presets'])
        if preset is None:
            return self._fail('SEM_PRESET_PARA_ALVO:%s' % self.target_mult)
        if not self._click(preset['box'], org, fs, 'PRESET_%sx' % preset['mult']):
            return self._fail('CLICK_PRESET_FALHOU')
        self._sleep(0.25)

        # C) confirmar
        crop2, fs2, org2 = self._recap_crop()
        panel2 = self._rp(crop2) if crop2 is not None else None
        confirm = (panel2 or panel).get('confirm')
        if confirm is None:
            return self._fail('SEM_BOTAO_CONFIRMAR')
        if not self._click(confirm['box'], org2 or org, fs2 or fs, 'CONFIRMAR'):
            return self._fail('CLICK_CONFIRMAR_FALHOU')
        self._sleep(0.3)

        # verificar efeito: a linha de botões sumiu (aposta entrou)
        crop3, _, _ = self._recap_crop()
        confirmed = (crop3 is not None
                     and self._ra(crop3)['status'] != 'EXPERIMENTAL_BUTTON_ROW')
        return dict(ok=True, confirmed=confirmed, preset=preset['mult'],
                    target_mult=self.target_mult, log=self.log)
