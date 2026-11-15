"""Build a separately checked-out TexasSolver with GCC; lab Linux, no GUI deps.

No external source is modified/copied into Software. Requires fmt headers,
GCC with OpenMP and the upstream evaluator resources. See the delivery TXT.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True)
    p.add_argument('--fmt-include', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--compiler', default='g++')
    p.add_argument('--chance-private-cards', type=int, choices=(2, 4), default=4,
                   help='4 correct HU; 2 reproduces the upstream counterexample in the lab')
    args = p.parse_args()
    root, out = Path(args.source).resolve(), Path(args.out).resolve()
    if out.exists():
        p.error('output already exists; choose a new path to preserve it')
    sources = []
    for part in ('', 'compairer', 'nodes', 'ranges', 'tools', 'trainable', 'solver', 'runtime'):
        # Unused legacy CfrSolver has an undefined vtable in this upstream commit.
        sources.extend(str(x) for x in sorted((root / 'src' / part).glob('*.cpp'))
                       if x.name != 'CfrSolver.cpp')
    out.parent.mkdir(parents=True, exist_ok=True)
    # Add one console command in a separate generated translation unit. The
    # original checkout is untouched. This makes the tree's raise budget real,
    # rather than silently using upstream's hardcoded four aggressions.
    original = root / 'src/tools/CommandLineTool.cpp'
    text = original.read_text()
    anchor = '}else if(command == "set_max_iteration"){'
    if text.count(anchor) != 1:
        raise SystemExit('unsupported CommandLineTool source; bounded patch not applied')
    patched = text.replace(anchor, '}else if(command == "set_raise_limit"){\n'
                           '        this->raise_limit = stoi(paramstr);\n    ' + anchor)
    generated = out.with_name(out.name + '.CommandLineTool.cpp')
    generated.write_text(patched)
    sources = [str(generated) if x == str(original) else x for x in sources]
    chance_patches = {}
    for filename in ('PCfrSolver.cpp', 'BestResponse.cpp'):
        original_chance = root / 'src/solver' / filename
        chance_text = original_chance.read_text()
        before = 'node->getCards().size() - Card::long2board(current_board).size() - 2'
        if chance_text.count(before) != 1:
            raise SystemExit('unsupported chance source: ' + filename)
        chance_text = chance_text.replace(before,
            'node->getCards().size() - Card::long2board(current_board).size() - ' + str(args.chance_private_cards))
        changed = out.with_name(out.name + '.' + filename)
        changed.write_text(chance_text)
        sources = [str(changed) if x == str(original_chance) else x for x in sources]
        chance_patches[filename] = hashlib.sha256(chance_text.encode()).hexdigest()
    command = [args.compiler, '-std=c++17', '-O2', '-fopenmp', '-DFMT_HEADER_ONLY',
               '-I' + str(root / 'include'), '-I' + str(Path(args.fmt_include).resolve())] + sources + ['-o', str(out)]
    subprocess.run(command, check=True)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True)
    manifest = dict(source_repository='https://github.com/bupticybee/TexasSolver', source_commit=commit,
                    source_dirty=bool(dirty), binary_sha256=sha, command=command,
                    supports_set_raise_limit=True,
                    hu_chance_denominator_cards=args.chance_private_cards, generated_chance_sources_sha256=chance_patches,
                    generated_console_sha256=hashlib.sha256(patched.encode()).hexdigest(),
                    source_patch=('add set_raise_limit; HU chance denominator subtracts %d private cards in CFR and BR; original checkout unchanged' % args.chance_private_cards),
                    license='AGPL-3.0 backend installed separately; not bundled with Software')
    out.with_name(out.name + '.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'binary': str(out), 'sha256': sha, 'source_commit': commit, 'source_dirty': bool(dirty)}))


if __name__ == '__main__':
    main()
