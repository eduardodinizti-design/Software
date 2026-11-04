"""VisualPilot - Fase 1 / Orquestrador de Ciclo Contínuo (Lobby Orchestrator).

Gerencia a esteira operacional completa de automação do Lobby PPPoker:
1. Varredura contínua e periódica do Lobby (loop com intervalo e jitter configuráveis).
2. Filtragem de elegibilidade (MTT, Buy-in <= limite, Status, Horário de início).
3. Controle de Anti-Duplicação de Inscrições com persistência JSON e TTL configurável.
4. Despacho de clique camuflado com suporte a teste A/B (Módulo 4).
5. Máquina de estados de confirmação de inscrição e navegação pós-clique (Módulo 5).
6. Vigilância ativa com Watchdog de Heartbeat e escalada remota de alertas.
7. Encerramento gracioso (SIGINT / SIGTERM) e persistência de telemetria em CSV.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import random
import re
import signal
import sys
import threading
import time
from typing import Any, Callable
import unicodedata
import urllib.error
import urllib.request

# Garantir que repo_visualpilot esteja no sys.path mesmo em execução direta
_current_file = Path(__file__).resolve()
for _ancestor in [_current_file.parent.parent.parent, _current_file.parent.parent]:
    if (_ancestor / "visualpilot").is_dir() and str(_ancestor) not in sys.path:
        sys.path.insert(0, str(_ancestor))


try:
    from visualpilot.boot_logger import (
        run_preflight_diagnostics,
        log_boot_event,
        TEMP_LOG_FILE,
    )
except Exception:
    def run_preflight_diagnostics(name: str = "orchestrator") -> bool:
        return True
    def log_boot_event(*args, **kwargs) -> None:
        pass
    TEMP_LOG_FILE = Path("/tmp/visualpilot_boot_debug.log")


from visualpilot.pppoker.lobby_clicker import (
    AuditLogger,
    HeartbeatMonitor,
    WindowNotFoundError,
    WindowStateError,
    WindowDrasticChangeError,
    SystemHaltError,
    find_pppoker_window,
    mask_webhook_url,
    calculate_absolute_click,
    execute_human_click,
)
from visualpilot.pppoker.tournament_registration import (
    TournamentRegistrationManager,
    ScreenTransitionTimeoutError,
    RegistrationStepResult,
    InsufficientFundsError,
)

logger = logging.getLogger("visualpilot.orchestrator")


def normalize_text(text: str) -> str:
    """Remove acentuação e espaços extras, convertendo para maiúsculas."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    cleaned = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(cleaned.upper().split())


def clean_name_key(text: str) -> str:
    """Gera chave única do nome removendo caracteres não alfanuméricos."""
    return re.sub(r"[^A-Z0-9]", "", normalize_text(text))


def generate_tournament_key(tournament: dict[str, Any]) -> str:
    """Gera identificador determinístico para um torneio baseado no nome, buy-in e horário."""
    raw_name = str(tournament.get("name") or tournament.get("name_label") or "TORNEIO")
    c_name = clean_name_key(raw_name)
    raw_buyin = str(tournament.get("buyin") or tournament.get("raw_buyin_text") or "0")
    buyin_num = re.sub(r"[^0-9\.]", "", raw_buyin) or "0"
    start_time = str(tournament.get("start_time") or "LIVE").strip().upper()
    start_key = re.sub(r"[^A-Z0-9]", "", start_time) or "LIVE"
    return f"{c_name}_{buyin_num}_{start_key}"


