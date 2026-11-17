"""Smoke end-to-end do dry-run de troca de clube sobre um gabarito real (guardado
por Tesseract): DENTRO do Karekas o coordenador reconhece o clube e é idempotente."""
import io
import os
import unittest
from contextlib import redirect_stdout


def _ocr_ready():
    try:
        from table_reading.pipeline import configure_ocr
        return configure_ocr().get('status') == 'READY'
    except Exception:
        return False


_INSIDE = os.path.join('tests', 'fixtures', 'lobby_live', 'karekas-lobby-live-1.png')


@unittest.skipUnless(_ocr_ready() and os.path.exists(_INSIDE),
                     'Tesseract/gabarito indisponível')
class DryRunSmokeTests(unittest.TestCase):
    def _run(self, target):
        from trocar_clube_dryrun import main
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(['--image', _INSIDE, '--target', target])
        return rc, buf.getvalue()

    def test_dentro_do_clube_reconhece_e_e_idempotente(self):
        rc, out = self._run('Karekas Yellow')
        self.assertEqual(rc, 0)
        self.assertIn('Karekas Yellow', out)
        self.assertIn('nada a fazer', out)                 # NOOP idempotente

    def test_alvo_diferente_planeja_troca_sem_enviar(self):
        rc, out = self._run('AK Amakha Club')
        self.assertEqual(rc, 0)
        self.assertIn('trocaria', out)                     # planeja a troca
        self.assertIn('NÃO enviado', out)                  # dry-run: nada é clicado


if __name__ == '__main__':
    unittest.main()
