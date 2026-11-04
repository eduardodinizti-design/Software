"""VisualPilot - Fase 1 / Módulo 4: Automação de Cliques, Tradução de Coordenadas e Auditoria em CSV.

Converte coordenadas relativas (local_box e click_point_local) extraídas nos
Módulos 2 e 3 em cliques absolutos no Windows via PyAutoGUI, localizando e
monitorando o estado da janela do PPPoker dinamicamente através do PyGetWindow.
Inclui sistema de auditoria persistente em CSV com rotatividade diária e guardião
de integridade de janela em tempo real.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import sys
import threading
import time
from typing import Any, Callable
import urllib.error
import urllib.request

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore


def _clip(val: float, low: float, high: float) -> float:
    """Fallback nativo para corte de valores numéricos sem dependência de numpy."""
    return max(low, min(high, val))

try:
    import pygetwindow as gw
except (ImportError, NotImplementedError):
    gw = None  # type: ignore

try:
    import pyautogui
except Exception:
    pyautogui = None  # type: ignore


class WindowNotFoundError(RuntimeError):
    """Lançada quando a janela do PPPoker não é localizada no desktop."""


class WindowStateError(RuntimeError):
    """Lançada quando a janela está minimizada, oculta ou com dimensões inválidas."""


class WindowDrasticChangeError(RuntimeError):
    """Lançada quando a resolução ou proporção da janela muda drasticamente antes do clique."""


class CoordinateBoundsError(ValueError):
    """Lançada quando a coordenada calculada cai fora da área visível da janela."""


class SystemHaltError(RuntimeError):
    """Lançada quando o sistema entra em estado SYSTEM_HALT por falta de pulsação (heartbeat)."""


CSV_HEADERS = [
    "timestamp_iso",
    "session_name",
    "event_type",
    "status",
    "tournament_name",
    "card_index",
    "buyin_chips",
    "target_abs_x",
    "target_abs_y",
    "win_left",
    "win_top",
    "win_width",
    "win_height",
    "duration_ms",
    "details"
]


class AuditLogger:
    """Registrador de auditoria em CSV com rotatividade diária automática e flush imediato."""

    def __init__(self, logs_dir: Path | str = "logs", default_session_name: str = "Sessão Padrão"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.default_session_name = default_session_name
        self._lock = threading.Lock()

    def get_current_log_path(self, now: datetime | None = None) -> Path:
        dt = now or datetime.now(timezone.utc)
        filename = f"clicks_audit_{dt.strftime('%Y-%m-%d')}.csv"
        return self.logs_dir / filename

    def log_event(
        self,
        event_type: str,
        status: str,
        tournament_name: str = "",
        card_index: int | str = "",
        buyin_chips: str = "",
        target_abs_x: int | str = "",
        target_abs_y: int | str = "",
        win_box: list[int] | tuple[int, int, int, int] | None = None,
        duration_ms: float | str = "",
        details: str = "",
        session_name: str | None = None,
        now: datetime | None = None
    ) -> dict[str, Any]:
        dt = now or datetime.now(timezone.utc)
        timestamp_iso = dt.isoformat()
        current_session = session_name if session_name is not None else self.default_session_name

        wb = win_box or [0, 0, 0, 0]
        w_left, w_top, w_width, w_height = wb[0], wb[1], wb[2], wb[3]

        record = {
            "timestamp_iso": timestamp_iso,
            "session_name": current_session,
            "event_type": event_type,
            "status": status,
            "tournament_name": tournament_name,
            "card_index": str(card_index),
            "buyin_chips": str(buyin_chips),
            "target_abs_x": str(target_abs_x),
            "target_abs_y": str(target_abs_y),
            "win_left": str(w_left),
            "win_top": str(w_top),
            "win_width": str(w_width),
            "win_height": str(w_height),
            "duration_ms": f"{float(duration_ms):.1f}" if duration_ms != "" else "",
            "details": details
        }

        log_path = self.get_current_log_path(dt)

        with self._lock:
            file_exists = log_path.is_file()
            with open(log_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(record)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass

        return record


class WindowIntegrityGuardian:
    """Monitor de integridade da janela do PPPoker."""

    @staticmethod
    def inspect_window(win_info: dict[str, Any], initial_win: dict[str, Any] | None = None) -> None:
        """Verifica se a janela está viva, visível e não sofreu mudança drástica de resolução."""
        if not win_info:
            raise WindowNotFoundError("Janela do PPPoker não foi encontrada (possivelmente fechada).")

        w, h = win_info.get("width", 0), win_info.get("height", 0)
        if w < 200 or h < 300:
            raise WindowStateError(f"Dimensões da janela inválidas ou colapsadas: {w}x{h}.")

        ratio = w / float(max(1, h))
        # Proporção esperada do lobby em portrait
        if not (0.35 <= ratio <= 0.85):
            raise WindowDrasticChangeError(
                f"Proporção da janela deformada: W/H = {ratio:.2f} ({w}x{h}). "
                "Esperado formato retrato entre 0.35 e 0.85."
            )

        if initial_win:
            init_w, init_h = initial_win.get("width", w), initial_win.get("height", h)
            # Se a área mudou mais de 35% subitamente entre o planejamento e o clique
            area_current = w * h
            area_initial = init_w * init_h
            if area_initial > 0:
                area_ratio = area_current / float(area_initial)
                if area_ratio < 0.65 or area_ratio > 1.45:
                    raise WindowDrasticChangeError(
                        f"Resolução da janela alterada drasticamente durante a operação: "
                        f"de {init_w}x{init_h} para {w}x{h} (variação de {area_ratio:.2f}x)."
                    )


def mask_webhook_url(url: str | None) -> str:
    """Mascara URLs sensíveis de webhook para exibição segura em logs e relatórios."""
    if not url:
        return "Nenhum (Modo Local/Simulado)"
    if "://" not in url:
        return "***"
    prefix, sep, suffix = url.partition("://")
    parts = suffix.split("/")
    if len(parts) <= 1:
        return f"{prefix}://{parts[0][:4]}***"
    domain = parts[0]
    path_mask = "/".join(p[:4] + "***" if len(p) > 4 else "***" for p in parts[1:])
    return f"{prefix}://{domain}/{path_mask}"


class EscalationNotifier:
    """Gerenciador de notificações remotas de escalada (Discord, Telegram, Webhook genérico ou E-mail).

    Disparado quando o sistema permanece em estado SYSTEM_HALT por mais de 5 minutos (300 segundos),
    garantindo que o operador seja alertado imediatamente mesmo longe do monitor.
    """

    def __init__(self, default_webhook_url: str | None = None, timeout: float = 8.0):
        self.default_webhook_url = default_webhook_url or os.getenv("VISUALPILOT_WEBHOOK_URL")
        self.timeout = float(timeout)

    def build_payload(
        self,
        title: str,
        details: str,
        elapsed_seconds: float,
        webhook_url: str,
        extra_fields: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any], str]:
        """Constrói o payload adequado de acordo com a URL do serviço (Discord, Telegram ou Webhook genérico)."""
        dt_iso = datetime.now(timezone.utc).isoformat()
        elapsed_min = elapsed_seconds / 60.0
        url_lower = webhook_url.lower()

        # Discord Webhook
        if "discord.com/api/webhooks" in url_lower:
            payload = {
                "content": f"🚨 **[ALERTA CRÍTICO: VISUALPILOT]** O bot entrou em **SYSTEM_HALT** há {elapsed_seconds:.0f}s ({elapsed_min:.1f} min)!",
                "embeds": [
                    {
                        "title": title or "🚨 Paralisação Crítica do Bot (> 5 minutos)",
                        "description": details,
                        "color": 15158332,  # Vermelho Alerta (0xE74C3C)
                        "fields": [
                            {"name": "Status", "value": "SYSTEM_HALT", "inline": True},
                            {"name": "Tempo Paralisado", "value": f"{elapsed_seconds:.1f}s (~{elapsed_min:.1f} min)", "inline": True},
                            {"name": "Ação de Proteção", "value": "Cliques bloqueados preventivamente", "inline": True},
                            {"name": "Data/Hora UTC", "value": dt_iso, "inline": False},
                            {"name": "Ação Recomendada", "value": "Acesse o desktop do bot e verifique se o PPPoker ou o script VisualPilot congelou.", "inline": False}
                        ],
                        "footer": {
                            "text": "VisualPilot Módulo 4 • Sistema de Escalada Watchdog"
                        }
                    }
                ]
            }
            return payload, "discord"

        # Telegram Bot
        if "api.telegram.org" in url_lower or "telegram" in url_lower:
            text = (
                f"🚨 *[VISUALPILOT CRITICAL]*\n"
                f"*{title}*\n\n"
                f"{details}\n\n"
                f"⏱ *Inatividade:* {elapsed_seconds:.1f}s (~{elapsed_min:.1f} min)\n"
                f"🕒 *Data UTC:* `{dt_iso}`\n"
                f"🛡 *Status:* Ações bloqueadas preventivamente.\n\n"
                f"👉 _Verifique o computador do bot imediatamente._"
            )
            payload = {
                "text": text,
                "parse_mode": "Markdown"
            }
            return payload, "telegram"

        # Webhook genérico (Slack, Zapier, Make/Integromat, n8n, Webhook de e-mail ou servidor próprio)
        payload = {
            "event": "SYSTEM_HALT_ESCALATION",
            "title": title,
            "status": "ESCALATED",
            "severity": "CRITICAL",
            "elapsed_seconds": round(elapsed_seconds, 1),
            "elapsed_minutes": round(elapsed_min, 2),
            "timestamp_utc": dt_iso,
            "details": details,
            "instructions": "Verifique o processo do bot e a janela PPPoker no desktop.",
            "custom": extra_fields or {}
        }
        return payload, "generic"

    def send_escalation(
        self,
        title: str = "Paralisação Crítica do Bot (> 5 minutos)",
        details: str = "O bot está congelado há mais de 300 segundos sem emitir pulsação de batimentos cardíacos.",
        elapsed_seconds: float = 300.0,
        webhook_url: str | None = None,
        dry_run: bool = False,
        extra_fields: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Despacha a notificação de escalada para o webhook configurado."""
        target_url = webhook_url or self.default_webhook_url
        dt_iso = datetime.now(timezone.utc).isoformat()

        if not target_url or target_url.startswith("mock://") or target_url.startswith("simulated://") or dry_run:
            payload, provider = self.build_payload(
                title=title,
                details=details,
                elapsed_seconds=elapsed_seconds,
                webhook_url=target_url or "mock://simulated-webhook",
                extra_fields=extra_fields
            )
            return {
                "success": True,
                "mode": "simulated",
                "provider": provider,
                "target_url": mask_webhook_url(target_url),
                "timestamp_utc": dt_iso,
                "elapsed_seconds": elapsed_seconds,
                "payload": payload,
                "http_status": 200,
                "message": "Alerta de escalada simulado com sucesso (modo dry-run/mock)"
            }

        try:
            payload, provider = self.build_payload(
                title=title,
                details=details,
                elapsed_seconds=elapsed_seconds,
                webhook_url=target_url,
                extra_fields=extra_fields
            )
            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url=target_url,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "VisualPilot-Watchdog-Escalation/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                status_code = getattr(response, "status", 200)
                resp_body = response.read().decode("utf-8", errors="ignore")
                return {
                    "success": 200 <= status_code < 300,
                    "mode": "live",
                    "provider": provider,
                    "target_url": mask_webhook_url(target_url),
                    "timestamp_utc": dt_iso,
                    "elapsed_seconds": elapsed_seconds,
                    "http_status": status_code,
                    "response": resp_body[:300],
                    "payload": payload,
                    "message": f"Webhook despachado com sucesso ({status_code})"
                }
        except urllib.error.HTTPError as http_err:
            return {
                "success": False,
                "mode": "live",
                "provider": "unknown",
                "target_url": mask_webhook_url(target_url),
                "timestamp_utc": dt_iso,
                "elapsed_seconds": elapsed_seconds,
                "http_status": http_err.code,
                "error": f"Erro HTTP {http_err.code}: {http_err.reason}",
                "message": f"Falha no despacho do webhook: {http_err}"
            }
        except Exception as exc:
            return {
                "success": False,
                "mode": "live",
                "provider": "unknown",
                "target_url": mask_webhook_url(target_url),
                "timestamp_utc": dt_iso,
                "elapsed_seconds": elapsed_seconds,
                "http_status": 0,
                "error": f"{type(exc).__name__}: {exc}",
                "message": f"Exceção de rede no webhook: {exc}"
            }