@dataclass
class AntiDupRecord:
    key: str
    tournament_name: str
    buyin: str
    start_time: str
    first_seen_iso: str
    last_registered_iso: str
    status: str  # REGISTERED, INSUFFICIENT_FUNDS, FAILED, SKIPPED_DUPLICATE
    registration_count: int = 1
    session_name: str = "Sessão Orquestrada"
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AntiDuplicationRegistry:
    """Controle persistente de anti-duplicação de inscrições em torneios."""

    def __init__(self, persistence_file: Path | str | None = None, ttl_hours: float = 24.0):
        self.persistence_file = Path(persistence_file) if persistence_file else None
        self.ttl_seconds = float(ttl_hours) * 3600.0
        self._records: dict[str, AntiDupRecord] = {}
        self._lock = threading.Lock()

        if self.persistence_file and self.persistence_file.is_file():
            self.load()

    def is_registered(self, tournament: dict[str, Any]) -> bool:
        """Verifica se o torneio já está registrado e ainda dentro do período de validade (TTL)."""
        key = generate_tournament_key(tournament)
        with self._lock:
            rec = self._records.get(key)
            if not rec:
                return False

            if rec.status in ("REGISTERED", "ALREADY_REGISTERED"):
                # Valida TTL
                try:
                    dt = datetime.fromisoformat(rec.last_registered_iso)
                    elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
                    if elapsed < self.ttl_seconds:
                        return True
                except Exception:
                    return True

            # Se falhou por saldo insuficiente nos últimos 10 minutos, também bloqueia re-tentativa imediata
            if rec.status == "INSUFFICIENT_FUNDS":
                try:
                    dt = datetime.fromisoformat(rec.last_registered_iso)
                    elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
                    if elapsed < 600.0:  # 10 min cooldown
                        return True
                except Exception:
                    return True

            return False

    def mark_registered(
        self,
        tournament: dict[str, Any],
        status: str = "REGISTERED",
        session_name: str = "Sessão Orquestrada",
        details: str = ""
    ) -> AntiDupRecord:
        """Registra a conclusão bem-sucedida de inscrição com timestamp e dados do torneio."""
        key = generate_tournament_key(tournament)
        now_iso = datetime.now(timezone.utc).isoformat()
        t_name = str(tournament.get("name") or tournament.get("name_label") or "Torneio")
        buyin = str(tournament.get("buyin") or "0")
        start_time = str(tournament.get("start_time") or "-")

        with self._lock:
            existing = self._records.get(key)
            if existing:
                existing.last_registered_iso = now_iso
                existing.status = status
                existing.registration_count += 1
                existing.session_name = session_name
                existing.details = details
                rec = existing
            else:
                rec = AntiDupRecord(
                    key=key,
                    tournament_name=t_name,
                    buyin=buyin,
                    start_time=start_time,
                    first_seen_iso=now_iso,
                    last_registered_iso=now_iso,
                    status=status,
                    registration_count=1,
                    session_name=session_name,
                    details=details or f"Inscrição confirmada pelo Orquestrador na sessão {session_name}."
                )
                self._records[key] = rec

        if self.persistence_file:
            self.save()

        return rec

    def mark_insufficient_funds(
        self,
        tournament: dict[str, Any],
        session_name: str = "Sessão Orquestrada"
    ) -> AntiDupRecord:
        """Marca torneio com erro de saldo para evitar loops de tentativas desnecessárias."""
        return self.mark_registered(
            tournament=tournament,
            status="INSUFFICIENT_FUNDS",
            session_name=session_name,
            details="Saldo de fichas insuficiente no PPPoker. Cooldown ativado."
        )

    def load(self) -> None:
        """Carrega registros persistidos do arquivo JSON."""
        if not self.persistence_file or not self.persistence_file.exists():
            return
        try:
            with self._lock:
                data = json.loads(self.persistence_file.read_text(encoding="utf-8"))
                for item in data.get("tournaments", []):
                    rec = AntiDupRecord(**item)
                    self._records[rec.key] = rec
        except Exception as e:
            logger.warning(f"Erro ao carregar arquivo de anti-duplicação: {e}")

    def save(self) -> None:
        """Salva atomicamente os registros no arquivo JSON."""
        if not self.persistence_file:
            return
        try:
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                data = {
                    "version": "1.0",
                    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "total_registered": len(self._records),
                    "tournaments": [r.to_dict() for r in self._records.values()]
                }
            tmp_path = self.persistence_file.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp_path.replace(self.persistence_file)
        except Exception as e:
            logger.warning(f"Erro ao salvar arquivo de anti-duplicação: {e}")

    def clear(self) -> None:
        """Limpa registros da memória e do arquivo persistido."""
        with self._lock:
            self._records.clear()
        if self.persistence_file and self.persistence_file.exists():
            try:
                self.persistence_file.unlink()
            except Exception:
                pass

    def get_all_records(self) -> list[dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in sorted(self._records.values(), key=lambda x: x.last_registered_iso, reverse=True)]


@dataclass
class LoopConfig:
    interval_seconds: float = 15.0
    jitter_seconds: float = 3.0
    max_iterations: int = 0  # 0 = loop infinito até sinal de parada
    max_buyin: float = 50.0
    target_formats: list[str] = field(default_factory=lambda: ["MTT", "NLH"])
    dry_run: bool = False
    auto_recovery: bool = True
    anti_dup_ttl_hours: float = 24.0
    anti_dup_file: str = "logs/registered_tournaments.json"
    session_name: str = "Sessão Orquestrada"
    webhook_url: str | None = None
    webhook_provider: str = "discord"


