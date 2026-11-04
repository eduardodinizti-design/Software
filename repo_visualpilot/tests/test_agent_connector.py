import json
from pathlib import Path
import tempfile
import unittest

from visualpilot.agent.connector import CloudConfig, RangeCoachConnector, canonical_hand
from visualpilot.agent.bridge import RangeCoachEventBridge
from visualpilot.agent.strategy import RangeCoachStrategy
from visualpilot.viz.app import cloud_status


class Response:
    def __init__(self, payload=None): self.payload = payload
    def read(self):
        return b"" if self.payload is None else json.dumps(self.payload).encode()


class Opener:
    def __init__(self, responses=()): self.responses=list(responses);self.requests=[]
    def open(self, request, timeout):
        self.requests.append((request,timeout))
        response=self.responses.pop(0) if self.responses else None
        if isinstance(response,Exception):raise response
        return Response(response)


def config():
    return CloudConfig("https://example.supabase.co", "secret", timeout_seconds=2)


class ConnectorTests(unittest.TestCase):
    def test_canonical_hand_is_order_independent(self):
        self.assertEqual(canonical_hand(["Kh","As"]),"AKo")
        self.assertEqual(canonical_hand(["As","Ks"]),"AKs")
        self.assertEqual(canonical_hand(["Qh","Qs"]),"QQ")

    def test_ini_loads_secret_from_environment(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"nvt_config.ini"
            path.write_text("[supabase]\nurl=https://x.supabase.co\napi_key=${TEST_RANGE_KEY}\n",encoding="utf-8")
            os.environ["TEST_RANGE_KEY"]="abc"
            try:self.assertEqual(CloudConfig.from_ini(path).api_key,"abc")
            finally:os.environ.pop("TEST_RANGE_KEY",None)

    def test_lookup_maps_remote_range_and_sends_auth_headers(self):
        opener=Opener([[{"action":"RAISE","sizing":2.2,"strategy_version":"v3","confidence":.91}]])
        connector=RangeCoachConnector(config(),opener=opener)
        result=connector.lookup_range(["As","Ks"],"BTN","freezeout")
        self.assertEqual(result["action"],"RAISE");self.assertEqual(result["sizing"],2.2)
        request,timeout=opener.requests[0]
        self.assertIn("hand_key=eq.AKs",request.full_url)
        self.assertEqual(request.get_header("Apikey"),"secret")
        self.assertEqual(timeout,2)

    def test_missing_position_never_queries_cloud(self):
        opener=Opener();connector=RangeCoachConnector(config(),opener=opener)
        self.assertEqual(connector.lookup_range(["As","Ks"],None)["status"],"pending")
        self.assertEqual(opener.requests,[])

    def test_audit_accepts_only_low_buyin_fictional_tournaments(self):
        opener=Opener([None]);connector=RangeCoachConnector(config(),opener=opener)
        self.assertEqual(connector.upload_audit({},dict(fictional=False,buyin_chips=1))["status"],"rejected")
        self.assertEqual(connector.upload_audit({},dict(fictional=True,buyin_chips=11))["status"],"rejected")
        result=connector.upload_audit({"hand_id":"h1","hero_cards":["As","Ks"]},
                                      dict(fictional=True,buyin_chips=10,tournament_id="t1"))
        self.assertEqual(result["status"],"uploaded");self.assertEqual(len(opener.requests),1)
        body=json.loads(opener.requests[0][0].data)
        self.assertTrue(body["fictional"]);self.assertEqual(body["source"],"visualpilot_observation_only")

    def test_diagnostic_reports_success_without_leaking_key(self):
        connector=RangeCoachConnector(config(),opener=Opener([[]]))
        result=connector.diagnose()
        self.assertTrue(result["connected"]);self.assertNotIn("secret",json.dumps(result))

    def test_diagnostic_reports_exception_type_only(self):
        connector=RangeCoachConnector(config(),opener=Opener([OSError("secret network detail")]))
        result=connector.diagnose()
        self.assertFalse(result["connected"]);self.assertEqual(result["error"],"OSError")
        self.assertNotIn("secret network detail",json.dumps(result))

    def test_strategy_is_advisory_and_requires_complete_hero(self):
        class Connector:
            def lookup_range(self,*args):return {"status":"found","action":"CALL"}
        strategy=RangeCoachStrategy(Connector())
        self.assertEqual(strategy.theoretical_action({"hero":[]},{})["status"],"pending")
        self.assertEqual(strategy.theoretical_action({"hero":["As","Ks"],"street":"preflop","board":[]},{"position":"BTN"})["action"],"CALL")

    def test_cloud_status_is_neutral_without_config(self):
        with tempfile.TemporaryDirectory() as folder:
            status=cloud_status(Path(folder)/"absent.ini")
        self.assertEqual(status["label"],"⚪ Nuvem não configurada")

    def test_invalid_non_https_configuration_is_rejected(self):
        with self.assertRaises(ValueError):RangeCoachConnector(CloudConfig("http://example.test","key"))

    def test_event_bridge_routes_partial_and_consolidated_without_blocking_ocr(self):
        calls=[];results=[]
        class Strategy:
            def theoretical_action(self,reading,context):
                calls.append(("partial",reading,context));return {"status":"found","action":"CALL"}
            def audit_consolidated(self,snapshot,tournament):
                calls.append(("audit",snapshot,tournament));return {"status":"uploaded"}
        bridge=RangeCoachEventBridge(Strategy(),results.append,workers=1)
        partial=bridge.partial_cards_ready(
            {"table":"mesa-1","generation":4,"reading":{"hero":["As","Ks"]}},
            {"position":"BTN"})
        audit=bridge.snapshot_consolidated(
            {"table":"mesa-1","hand_id":"h1"},
            {"tournament":{"fictional":True,"buyin_chips":5}})
        partial.result(timeout=1);audit.result(timeout=1);bridge.close()
        self.assertEqual([call[0] for call in calls],["partial","audit"])
        self.assertEqual([item["source"] for item in results],
                         ["PARTIAL_CARDS_READY","SNAPSHOT_CONSOLIDATED"])


if __name__=="__main__":unittest.main()