class HeartbeatMonitor:
    """Monitor de batimentos cardíacos (watchdog) com escalada remota via Webhook/Email.

    1. Watchdog Local (30s): Se o bot travar por erro de software ou permanecer inativo por mais de
       `timeout_seconds` (padrão 30.0s), o monitor registra um evento 'SYSTEM_HALT' no arquivo CSV
       de auditoria e bloqueia o despacho de cliques, evitando ações obsoletas.
    2. Escalada Remota (> 5 min): Caso o sistema permaneça em estado 'SYSTEM_HALT' por mais de
       `escalation_timeout_seconds` (padrão 300.0s = 5 minutos), um alerta crítico é despachado
       via webhook (Discord, Telegram, Zapier/Make ou E-mail) e registrado no log CSV.
    """

    def __init__(
        self,
        logger: AuditLogger | None = None,
        timeout_seconds: float = 30.0,
        check_interval: float = 1.0,
        auto_start: bool = False,
        on_halt: Any = None,
        escalation_timeout_seconds: float = 300.0,
        webhook_url: str | None = None,
        escalation_notifier: EscalationNotifier | None = None,
        on_escalate: Any = None
    ):
        self.logger = logger or AuditLogger()
        self.timeout_seconds = float(timeout_seconds)
        self.check_interval = float(check_interval)
        self.on_halt = on_halt
        self.escalation_timeout_seconds = float(escalation_timeout_seconds)
        self.webhook_url = webhook_url or os.getenv("VISUALPILOT_WEBHOOK_URL")
        self.escalation_notifier = escalation_notifier or EscalationNotifier(default_webhook_url=self.webhook_url)
        self.on_escalate = on_escalate

        self._lock = threading.Lock()
        self._last_beat: float = time.monotonic()
        self._is_halted: bool = False
        self._halt_time: float | None = None
        self._escalation_sent: bool = False
        self._escalation_time: float | None = None
        self._last_escalation_result: dict[str, Any] | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        if auto_start:
            self.start()

    @property
    def is_halted(self) -> bool:
        with self._lock:
            return self._is_halted

    @property
    def is_escalated(self) -> bool:
        with self._lock:
            return self._escalation_sent

    @property
    def last_beat_age(self) -> float:
        with self._lock:
            return max(0.0, time.monotonic() - self._last_beat)

    @property
    def halt_duration(self) -> float:
        with self._lock:
            if not self._is_halted or self._halt_time is None:
                return 0.0
            return max(0.0, time.monotonic() - self._halt_time)

    @property
    def time_until_escalation(self) -> float:
        with self._lock:
            if not self._is_halted or self._halt_time is None:
                return self.escalation_timeout_seconds
            elapsed_in_halt = time.monotonic() - self._halt_time
            return max(0.0, self.escalation_timeout_seconds - elapsed_in_halt)

    @property
    def last_escalation_result(self) -> dict[str, Any] | None:
        with self._lock:
            return self._last_escalation_result

    def beat(self, note: str = "") -> None:
        """Emite uma pulsação ativa do bot, renovando o watchdog."""
        with self._lock:
            if not self._is_halted:
                self._last_beat = time.monotonic()

    def check_pulse(self, now: float | None = None) -> bool:
        """Verifica a integridade da pulsação e avalia necessidade de escalada remota."""
        with self._lock:
            current_time = now if now is not None else time.monotonic()
            elapsed = current_time - self._last_beat

            if elapsed >= self.timeout_seconds:
                if not self._is_halted:
                    self._is_halted = True
                    self._halt_time = current_time
                    self._escalation_sent = False
                    self._escalation_time = None
                    self.logger.log_event(
                        event_type="SYSTEM_HALT",
                        status="HALT",
                        details=(
                            f"Inatividade detectada: sem pulsação por {elapsed:.1f}s "
                            f"(limite: {self.timeout_seconds:.1f}s). Possível travamento do software. "
                            "Ações bloqueadas preventivamente."
                        )
                    )
                    if callable(self.on_halt):
                        try:
                            self.on_halt()
                        except Exception:
                            pass

                # Avalia escalada remota se o tempo em SYSTEM_HALT exceder escalation_timeout_seconds (5 min)
                halt_duration = current_time - (self._halt_time if self._halt_time is not None else current_time)
                if halt_duration >= self.escalation_timeout_seconds and not self._escalation_sent:
                    self._escalation_sent = True
                    self._escalation_time = current_time
                    masked_target = mask_webhook_url(self.webhook_url)
                    esc_details = (
                        f"Sistema em SYSTEM_HALT há {halt_duration:.1f}s (~{halt_duration / 60.0:.1f} min, "
                        f"teto {self.escalation_timeout_seconds:.0f}s). Alerta remoto despachado via webhook ({masked_target})."
                    )
                    self.logger.log_event(
                        event_type="ESCALATION_ALERT_SENT",
                        status="ESCALATED",
                        details=esc_details
                    )
                    esc_res = self.escalation_notifier.send_escalation(
                        title="🚨 Paralisação Crítica do Bot (> 5 minutos)",
                        details=esc_details,
                        elapsed_seconds=halt_duration,
                        webhook_url=self.webhook_url
                    )
                    self._last_escalation_result = esc_res
                    if callable(self.on_escalate):
                        try:
                            self.on_escalate(esc_res)
                        except Exception:
                            pass

                return False
            return not self._is_halted

    def trigger_manual_escalation(
        self,
        reason: str = "Disparo manual de teste de webhook",
        now: float | None = None
    ) -> dict[str, Any]:
        """Dispara manualmente um alerta remoto de teste via webhook para validação operacional."""
        with self._lock:
            current_time = now if now is not None else time.monotonic()
            elapsed = (current_time - self._halt_time) if (self._is_halted and self._halt_time is not None) else 300.0
            masked_target = mask_webhook_url(self.webhook_url)
            details = f"Disparo manual de teste de webhook ({reason}) para {masked_target}."
            self.logger.log_event(
                event_type="ESCALATION_ALERT_SENT",
                status="ESCALATED",
                details=details
            )
            res = self.escalation_notifier.send_escalation(
                title=f"⚠️ Teste de Notificação Remota ({reason})",
                details=details,
                elapsed_seconds=elapsed,
                webhook_url=self.webhook_url
            )
            self._last_escalation_result = res
            return res

    def assert_healthy(self) -> None:
        """Assegura que o sistema não está paralisado; lança SystemHaltError se estiver."""
        if not self.check_pulse():
            raise SystemHaltError(
                f"Sistema paralisado (SYSTEM_HALT): inatividade superior a {self.timeout_seconds:.1f}s. "
                "Operação abortada preventivamente para evitar ações obsoletas."
            )

    def resume(self, reason: str = "Pulsação restabelecida pelo operador") -> None:
        """Restaura o monitor após estado de halt e grava o restabelecimento no log CSV."""
        with self._lock:
            was_halted = self._is_halted
            was_escalated = self._escalation_sent
            self._is_halted = False
            self._last_beat = time.monotonic()
            self._halt_time = None
            self._escalation_sent = False
            self._escalation_time = None

            if was_halted:
                detail_msg = f"Watchdog restabelecido: {reason}."
                if was_escalated:
                    detail_msg += " (Alerta de escalada remota redefinido)"
                self.logger.log_event(
                    event_type="SYSTEM_RESUMED",
                    status="SUCCESS",
                    details=detail_msg
                )

    def start(self) -> None:
        """Inicia o watchdog em uma thread daemon em segundo plano."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="VisualPilot-HeartbeatWatchdog",
                daemon=True
            )
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Encerra a thread de monitoramento do watchdog."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.check_pulse()
            self._stop_event.wait(self.check_interval)


PPP_TABLE_KEYWORDS = [
    "mtt", "nlh", "plo", "pko", "sat", "sng", "spin", "freeze", "stack",
    "rebuy", "table", "mesa", "big", "warm", "mini", "super", "4-max",
    "6-max", "9-max", "heads-up", "cash", "poker", "v228", "v2"
]


def is_pppoker_window_title(title: str) -> bool:
    """Verifica se o título da janela pertence ao cliente ou às mesas do PPPoker."""
    if not title:
        return False
    t = title.lower()
    if "pppoker" in t or "ldplayer" in t or "mumu" in t or "nox" in t:
        return True
    # Detecta títulos de mesas do PPPoker (ex: 'MTT NLH - v228', 'NLH 200 - v228', 'PLO5 - v228')
    if "- v2" in t or "v228" in t or "pppoker" in t:
        return True
    if any(kw in t for kw in ["mtt", "nlh", "plo", "pko", "sng", "spin"]) and len(t) < 40:
        return True
    return False


def score_pppoker_window_obj(win: Any, title_keyword: str = "pppoker") -> float:
    """Calcula prioridade da janela, dando preferência absoluta para mesas ativas sobre o lobby."""
    title = getattr(win, "title", "") or ""
    t_lower = title.lower()
    kw_lower = (title_keyword or "pppoker").lower()

    if not is_pppoker_window_title(title) and kw_lower not in t_lower:
        return -1000.0

    score = 0.0
    w = getattr(win, "width", 0)
    h = getattr(win, "height", 0)

    # 1. Prioridade para janelas de MESA DE POKER
    has_table_kw = any(k in t_lower for k in ["mtt", "nlh", "plo", "pko", "sat", "sng", "spin", "freeze", "stack", "4-max", "6-max", "9-max", "cash"])
    is_lobby_only = ("pppoker" in t_lower and not has_table_kw)

    if has_table_kw:
        score += 500.0  # Mesa aberta tem prioridade máxima!
    elif is_lobby_only:
        score += 50.0   # Lobby é fallback se nenhuma mesa estiver aberta

    # Se a palavra-chave específica foi solicitada (ex: 'MTT')
    if kw_lower and kw_lower in t_lower and kw_lower != "pppoker":
        score += 300.0

    # 2. Bônus por dimensões de mesa
    if w > 150 and h > 200:
        score += 100.0

    # 3. Bônus por janela em foco/ativa
    if getattr(win, "isActive", False):
        score += 80.0

    # 4. Penalidade se minimizada
    if getattr(win, "isMinimized", False):
        score -= 200.0

    return score


def find_pppoker_window(title_keyword: str = "pppoker") -> dict[str, Any]:
    """Localiza a janela do PPPoker (dando prioridade para mesas de jogo ativas como 'MTT NLH - v228')."""
    if gw is None:
        raise ImportError("A biblioteca 'pygetwindow' é necessária. Execute pip install pygetwindow.")

    all_windows = gw.getAllWindows()
    candidates = []

    for w in all_windows:
        t = getattr(w, "title", "") or ""
        sc = score_pppoker_window_obj(w, title_keyword=title_keyword)
        if sc > -500.0 and getattr(w, "width", 0) > 100 and getattr(w, "height", 0) > 150:
            candidates.append((sc, w))

    if not candidates:
        raise WindowNotFoundError(
            f"Nenhuma janela do PPPoker ou mesa de jogo (ex: 'MTT NLH - v228') encontrada. "
            "Certifique-se de que o aplicativo PPPoker e a mesa estão visíveis no Windows."
        )

    # Ordena por maior pontuação
    candidates.sort(key=lambda item: item[0], reverse=True)
    target_win = candidates[0][1]

    if getattr(target_win, "isMinimized", False):
        try:
            target_win.restore()
            time.sleep(0.2)
        except Exception:
            raise WindowStateError("A janela do PPPoker está minimizada. Restaure-a para permitir o clique.")

    return {
        "title": target_win.title,
        "left": int(target_win.left),
        "top": int(target_win.top),
        "width": int(target_win.width),
        "height": int(target_win.height),
        "is_active": getattr(target_win, "isActive", False),
        "window_obj": target_win
    }


def attempt_window_recovery(
    executable_path: str | Path | None = None,
    timeout_seconds: float = 12.0,
    title_keyword: str = "pppoker",
    logger: AuditLogger | None = None,
    session_name: str | None = None
) -> dict[str, Any]:
    """Tenta reabrir automaticamente a janela do PPPoker caso ela seja detectada como fechada."""
    import subprocess
    audit = logger or AuditLogger()
    target_path = Path(executable_path) if executable_path else Path(os.getenv("PPPOKER_EXE_PATH", r"C:\Program Files (x86)\PPPoker\PPPoker.exe"))

    audit.log_event(
        event_type="RECOVERY_ATTEMPTED",
        status="ABORTED",
        session_name=session_name,
        details=f"Modo de Recuperação: disparando executável em '{target_path}'..."
    )

    is_mock = str(target_path).startswith("mock://")
    if not target_path.exists() and not is_mock:
        err_msg = f"Executável do PPPoker não localizado em '{target_path}'. Configure o caminho correto."
        audit.log_event(
            event_type="RECOVERY_FAILED",
            status="ERROR",
            session_name=session_name,
            details=err_msg
        )
        raise FileNotFoundError(err_msg)

    if not is_mock:
        try:
            subprocess.Popen([str(target_path)], shell=False)
        except Exception as exc:
            err_msg = f"Falha ao executar '{target_path}': {exc}"
            audit.log_event(
                event_type="RECOVERY_FAILED",
                status="ERROR",
                session_name=session_name,
                details=err_msg
            )
            raise

    # Aguarda restauração da janela com polling
    started_wait = time.monotonic()
    restored_win = None
    while (time.monotonic() - started_wait) < timeout_seconds:
        time.sleep(1.0)
        try:
            restored_win = find_pppoker_window(title_keyword)
            if restored_win:
                break
        except Exception:
            pass

    if restored_win:
        audit.log_event(
            event_type="RECOVERY_SUCCESS",
            status="SUCCESS",
            session_name=session_name,
            win_box=[restored_win["left"], restored_win["top"], restored_win["width"], restored_win["height"]],
            details=f"PPPoker recuperado com sucesso: janela restaurada em ({restored_win['left']}, {restored_win['top']}) {restored_win['width']}x{restored_win['height']}."
        )
        return {"status": "recovered", "window": restored_win}
    else:
        err_msg = f"Timeout na recuperação ({timeout_seconds:.1f}s): Janela do PPPoker não detectada após execução."
        audit.log_event(
            event_type="RECOVERY_TIMEOUT",
            status="ERROR",
            session_name=session_name,
            details=err_msg
        )
        raise TimeoutError(err_msg)


def calculate_absolute_click(
    click_point_local: list[float] | tuple[float, float],
    window_rect: dict[str, int],
    captured_size: list[int] | tuple[int, int] = (787, 1470),
    apply_jitter: bool = True
) -> tuple[int, int, dict[str, Any]]:
    """Traduz as coordenadas relativas da imagem para coordenadas absolutas de tela."""
    # Validação rigorosa de alça de janela ativa (HWND) e processo do PPPoker.exe
    if window_rect.get("has_handle") is False:
        raise WindowStateError("Processo 'PPPoker.exe' perdeu a alça de janela ativa (HWND nulo ou invalidado).")
    if window_rect.get("is_alive") is False:
        raise WindowStateError("Processo 'PPPoker.exe' não está ativo no sistema operacional.")
    if window_rect.get("width", 0) <= 0 or window_rect.get("height", 0) <= 0:
        raise WindowStateError("Janela do 'PPPoker.exe' está fechada ou com dimensões colapsadas (0x0).")

    local_x, local_y = float(click_point_local[0]), float(click_point_local[1])
    win_left = window_rect["left"]
    win_top = window_rect["top"]
    win_width = window_rect["width"]
    win_height = window_rect["height"]

    cap_w, cap_h = float(captured_size[0]), float(captured_size[1])

    scale_x = win_width / cap_w if cap_w > 0 else 1.0
    scale_y = win_height / cap_h if cap_h > 0 else 1.0

    scaled_x = local_x * scale_x
    scaled_y = local_y * scale_y

    jitter_x = 0.0
    jitter_y = 0.0
    if apply_jitter:
        raw_jx = random.gauss(0, 3.0)
        raw_jy = random.gauss(0, 2.0)
        jitter_x = float(np.clip(raw_jx, -12.0, 12.0)) if np is not None else float(_clip(raw_jx, -12.0, 12.0))
        jitter_y = float(np.clip(raw_jy, -7.0, 7.0)) if np is not None else float(_clip(raw_jy, -7.0, 7.0))

    final_abs_x = int(round(win_left + scaled_x + jitter_x))
    final_abs_y = int(round(win_top + scaled_y + jitter_y))

    margin = 8
    if not (win_left + margin <= final_abs_x <= win_left + win_width - margin and
            win_top + margin <= final_abs_y <= win_top + win_height - margin):
        raise CoordinateBoundsError(
            f"Coordenada calculada ({final_abs_x}, {final_abs_y}) está fora dos limites da janela "
            f"[{win_left}, {win_top}, {win_width}, {win_height}]."
        )

    meta = {
        "local_point": [local_x, local_y],
        "scale_factors": [round(scale_x, 4), round(scale_y, 4)],
        "jitter": [round(jitter_x, 2), round(jitter_y, 2)],
        "absolute_point": [final_abs_x, final_abs_y],
        "window_box": [win_left, win_top, win_width, win_height]
    }

    return final_abs_x, final_abs_y, meta


CLICK_SPEED_PROFILES: dict[str, dict[str, Any]] = {
    "fast": {
        "name": "rápido",
        "move_duration": 0.16,
        "press_delay": 0.055,
        "default_reaction_delay": (0.15, 0.35)
    },
    "natural": {
        "name": "natural",
        "move_duration": 0.30,
        "press_delay": 0.090,
        "default_reaction_delay": (0.35, 0.85)
    },
    "slow": {
        "name": "lento",
        "move_duration": 0.65,
        "press_delay": 0.140,
        "default_reaction_delay": (0.80, 1.80)
    }
}


def human_bezier_ease(n: float) -> float:
    """Curva de aceleração customizada que simula a cinemática neuromuscular humana.

    Substitui padrões robóticos de velocidade constante ou interpolações lineares/quadráticas
    simétricas por um perfil assimétrico fundamentado na Lei de Fitts e no modelo de controle
    motor com mínimo jerk (Flanagan & Ostry):
    - Fase balística inicial (0.0 a 0.35): Rápida aceleração até atingir a velocidade de pico
      por volta de 35% do deslocamento.
    - Fase de desaceleração inercial (0.35 a 0.85): Redução suave da velocidade com amortecimento.
    - Fase de assentamento / mira fina (0.85 a 1.0): Aproximação assintótica com micro-acomodação.
    """
    if n <= 0.0:
        return 0.0
    if n >= 1.0:
        return 1.0

    if n < 0.35:
        # Aceleração rápida balística com curvatura suave no início
        t = n / 0.35
        return 0.40 * (t * t * (3.0 - 2.0 * t))
    else:
        # Desaceleração progressiva e assentamento suave
        t = (n - 0.35) / 0.65
        return 0.40 + 0.60 * (1.0 - (1.0 - t) ** 2.8)


def generate_bezier_trajectory(
    start_pt: tuple[float, float],
    end_pt: tuple[float, float],
    num_steps: int = 12,
    jitter_magnitude: float = 1.5,
    deviation_ratio: float | None = None
) -> dict[str, Any]:
    """Gera uma trajetória curva Bézier cúbica com controle motor humano e micro-jitter.

    Args:
        start_pt: Ponto inicial (x0, y0).
        end_pt: Ponto final de destino (x1, y1).
        num_steps: Quantidade de waypoints discretizados ao longo do deslocamento.
        jitter_magnitude: Amplitude máxima do micro-tremor neuromuscular em pixels.
        deviation_ratio: Razão de curvatura perpendicular relativa à distância euclidiana.
                         Se None, sorteia entre 0.04 e 0.12 com direção aleatória.

    Returns:
        Dicionário com waypoints, pontos de controle P0, P1, P2, P3 e metadados fisiológicos.
    """
    x0, y0 = float(start_pt[0]), float(start_pt[1])
    x3, y3 = float(end_pt[0]), float(end_pt[1])

    dx = x3 - x0
    dy = y3 - y0
    dist = (dx * dx + dy * dy) ** 0.5

    if dist < 3.0:
        return {
            "waypoints": [(round(x3, 1), round(y3, 1))],
            "control_points": [(round(x0, 1), round(y0, 1)), (round(x0, 1), round(y0, 1)),
                               (round(x3, 1), round(y3, 1)), (round(x3, 1), round(y3, 1))],
            "distance": round(dist, 1),
            "jitter_magnitude": jitter_magnitude,
            "acceleration_curve": "human_bezier_ease"
        }

    # Vetor unitário normal perpendicular ao segmento direto
    nx = -dy / dist
    ny = dx / dist

    if deviation_ratio is None:
        direction = random.choice([-1.0, 1.0])
        dev1 = direction * random.uniform(0.04, 0.13) * dist
        dev2 = direction * random.uniform(0.03, 0.10) * dist
    else:
        dev1 = deviation_ratio * dist
        dev2 = deviation_ratio * 0.75 * dist

    # Pontos de controle P1 e P2 (deslocados a 1/3 e 2/3 com desvio perpendicular orgânico)
    p1_x = x0 + 0.33 * dx + nx * dev1
    p1_y = y0 + 0.33 * dy + ny * dev1

    p2_x = x0 + 0.67 * dx + nx * dev2
    p2_y = y0 + 0.67 * dy + ny * dev2

    waypoints: list[tuple[float, float]] = []
    actual_steps = max(3, num_steps)

    for i in range(1, actual_steps + 1):
        s = i / actual_steps
        t = human_bezier_ease(s)

        # Equação de Bézier Cúbica: B(t) = (1-t)³P0 + 3(1-t)²t P1 + 3(1-t)t² P2 + t³P3
        omt = 1.0 - t
        omt2 = omt * omt
        omt3 = omt2 * omt
        t2 = t * t
        t3 = t2 * t

        bx = omt3 * x0 + 3.0 * omt2 * t * p1_x + 3.0 * omt * t2 * p2_x + t3 * x3
        by = omt3 * y0 + 3.0 * omt2 * t * p1_y + 3.0 * omt * t2 * p2_y + t3 * y3

        # Adiciona micro-jitter neuromuscular nos passos intermediários (nunca no destino exato)
        if i < actual_steps and jitter_magnitude > 0:
            jx = random.uniform(-jitter_magnitude, jitter_magnitude)
            jy = random.uniform(-jitter_magnitude, jitter_magnitude)
            bx += jx
            by += jy
        else:
            bx = x3
            by = y3

        waypoints.append((round(bx, 1), round(by, 1)))

    return {
        "waypoints": waypoints,
        "control_points": [(round(x0, 1), round(y0, 1)), (round(p1_x, 1), round(p1_y, 1)),
                           (round(p2_x, 1), round(p2_y, 1)), (round(x3, 1), round(y3, 1))],
        "distance": round(dist, 1),
        "jitter_magnitude": jitter_magnitude,
        "acceleration_curve": "human_bezier_ease"
    }


def execute_human_click(
    x: int,
    y: int,
    move_duration: float = 0.30,
    press_delay: float = 0.09,
    dry_run: bool = False,
    jitter_px: float = 1.5,
    use_bezier_trajectory: bool = True
) -> dict[str, Any]:
    """Executa o movimento suave de mouse e o clique físico via PyAutoGUI.

    Utiliza pyautogui.moveTo com uma curva de aceleração customizada que simula
    fisicamente a cinemática motora humana (curva Bézier cúbica com micro-jitter neuromuscular),
    evitando detectar padrões robóticos de velocidade constante ou trajetórias retilíneas.
    """
    if pyautogui is None and not dry_run:
        raise ImportError("A biblioteca 'pyautogui' é necessária. Execute pip install pyautogui.")

    started_at = time.perf_counter()

    actual_duration = move_duration + random.uniform(-0.03, 0.05)
    actual_duration = max(0.08, actual_duration)

    actual_press = press_delay + random.uniform(-0.015, 0.025)
    actual_press = max(0.04, actual_press)

    # Identifica o ponto inicial real do cursor ou ponto de partida plausível
    if pyautogui is not None and not dry_run:
        try:
            start_pos = pyautogui.position()
            start_x, start_y = float(start_pos[0]), float(start_pos[1])
        except Exception:
            start_x, start_y = float(x - 160), float(y - 130)
    else:
        start_x, start_y = float(x - 160), float(y - 130)

    trajectory = generate_bezier_trajectory(
        (start_x, start_y),
        (float(x), float(y)),
        num_steps=12,
        jitter_magnitude=jitter_px
    )

    if dry_run:
        return {
            "status": "simulated",
            "target_coordinates": [x, y],
            "move_duration_sec": move_duration,
            "press_delay_sec": press_delay,
            "dry_run": True,
            "acceleration_curve": "human_bezier_ease",
            "trajectory": trajectory
        }

    pyautogui.FAILSAFE = True

    # Executa o deslocamento por pyautogui.moveTo utilizando a curva customizada
    # e waypoints Bézier com jitter para deformar organicamente o percurso
    if use_bezier_trajectory and len(trajectory["waypoints"]) > 1:
        waypoints = trajectory["waypoints"]
        num_wp = len(waypoints)
        step_dur = actual_duration / num_wp
        for wp_x, wp_y in waypoints[:-1]:
            pyautogui.moveTo(int(wp_x), int(wp_y), duration=step_dur, tween=human_bezier_ease)
        last_x, last_y = waypoints[-1]
        pyautogui.moveTo(int(last_x), int(last_y), duration=step_dur, tween=human_bezier_ease)
    else:
        # Fallback direto com a curva customizada human_bezier_ease
        pyautogui.moveTo(x, y, duration=actual_duration, tween=human_bezier_ease)

    time.sleep(random.uniform(0.02, 0.05))

    pyautogui.mouseDown(button="left")
    time.sleep(actual_press)
    pyautogui.mouseUp(button="left")

    elapsed = time.perf_counter() - started_at

    return {
        "status": "clicked",
        "target_coordinates": [x, y],
        "actual_duration_sec": round(actual_duration, 3),
        "actual_press_sec": round(actual_press, 3),
        "total_elapsed_sec": round(elapsed, 3),
        "dry_run": False,
        "acceleration_curve": "human_bezier_ease",
        "trajectory": trajectory
    }


def click_tournament_card(
    tournament: dict[str, Any],
    captured_size: list[int] | tuple[int, int] = (787, 1470),
    dry_run: bool = False,
    mock_window: dict[str, int] | None = None,
    logger: AuditLogger | None = None,
    guardian_check_window: dict[str, Any] | None = None,
    heartbeat: HeartbeatMonitor | None = None,
    speed: str = "natural",
    reaction_delay_range: tuple[float, float] | None = None,
    session_name: str | None = None,
    auto_recovery: bool = False,
    recovery_executable_path: str | Path | None = None,
    ab_variant: str | None = None,
    ab_strategy_name: str | None = None
) -> dict[str, Any]:
    """Fluxo completo do Módulo 4 com auditoria CSV, guardião de janela, heartbeat watchdog e suporte a teste A/B."""
    audit = logger or (heartbeat.logger if heartbeat else AuditLogger())
    t_name = tournament.get("name", "DESCONHECIDO")
    c_index = tournament.get("card_index", "")
    buyin = tournament.get("buyin", "")

    # Checagem de watchdog de inatividade (Heartbeat)
    if heartbeat is not None:
        try:
            heartbeat.assert_healthy()
            heartbeat.beat(f"iniciando_clique_card_{c_index}")
        except SystemHaltError as exc:
            audit.log_event(
                event_type="CLICK_ABORTED",
                status="ABORTED",
                tournament_name=t_name,
                card_index=c_index,
                buyin_chips=buyin,
                details=f"Tentativa de clique abortada: {exc}"
            )
            raise

    # Checagem preliminar de elegibilidade
    if not tournament.get("eligible", False):
        reason = f"Torneio #{c_index} ('{t_name}') inelegível: {tournament.get('rejection_reasons')}"
        audit.log_event(
            event_type="CLICK_ABORTED",
            status="ABORTED",
            tournament_name=t_name,
            card_index=c_index,
            buyin_chips=buyin,
            details=reason
        )
        raise ValueError(reason)

    click_point_local = tournament.get("click_point_local")
    if not click_point_local or len(click_point_local) != 2:
        reason = "Coordenada 'click_point_local' ausente no registro do torneio."
        audit.log_event(
            event_type="CLICK_ABORTED",
            status="ERROR",
            tournament_name=t_name,
            card_index=c_index,
            buyin_chips=buyin,
            details=reason
        )
        raise ValueError(reason)

    # 1. Localização e monitoramento da janela
    try:
        if mock_window:
            win_info = mock_window
        else:
            win_info = find_pppoker_window("pppoker")

        # Monitor de integridade da janela
        WindowIntegrityGuardian.inspect_window(win_info, initial_win=guardian_check_window)

        if win_info.get("window_obj") and hasattr(win_info["window_obj"], "activate"):
            try:
                win_info["window_obj"].activate()
                time.sleep(0.15)
            except Exception:
                pass

    except WindowNotFoundError as exc:
        if auto_recovery:
            try:
                rec_res = attempt_window_recovery(
                    executable_path=recovery_executable_path,
                    logger=audit,
                    session_name=session_name
                )
                win_info = rec_res["window"]
                WindowIntegrityGuardian.inspect_window(win_info, initial_win=guardian_check_window)
            except Exception as rec_exc:
                audit.log_event(
                    event_type="WINDOW_CLOSED",
                    status="ABORTED",
                    session_name=session_name,
                    tournament_name=t_name,
                    card_index=c_index,
                    buyin_chips=buyin,
                    details=f"Recuperação automática falhou: {rec_exc}. Clique cancelado."
                )
                raise
        else:
            audit.log_event(
                event_type="WINDOW_CLOSED",
                status="ABORTED",
                session_name=session_name,
                tournament_name=t_name,
                card_index=c_index,
                buyin_chips=buyin,
                details=f"Tentativa de clique abortada: {exc}"
            )
            raise
    except WindowDrasticChangeError as exc:
        wb = [win_info.get("left", 0), win_info.get("top", 0), win_info.get("width", 0), win_info.get("height", 0)] if "win_info" in locals() else None
        audit.log_event(
            event_type="RESOLUTION_CHANGED",
            status="ABORTED",
            tournament_name=t_name,
            card_index=c_index,
            buyin_chips=buyin,
            win_box=wb,
            details=f"Tentativa de clique abortada: {exc}"
        )
        raise
    except Exception as exc:
        audit.log_event(
            event_type="WINDOW_ERROR",
            status="ERROR",
            tournament_name=t_name,
            card_index=c_index,
            buyin_chips=buyin,
            details=f"Falha de janela: {type(exc).__name__}: {exc}"
        )
        raise

    win_box = [win_info["left"], win_info["top"], win_info["width"], win_info["height"]]

    # 2. Conversão de coordenadas
    try:
        abs_x, abs_y, coord_meta = calculate_absolute_click(
            click_point_local,
            win_info,
            captured_size=captured_size,
            apply_jitter=not dry_run
        )
    except Exception as exc:
        audit.log_event(
            event_type="COORDINATE_ERROR",
            status="ERROR",
            tournament_name=t_name,
            card_index=c_index,
            buyin_chips=buyin,
            win_box=win_box,
            details=f"Erro de coordenadas: {exc}"
        )
        raise

    # 3. Execução do clique com velocidade configurável e atraso aleatório de camuflagem
    speed_key = (speed or "natural").lower()
    if speed_key in ("rapido", "rápido"):
        speed_key = "fast"
    elif speed_key in ("lento",):
        speed_key = "slow"
    profile = CLICK_SPEED_PROFILES.get(speed_key, CLICK_SPEED_PROFILES["natural"])

    delay_range = reaction_delay_range if reaction_delay_range is not None else profile.get("default_reaction_delay")
    reaction_delay_sec = 0.0
    if delay_range and delay_range[1] > 0:
        low, high = max(0.0, delay_range[0]), max(0.0, delay_range[1])
        if high >= low:
            reaction_delay_sec = random.uniform(low, high)
            if not dry_run and reaction_delay_sec > 0:
                time.sleep(reaction_delay_sec)

    # 2.1 Re-calibração dinâmica de escala e coordenadas lidas diretamente da API do PyGetWindow
    if not mock_window:
        try:
            fresh_win = find_pppoker_window("pppoker")
            if fresh_win and (fresh_win.get("width") != win_info.get("width") or fresh_win.get("height") != win_info.get("height") or fresh_win.get("left") != win_info.get("left") or fresh_win.get("top") != win_info.get("top")):
                win_info = fresh_win
                win_box = [win_info["left"], win_info["top"], win_info["width"], win_info["height"]]
                abs_x, abs_y, coord_meta = calculate_absolute_click(
                    click_point_local,
                    win_info,
                    captured_size=captured_size,
                    apply_jitter=not dry_run
                )
        except Exception:
            pass

    t0 = time.perf_counter()
    try:
        click_result = execute_human_click(
            abs_x,
            abs_y,
            move_duration=profile["move_duration"],
            press_delay=profile["press_delay"],
            dry_run=dry_run
        )
        duration_ms = (time.perf_counter() - t0) * 1000.0 + (reaction_delay_sec * 1000.0)

        speed_label = profile["name"]
        prefix = ""
        if ab_variant:
            var_name = ab_strategy_name or f"Variante {ab_variant.upper()}"
            prefix = f"[TESTE_AB: VARIANTE_{ab_variant.upper()} - \"{var_name}\"] "

        details_msg = (
            f"{prefix}Clique despachado ({speed_label}, move={profile['move_duration']*1000:.0f}ms, "
            f"delay_camuflagem={reaction_delay_sec*1000:.0f}ms)"
        )

        audit.log_event(
            event_type="CLICK_SUCCESS" if not dry_run else "CLICK_SIMULATED",
            status="SUCCESS",
            session_name=session_name,
            tournament_name=t_name,
            card_index=c_index,
            buyin_chips=buyin,
            target_abs_x=abs_x,
            target_abs_y=abs_y,
            win_box=win_box,
            duration_ms=duration_ms,
            details=details_msg
        )

        if heartbeat is not None:
            heartbeat.beat(f"clique_concluido_card_{c_index}")

        return {
            "module": "phase1_module4",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "tournament_target": {
                "card_index": c_index,
                "name": t_name,
                "buyin": buyin,
                "start_time": tournament.get("start_time")
            },
            "coordinate_translation": coord_meta,
            "camouflage": {
                "speed_profile": speed_key,
                "move_duration_sec": profile["move_duration"],
                "reaction_delay_sec": round(reaction_delay_sec, 3),
                "ab_variant": ab_variant.upper() if ab_variant else None,
                "ab_strategy_name": ab_strategy_name
            },
            "execution": click_result
        }
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000.0 + (reaction_delay_sec * 1000.0)
        audit.log_event(
            event_type="CLICK_FAILED",
            status="ERROR",
            tournament_name=t_name,
            card_index=c_index,
            buyin_chips=buyin,
            target_abs_x=abs_x,
            target_abs_y=abs_y,
            win_box=win_box,
            duration_ms=duration_ms,
            details=f"Falha física no clique: {exc}"
        )
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Módulo 4: Automação de cliques e conversão de coordenadas.")
    parser.add_argument("--tournaments", type=Path, default=None, help="Caminho para tournaments.json gerado pelo Módulo 3.")
    parser.add_argument("--card-index", type=int, default=None, help="Índice do cartão a clicar (padrão: primeiro elegível).")
    parser.add_argument("--speed", choices=["fast", "natural", "slow", "rapido", "lento"], default="natural", help="Velocidade do clique e movimento (padrão: natural).")
    parser.add_argument("--reaction-delay-min", type=float, default=None, help="Atraso cognitivo/camuflagem mínimo em segundos antes de mover o mouse.")
    parser.add_argument("--reaction-delay-max", type=float, default=None, help="Atraso cognitivo/camuflagem máximo em segundos antes de mover o mouse.")
    parser.add_argument("--dry-run", action="store_true", help="Apenas simula o cálculo sem mover o mouse físico.")
    parser.add_argument("--mock-window", action="store_true", help="Utiliza janela simulada (787x1470) para execução em ambientes headless/Linux sem interface gráfica.")
    parser.add_argument("--session-name", type=str, default="Sessão Principal", help="Identificador da Sessão de Jogo para agrupamento no CSV (ex: 'Sessão Matinal 01').")
    parser.add_argument("--auto-recovery", action="store_true", help="Ativa o Modo de Recuperação automática para reabrir o PPPoker caso a janela esteja fechada.")
    parser.add_argument("--pppoker-exe", type=Path, default=None, help="Caminho do executável do PPPoker para o Modo de Recuperação (padrão: C:\\Program Files (x86)\\PPPoker\\PPPoker.exe).")
    parser.add_argument("--ab-test", action="store_true", help="Executa bateria de teste A/B para estratégias de camuflagem alternadas.")
    parser.add_argument("--ab-count", type=int, default=10, help="Quantidade de cliques a executar no teste A/B alternado (padrão: 10).")
    parser.add_argument("--ab-a-name", type=str, default="Variante A (Furtiva)", help="Nome da estratégia A para o teste A/B.")
    parser.add_argument("--ab-a-speed", choices=["fast", "natural", "slow", "rapido", "lento"], default="natural", help="Velocidade da Variante A.")
    parser.add_argument("--ab-a-delay-min", type=float, default=0.35, help="Delay mínimo em segundos da Variante A.")
    parser.add_argument("--ab-a-delay-max", type=float, default=0.75, help="Delay máximo em segundos da Variante A.")
    parser.add_argument("--ab-b-name", type=str, default="Variante B (Agressiva)", help="Nome da estratégia B para o teste A/B.")
    parser.add_argument("--ab-b-speed", choices=["fast", "natural", "slow", "rapido", "lento"], default="fast", help="Velocidade da Variante B.")
    parser.add_argument("--ab-b-delay-min", type=float, default=0.10, help="Delay mínimo em segundos da Variante B.")
    parser.add_argument("--ab-b-delay-max", type=float, default=0.25, help="Delay máximo em segundos da Variante B.")
    parser.add_argument("--output", type=Path, default=None, help="Arquivo opcional para salvar o recibo do clique.")
    parser.add_argument("--logs-dir", type=Path, default=Path("logs"), help="Pasta para gravação dos logs de auditoria CSV.")
    parser.add_argument("--heartbeat-timeout", type=float, default=30.0, help="Tempo máximo de inatividade em segundos antes de disparar SYSTEM_HALT (padrão 30.0s).")
    parser.add_argument("--webhook-url", type=str, default=None, help="URL de webhook (Discord, Telegram, Zapier/Make) para alertas remotos de escalada caso SYSTEM_HALT persista por > 5 min.")
    parser.add_argument("--escalation-timeout", type=float, default=300.0, help="Tempo em segundos em SYSTEM_HALT antes de disparar alerta remoto (padrão 300.0s = 5 minutos).")
    parser.add_argument("--test-webhook", action="store_true", help="Dispara uma notificação remota de teste imediata para verificar a URL do webhook e encerra.")
    args = parser.parse_args(argv)

    if args.test_webhook:
        notifier = EscalationNotifier(default_webhook_url=args.webhook_url)
        print(f"Disparando notificação de teste para: {mask_webhook_url(args.webhook_url)}...")
        res = notifier.send_escalation(
            title="🔔 [TESTE OPERACIONAL] Webhook VisualPilot",
            details="Disparo manual de teste de conectividade de notificação remota do Módulo 4.",
            elapsed_seconds=300.0,
            webhook_url=args.webhook_url
        )
        print("Resultado do envio:")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["success"] else 1

    if not args.tournaments:
        print("Erro: --tournaments é obrigatório quando não estiver usando --test-webhook.", file=sys.stderr)
        return 1

    logger = AuditLogger(logs_dir=args.logs_dir, default_session_name=args.session_name)
    watchdog = HeartbeatMonitor(
        logger=logger,
        timeout_seconds=args.heartbeat_timeout,
        escalation_timeout_seconds=args.escalation_timeout,
        webhook_url=args.webhook_url,
        auto_start=True
    )

    try:
        data = json.loads(args.tournaments.read_text(encoding="utf-8"))
        tournaments = data.get("tournaments", [])

        target = None
        if args.card_index is not None:
            target = next((t for t in tournaments if t.get("card_index") == args.card_index), None)
            if not target:
                print(f"Erro: Cartão #{args.card_index} não encontrado no arquivo.", file=sys.stderr)
                return 1
        else:
            target = next((t for t in tournaments if t.get("eligible")), None)
            if not target:
                print("Nenhum torneio elegível encontrado em tournaments.json.", file=sys.stderr)
                return 1

        mock_win = None
        if args.mock_window or (args.dry_run and gw is None):
            mock_win = {
                "title": "PPPoker - Club Lobby (Simulado)",
                "left": 500,
                "top": 150,
                "width": 787,
                "height": 1470,
                "is_active": True
            }

        # Modo Teste A/B
        if args.ab_test:
            print(f"=== INICIANDO BATERIA DE TESTE A/B DE CAMUFLAGEM ({args.ab_count} CLIQUES) ===")
            print(f"  Variante A: '{args.ab_a_name}' | Velocidade: {args.ab_a_speed} | Delay: {args.ab_a_delay_min}s-{args.ab_a_delay_max}s")
            print(f"  Variante B: '{args.ab_b_name}' | Velocidade: {args.ab_b_speed} | Delay: {args.ab_b_delay_min}s-{args.ab_b_delay_max}s")
            print(f"  Sessão: {args.session_name}")
            print(f"  Arquivo CSV de Auditoria: {logger.get_current_log_path()}")
            print("-" * 75)

            latencies_a: list[float] = []
            latencies_b: list[float] = []
            reports: list[dict[str, Any]] = []

            for i in range(args.ab_count):
                variant = "A" if i % 2 == 0 else "B"
                if variant == "A":
                    var_name = args.ab_a_name
                    var_speed = args.ab_a_speed
                    var_dmin, var_dmax = args.ab_a_delay_min, args.ab_a_delay_max
                else:
                    var_name = args.ab_b_name
                    var_speed = args.ab_b_speed
                    var_dmin, var_dmax = args.ab_b_delay_min, args.ab_b_delay_max

                rep = click_tournament_card(
                    target,
                    dry_run=args.dry_run,
                    mock_window=mock_win,
                    logger=logger,
                    heartbeat=watchdog,
                    speed=var_speed,
                    reaction_delay_range=(var_dmin, var_dmax),
                    session_name=args.session_name,
                    auto_recovery=args.auto_recovery,
                    recovery_executable_path=args.pppoker_exe,
                    ab_variant=variant,
                    ab_strategy_name=var_name
                )
                reports.append(rep)
                # Estimar ou calcular tempo
                dur = rep.get("execution", {}).get("total_elapsed_sec", 0.0) * 1000.0 + (rep["camouflage"]["reaction_delay_sec"] * 1000.0)
                if variant == "A":
                    latencies_a.append(dur)
                else:
                    latencies_b.append(dur)

                print(f"  [Clique {i+1:02d}/{args.ab_count:02d}] Variante {variant} ({var_name}): {dur:.1f}ms | {rep['execution']['status']}")

            avg_a = sum(latencies_a) / max(1, len(latencies_a))
            avg_b = sum(latencies_b) / max(1, len(latencies_b))

            print("-" * 75)
            print("=== RELATÓRIO ANALÍTICO COMPARATIVO DO TESTE A/B ===")
            print(f"  Variante A ({args.ab_a_name}): {len(latencies_a)} amostras | Média: {avg_a:.1f}ms | Faixa: {min(latencies_a):.1f}..{max(latencies_a):.1f}ms")
            print(f"  Variante B ({args.ab_b_name}): {len(latencies_b)} amostras | Média: {avg_b:.1f}ms | Faixa: {min(latencies_b):.1f}..{max(latencies_b):.1f}ms")
            diff = abs(avg_a - avg_b)
            if avg_a > avg_b:
                print(f"  Veredito: Variante B é mais rápida em média por {diff:.1f}ms (maior agilidade no lobby).")
                print(f"            Variante A oferece maior proteção anti-detecção com latência cognitiva expandida.")
            else:
                print(f"  Veredito: Variante A é mais rápida em média por {diff:.1f}ms.")
            print(f"  Todos os registros foram salvos em: {logger.get_current_log_path()}")

            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps({"ab_test": True, "count": args.ab_count, "results": reports}, ensure_ascii=False, indent=2), encoding="utf-8")

            return 0

        # Modo Normal (Clique único)
        delay_range = None
        if args.reaction_delay_min is not None and args.reaction_delay_max is not None:
            delay_range = (args.reaction_delay_min, args.reaction_delay_max)

        report = click_tournament_card(
            target,
            dry_run=args.dry_run,
            mock_window=mock_win,
            logger=logger,
            heartbeat=watchdog,
            speed=args.speed,
            reaction_delay_range=delay_range,
            session_name=args.session_name,
            auto_recovery=args.auto_recovery,
            recovery_executable_path=args.pppoker_exe
        )

        print("Ação despachada com sucesso:")
        print(f"  Coordenada relativa local: {report['coordinate_translation']['local_point']}")
        print(f"  Janela PPPoker localizada em: {report['coordinate_translation']['window_box']}")
        print(f"  Coordenada absoluta de clique: {report['execution']['target_coordinates']}")
        print(f"  Modo de execução: {report['execution']['status']}")
        print(f"  Log registrado em: {logger.get_current_log_path()}")

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  Recibo salvo em: {args.output}")

        return 0
    except Exception as exc:
        print(f"Erro no despacho do clique: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        watchdog.stop()


if __name__ == "__main__":
    raise SystemExit(main())
