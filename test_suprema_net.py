"""TRAVA do extrator de JSON da ponte de rede da Suprema (offline): reassembla mensagens
que FRAGMENTAM entre reads de SSL, ignora o header binário WS/pomelo, e respeita strings
com chaves/aspas. Fecha a parte testável do suprema_net sem cliente aberto."""
import unittest

from suprema_net import JsonFrameExtractor, messages_from_stream, is_game_event
from suprema_state import SupremaTable

# header binário WS/pomelo tipico antes do corpo JSON (como visto no recon: 82 7e .. onMsg)
HDR = '\x82\x7e\x02\xc0\x04\x00\x02\xbc\x06\x05onMsg'


class Extractor(unittest.TestCase):

    def test_single_message_com_header(self):
        msg = HDR + '{"route":"onMsg","event":"gameinfo","data":{"game_info":{"pot":100}}}'
        got = messages_from_stream([msg])
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]['event'], 'gameinfo')
        self.assertEqual(got[0]['data']['game_info']['pot'], 100)

    def test_fragmentado_entre_chunks(self):
        full = HDR + '{"event":"moveturn","data":{"game_seat":{"1":{"seat":2,"coins":10000,"cards":[59,56]}}}}'
        a, b, c = full[:20], full[20:45], full[45:]     # 3 pedaços no meio do JSON
        ex = JsonFrameExtractor()
        self.assertEqual(ex.feed(a), [])                # incompleto
        self.assertEqual(ex.feed(b), [])                # ainda incompleto
        out = ex.feed(c)                                # fecha agora
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['event'], 'moveturn')

    def test_multiplas_mensagens_num_chunk(self):
        blob = (HDR + '{"event":"countdown","data":{"sec":15}}'
                + HDR + '{"event":"prompt","data":{"gamer_prompt":{"fold":true}}}')
        got = messages_from_stream([blob])
        self.assertEqual([m['event'] for m in got], ['countdown', 'prompt'])

    def test_string_com_chaves_e_aspas(self):
        # valor de string contendo { } " escapado não pode quebrar o balanceamento
        msg = HDR + '{"event":"x","data":{"s":"a{b}c \\"q\\" d"}}'
        got = messages_from_stream([msg])
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]['data']['s'], 'a{b}c "q" d')

    def test_lixo_binario_sem_json_nao_quebra(self):
        self.assertEqual(messages_from_stream(['\x82\x04\x03\x00\x00\x00']), [])

    def test_is_game_event(self):
        self.assertTrue(is_game_event({'event': 'moveturn'}))
        self.assertFalse(is_game_event({'event': 'matchesStatusPushNotify'}))
        self.assertFalse(is_game_event({'event': 'apiClub.clubHandler.jackpot'}))


class Integracao(unittest.TestCase):
    """stream cru (fragmentado) -> extrator -> SupremaTable -> table_state."""

    def test_stream_para_table_state(self):
        gi = HDR + '{"event":"gameinfo","data":{"game_info":{"dealer_seat":2,"shared_cards":[36,59,39],"pot":3000,"state":4}}}'
        mv = HDR + ('{"event":"moveturn","data":{"game_seat":{'
                    '"1754193":{"seat":2,"coins":10000,"cards":[40,23],"chips":500,"sitout":false},'
                    '"388769":{"seat":3,"coins":9000,"cards":null,"chips":500,"sitout":false},'
                    '"295455":{"seat":6,"coins":12000,"cards":[0,0],"chips":500,"sitout":false}}}}')
        # fragmenta o moveturn no meio (o caso real: moveturn > 1 read)
        chunks = [gi, mv[:40], mv[40:90], mv[90:]]
        table = SupremaTable(bb_chips=500)
        for msg in messages_from_stream(chunks):
            if is_game_event(msg):
                table.feed_json(msg)
        state, hero = table.to_table_state()
        self.assertIsNotNone(state, 'abstido: %r' % (hero,))
        self.assertEqual(hero, ['8c', '7d'])                  # [40,23] = 8c, 7d (decode real)
        self.assertEqual(state['board'], ['4c', 'Jh', '7c'])  # [36,59,39] = 4c,Jh,7c
        self.assertEqual(state['street'], 'FLOP')
        self.assertEqual(state['positions']['hero'], 'BTN')   # dealer=2
        self.assertAlmostEqual(state['seats']['hero']['stack_bb'], 20.0)


if __name__ == '__main__':
    unittest.main()
