"""VisualPilot - Fase 1 / Módulo 3: OCR por Cartão do Lobby PPPoker.

Consome os cartões segmentados pelo Módulo 2 e extrai com precisão:
- Nome do torneio (normalizado)
- Buy-in / Custo (com validação matemática e regras de limite <= 50)
- Horário de início (data e hora validadas)
- Tipo de jogo (MTT vs. Ring Game/Cash) e Status (Aberto vs. Encerrado)
- Ponto central de clique do Módulo 2 para navegação posterior.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
import unicodedata
from typing import Any

import cv2
import numpy as np

from .core import require_rgb

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None  # type: ignore


def normalize_text(text: str) -> str:
    """Remove acentuação e espaços extras, mantendo apenas letras e números em maiúsculas."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    cleaned = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(cleaned.upper().split())


def clean_name_key(text: str) -> str:
    """Gera chave única do nome removendo espaços para comparação segura."""
    return re.sub(r"[^A-Z0-9]", "", normalize_text(text))


def group_into_lines(ocr_results: list[Any]) -> list[str]:
    """Agrupa caixas de texto com baselines verticais próximas (Y +- 8px) ordenando por X."""
    boxes_with_centers = []
    for item in ocr_results:
        b, t, s = item[0], str(item[1]).strip(), float(item[2])
        if not t:
            continue
        cx = sum(p[0] for p in b) / 4.0
        cy = sum(p[1] for p in b) / 4.0
        boxes_with_centers.append((cy, cx, t, s))

    boxes_with_centers.sort()
    lines = []
    current_line: list[tuple[float, str]] = []
    current_y = None

    for cy, cx, t, s in boxes_with_centers:
        if current_y is None or abs(cy - current_y) <= 8.0:
            current_line.append((cx, t))
            current_y = cy if current_y is None else (current_y + cy) / 2.0
        else:
            current_line.sort()
            lines.append(" ".join([text for _, text in current_line]))
            current_line = [(cx, t)]
            current_y = cy

    if current_line:
        current_line.sort()
        lines.append(" ".join([text for _, text in current_line]))

    return lines


def extract_buyin(lines: list[str]) -> tuple[Decimal | None, list[Decimal], str | None]:
    """Localiza e valida o buy-in expresso nas linhas do cartão."""
    for line in lines:
        cleaned = normalize_text(line).replace(":", ": ")
        match = re.search(r"BUY-?IN[:：]\s*([0-9.,+\s\(\)]+)", cleaned)
        if match:
            raw = match.group(1).strip()

            # Caso 1: Total com breakdown em parênteses: 50 (28.34+14.16+7.5)
            paren_match = re.search(r"([0-9.,]+)\s*\(([0-9.,+\s]+)\)", raw)
            if paren_match:
                declared_total = Decimal(paren_match.group(1).replace(",", "."))
                breakdown_parts = [
                    Decimal(p.strip().replace(",", "."))
                    for p in paren_match.group(2).split("+")
                    if p.strip().replace(",", ".").replace(".", "", 1).isdigit()
                ]
                if breakdown_parts and sum(breakdown_parts) == declared_total:
                    return declared_total, breakdown_parts, line
                return declared_total, [declared_total], line

            # Caso 2: Parcelas somadas com +: 28.34 + 14.16 + 7.5
            if "+" in raw:
                parts = [
                    Decimal(p.strip().replace(",", "."))
                    for p in raw.split("+")
                    if p.strip().replace(",", ".").replace(".", "", 1).isdigit()
                ]
                if parts:
                    return sum(parts), parts, line

            # Caso 3: Múltiplos números após o label (ex: "2 200" onde 2 é prefixo duplicado da caixa)
            tokens = raw.split()
            if len(tokens) > 1:
                if len(tokens) >= 2 and tokens[1].startswith(tokens[0]):
                    val = Decimal(tokens[1].replace(",", "."))
                    return val, [val], line
                nums = [
                    Decimal(t.replace(",", "."))
                    for t in tokens
                    if t.replace(",", "").replace(".", "").isdigit()
                ]
                if nums:
                    val = max(nums)
                    return val, [val], line

            # Caso 4: Valor único simples: "50"
            num_clean = re.sub(r"[^0-9.,]", "", raw)
            if num_clean:
                try:
                    val = Decimal(num_clean.replace(",", "."))
                    return val, [val], line
                except Exception:
                    pass

    return None, [], None


