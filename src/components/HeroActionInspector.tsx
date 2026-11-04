import React, { useState, useEffect, useMemo } from 'react';
import {
  Flame,
  MousePointerClick,
  SlidersHorizontal,
  Clock,
  Coins,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Zap,
  Download,
  Copy,
  Check,
  Play,
  Pause,
  Sliders,
  Crosshair,
  Info,
  Percent,
  Brain,
  TrendingUp,
  Sparkles,
  Layers
} from 'lucide-react';

export interface ActionButtonData {
  id: 'btn_left' | 'btn_center' | 'btn_right';
  type: 'fold' | 'check' | 'call' | 'bet' | 'raise' | 'all_in';
  label: string;
  sublabel?: string;
  amountBb?: number;
  box: [number, number, number, number]; // [ymin, xmin, ymax, xmax]
  bgClass: string;
  hoverClass: string;
  borderClass: string;
  textClass: string;
}

export interface BetSizingShortcut {
  id: string;
  label: string;
  multiplier: number;
  amountBb: number;
}

interface ActionDispatchLog {
  id: string;
  timestamp: string;
  action: string;
  amountBb?: number;
  clickCoord: [number, number];
  reactionMs: number;
  movementMs: number;
  totalDurationMs: number;
  status: 'SUCCESS' | 'ABORTED';
}

export interface PresetScenarioButton {
  id: 'btn_left' | 'btn_center' | 'btn_right';
  type: 'fold' | 'check' | 'call' | 'bet' | 'raise' | 'all_in';
  label: string;
  sublabel: string;
  amountBb: number;
}

export interface GameScenario {
  name: string;
  desc: string;
  isHeroTurn: boolean;
  potBb: number;
  betToCallBb: number;
  timeBankSec: number;
  heroCards?: [string, string];
  boardCards?: string[];
  buttons: PresetScenarioButton[];
}

const PRESET_GAME_SCENARIOS: GameScenario[] = [
  {
    name: 'Opção Livre (Check ou Bet)',
    desc: 'Flop em pote limpado (Pot: 5.0 BB). Nenhuma aposta a pagar.',
    isHeroTurn: true,
    potBb: 5.0,
    betToCallBb: 0,
    timeBankSec: 14.0,
    heroCards: ['K♦', 'Q♦'],
    boardCards: ['A♠', '8♦', '3♦'],
    buttons: [
      { id: 'btn_left', type: 'check', label: 'Check', sublabel: 'Mesa gratuita', amountBb: 0 },
      { id: 'btn_center', type: 'bet', label: 'Bet 2.0 BB', sublabel: '40% do Pote', amountBb: 2.0 },
      { id: 'btn_right', type: 'bet', label: 'Bet 3.8 BB', sublabel: '75% do Pote', amountBb: 3.8 }
    ]
  },
  {
    name: 'Enfrentando Aposta (Fold, Call ou 3-Bet)',
    desc: 'Vilão apostou 6.0 BB no Turn (Pot: 18.0 BB).',
    isHeroTurn: true,
    potBb: 18.0,
    betToCallBb: 6.0,
    timeBankSec: 12.0,
    heroCards: ['A♠', 'K♥'],
    boardCards: ['A♦', '8♣', '4♠', 'T♦'],
    buttons: [
      { id: 'btn_left' as const, type: 'fold' as const, label: 'Fold', sublabel: 'Desistir da mão', amountBb: 0 },
      { id: 'btn_center' as const, type: 'call' as const, label: 'Call 6.0 BB', sublabel: 'Pagar aposta', amountBb: 6.0 },
      { id: 'btn_right' as const, type: 'raise' as const, label: 'Raise 18.0 BB', sublabel: 'Aumentar 3x', amountBb: 18.0 }
    ]
  },
  {
    name: 'All-In Enfrentado no Showdown',
    desc: 'Vilão shovou 52.0 BB no River (Pot: 84.0 BB). Apenas Fold ou Call.',
    isHeroTurn: true,
    potBb: 84.0,
    betToCallBb: 52.0,
    timeBankSec: 8.5,
    heroCards: ['Q♠', 'Q♥'],
    boardCards: ['J♠', '9♦', '6♣', '2♥', '5♠'],
    buttons: [
      { id: 'btn_left' as const, type: 'fold' as const, label: 'Fold', sublabel: 'Desistir fichas', amountBb: 0 },
      { id: 'btn_center' as const, type: 'call' as const, label: 'Call 52.0 BB', sublabel: 'Call All-In!', amountBb: 52.0 },
      { id: 'btn_right' as const, type: 'all_in' as const, label: 'All-In', sublabel: 'Cobrir oponente', amountBb: 65.0 }
    ]
  },
  {
    name: 'Pré-Flop no Botão (BTN)',
    desc: 'Mão em aberto. Você está no Botão (Pot: 1.5 BB).',
    isHeroTurn: true,
    potBb: 1.5,
    betToCallBb: 1.0,
    timeBankSec: 15.0,
    heroCards: ['A♠', 'K♠'],
    boardCards: [],
    buttons: [
      { id: 'btn_left' as const, type: 'fold' as const, label: 'Fold', sublabel: 'Desistir mão', amountBb: 0 },
      { id: 'btn_center' as const, type: 'call' as const, label: 'Call 1.0 BB', sublabel: 'Completar SB/BB', amountBb: 1.0 },
      { id: 'btn_right' as const, type: 'raise' as const, label: 'Raise 2.5 BB', sublabel: 'Open Raise Padrão', amountBb: 2.5 }
    ]
  },
  {
    name: 'Turno do Vilão (Aguardando)',
    desc: 'Oponente no Cutoff pensando. Botões desabilitados.',
    isHeroTurn: false,
    potBb: 12.0,
    betToCallBb: 0,
    timeBankSec: 0,
    heroCards: ['7♥', '8♥'],
    boardCards: ['6♦', '9♠', '2♣'],
    buttons: []
  }
];

