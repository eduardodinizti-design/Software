"""REGRA INVIOLAVEL (Eduardo 18/11): NUNCA clicar FOLD tendo CHECK disponivel.
Foldar de graca e sempre pior E dispara a popup 'tem certeza?' do PPPoker que cobre
a mesa e TRAVA o bot. Trava a regra: se quebrar, a suite falha."""
import unittest

import operar_mesa


def _row(acts):
    return dict(status='EXPERIMENTAL_BUTTON_ROW', buttons=[dict(action=a) for a in acts])


class NeverFoldFree(unittest.TestCase):
    def test_fold_vira_check_quando_check_disponivel(self):
        self.assertEqual(operar_mesa.never_fold_free('fold', _row(['FOLD', 'CHECK'])), 'check')

    def test_fold_permanece_quando_nao_ha_check(self):
        # enfrentando aposta (Fold/Call) -> fold e legitimo (nao ha check gratis)
        self.assertEqual(operar_mesa.never_fold_free('fold', _row(['FOLD', 'CALL'])), 'fold')

    def test_outras_acoes_nao_sao_tocadas(self):
        self.assertEqual(operar_mesa.never_fold_free('call', _row(['FOLD', 'CHECK'])), 'call')
        self.assertEqual(operar_mesa.never_fold_free('all_in', _row(['FOLD', 'CHECK'])), 'all_in')
        self.assertEqual(operar_mesa.never_fold_free('check', _row(['FOLD', 'CHECK'])), 'check')

    def test_sem_button_row_nao_altera(self):
        self.assertEqual(operar_mesa.never_fold_free('fold', dict(status='NO_BUTTON_ROW', buttons=[])), 'fold')
        self.assertEqual(operar_mesa.never_fold_free('fold', None), 'fold')


if __name__ == '__main__':
    unittest.main()