def extract_start_time(lines: list[str]) -> str | None:
    """Extrai e valida o horário de início no formato MM/DD HH:MM."""
    for line in lines:
        cleaned = normalize_text(line).replace(" ", "")
        match = re.search(r"(?:INICIO|HORARIO)?[:：]?([0-1]?[0-9]/[0-3]?[0-9])\s*([0-2][0-9]:[0-5][0-9])", cleaned)
        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            try:
                month, day = date_str.split("/")
                m_int, d_int = int(month), int(day)
                if 1 <= m_int <= 12 and 1 <= d_int <= 31:
                    return f"{m_int:02d}/{d_int:02d} {time_str}"
            except Exception:
                pass

        match_direct = re.search(r"([0-1][0-9]/[0-3][0-9])\s*([0-2][0-9]:[0-5][0-9])", line)
        if match_direct:
            try:
                m_int, d_int = int(match_direct.group(1).split("/")[0]), int(match_direct.group(1).split("/")[1])
                if 1 <= m_int <= 12 and 1 <= d_int <= 31:
                    return f"{match_direct.group(1)} {match_direct.group(2)}"
            except Exception:
                pass

    return None


def extract_tournament_name(lines: list[str]) -> str:
    """Extrai o título principal do torneio, descartando rótulos conhecidos de metadados."""
    ignored_keywords = {
        "BUY-IN", "BUYIN", "PREMIACAO", "HORARIO", "INICIO", "BLINDS",
        "JACKPOT", "EARLY", "PKO", "NLH", "PL06", "PLO6", "PPST", "10MIN",
        "20MIN", "3MIN", "PF", "0/6", "1/2"
    }

    candidates = []
    for line in lines:
        norm = normalize_text(line)
        cleaned = norm.replace(" ", "")

        if any(kw in cleaned for kw in ("BUY-IN", "BUYIN", "PREMIACAO", "HORARIO", "INICIO", "BLINDS")):
            continue

        words = [w for w in norm.split() if w not in ignored_keywords and len(w) > 1]
        if words:
            candidates.append(norm)

    if candidates:
        candidates.sort(key=lambda t: len(re.sub(r"[^A-Z]", "", t)), reverse=True)
        return candidates[0]

    return "TORNEIO SEM NOME"


def parse_card_lines(lines: list[str], max_buyin: float = 50.0) -> dict[str, Any]:
    """Interpreta as linhas lidas do cartão e retorna a estrutura do torneio."""
    name = extract_tournament_name(lines)
    buyin_val, breakdown, raw_buyin = extract_buyin(lines)
    start_time = extract_start_time(lines)

    is_cash_game = any("BLINDS" in normalize_text(l) or "PL06" in normalize_text(l) for l in lines)
    is_pko = any("PKO" in normalize_text(l) for l in lines)

    if is_cash_game:
        start_time = None

    eligible = True
    rejection_reasons = []

    if is_cash_game:
        eligible = False
        rejection_reasons.append("cash_game_not_mtt")

    if buyin_val is None:
        eligible = False
        rejection_reasons.append("buyin_not_found_or_unreadable")
    elif float(buyin_val) > max_buyin:
        eligible = False
        rejection_reasons.append(f"buyin_exceeds_limit_{max_buyin}")

    is_closed = any("ENCERRADO" in normalize_text(l) for l in lines)
    if is_closed:
        eligible = False
        rejection_reasons.append("registration_closed")

    status = "closed" if is_closed else ("open" if eligible else "ineligible")

    return {
        "name": name,
        "name_key": clean_name_key(name),
        "buyin": str(buyin_val) if buyin_val is not None else None,
        "buyin_breakdown": [float(b) for b in breakdown] if breakdown else [],
        "raw_buyin_text": raw_buyin,
        "start_time": start_time,
        "game_format": "Cash Game (Blinds)" if is_cash_game else ("MTT PKO" if is_pko else "MTT"),
        "status": status,
        "eligible": eligible,
        "rejection_reasons": rejection_reasons,
        "raw_lines": lines
    }


