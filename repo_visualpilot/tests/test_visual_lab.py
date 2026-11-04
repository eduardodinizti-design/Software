import unittest
import tempfile
import threading
import json
from urllib.request import Request,urlopen
from visualpilot.lab.engine import SimulatedTable
from visualpilot.lab.server import create_server

class SimulatedActuatorTests(unittest.TestCase):
    def decision(self,generation=1,action='call'):
        return dict(status='found',observation=dict(table='laboratory-table',generation=generation),
                    options=[dict(action=action,frequency=1,sizing_bb=2.5)])
    def test_click_is_isolated_and_not_repeated(self):
        table=SimulatedTable();buttons=[dict(action='call',amount=2.5,unit='BB')]
        self.assertEqual(table.apply(self.decision(),buttons)['status'],'applied')
        self.assertEqual(table.apply(self.decision(),buttons)['status'],'blocked')
        self.assertEqual(len(table.actions),1)
        self.assertEqual(table.actions[0]['target'],'simulator_only')
    def test_old_generation_wrong_sizing_and_missing_button_block(self):
        for result,buttons in [(self.decision(2),[dict(action='call',amount=2.5,unit='BB')]),
                               (self.decision(),[dict(action='call',amount=3,unit='BB')]),
                               (self.decision(),[]),(dict(status='pending'),[])]:
            table=SimulatedTable()
            self.assertEqual(table.apply(result,buttons)['status'],'blocked')
            self.assertEqual(table.actions,[])

class VisualLabHTTPTests(unittest.TestCase):
    def test_live_ocr_actions_blocked_cards_and_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            server=create_server(0,folder);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            def post(path,data):
                req=Request(base+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
                with urlopen(req,timeout=30) as response:return json.load(response)
            try:
                last=None
                for i,action in enumerate(['call','check','bet','raise','fold']):
                    event=post('/api/observe',dict(index=i,obscure=False))
                    self.assertEqual(event['reading']['hero'],['5c','2s'])
                    self.assertEqual(event['decision']['options'][0]['action'],action)
                    if last:self.assertEqual(post('/api/apply',dict(token=last))['status'],'blocked')
                    self.assertEqual(post('/api/apply',dict(token=event['token']))['action'],action)
                    self.assertEqual(post('/api/apply',dict(token=event['token']))['status'],'blocked')
                    last=event['token']
                event=post('/api/observe',dict(index=2,obscure=True))
                self.assertEqual(event['reading']['hero'],[])
                self.assertEqual(post('/api/apply',dict(token=event['token']))['status'],'blocked')
                saved=list(server.lab_session.folder.glob('*.png'))
                self.assertEqual(len(saved),6)
                rows=[json.loads(line) for line in (server.lab_session.folder/'events.jsonl').read_text().splitlines()]
                applied=[r for r in rows if r.get('status')=='applied']
                self.assertEqual([r['action'] for r in applied],['call','check','bet','raise','fold'])
            finally:
                server.shutdown();server.server_close();thread.join(5)
