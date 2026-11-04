#!/usr/bin/env python3
"""
VisualPilot - Servidor Central de Telemetria, Ponte Web e Servidor Estático (telemetry_server.py).
Segurança reforçada:
- Escuta em 127.0.0.1 por padrão (localhost).
- Bloqueio estrito de travessia de diretório (Path Traversal / fora de dist/), prevenindo ../, encoded paths e symlinks.
- Limite estrito de tamanho de requisição (máx 1 MB).
- Registro de falhas e auditoria de requisições.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
TELEMETRY_JSON = LOGS_DIR / "telemetry.json"
TAKEOVER_FLAG = LOGS_DIR / "takeover_paused.flag"
DIST_DIR = (BASE_DIR / "dist").resolve()
SERVER_LOG = LOGS_DIR / "server_error.log"

MAX_BODY_SIZE = 1_048_576  # 1 MB

IN_MEMORY_STATE = {
    "status": "ONLINE",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "hand_counter": 0,
    "table_title": "PPPoker",
    "is_hero_turn": False,
    "hero_cards": [],
    "board_cards": [],
    "pot_bb": None,
    "stack_bb": None,
    "hero_position": "BTN",
    "recommended_action": "AGUARDANDO_ROBÔ",
    "recommended_sizing_bb": 0.0,
    "equity_pct": 0.0,
    "ev_bb": 0.0,
    "fps": 0.0,
    "window_geometry": [0, 0, 1920, 1080],
    "is_human_takeover": False,
    "last_frame_b64": None,
    "log_message": "Servidor de telemetria ativo em 127.0.0.1:8000 (Seguro)."
}


def log_server_error(msg: str):
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        dt = datetime.now(timezone.utc).isoformat()
        with open(SERVER_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{dt}] {msg}\n")
    except Exception:
        pass


class TelemetryRequestHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self, content_type: str = "application/json", status: int = 200):
        self.send_response(status)
        # Restrito a localhost por segurança
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8000")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    def do_OPTIONS(self):
        self._send_cors_headers()
        self.wfile.write(b"")

    def do_GET(self):
        try:
            parsed_path = self.path.split("?")[0]
            path = parsed_path.rstrip("/")

            # API Routes
            if path == "/api" or path == "/api/status":
                self._send_cors_headers()
                payload = {
                    "status": "ONLINE",
                    "app": "VisualPilot Telemetry Bridge",
                    "version": "1.0.0",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "has_telemetry_file": TELEMETRY_JSON.exists(),
                    "is_human_takeover": TAKEOVER_FLAG.exists()
                }
                self.wfile.write(json.dumps(payload).encode("utf-8"))
                return

            if path in ("/api/telemetry", "/api/telemetry/status"):
                self._send_cors_headers()
                data = dict(IN_MEMORY_STATE)
                if TELEMETRY_JSON.exists():
                    try:
                        with open(TELEMETRY_JSON, "r", encoding="utf-8") as f:
                            disk_data = json.load(f)
                            data.update(disk_data)
                    except Exception:
                        pass
                data["is_human_takeover"] = TAKEOVER_FLAG.exists()
                self.wfile.write(json.dumps(data).encode("utf-8"))
                return

            if path == "/api/telemetry/frame":
                frame_b64 = IN_MEMORY_STATE.get("last_frame_b64")
                if TELEMETRY_JSON.exists() and not frame_b64:
                    try:
                        with open(TELEMETRY_JSON, "r", encoding="utf-8") as f:
                            disk_data = json.load(f)
                            frame_b64 = disk_data.get("last_frame_b64")
                    except Exception:
                        pass

                if frame_b64:
                    try:
                        img_bytes = base64.b64decode(frame_b64)
                        self._send_cors_headers("image/jpeg")
                        self.wfile.write(img_bytes)
                        return
                    except Exception:
                        pass

                self._send_cors_headers("application/json", 404)
                self.wfile.write(json.dumps({"error": "Nenhum frame capturado ainda"}).encode("utf-8"))
                return

            # Static Frontend Server (dist/) com blindagem estrita contra Path Traversal
            if DIST_DIR.is_dir():
                sub_path = path.lstrip("/")
                if sub_path == "" or sub_path == "/":
                    target_file = DIST_DIR / "index.html"
                else:
                    target_file = (DIST_DIR / sub_path).resolve()

                # Validação de segurança: o arquivo alvo DEVE estar estritamente dentro de DIST_DIR
                try:
                    target_file.relative_to(DIST_DIR)
                except ValueError:
                    log_server_error(f"Tentativa de Path Traversal bloqueada: {path}")
                    self._send_cors_headers("application/json", 403)
                    self.wfile.write(json.dumps({"error": "Acesso negado: fora do diretório permitido"}).encode("utf-8"))
                    return

                if not target_file.exists() or target_file.is_dir():
                    target_file = DIST_DIR / "index.html"

                if target_file.exists() and target_file.is_file():
                    try:
                        mime_type, _ = mimetypes.guess_type(str(target_file))
                        mime_type = mime_type or "application/octet-stream"
                        content = target_file.read_bytes()
                        self.send_response(200)
                        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8000")
                        self.send_header("Content-Type", mime_type)
                        self.send_header("Content-Length", str(len(content)))
                        self.end_headers()
                        self.wfile.write(content)
                        return
                    except Exception as exc:
                        log_server_error(f"Erro ao servir arquivo estático {target_file}: {exc}")

            # Fallback 404
            self._send_cors_headers("application/json", 404)
            self.wfile.write(json.dumps({"error": "Endpoint ou arquivo não encontrado"}).encode("utf-8"))

        except Exception as exc:
            log_server_error(f"Exceção em do_GET ({self.path}): {exc}")
            try:
                self._send_cors_headers("application/json", 500)
                self.wfile.write(json.dumps({"error": "Erro interno no servidor"}).encode("utf-8"))
            except Exception:
                pass

    def do_POST(self):
        try:
            # Validação estrita de origem: apenas solicitações locais (localhost) podem alterar estado ou enviar telemetria
            client_ip = self.client_address[0]
            if client_ip not in ("127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1"):
                log_server_error(f"Acesso POST negado de IP externo não autorizado: {client_ip}")
                self._send_cors_headers("application/json", 403)
                self.wfile.write(json.dumps({"error": "Acesso negado: comandos e push de telemetria permitidos apenas a partir de localhost"}).encode("utf-8"))
                return

            path = self.path.split("?")[0].rstrip("/")
            content_len = int(self.headers.get("Content-Length", 0))

            if content_len > MAX_BODY_SIZE:
                self._send_cors_headers("application/json", 413)
                self.wfile.write(json.dumps({"error": "Payload muito grande (máximo 1 MB)"}).encode("utf-8"))
                return

            body = self.rfile.read(content_len) if content_len > 0 else b"{}"

            if path in ("/api/telemetry/push", "/api/telemetry"):
                try:
                    new_data = json.loads(body.decode("utf-8"))
                    IN_MEMORY_STATE.update(new_data)
                    LOGS_DIR.mkdir(parents=True, exist_ok=True)
                    with open(TELEMETRY_JSON, "w", encoding="utf-8") as f:
                        json.dump(IN_MEMORY_STATE, f, ensure_ascii=False)
                    self._send_cors_headers()
                    self.wfile.write(json.dumps({"status": "SUCCESS", "received": True}).encode("utf-8"))
                except Exception as e:
                    log_server_error(f"Erro ao processar push de telemetria: {e}")
                    self._send_cors_headers("application/json", 400)
                    self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

            if path == "/api/takeover/pause":
                LOGS_DIR.mkdir(parents=True, exist_ok=True)
                TAKEOVER_FLAG.write_text("PAUSED_BY_WEB", encoding="utf-8")
                self._send_cors_headers()
                self.wfile.write(json.dumps({"status": "PAUSED", "is_human_takeover": True}).encode("utf-8"))
                return

            if path == "/api/takeover/resume":
                TAKEOVER_FLAG.unlink(missing_ok=True)
                self._send_cors_headers()
                self.wfile.write(json.dumps({"status": "RESUMED", "is_human_takeover": False}).encode("utf-8"))
                return

            self._send_cors_headers("application/json", 404)
            self.wfile.write(json.dumps({"error": "Endpoint POST não encontrado"}).encode("utf-8"))

        except Exception as exc:
            log_server_error(f"Exceção em do_POST ({self.path}): {exc}")
            try:
                self._send_cors_headers("application/json", 500)
                self.wfile.write(json.dumps({"error": "Erro interno no servidor"}).encode("utf-8"))
            except Exception:
                pass

    def log_message(self, format, *args):
        # Silencia logs padrão no console, registrando apenas em caso de erro via log_server_error
        pass


def run_server(port: int = 8000, host: str = "127.0.0.1") -> None:
    print("=" * 76)
    print("      VISUALPILOT - SERVIDOR DE TELEMETRIA E PAINEL WEB ESTÁTICO")
    print("=" * 76)
    print(f" • Painel Web Local  : http://{host}:{port}")
    print(f" • API Telemetria    : http://{host}:{port}/api/telemetry")
    print(f" • Diretório Dist    : {DIST_DIR} ({'Encontrado' if DIST_DIR.is_dir() else 'Não encontrado'})")
    print(f" • Segurança         : Escutando em {host} (Localhost Blindado)")
    print(" • Pressione Ctrl+C para encerrar o servidor.")
    print("=" * 76)

    httpd = HTTPServer((host, port), TelemetryRequestHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor web encerrado pelo usuário.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VisualPilot Servidor Web & Telemetria")
    parser.add_argument("--port", type=int, default=8000, help="Porta HTTP (padrão: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host bind (padrão: 127.0.0.1)")
    args = parser.parse_args()
    run_server(port=args.port, host=args.host)
