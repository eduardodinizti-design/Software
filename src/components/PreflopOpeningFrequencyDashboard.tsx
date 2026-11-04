import React, { useState, useMemo } from 'react';
import {
  Scale,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  SlidersHorizontal,
  Zap,
  RefreshCw,
  ShieldCheck,
  Layers,
  Info,
  Sparkles,
  ArrowUpRight,
  ArrowDownRight
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

export interface PositionFrequencyRecord {
  position: 'UTG' | 'MP' | 'CO' | 'BTN' | 'SB';
  positionLabel: string;
  idealFreqPct: number; // GTO Benchmark
  botFreqPct: number;   // Frequência Real do Bot
  sampleHands: number;
  tacticalAdvice: string;
  recommendedAction: string;
}

export interface StructurePreset {
  id: string;
  name: string;
  stackBb: number;
  description: string;
  frequencies: Record<'UTG' | 'MP' | 'CO' | 'BTN' | 'SB', number>;
}

const STRUCTURE_PRESETS: StructurePreset[] = [
  {
    id: 'mtt_deep_50bb',
    name: 'MTT Deepstack (40-60 BB)',
    stackBb: 50,
    description: 'Equilíbrio GTO padrão para início e meio de torneios com realizações de equidade sólidas.',
    frequencies: {
      UTG: 15.1,
      MP: 19.5,
      CO: 27.2,
      BTN: 44.8,
      SB: 38.6
    }
  },
  {
    id: 'pko_bounty_25bb',
    name: 'PKO Bounty (25-30 BB)',
    stackBb: 25,
    description: 'Aberturas estendidas para isolar stacks menores e acumular bounties progressivos.',
    frequencies: {
      UTG: 16.5,
      MP: 21.0,
      CO: 29.5,
      BTN: 48.2,
      SB: 36.0
    }
  },
  {
    id: 'turbo_15bb',
    name: 'Turbo / Short Stack (15 BB Push/Fold)',
    stackBb: 15,
    description: 'Ranges Nash polarizados e lineares focados em all-in direto e re-steals.',
    frequencies: {
      UTG: 13.8,
      MP: 17.2,
      CO: 24.5,
      BTN: 39.5,
      SB: 42.0
    }
  }
];

const INITIAL_BOT_FREQUENCIES: Record<'UTG' | 'MP' | 'CO' | 'BTN' | 'SB', number> = {
  UTG: 16.9, // +1.8% (leve over-open)
  MP: 19.3,  // -0.2% (equilibrado)
  CO: 23.8,  // -3.4% (sub-abertura / conservador)
  BTN: 51.2, // +6.4% (over-opening grave / blefes em excesso)
  SB: 31.5   // -7.1% (sub-abertura crítica / desperdício de EV)
};

export const PreflopOpeningFrequencyDashboard: React.FC<{
  onNotify?: (title: string, message: string, severity: 'INFO' | 'WARN' | 'CRITICAL') => void;
}> = ({ onNotify }) => {
  const [selectedStructureId, setSelectedStructureId] = useState<string>('mtt_deep_50bb');
  const [tolerancePct, setTolerancePct] = useState<number>(2.0); // ±2.0%
  const [botFrequencies, setBotFrequencies] = useState(INITIAL_BOT_FREQUENCIES);
  const [isCalibrating, setIsCalibrating] = useState<boolean>(false);
  const [selectedPositionDetail, setSelectedPositionDetail] = useState<string | null>('BTN');

  const activeStructure = useMemo(
    () => STRUCTURE_PRESETS.find(s => s.id === selectedStructureId) || STRUCTURE_PRESETS[0],
    [selectedStructureId]
  );

  // Calcula dados combinados por posição
  const frequencyData = useMemo(() => {
    const positions: Array<'UTG' | 'MP' | 'CO' | 'BTN' | 'SB'> = ['UTG', 'MP', 'CO', 'BTN', 'SB'];
    const positionLabels: Record<string, string> = {
      UTG: 'Under the Gun (UTG)',
      MP: 'Middle Position (MP)',
      CO: 'Cutoff (CO)',
      BTN: 'Button (BTN)',
      SB: 'Small Blind (SB)'
    };

    const adviceMap: Record<string, { advice: string; fix: string }> = {
      UTG: {
        advice: 'Range deve permanecer restrito e orientado a valor. Aumentar frequência expõe o bot a 3-bets.',
        fix: 'Remover suited connectors baixos (ex: 54s, 65s) e broadways offsuit marginais (ATo, KJo).'
      },
      MP: {
        advice: 'Posição intermediária com boa flexibilidade. Frequência atual está próxima da zona ideal GTO.',
        fix: 'Manter matriz de aberturas atual. Monitorar se o CO ou BTN aumentam taxa de 3-bet.'
      },
      CO: {
        advice: 'O bot está abrindo significativamente menos do que o GTO recomenda, deixando EV lucrativo na mesa.',
        fix: 'Adicionar broadways suited secundários (Q9s, J9s, T8s) e mãos A-high suited marginais (A3s, A2s).'
      },
      BTN: {
        advice: 'Abertura excessiva (+5.4%). O bot está inflacionando potes com mãos offsuit fracas facilmente dominadas.',
        fix: 'Reduzir abertura com offsuit connectors (87o, 76o) e Ax offsuit fraco (A6o-A2o); manter broadways fortes.'
      },
      SB: {
        advice: 'Sub-abertura crítica (-7.1%). Em potes em que a mesa rodou em fold, o bot deve pressionar o Big Blind.',
        fix: 'Adicionar estratégia polarizada de raise 3.0x com suited broadways e conectores para punir passividade do BB.'
      }
    };

    return positions.map(pos => {
      const ideal = activeStructure.frequencies[pos];
      const bot = botFrequencies[pos];
      const delta = Number((bot - ideal).toFixed(1));
      const absDelta = Math.abs(delta);

      let status: 'BALANCED' | 'OVER_OPENING' | 'UNDER_OPENING' = 'BALANCED';
      if (delta > tolerancePct) {
        status = 'OVER_OPENING';
      } else if (delta < -tolerancePct) {
        status = 'UNDER_OPENING';
      }

      return {
        position: pos,
        positionLabel: positionLabels[pos],
        idealFreqPct: ideal,
        botFreqPct: bot,
        delta,
        absDelta,
        status,
        sampleHands: pos === 'BTN' ? 1420 : pos === 'CO' ? 1120 : pos === 'MP' ? 980 : pos === 'SB' ? 840 : 760,
        tacticalAdvice: adviceMap[pos].advice,
        recommendedAction: adviceMap[pos].fix
      };
    });
  }, [activeStructure, botFrequencies, tolerancePct]);

  // Contadores de Discrepância
  const discrepanciesCount = useMemo(() => {
    return frequencyData.filter(f => f.status !== 'BALANCED').length;
  }, [frequencyData]);

  // Handler: Calibrar Motor Automaticamente (converge para o ideal)
  const handleAutoCalibrateAll = () => {
    setIsCalibrating(true);
    onNotify?.(
      "CALIBRANDO MOTOR GTO",
      `Iniciando ajuste algorítmico das frequências pré-flop para convergir com ${activeStructure.name}...`,
      "INFO"
    );

    setTimeout(() => {
      setBotFrequencies({
        UTG: activeStructure.frequencies.UTG,
        MP: activeStructure.frequencies.MP,
        CO: activeStructure.frequencies.CO,
        BTN: activeStructure.frequencies.BTN,
        SB: activeStructure.frequencies.SB
      });
      setIsCalibrating(false);
      onNotify?.(
        "MOTOR GTO CALIBRADO",
        `Frequências pré-flop ajustadas para 100% de convergência GTO com tolerância de ±${tolerancePct.toFixed(1)}%.`,
        "INFO"
      );
    }, 450);
  };

  // Handler: Calibrar apenas uma posição
  const handleCalibratePosition = (pos: 'UTG' | 'MP' | 'CO' | 'BTN' | 'SB') => {
    setBotFrequencies(prev => ({
      ...prev,
      [pos]: activeStructure.frequencies[pos]
    }));
    onNotify?.(
      "POSIÇÃO CALIBRADA",
      `Frequência da posição ${pos} ajustada para a meta ideal de ${activeStructure.frequencies[pos]}%.`,
      "INFO"
    );
  };

  // Handler: Simular Desvios da Sessão Recente
  const handleSimulateSessionDrift = () => {
    setBotFrequencies({
      UTG: Number((activeStructure.frequencies.UTG + (Math.random() * 3.5 - 1.2)).toFixed(1)),
      MP: Number((activeStructure.frequencies.MP + (Math.random() * 2.5 - 1.2)).toFixed(1)),
      CO: Number((activeStructure.frequencies.CO - (Math.random() * 4.0 + 1.0)).toFixed(1)),
      BTN: Number((activeStructure.frequencies.BTN + (Math.random() * 6.0 + 2.0)).toFixed(1)),
      SB: Number((activeStructure.frequencies.SB - (Math.random() * 6.5 + 2.0)).toFixed(1))
    });
    onNotify?.(
      "AMOSTRAGEM ATUALIZADA",
      "Desvios reais da sessão simulada carregados no comparador de frequência.",
      "WARN"
    );
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-5">
      {/* Dashboard Header Strip */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-500/20 text-purple-400 border border-purple-500/30 shrink-0">
            <Scale className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-base text-slate-100 tracking-tight">
                Dashboard de Frequência de Abertura: Ideal GTO vs Frequência Atual do Bot
              </h3>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${
                discrepanciesCount === 0
                  ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                  : 'bg-rose-950 text-rose-300 border-rose-700 animate-pulse'
              }`}>
                {discrepanciesCount === 0 ? 'Convergência Total' : `${discrepanciesCount} Discrepâncias Críticas`}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Rastreamento em tempo real do Raise First In (RFI) por posição comparado à teoria de jogo ideal para eliminar drenos de fichas.
            </p>
          </div>
        </div>

        {/* Global Calibration Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap font-mono text-xs">
          <button
            onClick={handleSimulateSessionDrift}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 font-semibold transition-colors cursor-pointer"
            title="Simula desvio de abertura com base em amostragem recente de mesas ativas"
          >
            <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
            <span>Simular Desvio Amostral</span>
          </button>

          <button
            onClick={handleAutoCalibrateAll}
            disabled={isCalibrating || discrepanciesCount === 0}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl font-bold transition-all shadow-md cursor-pointer ${
              discrepanciesCount === 0
                ? 'bg-slate-800 text-slate-500 border border-slate-800 cursor-not-allowed'
                : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-emerald-500/20'
            }`}
          >
            <Zap className={`w-3.5 h-3.5 ${isCalibrating ? 'animate-spin' : ''}`} />
            <span>{isCalibrating ? 'Calibrando...' : 'Calibrar Motor Automaticamente'}</span>
          </button>
        </div>
      </div>

      {/* Control Strip: Structure Preset & Tolerance Threshold Slider */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 bg-slate-950/70 p-4 rounded-xl border border-slate-800">
        {/* Structure Preset Picker (8 cols) */}
        <div className="md:col-span-8 space-y-1.5">
          <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-mono block">
            1. Estrutura / Profundidade de Stack (Benchmark Teórico):
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {STRUCTURE_PRESETS.map(s => (
              <button
                key={s.id}
                onClick={() => setSelectedStructureId(s.id)}
                className={`text-left p-2.5 rounded-xl border transition-all cursor-pointer ${
                  selectedStructureId === s.id
                    ? 'bg-purple-950/70 border-purple-500 text-purple-200 shadow'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs font-mono">{s.name}</span>
                  <span className="text-[10px] font-mono font-black text-purple-400">{s.stackBb} BB</span>
                </div>
                <p className="text-[10px] text-slate-500 mt-1 line-clamp-1">{s.description}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Tolerance Threshold Slider (4 cols) */}
        <div className="md:col-span-4 flex flex-col justify-between bg-slate-900 p-3 rounded-xl border border-slate-800 space-y-2 font-mono text-xs">
          <div className="flex items-center justify-between">
            <span className="text-slate-400 flex items-center gap-1">
              <SlidersHorizontal className="w-3.5 h-3.5 text-purple-400" />
              <span>Tolerância de Desvio:</span>
            </span>
            <strong className="text-purple-300 font-bold">±{tolerancePct.toFixed(1)}%</strong>
          </div>
          <input
            type="range"
            min={1.0}
            max={4.5}
            step={0.5}
            value={tolerancePct}
            onChange={(e) => setTolerancePct(Number(e.target.value))}
            className="w-full accent-purple-500 bg-slate-950 h-1.5 rounded cursor-pointer"
          />
          <span className="text-[10px] text-slate-500 block">
            Desvios fora de ±{tolerancePct.toFixed(1)}% disparam avisos de abertura excessiva ou sub-abertura.
          </span>
        </div>
      </div>

      {/* Visual Charts: Grouped Bar Chart & Delta Gauge */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left: Recharts Grouped Bar Chart (8 cols) */}
        <div className="lg:col-span-8 bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <TrendingUp className="w-4 h-4 text-purple-400" />
              <span>Comparativo de Frequência (% RFI por Posição)</span>
            </span>
            <div className="flex items-center gap-4 text-xs font-mono">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-purple-500 inline-block" />
                <span className="text-slate-300">Ideal GTO</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-cyan-400 inline-block" />
                <span className="text-slate-300">Bot Atual</span>
              </div>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={frequencyData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="position" stroke="#94a3b8" tick={{ fontSize: 12, fontWeight: 700 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} unit="%" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '12px' }}
                  itemStyle={{ color: '#f8fafc' }}
                  formatter={(val: any, name: any) => [
                    `${val}%`,
                    name === 'idealFreqPct' ? 'Frequência Ideal (GTO)' : 'Frequência Atual do Bot'
                  ]}
                />
                <Bar dataKey="idealFreqPct" name="idealFreqPct" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="botFreqPct" name="botFreqPct" radius={[4, 4, 0, 0]}>
                  {frequencyData.map((entry, index) => {
                    const color =
                      entry.status === 'BALANCED' ? '#06b6d4' :
                      entry.status === 'OVER_OPENING' ? '#f43f5e' :
                      '#f59e0b';
                    return <Cell key={`cell-${index}`} fill={color} />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right: Discrepancy Delta Bar Chart (4 cols) */}
        <div className="lg:col-span-4 bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>Discrepância (Delta %)</span>
              </span>
              <span className="text-[10px] font-mono text-slate-500">Tolerância: ±{tolerancePct}%</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
              Diferença entre o RFI real do bot e a solução GTO. Barras em vermelho indicam vazamento por excesso; em âmbar indicam falta de agressão.
            </p>
          </div>

          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={frequencyData} layout="vertical" margin={{ top: 5, right: 15, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis type="number" stroke="#64748b" tick={{ fontSize: 10 }} unit="%" domain={[-10, 10]} />
                <YAxis dataKey="position" type="category" stroke="#94a3b8" tick={{ fontSize: 11, fontWeight: 700 }} width={35} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '12px' }}
                  formatter={(val: any) => [`${val > 0 ? `+${val}` : val}%`, 'Desvio vs GTO']}
                />
                <ReferenceLine x={0} stroke="#475569" strokeWidth={1.5} />
                <ReferenceLine x={tolerancePct} stroke="#f43f5e" strokeDasharray="2 2" strokeWidth={1} />
                <ReferenceLine x={-tolerancePct} stroke="#f59e0b" strokeDasharray="2 2" strokeWidth={1} />
                <Bar dataKey="delta" radius={[0, 4, 4, 0]}>
                  {frequencyData.map((entry, index) => (
                    <Cell
                      key={`delta-${index}`}
                      fill={
                        entry.status === 'BALANCED' ? '#10b981' :
                        entry.status === 'OVER_OPENING' ? '#f43f5e' :
                        '#f59e0b'
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-400">
            <span className="flex items-center gap-1 text-rose-400 font-bold">
              <ArrowUpRight className="w-3 h-3" /> Over-Opening
            </span>
            <span className="flex items-center gap-1 text-amber-400 font-bold">
              <ArrowDownRight className="w-3 h-3" /> Under-Opening
            </span>
          </div>
        </div>
      </div>

      {/* Discrepancy Cards & Remediation Grid */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider block">
            Diagnóstico Posição por Posição & Ações Corretivas no Motor:
          </span>
          <span className="text-[11px] font-mono text-slate-500">
            Clique em "Ajustar Range" para aplicar correção imediata na posição desejada
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          {frequencyData.map(item => {
            const isBalanced = item.status === 'BALANCED';
            const isOver = item.status === 'OVER_OPENING';
            const isSelected = selectedPositionDetail === item.position;

            return (
              <div
                key={item.position}
                onClick={() => setSelectedPositionDetail(item.position)}
                className={`p-3.5 rounded-2xl border transition-all cursor-pointer space-y-2.5 flex flex-col justify-between ${
                  isSelected ? 'ring-2 ring-purple-500 shadow-lg' : ''
                } ${
                  isBalanced
                    ? 'bg-slate-950/80 border-emerald-900/40 hover:border-emerald-600/60'
                    : isOver
                    ? 'bg-rose-950/20 border-rose-800/70 hover:border-rose-600 shadow-md'
                    : 'bg-amber-950/20 border-amber-800/70 hover:border-amber-600 shadow-md'
                }`}
              >
                <div className="space-y-2">
                  {/* Position Header & Badge */}
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded-lg bg-slate-900 text-slate-100 font-black font-mono text-xs border border-slate-700">
                      {item.position}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                      isBalanced ? 'bg-emerald-950 text-emerald-300 border-emerald-700' :
                      isOver ? 'bg-rose-950 text-rose-300 border-rose-700' :
                      'bg-amber-950 text-amber-300 border-amber-700'
                    }`}>
                      {isBalanced ? 'EQUILIBRADO' : isOver ? 'OVER-OPEN' : 'SUB-ABERTURA'}
                    </span>
                  </div>

                  {/* Frequencies and Delta */}
                  <div className="space-y-1 font-mono text-xs">
                    <div className="flex justify-between text-slate-400">
                      <span>Ideal GTO:</span>
                      <strong className="text-purple-300">{item.idealFreqPct}%</strong>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Bot Atual:</span>
                      <strong className={isBalanced ? 'text-slate-200' : isOver ? 'text-rose-400' : 'text-amber-400'}>
                        {item.botFreqPct}%
                      </strong>
                    </div>
                    <div className="flex justify-between pt-1 border-t border-slate-800/80">
                      <span className="text-slate-500">Discrepância:</span>
                      <strong className={`font-black ${
                        isBalanced ? 'text-emerald-400' : isOver ? 'text-rose-400' : 'text-amber-400'
                      }`}>
                        {item.delta > 0 ? `+${item.delta}` : item.delta}%
                      </strong>
                    </div>
                  </div>

                  {/* Tactical Hint */}
                  <p className="text-[11px] text-slate-400 leading-snug line-clamp-3">
                    {item.recommendedAction}
                  </p>
                </div>

                {/* Adjust Button */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleCalibratePosition(item.position);
                  }}
                  disabled={isBalanced}
                  className={`w-full py-1.5 rounded-lg font-mono text-xs font-bold transition-all flex items-center justify-center gap-1 cursor-pointer ${
                    isBalanced
                      ? 'bg-slate-900 border border-slate-800 text-slate-600 cursor-default'
                      : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-sm'
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>{isBalanced ? 'Calibrado' : 'Ajustar Range'}</span>
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
