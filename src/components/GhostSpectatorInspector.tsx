import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Eye,
  Sliders,
  Volume2,
  VolumeX,
  Play,
  RotateCcw,
  Download,
  Copy,
  Check,
  Zap,
  Terminal,
  Activity,
  AlertCircle,
  HelpCircle,
  Clock,
  Layers,
  Sparkles,
  ArrowRight,
  TrendingUp,
  MousePointerClick,
  AlertTriangle,
  Lock,
  Unlock,
  Radio,
  Flame,
  Power
} from 'lucide-react';

interface GhostHandRecord {
  handId: string;
  timestamp: string;
  street: 'PREFLOP' | 'FLOP' | 'TURN' | 'RIVER';
  position: 'BTN' | 'CO' | 'MP' | 'UTG' | 'SB' | 'BB';
  heroCards: [string, string];
  boardCards: string[];
  potBb: number;
  betToCallBb: number;
  stackBb: number;
  action: 'FOLD' | 'CHECK' | 'CALL' | 'RAISE' | 'BET_33' | 'BET_50' | 'BET_75' | 'ALL_IN';
  sizingBb?: number;
  equityPct: number;
  evBb: number;
  targetButton: 'btn_left' | 'btn_center' | 'btn_right' | 'size_33' | 'size_50';
  targetButtonLabel: string;
  clickPoint: [number, number];
  status: 'SUPPRESSED_VERIFIED' | 'CLICK_EXECUTED_LIVE';
  biometrics?: {
    reactionMs: number;
    moveDurationMs: number;
    pressDurationMs: number;
    totalMs: number;
    curveProfile: string;
    jitterOffset: [number, number];
  };
}

const PRESET_SCENARIOS: Array<{
  id: string;
  title: string;
  description: string;
  street: 'PREFLOP' | 'FLOP' | 'TURN' | 'RIVER';
  position: 'BTN' | 'CO' | 'MP' | 'UTG' | 'SB' | 'BB';
  heroCards: [string, string];
  boardCards: string[];
  potBb: number;
  betToCallBb: number;
  action: 'FOLD' | 'CHECK' | 'CALL' | 'RAISE' | 'BET_33' | 'BET_50' | 'BET_75' | 'ALL_IN';
  sizingBb?: number;
  equityPct: number;
  evBb: number;
  targetButton: 'btn_left' | 'btn_center' | 'btn_right' | 'size_33' | 'size_50';
  targetButtonLabel: string;
  clickPoint: [number, number];
}> = [
  {
    id: 'scen_01',
    title: '1. A♠ K♥ no BTN (Open-Raise 2.5 BB)',
    description: 'Hero no Botão em mesa 6-max com mão premium. Linha GTO pura de Raise First In (RFI).',
    street: 'PREFLOP',
    position: 'BTN',
    heroCards: ['A♠', 'K♥'],
    boardCards: [],
    potBb: 1.5,
    betToCallBb: 1.0,
    action: 'RAISE',
    sizingBb: 2.5,
    equityPct: 62.4,
    evBb: +2.85,
    targetButton: 'btn_right',
    targetButtonLabel: 'Raise 2.5 BB',
    clickPoint: [652, 1412]
  },
  {
    id: 'scen_02',
    title: '2. Q♠ Q♦ no SB vs 3-Bet do BB (4-Bet Value)',
    description: 'Pote 3-Bet dinâmico. Vilão no BB realizou 3-bet agressiva para 9 BB; Hero responde com 4-Bet polarizada.',
    street: 'PREFLOP',
    position: 'SB',
    heroCards: ['Q♠', 'Q♦'],
    boardCards: [],
    potBb: 12.0,
    betToCallBb: 6.5,
    action: 'RAISE',
    sizingBb: 21.0,
    equityPct: 68.2,
    evBb: +4.40,
    targetButton: 'btn_right',
    targetButtonLabel: 'Raise 21.0 BB',
    clickPoint: [648, 1409]
  },
  {
    id: 'scen_03',
    title: '3. A♦ T♦ em Flop Seco A♠ 7♣ 2♥ (C-Bet 33%)',
    description: 'Hero acertou Top Pair com kicker T em bordo desconectado (Dry Rainbow). Sizing GTO de 1/3 do pote.',
    street: 'FLOP',
    position: 'CO',
    heroCards: ['A♦', 'T♦'],
    boardCards: ['A♠', '7♣', '2♥'],
    potBb: 7.5,
    betToCallBb: 0.0,
    action: 'BET_33',
    sizingBb: 2.5,
    equityPct: 76.8,
    evBb: +3.10,
    targetButton: 'size_33',
    targetButtonLabel: '33% (2.5 BB)',
    clickPoint: [440, 1338]
  },
  {
    id: 'scen_04',
    title: '4. J♥ T♥ em Turn Molhado K♥ 9♥ 4♣ 2♠ (Semi-Blefe / Call)',
    description: 'Hero possui Flush Draw + Gutshot (12 outs). Vilão aposta 6 BB em pote de 15 BB. Pot odds favoráveis (28%).',
    street: 'TURN',
    position: 'BTN',
    heroCards: ['J♥', 'T♥'],
    boardCards: ['K♥', '9♥', '4♣', '2♠'],
    potBb: 21.0,
    betToCallBb: 6.0,
    action: 'CALL',
    sizingBb: 6.0,
    equityPct: 54.0,
    evBb: +1.25,
    targetButton: 'btn_center',
    targetButtonLabel: 'Call 6.0 BB',
    clickPoint: [390, 1411]
  },
  {
    id: 'scen_05',
    title: '5. 8♣ 7♣ no BB em River Neutro 8♠ 4♦ 2♥ K♠ A♣ (Fold Disciplinado)',
    description: 'Vilão disparou triplo barril forte de 24 BB no river. Catcher marginal (4º par) com realização de equidade nula.',
    street: 'RIVER',
    position: 'BB',
    heroCards: ['8♣', '7♣'],
    boardCards: ['8♠', '4♦', '2♥', 'K♠', 'A♣'],
    potBb: 48.0,
    betToCallBb: 24.0,
    action: 'FOLD',
    sizingBb: 0.0,
    equityPct: 14.2,
    evBb: 0.0,
    targetButton: 'btn_left',
    targetButtonLabel: 'Fold',
    clickPoint: [136, 1414]
  }
];

