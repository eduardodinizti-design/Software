import React, { useState, useMemo } from 'react';
import {
  AlertTriangle,
  TrendingDown,
  TrendingUp,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Filter,
  BarChart2,
  RefreshCw,
  Info,
  Layers,
  ArrowRight,
  Flame,
  Zap,
  SlidersHorizontal
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine
} from 'recharts';

export interface SessionErrorHandRecord {
  id: string;
  handId: string;
  handNumber: number;
  timestamp: string;
  table: string;
  heroCards: string;
  combo: string;
  position: string;
  failureType: 'RANGE_INCORRETO' | 'LEITURA_BOARD_ERRADA' | 'GESTAO_POTE_FALHA' | 'SIZING_INADEQUADO' | 'BLUFF_CATCH_INDEVIDO';
  failureLabel: string;
  lossBb: number;
  description: string;
  suggestedCorrection: string;
  resolved: boolean;
}

export interface SessionBlockErrorStat {
  blockLabel: string;
  handRange: string;
  rangeIncorreto: number;
  leituraBoardErrada: number;
  gestaoPoteFalha: number;
  sizingInadequado: number;
  bluffCatchIndevido: number;
  totalErrors: number;
  bbLost: number;
}

const INITIAL_SESSION_BLOCKS: SessionBlockErrorStat[] = [
  {
    blockLabel: 'Mãos 1-100',
    handRange: '1 - 100',
    rangeIncorreto: 6,
    leituraBoardErrada: 4,
    gestaoPoteFalha: 5,
    sizingInadequado: 3,
    bluffCatchIndevido: 4,
    totalErrors: 22,
    bbLost: -54.0
  },
  {
    blockLabel: 'Mãos 101-200',
    handRange: '101 - 200',
    rangeIncorreto: 4,
    leituraBoardErrada: 3,
    gestaoPoteFalha: 4,
    sizingInadequado: 2,
    bluffCatchIndevido: 3,
    totalErrors: 16,
    bbLost: -41.5
  },
  {
    blockLabel: 'Mãos 201-300',
    handRange: '201 - 300',
    rangeIncorreto: 3,
    leituraBoardErrada: 2,
    gestaoPoteFalha: 2,
    sizingInadequado: 2,
    bluffCatchIndevido: 2,
    totalErrors: 11,
    bbLost: -26.0
  },
  {
    blockLabel: 'Mãos 301-400',
    handRange: '301 - 400',
    rangeIncorreto: 1,
    leituraBoardErrada: 2,
    gestaoPoteFalha: 1,
    sizingInadequado: 1,
    bluffCatchIndevido: 1,
    totalErrors: 6,
    bbLost: -14.2
  },
  {
    blockLabel: 'Mãos 401-500',
    handRange: '401 - 500',
    rangeIncorreto: 1,
    leituraBoardErrada: 1,
    gestaoPoteFalha: 0,
    sizingInadequado: 1,
    bluffCatchIndevido: 0,
    totalErrors: 3,
    bbLost: -6.8
  }
];

