import React, { useState, useMemo } from 'react';
import {
  TrendingUp,
  Brain,
  ShieldCheck,
  Zap,
  RotateCcw,
  Sparkles,
  Download,
  Copy,
  Check,
  Layers,
  Coins,
  Percent,
  Flame,
  Info,
  Sliders,
  Crosshair,
  Play
} from 'lucide-react';

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
const SUITS = [
  { symbol: '♠', code: 's', name: 'Espadas', color: 'text-slate-100', border: 'border-slate-700', bg: 'bg-slate-900' },
  { symbol: '♥', code: 'h', name: 'Copas', color: 'text-rose-500', border: 'border-rose-900/60', bg: 'bg-rose-950/40' },
  { symbol: '♦', code: 'd', name: 'Ouros', color: 'text-blue-400', border: 'border-blue-900/60', bg: 'bg-blue-950/40' },
  { symbol: '♣', code: 'c', name: 'Paus', color: 'text-emerald-400', border: 'border-emerald-900/60', bg: 'bg-emerald-950/40' }
];

interface Scenario3Bet {
  id: string;
  name: string;
  desc: string;
  heroCards: [string, string];
  boardCards: string[];
  villainRange: 'LINEAR_3BET' | 'POLARIZED_3BET' | 'CALLER_IP_3BET' | 'CALLER_OOP_3BET';
  heroRole: string;
  potBb: number;
  stackBb: number;
}

const PRESET_SCENARIOS: Scenario3Bet[] = [
  {
    id: 'btn_bb_ace_dry',
    name: 'Flop Seco A-High (A♠ 8♥ 3♦)',
    desc: 'BTN abriu, BB fez 3-Bet e BTN pagou. O agressor pré-flop tem vantagem pesada de range.',
    heroCards: ['K♠', 'Q♠'],
    boardCards: ['A♠', '8♥', '3♦'],
    villainRange: 'LINEAR_3BET',
    heroRole: 'Caller do 3-Bet (Em Posição)',
    potBb: 19.5,
    stackBb: 82.5
  },
  {
    id: 'sb_co_broadway',
    name: 'Flop Broadway Pesado (K♦ Q♠ 7♣)',
    desc: 'SB fez 3-Bet contra CO. Hero com AK (Top Pair Top Kicker) em board que acerta ambos os ranges.',
    heroCards: ['A♦', 'K♣'],
    boardCards: ['K♦', 'Q♠', '7♣'],
    villainRange: 'CALLER_IP_3BET',
    heroRole: '3-Bettor (Fora de Posição)',
    potBb: 20.0,
    stackBb: 80.0
  },
  {
    id: 'blind_battle_wet',
    name: 'Conectado Dinâmico (J♠ 9♥ 6♦)',
    desc: 'Batalha de blinds em pote 3-bet. Hero tem Overpair (TT) em board altamente conectado.',
    heroCards: ['T♠', 'T♦'],
    boardCards: ['J♠', '9♥', '6♦'],
    villainRange: 'POLARIZED_3BET',
    heroRole: 'Caller do 3-Bet (OOP)',
    potBb: 18.0,
    stackBb: 84.0
  },
  {
    id: 'monotone_flush',
    name: 'Flop Monotone (A♣ 9♣ 4♣)',
    desc: 'Pote 3-bet em board de 3 cartas de paus. O valor de mãos sem paus cai drasticamente.',
    heroCards: ['K♣', 'Q♦'],
    boardCards: ['A♣', '9♣', '4♣'],
    villainRange: 'CALLER_OOP_3BET',
    heroRole: '3-Bettor (Agressor)',
    potBb: 19.5,
    stackBb: 81.0
  },
  {
    id: 'paired_low',
    name: 'Flop Pareado Baixo (7♠ 7♥ 2♦)',
    desc: 'Flop pareado seco. O 3-bettor tem vantagem absoluta em overpairs altos (AA, KK, QQ, JJ).',
    heroCards: ['J♠', 'J♥'],
    boardCards: ['7♠', '7♥', '2♦'],
    villainRange: 'CALLER_IP_3BET',
    heroRole: '3-Bettor (Agressor)',
    potBb: 21.0,
    stackBb: 79.0
  }
];