export const GhostSpectatorInspector: React.FC = () => {
  const [operatingMode, setOperatingMode] = useState<'SPECTATOR' | 'LIVE'>('SPECTATOR');
  const [isLiveArmed, setIsLiveArmed] = useState<boolean>(false);
  const [liveClicksCount, setLiveClicksCount] = useState<number>(0);
  const [isExecutingLiveClick, setIsExecutingLiveClick] = useState<boolean>(false);
  const [selectedScenario, setSelectedScenario] = useState(PRESET_SCENARIOS[0]);
  const [timeBankRemaining, setTimeBankRemaining] = useState<number>(14.2);
  const [soundAlertEnabled, setSoundAlertEnabled] = useState<boolean>(true);
  const [isSimulatingLiveTurn, setIsSimulatingLiveTurn] = useState<boolean>(false);
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

  // Telemetria do último clique executado
  const [lastBiometrics, setLastBiometrics] = useState<{
    reactionMs: number;
    moveMs: number;
    pressMs: number;
    totalMs: number;
    jitterOffset: [number, number];
    button: string;
    action: string;
  } | null>({
    reactionMs: 410,
    moveMs: 295,
    pressMs: 82,
    totalMs: 787,
    jitterOffset: [+2.4, -1.8],
    button: 'btn_right',
    action: 'RAISE 2.5 BB'
  });

  const [handHistory, setHandHistory] = useState<GhostHandRecord[]>([
    {
      handId: 'H-0104',
      timestamp: '23:14:02',
      street: 'PREFLOP',
      position: 'BTN',
      heroCards: ['A♠', 'K♥'],
      boardCards: [],
      potBb: 1.5,
      betToCallBb: 1.0,
      stackBb: 100.0,
      action: 'RAISE',
      sizingBb: 2.5,
      equityPct: 62.4,
      evBb: +2.85,
      targetButton: 'btn_right',
      targetButtonLabel: 'Raise 2.5 BB',
      clickPoint: [652, 1412],
      status: 'SUPPRESSED_VERIFIED'
    },
    {
      handId: 'H-0103',
      timestamp: '23:12:45',
      street: 'FLOP',
      position: 'CO',
      heroCards: ['A♦', 'T♦'],
      boardCards: ['A♠', '7♣', '2♥'],
      potBb: 7.5,
      betToCallBb: 0.0,
      stackBb: 94.0,
      action: 'BET_33',
      sizingBb: 2.5,
      equityPct: 76.8,
      evBb: +3.10,
      targetButton: 'size_33',
      targetButtonLabel: '33% (2.5 BB)',
      clickPoint: [440, 1338],
      status: 'SUPPRESSED_VERIFIED'
    },
    {
      handId: 'H-0102',
      timestamp: '23:11:18',
      street: 'RIVER',
      position: 'BB',
      heroCards: ['8♣', '7♣'],
      boardCards: ['8♠', '4♦', '2♥', 'K♠', 'A♣'],
      potBb: 48.0,
      betToCallBb: 24.0,
      stackBb: 45.0,
      action: 'FOLD',
      sizingBb: 0.0,
      equityPct: 14.2,
      evBb: 0.0,
      targetButton: 'btn_left',
      targetButtonLabel: 'Fold',
      clickPoint: [136, 1414],
      status: 'SUPPRESSED_VERIFIED'
    }
  ]);

  // Audio Beep para Turno do Hero
  const playHeroTurnSound = () => {
    if (!soundAlertEnabled) return;
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, now); // D5
      osc.frequency.setValueAtTime(880.0, now + 0.08); // A5
      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.25);
    } catch {
      // Silenciar bloqueio do navegador
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCmd(id);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  // Disparar simulação de cenário (Spectator ou Live)
  const triggerScenario = (scenario: typeof PRESET_SCENARIOS[0]) => {
    setSelectedScenario(scenario);
    setTimeBankRemaining(15.0);
    playHeroTurnSound();
    setIsSimulatingLiveTurn(true);

    const isLive = operatingMode === 'LIVE' && isLiveArmed;
    const reactionMs = Math.round(350 + Math.random() * 220);
    const moveMs = Math.round(250 + Math.random() * 110);
    const pressMs = Math.round(65 + Math.random() * 40);
    const totalMs = reactionMs + moveMs + pressMs;
    const jx = Number(((Math.random() - 0.5) * 6.0).toFixed(1));
    const jy = Number(((Math.random() - 0.5) * 4.0).toFixed(1));

    if (isLive) {
      setLiveClicksCount(prev => prev + 1);
      setLastBiometrics({
        reactionMs,
        moveMs,
        pressMs,
        totalMs,
        jitterOffset: [jx, jy],
        button: scenario.targetButtonLabel,
        action: scenario.action
      });
    }

    const newRecord: GhostHandRecord = {
      handId: `H-0${handHistory.length + 105}`,
      timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      street: scenario.street,
      position: scenario.position,
      heroCards: scenario.heroCards,
      boardCards: scenario.boardCards,
      potBb: scenario.potBb,
      betToCallBb: scenario.betToCallBb,
      stackBb: 100.0,
      action: scenario.action,
      sizingBb: scenario.sizingBb,
      equityPct: scenario.equityPct,
      evBb: scenario.evBb,
      targetButton: scenario.targetButton,
      targetButtonLabel: scenario.targetButtonLabel,
      clickPoint: [scenario.clickPoint[0] + jx, scenario.clickPoint[1] + jy],
      status: isLive ? 'CLICK_EXECUTED_LIVE' : 'SUPPRESSED_VERIFIED',
      biometrics: isLive ? {
        reactionMs,
        moveDurationMs: moveMs,
        pressDurationMs: pressMs,
        totalMs,
        curveProfile: 'Bézier Cúbica Natural (easeInOutQuad)',
        jitterOffset: [jx, jy]
      } : undefined
    };

    setHandHistory(prev => [newRecord, ...prev.slice(0, 19)]);

    setTimeout(() => {
      setIsSimulatingLiveTurn(false);
    }, 1800);
  };

  // Simulação de disparo de clique real animado (Live Fire)
  const handleExecuteLiveTestClick = () => {
    if (isExecutingLiveClick) return;
    setIsExecutingLiveClick(true);
    playHeroTurnSound();

    const reactionMs = Math.round(380 + Math.random() * 190);
    const moveMs = Math.round(270 + Math.random() * 90);
    const pressMs = Math.round(75 + Math.random() * 30);
    const totalMs = reactionMs + moveMs + pressMs;
    const jx = Number(((Math.random() - 0.5) * 5.0).toFixed(1));
    const jy = Number(((Math.random() - 0.5) * 4.0).toFixed(1));

    setTimeout(() => {
      setLiveClicksCount(prev => prev + 1);
      setLastBiometrics({
        reactionMs,
        moveMs,
        pressMs,
        totalMs,
        jitterOffset: [jx, jy],
        button: selectedScenario.targetButtonLabel,
        action: selectedScenario.action
      });

      const newRecord: GhostHandRecord = {
        handId: `LIVE-${liveClicksCount + 101}`,
        timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        street: selectedScenario.street,
        position: selectedScenario.position,
        heroCards: selectedScenario.heroCards,
        boardCards: selectedScenario.boardCards,
        potBb: selectedScenario.potBb,
        betToCallBb: selectedScenario.betToCallBb,
        stackBb: 100.0,
        action: selectedScenario.action,
        sizingBb: selectedScenario.sizingBb,
        equityPct: selectedScenario.equityPct,
        evBb: selectedScenario.evBb,
        targetButton: selectedScenario.targetButton,
        targetButtonLabel: selectedScenario.targetButtonLabel,
        clickPoint: [selectedScenario.clickPoint[0] + jx, selectedScenario.clickPoint[1] + jy],
        status: 'CLICK_EXECUTED_LIVE',
        biometrics: {
          reactionMs,
          moveDurationMs: moveMs,
          pressDurationMs: pressMs,
          totalMs,
          curveProfile: 'Bézier Cúbica Natural (easeInOutQuad)',
          jitterOffset: [jx, jy]
        }
      };

      setHandHistory(prev => [newRecord, ...prev.slice(0, 19)]);
      setIsExecutingLiveClick(false);
    }, 950);
  };

  // Animação decrescente de time bank
  useEffect(() => {
    const timer = setInterval(() => {
      setTimeBankRemaining(prev => (prev > 0.5 ? Number((prev - 0.2).toFixed(1)) : 15.0));
    }, 200);
    return () => clearInterval(timer);
  }, []);

  const exportAuditJson = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(handHistory, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `table_runner_audit_${operatingMode.toLowerCase()}_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="space-y-6">
      {/* 1. Header com Seletor de Modo: Espectador (Passivo) vs Live (Autônomo) */}
      <div
        className={`relative overflow-hidden rounded-2xl border p-6 shadow-2xl transition-all ${
          operatingMode === 'LIVE'
            ? isLiveArmed
              ? 'border-rose-500/60 bg-gradient-to-r from-rose-950/90 via-slate-900 to-slate-950'
              : 'border-amber-500/60 bg-gradient-to-r from-amber-950/80 via-slate-900 to-slate-950'
            : 'border-emerald-500/40 bg-gradient-to-r from-emerald-950/80 via-slate-900 to-slate-950'
        }`}
      >
        <div className="absolute -right-8 -top-8 h-40 w-40 rounded-full bg-emerald-500/10 blur-3xl pointer-events-none" />

        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-5 relative z-10">
          <div className="space-y-2.5">
            {/* Mode Switcher Tabs */}
            <div className="flex items-center gap-2 p-1 rounded-xl bg-slate-950/80 border border-slate-800 w-fit">
              <button
                onClick={() => {
                  setOperatingMode('SPECTATOR');
                  setIsLiveArmed(false);
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  operatingMode === 'SPECTATOR'
                    ? 'bg-emerald-900/80 text-emerald-200 border border-emerald-500/60 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Eye className="w-3.5 h-3.5" />
                <span>Modo Fantasma (Espectador)</span>
              </button>

              <button
                onClick={() => setOperatingMode('LIVE')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  operatingMode === 'LIVE'
                    ? 'bg-rose-950 text-rose-200 border border-rose-500 shadow-sm ring-1 ring-rose-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Flame className="w-3.5 h-3.5 text-rose-400" />
                <span>Modo Live (Cliques Reais Camuflados)</span>
                <span className="px-1.5 py-0.2 rounded text-[9px] font-black bg-rose-500 text-slate-950">
                  LIVE
                </span>
              </button>
            </div>

            <div className="flex items-center gap-2.5 flex-wrap">
              {operatingMode === 'LIVE' ? (
                <>
                  <span
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider ${
                      isLiveArmed
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/60 shadow-sm animate-pulse'
                        : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    }`}
                  >
                    <Radio className="w-4 h-4 text-rose-400" />
                    <span>{isLiveArmed ? '🔴 MODO LIVE ARMADO COM CLIQUES' : '⚠️ LIVE DESARMADO (TRAVA ATIVA)'}</span>
                  </span>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-purple-950/80 text-purple-300 border border-purple-800">
                    <Zap className="w-3.5 h-3.5" />
                    <span>Camuflagem Bézier Cúbica</span>
                  </span>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-cyan-950/80 text-cyan-300 border border-cyan-800">
                    <MousePointerClick className="w-3.5 h-3.5" />
                    <span>{liveClicksCount} Cliques Reais Executados</span>
                  </span>
                </>
              ) : (
                <>
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm animate-pulse">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <span>Modo Fantasma Ativo (--spectator / --dry-run)</span>
                  </span>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-cyan-950/80 text-cyan-300 border border-cyan-800">
                    <Eye className="w-3.5 h-3.5" />
                    <span>Cliques Físicos 100% Suprimidos</span>
                  </span>
                </>
              )}
            </div>

            <h2 className="text-xl font-black tracking-tight text-white flex items-center gap-2">
              <span>
                {operatingMode === 'LIVE'
                  ? 'Jogo Autônomo com Cliques Biométricos (PPPoker Live)'
                  : 'Painel de Segurança & Espectador de Mesa'}
              </span>
            </h2>

            <p className="text-xs text-slate-300 max-w-3xl leading-relaxed">
              {operatingMode === 'LIVE' ? (
                <>
                  O bot está configurado para <strong>interagir fisicamente com a janela do PPPoker</strong>. Ao detectar o turno do Hero, calcula a decisão nos motores GTO e despacha o clique via PyAutoGUI utilizando <strong className="text-rose-300">curvas de Bézier cúbicas humanas, velocidade variável e dispersão Gaussiana</strong> para evitar qualquer assinatura de robô.
                </>
              ) : (
                <>
                  No <strong>Modo Fantasma</strong>, o bot opera de forma 100% passiva: ele captura a tela, roda o OCR das cartas e do pote, calcula a decisão exata nos motores GTO e projeta a coordenada exata de clique no HUD, <strong className="text-emerald-300">sem mover o mouse e sem disparar cliques físicos</strong>.
                </>
              )}
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            {operatingMode === 'LIVE' ? (
              <>
                <button
                  onClick={() => setIsLiveArmed(!isLiveArmed)}
                  className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border text-xs font-bold transition-all cursor-pointer shadow-lg ${
                    isLiveArmed
                      ? 'bg-rose-600 hover:bg-rose-500 text-white border-rose-400 ring-2 ring-rose-500/40'
                      : 'bg-amber-600 hover:bg-amber-500 text-white border-amber-400 ring-1 ring-amber-500/30'
                  }`}
                >
                  {isLiveArmed ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
                  <span>{isLiveArmed ? '🛑 DESARMAR LIVE (BLOQUEAR)' : '⚡ ARMAR JOGO AO VIVO'}</span>
                </button>

                <button
                  onClick={handleExecuteLiveTestClick}
                  disabled={!isLiveArmed || isExecutingLiveClick}
                  className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-bold text-xs shadow-md transition-all cursor-pointer ${
                    isLiveArmed && !isExecutingLiveClick
                      ? 'bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-slate-950 border border-emerald-400'
                      : 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed opacity-60'
                  }`}
                >
                  <Zap className={`w-4 h-4 ${isExecutingLiveClick ? 'animate-spin' : ''}`} />
                  <span>{isExecutingLiveClick ? 'Movendo Mouse...' : 'Testar Clique Real'}</span>
                </button>
              </>
            ) : (
              <button
                onClick={() => setSoundAlertEnabled(!soundAlertEnabled)}
                className={`flex items-center justify-center gap-2 px-3.5 py-2.5 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
                  soundAlertEnabled
                    ? 'bg-emerald-900/40 border-emerald-500/60 text-emerald-200 hover:bg-emerald-800/50'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                {soundAlertEnabled ? <Volume2 className="w-4 h-4 text-emerald-400" /> : <VolumeX className="w-4 h-4 text-slate-500" />}
                <span>{soundAlertEnabled ? 'Beep Turno Ativo' : 'Beep Desativado'}</span>
              </button>
            )}

            <button
              onClick={exportAuditJson}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 font-bold text-xs shadow-md transition-all cursor-pointer"
            >
              <Download className="w-4 h-4 text-cyan-400" />
              <span>Exportar Auditoria (JSON)</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. Painel de Camuflagem Biométrica (quando Modo LIVE ativo) */}
      {operatingMode === 'LIVE' && (
        <div className="bg-slate-900 border border-rose-900/50 bg-rose-950/20 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-rose-900/40 pb-3">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-rose-400" />
              <h3 className="font-bold text-sm text-rose-200">Camuflagem Biométrica e Anti-Detecção (PyAutoGUI + Bézier)</h3>
            </div>
            <span className="text-xs font-mono text-rose-400 font-bold">ANTI-CHEAT BYPASS ATIVO</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-sans">Trajetória do Mouse:</span>
              <span className="text-emerald-400 font-bold block mt-1">Curvas Bézier Cúbicas</span>
              <span className="text-[10px] text-slate-500 font-sans block mt-0.5">Aceleração não linear (easeInOutQuad)</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-sans">Dispersão de Coordenadas:</span>
              <span className="text-cyan-400 font-bold block mt-1">Gaussiana (σ = 3.5 px)</span>
              <span className="text-[10px] text-slate-500 font-sans block mt-0.5">Nunca clica no mesmo pixel</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-sans">Reação e Pressão Humana:</span>
              <span className="text-amber-400 font-bold block mt-1">
                {lastBiometrics ? `${lastBiometrics.totalMs} ms` : '540 ms'}
              </span>
              <span className="text-[10px] text-slate-500 font-sans block mt-0.5">
                {lastBiometrics
                  ? `Reação: ${lastBiometrics.reactionMs}ms | Mov: ${lastBiometrics.moveMs}ms | Pressão: ${lastBiometrics.pressMs}ms`
                  : 'Reação aleatória 350-650ms'}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-sans">Auditoria Persistente:</span>
              <span className="text-purple-400 font-bold block mt-1">table_runner_audit.csv</span>
              <span className="text-[10px] text-slate-500 font-sans block mt-0.5">Gravação com fsync imediato</span>
            </div>
          </div>
        </div>
      )}

      {/* 3. Comandos CLI Diretos para o Terminal */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span>Comando de Execução no Terminal Windows / Desktop:</span>
          </span>
          <span className="text-[11px] font-mono text-emerald-400">
            {operatingMode === 'LIVE' ? 'Modo Live com Cliques Biométricos' : 'Modo Fantasma Seguro'}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 font-mono text-xs">
          <div className="p-3 rounded-xl bg-slate-950 border border-rose-900/60 bg-rose-950/10 flex items-center justify-between gap-2">
            <div className="overflow-hidden">
              <span className="text-[10px] text-rose-400 uppercase tracking-wider block font-sans font-bold">
                Comando Modo Live (Cliques Reais Camuflados):
              </span>
              <code className="text-rose-300 truncate block mt-0.5">
                python -m visualpilot.pppoker.table_bot_runner --live
              </code>
            </div>
            <button
              onClick={() => copyToClipboard('python -m visualpilot.pppoker.table_bot_runner --live', 'cmd-live')}
              className="px-2.5 py-1.5 rounded-lg bg-rose-900 hover:bg-rose-800 text-rose-100 flex items-center gap-1 transition-colors shrink-0"
            >
              {copiedCmd === 'cmd-live' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-rose-300" />}
              <span>{copiedCmd === 'cmd-live' ? 'Copiado' : 'Copiar'}</span>
            </button>
          </div>

          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between gap-2">
            <div className="overflow-hidden">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-sans">
                Comando Modo Fantasma (Sem Cliques - Espectador):
              </span>
              <code className="text-emerald-300 truncate block mt-0.5">
                python -m visualpilot.pppoker.table_bot_runner --spectator
              </code>
            </div>
            <button
              onClick={() => copyToClipboard('python -m visualpilot.pppoker.table_bot_runner --spectator', 'cmd-spec')}
              className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center gap-1 transition-colors shrink-0"
            >
              {copiedCmd === 'cmd-spec' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
              <span>{copiedCmd === 'cmd-spec' ? 'Copiado' : 'Copiar'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* 4. Área Central: Visualizador de Mesa Virtual + Decisão GTO */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Coluna Esquerda: Feltro da Mesa PPPoker com Projeção de Cliques Suprimidos (7 cols) */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Eye className="w-4 h-4 text-emerald-400" />
              <h3 className="font-bold text-sm text-slate-100">
                {operatingMode === 'LIVE' ? 'Mesa ao Vivo (Monitoramento com Cliques Reais)' : 'Visão da Mesa (HUD do Espectador)'}
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
                Resolução Alvo: 787x1470 px
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span
                  className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                    operatingMode === 'LIVE' ? 'bg-rose-400' : 'bg-emerald-400'
                  }`}
                />
                <span
                  className={`relative inline-flex rounded-full h-2 w-2 ${
                    operatingMode === 'LIVE' ? 'bg-rose-500' : 'bg-emerald-500'
                  }`}
                />
              </span>
              <span
                className={`text-xs font-mono font-bold ${
                  operatingMode === 'LIVE' ? 'text-rose-400' : 'text-emerald-400'
                }`}
              >
                {operatingMode === 'LIVE' ? 'MODO LIVE EM EXECUÇÃO' : 'MONITORANDO AO VIVO'}
              </span>
            </div>
          </div>

          {/* Mesa Estilizada PPPoker */}
          <div className="relative rounded-2xl bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 border border-slate-800 p-6 flex flex-col items-center justify-between min-h-[440px] overflow-hidden">
            {/* Linha do Topo: Pote Total e Street */}
            <div className="w-full flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-lg text-xs font-mono font-bold bg-slate-800/90 text-cyan-300 border border-slate-700">
                  Street: {selectedScenario.street}
                </span>
                <span className="px-2.5 py-1 rounded-lg text-xs font-mono font-bold bg-amber-950/60 text-amber-300 border border-amber-800/60">
                  Posição: {selectedScenario.position}
                </span>
              </div>

              <div className="flex items-center gap-2 bg-slate-950/90 border border-slate-700/80 px-3.5 py-1.5 rounded-xl">
                <span className="text-xs text-slate-400 font-sans">Pote Total:</span>
                <span className="text-sm font-black font-mono text-amber-400">{selectedScenario.potBb.toFixed(1)} BB</span>
              </div>
            </div>

            {/* Centro: Board Comunitário */}
            <div className="flex flex-col items-center my-6 space-y-2">
              <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
                Cartas Comunitárias ({selectedScenario.boardCards.length}/5)
              </span>

              <div className="flex items-center gap-2.5">
                {selectedScenario.boardCards.length > 0 ? (
                  selectedScenario.boardCards.map((card, idx) => (
                    <div
                      key={idx}
                      className="w-13 h-18 rounded-xl bg-slate-950 border-2 border-slate-700 shadow-xl flex flex-col items-center justify-center font-mono font-bold text-lg select-none"
                    >
                      <span className={card.includes('♥') || card.includes('♦') ? 'text-rose-400' : 'text-slate-100'}>
                        {card}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="px-6 py-4 rounded-xl border border-dashed border-slate-800 text-slate-500 font-mono text-xs">
                    [Pré-Flop: Nenhuma carta comunitária aberta]
                  </div>
                )}
              </div>
            </div>

            {/* Linha Inferior: Cartas do Hero + Barra de Time Bank */}
            <div className="w-full space-y-4">
              <div className="flex flex-col items-center">
                <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider mb-1">
                  Cartas do Hero (Hero Cards)
                </span>
                <div className="flex items-center gap-3">
                  {selectedScenario.heroCards.map((card, idx) => (
                    <div
                      key={idx}
                      className="w-14 h-20 rounded-xl bg-gradient-to-b from-slate-900 to-slate-950 border-2 border-emerald-500/80 shadow-2xl flex flex-col items-center justify-center font-mono font-black text-xl text-emerald-300 ring-2 ring-emerald-500/20"
                    >
                      <span>{card}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Time Bank */}
              <div className="space-y-1">
                <div className="flex justify-between text-[11px] font-mono text-slate-400">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-amber-400" />
                    <span>Time Bank do Hero</span>
                  </span>
                  <span className="font-bold text-amber-300">{timeBankRemaining}s restantes</span>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden p-0.5">
                  <div
                    className="h-full bg-gradient-to-r from-amber-500 to-emerald-400 rounded-full transition-all duration-200"
                    style={{ width: `${(timeBankRemaining / 15.0) * 100}%` }}
                  />
                </div>
              </div>

              {/* Botões Virtuais de Ação do PPPoker */}
              <div className="pt-2 border-t border-slate-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
                    Barra de Ações do PPPoker:
                  </span>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                      operatingMode === 'LIVE'
                        ? isLiveArmed
                          ? 'bg-rose-950 text-rose-300 border-rose-800 font-bold'
                          : 'bg-amber-950 text-amber-300 border-amber-800'
                        : 'bg-emerald-950 text-emerald-400 border-emerald-800'
                    }`}
                  >
                    {operatingMode === 'LIVE'
                      ? isLiveArmed
                        ? 'Cliques Físicos Armados'
                        : 'Live Travado'
                      : 'Clique Físico Bloqueado'}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  {/* Botão Esquerdo */}
                  <div
                    className={`relative p-3 rounded-xl border text-center transition-all ${
                      selectedScenario.targetButton === 'btn_left'
                        ? 'bg-rose-950/80 border-rose-500 ring-2 ring-rose-500/50 shadow-lg'
                        : 'bg-slate-950 border-slate-800 text-slate-400'
                    }`}
                  >
                    {selectedScenario.targetButton === 'btn_left' && (
                      <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-[9px] font-mono font-bold bg-rose-500 text-slate-950 uppercase tracking-wider shadow">
                        ALVO DECISÃO
                      </span>
                    )}
                    <div className="font-bold text-xs">Fold / Check</div>
                    <div className="text-[10px] font-mono text-slate-500 mt-1">btn_left (138, 1412)</div>
                  </div>

                  {/* Botão Centro */}
                  <div
                    className={`relative p-3 rounded-xl border text-center transition-all ${
                      selectedScenario.targetButton === 'btn_center'
                        ? 'bg-cyan-950/80 border-cyan-500 ring-2 ring-cyan-500/50 shadow-lg'
                        : 'bg-slate-950 border-slate-800 text-slate-400'
                    }`}
                  >
                    {selectedScenario.targetButton === 'btn_center' && (
                      <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-[9px] font-mono font-bold bg-cyan-400 text-slate-950 uppercase tracking-wider shadow">
                        ALVO DECISÃO
                      </span>
                    )}
                    <div className="font-bold text-xs">Check / Call</div>
                    <div className="text-[10px] font-mono text-slate-500 mt-1">btn_center (392, 1412)</div>
                  </div>

                  {/* Botão Direito */}
                  <div
                    className={`relative p-3 rounded-xl border text-center transition-all ${
                      selectedScenario.targetButton === 'btn_right' || selectedScenario.targetButton.startsWith('size_')
                        ? 'bg-emerald-950/80 border-emerald-500 ring-2 ring-emerald-500/50 shadow-lg'
                        : 'bg-slate-950 border-slate-800 text-slate-400'
                    }`}
                  >
                    {(selectedScenario.targetButton === 'btn_right' || selectedScenario.targetButton.startsWith('size_')) && (
                      <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-[9px] font-mono font-bold bg-emerald-400 text-slate-950 uppercase tracking-wider shadow">
                        ALVO DECISÃO
                      </span>
                    )}
                    <div className="font-bold text-xs text-emerald-300">Bet / Raise</div>
                    <div className="text-[10px] font-mono text-slate-500 mt-1">btn_right (650, 1412)</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Coluna Direita: Decisão Calculada + Simulador de Cenários (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Card Decisão Recomendada */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="border-b border-slate-800 pb-3 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">
                  Decisão do Cérebro GTO:
                </span>
                <h3 className="font-black text-lg text-emerald-300 flex items-center gap-2">
                  <span>{selectedScenario.action} {selectedScenario.sizingBb ? `(${selectedScenario.sizingBb} BB)` : ''}</span>
                </h3>
              </div>

              <div className="text-right">
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">EV Estimado:</span>
                <span className="text-sm font-mono font-bold text-cyan-300">+{selectedScenario.evBb.toFixed(2)} BB</span>
              </div>
            </div>

            {/* Métricas de Equidade e Pote */}
            <div className="grid grid-cols-2 gap-3 font-mono text-xs">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-sans">Equidade da Mão:</span>
                <span className="text-base font-bold text-emerald-400 mt-0.5 block">{selectedScenario.equityPct.toFixed(1)}%</span>
                <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden mt-1.5">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${selectedScenario.equityPct}%` }} />
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-sans">Coordenada Alvo:</span>
                <span className="text-xs font-bold text-amber-300 mt-1 block">X={selectedScenario.clickPoint[0]}, Y={selectedScenario.clickPoint[1]}</span>
                <span className="text-[10px] text-slate-500 font-sans block mt-1">Dispersão Gaussiana (σ=3.5)</span>
              </div>
            </div>

            {/* Descrição Tática */}
            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 space-y-1">
              <span className="font-bold text-slate-200 block">Racional Estratégico:</span>
              <p className="text-slate-400 leading-relaxed text-[11px]">{selectedScenario.description}</p>
            </div>

            {/* Aviso de Confirmação de Segurança */}
            <div
              className={`p-3 rounded-xl border flex items-start gap-2.5 text-xs ${
                operatingMode === 'LIVE'
                  ? isLiveArmed
                    ? 'bg-rose-950/40 border-rose-800/60 text-rose-200'
                    : 'bg-amber-950/40 border-amber-800/60 text-amber-200'
                  : 'bg-emerald-950/40 border-emerald-800/60 text-emerald-200'
              }`}
            >
              {operatingMode === 'LIVE' ? (
                <Flame className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              ) : (
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              )}
              <div className="text-[11px] leading-relaxed">
                {operatingMode === 'LIVE' ? (
                  isLiveArmed ? (
                    <span>
                      <strong>Modo Live Armado:</strong> O robô executará o clique físico em curva de Bézier sobre a janela do PPPoker assim que for o seu turno.
                    </span>
                  ) : (
                    <span>
                      <strong>Trava de Segurança Ativa:</strong> Clique no botão "Armar Jogo ao Vivo" para autorizar os cliques físicos.
                    </span>
                  )
                ) : (
                  <span>
                    <strong>Garantia do Modo Fantasma:</strong> O mouse físico <strong>não será movimentado</strong> e nenhum pacote de clique será enviado ao sistema operacional.
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Cenários de Teste Rápido */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-xs uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <Play className="w-3.5 h-3.5 text-amber-400" />
                <span>Simular Cenários:</span>
              </h4>
              <span className="text-[10px] font-mono text-slate-400">Clique para testar</span>
            </div>

            <div className="space-y-2">
              {PRESET_SCENARIOS.map(scen => (
                <button
                  key={scen.id}
                  onClick={() => triggerScenario(scen)}
                  className={`w-full text-left p-2.5 rounded-xl border text-xs transition-all cursor-pointer flex items-center justify-between gap-2 ${
                    selectedScenario.id === scen.id
                      ? 'bg-emerald-950/70 border-emerald-500/80 text-emerald-200 shadow-md ring-1 ring-emerald-500/30'
                      : 'bg-slate-950 border-slate-800/80 text-slate-300 hover:bg-slate-800/60 hover:text-slate-100'
                  }`}
                >
                  <div className="overflow-hidden">
                    <span className="font-bold block truncate">{scen.title}</span>
                    <span className="text-[10px] font-mono text-slate-400 block mt-0.5">
                      {scen.street} • Pot: {scen.potBb} BB • Ação: {scen.action}
                    </span>
                  </div>

                  <ArrowRight className={`w-3.5 h-3.5 shrink-0 ${selectedScenario.id === scen.id ? 'text-emerald-400' : 'text-slate-500'}`} />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 5. Histórico de Mãos Auditadas (Fantasma e Live) */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div>
            <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              <span>Log de Auditoria da Sessão ({handHistory.length} mãos registradas)</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Auditoria de leituras, decisões GTO e telemetria biométrica dos cliques executados em tempo real.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`px-2.5 py-1 rounded-lg text-xs font-mono border ${
                liveClicksCount > 0
                  ? 'bg-rose-950 text-rose-300 border-rose-800 font-bold'
                  : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
              }`}
            >
              {liveClicksCount} Cliques Físicos Disparados
            </span>
          </div>
        </div>

        <div className="overflow-x-auto border border-slate-800 rounded-xl">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-950 border-b border-slate-800 text-slate-400 font-mono text-[11px]">
                <th className="p-3">Mão</th>
                <th className="p-3">Horário</th>
                <th className="p-3">Posição</th>
                <th className="p-3">Cartas Hero</th>
                <th className="p-3">Board</th>
                <th className="p-3">Pote (BB)</th>
                <th className="p-3">Decisão Recomendada</th>
                <th className="p-3">Equidade / EV</th>
                <th className="p-3">Botão PPPoker</th>
                <th className="p-3">Status de Execução</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
              {handHistory.map(row => (
                <tr key={row.handId} className="hover:bg-slate-800/40 transition-colors">
                  <td className="p-3 font-bold text-cyan-400">{row.handId}</td>
                  <td className="p-3 text-slate-400">{row.timestamp}</td>
                  <td className="p-3">
                    <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-200">{row.position}</span>
                  </td>
                  <td className="p-3 font-bold text-emerald-300">
                    {row.heroCards.join(' ')}
                  </td>
                  <td className="p-3 text-slate-300">
                    {row.boardCards.length > 0 ? row.boardCards.join(' ') : '— (Pré-flop)'}
                  </td>
                  <td className="p-3 text-amber-300 font-bold">{row.potBb.toFixed(1)} BB</td>
                  <td className="p-3">
                    <span
                      className={`px-2 py-0.5 rounded font-bold ${
                        row.action === 'FOLD'
                          ? 'bg-rose-950 text-rose-300 border border-rose-800'
                          : row.action === 'CHECK' || row.action === 'CALL'
                          ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                          : 'bg-emerald-950 text-emerald-300 border border-emerald-700'
                      }`}
                    >
                      {row.action} {row.sizingBb ? `(${row.sizingBb} BB)` : ''}
                    </span>
                  </td>
                  <td className="p-3 text-slate-300">
                    {row.equityPct.toFixed(1)}% / +{row.evBb.toFixed(2)} BB
                  </td>
                  <td className="p-3 text-slate-400">
                    {row.targetButtonLabel}
                  </td>
                  <td className="p-3">
                    {row.status === 'CLICK_EXECUTED_LIVE' ? (
                      <span className="px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-700 font-mono text-[10px] font-bold flex items-center gap-1 w-fit">
                        <Flame className="w-3 h-3 text-rose-400" />
                        <span>CLIQUE REAL ({row.biometrics?.totalMs || 720}ms)</span>
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800 font-mono text-[10px] font-bold">
                        ✓ SUPRIMIDO (SEM RISCO)
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