export const HeroActionInspector: React.FC<{
  onNotify?: (title: string, message: string, severity: 'INFO' | 'WARN' | 'CRITICAL') => void;
}> = ({ onNotify }) => {
  const [currentScenario, setCurrentScenario] = useState(PRESET_GAME_SCENARIOS[1]);
  const [isHeroTurn, setIsHeroTurn] = useState<boolean>(true);
  const [timeBankRemaining, setTimeBankRemaining] = useState<number>(12.0);
  const [timeBankTotal, setTimeBankTotal] = useState<number>(15.0);
  const [potBb, setPotBb] = useState<number>(18.0);
  const [betToCallBb, setBetToCallBb] = useState<number>(6.0);
  const [customRaiseAmount, setCustomRaiseAmount] = useState<number>(18.0);
  const [isDispatching, setIsDispatching] = useState<boolean>(false);
  const [lastDispatchedAction, setLastDispatchedAction] = useState<string | null>(null);
  const [dispatchLogs, setDispatchLogs] = useState<ActionDispatchLog[]>([
    {
      id: 'log-1',
      timestamp: '11:24:10',
      action: 'Call 6.0 BB',
      amountBb: 6.0,
      clickCoord: [392, 1412],
      reactionMs: 420,
      movementMs: 280,
      totalDurationMs: 700,
      status: 'SUCCESS'
    }
  ]);

  // Button ROIs Calibration (ymin, xmin, ymax, xmax) on 787x1470
  const [buttonRois, setButtonRois] = useState<{ [btnId: string]: [number, number, number, number] }>({
    btn_left:   [1370, 20, 1455, 255],
    btn_center: [1370, 270, 1455, 515],
    btn_right:  [1370, 530, 1455, 770]
  });

  const [copiedPython, setCopiedPython] = useState<boolean>(false);

  // Time Bank Timer Countdown Effect
  useEffect(() => {
    let timer: any = null;
    if (isHeroTurn && timeBankRemaining > 0) {
      timer = setInterval(() => {
        setTimeBankRemaining(prev => {
          if (prev <= 0.2) {
            setIsHeroTurn(false);
            return 0;
          }
          return Number((prev - 0.2).toFixed(1));
        });
      }, 200);
    }
    return () => clearInterval(timer);
  }, [isHeroTurn, timeBankRemaining]);

  // Sizing Shortcuts based on Current Pot
  const sizingShortcuts: BetSizingShortcut[] = [
    { id: 'min', label: 'Min (2.2x)', multiplier: 2.2, amountBb: Math.max(2.0, Number((betToCallBb * 2.2).toFixed(1))) },
    { id: '33',  label: '33% Pot',    multiplier: 0.33, amountBb: Number((potBb * 0.33).toFixed(1)) },
    { id: '50',  label: '50% Pot',    multiplier: 0.50, amountBb: Number((potBb * 0.50).toFixed(1)) },
    { id: '75',  label: '75% Pot',    multiplier: 0.75, amountBb: Number((potBb * 0.75).toFixed(1)) },
    { id: 'pot', label: 'Pot (100%)', multiplier: 1.0,  amountBb: Number((potBb * 1.0).toFixed(1)) },
    { id: 'all', label: 'All-In',     multiplier: 0,    amountBb: 65.0 }
  ];

  // Hole Cards & Community Board Cards for Hand Strength Calculator
  const [heroCards, setHeroCards] = useState<[string, string]>(PRESET_GAME_SCENARIOS[1].heroCards || ['A♠', 'K♥']);
  const [boardCards, setBoardCards] = useState<string[]>(PRESET_GAME_SCENARIOS[1].boardCards || ['A♦', '8♣', '4♠', 'T♦']);

  const handleApplyScenario = (scenario: typeof PRESET_GAME_SCENARIOS[0]) => {
    setCurrentScenario(scenario);
    setIsHeroTurn(scenario.isHeroTurn);
    setPotBb(scenario.potBb);
    setBetToCallBb(scenario.betToCallBb);
    setTimeBankRemaining(scenario.timeBankSec);
    setTimeBankTotal(15.0);
    if (scenario.heroCards) setHeroCards(scenario.heroCards);
    if (scenario.boardCards !== undefined) setBoardCards(scenario.boardCards);
    const rightBtn = scenario.buttons.find(b => b.id === 'btn_right');
    if (rightBtn && rightBtn.amountBb) {
      setCustomRaiseAmount(rightBtn.amountBb);
    } else {
      setCustomRaiseAmount(Number((scenario.potBb * 0.75).toFixed(1)));
    }
  };

  // Hand Strength Calculator Engine
  const handStrengthAnalysis = useMemo(() => {
    const RANK_VALS: Record<string, number> = {
      '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
      'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
    };

    const c1Rank = heroCards[0][0];
    const c1Suit = heroCards[0][1];
    const c2Rank = heroCards[1][0];
    const c2Suit = heroCards[1][1];
    const isPocketPair = c1Rank === c2Rank;
    const isSuited = c1Suit === c2Suit;
    const h1Val = RANK_VALS[c1Rank] || 10;
    const h2Val = RANK_VALS[c2Rank] || 10;
    const highHeroVal = Math.max(h1Val, h2Val);
    const lowHeroVal = Math.min(h1Val, h2Val);

    // Pre-flop (no community cards detected)
    if (boardCards.length === 0) {
      let score = 30;
      let made = 'Mão Pré-Flop Não Pareada';
      if (isPocketPair) {
        made = `Par de Bolso (${c1Rank}${c2Rank})`;
        score = h1Val >= 13 ? 95 : h1Val >= 10 ? 84 : h1Val >= 7 ? 72 : 60;
      } else if (highHeroVal >= 13 && lowHeroVal >= 10) {
        made = `Broadway ${isSuited ? 'Suited' : 'Offsuit'} (${c1Rank}${c2Rank}${isSuited ? 's' : 'o'})`;
        score = isSuited ? 85 : 78;
      } else if (isSuited) {
        made = `Cartas Suited (${c1Rank}${c2Rank}s)`;
        score = 55 + (highHeroVal - 5);
      }

      return {
        madeHand: made,
        strengthScore: Math.min(99, Math.max(10, score)),
        tier: score >= 80 ? 'MONSTER' : score >= 65 ? 'STRONG' : score >= 45 ? 'MEDIUM' : 'WEAK',
        tierLabel: score >= 80 ? 'Força Premium Pré-Flop' : score >= 65 ? 'Mão Forte (Abrir/Raise)' : score >= 45 ? 'Mão Jogável' : 'Mão Marginal',
        tierBadge: score >= 80 ? 'bg-emerald-950 text-emerald-300 border-emerald-700' : score >= 65 ? 'bg-cyan-950 text-cyan-300 border-cyan-700' : 'bg-slate-900 text-slate-300 border-slate-700',
        draws: [] as { name: string; outs: number; odds: string }[],
        potOddsReq: betToCallBb > 0 ? Number(((betToCallBb / (potBb + betToCallBb)) * 100).toFixed(1)) : 0,
        advice: score >= 75 ? 'Mão forte pré-flop. Aumentar (Raise) ou 3-Bet por valor.' : score >= 45 ? 'Completar ou pagar apostas moderadas.' : 'Descartar (Fold) em posições iniciais.'
      };
    }

    // Post-flop: analyze with board cards
    const boardRanks = boardCards.map(c => c[0]);
    const boardSuits = boardCards.map(c => c[1]);
    const boardVals = boardRanks.map(r => RANK_VALS[r] || 2);
    const topBoardVal = Math.max(...boardVals);

    const allRanks = [c1Rank, c2Rank, ...boardRanks];
    const rankCounts: Record<string, number> = {};
    allRanks.forEach(r => { rankCounts[r] = (rankCounts[r] || 0) + 1; });

    const allSuits = [c1Suit, c2Suit, ...boardSuits];
    const suitCounts: Record<string, number> = {};
    allSuits.forEach(s => { suitCounts[s] = (suitCounts[s] || 0) + 1; });

    const flushSuit = Object.keys(suitCounts).find(s => suitCounts[s] >= 5);
    const hasFlush = Boolean(flushSuit);

    const quadRank = Object.keys(rankCounts).find(r => rankCounts[r] === 4);
    const tripsRanks = Object.keys(rankCounts).filter(r => rankCounts[r] === 3);
    const pairRanks = Object.keys(rankCounts).filter(r => rankCounts[r] === 2);

    let made = 'Carta Alta';
    let baseScore = 20;
    let tier: 'MONSTER' | 'STRONG' | 'MEDIUM' | 'DRAW' | 'WEAK' = 'WEAK';

    if (quadRank) {
      made = `Quadra de ${quadRank}`;
      baseScore = 98;
      tier = 'MONSTER';
    } else if (tripsRanks.length >= 1 && (pairRanks.length >= 1 || tripsRanks.length >= 2)) {
      made = 'Full House';
      baseScore = 93;
      tier = 'MONSTER';
    } else if (hasFlush) {
      made = 'Flush Completo';
      baseScore = 88;
      tier = 'MONSTER';
    } else if (tripsRanks.length >= 1) {
      if (isPocketPair && tripsRanks.includes(c1Rank)) {
        made = `Trinca / Set de ${c1Rank}s (Pocket Pair)`;
        baseScore = 82;
        tier = 'MONSTER';
      } else {
        made = `Trinca de ${tripsRanks[0]}s (Trips no Bordo)`;
        baseScore = 75;
        tier = 'STRONG';
      }
    } else if (pairRanks.length >= 2) {
      const heroHits = pairRanks.filter(r => [c1Rank, c2Rank].includes(r));
      if (heroHits.length >= 2) {
        made = `Dois Pares (${heroHits.join(' e ')})`;
        baseScore = 74;
        tier = 'STRONG';
      } else if (heroHits.length === 1) {
        made = `Dois Pares com o Bordo (${heroHits[0]}s)`;
        baseScore = 65;
        tier = 'STRONG';
      } else {
        made = `Dois Pares no Bordo`;
        baseScore = 48;
        tier = 'MEDIUM';
      }
    } else if (pairRanks.length === 1) {
      const pRank = pairRanks[0];
      const pVal = RANK_VALS[pRank] || 2;
      if (isPocketPair) {
        if (pVal > topBoardVal) {
          made = `Overpair (${pRank}${pRank})`;
          baseScore = 78;
          tier = 'STRONG';
        } else {
          made = `Pocket Pair Médio (${pRank}${pRank})`;
          baseScore = 52;
          tier = 'MEDIUM';
        }
      } else if ([c1Rank, c2Rank].includes(pRank)) {
        if (pVal === topBoardVal) {
          const kicker = c1Rank === pRank ? c2Rank : c1Rank;
          const kickerVal = RANK_VALS[kicker] || 2;
          const isTk = kickerVal >= 13;
          made = `Top Pair (${pRank}) com ${isTk ? 'Top Kicker (TK)' : 'Bom Kicker'}`;
          baseScore = isTk ? 72 : 62;
          tier = 'STRONG';
        } else {
          made = `Par Médio / Segundo Par (${pRank})`;
          baseScore = 46;
          tier = 'MEDIUM';
        }
      } else {
        made = `Par no Bordo (${pRank})`;
        baseScore = 32;
        tier = 'WEAK';
      }
    }

    // Draws Detection
    const draws: { name: string; outs: number; odds: string }[] = [];
    const fourSuit = Object.keys(suitCounts).find(s => suitCounts[s] === 4);
    if (fourSuit && !hasFlush) {
      draws.push({
        name: `Flush Draw (${fourSuit === 's' ? '♠' : fourSuit === 'h' ? '♥' : fourSuit === 'd' ? '♦' : '♣'})`,
        outs: 9,
        odds: boardCards.length === 3 ? '~35% (Turn+River)' : '~18% (River)'
      });
      baseScore += 15;
      if (tier === 'WEAK') tier = 'DRAW';
    }

    if (highHeroVal > topBoardVal && lowHeroVal > topBoardVal && baseScore < 50) {
      draws.push({ name: 'Duas Overcards (Hero maior que o bordo)', outs: 6, odds: '~24%' });
      baseScore += 8;
      if (tier === 'WEAK') tier = 'DRAW';
    }

    const finalScore = Math.min(99, Math.max(10, baseScore));
    const potOddsReq = betToCallBb > 0 ? Number(((betToCallBb / (potBb + betToCallBb)) * 100).toFixed(1)) : 0;

    let advice = '';
    if (finalScore >= 80) {
      advice = `Mão Monstro (${finalScore}% de força). Aumentar (Raise) ou Bet forte para extrair valor máximo no pote de ${potBb} BB.`;
    } else if (finalScore >= 60) {
      if (betToCallBb > 0) {
        advice = `Top Pair / Valor Sólido. Pot odds necessária: ${potOddsReq}%. CALL ou RAISE amplamente lucrativo (+EV).`;
      } else {
        advice = `Mão forte. Apostar (Bet 33%-75% do pote) para proteção e extração de valor.`;
      }
    } else if (draws.length > 0) {
      const totalOuts = draws.reduce((acc, d) => acc + d.outs, 0);
      advice = `Projeto Competitivo (${totalOuts} Outs). Com pot odds de ${potOddsReq}%, pagar (Call) é matematicamente vantajoso.`;
    } else if (betToCallBb > 0) {
      advice = `Mão fraca / Showdown value marginal perante aposta de ${betToCallBb} BB. Fold recomendado se enfrentar agressão.`;
    } else {
      advice = `Opção livre. Pedir mesa (Check) para realizar equidade gratuitamente.`;
    }

    const tierBadge =
      tier === 'MONSTER' ? 'bg-emerald-950 text-emerald-300 border-emerald-700 shadow-emerald-950/40' :
      tier === 'STRONG' ? 'bg-cyan-950 text-cyan-300 border-cyan-700 shadow-cyan-950/40' :
      tier === 'DRAW' ? 'bg-amber-950 text-amber-300 border-amber-700 shadow-amber-950/40' :
      tier === 'MEDIUM' ? 'bg-blue-950 text-blue-300 border-blue-700' :
      'bg-slate-900 text-slate-300 border-slate-700';

    const tierLabel =
      tier === 'MONSTER' ? 'Monstro / Força Extrema' :
      tier === 'STRONG' ? 'Valor Sólido (Top Pair / Overpair)' :
      tier === 'DRAW' ? 'Projeto Forte (Outs Ativos)' :
      tier === 'MEDIUM' ? 'Showdown Médio / Marginal' :
      'Mão Fraca / Air';

    return {
      madeHand: made,
      strengthScore: finalScore,
      tier,
      tierLabel,
      tierBadge,
      draws,
      potOddsReq,
      advice
    };
  }, [heroCards, boardCards, betToCallBb, potBb]);

  const simulateActionClick = (buttonId: 'btn_left' | 'btn_center' | 'btn_right', actionLabel: string, amountBb?: number) => {
    if (!isHeroTurn) return;
    setIsDispatching(true);

    const box = buttonRois[buttonId];
    // Calculate Gaussian Jitter coordinates (+/- 4px)
    const cx = Math.round((box[1] + box[3]) / 2);
    const cy = Math.round((box[0] + box[2]) / 2);
    const jx = cx + Math.round((Math.random() - 0.5) * 8);
    const jy = cy + Math.round((Math.random() - 0.5) * 8);

    const reactionTime = 380 + Math.round(Math.random() * 150);
    const movementTime = 220 + Math.round(Math.random() * 100);
    const totalTime = reactionTime + movementTime;

    setTimeout(() => {
      setIsDispatching(false);
      setLastDispatchedAction(actionLabel);
      setIsHeroTurn(false); // Turn finished

      const newLog: ActionDispatchLog = {
        id: `log-${Date.now().toString().slice(-4)}`,
        timestamp: new Date().toLocaleTimeString(),
        action: actionLabel,
        amountBb,
        clickCoord: [jx, jy],
        reactionMs: reactionTime,
        movementMs: movementTime,
        totalDurationMs: totalTime,
        status: 'SUCCESS'
      };

      setDispatchLogs(prev => [newLog, ...prev]);

      onNotify?.(
        `AÇÃO DESPACHADA: [${actionLabel}]`,
        `Clique injetado em (${jx}, ${jy}) px via PyAutoGUI suave com latência total de ${totalTime}ms (Reação: ${reactionTime}ms, Movimento: ${movementTime}ms).`,
        'INFO'
      );
    }, 450);
  };

  const adjustRoi = (buttonId: string, coordIdx: number, delta: number) => {
    setButtonRois(prev => {
      const cur = [...prev[buttonId]] as [number, number, number, number];
      cur[coordIdx] += delta;
      return { ...prev, [buttonId]: cur };
    });
  };

  const copyPythonRois = () => {
    const code = `
# ROIs dos Botões de Ação do Hero (787x1470 px)
ACTION_BUTTON_ROIS = {
    "btn_left":   (${buttonRois.btn_left.join(', ')}),   # Fold / Check
    "btn_center": (${buttonRois.btn_center.join(', ')}), # Check / Call
    "btn_right":  (${buttonRois.btn_right.join(', ')}),  # Bet / Raise / All-in
}
`.trim();
    navigator.clipboard.writeText(code);
    setCopiedPython(true);
    setTimeout(() => setCopiedPython(false), 2000);
  };

  const timePercent = Math.max(0, Math.min(100, (timeBankRemaining / Math.max(0.1, timeBankTotal)) * 100));

  const renderCardBadge = (cardStr: string, isHole: boolean = false) => {
    const rank = cardStr.slice(0, -1);
    const suitChar = cardStr.slice(-1);
    const suitStyle =
      suitChar === '♠'
        ? 'text-slate-100 bg-slate-900 border-slate-700 shadow-sm'
        : suitChar === '♥'
        ? 'text-rose-400 bg-rose-950/60 border-rose-800 shadow-sm'
        : suitChar === '♦'
        ? 'text-blue-400 bg-blue-950/60 border-blue-800 shadow-sm'
        : 'text-emerald-400 bg-emerald-950/60 border-emerald-800 shadow-sm';

    return (
      <div
        className={`inline-flex items-center justify-center font-mono font-black border rounded-lg select-none transition-transform hover:scale-105 ${
          isHole
            ? 'px-2.5 py-1 text-sm gap-1 min-w-[38px] ring-1 ring-amber-500/20'
            : 'px-2 py-0.5 text-xs gap-0.5 min-w-[30px]'
        } ${suitStyle}`}
      >
        <span>{rank}</span>
        <span className="text-sm leading-none">{suitChar}</span>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-80 h-full bg-gradient-to-l from-emerald-500/10 via-amber-500/5 to-transparent pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <MousePointerClick className="w-5 h-5" />
              </span>
              <h2 className="text-xl font-bold text-slate-100 tracking-tight">
                Detecção e Automação dos Botões de Ação do Hero
              </h2>
            </div>
            <p className="text-xs text-slate-400 max-w-2xl">
              Identificação de turno ativo (Hero Turn), leitura dos 3 botões primários (Fold, Check, Call, Bet/Raise), controle de Time Bank e injeção de cliques camuflados com dispersão gaussiana de píxel.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => {
                setTimeBankRemaining(15.0);
                setIsHeroTurn(true);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition-colors shadow-sm"
              title="Reiniciar contagem regressiva de ação"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-950" />
              <span>Reiniciar Turno</span>
            </button>

            <button
              onClick={copyPythonRois}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 transition-colors shadow-sm"
            >
              {copiedPython ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
              <span>{copiedPython ? 'Copiado!' : 'Copiar ROIs Python'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Grid: Left (Table Action Bar Simulator) + Right (Controls, Sizing & Audit Logs) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Simulated Table Action Bar & Time Bank (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Flame className={`w-5 h-5 ${isHeroTurn ? 'text-amber-400 animate-pulse' : 'text-slate-500'}`} />
                <div>
                  <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                    <span>Barra de Ação Inferior (PPPoker Table)</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider ${
                      isHeroTurn
                        ? 'bg-amber-950 text-amber-300 border border-amber-800 animate-pulse'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                    }`}>
                      {isHeroTurn ? 'Sua Vez de Agir' : 'Aguardando Vilão'}
                    </span>
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">
                    Y: 1350..1470 px • Resolução Base: 787 × 1470 px
                  </span>
                </div>
              </div>

              {/* Pot & Call Amounts */}
              <div className="text-right font-mono">
                <span className="text-[10px] text-slate-500 block">Pote Total</span>
                <span className="text-sm font-bold text-emerald-400">{potBb} BB</span>
              </div>
            </div>

            {/* Time Bank Progress Strip */}
            <div className="space-y-1.5 p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 flex items-center gap-1.5 text-[11px]">
                  <Clock className="w-3.5 h-3.5 text-amber-400" />
                  <span>Time Bank Restante:</span>
                </span>
                <span className={`font-bold ${
                  timeBankRemaining > 6
                    ? 'text-emerald-400'
                    : timeBankRemaining > 3
                    ? 'text-amber-400'
                    : 'text-rose-400 animate-pulse'
                }`}>
                  {timeBankRemaining.toFixed(1)}s ({timePercent.toFixed(0)}%)
                </span>
              </div>

              <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden border border-slate-800 p-0.5">
                <div
                  className={`h-full rounded-full transition-all duration-200 ${
                    timeBankRemaining > 6
                      ? 'bg-emerald-500'
                      : timeBankRemaining > 3
                      ? 'bg-amber-500'
                      : 'bg-rose-500 animate-pulse'
                  }`}
                  style={{ width: `${timePercent}%` }}
                />
              </div>
            </div>

            {/* Hand Strength Calculator Module (Dynamic OCR Estimation) */}
            <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-3.5 shadow-inner">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30">
                    <Brain className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-xs text-slate-100 uppercase tracking-wider">
                        Calculadora de Força da Mão (Hand Strength)
                      </h4>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${handStrengthAnalysis.tierBadge}`}>
                        {handStrengthAnalysis.tierLabel}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Estimativa dinâmica de equidade e força relativa baseada nas cartas detectadas pelo OCR
                    </p>
                  </div>
                </div>

                <div className="text-right font-mono">
                  <span className="text-[10px] text-slate-500 block">Força Relativa</span>
                  <div className="flex items-center justify-end gap-1">
                    <span className="text-base font-black text-emerald-400">{handStrengthAnalysis.strengthScore}%</span>
                  </div>
                </div>
              </div>

              {/* Detected Hole & Board Cards */}
              <div className="flex items-center justify-between flex-wrap gap-3 p-2.5 rounded-xl bg-slate-900/90 border border-slate-800">
                {/* Hero Hole Cards */}
                <div className="space-y-1">
                  <span className="text-[10px] font-mono uppercase font-bold text-slate-400 flex items-center gap-1">
                    <span>Cartas do Hero:</span>
                    <span className="text-emerald-400 text-[9px]">(Detectadas)</span>
                  </span>
                  <div className="flex items-center gap-1.5">
                    {heroCards.map((c, i) => (
                      <div key={i}>{renderCardBadge(c, true)}</div>
                    ))}
                  </div>
                </div>

                {/* Board Cards */}
                <div className="space-y-1">
                  <span className="text-[10px] font-mono uppercase font-bold text-slate-400 flex items-center gap-1">
                    <span>Bordo Comunitário:</span>
                    <span className="text-slate-400 text-[9px]">
                      ({boardCards.length === 0 ? 'Pré-Flop' : boardCards.length === 3 ? 'Flop' : boardCards.length === 4 ? 'Turn' : 'River'})
                    </span>
                  </span>
                  <div className="flex items-center gap-1">
                    {boardCards.length === 0 ? (
                      <span className="text-xs font-mono text-slate-500 italic bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
                        Nenhum bordo (Street Pré-Flop)
                      </span>
                    ) : (
                      boardCards.map((c, i) => (
                        <div key={i}>{renderCardBadge(c, false)}</div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Strength Meter Bar */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-slate-200 font-bold flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                    <span>Mão Formada: <strong className="text-emerald-300 font-bold">{handStrengthAnalysis.madeHand}</strong></span>
                  </span>
                  <span className="text-slate-400">
                    Pot Odds Req: <span className="text-amber-300 font-bold">{handStrengthAnalysis.potOddsReq}%</span>
                  </span>
                </div>

                <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden border border-slate-800 p-0.5">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      handStrengthAnalysis.strengthScore >= 80 ? 'bg-gradient-to-r from-cyan-400 to-emerald-400' :
                      handStrengthAnalysis.strengthScore >= 60 ? 'bg-gradient-to-r from-amber-400 to-cyan-400' :
                      handStrengthAnalysis.strengthScore >= 40 ? 'bg-gradient-to-r from-rose-400 to-amber-400' :
                      'bg-rose-500'
                    }`}
                    style={{ width: `${handStrengthAnalysis.strengthScore}%` }}
                  />
                </div>
              </div>

              {/* Draws & Outs Section */}
              {handStrengthAnalysis.draws.length > 0 && (
                <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-[11px] font-mono flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-1.5 text-amber-300 font-semibold">
                    <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
                    <span>Projetos: {handStrengthAnalysis.draws.map(d => `${d.name} (${d.outs} Outs)`).join(' + ')}</span>
                  </div>
                  <div className="text-slate-400">
                    Probabilidade: <strong className="text-emerald-400">{handStrengthAnalysis.draws[0].odds}</strong>
                  </div>
                </div>
              )}

              {/* GTO & Pot Odds Decision Link */}
              <div className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 text-xs font-mono text-slate-300 flex items-start gap-2">
                <Info className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <div className="space-y-0.5 leading-relaxed">
                  <span className="text-emerald-400 font-bold block">Conselho Estratégico para os Botões Abaixo:</span>
                  <span>{handStrengthAnalysis.advice}</span>
                </div>
              </div>
            </div>

            {/* Simulated PPPoker Action Strip (The 3 Main Buttons) */}
            <div className="p-4 rounded-2xl bg-gradient-to-b from-slate-950 to-[#07130e] border-2 border-slate-800 space-y-3 relative shadow-inner">
              {/* Sizing Shortcut Chips Row (Above Raise Button) */}
              {isHeroTurn && (
                <div className="space-y-1.5">
                  <span className="text-[10px] text-slate-400 uppercase font-mono tracking-wider block">
                    Atalhos de Dimensionamento de Aposta (Pre-Raise):
                  </span>
                  <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                    {sizingShortcuts.map(chip => (
                      <button
                        key={chip.id}
                        onClick={() => setCustomRaiseAmount(chip.amountBb)}
                        className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono font-bold transition-all shrink-0 cursor-pointer ${
                          customRaiseAmount === chip.amountBb
                            ? 'bg-amber-500 text-slate-950 border-amber-400 shadow-md font-black scale-102'
                            : 'bg-slate-900/90 border-slate-800 text-slate-300 hover:border-slate-700 hover:text-white'
                        }`}
                      >
                        {chip.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* The 3 Core Action Buttons */}
              <div className="grid grid-cols-3 gap-2.5 pt-1">
                {/* 1. Left Button: Fold / Check */}
                {(() => {
                  const leftBtn = currentScenario.buttons.find(b => b.id === 'btn_left');
                  const isCheck = leftBtn?.type === 'check';
                  return (
                    <button
                      onClick={() => simulateActionClick('btn_left', leftBtn?.label || 'Fold', 0)}
                      disabled={!isHeroTurn || isDispatching}
                      className={`relative flex flex-col items-center justify-center p-3 rounded-xl border-2 transition-all cursor-pointer shadow-lg disabled:opacity-30 disabled:cursor-not-allowed ${
                        isCheck
                          ? 'bg-gradient-to-b from-emerald-950 to-slate-950 border-emerald-600 text-emerald-300 hover:border-emerald-400 hover:scale-102'
                          : 'bg-gradient-to-b from-rose-950 to-slate-950 border-rose-600 text-rose-300 hover:border-rose-400 hover:scale-102'
                      }`}
                    >
                      <span className="text-sm font-black tracking-tight leading-tight">
                        {leftBtn?.label || 'Fold'}
                      </span>
                      <span className="text-[10px] opacity-75 font-mono">
                        {leftBtn?.sublabel || 'Desistir'}
                      </span>
                    </button>
                  );
                })()}

                {/* 2. Center Button: Check / Call */}
                {(() => {
                  const centerBtn = currentScenario.buttons.find(b => b.id === 'btn_center');
                  const isFreeCheck = centerBtn?.type === 'check';
                  return (
                    <button
                      onClick={() => simulateActionClick('btn_center', centerBtn?.label || 'Check', centerBtn?.amountBb || 0)}
                      disabled={!isHeroTurn || isDispatching}
                      className={`relative flex flex-col items-center justify-center p-3 rounded-xl border-2 transition-all cursor-pointer shadow-lg disabled:opacity-30 disabled:cursor-not-allowed ${
                        isFreeCheck
                          ? 'bg-gradient-to-b from-emerald-900 to-slate-950 border-emerald-500 text-emerald-200 hover:border-emerald-300 hover:scale-102'
                          : 'bg-gradient-to-b from-cyan-950 to-slate-950 border-cyan-500 text-cyan-200 hover:border-cyan-300 hover:scale-102'
                      }`}
                    >
                      <span className="text-sm font-black tracking-tight leading-tight">
                        {centerBtn?.label || 'Check'}
                      </span>
                      <span className="text-[10px] opacity-75 font-mono">
                        {centerBtn?.sublabel || 'Confirmar'}
                      </span>
                    </button>
                  );
                })()}

                {/* 3. Right Button: Bet / Raise / All-in */}
                {(() => {
                  const rightBtn = currentScenario.buttons.find(b => b.id === 'btn_right');
                  const isAllIn = rightBtn?.type === 'all_in';
                  const displayRaise = customRaiseAmount > 0 ? customRaiseAmount : (rightBtn?.amountBb || 18.0);
                  const label = isAllIn ? 'All-In 65 BB' : `Raise ${displayRaise} BB`;

                  return (
                    <button
                      onClick={() => simulateActionClick('btn_right', label, displayRaise)}
                      disabled={!isHeroTurn || isDispatching}
                      className={`relative flex flex-col items-center justify-center p-3 rounded-xl border-2 transition-all cursor-pointer shadow-lg disabled:opacity-30 disabled:cursor-not-allowed ${
                        isAllIn
                          ? 'bg-gradient-to-b from-rose-900 to-slate-950 border-rose-500 text-rose-100 hover:border-rose-400 hover:scale-102 animate-pulse'
                          : 'bg-gradient-to-b from-amber-950 to-slate-950 border-amber-500 text-amber-200 hover:border-amber-400 hover:scale-102'
                      }`}
                    >
                      <span className="text-sm font-black tracking-tight leading-tight">
                        {label}
                      </span>
                      <span className="text-[10px] opacity-75 font-mono">
                        {isAllIn ? 'Tudo ou Nada' : `${((displayRaise / Math.max(1, potBb)) * 100).toFixed(0)}% do Pote`}
                      </span>
                    </button>
                  );
                })()}
              </div>

              {/* Slider for Precise Raise Sizing */}
              {isHeroTurn && (
                <div className="pt-2 border-t border-slate-900 flex items-center gap-3">
                  <span className="text-[10px] text-slate-400 font-mono shrink-0">
                    Ajuste Fino de Raise:
                  </span>
                  <input
                    type="range"
                    min={betToCallBb > 0 ? betToCallBb * 2 : 2}
                    max={65}
                    step={0.5}
                    value={customRaiseAmount}
                    onChange={(e) => setCustomRaiseAmount(Number(e.target.value))}
                    className="w-full accent-amber-500 bg-slate-900 h-1.5 rounded-lg cursor-pointer"
                  />
                  <span className="text-xs font-mono font-bold text-amber-400 shrink-0">
                    {customRaiseAmount.toFixed(1)} BB
                  </span>
                </div>
              )}
            </div>

            {/* Quick Game Scenario Presets */}
            <div className="space-y-2 pt-2 border-t border-slate-800">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                Alternar Cenário da Mesa:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {PRESET_GAME_SCENARIOS.map(scen => (
                  <button
                    key={scen.name}
                    onClick={() => handleApplyScenario(scen)}
                    className={`text-left p-2.5 rounded-xl border transition-all cursor-pointer ${
                      currentScenario.name === scen.name
                        ? 'bg-emerald-950/80 border-emerald-600 text-emerald-200 shadow'
                        : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
                    }`}
                  >
                    <div className="text-xs font-bold truncate">{scen.name}</div>
                    <div className="text-[10px] text-slate-400 truncate">{scen.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: ROI Calibration Controls & Action Audit Logs (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          {/* ROI Fine-Tuning Module */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-emerald-400" />
                <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider">
                  Calibração de ROIs dos Botões de Ação
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-400">
                Padrão 787 × 1470 px
              </span>
            </div>

            <div className="space-y-3">
              {/* Button Left */}
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 font-mono text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200">
                    Botão 1 (Esquerda: Fold/Check)
                  </span>
                  <span className="text-slate-400 text-[11px]">
                    [{buttonRois.btn_left.join(', ')}]
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-1.5 text-[11px]">
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">Y1: {buttonRois.btn_left[0]}</span>
                    <button onClick={() => adjustRoi('btn_left', 0, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">X1: {buttonRois.btn_left[1]}</span>
                    <button onClick={() => adjustRoi('btn_left', 1, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">Y2: {buttonRois.btn_left[2]}</span>
                    <button onClick={() => adjustRoi('btn_left', 2, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">X2: {buttonRois.btn_left[3]}</span>
                    <button onClick={() => adjustRoi('btn_left', 3, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                </div>
              </div>

              {/* Button Center */}
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 font-mono text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200">
                    Botão 2 (Centro: Check/Call)
                  </span>
                  <span className="text-slate-400 text-[11px]">
                    [{buttonRois.btn_center.join(', ')}]
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-1.5 text-[11px]">
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">Y1: {buttonRois.btn_center[0]}</span>
                    <button onClick={() => adjustRoi('btn_center', 0, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">X1: {buttonRois.btn_center[1]}</span>
                    <button onClick={() => adjustRoi('btn_center', 1, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">Y2: {buttonRois.btn_center[2]}</span>
                    <button onClick={() => adjustRoi('btn_center', 2, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">X2: {buttonRois.btn_center[3]}</span>
                    <button onClick={() => adjustRoi('btn_center', 3, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                </div>
              </div>

              {/* Button Right */}
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 font-mono text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200">
                    Botão 3 (Direita: Bet/Raise/All-In)
                  </span>
                  <span className="text-slate-400 text-[11px]">
                    [{buttonRois.btn_right.join(', ')}]
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-1.5 text-[11px]">
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">Y1: {buttonRois.btn_right[0]}</span>
                    <button onClick={() => adjustRoi('btn_right', 0, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">X1: {buttonRois.btn_right[1]}</span>
                    <button onClick={() => adjustRoi('btn_right', 1, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">Y2: {buttonRois.btn_right[2]}</span>
                    <button onClick={() => adjustRoi('btn_right', 2, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                    <span className="text-slate-500">X2: {buttonRois.btn_right[3]}</span>
                    <button onClick={() => adjustRoi('btn_right', 3, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Action Dispatch Logs (Audit History) */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider">
                  Histórico de Despacho de Ações (PyAutoGUI)
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-500">
                {dispatchLogs.length} eventos
              </span>
            </div>

            <div className="space-y-2 max-h-[220px] overflow-y-auto">
              {dispatchLogs.map(log => (
                <div
                  key={log.id}
                  className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between gap-3 text-xs font-mono"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-emerald-300">{log.action}</span>
                      <span className="text-[10px] text-slate-400">({log.clickCoord[0]}, {log.clickCoord[1]} px)</span>
                    </div>
                    <div className="text-[10px] text-slate-500">
                      Reação: {log.reactionMs}ms • Movimento Bézier: {log.movementMs}ms
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="font-bold text-slate-200">{log.totalDurationMs}ms</span>
                    <span className="text-[10px] text-slate-500 block">{log.timestamp}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
