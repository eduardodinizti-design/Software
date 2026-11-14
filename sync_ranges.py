"""Sync da fonte de ranges (repo range-coach-pro) -> pack de estudo do bot.

Fluxo: (opcional git pull) -> varre `public/solver/hrc/*.json` -> diff por
sha256 contra o lockfile -> reconstrói o pack de estudo (hrc_ingest) ->
atualiza o lock -> imprime o que mudou + resumo de cobertura (preflop_coverage).

Isto é o "você atualiza um range lá, eu aprendo aqui": você edita/roda a solve
na range-coach-pro (os JSON vão pro GitHub), dá `git pull` no checkout local (ou
usa --git-pull), e este comando re-ingere só a diferença e reconstrói o pack.
O pack entra TODO validated=False (sombra); promover a executável é passo
separado de homologação ao vivo (ver hrc_ingest).

Núcleo puro/testável (diff + lock); IO/git isolados. O JSON baixado é DADO:
só é lido com json.load, nunca executado.
"""
import hashlib
import json
import subprocess
from pathlib import Path

import hrc_ingest
import preflop_coverage

GITHUB_URL = 'https://github.com/eduardodinizti-design/range-coach-pro'
DEFAULT_BRANCH = 'main'
SOLVER_SUBDIR = 'public/solver/hrc'


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scan_dir(hrc_dir, glob='*.json'):
    """{nome_arquivo: sha256} de cada solve (ignora manifest.json). Determinístico."""
    out = {}
    for p in sorted(Path(hrc_dir).glob(glob)):
        if p.name == 'manifest.json':
            continue
        out[p.name] = sha256_file(p)
    return out


def diff_sources(current, lock):
    """Compara {nome:sha} atual vs lock. Devolve added/changed/removed/unchanged.
    Puro — é o coração do sync e o que os testes fixam."""
    cur, old = dict(current or {}), dict(lock or {})
    added = sorted(k for k in cur if k not in old)
    removed = sorted(k for k in old if k not in cur)
    changed = sorted(k for k in cur if k in old and cur[k] != old[k])
    unchanged = sorted(k for k in cur if k in old and cur[k] == old[k])
    return dict(added=added, changed=changed, removed=removed, unchanged=unchanged)


def load_lock(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding='utf-8')).get('files', {})
    except (ValueError, OSError):
        return {}


def write_lock(path, files, *, source):
    Path(path).write_text(json.dumps(
        dict(files=files, source=source), ensure_ascii=False, indent=1), encoding='utf-8')


def git_update(source_dir, *, url=GITHUB_URL, branch=DEFAULT_BRANCH):
    """Clona (shallow) se ausente, senão `git pull`. Devolve (ok, msg). Falha de
    rede NÃO derruba o sync: segue com o que já está em disco."""
    src = Path(source_dir)
    try:
        if (src / '.git').exists():
            r = subprocess.run(['git', '-C', str(src), 'pull', '--ff-only'],
                               capture_output=True, text=True, timeout=180)
        else:
            src.parent.mkdir(parents=True, exist_ok=True)
            r = subprocess.run(['git', 'clone', '--depth', '1', '--branch', branch,
                                url, str(src)], capture_output=True, text=True, timeout=300)
        ok = r.returncode == 0
        return ok, (r.stdout + r.stderr).strip()[-500:]
    except (OSError, subprocess.SubprocessError) as e:
        return False, 'git indisponível: %s' % e


def sync(source_dir, out_pack, lock_path, *, git_pull=False, url=GITHUB_URL,
         branch=DEFAULT_BRANCH):
    """Executa o sync completo. Devolve um relatório (dict) com o diff, nº de nós
    e o resumo de cobertura. Reconstrói o pack a partir de TODOS os arquivos
    atuais (o pack é sempre um retrato completo da fonte)."""
    report = {'git': None}
    if git_pull:
        ok, msg = git_update(source_dir, url=url, branch=branch)
        report['git'] = dict(ok=ok, msg=msg)

    hrc_dir = Path(source_dir) / SOLVER_SUBDIR
    if not hrc_dir.exists():
        hrc_dir = Path(source_dir)              # já aponta direto p/ a pasta hrc
    current = scan_dir(hrc_dir)
    if not current:
        raise FileNotFoundError('nenhuma solve HRC em %s' % hrc_dir)

    report['diff'] = diff_sources(current, load_lock(lock_path))

    paths = [hrc_dir / name for name in sorted(current)]
    pack = hrc_ingest.build_pack(paths)
    Path(out_pack).parent.mkdir(parents=True, exist_ok=True)
    Path(out_pack).write_text(json.dumps(pack, ensure_ascii=False), encoding='utf-8')
    write_lock(lock_path, current, source=dict(dir=str(hrc_dir), url=url, branch=branch))

    report['nodes'] = len(pack['nodes'])
    report['files'] = len(current)
    report['coverage'] = preflop_coverage.summarize(pack)
    report['out'] = str(out_pack)
    return report


def _cli(argv=None):
    import argparse
    default_src = ('C:/Meus Projetos/Aplicativos/range-coach-pro-'
                   '356340d98ec068ef07fd3d6221bdc5c53bf4dff7')
    ap = argparse.ArgumentParser(description='Sync range-coach-pro -> pack de estudo')
    ap.add_argument('--source', default=default_src,
                    help='checkout do range-coach-pro (contém public/solver/hrc)')
    ap.add_argument('--out', default='strategy_data/preflop_hrc/nvt-preflop-hrc-20261114.json')
    ap.add_argument('--lock', default='strategy_data/preflop_hrc/.hrc-sync-lock.json')
    ap.add_argument('--git-pull', action='store_true', help='git clone/pull antes de ingerir')
    ap.add_argument('--branch', default=DEFAULT_BRANCH)
    args = ap.parse_args(argv)
    rep = sync(args.source, args.out, args.lock, git_pull=args.git_pull, branch=args.branch)
    d, cov = rep['diff'], rep['coverage']
    if rep['git']:
        print('git:', 'OK' if rep['git']['ok'] else 'FALHOU (seguindo com o disco)')
    print('arquivos=%d  +novos=%d  ~alterados=%d  -removidos=%d  =iguais=%d'
          % (rep['files'], len(d['added']), len(d['changed']), len(d['removed']), len(d['unchanged'])))
    for k in ('added', 'changed', 'removed'):
        if d[k]:
            print('  %s: %s' % (k, ', '.join(d[k])[:300]))
    print('nós=%d -> %s' % (rep['nodes'], rep['out']))
    print('cobertura: contextos=%d (completos=%d) regime=%s'
          % (cov['contexts'], cov['contexts_full'], cov['by_regime']))
    return 0


if __name__ == '__main__':
    raise SystemExit(_cli())
