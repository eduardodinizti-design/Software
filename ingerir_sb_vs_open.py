"""Ingere as ranges de SB-vs-open (image.png, paleta custom) como nós vs_open AUTORIDADE
(validated=True) no pack do Eduardo. Mapeia opener->painel. Mata o flat de marginal do SB."""
import json
import os

import hrc_ingest
import ingerir_ranges_transcritos as ing
import transcrever_sb_vs_open as T

EDU = r'C:\Meus Projetos\Aplicativos\nvt-ranges-eduardo.json'
SOURCE = {'name': 'eduardo_gtow_sb_vs_open'}
# opener -> painel
OPENER_PANEL = {'UTG': 'SB x EP', 'UTG+1': 'SB x EP', 'UTG+2': 'SB x EP',
                'LJ': 'SB x MP', 'HJ': 'SB x MP', 'CO': 'SB x CO', 'BTN': 'SB x BTN'}
STACK = 30


def build_nodes():
    panels = T.read_all()
    nodes = []
    for opener, pname in OPENER_PANEL.items():
        hands = panels[pname]                       # {hand: {action: freq}}
        freq = {'call': ing._arr(hands, ['call']),
                'three_bet': ing._arr(hands, ['three_bet']),
                'all_in': ing._arr(hands, ['all_in'])}
        freq['fold'] = hrc_ingest._derive_fold(freq)
        node = hrc_ingest._node(ing._ctx(STACK), 'vs_open', 'SB', (opener,),
                                freq, {}, SOURCE, 'bb')
        node['validated'] = True                    # AUTORIDADE (a range do Eduardo manda)
        nodes.append(node)
    return nodes


def main():
    pack = json.load(open(EDU, encoding='utf-8'))
    new = build_nodes()
    # remove nós SB vs_open @30 já existentes desta fonte (idempotente)
    # idempotente DE VERDADE: remove TODO nó SB vs_open (qualquer fonte/stack) antes de re-adicionar
    # — a transcrição anterior usou fonte diferente e duplicava. (RFI = spot 'open_raise', intacto.)
    keep = [n for n in pack['nodes']
            if not (n.get('spot') == 'vs_open' and n.get('hero') == 'SB')]
    pack['nodes'] = keep + new
    json.dump(pack, open(EDU, 'w', encoding='utf-8'), ensure_ascii=False)
    print('ingeridos %d nós SB vs_open @30bb (total pack=%d)' % (len(new), len(pack['nodes'])))


if __name__ == '__main__':
    main()
