"""Checa a release SB40 do outro agente e, SE o bundle de evidencias ja estiver
publicado, baixa e INGERE (acumula no pack sb40_srp_shadow). Se nao, reporta que
os calculos ainda estao em andamento (NAO ingere batch pela metade).

REGRA (Eduardo 16/11): rodar isto no inicio da sessao / periodicamente ate as
proximas levas (17+17...) entrarem. A amostragem acumula sozinha.

Uso: python -I checar_ingerir_sb40.py [tag]
  tag opcional (default: varre as releases e pega a mais nova SB40 com evidencias).
Rede: so baixa o evidencias (DADO nao-confiavel) e ingere; nao executa nada dele.
"""
import json
import os
import re
import sys
import tempfile
import urllib.request

REPO = 'eduardodinizti-design/Software'
PACK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'strategy_data', 'postflop_solver', 'sb40_srp_shadow.json.gz')
API = 'https://api.github.com/repos/%s/releases' % REPO


def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'nvt-sb40-checker',
                                               'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _evidencias_url(rel):
    for a in rel.get('assets', []):
        if re.match(r'evidencias-sb40.*\.zip$', a.get('name', '')):
            return a['browser_download_url']
    return None


def find_all_evidencias(tag=None):
    """Devolve a lista [(tag, url_evidencias), ...] de TODAS as releases SB40 que já
    publicaram o bundle de evidencias, da MAIS VELHA p/ a mais nova (ordem de leva).

    Por que todas e não só a mais nova: o outro agente publica uma leva de ~17 flops a
    cada poucas horas; entre duas sessões nossas podem ter saído várias. Pegar só a mais
    nova PULAVA silenciosamente as intermediárias (bug que deixou o pack em 33/101 flops).
    O pack dedupa por (flop,rua,nó,combo), então re-ingerir é inócuo — acumula o que faltar.
    Se `tag` for dado, restringe a essa release só."""
    releases = _get('%s?per_page=50' % API)
    sb40 = [r for r in releases if 'sb-bb40' in (r.get('tag_name') or '')]
    sb40.sort(key=lambda r: r.get('published_at') or r.get('created_at') or '')  # velha->nova
    if tag:
        sb40 = [r for r in sb40 if r.get('tag_name') == tag]
    out = []
    for r in sb40:
        url = _evidencias_url(r)
        if url:
            out.append((r['tag_name'], url))
    return out, sb40[-1]['tag_name'] if sb40 else None


def main(argv=None):
    a = argv or sys.argv[1:]
    tag = a[0] if a else None
    try:
        levas, newest = find_all_evidencias(tag)
    except Exception as e:                             # noqa: BLE001
        print('ERRO ao consultar release:', e); return 1
    if not levas:
        print('AINDA NAO PRONTO: release mais nova SB40 = %s, SEM evidencias publicado '
              '(calculos em andamento). Nao ingeri.' % newest)
        return 3                                        # 3 = ainda nao pronto
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I tira o dir do path
    import ingest_sb40
    print('Levas SB40 com evidencias publicado: %d (ingerindo todas; dedup acumula)' % len(levas))
    rc = 0
    for found_tag, url in levas:
        print('\n--- %s ---\n%s' % (found_tag, url))
        tmp = os.path.join(tempfile.gettempdir(), 'evidencias-%s.zip' % found_tag)
        req = urllib.request.Request(url, headers={'User-Agent': 'nvt-sb40-checker'})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'wb') as fh:
            fh.write(r.read())
        print('baixado %d bytes -> %s' % (os.path.getsize(tmp), tmp))
        rc = ingest_sb40.main([tmp, PACK]) or rc
    return rc


if __name__ == '__main__':
    sys.exit(main())