const INITIAL_ERROR_HANDS: SessionErrorHandRecord[] = [
  {
    id: 'err_01',
    handId: 'hand_10481',
    handNumber: 42,
    timestamp: '13:32:44',
    table: 'PPPoker #2 (Rubi)',
    heroCards: 'K♦ Q♠',
    combo: 'KQo',
    position: 'SB',
    failureType: 'RANGE_INCORRETO',
    failureLabel: 'Range Incorreto (Limp -EV)',
    lossBb: -3.5,
    description: 'Completar o blind deu odds perfeitas ao BB para punir fora de posição.',
    suggestedCorrection: 'Raise 3.0x ou Fold direto no SB.',
    resolved: true
  },
  {
    id: 'err_02',
    handId: 'hand_10479',
    handNumber: 94,
    timestamp: '13:28:15',
    table: 'PPPoker #1 (Diamante)',
    heroCards: 'K♠ J♦',
    combo: 'KJo',
    position: 'MP',
    failureType: 'RANGE_INCORRETO',
    failureLabel: 'Range Incorreto (Call 3-Bet Dominado)',
    lossBb: -7.0,
    description: 'Call 3-bet OOP contra jogador agressivo com cartas facilmente dominadas.',
    suggestedCorrection: 'Fold obrigatório pré-flop contra 3-bet em MP.',
    resolved: true
  },
  {
    id: 'err_03',
    handId: 'hand_10444',
    handNumber: 156,
    timestamp: '13:41:20',
    table: 'ClubGG Mystery #4',
    heroCards: 'A♣ 3♣',
    combo: 'A3s',
    position: 'BB',
    failureType: 'LEITURA_BOARD_ERRADA',
    failureLabel: 'Leitura de Board Errada (Overplay Bottom Pair)',
    lossBb: -11.0,
    description: 'Pagar duas apostas em bordo T-8-3-K com par de 3 sem kicker.',
    suggestedCorrection: 'Foldar no Turn ao enfrentar o segundo barril do vilão.',
    resolved: false
  },
  {
    id: 'err_04',
    handId: 'hand_10420',
    handNumber: 218,
    timestamp: '13:52:10',
    table: 'PPPoker #1 (Diamante)',
    heroCards: 'Q♥ J♥',
    combo: 'QJs',
    position: 'CO',
    failureType: 'BLUFF_CATCH_INDEVIDO',
    failureLabel: 'Bluff-Catch Indevido no River',
    lossBb: -9.0,
    description: 'Call no river com par de Damas em bordo com Ás contra aposta de 80% do pote.',
    suggestedCorrection: 'Foldar no River; o field sub-blefa em potes grandes.',
    resolved: false
  },
  {
    id: 'err_05',
    handId: 'hand_10398',
    handNumber: 284,
    timestamp: '14:04:33',
    table: 'Upoker Liga Suprema',
    heroCards: '8♦ 7♦',
    combo: '87s',
    position: 'BTN',
    failureType: 'GESTAO_POTE_FALHA',
    failureLabel: 'Falha de Gestão de Pote (Overbet OOP)',
    lossBb: -14.5,
    description: 'Inflar o pote com semi-bluff em textura já emparelhada sem cartas de saída limpas.',
    suggestedCorrection: 'Controle de pote via Check-Behind no Turn.',
    resolved: true
  },
  {
    id: 'err_06',
    handId: 'hand_10362',
    handNumber: 345,
    timestamp: '14:18:05',
    table: 'PPPoker #2 (Rubi)',
    heroCards: 'A♠ K♠',
    combo: 'AKs',
    position: 'UTG',
    failureType: 'SIZING_INADEQUADO',
    failureLabel: 'Dimensionamento Inadequado (C-Bet Excessiva)',
    lossBb: -5.2,
    description: 'C-Bet de 75% em bordo seco A-7-2 rainbow onde 33% atinge o mesmo objetivo.',
    suggestedCorrection: 'Utilizar sizing padronizado de 33% em texturas secas.',
    resolved: true
  }
];

