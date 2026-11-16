"""One checked handoff after BOTH Windows data workflows succeed."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import REPOSITORY
from strategy.batch_jobs import atomic_json
from strategy.blind_war import SB40_TAG
from strategy.campaign import CLOSE32_TAG
from strategy.state_contract import StrategyError
from strategy.texassolver_backend import file_hash
from collect_hu_campaign_evidence import main as collect


def await_success(run_ids):
    started=time.monotonic()
    while time.monotonic()-started<13500:
        states=[]
        for run_id in run_ids:
            r=subprocess.run(['gh','api',f'repos/{REPOSITORY}/actions/runs/{run_id}'],capture_output=True,text=True,check=True,timeout=45)
            value=json.loads(r.stdout);states.append((run_id,value['status'],value['conclusion']))
        if any(s=='completed' and c!='success' for _,s,c in states):raise StrategyError('FINAL_WINDOWS_WORKFLOW_FAILED:'+str(states))
        if all(s=='completed' and c=='success' for _,s,c in states):return
        print(json.dumps(dict(waiting_for_actual_windows_workflows=states)),flush=True);time.sleep(30)
    raise StrategyError('FINAL_WINDOWS_WORKFLOWS_WAIT_TIMEOUT')


def latest(folder,pattern):
    values=list(folder.glob(pattern))
    if not values:raise StrategyError('CHECKED_FINAL_ARTIFACT_REQUIRED:'+pattern)
    attempts=[(int(m[1]),path) for path in values if (m:=re.search(r'-a([0-9]+)\.[^.]+$',path.name))]
    if len(attempts)!=len(values):raise StrategyError('UNAMBIGUOUS_RUN_ATTEMPTS_REQUIRED:'+pattern)
    return max(attempts,key=lambda item:item[0])[1]


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--btn-run',required=True)
    p.add_argument('--sb-run',required=True);p.add_argument('--output',required=True);args=p.parse_args(argv)
    output=Path(args.output)
    if output.exists():raise StrategyError('COMBINED_DELIVERY_OUTPUT_MUST_BE_NEW')
    await_success([args.btn_run,args.sb_run]);output.mkdir(parents=True);published=output/'published'
    collect(['--output',str(published),'--delivery-run',args.btn_run,'--windows-run',args.btn_run,
        '--sb-delivery-run',args.sb_run,'--sb-windows-run',args.sb_run])
    btn_file=latest(published,'entrega-btn32-'+args.btn_run+'-a*.json');sb_file=latest(published,'entrega-sb40-'+args.sb_run+'-a*.json')
    btn=json.loads(btn_file.read_text());sb=json.loads(sb_file.read_text())
    proof=json.loads((published/'publication-proof.json').read_text());stamp=os.environ['GITHUB_RUN_ID']+'-a'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
    if (btn['complete_distinct_flop_models']!=32 or sb['complete_distinct_flop_models']!=1
            or proof['status']!='PASS'):raise StrategyError('THIRTY_TWO_PLUS_ONE_CHECKED_MODELS_REQUIRED')
    contracts={}
    for family,run in (('btn32',args.btn_run),('sb40',args.sb_run)):
        text=latest(published,'windows-contracts-'+family+'-'+run+'-a*.txt').read_text(encoding='utf-8-sig')
        match=re.search(r'Ran (\d+) tests',text)
        if not match or not re.search(r'\nOK(?: |\n|\r|$)',text):raise StrategyError('FINAL_WINDOWS_CONTRACTS_NOT_PASS')
        contracts[family]=int(match[1])
    source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    summary=dict(schema='software.hu-32-and-sb40-combined-delivery.v1',status='PASS',
        btn_bb25_complete_distinct_flops=32,sb_bb40_full_reference_pilot_flops=1,
        new_windows_policy_transfers=16,new_confirmed_synthetic_hands=16,
        transfer_count_semantics='DISTINCT_VALIDATED_MODELS; repeated downloads for a repaired fixture are not new models',
        new_json_street_roundtrips=48,new_exact_suit_street_queries=48,
        windows_contract_tests=contracts,source_commit=source_commit,
        btn_summary=btn_file.name,sb_summary=sb_file.name,
        source_ranges='USER_APPROVED_NVT_REFERENCE_NOT_DIRECT_HRC_CERTIFICATION',
        native_global_gap_independently_certified=False,pppoker_windows_validated=False,user_notebook_validated=False,
        source_workflows=dict(btn_windows=args.btn_run,sb_windows=args.sb_run))
    atomic_json(output/f'consolidado-32-sb40-{stamp}.json',summary)
    bcase=sb['inventory'][0]
    lines=['SOFTWARE ORIGINAL — 32 FLOPS BTN x BB E PILOTO BLIND WAR 40 BB','',
        'CONCLUIDO: 32 flops distintos BTN x BB de 25 BB com arvores completas, publicados e consultaveis.',
        'CONCLUIDO: 1 flop completo SB x BB de 40 BB, As 7d 2c, com respostas de flop, turn e river.',
        'O piloto SB40 e outra familia de jogo; nao e contado como um 33o flop distinto do banco BTN.','',
        f"BTN: {btn['total_public_nodes']:,} estados publicos, {btn['total_policy_file_bytes']/1024**3:.2f} GiB de politicas SQLite.",
        f"SB40: {sb['total_public_nodes']:,} estados publicos, {sb['total_policy_file_bytes']/1024**3:.2f} GiB de politica SQLite.",
        f"SB40: {bcase['iterations']} iteracoes reais; gap global NATIVO {bcase['global_gap_bb']:.9f} BB.",
        'Os 15 modelos novos que completam 32 e o piloto SB40 foram baixados integralmente em runners Windows.',
        'Foram conferidos partes, ZIPs, SQLite, identidades, ranges, menu e consultas nas tres ruas.',
        '16 maos sinteticas completas ate showdown; 48 consultas JSON e 48 consultas com bijecao exata de naipes.',
        f"Contratos Windows: {contracts}; nenhum desses testes e uma sessao real no PPPoker.",'',
        'COMO O BOT APRENDEU',
        'library.json aponta para politicas completas no disco: acoes, frequencias por combinacao, sizes e respostas.',
        'O bot consulta o no correspondente ao board, posicoes, dinheiro e historico confirmado.',
        'Nao se trata de uma rede neural treinada para qualquer situacao. Outros ranks, stacks e chegadas precisam de politicas proprias.',
        'O arquivo SQLite guarda a arvore completa dentro do menu estudado. JSONL completo e um export opcional verificado no a no.',
        'Parametros e checkpoints de convergencia ficam nos reports dos bancos; nao sao snapshots CFR para retomar cada iteracao.','',
        'MODELOS',
        'BTN: nove jogadores originalmente, BTN open 2,5 BB x BB call, 25 BB antes do open, sem ante, pote 5,5 BB e 22,5/22,5 BB restantes.',
        'SB40: nove jogadores originalmente, sete folds, SB open 2 BB x BB call, BBA 1 BB, ambos 40 BB antes das postagens.',
        'Chegada SB40: pote 5 BB, stacks SB 38 BB e BB 37 BB; SB age primeiro no pos-flop.',
        'Menu: bet 1/3, raise de 100% do pote e all-in, com duas agressoes por rua. Frequencias e sizes efetivos sao preservados.',
        'Ranges NVT autorizados como referencia. Os rotulos HRC/validado do exportador nao sao certificacao HRC independente.','',
        'CORRECOES REPRODUZIDAS NESTE LOTE',
        '1. Monitor nao encerra um lote quando o worker conclui e remove o export temporario.',
        '2. Verificador aceita checks e linhas mistas suportadas; confere o ID e o size exatos da acao, sem exigir tres apostas.',
        '3. All-in nativo baseado em stack efetivo e traduzido para all-in fisico do jogador que cobre, com devolucao do excedente.',
        '   O SB40 convergido em 171 iteracoes foi recuperado do export original; o calculo CFR nao foi repetido.',
        '   O hash do executavel original nao foi retido no artifact de falha; essa ausencia esta registrada na proveniencia.',
        '   A medicao de pico RSS recuperada abrange o conversor; nao e apresentada como o pico do treinamento original.',
        '4. Metadados do GitHub usam a autenticacao do workflow; o token nao e enviado aos downloads publicos nem a outro host.',
        '5. Em empate, os saldos finais sozinhos nao identificam os sizes intermediarios. A fixture sintetica retem o rotulo do pote final.',
        '   Sem essa evidencia, o coletor continua rejeitando caminhos ambiguos; nenhum historico real e adivinhado.',
        'As transferencias Windows ja aprovadas foram reaproveitadas com a origem real de cada receipt preservada.',
        'As falhas iniciais e sua recuperacao estao documentadas; os dois workflows finais Windows precisam estar verdes para esta entrega.','',
        'INSTALAR',
        'Baixe o ZIP Software-HU-32-SB40 desta entrega e extraia em pasta nova, preservando a instalacao antiga.',
        'Instale Python 3.12 x64 e requirements.txt conforme docs/GUIA_32_FLOPS_E_BLIND_WAR_40BB_20261115.txt.',
        'Execute BAIXAR_BANCO_BTN_BB_32.bat e/ou BAIXAR_BLIND_WAR_40BB.bat. Eles instalam dados e nao acionam o mouse.',
        'Indices: runtime/hu/btn32/bank/library.json e runtime/hu/sb40/bank/library.json.',
        'Informe o indice correto ao Software com --postflop-library. Esta entrega usa uma familia por sessao, sem troca automatica.',
        'Comece a observacao antes da mao para confirmar blinds, open e chegada ao flop.',
        'Os bancos ficam no disco com cache limitado; o notebook de 8 GB nao carrega as arvores inteiras na RAM.',
        'Os processos nativos terminaram; temporarios pertencentes aos workers foram removidos apos validacao. Bancos e trabalho antigo foram preservados.','',
        'PENDENCIAS CONCRETAS',
        'SB limp x BB check de 40 BB: faltam os ranges proprios no upload. O complemento do range de raise nao foi usado como limp.',
        'Esse ramo precisa de perfil de chegada limpado: pote 3 BB, SB 39 BB e BB 38 BB com BBA 1 BB, mais testemunho de limp/check.',
        '3-bet pots, outros sizes/stacks, multiway, ICM e PKO precisam de modelos proprios.',
        'Gap nativo <= 0,5% do pote nao certifica por metodo independente o gap global; um river condicional por modelo foi enumerado independentemente.',
        'EV independente por acao nao esta salvo em todos os nos; ev_bb pode ser null.',
        'Leitura, sincronizacao, efeito real do clique e desempenho com varias mesas ainda precisam de validacao no PPPoker Windows do notebook.',
        'Em uma mao real empatada cujo pote final nao foi capturado, a confirmacao completa do historico pode continuar ambigua.',
        'O caso historico 8h -> 3h continua pendente de reproducao no mesmo tema. Nenhum limiar de leitura foi reduzido.','',
        'EVIDENCIAS',f'https://github.com/{REPOSITORY}/pull/14',
        f'https://github.com/{REPOSITORY}/actions/runs/{args.btn_run}',f'https://github.com/{REPOSITORY}/actions/runs/{args.sb_run}',
        f'https://github.com/{REPOSITORY}/releases/tag/{CLOSE32_TAG}',f'https://github.com/{REPOSITORY}/releases/tag/{SB40_TAG}',
        'Orientacao tecnica: docs/CONTRATO_CONSUMO_HU_E_PROXIMA_BLIND_WAR_20261115.txt',f'Codigo desta entrega: {source_commit}']
    report=output/f'ENTREGA_32_FLOPS_E_BLIND_WAR_40BB-{stamp}.txt';report.write_text('\n'.join(lines)+'\n')
    source=output/f'Software-HU-32-SB40-{source_commit[:8]}-{stamp}.zip'
    subprocess.run(['git','archive','--format=zip','--prefix=Software/','HEAD','-o',str(source)],check=True)
    with zipfile.ZipFile(source,'a',compression=zipfile.ZIP_DEFLATED) as z:z.write(report,'Software/RELATORIO_32_E_SB40.txt')
    manifest=output/f'source-combined-{stamp}.json';atomic_json(manifest,dict(asset=source.name,sha256=file_hash(source),
        bytes=source.stat().st_size,source_commit=source_commit,contains_full_policy_data=False))
    evidence=output/f'evidencias-32-sb40-{stamp}.zip'
    with zipfile.ZipFile(evidence,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in published.iterdir():z.write(path,path.name)
    for tag in (CLOSE32_TAG,SB40_TAG):
        for path in (report,source,manifest,evidence,output/f'consolidado-32-sb40-{stamp}.json'):
            subprocess.run(['gh','release','upload',tag,'--repo',REPOSITORY,str(path)],check=True)
    print(json.dumps(dict(status='PASS',report=report.name,source=source.name,models='32 BTN25 plus 1 SB40')));return 0


if __name__=='__main__':raise SystemExit(main())
