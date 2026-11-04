"""Painel Streamlit da Central VisualPilot."""
from __future__ import annotations

from pathlib import Path

from visualpilot.agent.connector import RangeCoachConnector


def cloud_status(config_path="nvt_config.ini", connector_factory=RangeCoachConnector.from_ini):
    if not Path(config_path).is_file():
        return {"connected": False, "label": "⚪ Nuvem não configurada"}
    try:
        return connector_factory(config_path).diagnose()
    except Exception as exc:
        return {"connected": False, "label": "🔴 Configuração da nuvem inválida",
                "error": type(exc).__name__}


def render_cloud_diagnostic(st=None, config_path="nvt_config.ini"):
    """Pode ser chamado pelo app Streamlit sem tornar Streamlit uma dependência base."""
    if st is None:
        import streamlit as st
    status = cloud_status(config_path)
    st.subheader("Sincronização Range Coach Pro")
    st.write(status["label"])
    if status.get("latency_ms") is not None:
        st.caption(f"Latência do diagnóstico: {status['latency_ms']:.1f} ms")
    return status


def render_table(st, session, key, event, preview, thumbnail_width):
    import json
    st.subheader(f"Mesa {event.get('number', preview.get('number', key))}")
    picture, summary = st.columns([1, 1.35])
    with picture:
        if preview.get('preview'):
            st.image(preview['preview'], width=thumbnail_width)
            if st.button('Ampliar imagem', key='enlarge-'+key):
                @st.dialog('Imagem da mesa', width='large')
                def enlarged():
                    st.image(preview['preview'], width=400)
                    st.caption(f"Último recebimento (UTC): {preview.get('received_at')}")
                enlarged()
        else:
            st.caption('Aguardando imagem para prévia.')
    with summary:
        frame_age = preview.get('frame_age')
        age = event.get('age_seconds')
        st.caption(f"Imagem recebida há: {frame_age:.1f} s" if frame_age is not None else 'Imagem: pendente')
        if frame_age is not None and frame_age > 5:
            st.warning('Transmissão sem imagens recentes. A prévia acima está congelada.')
        if event.get('stale'):
            st.warning('Leitura desatualizada. Verifique se o coletor continua aberto no PC.')
        reading = event.get('reading', {})
        st.write('Cartas do Hero: ' + (' · '.join(reading.get('hero') or []) or 'pendente'))
        st.write('Board: ' + (' · '.join(reading.get('board') or []) or 'pendente / sem cartas reconhecidas'))
        st.caption('Etapa: ' + str(reading.get('street') or 'desconhecida'))
        transport_verified=(event.get('observation') or {}).get('transport_verified')
        if age is not None:
            st.caption(f"Limite de idade da imagem: {age:.1f} s" if transport_verified else f"Última leitura há {age:.1f} s")
        if transport_verified is False:
            st.warning('Idade anterior à chegada na Central não comprovada.')
        buttons = reading.get('hero_buttons') or reading.get('actions') or []
        labels = []
        for button in buttons:
            if isinstance(button, dict):
                label = str(button.get('action', 'pendente')).title()
                if button.get('amount') is not None:
                    label += f" {button['amount']} {button.get('unit') or ''}"
                elif button.get('amount_status') == 'pending': label += ' (valor pendente)'
                labels.append(label)
            else: labels.append(str(button))
        st.text(' · '.join(labels) or 'Botões: pendentes / não observados')
        if preview.get('button_seconds') is not None:
            st.caption(f"Tempo desde a observação dos botões: {preview['button_seconds']:.1f} s")
    if st.button('Marcar decisão para revisão', key='mark-'+key):
        session.monitor.mark(key)
        preview = session.monitor.snapshot().get(key, preview)
        st.success('Momento marcado no diário. Nenhuma jogada foi executada.')
    with st.expander('Detalhes da leitura e qualidade'):
        st.write(f"Pote: {reading.get('pot') or 'pendente'} · Stack: {reading.get('hero_stack') or 'pendente'}")
        st.write('Ações visíveis dos jogadores:')
        for action in reading.get('observed_actions') or []:
            st.text(f"{action.get('player_label') or 'jogador pendente'}: {action.get('action') or 'pendente'}" if isinstance(action, dict) else str(action))
        if reading.get('reason'): st.caption(reading['reason'])
        if event.get('latency') is not None:
            if transport_verified:
                st.caption(f"Limite de idade ao publicar: {event['latency']:.2f} s, incluindo captura, transporte e processamento.")
            else:
                st.caption(f"Idade da amostra ao publicar: {event['latency']:.2f} s; não mede o tempo total de rede.")
        st.caption('Intervalos de botões são estimativas visuais; não confirmam clique ou ação escolhida.')
        st.json(reading)
        st.json(event.get('field_confirmation', {}))
    with st.expander('Momentos e evidências da mesa'):
        st.caption('Imagens amostradas a cada 2 s, até 64 MB por sessão; não é vídeo contínuo. Até 30 eventos recentes abaixo.')
        events = preview.get('events', [])
        st.json(events)
        st.download_button('Baixar eventos recentes', json.dumps(events, ensure_ascii=False, indent=2),
                           file_name='momentos.json', mime='application/json', key='download-'+key)


