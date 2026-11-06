"""Inventory labeled local evidence without counting augmentations as new samples."""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1];docs=root/'docs/table-reading'
labels=json.loads((docs/'development-labels.json').read_text())['tables']
board=json.loads((docs/'board-development-results.json').read_text())['results']
buttons=json.loads((docs/'button-development-observations.json').read_text())
ranks='23456789TJQKA';suits='cdhs';deck={r+s for r in ranks for s in suits}
seen=set();entries=[]
for row in labels:
 key=(row['sha256'],tuple(row['box']))
 if key in seen:raise ValueError('Duplicate labeled crop')
 seen.add(key)
 file=args.assets/row['source'];actual=hashlib.sha256(file.read_bytes()).hexdigest()
 if actual!=row['sha256']:raise ValueError('Fixture mismatch: '+row['source'])
 entries.append(dict(source=row['source'],sha256=actual,box=row['box'],hero_expected=row['expected'],evidence='REAL_IMAGE_DEVELOPMENT',independent_holdout=False))
def coverage(cards):
 counts=Counter(cards)
 if set(counts)-deck:raise ValueError('Invalid card label')
 return dict(occurrences=sum(counts.values()),unique_cards=len(counts),card_counts=dict(sorted(counts.items())),
             rank_counts=dict(Counter(c[0] for c in cards)),suit_counts=dict(Counter(c[1] for c in cards)),
             missing_cards=sorted(deck-set(cards)),missing_ranks=[r for r in ranks if not any(c[0]==r for c in cards)])
hero=[c for row in labels for c in row['expected']]
board_cards=[c for row in board for c in row['expected']]
# OCR outputs are observations, not independent human labels for buttons.
button_observations=Counter(b.get('action') or b.get('kind') or 'UNIDENTIFIED' for row in buttons for b in row['result']['buttons'])
report=dict(scope='Labeled local corpus only. Distinct screenshots/crops are not necessarily independent hands.',
            source_images=len({r['sha256'] for r in labels}),table_crops=len(entries),independent_holdout_images=0,
            hero=coverage(hero),board=coverage(board_cards),
            board_rows_by_count=dict(Counter(str(len(r['expected'])) for r in board)),
            crop_sizes=sorted({f"{r['box'][2]}x{r['box'][3]}" for r in labels}),
            buttons=dict(scope='OCR observations; not a fully human-labeled acceptance set',observations=dict(button_observations),
                         rows_detected=sum(bool(r['result']['buttons']) for r in buttons),total_regions=len(buttons)),
            excluded_from_independent_coverage=['resizes','brightness/blur variants','synthetic scenes','mock OCR','chat images without locally available original PNG'],
            entries=entries)
(docs/'COVERAGE.json').write_text(json.dumps(report,indent=2))
lines=['# Cobertura auditável do corpus local','',
       f"{report['source_images']} arquivos de imagem distintos; {len(entries)} recortes rotulados. Nenhum conjunto independente de avaliação. Arquivos verificados por SHA-256. Não equivalem necessariamente a mãos independentes.",'',
       '| Grupo | Ocorrências rotuladas | Identidades distintas de 52 | Ranks ausentes |',
       '|---|---:|---:|---|',
       f"| Hero | {len(hero)} | {report['hero']['unique_cards']} | {', '.join(report['hero']['missing_ranks'])} |",
       f"| Board | {len(board_cards)} | {report['board']['unique_cards']} | {', '.join(report['board']['missing_ranks'])} |",'',
       '## Frequência por carta (Hero / board)','', '| Carta | Hero | Board |','|---|---:|---:|']
for r in ranks:
 for s in suits:
  c=r+s;lines.append(f"| {c} | {hero.count(c)} | {board_cards.count(c)} |")
lines += ['', '## Lacunas prioritárias','',
          '- Board real: só um flop rotulado (Jc/5d/3c); nenhum turn ou river real rotulado neste corpus.',
          '- Hero: ampliar os ranks ausentes e pares que geraram erro (8/3, 9 e K), com exemplos novos separados da calibração.',
          '- Botões: saídas OCR disponíveis, mas faltam rótulos humanos completos por captura e exemplos independentes de Check/Bet e valores.',
          '- Geometria: os tamanhos listados são tamanhos existentes, não faixa certificada; ainda falta definir a disposição operacional de seis mesas.',
          '- Mesa sem ação e lobby: adicionar exemplos originais rotulados, incluindo a rejeição conhecida do menu.',
          '- Imagens embutidas no chat e confirmações do usuário são evidência qualitativa; não entram como PNGs reproduzíveis nem como novas amostras independentes.',
          '- Transformações de uma imagem contam como testes de robustez, nunca como novas cartas/mãos reais.', '',
          '## Tamanhos presentes','', ', '.join(report['crop_sizes']), '',
          'Este inventário mede presença de exemplos, não precisão de reconhecimento. Não inferir 100% por testes aprovados nem combinar cobertura Hero com board: são regiões e extrações diferentes.']
(docs/'COVERAGE.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({k:report[k] for k in ['source_images','table_crops','hero','board','board_rows_by_count','crop_sizes','buttons']},indent=2))
