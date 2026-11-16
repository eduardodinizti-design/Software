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


def find_evidencias(tag=None):
    """Checa a release SB40 MAIS NOVA (ou a `tag` dada) e devolve
    (tag, url_evidencias) se o bundle de evidencias JA estiver publicado nela, senao
    (tag, None). SO a mais nova — nao cai em releases velhas (evita re-ingerir o batch
    anterior). O pack dedupa por (flop,rua,nó,combo), mas aqui a regra é: só ingerir
    quando a leva NOVA publicou o evidencias."""
    releases = _get('%s?per_page=20' % API)
    sb40 = [r for r in releases if 'sb-bb40' in (r.get('tag_name') or '')]
    if not sb40:
        return None, None
    # A API NAO ordena por data -> ordena explicitamente pela MAIS NOVA (published_at).
    sb40.sort(key=lambda r: r.get('published_at') or r.get('created_at') or '', reverse=True)
    rel = next((r for r in sb40 if r.get('tag_name') == tag), None) if tag else sb40[0]
    if rel is None:
        return tag, None
    for a in rel.get('assets', []):
        if re.match(r'evidencias-sb40.*\.zip$', a.get('name', '')):
            return rel['tag_name'], a['browser_download_url']
    return rel['tag_name'], None


def main(argv=None):
    a = argv or sys.argv[1:]
    tag = a[0] if a else None
    try:
        found_tag, url = find_evidencias(tag)
    except Exception as e:                             # noqa: BLE001
        print('ERRO ao consultar release:', e); return 1
    if not url:
        print('AINDA NAO PRONTO: release mais nova SB40 = %s, SEM evidencias publicado '
              '(calculos em andamento). Nao ingeri.' % found_tag)
        return 3                                        # 3 = ainda nao pronto
    print('EVIDENCIAS PUBLICADO na %s -> %s' % (found_tag, url))
    tmp = os.path.join(tempfile.gettempdir(), 'evidencias-%s.zip' % found_tag)
    req = urllib.request.Request(url, headers={'User-Agent': 'nvt-sb40-checker'})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'wb') as fh:
        fh.write(r.read())
    print('baixado %d bytes -> %s' % (os.path.getsize(tmp), tmp))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I tira o dir do path
    import ingest_sb40
    rc = ingest_sb40.main([tmp, PACK])
    return rc


if __name__ == '__main__':
    sys.exit(main())