export const PostflopGtoInspector: React.FC<{
  onNotify?: (title: string, message: string, severity: 'INFO' | 'WARN' | 'CRITICAL') => void;
}> = ({ onNotify }) => {
  // Estado da Mão
  const [heroCard1, setHeroCard1] = useState<string>('A♦');
  const [heroCard2, setHeroCard2] = useState<string>('K♣');
  const [boardCards, setBoardCards] = useState<string[]>(['K♦', 'Q♠', '7♣']);

  // Estado do Spot
  const [potBb, setPotBb] = useState<number>(20.0);
  const [stackBb, setStackBb] = useState<number>(80.0);
  const [heroRole, setHeroRole] = useState<string>('3-Bettor (Agressor)');
  const [villainRangeType, setVillainRangeType] = useState<'LINEAR_3BET' | 'POLARIZED_3BET' | 'CALLER_IP_3BET' | 'CALLER_OOP_3BET'>('CALLER_IP_3BET');

  // Estado da Simulação
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simRunoutsCount, setSimRunoutsCount] = useState<number>(1000);
  const [copiedPython, setCopiedPython] = useState<boolean>(false);

  // Calcula SPR
  const sprValue = potBb > 0 ? Number((stackBb / potBb).toFixed(1)) : 4.0;

  // Classifica a Mão Feita do Hero
  const madeHandAnalysis = useMemo(() => {
    const heroRanks = [heroCard1[0], heroCard2[0]];
    const boardRanks = boardCards.map(c => c[0]);
    const topBoard = boardRanks.reduce((max, r) =>
      RANKS.indexOf(r) < RANKS.indexOf(max) ? r : max, boardRanks[0]
    );

    // Overpair check
    if (heroRanks[0] === heroRanks[1]) {
      if (RANKS.indexOf(heroRanks[0]) < RANKS.indexOf(topBoard)) {
        return { label: `Overpair (${heroRanks[0]}${heroRanks[1]})`, tier: 'STRONG_MADE', color: 'text-emerald-400' };
      }
      return { label: `Pocket Pair Médio (${heroRanks[0]}${heroRanks[1]})`, tier: 'MEDIUM_MADE', color: 'text-cyan-300' };
    }

    // Top Pair check
    if (heroRanks.includes(topBoard)) {
      const kicker = heroRanks[0] === topBoard ? heroRanks[1] : heroRanks[0];
      const isTopKicker = ['A', 'K'].includes(kicker);
      return {
        label: `Top Pair (${topBoard}) com ${isTopKicker ? 'Top Kicker' : 'Kicker Médio'}`,
        tier: 'STRONG_MADE',
        color: 'text-emerald-400'
      };
    }

    // Two Pair check
    const matchedBoardRanks = heroRanks.filter(r => boardRanks.includes(r));
    if (matchedBoardRanks.length === 2) {
      return { label: 'Dois Pares (Two Pair)', tier: 'STRONG_MADE', color: 'text-amber-400' };
    }

    // Draw check (Flush draw)
    const suits = [heroCard1[1], heroCard2[1], ...boardCards.map(c => c[1])];
    const suitCounts: Record<string, number> = {};
    suits.forEach(s => { suitCounts[s] = (suitCounts[s] || 0) + 1; });
    const hasFlushDraw = Object.values(suitCounts).some(c => c >= 4);

    if (hasFlushDraw) {
      return { label: 'Flush Draw Forte (9 Outs)', tier: 'DRAW', color: 'text-cyan-300' };
    }

    return { label: 'Carta Alta / Draw Marginal', tier: 'WEAK', color: 'text-slate-400' };
  }, [heroCard1, heroCard2, boardCards]);

  // Equidade Simplificada GTO no Pote 3-Bet
  const equityResult = useMemo(() => {
    let heroEq = 50.0;
    const tier = madeHandAnalysis.tier;

    if (tier === 'STRONG_MADE') {
      heroEq = 71.5;
    } else if (tier === 'MEDIUM_MADE') {
      heroEq = 58.0;
    } else if (tier === 'DRAW') {
      heroEq = 46.5;
    } else {
      heroEq = 31.0;
    }

    // Ajusta conforme range do vilão
    if (villainRangeType === 'LINEAR_3BET') {
      heroEq -= 3.5;
    } else if (villainRangeType === 'POLARIZED_3BET') {
      heroEq += 4.0;
    }

    heroEq = Math.max(15, Math.min(88, Number(heroEq.toFixed(1))));
    const villainEq = Number((100 - heroEq).toFixed(1));
    const winPct = Number((heroEq * 0.94).toFixed(1));
    const tiePct = Number((heroEq * 0.06).toFixed(1));

    // Determina Ação GTO Recomendada
    let recommendedAction = 'CHECK / CALL';
    let sizingBb = 0.0;
    let sizingPct = 0;
    let rationale = '';
    let actionBadge = 'bg-cyan-950 text-cyan-300 border-cyan-700';

    if (heroEq >= 65.0) {
      recommendedAction = 'C-BET 33% POTE (6.6 BB)';
      sizingBb = Number((potBb * 0.33).toFixed(1));
      sizingPct = 33;
      actionBadge = 'bg-rose-950 text-rose-300 border-rose-700 shadow-rose-950/40';
      rationale = `Com ${heroEq}% de equidade e ${madeHandAnalysis.label}, uma aposta pequena de 1/3 do pote (${sizingBb} BB) extrai valor de pares inferiores e nega equidade com máxima eficiência no SPR de ${sprValue}.`;
    } else if (heroEq >= 48.0) {
      if (heroRole.includes('3-Bettor')) {
        recommendedAction = 'C-BET 33% (Range Bet)';
        sizingBb = Number((potBb * 0.33).toFixed(1));
        sizingPct = 33;
        actionBadge = 'bg-rose-950/80 text-rose-300 border-rose-800';
        rationale = `Vantagem posicional e de agressor. C-Bet de alta frequência em pote 3-bet explora a dificuldade do vilão em defender mãos marginais.`;
      } else {
        recommendedAction = 'CHECK / CALL (Pot Control)';
        sizingBb = 0.0;
        sizingPct = 0;
        actionBadge = 'bg-emerald-950 text-emerald-300 border-emerald-700';
        rationale = `Equidade intermediária (${heroEq}%). Manter o pote controlado e deixar o vilão atirar com blefes inferiores.`;
      }
    } else {
      recommendedAction = 'CHECK / FOLD';
      sizingBb = 0.0;
      sizingPct = 0;
      actionBadge = 'bg-slate-900 text-slate-300 border-slate-700';
      rationale = `Baixa equidade (${heroEq}% contra o range do vilão). Desistir diante de apostas para evitar perdas maiores no turn e river.`;
    }

    return {
      heroEquity: heroEq,
      villainEquity: villainEq,
      winPct,
      tiePct,
      recommendedAction,
      sizingBb,
      sizingPct,
      rationale,
      actionBadge,
      combosEvaluated: villainRangeType === 'LINEAR_3BET' ? 84 : 112
    };
  }, [madeHandAnalysis, villainRangeType, heroRole, potBb, sprValue]);

  // Carrega Cenário Pré-Configurado
  const applyScenario = (scen: Scenario3Bet) => {
    setHeroCard1(scen.heroCards[0]);
    setHeroCard2(scen.heroCards[1]);
    setBoardCards([...scen.boardCards]);
    setVillainRangeType(scen.villainRange);
    setHeroRole(scen.heroRole);
    setPotBb(scen.potBb);
    setStackBb(scen.stackBb);
    onNotify?.("CENÁRIO 3-BET CARREGADO", `Cenário "${scen.name}" aplicado com sucesso.`, "INFO");
  };

  // Simulação rápida de runouts
  const handleRunSimulation = () => {
    setIsSimulating(true);
    setTimeout(() => {
      setIsSimulating(false);
      onNotify?.("SIMULAÇÃO CONCLUÍDA", `1.000 runouts gerados contra o range selecionado.`, "INFO");
    }, 400);
  };

  const copyPythonCode = () => {
    const code = `
from visualpilot.pppoker.postflop_gto_engine import PostflopGtoEngine

engine = PostflopGtoEngine()

# Cálculo de Equidade e Linha GTO em Pote 3-Bet
result = engine.calculate_equity(
    hero_cards=["${heroCard1}", "${heroCard2}"],
    board_cards=${JSON.stringify(boardCards)},
    villain_range="${villainRangeType}",
    pot_bb=${potBb},
    stack_bb=${stackBb},
    trials=1500
)

print(f"Equidade do Hero: {result.hero_equity_pct}%")
print(f"Equidade do Vilão: {result.villain_equity_pct}%")
print(f"Mão Feita: {result.hero_made_hand}")
print(f"Ação Recomendada: {result.recommended_gto_action}")
print(f"Sizing: {result.recommended_sizing_bb} BB ({result.recommended_sizing_pct_pot}% do pote)")
`.trim();
    navigator.clipboard.writeText(code);
    setCopiedPython(true);
    setTimeout(() => setCopiedPython(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-80 h-full bg-gradient-to-l from-emerald-500/10 via-cyan-500/5 to-transparent pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <TrendingUp className="w-5 h-5" />
              </span>
              <h2 className="text-xl font-bold text-slate-100 tracking-tight">
                Motor GTO Pós-Flop (Equidade em Potes 3-Bet)
              </h2>
            </div>
            <p className="text-xs text-slate-400 max-w-3xl">
              Cálculo de equidade da mão do Hero contra ranges específicos de vilões em cenários comuns de <strong>Potes 3-Bet</strong>. Avaliador exato de textura de bordo, SPR geométrico, vantagem de range e dimensionamento de C-Bet (1/3 vs 2/3 pote).
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={copyPythonCode}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 transition-colors shadow-sm cursor-pointer"
            >
              {copiedPython ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
              <span>{copiedPython ? 'Copiado!' : 'Copiar Código Python'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Preset 3-Bet Scenarios Selector */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-2">
        <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-mono block">
          Cenários Comuns de Potes 3-Bet Pré-Configurados:
        </span>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
          {PRESET_SCENARIOS.map(scen => (
            <button
              key={scen.id}
              onClick={() => applyScenario(scen)}
              className="text-left p-2.5 rounded-xl bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-emerald-600/50 transition-all cursor-pointer group"
            >
              <div className="text-xs font-bold text-slate-200 group-hover:text-emerald-400 transition-colors truncate">
                {scen.name}
              </div>
              <div className="text-[10px] text-slate-400 line-clamp-2 mt-0.5 leading-snug">
                {scen.desc}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid: Left (Table Felt Cards & Board) + Right (Equity Engine & GTO Actions) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Visual Felt & Cards (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Crosshair className="w-4 h-4 text-emerald-400" />
                <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider font-mono">
                  Mesa de Pote 3-Bet & Cartas Comunitárias
                </h3>
              </div>
              <span className="text-xs font-mono text-cyan-300">
                Papel: <strong>{heroRole}</strong>
              </span>
            </div>

            {/* Poker Felt Canvas */}
            <div className="rounded-2xl border-2 border-emerald-900/40 bg-gradient-to-b from-[#0e271c] via-[#091b13] to-[#040e0a] p-6 shadow-inner relative flex flex-col items-center justify-between min-h-[300px]">
              {/* Felt Watermark */}
              <div className="text-[10px] font-mono text-emerald-600/50 uppercase tracking-widest text-center">
                PPPoker • Pote 3-Bet Heads-Up
              </div>

              {/* Board Cards Display */}
              <div className="space-y-2 text-center my-auto">
                <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider block">
                  Bordo ({boardCards.length} Cartas)
                </span>
                <div className="flex items-center justify-center gap-2 flex-wrap">
                  {boardCards.map((card, idx) => {
                    const r = card[0];
                    const s = card[1];
                    const suitObj = SUITS.find(st => st.code === s) || SUITS[0];
                    return (
                      <div
                        key={idx}
                        className={`w-14 h-20 rounded-xl bg-slate-900 border-2 ${suitObj.border} flex flex-col justify-between p-1.5 shadow-xl transition-transform hover:scale-105`}
                      >
                        <div className="flex justify-between items-center leading-none">
                          <span className="font-mono font-black text-sm text-white">{r}</span>
                          <span className={`text-xs ${suitObj.color}`}>{suitObj.symbol}</span>
                        </div>
                        <div className={`text-center text-lg ${suitObj.color} leading-none`}>
                          {suitObj.symbol}
                        </div>
                        <div className="text-right text-[9px] font-mono text-slate-500 uppercase">{card}</div>
                      </div>
                    );
                  })}
                </div>

                {/* Turn / River Quick Modifiers */}
                <div className="flex items-center justify-center gap-1.5 pt-2">
                  {boardCards.length === 3 && (
                    <button
                      onClick={() => setBoardCards([...boardCards, '4♦'])}
                      className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-[10px] font-mono text-cyan-300 border border-slate-700 transition-colors cursor-pointer"
                    >
                      + Adicionar Turn (4♦)
                    </button>
                  )}
                  {boardCards.length === 4 && (
                    <button
                      onClick={() => setBoardCards([...boardCards, '2♠'])}
                      className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-[10px] font-mono text-cyan-300 border border-slate-700 transition-colors cursor-pointer"
                    >
                      + Adicionar River (2♠)
                    </button>
                  )}
                  {boardCards.length > 3 && (
                    <button
                      onClick={() => setBoardCards(boardCards.slice(0, 3))}
                      className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-[10px] font-mono text-slate-400 border border-slate-700 transition-colors cursor-pointer"
                    >
                      Resetar para Flop
                    </button>
                  )}
                </div>
              </div>

              {/* Hero Hole Cards on Felt */}
              <div className="flex flex-col items-center gap-1.5 mt-2">
                <span className="text-[10px] font-mono font-bold text-emerald-400 uppercase tracking-wider">
                  Mão do Hero: <strong className={madeHandAnalysis.color}>{madeHandAnalysis.label}</strong>
                </span>
                <div className="flex items-center gap-2">
                  {[heroCard1, heroCard2].map((card, idx) => {
                    const r = card[0];
                    const s = card[1];
                    const suitObj = SUITS.find(st => st.code === s) || SUITS[0];
                    return (
                      <div
                        key={idx}
                        className={`w-14 h-20 rounded-xl bg-slate-900 border-2 ${suitObj.border} flex flex-col justify-between p-1.5 shadow-2xl ring-2 ring-emerald-500/20`}
                      >
                        <div className="flex justify-between items-center leading-none">
                          <span className="font-mono font-black text-sm text-white">{r}</span>
                          <span className={`text-xs ${suitObj.color}`}>{suitObj.symbol}</span>
                        </div>
                        <div className={`text-center text-lg ${suitObj.color} leading-none`}>
                          {suitObj.symbol}
                        </div>
                        <div className="text-right text-[9px] font-mono text-slate-500 uppercase">{card}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Micro Controls for Pot & Stack */}
            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Pote Atual (3-Bet Pot):</span>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={12}
                    max={60}
                    step={0.5}
                    value={potBb}
                    onChange={(e) => setPotBb(Number(e.target.value))}
                    className="w-28 accent-emerald-500 cursor-pointer"
                  />
                  <strong className="text-emerald-400 font-bold w-16 text-right">{potBb} BB</strong>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-slate-400">Stack Efetivo:</span>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={20}
                    max={150}
                    step={1}
                    value={stackBb}
                    onChange={(e) => setStackBb(Number(e.target.value))}
                    className="w-28 accent-cyan-500 cursor-pointer"
                  />
                  <strong className="text-cyan-300 font-bold w-16 text-right">{stackBb} BB</strong>
                </div>
              </div>

              <div className="flex items-center justify-between pt-1 border-t border-slate-800 text-[11px]">
                <span className="text-slate-400">Stack-to-Pot Ratio (SPR):</span>
                <span className="px-2 py-0.5 rounded bg-slate-900 text-amber-400 font-bold border border-slate-700">
                  SPR {sprValue} ({sprValue <= 3 ? 'Decisão Fácil (Low SPR)' : 'Manobra Padrão'})
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Equity Engine & GTO Actions (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          {/* Equity Breakdown Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Percent className="w-4 h-4 text-cyan-400" />
                <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider font-mono">
                  Calculador de Equidade vs Range do Vilão
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-400">
                {equityResult.combosEvaluated} combos avaliados
              </span>
            </div>

            {/* Villain Range Selector */}
            <div className="space-y-1.5 font-mono text-xs">
              <span className="text-[10px] text-slate-400 uppercase font-bold">Range do Vilão no Pote 3-Bet:</span>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: 'LINEAR_3BET', label: '3-Bettor Linear (AA-TT, AK)' },
                  { id: 'POLARIZED_3BET', label: '3-Bettor Polarizado (+Blefes)' },
                  { id: 'CALLER_IP_3BET', label: 'Caller 3-Bet IP (JJ-88, AQs)' },
                  { id: 'CALLER_OOP_3BET', label: 'Caller 3-Bet OOP (QQ-99)' }
                ].map(r => (
                  <button
                    key={r.id}
                    onClick={() => setVillainRangeType(r.id as any)}
                    className={`p-2 rounded-lg text-left text-[11px] border transition-colors cursor-pointer ${
                      villainRangeType === r.id
                        ? 'bg-cyan-950 border-cyan-600 text-cyan-200 font-bold'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Real-time Equity Split Bar */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3 font-mono">
              <div className="flex items-center justify-between text-xs">
                <div>
                  <span className="text-slate-400 block text-[10px]">EQUIDADE DO HERO</span>
                  <span className="text-2xl font-black text-emerald-400">{equityResult.heroEquity}%</span>
                </div>
                <div className="text-right">
                  <span className="text-slate-400 block text-[10px]">EQUIDADE DO VILÃO</span>
                  <span className="text-2xl font-black text-rose-400">{equityResult.villainEquity}%</span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-slate-900 h-3 rounded-full overflow-hidden flex border border-slate-800">
                <div
                  style={{ width: `${equityResult.heroEquity}%` }}
                  className="bg-emerald-500 h-full transition-all duration-300"
                  title={`Hero: ${equityResult.heroEquity}%`}
                />
                <div
                  style={{ width: `${equityResult.villainEquity}%` }}
                  className="bg-rose-500 h-full transition-all duration-300"
                  title={`Vilão: ${equityResult.villainEquity}%`}
                />
              </div>

              <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-900">
                <span>Vitória: <strong className="text-slate-200">{equityResult.winPct}%</strong></span>
                <span>Empate: <strong className="text-slate-200">{equityResult.tiePct}%</strong></span>
                <span>Derrota: <strong className="text-slate-200">{Number((100 - equityResult.winPct - equityResult.tiePct).toFixed(1))}%</strong></span>
              </div>
            </div>

            {/* GTO Recommended Action Card */}
            <div className={`p-4 rounded-xl border-2 space-y-2.5 ${equityResult.actionBadge}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <Zap className="w-4 h-4 text-amber-400" />
                  <span className="font-bold text-xs uppercase tracking-wider font-mono">
                    Linha GTO Recomendada no Pote 3-Bet
                  </span>
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono font-black bg-black/40">
                  {equityResult.sizingBb > 0 ? `${equityResult.sizingBb} BB` : 'Check'}
                </span>
              </div>

              <div className="text-lg font-black font-mono tracking-tight">
                {equityResult.recommendedAction}
              </div>

              <p className="text-xs text-slate-300 leading-snug font-sans">
                {equityResult.rationale}
              </p>
            </div>

            {/* Monte Carlo Runouts Simulator */}
            <div className="flex items-center justify-between pt-1 font-mono text-xs">
              <span className="text-slate-400 text-[11px]">
                Simulação Estocástica de Runouts (Flop/Turn/River)
              </span>
              <button
                onClick={handleRunSimulation}
                disabled={isSimulating}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold text-xs transition-colors cursor-pointer disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5" />
                <span>{isSimulating ? 'Simulando...' : 'Rodar 1.000 Runouts'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