export const SessionErrorHistoryInspector: React.FC<{
  onNotify?: (title: string, message: string, severity: 'INFO' | 'WARN' | 'CRITICAL') => void;
}> = ({ onNotify }) => {
  const [sessionBlocks, setSessionBlocks] = useState<SessionBlockErrorStat[]>(INITIAL_SESSION_BLOCKS);
  const [errorHands, setErrorHands] = useState<SessionErrorHandRecord[]>(INITIAL_ERROR_HANDS);
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<string>('ALL');

  // Categorias de falhas e suas cores/estilos
  const failureCategoryMeta = {
    RANGE_INCORRETO: {
      label: 'Range Incorreto',
      color: '#a855f7',
      bgClass: 'bg-purple-950 text-purple-300 border-purple-700',
      description: 'Aberturas fora de posição, limps desnecessários ou calls contra 3-bet sem odds.'
    },
    LEITURA_BOARD_ERRADA: {
      label: 'Leitura de Board Errada',
      color: '#06b6d4',
      bgClass: 'bg-cyan-950 text-cyan-300 border-cyan-700',
      description: 'Superestimar showdown value de pares médios em bordos hiper-conectados ou perigosos.'
    },
    GESTAO_POTE_FALHA: {
      label: 'Falha de Gestão de Pote',
      color: '#f43f5e',
      bgClass: 'bg-rose-950 text-rose-300 border-rose-700',
      description: 'Inflar o pote desnecessariamente ou perder controle de tamanho de pote fora de posição.'
    },
    SIZING_INADEQUADO: {
      label: 'Sizing Inadequado',
      color: '#f59e0b',
      bgClass: 'bg-amber-950 text-amber-300 border-amber-700',
      description: 'Dimensionamento fora dos padrões GTO (apostas excessivas ou pequenas demais).'
    },
    BLUFF_CATCH_INDEVIDO: {
      label: 'Bluff-Catch Indevido',
      color: '#3b82f6',
      bgClass: 'bg-blue-950 text-blue-300 border-blue-700',
      description: 'Pagar 3º barril no river sem blockers específicos contra a tendência do field de sub-blefar.'
    }
  };

  // Totais agregados
  const totalErrorsSession = useMemo(
    () => sessionBlocks.reduce((acc, b) => acc + b.totalErrors, 0),
    [sessionBlocks]
  );

  const totalBbLostSession = useMemo(
    () => Number(sessionBlocks.reduce((acc, b) => acc + b.bbLost, 0).toFixed(1)),
    [sessionBlocks]
  );

  // Redução percentual de falhas do bloco 1 ao 5
  const errorReductionPct = useMemo(() => {
    const first = sessionBlocks[0]?.totalErrors || 1;
    const last = sessionBlocks[sessionBlocks.length - 1]?.totalErrors || 0;
    return Number((((first - last) / first) * 100).toFixed(1));
  }, [sessionBlocks]);

  // Contagem por categoria
  const categoryTotals = useMemo(() => {
    return {
      RANGE_INCORRETO: sessionBlocks.reduce((acc, b) => acc + b.rangeIncorreto, 0),
      LEITURA_BOARD_ERRADA: sessionBlocks.reduce((acc, b) => acc + b.leituraBoardErrada, 0),
      GESTAO_POTE_FALHA: sessionBlocks.reduce((acc, b) => acc + b.gestaoPoteFalha, 0),
      SIZING_INADEQUADO: sessionBlocks.reduce((acc, b) => acc + b.sizingInadequado, 0),
      BLUFF_CATCH_INDEVIDO: sessionBlocks.reduce((acc, b) => acc + b.bluffCatchIndevido, 0)
    };
  }, [sessionBlocks]);

  // Mãos filtradas
  const filteredHands = useMemo(() => {
    if (selectedCategoryFilter === 'ALL') return errorHands;
    return errorHands.filter(h => h.failureType === selectedCategoryFilter);
  }, [errorHands, selectedCategoryFilter]);

  // Handler: Marcar falha como corrigida
  const handleResolveHand = (id: string) => {
    setErrorHands(prev =>
      prev.map(h => (h.id === id ? { ...h, resolved: true } : h))
    );
    onNotify?.("FALHA AUDITADA", "A falha foi marcada como corrigida e o peso correspondente foi recalculado no cérebro.", "INFO");
  };

  // Handler: Simular Nova Mão com Falha
  const handleSimulateNewError = () => {
    const types: Array<'RANGE_INCORRETO' | 'LEITURA_BOARD_ERRADA' | 'GESTAO_POTE_FALHA' | 'SIZING_INADEQUADO' | 'BLUFF_CATCH_INDEVIDO'> = [
      'RANGE_INCORRETO', 'LEITURA_BOARD_ERRADA', 'GESTAO_POTE_FALHA', 'SIZING_INADEQUADO', 'BLUFF_CATCH_INDEVIDO'
    ];
    const pickedType = types[Math.floor(Math.random() * types.length)];
    const newHand: SessionErrorHandRecord = {
      id: `err_${Date.now().toString().slice(-4)}`,
      handId: `hand_${Math.floor(Math.random() * 200 + 10500)}`,
      handNumber: 480 + Math.floor(Math.random() * 20),
      timestamp: new Date().toLocaleTimeString('pt-BR'),
      table: 'PPPoker #1 (Diamante)',
      heroCards: 'A♠ 9♦',
      combo: 'A9o',
      position: 'UTG',
      failureType: pickedType,
      failureLabel: failureCategoryMeta[pickedType].label,
      lossBb: -Number((Math.random() * 8 + 3).toFixed(1)),
      description: 'Desvio detectado automaticamente pelo OCR vs tabela de range GTO.',
      suggestedCorrection: 'Ajustar política de abertura de acordo com o solver.',
      resolved: false
    };

    setErrorHands(prev => [newHand, ...prev]);
    onNotify?.("NOVA FALHA DETECTADA", `Erro categorizado como '${failureCategoryMeta[pickedType].label}' adicionado ao histórico da sessão.`, "WARN");
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-5">
      {/* Header Strip */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/30 shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-base text-slate-100 tracking-tight">
                Histórico de Erros da Última Sessão por Tipo de Falha
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-emerald-950 text-emerald-300 border border-emerald-700">
                Redução de -{errorReductionPct}%
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Acompanhamento longitudinal das 500 mãos da última sessão, categorizando falhas de range, leitura de board e gestão de pote para medir o aprendizado contínuo.
            </p>
          </div>
        </div>

        <button
          onClick={handleSimulateNewError}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-mono font-bold text-slate-200 transition-colors cursor-pointer shadow-sm"
        >
          <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
          <span>Simular Falha na Sessão</span>
        </button>
      </div>

      {/* KPI Cards Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <span className="text-[10px] text-slate-500 uppercase block">Total de Falhas na Sessão</span>
          <span className="text-lg font-black text-rose-400">{totalErrorsSession} erros</span>
          <span className="text-[10px] text-slate-500 block">em 500 mãos analisadas</span>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <span className="text-[10px] text-emerald-400 uppercase block">Evolução / Redução</span>
          <span className="text-lg font-black text-emerald-400">-{errorReductionPct}%</span>
          <span className="text-[10px] text-slate-500 block">de 22 p/ 3 erros por bloco</span>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <span className="text-[10px] text-slate-500 uppercase block">Custo Total das Falhas</span>
          <span className="text-lg font-black text-rose-400">{totalBbLostSession} BB</span>
          <span className="text-[10px] text-slate-500 block">impacto negativo no winrate</span>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <span className="text-[10px] text-purple-400 uppercase block">Maior Causa de Falha</span>
          <span className="text-sm font-bold text-purple-300 truncate block">Range Incorreto</span>
          <span className="text-[10px] text-slate-500 block">{categoryTotals.RANGE_INCORRETO} ocorrências (25.8%)</span>
        </div>
      </div>

      {/* Main Stacked Bar Chart: Error Evolution Over Session Blocks */}
      <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <span className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
              <BarChart2 className="w-4 h-4 text-purple-400" />
              <span>Evolução Cronológica de Falhas (Blocos de 100 Mãos)</span>
            </span>
            <p className="text-[11px] text-slate-400">
              Gráfico de barras empilhadas categorizando cada tipo de erro ao longo do progresso da sessão.
            </p>
          </div>

          {/* Legend Badges */}
          <div className="flex items-center gap-3 text-xs font-mono flex-wrap">
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded bg-purple-500 inline-block" />
              <span className="text-slate-300 text-[11px]">Range Incorreto</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded bg-cyan-400 inline-block" />
              <span className="text-slate-300 text-[11px]">Leitura de Board</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded bg-rose-500 inline-block" />
              <span className="text-slate-300 text-[11px]">Gestão de Pote</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded bg-amber-400 inline-block" />
              <span className="text-slate-300 text-[11px]">Sizing Inadequado</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded bg-blue-500 inline-block" />
              <span className="text-slate-300 text-[11px]">Bluff-Catch</span>
            </div>
          </div>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={sessionBlocks} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="blockLabel" stroke="#94a3b8" tick={{ fontSize: 11, fontWeight: 700 }} />
              <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '12px' }}
                itemStyle={{ color: '#f8fafc' }}
                formatter={(val: any, name: any) => {
                  const labels: Record<string, string> = {
                    rangeIncorreto: 'Range Incorreto',
                    leituraBoardErrada: 'Leitura de Board Errada',
                    gestaoPoteFalha: 'Falha de Gestão de Pote',
                    sizingInadequado: 'Sizing Inadequado',
                    bluffCatchIndevido: 'Bluff-Catch Indevido'
                  };
                  return [`${val} erros`, labels[name] || name];
                }}
              />
              <Bar dataKey="rangeIncorreto" name="rangeIncorreto" stackId="errors" fill="#a855f7" />
              <Bar dataKey="leituraBoardErrada" name="leituraBoardErrada" stackId="errors" fill="#06b6d4" />
              <Bar dataKey="gestaoPoteFalha" name="gestaoPoteFalha" stackId="errors" fill="#f43f5e" />
              <Bar dataKey="sizingInadequado" name="sizingInadequado" stackId="errors" fill="#f59e0b" />
              <Bar dataKey="bluffCatchIndevido" name="bluffCatchIndevido" stackId="errors" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Category Distribution Grid & Filters */}
      <div className="space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <span className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider block">
            Distribuição Total por Categoria de Falha na Sessão:
          </span>
          <div className="flex items-center gap-1.5 flex-wrap font-mono text-xs">
            <button
              onClick={() => setSelectedCategoryFilter('ALL')}
              className={`px-2.5 py-1 rounded-lg border transition-all cursor-pointer ${
                selectedCategoryFilter === 'ALL'
                  ? 'bg-purple-950 text-purple-200 border-purple-500 font-bold'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              Todas as Falhas ({errorHands.length})
            </button>
            {Object.entries(failureCategoryMeta).map(([key, meta]) => (
              <button
                key={key}
                onClick={() => setSelectedCategoryFilter(key)}
                className={`px-2.5 py-1 rounded-lg border transition-all cursor-pointer ${
                  selectedCategoryFilter === key
                    ? 'bg-slate-800 text-white border-slate-500 font-bold'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                {meta.label} ({categoryTotals[key as keyof typeof categoryTotals]})
              </button>
            ))}
          </div>
        </div>

        {/* Detailed Hand Occurrences List */}
        <div className="space-y-2">
          {filteredHands.map(hand => {
            const meta = failureCategoryMeta[hand.failureType];
            return (
              <div
                key={hand.id}
                className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/90 hover:border-slate-700 transition-all font-mono text-xs space-y-2"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500 font-bold">{hand.timestamp}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-900 border border-slate-800 text-slate-300">
                      Mão #{hand.handNumber} ({hand.table})
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${meta.bgClass}`}>
                      {meta.label}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-950 text-purple-300 border border-purple-800">
                      {hand.combo} ({hand.position})
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="font-black text-rose-400">
                      {hand.lossBb} BB
                    </span>
                    {hand.resolved ? (
                      <span className="text-[10px] text-emerald-400 flex items-center gap-1 font-bold">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Corrigido
                      </span>
                    ) : (
                      <button
                        onClick={() => handleResolveHand(hand.id)}
                        className="px-2.5 py-1 rounded bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-[10px] transition-colors cursor-pointer"
                      >
                        Aplicar Correção
                      </button>
                    )}
                  </div>
                </div>

                <div className="text-[11px] text-slate-400 flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 border-t border-slate-900">
                  <p>
                    <strong className="text-slate-300">Diagnóstico: </strong>{hand.description}
                  </p>
                  <p className="text-emerald-400 shrink-0">
                    <strong>GTO: </strong>{hand.suggestedCorrection}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
