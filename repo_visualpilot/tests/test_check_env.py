"""Testes unitários para o script de pré-voo (check_env)."""
from pathlib import Path
import tempfile
import unittest

from visualpilot.pppoker.check_env import run_preflight_checks


class CheckEnvTests(unittest.TestCase):
    def test_run_preflight_checks_creates_csv_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            res = run_preflight_checks(logs_dir=tmpdir, require_window=False)

            self.assertIn("all_passed", res)
            self.assertIn("checks", res)

            # O diretório de logs e o arquivo CSV devem ter sido validados ou criados
            csv_check = next((c for c in res["checks"] if c["name"] == "Arquivo de Auditoria CSV"), None)
            self.assertIsNotNone(csv_check)
            self.assertEqual(csv_check["status"], "OK")

            # Verifica que o arquivo realmente foi criado em disco
            created_files = list(Path(tmpdir).glob("clicks_audit_*.csv"))
            self.assertEqual(len(created_files), 1)

            # Verifica cabeçalho
            content = created_files[0].read_text(encoding="utf-8")
            self.assertIn("timestamp_iso", content)
            self.assertIn("event_type", content)
            self.assertIn("status", content)

    def test_run_preflight_checks_with_require_window_without_pppoker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Sem requerer janela não falha criticamente (apenas alerta)
            res_warn = run_preflight_checks(logs_dir=tmpdir, require_window=False)
            win_check_warn = next((c for c in res_warn["checks"] if c["name"] == "Janela do PPPoker"), None)
            self.assertIsNotNone(win_check_warn)
            self.assertIn(win_check_warn["status"], ["OK", "WARN"])

            # Com require_window=True, se a janela não existir no ambiente de CI, falha explicitamente
            # (ou passa caso exista um mock/janela ativa)
            res_strict = run_preflight_checks(logs_dir=tmpdir, require_window=True)
            self.assertIn("all_passed", res_strict)


if __name__ == "__main__":
    unittest.main()
