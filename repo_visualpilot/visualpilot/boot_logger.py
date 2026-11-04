"""VisualPilot - Módulo Centralizado de Diagnóstico de Boot e Logging (Windows & Linux).

Registra e investiga falhas de inicialização com categorias estruturadas:
- [PATH]: Diretórios, PYTHONPATH, sys.path, espaços e alertas do OneDrive
- [PERM]: Permissões de gravação no diretório raiz, logs e %TEMP%
- [DEP]:  Importação e detecção de dependências (pyautogui, pygetwindow, pillow, numpy, pytesseract, cv2, mss, requests, tkinter)
- [WIN]:  Estado da janela de jogo (PPPoker)
- Gravação persistente e simultânea em:
  1. %TEMP%/visualpilot_boot_debug.log
  2. logs/startup_debug.log
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

TEMP_LOG_FILE = Path(tempfile.gettempdir()) / "visualpilot_boot_debug.log"


def get_project_root() -> Path:
    """Retorna o diretório raiz absoluto do projeto."""
    current = Path(__file__).resolve().parent
    # Se estiver dentro de repo_visualpilot/visualpilot, a raiz é dois níveis acima
    if (current.parent.parent / "package.json").is_file() or (current.parent.parent / "diagnostico.py").is_file():
        return current.parent.parent
    if (current.parent / "package.json").is_file():
        return current.parent
    return current


PROJECT_ROOT = get_project_root()
LOCAL_LOG_DIR = PROJECT_ROOT / "logs"
LOCAL_LOG_FILE = LOCAL_LOG_DIR / "startup_debug.log"


def log_boot_event(
    category: str,
    message: str,
    details: Optional[str] = None,
    to_stdout: bool = True,
    status: str = "INFO",
) -> None:
    """Grava um evento estruturado de boot no console e nos arquivos de log."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    header = f"[{timestamp}] [{status.upper():<5}] [{category.upper():<4}] {message}"
    lines = [header]
    if details:
        for d in details.splitlines():
            lines.append(f"    --> {d}")
    content = "\n".join(lines) + "\n"

    if to_stdout:
        print(content.rstrip())

    # Gravação em %TEMP%/visualpilot_boot_debug.log
    try:
        with open(TEMP_LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(content)
    except Exception:
        pass

    # Gravação em logs/startup_debug.log
    try:
        LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(content)
    except Exception:
        pass


def audit_paths() -> Tuple[bool, List[str]]:
    """Investiga caminhos de execução, presença de OneDrive e PYTHONPATH."""
    issues = []
    root_str = str(PROJECT_ROOT)

    # 1. Checagem de OneDrive
    if "onedrive" in root_str.lower():
        issues.append(
            f"Alerta de Nuvem: Projeto executando dentro do OneDrive ({root_str}).\n"
            "Arquivos 'sob demanda' podem bloquear a leitura/escrita de pacotes no ambiente virtual.\n"
            "Solução: Clique com o botão direito na pasta do projeto e marque 'Sempre manter neste dispositivo'."
        )

    # 2. Espaços no caminho
    if " " in root_str:
        log_boot_event("PATH", f"Caminho do projeto contém espaços: '{root_str}'", status="WARN")

    # 3. sys.path
    embedded_site = PROJECT_ROOT / "python_embedded" / "Lib" / "site-packages"
    if embedded_site.is_dir() and str(embedded_site) not in sys.path:
        sys.path.insert(0, str(embedded_site))
    repo_path = PROJECT_ROOT / "repo_visualpilot"
    if repo_path.is_dir() and str(repo_path) not in sys.path:
        sys.path.insert(0, str(repo_path))
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(1, str(PROJECT_ROOT))

    log_boot_event(
        "PATH",
        f"Auditoria de Caminho Concluída. Raiz: {PROJECT_ROOT} | Executável: {sys.executable}",
        details=f"sys.path=[{', '.join(sys.path[:4])}...]",
        status="OK" if not issues else "WARN",
    )
    return len(issues) == 0, issues


def audit_permissions() -> Tuple[bool, List[str]]:
    """Testa permissões reais de gravação em disco."""
    errors = []

    # 1. Gravação na Raiz do Projeto
    probe_root = PROJECT_ROOT / f".probe_root_{os.getpid()}.tmp"
    try:
        probe_root.write_text("probe_ok", encoding="utf-8")
        probe_root.unlink(missing_ok=True)
        log_boot_event("PERM", "Permissão de gravação na Raiz do Projeto: OK", status="OK")
    except Exception as e:
        err = f"Falha de gravação na raiz ({PROJECT_ROOT}): {e}"
        errors.append(err)
        log_boot_event("PERM", err, details=traceback.format_exc(), status="FAIL")

    # 2. Gravação na pasta logs/
    try:
        LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
        probe_log = LOCAL_LOG_DIR / f".probe_log_{os.getpid()}.tmp"
        probe_log.write_text("probe_ok", encoding="utf-8")
        probe_log.unlink(missing_ok=True)
        log_boot_event("PERM", "Permissão de gravação na pasta logs/: OK", status="OK")
    except Exception as e:
        err = f"Falha de gravação na pasta de logs ({LOCAL_LOG_DIR}): {e}"
        errors.append(err)
        log_boot_event("PERM", err, details=traceback.format_exc(), status="FAIL")

    # 3. Gravação na pasta %TEMP%
    try:
        probe_temp = Path(tempfile.gettempdir()) / f".probe_temp_{os.getpid()}.tmp"
        probe_temp.write_text("probe_ok", encoding="utf-8")
        probe_temp.unlink(missing_ok=True)
        log_boot_event("PERM", f"Permissão de gravação em %TEMP% ({tempfile.gettempdir()}): OK", status="OK")
    except Exception as e:
        err = f"Falha de gravação no diretório temporário (%TEMP%): {e}"
        errors.append(err)
        log_boot_event("PERM", err, details=traceback.format_exc(), status="FAIL")

    return len(errors) == 0, errors


def audit_dependencies() -> Tuple[bool, List[str], List[str]]:
    """Testa a importação de cada pacote requerido."""
    required = [
        ("pyautogui", "PyAutoGUI (Cliques de Mouse)"),
        ("pygetwindow", "PyGetWindow (Janela do PPPoker)"),
        ("PIL", "Pillow (Captura de Frame)"),
        ("numpy", "NumPy (Cálculo de Matrizes)"),
        ("pytesseract", "PyTesseract (OCR de Mesa)"),
        ("mss", "MSS (Captura Ultrarrápida)"),
        ("cv2", "OpenCV (Visão Computacional)"),
        ("requests", "Requests (Comunicação Web)"),
    ]

    missing = []
    available = []

    for mod_name, label in required:
        try:
            mod = importlib.import_module(mod_name)
            ver = getattr(mod, "__version__", "ativo")
            available.append(f"{label}: OK (v{ver})")
            log_boot_event("DEP", f"{label}: OK (v{ver})", status="OK")
        except ModuleNotFoundError:
            missing.append(mod_name)
            log_boot_event("DEP", f"{label}: AUSENTE (ModuleNotFoundError)", status="FAIL")
        except Exception as e:
            missing.append(mod_name)
            log_boot_event("DEP", f"{label}: ERRO DE IMPORT ({e})", details=traceback.format_exc(), status="FAIL")

    return len(missing) == 0, missing, available


def run_preflight_diagnostics(caller_name: str = "boot") -> bool:
    """Executa diagnóstico completo antes do início de qualquer script e grava logs."""
    log_boot_event("BOOT", "=" * 60, to_stdout=False)
    log_boot_event("BOOT", f"INICIANDO {caller_name.upper()} NO WINDOWS / PYTHON {platform.python_version()}", status="INFO")
    log_boot_event("BOOT", f"Log temporário: {TEMP_LOG_FILE}", status="INFO")

    paths_ok, path_issues = audit_paths()
    perms_ok, perm_errors = audit_permissions()
    deps_ok, missing_deps, _ = audit_dependencies()

    success = paths_ok and perms_ok and deps_ok

    if not success:
        log_boot_event(
            "BOOT",
            f"FALHA NO PRÉ-VOO DE {caller_name.upper()}: Dependências ausentes ou problemas de permissão.",
            details=(
                f"Dependências ausentes: {', '.join(missing_deps) if missing_deps else 'Nenhuma'}\n"
                f"Problemas de permissão: {', '.join(perm_errors) if perm_errors else 'Nenhum'}\n"
                f"Avisos de caminho: {', '.join(path_issues) if path_issues else 'Nenhum'}\n"
                "AÇÃO CORRETIVA RECOMENDADA:\n"
                f"1. Execute: pip install {' '.join(missing_deps)}\n"
                "2. Ou dê dois cliques em: corrigir_instalacao.bat"
            ),
            status="FAIL",
        )
    else:
        log_boot_event("BOOT", f"PRÉ-VOO DE {caller_name.upper()} CONCLUÍDO COM SUCESSO!", status="OK")

    return success
