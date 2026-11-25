"""Camada Nash push/fold SOMBRA (GATED): quando o contexto exato de um spot de
PUSH/FOLD (open_shove/vs_open_shove/3bet_shove) na zona de shove não tem nó
validado — tipicamente spreads enviesados (curtos_ini/curtos_fim) ou modos PKO —
o advisor devolve, como REFERÊNCIA, a MESMA tabela Nash de um contexto vizinho
(spread 'iguais' do mesmo modo/stage, senão Nash chip-EV), marcada validated=False
+ caveat. Vira CONSELHO/SOMBRA em vez de ABSTENÇÃO; NUNCA auto-executa. Não inventa
range: reusa nó Nash/ICM já validado no pack.

Invariantes travados aqui:
 - sombra SÓ para spots de push/fold, SÓ quando o nó exato falta;
 - sombra NUNCA é validated=True nem execution_allowed=True;
 - o range sombreado é IDÊNTICO ao do nó de referência (shova as mesmas mãos);
 - contextos que JÁ têm nó validado continuam validated=True (sem regressão);
 - spots de RAISE na zona de shove continuam abstendo (guarda anti mini-raise intacta).
"""
import unittest

from preflop_advisor import PreflopAdvisor, NASH_SHADOW_SPOTS
import auditar_cobertura_preflop as A

PACK = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'


class NashShadowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adv = PreflopAdvisor.from_file(PACK)

    # --- spots que ANTES abstinham (SHOVE_ZONE_PUSHFOLD_ONLY_NO_BORROW) ---

    def test_vs_open_short_icm_skewed_spread_now_advises_shadow(self):
        """icm/bubble/curtos_fim BB vs BTN @10bb: antes ABSTAIN; agora ADVICE sombra."""
        st = A.st_vs_open('BB', 'BTN', 10, 'curtos_fim')
        r = self.adv.advise_from_reading(st, ['Ad', 'Ac'], mode='icm', stage='bubble')
        self.assertEqual(r['status'], 'ADVICE')
        self.assertNotEqual(r.get('reason'), 'SHOVE_ZONE_PUSHFOLD_ONLY_NO_BORROW')
        self.assertIs(r.get('validated'), False)
        self.assertFalse(r.get('execution_allowed'))
        self.assertTrue(any('NASH_SHADOW' in c for c in (r.get('caveats') or [])))

    def test_first_in_short_icm_skewed_spread_now_advises_shadow(self):
        """icm/bubble/curtos_fim HJ @10bb (first-in): antes ABSTAIN; agora ADVICE sombra."""
        st = A.st_first_in('HJ', 10, 'curtos_fim')
        r = self.adv.advise_from_reading(st, ['Ad', 'Ac'], mode='icm', stage='bubble')
        self.assertEqual(r['status'], 'ADVICE')
        self.assertIs(r.get('validated'), False)
        self.assertFalse(r.get('execution_allowed'))
        self.assertTrue(any('NASH_SHADOW' in c for c in (r.get('caveats') or [])))

    def test_shadow_is_push_fold_only(self):
        """A sombra é push/fold: AA shova, 72o folda (mão fora do range -> fold)."""
        st = A.st_first_in('HJ', 10, 'curtos_fim')
        aa = self.adv.advise_from_reading(st, ['Ad', 'Ac'], mode='icm', stage='bubble')
        trash = self.adv.advise_from_reading(st, ['7c', '2d'], mode='icm', stage='bubble')
        self.assertEqual(aa.get('recommended'), 'all_in')
        self.assertIn(trash.get('status'), ('ADVICE', 'OUT_OF_RANGE'))
        if trash.get('status') == 'ADVICE':
            self.assertEqual(trash.get('recommended'), 'fold')

    # --- INVARIANTES de segurança ---

    def test_shadow_never_validated(self):
        """Em TODA a zona de shove skewed, a sombra nunca marca validated/executável."""
        bad = []
        for spread in ('curtos_fim', 'curtos_ini'):
            for stk in (5, 8, 10, 12, 15):
                for st, kw in (
                    (A.st_first_in('CO', stk, spread), {}),
                    (A.st_vs_open('BB', 'BTN', stk, spread), {}),
                ):
                    r = self.adv.advise_from_reading(st, ['Ad', 'Ac'],
                                                     mode='icm', stage='bubble', **kw)
                    if r.get('status') == 'ADVICE' and r.get('validated'):
                        # Só é aceitável validated=True se NÃO foi sombra.
                        if any('NASH_SHADOW' in c for c in (r.get('caveats') or [])):
                            bad.append((spread, stk, r.get('caveats')))
                    if r.get('execution_allowed'):
                        bad.append(('exec', spread, stk))
        self.assertEqual(bad, [], 'sombra marcou validated/executável: %r' % bad)

    def test_shadow_range_subset_of_reference(self):
        """O range sombreado ⊆ o range do nó Nash de referência (iguais@mesmo bucket): a
        sombra REUSA a referência (nunca inventa mão fora dela), e o ICM-tightening (opção A,
        20/11) só REMOVE marginais em bolha — nunca adiciona. Mantém os fortes (AA)."""
        # nó de referência: icm/bubble/iguais open_shove HJ @10
        ref = self.adv._index[('icm', 'regular', 'bubble', 9, 10,
                               'open_shove', 'HJ', (), 'iguais')]
        shove_ref = {h for h, f in zip(self.adv.hands, ref['freq']['all_in']) if f > 0}
        shoved = set()
        for h in self.adv.hands:
            c = _cards(h)
            st = A.st_first_in('HJ', 10, 'curtos_fim')
            r = self.adv.advise_from_reading(st, c, mode='icm', stage='bubble')
            if r.get('status') == 'ADVICE' and r.get('recommended') == 'all_in':
                shoved.add(h)
        self.assertTrue(shoved <= shove_ref,
                        'sombra inventou mão fora da referência: %r' % (shoved - shove_ref))
        self.assertIn('AA', shoved)                 # ICM não aperta os fortes
        self.assertTrue(shoved < shove_ref)         # bolha REMOVEU marginais (aperto ativo)

    def test_existing_validated_node_not_shadowed(self):
        """Contexto COM nó validado (icm/bubble/iguais) continua validated=True."""
        st = A.st_first_in('HJ', 10, 'iguais')
        r = self.adv.advise_from_reading(st, ['Ad', 'Ac'], mode='icm', stage='bubble')
        self.assertEqual(r['status'], 'ADVICE')
        self.assertIs(r.get('validated'), True)
        self.assertFalse(any('NASH_SHADOW' in c for c in (r.get('caveats') or [])))

    def test_chip_ev_shove_unchanged(self):
        """chip_ev é a própria referência Nash: sem sombra, segue validated=True."""
        st = A.st_first_in('CO', 10, 'iguais')
        r = self.adv.advise_from_reading(st, ['Ad', 'Ac'], mode='chip_ev', stage='mid')
        self.assertEqual(r['status'], 'ADVICE')
        self.assertIs(r.get('validated'), True)
        self.assertFalse(any('NASH_SHADOW' in c for c in (r.get('caveats') or [])))

    def test_raise_spot_in_shove_zone_still_abstains(self):
        """Guarda anti mini-raise intacta: open_raise curto NÃO vira sombra de shove."""
        r = self.adv.advise(hero_cards=['Kd', 'Qs'], hero_position='CO', stack_bb=10,
                            mode='icm', stage='bubble', spread='curtos_fim', spot='open_raise')
        self.assertEqual(r['status'], 'ABSTAIN')
        self.assertFalse(any('NASH_SHADOW' in c for c in (r.get('caveats') or [])))

    def test_shadow_spots_constant(self):
        self.assertEqual(NASH_SHADOW_SPOTS,
                         frozenset({'open_shove', 'vs_open_shove', '3bet_shove'}))

    # --- ICM-TIGHTENING do jam Nash (Eduardo 20/11, opção A) ---

    def _jam_set(self, mode, stage, stk=10):
        """Conjunto de mãos que JAMAM (BB vs BTN, shove zone) no modo/fase dados."""
        out = set()
        for h in self.adv.hands:
            r = self.adv.advise_from_reading(A.st_vs_open('BB', 'BTN', stk), _cards(h),
                                             mode=mode, stage=stage)
            if r.get('status') == 'ADVICE' and r.get('recommended') == 'all_in':
                out.add(h)
        return out

    def test_icm_tighten_monotonic_by_phase(self):
        """O jam ICM aperta de forma monotônica: bolha ⊆ FT ⊆ mid ⊆ chip_ev (fold só cresce
        com o risk premium). AA jama em todas as fases."""
        chip = self._jam_set('chip_ev', 'mid')
        mid = self._jam_set('icm', 'mid')
        ft = self._jam_set('icm', 'ft')
        bubble = self._jam_set('icm', 'bubble')
        self.assertTrue(bubble <= ft <= mid <= chip,
                        'não-monotônico: bubble=%d ft=%d mid=%d chip=%d'
                        % (len(bubble), len(ft), len(mid), len(chip)))
        self.assertLess(len(bubble), len(chip))      # bolha REALMENTE aperta vs chip-EV
        for s in (chip, mid, ft, bubble):
            self.assertIn('AA', s)

    def test_icm_tighten_stack_aware(self):
        """Stack-aware: a 20bb (mais fold equity, ICM pesa) o jam de bolha é mais TIGHT que
        a 10bb (curto, quase não pode foldar)."""
        b10 = self._jam_set('icm', 'bubble', stk=10)
        b20 = self._jam_set('icm', 'bubble', stk=20)
        self.assertLessEqual(len(b20), len(b10))

    def test_chip_ev_jam_never_tightened(self):
        """chip_ev nunca recebe o aperto ICM (sem caveat NASH_ICM)."""
        for h in ('AA', 'Q9s', 'J9s', 'A2s'):
            r = self.adv.advise_from_reading(A.st_vs_open('BB', 'BTN', 10), _cards(h),
                                             mode='chip_ev', stage='mid')
            self.assertFalse(any('NASH_ICM' in c for c in (r.get('caveats') or [])))


def _cards(hand):
    """'AKs'->['As','Ks']; 'AA'->['Ad','Ac']; 'AKo'->['As','Kh'] (naipes p/ teste)."""
    r1 = hand[0]
    if len(hand) == 2:                                  # par
        return [r1 + 'd', r1 + 'c']
    r2 = hand[1]
    if hand[2] == 's':
        return [r1 + 's', r2 + 's']
    return [r1 + 's', r2 + 'h']


if __name__ == '__main__':
    unittest.main()