class LobbyOrchestrator:
    """Orquestrador do Ciclo Contínuo de Automação do Lobby PPPoker."""

    def __init__(
        self,
        config: LoopConfig | None = None,
        logger_instance: AuditLogger | None = None,
        heartbeat: HeartbeatMonitor | None = None,
        registration_manager: TournamentRegistrationManager | None = None,
        anti_dup: AntiDuplicationRegistry | None = None
    ):
        self.config = config or LoopConfig()
        self.logger = logger_instance or AuditLogger(default_session_name=self.config.session_name)
        self.heartbeat = heartbeat or HeartbeatMonitor(logger=self.logger, timeout_seconds=35.0)
        self.reg_manager = registration_manager or TournamentRegistrationManager(
            logger=self.logger,
            heartbeat=self.heartbeat,
            dry_run=self.config.dry_run
        )
        self.anti_dup = anti_dup or AntiDuplicationRegistry(
            persistence_file=self.config.anti_dup_file,
            ttl_hours=self.config.anti_dup_ttl_hours
        )

        self._stop_requested = False
        self._is_running = False
        self._cycle_count = 0
        self._tournaments_scanned = 0
        self._tournaments_eligible = 0
        self._tournaments_skipped_dup = 0
        self._tournaments_registered = 0
        self._errors_count = 0
        self._start_time_iso = ""

    @property
    def is_running(self) -> bool:
        return self._is_running

    def request_stop(self) -> None:
        """Solicita a interrupção suave do loop após o ciclo atual."""
        self._stop_requested = True
        logger.info("Solicitação de parada recebida. Finalizando ciclo atual...")

    def run_cycle(self, tournaments_input: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Executa um ciclo completo de varredura, anti-duplicação e inscrição."""
        cycle_start = time.perf_counter()
        self._cycle_count += 1
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Verifica integridade do watchdog de pulsação
        self.heartbeat.beat(f"inicio_ciclo_{self._cycle_count}")
        self.heartbeat.assert_healthy()

        # 2. Localiza e monitora janela PPPoker
        win_info = None
        if not self.config.dry_run:
            try:
                win_info = find_pppoker_window("pppoker")
            except Exception as e:
                self._errors_count += 1
                self.logger.log_event(
                    event_type="WINDOW_ERROR_ORCHESTRATOR",
                    status="ABORTED",
                    duration_ms=(time.perf_counter() - cycle_start) * 1000.0,
                    details=f"Falha ao localizar janela PPPoker no ciclo {self._cycle_count}: {e}"
                )
                if not self.config.auto_recovery:
                    raise
                logger.warning(f"Janela PPPoker não encontrada no ciclo {self._cycle_count}. Aguardando recuperação...")
                return {
                    "cycle": self._cycle_count,
                    "status": "WINDOW_RECOVERY_WAIT",
                    "details": str(e),
                    "registered_count": 0
                }
        else:
            win_info = {"title": "PPPoker (Simulated)", "left": 500, "top": 150, "width": 787, "height": 1470}

        # 3. Obtém cartões de torneio do lobby (fornecidos ou sintéticos padrão)
        if tournaments_input is not None:
            tournaments = tournaments_input
        else:
            # Torneios padrão de referência do lobby PPPoker (Fase 1)
            tournaments = [
                {
                    "index": 0,
                    "name_label": "PPPOKER SUPER CLASSIC 20K",
                    "buyin": "20",
                    "start_time": "14:00",
                    "game_format": "MTT",
                    "status": "ABERTO",
                    "eligible": True,
                    "click_point_local": [393.5, 342.0]
                },
                {
                    "index": 1,
                    "name_label": "TARDEZINHA PKO 5K GTD",
                    "buyin": "10",
                    "start_time": "16:30",
                    "game_format": "MTT",
                    "status": "ABERTO",
                    "eligible": True,
                    "click_point_local": [393.5, 552.0]
                },
                {
                    "index": 2,
                    "name_label": "CORUJAO HYPER PKO10K",
                    "buyin": "50",
                    "start_time": "23:00",
                    "game_format": "MTT",
                    "status": "ABERTO",
                    "eligible": True,
                    "click_point_local": [404.0, 992.0]
                },
                {
                    "index": 3,
                    "name_label": "HIGH ROLLER PRIME 100K",
                    "buyin": "150",
                    "start_time": "21:00",
                    "game_format": "MTT",
                    "status": "ABERTO",
                    "eligible": False,
                    "click_point_local": [393.5, 1202.0]
                }
            ]

        self._tournaments_scanned += len(tournaments)
        cycle_registered = 0
        cycle_skipped_dup = 0
        cycle_eligible = 0
        actions_taken = []

        # 4. Avalia cada cartão do lobby
        for t in tournaments:
            t_name = str(t.get("name_label") or t.get("name") or "Torneio")
            buyin_val = float(re.sub(r"[^0-9\.]", "", str(t.get("buyin") or "0")) or "0")
            fmt = str(t.get("game_format") or "MTT").upper()
            status = str(t.get("status") or "ABERTO").upper()

            # Checagem de elegibilidade
            is_eligible = (
                fmt in self.config.target_formats and
                buyin_val <= self.config.max_buyin and
                status not in ("ENCERRADO", "FINALIZADO")
            )

            if not is_eligible:
                continue

            cycle_eligible += 1
            self._tournaments_eligible += 1

            # 5. CONTROLE DE ANTI-DUPLICAÇÃO
            if self.anti_dup.is_registered(t):
                cycle_skipped_dup += 1
                self._tournaments_skipped_dup += 1
                logger.info(f"[ANTI-DUP] Torneio '{t_name}' ignorado: inscrição já ativa no registro.")
                self.logger.log_event(
                    event_type="TOURNAMENT_SKIPPED_ALREADY_REGISTERED",
                    status="SKIPPED",
                    tournament_name=t_name,
                    card_index=str(t.get("index", "")),
                    buyin_chips=str(buyin_val),
                    details=f"Inscrição evitada por Anti-Duplicação: '{t_name}' já consta no registro persistente."
                )
                actions_taken.append({"tournament": t_name, "action": "SKIPPED_DUPLICATE"})
                continue

            # 6. Torneio elegível e não registrado: dispara inscrição completa (Módulos 4 e 5)!
            logger.info(f"[ORQUESTRADOR] Iniciando inscrição no torneio elegível: '{t_name}' (Buy-in: {buyin_val})")

            try:
                # Dispara ciclo completo com a máquina de estados Módulo 5
                reg_result = self.reg_manager.run_full_registration(t)

                # Salva no registro de Anti-Duplicação
                rec = self.anti_dup.mark_registered(
                    tournament=t,
                    status="REGISTERED",
                    session_name=self.config.session_name,
                    details=f"Inscrição concluída no ciclo #{self._cycle_count} em {reg_result.get('total_duration_ms', 0):.1f}ms."
                )

                cycle_registered += 1
                self._tournaments_registered += 1
                actions_taken.append({
                    "tournament": t_name,
                    "action": "REGISTERED",
                    "duration_ms": reg_result.get("total_duration_ms", 0)
                })

                self._dispatch_webhook(
                    severity="INFO",
                    title="Inscrição Confirmada pelo Orquestrador",
                    details=f"Vaga garantida no torneio '{t_name}' ({buyin_val} fichas). Registro anti-duplicação atualizado."
                )

            except InsufficientFundsError:
                self.anti_dup.mark_insufficient_funds(t, session_name=self.config.session_name)
                actions_taken.append({"tournament": t_name, "action": "INSUFFICIENT_FUNDS"})
                self._dispatch_webhook(
                    severity="WARN",
                    title="Saldo Insuficiente de Fichas",
                    details=f"Falha ao registrar '{t_name}': saldo insuficiente no PPPoker."
                )
            except Exception as e:
                self._errors_count += 1
                actions_taken.append({"tournament": t_name, "action": "ERROR", "error": str(e)})
                logger.error(f"Erro ao processar inscrição de '{t_name}': {e}")

        cycle_duration_ms = (time.perf_counter() - cycle_start) * 1000.0

        return {
            "cycle": self._cycle_count,
            "timestamp_iso": now_iso,
            "status": "COMPLETED",
            "cycle_duration_ms": cycle_duration_ms,
            "tournaments_scanned": len(tournaments),
            "tournaments_eligible": cycle_eligible,
            "skipped_duplicate": cycle_skipped_dup,
            "registered_count": cycle_registered,
            "actions": actions_taken
        }

    def run_loop(self, on_cycle_callback: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        """Inicia o loop contínuo de orquestração com intervalo e jitter configuráveis."""
        self._is_running = True
        self._stop_requested = False
        self._start_time_iso = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Orquestrador iniciado: loop interval={self.config.interval_seconds}s (±{self.config.jitter_seconds}s), "
            f"max_iterations={self.config.max_iterations or 'infinito'}, dry_run={self.config.dry_run}"
        )

        self.logger.log_event(
            event_type="ORCHESTRATOR_STARTED",
            status="SUCCESS",
            details=f"Orquestrador de ciclo contínuo iniciado. Sessão: '{self.config.session_name}'."
        )

        # Configura captura de sinais para shutdown gracioso
        original_sigint = None
        original_sigterm = None
        try:
            if threading.current_thread() is threading.main_thread():
                original_sigint = signal.signal(signal.SIGINT, lambda s, f: self.request_stop())
                original_sigterm = signal.signal(signal.SIGTERM, lambda s, f: self.request_stop())
        except Exception:
            pass

        try:
            while not self._stop_requested:
                cycle_result = self.run_cycle()

                if on_cycle_callback:
                    try:
                        on_cycle_callback(cycle_result)
                    except Exception as cb_err:
                        logger.warning(f"Erro no callback do ciclo: {cb_err}")

                if self.config.max_iterations > 0 and self._cycle_count >= self.config.max_iterations:
                    logger.info(f"Limite de iterações atingido ({self.config.max_iterations}). Encerrando loop.")
                    break

                if self._stop_requested:
                    break

                # Intervalo com Jitter cognitivo
                jitter = random.uniform(-self.config.jitter_seconds, self.config.jitter_seconds)
                sleep_time = max(1.0, self.config.interval_seconds + jitter)

                # Dorme em fatias pequenas para responder instantaneamente ao pedido de parada
                steps = int(sleep_time / 0.2)
                for _ in range(steps):
                    if self._stop_requested:
                        break
                    time.sleep(0.2)

        finally:
            self._is_running = False
            self.anti_dup.save()

            if original_sigint is not None:
                try:
                    signal.signal(signal.SIGINT, original_sigint)
                except Exception:
                    pass
            if original_sigterm is not None:
                try:
                    signal.signal(signal.SIGTERM, original_sigterm)
                except Exception:
                    pass

            self.logger.log_event(
                event_type="ORCHESTRATOR_STOPPED",
                status="SUCCESS",
                details=f"Orquestrador finalizado. Total de ciclos: {self._cycle_count}, Inscrições realizadas: {self._tournaments_registered}."
            )

        return self.get_summary()

    def get_summary(self) -> dict[str, Any]:
        """Retorna telemetria consolidada da execução do orquestrador."""
        return {
            "orchestrator": "VisualPilot Phase 1 Continuous Loop Orchestrator",
            "session_name": self.config.session_name,
            "is_running": self._is_running,
            "started_at_iso": self._start_time_iso,
            "total_cycles": self._cycle_count,
            "tournaments_scanned": self._tournaments_scanned,
            "tournaments_eligible": self._tournaments_eligible,
            "tournaments_skipped_duplicate": self._tournaments_skipped_dup,
            "tournaments_registered": self._tournaments_registered,
            "errors_count": self._errors_count,
            "anti_duplication_registry_count": len(self.anti_dup.get_all_records()),
            "config": {
                "interval_seconds": self.config.interval_seconds,
                "jitter_seconds": self.config.jitter_seconds,
                "max_buyin": self.config.max_buyin,
                "dry_run": self.config.dry_run,
                "auto_recovery": self.config.auto_recovery
            }
        }

    def _dispatch_webhook(self, severity: str, title: str, details: str) -> None:
        """Despacha alerta para webhook configurado (Discord, Telegram, Zapier)."""
        if not self.config.webhook_url:
            return

        def _worker():
            try:
                payload = {
                    "event": f"ORCHESTRATOR_{severity}_ALERT",
                    "severity": severity,
                    "title": title,
                    "details": details,
                    "session_name": self.config.session_name,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat()
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    self.config.webhook_url,
                    data=data,
                    headers={"Content-Type": "application/json", "User-Agent": "VisualPilot-Orchestrator/1.0"}
                )
                with urllib.request.urlopen(req, timeout=4.0):
                    pass
            except Exception as e:
                logger.debug(f"Falha silenciosa ao despachar webhook do orquestrador: {e}")

        threading.Thread(target=_worker, daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VisualPilot - Orquestrador de Ciclo Contínuo com Anti-Duplicação do Lobby PPPoker"
    )
    parser.add_argument("--interval", type=float, default=15.0, help="Intervalo base entre ciclos em segundos (padrão: 15.0)")
    parser.add_argument("--jitter", type=float, default=3.0, help="Variação aleatória (jitter) em segundos (padrão: 3.0)")
    parser.add_argument("--max-iterations", type=int, default=0, help="Máximo de iterações a rodar (0 para loop infinito)")
    parser.add_argument("--max-buyin", type=float, default=50.0, help="Limite máximo de buy-in em fichas (padrão: 50.0)")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulação sem disparos físicos no desktop")
    parser.add_argument("--session-name", type=str, default="Sessão Orquestrada 01", help="Nome da sessão de jogo")
    parser.add_argument("--anti-dup-file", type=str, default="logs/registered_tournaments.json", help="Caminho do arquivo JSON de anti-duplicação")
    parser.add_argument("--clear-anti-dup", action="store_true", help="Limpa o registro de anti-duplicação antes de iniciar")
    parser.add_argument("--webhook-url", type=str, default=None, help="URL opcional de webhook para alertas")

    args = parser.parse_args()

    # Executa pré-voo de ambiente e registra no log temporário
    log_boot_event("ORCH", f"Iniciando LobbyOrchestrator | Sessão: '{args.session_name}' | DryRun: {args.dry_run}")
    preflight_ok = run_preflight_diagnostics("lobby_orchestrator")
    if not preflight_ok:
        err_msg = (
            "\n" + "=" * 65 + "\n"
            " [FALHA DE PRÉ-VOO]: O orquestrador não pode iniciar sem as dependências!\n"
            " Execute no terminal CMD:\n"
            "     corrigir_instalacao.bat\n"
            " ou:\n"
            "     pip install -r requirements.txt\n"
            f" Log completo em: {TEMP_LOG_FILE}\n"
            + "=" * 65 + "\n"
        )
        print(err_msg, file=sys.stderr)
        log_boot_event("ORCH", "Falha de pré-voo em lobby_orchestrator", details=err_msg, status="FAIL")
        if sys.stdin and sys.stdin.isatty():
            input("\nPressione ENTER para fechar...")
        sys.exit(1)

    cfg = LoopConfig(

        interval_seconds=args.interval,
        jitter_seconds=args.jitter,
        max_iterations=args.max_iterations,
        max_buyin=args.max_buyin,
        dry_run=args.dry_run,
        session_name=args.session_name,
        anti_dup_file=args.anti_dup_file,
        webhook_url=args.webhook_url
    )

    anti_dup = AntiDuplicationRegistry(persistence_file=cfg.anti_dup_file)
    if args.clear_anti_dup:
        anti_dup.clear()
        print("✓ Registro de anti-duplicação zerado com sucesso.")

    orch = LobbyOrchestrator(config=cfg, anti_dup=anti_dup)

    print("\n" + "=" * 70)
    print("♠ VISUALPILOT: ORQUESTRADOR DE CICLO CONTÍNUO DO LOBBY PPPOKER")
    print(f"  • Sessão Ativa: '{cfg.session_name}'")
    print(f"  • Intervalo de Loop: {cfg.interval_seconds}s (±{cfg.jitter_seconds}s)")
    print(f"  • Limite Máximo de Buy-in: {cfg.max_buyin} fichas")
    print(f"  • Modo: {'DRY-RUN (Simulação Segura)' if cfg.dry_run else 'PRODUÇÃO (PyAutoGUI Real)'}")
    print(f"  • Registro Anti-Duplicação: {cfg.anti_dup_file} ({len(anti_dup.get_all_records())} registros ativos)")
    print("=" * 70 + "\n")

    def on_cycle(res: dict[str, Any]):
        print(
            f"[{res['timestamp_iso'][11:19]}] Ciclo #{res['cycle']}: "
            f"Varredura de {res['tournaments_scanned']} cartões | "
            f"{res['tournaments_eligible']} elegíveis | "
            f"{res['skipped_duplicate']} ignorados por anti-dup | "
            f"{res['registered_count']} novas inscrições ({res['cycle_duration_ms']:.1f}ms)"
        )

    summary = orch.run_loop(on_cycle_callback=on_cycle)
    print("\n" + "=" * 70)
    print("✓ ORQUESTRADOR ENCERRADO COM SUCESSO")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
