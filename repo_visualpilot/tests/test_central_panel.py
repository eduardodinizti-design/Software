"""Renderização real Streamlit; controlador isolado, sem alegar navegador físico."""
from pathlib import Path
import importlib.util
import json
import unittest
from unittest.mock import Mock, patch
from visualpilot.viz.session import RemoteSession


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit é dependência de build/painel')
class PanelTests(unittest.TestCase):
    def test_connected_without_tables_is_distinct_from_lost_heartbeat(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        from time import monotonic
        st.cache_resource.clear()
        session=RemoteSession();session.thread=Mock()
        session.thread.is_alive.return_value=True
        session.output.put(dict(kind='collector_status',member='PC',session='one',
                                observed=monotonic(),visible_tables=0))
        app=Path(__file__).resolve().parents[1]/'visualpilot/viz/app.py'
        try:
            with patch('visualpilot.viz.session.RemoteSession',return_value=session):
                at=AppTest.from_file(str(app)).run(timeout=15)
                self.assertFalse(at.exception,list(at.exception))
                self.assertTrue(any('Nenhuma mesa visível' in v.value for v in at.info))
                self.assertFalse(any('Aguardando imagens' in v.value for v in at.info))
                session.collectors['PC']['observed']-=10
                at.run(timeout=15)
                self.assertTrue(any('sem resposta de conexão' in v.value for v in at.warning))
        finally:st.cache_resource.clear()

    def test_disconnected_table_warns_and_hides_old_cards(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        from time import monotonic
        st.cache_resource.clear()
        session = RemoteSession()
        session.output.put(dict(kind='reading',table='one',number=1,
            observed=monotonic()-10,reading=dict(hero=['As','Ks'],board=[],street='preflop')))
        app = Path(__file__).resolve().parents[1] / 'visualpilot/viz/app.py'
        try:
            with patch('visualpilot.viz.session.RemoteSession',return_value=session):
                at = AppTest.from_file(str(app)).run(timeout=15)
                self.assertFalse(at.exception, list(at.exception))
                self.assertTrue(any('desatualizada' in x.value for x in at.warning))
                self.assertTrue(any(json.loads(x.value).get('hero') == [] for x in at.json))
        finally:
            st.cache_resource.clear()

    def test_preview_stale_warning_and_manual_marker(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        import numpy as np
        from time import monotonic
        st.cache_resource.clear()
        session=RemoteSession()
        session.monitor.frame('one',1,np.zeros((40,30,3),dtype=np.uint8))
        session.monitor.tables['one']['received']=monotonic()-10
        app=Path(__file__).resolve().parents[1]/'visualpilot/viz/app.py'
        try:
            with patch('visualpilot.viz.session.RemoteSession',return_value=session):
                at=AppTest.from_file(str(app)).run(timeout=15)
                self.assertFalse(at.exception,list(at.exception))
                self.assertTrue(any('congelada' in w.value for w in at.warning))
                next(b for b in at.button if b.label=='Marcar decisão para revisão').click().run()
                self.assertEqual(session.monitor.snapshot()['one']['events'][-1]['kind'],'manual_review_marker')
        finally:st.cache_resource.clear()

    def test_legacy_launcher_without_build_id_shows_compatibility_message(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        from visualpilot.viz import launcher
        st.cache_resource.clear()
        session=RemoteSession();del session.monitor
        app=Path(__file__).resolve().parents[1]/'visualpilot/viz/app.py'
        try:
            with patch.dict(launcher.__dict__), patch('visualpilot.viz.session.RemoteSession',return_value=session):
                del launcher.BUILD_ID
                at=AppTest.from_file(str(app)).run(timeout=15)
                self.assertFalse(at.exception,list(at.exception))
                self.assertTrue(any('incompatível' in e.value for e in at.error))
        finally:st.cache_resource.clear()

    def test_river_reading_is_rendered_with_table_and_status(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        st.cache_resource.clear()
        session = RemoteSession()
        session.thread = Mock()
        session.thread.is_alive.return_value = True
        session.output.put(dict(kind='partial_cards',table='one',number=1,
                                reading=dict(hero=['Th','4d'],board=['7h','As','Ts','2h','3c'],street='river')))
        app = Path(__file__).resolve().parents[1] / 'visualpilot/viz/app.py'
        try:
            with patch('visualpilot.viz.session.RemoteSession',return_value=session):
                at = AppTest.from_file(str(app)).run(timeout=15)
                self.assertFalse(at.exception, list(at.exception))
                self.assertTrue(any(x.value == 'Mesa 1' for x in at.subheader))
                values = [json.loads(x.value) for x in at.json]
                self.assertTrue(any(v.get('street') == 'river' and v.get('hero') == ['Th','4d'] for v in values))
                at.button[1].click().run(timeout=15)
                self.assertTrue(session.stop.is_set())
        finally:
            st.cache_resource.clear()
