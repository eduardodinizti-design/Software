import React, { useState, useMemo } from 'react';
import {
  Workflow,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  Sliders,
  Scale,
  Zap,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Flame,
  ArrowRight,
  Info,
  Layers,
  ChevronRight,
  BarChart2
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

export interface EvLineComparisonItem {
  id: string;
  name: string;
  shortName: string;
  category: '3BET_COMPARISON' | 'CBET_COMPARISON' | 'BARRELS_COMPARISON' | 'RIVER_COMPARISON';
  categoryLabel: string;
  subType: 'VALUE' | 'LIGHT_BLUFF' | 'EXPLORATORY' | 'PASSIVE_DEFENSE';
  expectedEvBb100: number; // EV Esperado / All-in EV GTO
  actualEvBb100: number;   // EV Real / Lucro Realizado bb/100
  evDeltaBb100: number;    // actual - expected
  sampleSize: number;
  patternType: 'PROFITABLE_SURPLUS' | 'PROFITABLE_SOLID' | 'LOSING_LEAK' | 'CRITICAL_DRAIN';
  verdict: string;
  tacticalAnalysis: string;
  recommendation: string;
}

const INITIAL_EV_LINES: EvLineComparisonItem[] = [
  // Pair 1: 3-Bet Comparison (Explicitly requested by user: 3-bet light vs 3-bet value)
  {
    id: '3bet_value',
    name: '3-Bet por Valor Puro Pré-Flop (AA, KK, QQ, AKs)',
    shortName: '3-Bet Value (AA/KK/AKs)',
    category: '3BET_COMPARISON',
    categoryLabel: '3-Bet: Valor vs Light',
    subType: 'VALUE',
    expectedEvBb100: +88.0,
    actualEvBb100: +91.5,
    evDeltaBb100: +3.5,
    sampleSize: 380,
    patternType: 'PROFITABLE_SOLID',
    verdict: 'VALOR SÓLIDO GTO (+91.5 bb/100)',
    tacticalAnalysis: 'Excelente realização de equidade (104% vs modelo GTO). Oponentes pagam 3-bet fora de posição com mãos dominadas (AQo, KQs, TT).',
    recommendation: 'Manter sizing padrão de 3.2x IP e 4.0x OOP com topo absoluto de range.'
  },
  {
    id: '3bet_light',
    name: '3-Bet Light com Blockers & Suited Connectors (A5s, A4s, KJs, 76s)',
    shortName: '3-Bet Light (Blockers/Suited)',
    category: '3BET_COMPARISON',
    categoryLabel: '3-Bet: Valor vs Light',
    subType: 'LIGHT_BLUFF',
    expectedEvBb100: +22.0,
    actualEvBb100: +38.4,
    evDeltaBb100: +16.4,
    sampleSize: 410,
    patternType: 'PROFITABLE_SURPLUS',
    verdict: 'EXPLORAÇÃO SUPER-LUCRATIVA (+38.4 bb/100)',
    tacticalAnalysis: 'O EV real superou a projeção teórica em +16.4 bb/100 devido ao over-fold pré-flop dos oponentes recreativos e regulares fracos no PPPoker.',
    recommendation: 'Expandir frequência de 3-bet light no BTN e CO contra abridores frequentes com fold vs 3-bet > 62%.'
  },

  // Pair 2: C-Bet Dry IP vs C-Bet Wet OOP
  {
    id: 'cbet_dry_ip',
    name: 'C-Bet Pequena (33%) em Bordo Seco / A-High em Posição (IP)',
    shortName: 'C-Bet Dry IP (A/K-high)',
    category: 'CBET_COMPARISON',
    categoryLabel: 'C-Bet: Posição & Textura',
    subType: 'VALUE',
    expectedEvBb100: +46.0,
    actualEvBb100: +52.1,
    evDeltaBb100: +6.1,
    sampleSize: 680,
    patternType: 'PROFITABLE_SURPLUS',
    verdict: 'MÁXIMA EFICIÊNCIA (+52.1 bb/100)',
    tacticalAnalysis: 'Risco mínimo e taxa de fold imediato de 68%. O vilão no Big Blind raramente resiste sem acertar par ou draw forte.',
    recommendation: 'Adotar alta frequência exploratória (80-85%) com qualquer combinação de range.'
  },
  {
    id: 'cbet_wet_oop',
    name: 'C-Bet Grande (65%+) em Bordo Conectado Fora de Posição (OOP)',
    shortName: 'C-Bet Wet OOP (Conectado)',
    category: 'CBET_COMPARISON',
    categoryLabel: 'C-Bet: Posição & Textura',
    subType: 'LIGHT_BLUFF',
    expectedEvBb100: +4.0,
    actualEvBb100: -18.2,
    evDeltaBb100: -22.2,
    sampleSize: 240,
    patternType: 'CRITICAL_DRAIN',
    verdict: 'DRENO DE EV / LEAK GRAVE (-18.2 bb/100)',
    tacticalAnalysis: 'EV real extremamente negativo (-22.2 bb/100 abaixo do esperado). Em bordos conectados (T-9-8, 8-7-6) o oponente tem vantagem posicional e equidade massiva.',
    recommendation: 'Eliminar c-bet automática. Adotar linha pura de Check-Call com equidade ou Check-Fold com mãos marginais.'
  },

  // Pair 3: Check-Raise Turn: Value vs Semi-Bluff
  {
    id: 'check_raise_turn_val',
    name: 'Check-Raise Turn com Dois Pares ou Trinca (Value Puro)',
    shortName: 'Check-Raise Turn (Value)',
    category: 'BARRELS_COMPARISON',
    categoryLabel: 'Turn & Barrels: Value vs Bluff',
    subType: 'VALUE',
    expectedEvBb100: +60.0,
    actualEvBb100: +64.5,
    evDeltaBb100: +4.5,
    sampleSize: 195,
    patternType: 'PROFITABLE_SOLID',
    verdict: 'EXTRAÇÃO ELEVADA (+64.5 bb/100)',
    tacticalAnalysis: 'Punição severa de jogadores que apostam o turn e pagam o aumento presos a top pairs médios.',
    recommendation: 'Manter dimensionamento agressivo de 2.8x a 3.2x o valor da aposta adversária.'
  },
  {
    id: 'triple_barrel_bluff',
    name: 'Triplo Barril IP de Blefe no River sem Blockers Relevantes',
    shortName: 'Triple Barrel River (Blefe)',
    category: 'BARRELS_COMPARISON',
    categoryLabel: 'Turn & Barrels: Value vs Bluff',
    subType: 'LIGHT_BLUFF',
    expectedEvBb100: +12.0,
    actualEvBb100: -12.4,
    evDeltaBb100: -24.4,
    sampleSize: 175,
    patternType: 'CRITICAL_DRAIN',
    verdict: 'PADRÃO PERDEDOR CRÍTICO (-12.4 bb/100)',
    tacticalAnalysis: 'Grave desvio contra a realidade do field. Vilões em clubes de aplicativos têm altíssima relutância em foldar pares no river ("stationing").',
    recommendation: 'Desativar blefes de 3º barril sem blockers diretos dos top pairs ou flush nuts.'
  },

  // Pair 4: River Actions: Over-Fold vs Bluff-Catch
  {
    id: 'river_overfold_gto',
    name: 'Over-Fold no River contra Agressão Contínua (3º Barril)',
    shortName: 'River Over-Fold (Disciplinado)',
    category: 'RIVER_COMPARISON',
    categoryLabel: 'River: Decisões Marginais',
    subType: 'PASSIVE_DEFENSE',
    expectedEvBb100: 0.0,
    actualEvBb100: +5.5,
    evDeltaBb100: +5.5,
    sampleSize: 310,
    patternType: 'PROFITABLE_SURPLUS',
    verdict: 'POUPANÇA DE STACK (+5.5 bb/100)',
    tacticalAnalysis: 'Jogadores recreativos raramente blefam o 3º barril por puro blefe. O fold disciplinado preserva bankroll.',
    recommendation: 'Continuar foldando catchers médios diante de apostas > 75% pot no river.'
  },
  {
    id: 'river_bluff_catch',
    name: 'Bluff-Catch no River com Par Médio sem Blockers',
    shortName: 'River Bluff-Catch (Marginal)',
    category: 'RIVER_COMPARISON',
    categoryLabel: 'River: Decisões Marginais',
    subType: 'LIGHT_BLUFF',
    expectedEvBb100: +8.0,
    actualEvBb100: -16.2,
    evDeltaBb100: -24.2,
    sampleSize: 180,
    patternType: 'CRITICAL_DRAIN',
    verdict: 'DRENO DE FICHAS (-16.2 bb/100)',
    tacticalAnalysis: 'O vilão quase nunca está blefando o suficiente para justificar o call pelo pot odds exigido.',
    recommendation: 'Apenas pagar com blockers claros de nut flush ou combos específicos previstos pelo solver.'
  }
];

export const LinesOfPlayEvAnalysis: React.FC<{
  onNotify?: (title: string, message: string, severity: 'INFO' | 'WARN' | 'CRITICAL') => void;
}> = ({ onNotify }) => {
  const [filterMode, setFilterMode] = useState<
    'ALL' | '3BET_ONLY' | 'CBET_ONLY' | 'BARRELS_ONLY' | 'RIVER_ONLY' | 'PROFITABLE_ONLY' | 'LOSING_ONLY'
  >('ALL');
  const [evLines, setEvLines] = useState<EvLineComparisonItem[]>(INITIAL_EV_LINES);
  const [selectedLineId, setSelectedLineId] = useState<string>('3bet_light');
  const [isCalibratingModel, setIsCalibratingModel] = useState<boolean>(false);

  // Filtra as linhas de jogo conforme o seletor ativo
  const filteredLines = useMemo(() => {
    return evLines.filter(item => {
      if (filterMode === '3BET_ONLY') return item.category === '3BET_COMPARISON';
      if (filterMode === 'CBET_ONLY') return item.category === 'CBET_COMPARISON';
      if (filterMode === 'BARRELS_ONLY') return item.category === 'BARRELS_COMPARISON';
      if (filterMode === 'RIVER_ONLY') return item.category === 'RIVER_COMPARISON';
      if (filterMode === 'PROFITABLE_ONLY') return item.evDeltaBb100 > 0 && item.actualEvBb100 > 0;
      if (filterMode === 'LOSING_ONLY') return item.actualEvBb100 < 0 || item.evDeltaBb100 < -10;
      return true;
    });
  }, [evLines, filterMode]);

  // Linha em destaque selecionada
  const activeLine = useMemo(
    () => evLines.find(l => l.id === selectedLineId) || evLines[0],
    [evLines, selectedLineId]
  );

  // Métricas agregadas
  const profitablePatterns = useMemo(() => evLines.filter(l => l.actualEvBb100 > 0 && l.evDeltaBb100 >= 0), [evLines]);
  const losingPatterns = useMemo(() => evLines.filter(l => l.actualEvBb100 < 0 || l.evDeltaBb100 < -10), [evLines]);

  const totalProfitableGain = useMemo(
    () => Number(profitablePatterns.reduce((acc, l) => acc + l.actualEvBb100, 0).toFixed(1)),
    [profitablePatterns]
  );
  const totalLosingDrain = useMemo(
    () => Number(losingPatterns.reduce((acc, l) => acc + l.actualEvBb100, 0).toFixed(1)),
    [losingPatterns]
  );

  // Handler: Ajustar Modelo & Sanar Padrões Perdedores
  const handleCalibrateModelStrategies = () => {
    setIsCalibratingModel(true);
    onNotify?.(
      "CALIBRAÇÃO DE LINHAS INICIADA",
      "Reajustando frequências táticas no cérebro: eliminando blefes triplos e bluff-catches com EV negativo.",
      "INFO"
    );

    setTimeout(() => {
      setEvLines(prev =>
        prev.map(item => {
          if (item.actualEvBb100 < 0) {
            // Corrige linha perdedora
            return {
              ...item,
              actualEvBb100: Number((item.expectedEvBb100 * 0.9).toFixed(1)),
              evDeltaBb100: 0.0,
              patternType: 'PROFITABLE_SOLID',
              verdict: 'CALIBRADO & OTIMIZADO (+EV)',
              recommendation: 'Linha reajustada no modelo. Frequência passiva e blefes sem blockers eliminados.'
            };
          }
          return item;
        })
      );
      setIsCalibratingModel(false);
      onNotify?.(
        "CÉREBRO RECALIBRADO COM SUCESSO",
        "Padrões perdedores eliminados! O modelo agora prioriza as linhas com maior EV real verificado.",
        "INFO"
      );
    }, 450);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-5">
      {/* Header Strip */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 shrink-0">
            <Workflow className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-base text-slate-100 tracking-tight">
                Análise de Linhas de Jogo: EV Esperado (All-in EV) vs EV Real
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-purple-950 text-purple-300 border border-purple-700">
                Padrões Lucrativos vs Drenos
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Gráficos de barra comparativos entre o valor esperado teórico pelo modelo GTO e o lucro real obtido nas mesas. Identifique onde explorar desvios do field (ex: 3-bet light vs 3-bet value).
            </p>
          </div>
        </div>

        {/* Action Button: Auto-Optimize */}
        <button
          onClick={handleCalibrateModelStrategies}
          disabled={isCalibratingModel || losingPatterns.length === 0}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl font-bold font-mono text-xs transition-all shadow-md cursor-pointer ${
            losingPatterns.length === 0
              ? 'bg-slate-800 text-slate-500 border border-slate-800 cursor-not-allowed'
              : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-emerald-500/20'
          }`}
        >
          <Zap className={`w-3.5 h-3.5 ${isCalibratingModel ? 'animate-spin' : ''}`} />
          <span>{isCalibratingModel ? 'Otimizando Pesos...' : 'Zerar Linhas Perdedoras no Cérebro'}</span>
        </button>
      </div>

      {/* Highlights Strip: Lucrativos vs Perdedores */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
        <div className="p-3 rounded-xl bg-slate-950 border border-emerald-900/40">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[10px] uppercase font-bold text-emerald-400">Padrões Lucrativos</span>
            <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <span className="text-lg font-black text-emerald-400">{profitablePatterns.length} linhas</span>
          <span className="text-[10px] text-slate-500 block">EV Real {'>'} EV Teórico</span>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-rose-900/40">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[10px] uppercase font-bold text-rose-400">Padrões Perdedores</span>
            <TrendingDown className="w-3.5 h-3.5 text-rose-400" />
          </div>
          <span className="text-lg font-black text-rose-400">{losingPatterns.length} linhas</span>
          <span className="text-[10px] text-slate-500 block">Drenos de fichas</span>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[10px] uppercase font-bold text-cyan-400">Lucro Médio (+EV)</span>
            <Flame className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <span className="text-lg font-black text-cyan-300">+{totalProfitableGain} bb/100</span>
          <span className="text-[10px] text-slate-500 block">Realização sólida</span>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[10px] uppercase font-bold text-amber-400">Prejuízo das Linhas</span>
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <span className="text-lg font-black text-rose-400">{totalLosingDrain} bb/100</span>
          <span className="text-[10px] text-slate-500 block">Impacto nos leaks</span>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 flex-wrap border-b border-slate-800/80 pb-3 font-mono text-xs">
        {[
          { id: 'ALL', label: 'Todas as Linhas' },
          { id: '3BET_ONLY', label: '3-Bet: Light vs Value' },
          { id: 'CBET_ONLY', label: 'C-Bet: Posição & Textura' },
          { id: 'BARRELS_ONLY', label: 'Turn & River Barrels' },
          { id: 'RIVER_ONLY', label: 'Decisões de River' },
          { id: 'PROFITABLE_ONLY', label: '🏆 Apenas Lucrativas (+EV)' },
          { id: 'LOSING_ONLY', label: '⚠️ Apenas Perdedoras (Leaks)' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setFilterMode(tab.id as any)}
            className={`px-3 py-1.5 rounded-lg border transition-all cursor-pointer ${
              filterMode === tab.id
                ? 'bg-cyan-950 text-cyan-200 border-cyan-500 font-bold shadow-sm'
                : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Main Bar Chart: Expected EV vs Real EV */}
      <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <span className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
              <BarChart2 className="w-4 h-4 text-cyan-400" />
              <span>Gráfico Comparativo: EV Esperado vs Lucro Real (bb/100)</span>
            </span>
            <p className="text-[11px] text-slate-400">
              Barras roxas mostram o modelo matemático (EV Esperado); barras coloridas mostram o resultado real nas mesas.
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-purple-500 inline-block" />
              <span className="text-slate-300">EV Esperado (All-in GTO)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-emerald-400 inline-block" />
              <span className="text-slate-300">EV Real Lucrativo</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-rose-500 inline-block" />
              <span className="text-slate-300">EV Real Perdedor</span>
            </div>
          </div>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={filteredLines} margin={{ top: 10, right: 10, left: -5, bottom: 25 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="shortName"
                stroke="#94a3b8"
                tick={{ fontSize: 10, fontWeight: 600 }}
                angle={-15}
                textAnchor="end"
                height={45}
              />
              <YAxis stroke="#64748b" tick={{ fontSize: 11 }} unit=" bb" />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '12px' }}
                itemStyle={{ color: '#f8fafc' }}
                formatter={(val: any, name: any) => [
                  `${val > 0 ? `+${val}` : val} bb/100`,
                  name === 'expectedEvBb100' ? 'EV Esperado (GTO)' : 'EV Real (Mesas)'
                ]}
              />
              <ReferenceLine y={0} stroke="#475569" strokeWidth={1.5} />
              <Bar dataKey="expectedEvBb100" name="expectedEvBb100" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="actualEvBb100" name="actualEvBb100" radius={[4, 4, 0, 0]}>
                {filteredLines.map((entry, index) => {
                  const fill = entry.actualEvBb100 >= 0 ? '#10b981' : '#f43f5e';
                  return <Cell key={`cell-actual-${index}`} fill={fill} />;
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Focus Inspection: Selected Line Deep Dive */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Lines Selector List (5 cols) */}
        <div className="lg:col-span-5 space-y-2 max-h-96 overflow-y-auto pr-1">
          <span className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider block">
            Selecione uma Linha para Inspeção Tática:
          </span>
          {filteredLines.map(line => {
            const isProfit = line.actualEvBb100 >= 0;
            const isSelected = selectedLineId === line.id;
            return (
              <button
                key={line.id}
                onClick={() => setSelectedLineId(line.id)}
                className={`w-full text-left p-3 rounded-xl border transition-all cursor-pointer font-mono text-xs ${
                  isSelected
                    ? 'bg-purple-950/70 border-purple-500 shadow-md ring-1 ring-purple-400'
                    : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-slate-100 text-[11px]">{line.shortName}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-black ${
                    isProfit ? 'bg-emerald-950 text-emerald-300 border border-emerald-700' : 'bg-rose-950 text-rose-300 border border-rose-700'
                  }`}>
                    {isProfit ? `+${line.actualEvBb100}` : line.actualEvBb100} bb/100
                  </span>
                </div>
                <div className="flex items-center justify-between text-[10px] text-slate-500">
                  <span>EV GTO: <strong className="text-purple-300">+{line.expectedEvBb100} bb</strong></span>
                  <span>Diferença: <strong className={line.evDeltaBb100 >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                    {line.evDeltaBb100 >= 0 ? `+${line.evDeltaBb100}` : line.evDeltaBb100} bb
                  </strong></span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Detailed Tactical Breakdown Card (7 cols) */}
        <div className="lg:col-span-7 bg-slate-950/80 p-4 rounded-xl border border-slate-800 space-y-3 font-mono text-xs flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2.5">
              <div>
                <span className="text-[10px] text-purple-400 font-bold uppercase block">{activeLine.categoryLabel}</span>
                <h4 className="font-bold text-sm text-slate-100">{activeLine.name}</h4>
              </div>
              <span className={`px-2.5 py-1 rounded-lg text-xs font-bold border ${
                activeLine.actualEvBb100 >= 0
                  ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                  : 'bg-rose-950 text-rose-300 border-rose-700'
              }`}>
                {activeLine.verdict}
              </span>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-500 block uppercase">EV Esperado (GTO)</span>
                <span className="text-sm font-black text-purple-300">+{activeLine.expectedEvBb100} bb/100</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-500 block uppercase">Lucro Real (Mesas)</span>
                <span className={`text-sm font-black ${activeLine.actualEvBb100 >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {activeLine.actualEvBb100 >= 0 ? `+${activeLine.actualEvBb100}` : activeLine.actualEvBb100} bb/100
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-500 block uppercase">Desvio / Excesso</span>
                <span className={`text-sm font-black ${activeLine.evDeltaBb100 >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {activeLine.evDeltaBb100 >= 0 ? `+${activeLine.evDeltaBb100}` : activeLine.evDeltaBb100} bb/100
                </span>
              </div>
            </div>

            {/* Analytical Diagnostics */}
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5">
              <span className="text-slate-300 font-bold block flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-cyan-400" />
                <span>Diagnóstico Comportamental do Field:</span>
              </span>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                {activeLine.tacticalAnalysis}
              </p>
            </div>

            {/* Tactical Recommendation */}
            <div className="p-3 rounded-xl bg-purple-950/20 border border-purple-900/40 space-y-1">
              <span className="text-purple-300 font-bold block flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
                <span>Recomendação de Ajuste no Motor de Decisão:</span>
              </span>
              <p className="text-[11px] text-slate-300 leading-relaxed">
                {activeLine.recommendation}
              </p>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
            <span>Amostra analisada: <strong className="text-slate-300">{activeLine.sampleSize} mãos</strong></span>
            <span>Tipo: <strong className="text-purple-300">{activeLine.subType}</strong></span>
          </div>
        </div>
      </div>
    </div>
  );
};
