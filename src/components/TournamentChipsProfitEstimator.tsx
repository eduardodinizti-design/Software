import React, { useState, useMemo } from 'react';
import {
  Coins,
  TrendingUp,
  TrendingDown,
  ShieldCheck,
  CheckCircle2,
  AlertOctagon,
  Percent,
  Sliders,
  Download,
  HelpCircle,
  Award,
  Sparkles,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  FileSpreadsheet,
  Clock,
  Timer,
  Zap,
  Activity,
  Calendar,
  Layers
} from 'lucide-react';

export interface AuditLogRowForEstimator {
  timestamp_iso: string;
  session_name: string;
  event_type: string;
  status: 'SUCCESS' | 'ABORTED' | 'ERROR' | 'HALT' | 'ESCALATED' | 'RECOVERY' | 'SKIPPED' | string;
  tournament_name: string;
  card_index: string;
  buyin_chips: string;
  target_abs_x: string;
  target_abs_y: string;
  win_left: string;
  win_top: string;
  win_width: string;
  win_height: string;
  duration_ms: string;
  details: string;
}

interface TournamentChipsProfitEstimatorProps {
  logRows: AuditLogRowForEstimator[];
  onFilterByStatus?: (status: string) => void;
}

export const TournamentChipsProfitEstimator: React.FC<TournamentChipsProfitEstimatorProps> = ({
  logRows,
  onFilterByStatus
}) => {
  // Configuração do ROI base esperado do bot em MTTs do PPPoker
  const [baseRoiPercent, setBaseRoiPercent] = useState<number>(28.5); // +28.5% padrão GTO/field soft
  const [showDetailsTable, setShowDetailsTable] = useState<boolean>(true);

  // Filtragem e cálculo dinâmico baseado nos dados do log CSV
  const metrics = useMemo(() => {
    // Considera registros de torneios que possuem valor de buyin_chips numérico
    const tournamentRows = logRows.filter(row => {
      if (!row.buyin_chips || row.buyin_chips === '-') return false;
      const val = parseFloat(row.buyin_chips.replace(/[^0-9.]/g, ''));
      return !isNaN(val) && val > 0;
    });

    const totalAttempts = tournamentRows.length;
    const successRows = tournamentRows.filter(r => r.status === 'SUCCESS');
    const abortedRows = tournamentRows.filter(r => r.status !== 'SUCCESS');

    const successfulRegistrations = successRows.length;
    const abortedRegistrations = abortedRows.length;

    // 1. Taxa de sucesso das inscrições em porcentagem
    const successRatePct = totalAttempts > 0 
      ? Number(((successfulRegistrations / totalAttempts) * 100).toFixed(1))
      : 100.0;

    // Fichas investidas de fato em inscrições confirmadas (status == 'SUCCESS')
    const totalChipsInvested = successRows.reduce((acc, row) => {
      const buyin = parseFloat(row.buyin_chips.replace(/[^0-9.]/g, '')) || 0;
      return acc + buyin;
    }, 0);

    // Fichas que seriam gastas nas tentativas abortadas (preservadas pelo watchdog/bloqueio)
    const chipsSavedFromAbort = abortedRows.reduce((acc, row) => {
      const buyin = parseFloat(row.buyin_chips.replace(/[^0-9.]/g, '')) || 0;
      return acc + buyin;
    }, 0);

    const totalChipsAttempted = totalChipsInvested + chipsSavedFromAbort;

    // 2. ROI total estimado:
    // Ponderado pela taxa de sucesso: cada % de falha penaliza o ROI efetivo por atraso/perda de blinds
    const successRatePenalty = (100.0 - successRatePct) * 0.20;
    const effectiveRoiPercent = Number((baseRoiPercent - successRatePenalty).toFixed(1));

    // Retorno bruto estimado e lucro/prejuízo líquido de fichas
    const estimatedGrossReturnChips = Number((totalChipsInvested * (1 + effectiveRoiPercent / 100.0)).toFixed(1));
    const estimatedNetChipsProfit = Number((estimatedGrossReturnChips - totalChipsInvested).toFixed(1));

    // Média de fichas ganhas/perdidas por torneio inscrito com sucesso
    const netChipsPerTournament = successfulRegistrations > 0
      ? Number((estimatedNetChipsProfit / successfulRegistrations).toFixed(2))
      : 0.0;

    // 3. Tempo médio entre inscrições bem-sucedidas (usando o timestamp_iso do log CSV)
    const sortedSuccess = [...successRows]
      .map(r => ({
        ...r,
        timeMs: r.timestamp_iso ? new Date(r.timestamp_iso).getTime() : NaN
      }))
      .filter(r => !isNaN(r.timeMs))
      .sort((a, b) => a.timeMs - b.timeMs);

    const timeDiffsSec: number[] = [];
    for (let i = 1; i < sortedSuccess.length; i++) {
      const diff = (sortedSuccess[i].timeMs - sortedSuccess[i - 1].timeMs) / 1000;
      if (diff >= 0 && diff < 86400) { // Limite de 24h para cálculo de sessão
        timeDiffsSec.push(diff);
      }
    }

    const avgTimeBetweenSuccessSec = timeDiffsSec.length > 0
      ? timeDiffsSec.reduce((a, b) => a + b, 0) / timeDiffsSec.length
      : (sortedSuccess.length > 0 ? 10.0 : 0);

    const formatDurationSec = (seconds: number): string => {
      if (seconds <= 0) return '—';
      if (seconds < 60) return `${Math.round(seconds)}s`;
      const mins = Math.floor(seconds / 60);
      const remSec = Math.round(seconds % 60);
      if (mins < 60) {
        return remSec > 0 ? `${mins}m ${remSec}s` : `${mins}m`;
      }
      const hrs = Math.floor(mins / 60);
      const remMins = mins % 60;
      return `${hrs}h ${remMins}m`;
    };

    const avgTimeBetweenSuccessFormatted = formatDurationSec(avgTimeBetweenSuccessSec);
    const minTimeBetweenFormatted = formatDurationSec(timeDiffsSec.length > 0 ? Math.min(...timeDiffsSec) : avgTimeBetweenSuccessSec);
    const maxTimeBetweenFormatted = formatDurationSec(timeDiffsSec.length > 0 ? Math.max(...timeDiffsSec) : avgTimeBetweenSuccessSec);

    const registrationsPerHour = avgTimeBetweenSuccessSec > 0 
      ? Number((3600 / avgTimeBetweenSuccessSec).toFixed(1))
      : 0;

    return {
      totalAttempts,
      successfulRegistrations,
      abortedRegistrations,
      successRatePct,
      totalChipsInvested,
      chipsSavedFromAbort,
      totalChipsAttempted,
      effectiveRoiPercent,
      estimatedGrossReturnChips,
      estimatedNetChipsProfit,
      netChipsPerTournament,
      avgTimeBetweenSuccessSec,
      avgTimeBetweenSuccessFormatted,
      minTimeBetweenFormatted,
      maxTimeBetweenFormatted,
      registrationsPerHour,
      tournamentRows
    };
  }, [logRows, baseRoiPercent]);

  const exportEstimatorJson = () => {
    const payload = {
      timestamp_export: new Date().toISOString(),
      base_roi_configured: baseRoiPercent,
      kpis: {
        estimated_total_roi_percent: metrics.effectiveRoiPercent,
        registration_success_rate_percent: metrics.successRatePct,
        avg_time_between_successful_registrations: metrics.avgTimeBetweenSuccessFormatted,
        avg_time_between_seconds: metrics.avgTimeBetweenSuccessSec,
        min_interval_formatted: metrics.minTimeBetweenFormatted,
        max_interval_formatted: metrics.maxTimeBetweenFormatted,
        registrations_per_hour_cadence: metrics.registrationsPerHour
      },
      chips_balance: {
        total_chips_invested: metrics.totalChipsInvested,
        chips_saved_from_abort: metrics.chipsSavedFromAbort,
        estimated_gross_return: metrics.estimatedGrossReturnChips,
        estimated_net_profit: metrics.estimatedNetChipsProfit,
        net_chips_per_tournament: metrics.netChipsPerTournament
      },
      audit_records_count: {
        total_attempts: metrics.totalAttempts,
        success_count: metrics.successfulRegistrations,
        aborted_count: metrics.abortedRegistrations
      },
      tournaments_audited: metrics.tournamentRows.map(r => ({
        timestamp: r.timestamp_iso,
        tournament_name: r.tournament_name,
        buyin_chips: r.buyin_chips,
        status: r.status,
        session_name: r.session_name,
        details: r.details
      }))
    };

    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(payload, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `kpi_auditoria_fichas_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const isProfitable = metrics.estimatedNetChipsProfit >= 0;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-5">
      {/* 1. Header do Painel com Identificação e Origem dos Dados */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 via-cyan-500/20 to-amber-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-bold shadow-md shadow-emerald-500/10 shrink-0">
            <Activity className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-sm text-slate-100 flex items-center gap-1.5">
                <span>Painel de Indicadores (KPIs) de Inscrições & Balanço de Fichas</span>
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold">
                Alimentado via Log CSV
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Cálculo contínuo alimentado pelos carimbos de data/hora (<code className="text-slate-300 font-mono">timestamp_iso</code>), buy-ins (<code className="text-amber-300 font-mono">buyin_chips</code>) e confirmações (<code className="text-emerald-300 font-mono">SUCCESS</code>).
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={exportEstimatorJson}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold shadow transition-all cursor-pointer"
            title="Exportar métricas de KPIs em JSON"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" />
            <span>Exportar KPIs (JSON)</span>
          </button>
        </div>
      </div>

      {/* 2. PAINEL CENTRAL DE 3 KPIS PRINCIPAIS (SOLICITADO) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* KPI 1: ROI TOTAL ESTIMADO */}
        <div className="p-4 rounded-xl bg-gradient-to-b from-slate-950 to-slate-900 border border-emerald-500/40 relative overflow-hidden shadow-lg space-y-2">
          <div className="absolute -right-6 -bottom-6 w-24 h-24 bg-emerald-500/10 rounded-full blur-2xl pointer-events-none" />

          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Award className="w-4 h-4 text-emerald-400" />
              <span>ROI Total Estimado</span>
            </span>
            <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${
              isProfitable
                ? 'bg-emerald-950/80 text-emerald-300 border-emerald-600'
                : 'bg-rose-950/80 text-rose-300 border-rose-600'
            }`}>
              {isProfitable ? 'RENTÁVEL' : 'DÉFICIT'}
            </span>
          </div>

          <div className="flex items-baseline gap-2">
            <span className={`text-3xl lg:text-4xl font-black font-mono tracking-tight ${
              metrics.effectiveRoiPercent >= 0 ? 'text-emerald-300' : 'text-rose-400'
            }`}>
              {metrics.effectiveRoiPercent >= 0 ? `+${metrics.effectiveRoiPercent}%` : `${metrics.effectiveRoiPercent}%`}
            </span>
            <span className="text-xs text-slate-400 font-sans">ROI Efetivo</span>
          </div>

          <div className="pt-1 border-t border-slate-800/80 space-y-1 text-[11px]">
            <div className="flex justify-between text-slate-300 font-mono">
              <span className="text-slate-400 font-sans">Saldo Líquido:</span>
              <span className={`font-bold ${isProfitable ? 'text-emerald-400' : 'text-rose-400'}`}>
                {isProfitable ? `+${metrics.estimatedNetChipsProfit}` : `${metrics.estimatedNetChipsProfit}`} fichas
              </span>
            </div>
            <div className="flex justify-between text-slate-400 font-mono text-[10px]">
              <span>Investido: {metrics.totalChipsInvested} fichas</span>
              <span>Retorno: {metrics.estimatedGrossReturnChips} fichas</span>
            </div>
          </div>
        </div>

        {/* KPI 2: TAXA DE SUCESSO DAS INSCRIÇÕES */}
        <div className="p-4 rounded-xl bg-gradient-to-b from-slate-950 to-slate-900 border border-cyan-500/40 relative overflow-hidden shadow-lg space-y-2">
          <div className="absolute -right-6 -bottom-6 w-24 h-24 bg-cyan-500/10 rounded-full blur-2xl pointer-events-none" />

          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Percent className="w-4 h-4 text-cyan-400" />
              <span>Taxa de Sucesso de Inscrição</span>
            </span>
            <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${
              metrics.successRatePct >= 90
                ? 'bg-cyan-950/80 text-cyan-300 border-cyan-600'
                : metrics.successRatePct >= 70
                ? 'bg-amber-950/80 text-amber-300 border-amber-600'
                : 'bg-rose-950/80 text-rose-300 border-rose-600'
            }`}>
              {metrics.successfulRegistrations}/{metrics.totalAttempts} OK
            </span>
          </div>

          <div className="flex items-baseline gap-2">
            <span className="text-3xl lg:text-4xl font-black font-mono tracking-tight text-cyan-300">
              {metrics.successRatePct}%
            </span>
            <span className="text-xs text-slate-400 font-sans">Aproveitamento</span>
          </div>

          <div className="pt-1 border-t border-slate-800/80 space-y-1.5">
            <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden p-0.5">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, metrics.successRatePct)}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-slate-400 font-mono">
              <span className="text-emerald-400 font-bold">{metrics.successfulRegistrations} Sucessos (SUCCESS)</span>
              <span className="text-rose-400 font-bold">{metrics.abortedRegistrations} Abortados</span>
            </div>
          </div>
        </div>

        {/* KPI 3: TEMPO MÉDIO ENTRE INSCRIÇÕES BEM-SUCEDIDAS */}
        <div className="p-4 rounded-xl bg-gradient-to-b from-slate-950 to-slate-900 border border-amber-500/40 relative overflow-hidden shadow-lg space-y-2">
          <div className="absolute -right-6 -bottom-6 w-24 h-24 bg-amber-500/10 rounded-full blur-2xl pointer-events-none" />

          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Timer className="w-4 h-4 text-amber-400" />
              <span>Tempo Médio Entre Sucessos</span>
            </span>
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-amber-950/80 text-amber-300 border border-amber-600">
              CADÊNCIA
            </span>
          </div>

          <div className="flex items-baseline gap-2">
            <span className="text-3xl lg:text-4xl font-black font-mono tracking-tight text-amber-300">
              {metrics.avgTimeBetweenSuccessFormatted}
            </span>
            <span className="text-xs text-slate-400 font-sans">Intervalo Médio</span>
          </div>

          <div className="pt-1 border-t border-slate-800/80 space-y-1 text-[11px]">
            <div className="flex justify-between text-slate-300 font-mono">
              <span className="text-slate-400 font-sans">Ritmo Estimado:</span>
              <span className="text-amber-400 font-bold">~{metrics.registrationsPerHour} registros/hora</span>
            </div>
            <div className="flex justify-between text-slate-400 font-mono text-[10px]">
              <span>Mín: {metrics.minTimeBetweenFormatted}</span>
              <span>Máx: {metrics.maxTimeBetweenFormatted}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Slider de Ajuste de ROI Esperado & Calibrador */}
      <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-bold text-slate-200">
              Calibrador de ROI Esperado do Bot no Field (MTT ROI %):
            </span>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs">
            <span className="text-slate-400 font-sans text-[11px]">ROI Base Selecionado:</span>
            <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 font-bold">
              {baseRoiPercent >= 0 ? `+${baseRoiPercent}%` : `${baseRoiPercent}%`}
            </span>
          </div>
        </div>

        <div className="space-y-1">
          <input
            type="range"
            min="-20"
            max="60"
            step="0.5"
            value={baseRoiPercent}
            onChange={(e) => setBaseRoiPercent(parseFloat(e.target.value))}
            className="w-full accent-amber-500 cursor-pointer"
          />

          <div className="flex justify-between text-[10px] font-mono text-slate-500">
            <span>-20% (Downswing severo)</span>
            <span>0% (Breakeven)</span>
            <span className="text-amber-400 font-bold">+28.5% (Field Médio PPPoker)</span>
            <span>+60% (Field Hiper Soft)</span>
          </div>
        </div>

        <p className="text-[11px] text-slate-400 leading-relaxed font-sans pt-1">
          O cálculo consome o campo <code className="text-amber-300 font-mono">buyin_chips</code> de cada linha com status <code className="text-emerald-400 font-mono">SUCCESS</code> do log CSV. A taxa de sucesso de {metrics.successRatePct}% calibra a rentabilidade final e o tempo médio entre sucessos ({metrics.avgTimeBetweenSuccessFormatted}) afere o ritmo operacional.
        </p>
      </div>

      {/* 4. Tabela de Detalhamento dos Registros Auditados do Log CSV */}
      <div className="space-y-2 pt-1">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setShowDetailsTable(!showDetailsTable)}
            className="flex items-center gap-1.5 text-xs font-bold text-slate-300 hover:text-white transition-colors cursor-pointer"
          >
            <FileSpreadsheet className="w-4 h-4 text-cyan-400" />
            <span>Detalhamento dos Torneios no Log CSV ({metrics.tournamentRows.length} registros com buy-in)</span>
            <span className="text-[10px] font-mono text-slate-500">({showDetailsTable ? 'Ocultar' : 'Exibir'})</span>
          </button>

          {onFilterByStatus && (
            <div className="flex items-center gap-1 text-[11px]">
              <span className="text-slate-500 font-sans">Filtrar na Auditoria:</span>
              <button
                type="button"
                onClick={() => onFilterByStatus('SUCCESS')}
                className="px-2 py-0.5 rounded bg-emerald-950 hover:bg-emerald-900 border border-emerald-800 text-emerald-300 text-[10px] font-mono cursor-pointer"
              >
                Só Sucessos
              </button>
              <button
                type="button"
                onClick={() => onFilterByStatus('ABORTED')}
                className="px-2 py-0.5 rounded bg-rose-950 hover:bg-rose-900 border border-rose-800 text-rose-300 text-[10px] font-mono cursor-pointer"
              >
                Só Abortados
              </button>
            </div>
          )}
        </div>

        {showDetailsTable && (
          <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950">
            <div className="max-h-60 overflow-y-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-900/90 border-b border-slate-800 text-slate-400 uppercase text-[10px] sticky top-0 z-10">
                  <tr>
                    <th className="py-2.5 px-3">Horário (timestamp_iso)</th>
                    <th className="py-2.5 px-3">Torneio</th>
                    <th className="py-2.5 px-3">Buy-in (Fichas)</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Impacto no Balanço</th>
                    <th className="py-2.5 px-3">Detalhes do Evento</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300 text-[11px]">
                  {metrics.tournamentRows.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-slate-500 font-sans text-xs">
                        Nenhum registro de torneio com 'buyin_chips' encontrado no log de auditoria atual.
                      </td>
                    </tr>
                  ) : (
                    metrics.tournamentRows.map((row, index) => {
                      const isSuccess = row.status === 'SUCCESS';
                      const buyinNum = parseFloat(row.buyin_chips.replace(/[^0-9.]/g, '')) || 0;
                      const estimatedReturnThisHand = isSuccess
                        ? Number((buyinNum * (1 + metrics.effectiveRoiPercent / 100)).toFixed(1))
                        : 0;
                      const profitThisHand = isSuccess
                        ? Number((estimatedReturnThisHand - buyinNum).toFixed(1))
                        : 0;

                      return (
                        <tr key={index} className="hover:bg-slate-900/40 transition-colors">
                          <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                            {row.timestamp_iso ? row.timestamp_iso.slice(11, 19) : '--:--:--'}
                          </td>
                          <td className="py-2.5 px-3 font-semibold text-slate-200 whitespace-nowrap">
                            {row.tournament_name || 'Torneio MTT'}
                          </td>
                          <td className="py-2.5 px-3 text-amber-300 font-bold whitespace-nowrap">
                            {row.buyin_chips} fichas
                          </td>
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              isSuccess
                                ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                                : 'bg-rose-950 text-rose-300 border-rose-800'
                            }`}>
                              {row.status}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            {isSuccess ? (
                              <span className="text-emerald-400 font-bold">
                                +{profitThisHand} fichas ({metrics.effectiveRoiPercent >= 0 ? `+${metrics.effectiveRoiPercent}%` : `${metrics.effectiveRoiPercent}%`})
                              </span>
                            ) : (
                              <span className="text-cyan-400 font-medium">
                                Preservado (0 debitado)
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-slate-400 text-[10px] max-w-xs truncate" title={row.details}>
                            {row.details || 'Registro processado'}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