def read_card_image(ocr: Any, image: np.ndarray) -> list[str]:
    """Executa o RapidOCR no recorte do cartão e retorna as linhas agrupadas por baseline horizontal."""
    require_rgb(image)
    results, _ = ocr(image)
    if not results:
        return []
    return group_into_lines(results)


def process_cards_ocr(
    segments_json_path: Path | str,
    cards_dir: Path | str,
    output_dir: Path | str,
    max_buyin: float = 50.0
) -> dict[str, Any]:
    """Consome segments.json do Módulo 2, executa OCR em cada cartão e salva tournaments.json."""
    if RapidOCR is None:
        raise ImportError("rapidocr_onnxruntime não está instalado. Execute pip install rapidocr-onnxruntime onnxruntime.")

    segments_path = Path(segments_json_path)
    if not segments_path.is_file():
        raise FileNotFoundError(f"Arquivo segments.json não encontrado: {segments_path}")

    segments_data = json.loads(segments_path.read_text(encoding="utf-8"))
    cards_path = Path(cards_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ocr = RapidOCR()
    tournaments = []

    for card_meta in segments_data.get("cards", []):
        card_index = card_meta["index"]
        crop_file = card_meta.get("crop_file", f"card_{card_index:02d}.png")
        crop_full_path = cards_path / crop_file

        if not crop_full_path.is_file():
            print(f"Aviso: Recorte {crop_file} não encontrado em {cards_path}", file=sys.stderr)
            continue

        card_bgr = cv2.imread(str(crop_full_path))
        if card_bgr is None:
            continue

        card_rgb = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2RGB)
        lines = read_card_image(ocr, card_rgb)
        parsed = parse_card_lines(lines, max_buyin=max_buyin)

        tournament_record = {
            "card_index": card_index,
            "complete": card_meta.get("complete", True),
            "clip_reason": card_meta.get("clip_reason"),
            "click_point_local": card_meta.get("click_point_local"),
            "click_point_absolute": card_meta.get("click_point_absolute"),
            "box": card_meta.get("local_box"),
            "crop_file": crop_file,
            **parsed
        }
        tournaments.append(tournament_record)

    report = {
        "module": "phase1_module3",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_cards_processed": len(tournaments),
        "eligible_for_registration": sum(1 for t in tournaments if t["eligible"]),
        "max_buyin_limit": max_buyin,
        "tournaments": tournaments
    }

    tournaments_json_path = out / "tournaments.json"
    tournaments_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Módulo 3: OCR por cartão e extração de dados do torneio.")
    parser.add_argument("--segments", type=Path, required=True, help="Caminho para segments.json gerado pelo Módulo 2.")
    parser.add_argument("--cards-dir", type=Path, required=True, help="Pasta contendo os recortes dos cartões (card_XX.png).")
    parser.add_argument("--output", type=Path, required=True, help="Pasta de saída para tournaments.json.")
    parser.add_argument("--max-buyin", type=float, default=50.0, help="Limite máximo de buy-in autorizado (padrão: 50).")
    args = parser.parse_args(argv)

    try:
        report = process_cards_ocr(args.segments, args.cards_dir, args.output, max_buyin=args.max_buyin)
        print("Leitura OCR concluída com sucesso:")
        print(f"  Cartões processados: {report['total_cards_processed']}")
        print(f"  Torneios elegíveis (buy-in <= {args.max_buyin}): {report['eligible_for_registration']}")
        for t in report["tournaments"]:
            status_symbol = "✓ [ELEGÍVEL]" if t["eligible"] else f"✗ [{', '.join(t['rejection_reasons'])}]"
            print(f"  #{t['card_index']} {t['name']} | Buy-in: {t['buyin'] or 'N/A'} | Início: {t['start_time'] or 'N/A'} -> {status_symbol}")
        print(f"  Dados salvos em: {args.output / 'tournaments.json'}")
        return 0
    except Exception as exc:
        print(f"Erro no OCR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