def main():
    import streamlit as st
    st.set_page_config(page_title="NVT Poker Team — VisualPilot", page_icon="♠", layout="wide", initial_sidebar_state="collapsed")
    st.header("VisualPilot — Central de observação")
    st.caption('NVT Poker Team · mesas e fichas fictícias · painel compacto v1')
    with st.sidebar:
        from visualpilot.viz import launcher
        build_id = getattr(launcher, "BUILD_ID", "versão anterior — utilize o pacote completo atual da Central")
        st.caption(f"Versão da Central: {build_id}")
        columns_mode = st.selectbox('Mesas por linha', ['Automático', '2', '3'])
        thumbnail_width = st.select_slider('Largura da miniatura', options=[120,150,190,230], value=150)
        render_cloud_diagnostic(st)
    from visualpilot.viz.session import RemoteSession
    @st.cache_resource
    def controller(): return RemoteSession()
    session = controller()
    if not hasattr(session, 'monitor'):
        st.error('Esta pasta contém uma Central anterior, incompatível com o painel compacto. Abra a Central do pacote completo atual. Os registros existentes foram preservados.')
        return
    start, stop = st.columns(2)
    start.button('Iniciar coleta', on_click=session.start)
    stop.button('Parar coleta', on_click=session.stop.set)
    @st.fragment(run_every=1)
    def readings():
        session.poll()
        if getattr(session,'transport_warning',None):st.warning(session.transport_warning)
        active = session.thread is not None and session.thread.is_alive()
        st.caption('Coleta ativa' if active else 'Coleta parada')
        if active:
            for member,state in session.collectors.items():
                if not state['connected']:
                    st.warning(f'Coletor {member}: sem resposta de conexão há {state["age_seconds"]:.1f} s.')
                elif state.get('discovery_state')=='error':
                    st.warning(f'Coletor {member} conectado, mas houve falha ao examinar os monitores.')
                elif state.get('discovery_state')=='pending':
                    st.caption(f'Coletor {member} conectado. Aguardando descoberta de mesas.')
                elif state['visible_tables']==0:
                    st.info(f'Coletor {member} conectado. Nenhuma mesa visível informada.')
                elif state['visible_tables'] is None:
                    st.caption(f'Coletor {member} conectado. Aguardando descoberta de mesas.')
                else:
                    st.caption(f'Coletor {member} conectado. Mesas visíveis informadas: {state["visible_tables"]}.')
        if session.error: st.error(session.error)
        if session.folder:
            with st.expander('Pasta dos registros'): st.caption(f'Registros da sessão: {session.folder}')
        previews = session.monitor.snapshot()
        if session.monitor.error: st.warning(session.monitor.error)
        keys = list(dict.fromkeys([*session.tables, *previews]))
        count = (3 if len(keys) in (3,5,6) else 2) if columns_mode=='Automático' else int(columns_mode)
        for offset in range(0, len(keys), count):
            columns = st.columns(count)
            for column, key in zip(columns, keys[offset:offset+count]):
                with column:
                    with st.container(border=True):
                        render_table(st, session, key, session.tables.get(key, {}), previews.get(key, {}), thumbnail_width)
        if active and not keys and not any(s['connected'] and s['visible_tables']==0
                and s.get('discovery_state','ready')=='ready' for s in session.collectors.values()):
            st.info('Aguardando imagens do coletor.')
    readings()


if __name__ == '__main__':
    main()
