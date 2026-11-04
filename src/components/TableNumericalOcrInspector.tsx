import React, { useState } from 'react';
import {
  Coins,
  Crosshair,
  Sliders,
  Sparkles,
  RefreshCw,
  Download,
  Copy,
  Check,
  RotateCcw,
  ShieldCheck,
  TrendingUp,
  Percent,
  SlidersHorizontal,
  Info,
  CheckCircle2,
  AlertTriangle,
  UserCheck
} from 'lucide-react';
import { TableTreemap } from './TableTreemap';

export interface SeatData {
  seatNumber: number;
  playerName: string;
  stackBb: number;
  stackChips: number;
  currentBetBb: number;
  isHero: boolean;
  isFolded: boolean;
  box: [number, number, number, number]; // [ymin, xmin, ymax, xmax]
}

const DEFAULT_SEATS: SeatData[] = [
  { seatNumber: 1, playerName: 'DealerPro',   stackBb: 105.0, stackChips: 10500, currentBetBb: 0.0, isHero: false, isFolded: false, box: [265, 30, 335, 210] },
  { seatNumber: 2, playerName: 'ShortBlind',  stackBb: 38.0,  stackChips: 3800,  currentBetBb: 0.5, isHero: false, isFolded: false, box: [170, 300, 240, 485] },
  { seatNumber: 3, playerName: 'BigBlind_BR', stackBb: 92.0,  stackChips: 9200,  currentBetBb: 1.0, isHero: false, isFolded: false, box: [265, 575, 335, 755] },
  { seatNumber: 4, playerName: 'AggroUTG',    stackBb: 140.0, stackChips: 14000, currentBetBb: 6.0, isHero: false, isFolded: false, box: [720, 575, 790, 755] },
  { seatNumber: 5, playerName: 'Hero (Você)', stackBb: 115.0, stackChips: 11500, currentBetBb: 0.0, isHero: true,  isFolded: false, box: [1190, 290, 1260, 495] },
  { seatNumber: 6, playerName: 'NitPlayer',   stackBb: 75.0,  stackChips: 7500,  currentBetBb: 0.0, isHero: false, isFolded: true,  box: [720, 30, 790, 210] },
];

const PRESET_NUMERICAL_SCENARIOS = [
  {
    name: 'Flop Standard em Pote 3-Bet',
    desc: 'Vilão UTG apostou 6.0 BB num pote de 18.5 BB. Hero no Cutoff.',
    potBb: 18.5,
    toCallBb: 6.0,
    dealerSeat: 1,
    seats: [
      { seatNumber: 1, playerName: 'DealerPro',   stackBb: 105.0, stackChips: 10500, currentBetBb: 0.0, isHero: false, isFolded: false, box: [265, 30, 335, 210] as [number, number, number, number] },
      { seatNumber: 2, playerName: 'ShortBlind',  stackBb: 38.0,  stackChips: 3800,  currentBetBb: 0.5, isHero: false, isFolded: false, box: [170, 300, 240, 485] as [number, number, number, number] },
      { seatNumber: 3, playerName: 'BigBlind_BR', stackBb: 92.0,  stackChips: 9200,  currentBetBb: 1.0, isHero: false, isFolded: false, box: [265, 575, 335, 755] as [number, number, number, number] },
      { seatNumber: 4, playerName: 'AggroUTG',    stackBb: 140.0, stackChips: 14000, currentBetBb: 6.0, isHero: false, isFolded: false, box: [720, 575, 790, 755] as [number, number, number, number] },
      { seatNumber: 5, playerName: 'Hero (Você)', stackBb: 115.0, stackChips: 11500, currentBetBb: 0.0, isHero: true,  isFolded: false, box: [1190, 290, 1260, 495] as [number, number, number, number] },
      { seatNumber: 6, playerName: 'NitPlayer',   stackBb: 75.0,  stackChips: 7500,  currentBetBb: 0.0, isHero: false, isFolded: true,  box: [720, 30, 790, 210] as [number, number, number, number] },
    ]
  },
  {
    name: 'Batalha de Blinds (Heads-Up SB vs BB)',
    desc: 'SB abriu limp/raise e Hero defende o Big Blind.',
    potBb: 7.5,
    toCallBb: 2.5,
    dealerSeat: 2,
    seats: [
      { seatNumber: 1, playerName: 'Seat Open',   stackBb: 0,     stackChips: 0,     currentBetBb: 0.0, isHero: false, isFolded: true,  box: [265, 30, 335, 210] as [number, number, number, number] },
      { seatNumber: 2, playerName: 'AggroSB',     stackBb: 85.0,  stackChips: 8500,  currentBetBb: 2.5, isHero: false, isFolded: false, box: [170, 300, 240, 485] as [number, number, number, number] },
      { seatNumber: 3, playerName: 'Seat Open',   stackBb: 0,     stackChips: 0,     currentBetBb: 0.0, isHero: false, isFolded: true,  box: [265, 575, 335, 755] as [number, number, number, number] },
      { seatNumber: 4, playerName: 'Seat Open',   stackBb: 0,     stackChips: 0,     currentBetBb: 0.0, isHero: false, isFolded: true,  box: [720, 575, 790, 755] as [number, number, number, number] },
      { seatNumber: 5, playerName: 'Hero (Você)', stackBb: 98.0,  stackChips: 9800,  currentBetBb: 1.0, isHero: true,  isFolded: false, box: [1190, 290, 1260, 495] as [number, number, number, number] },
      { seatNumber: 6, playerName: 'Seat Open',   stackBb: 0,     stackChips: 0,     currentBetBb: 0.0, isHero: false, isFolded: true,  box: [720, 30, 790, 210] as [number, number, number, number] },
    ]
  },
  {
    name: 'Pote Multi-Way 4 Jogadores no Turn',
    desc: 'Pote inflado de 48.0 BB com aposta pesada de 18.0 BB.',
    potBb: 48.0,
    toCallBb: 18.0,
    dealerSeat: 4,
    seats: [
      { seatNumber: 1, playerName: 'Caller_1',    stackBb: 62.0,  stackChips: 6200,  currentBetBb: 0.0, isHero: false, isFolded: false, box: [265, 30, 335, 210] as [number, number, number, number] },
      { seatNumber: 2, playerName: 'Caller_2',    stackBb: 45.0,  stackChips: 4500,  currentBetBb: 0.0, isHero: false, isFolded: false, box: [170, 300, 240, 485] as [number, number, number, number] },
      { seatNumber: 3, playerName: 'Nit_Folds',   stackBb: 80.0,  stackChips: 8000,  currentBetBb: 0.0, isHero: false, isFolded: true,  box: [265, 575, 335, 755] as [number, number, number, number] },
      { seatNumber: 4, playerName: 'ManiacBet',   stackBb: 120.0, stackChips: 12000, currentBetBb: 18.0, isHero: false, isFolded: false, box: [720, 575, 790, 755] as [number, number, number, number] },
      { seatNumber: 5, playerName: 'Hero (Você)', stackBb: 72.0,  stackChips: 7200,  currentBetBb: 0.0, isHero: true,  isFolded: false, box: [1190, 290, 1260, 495] as [number, number, number, number] },
      { seatNumber: 6, playerName: 'Folded_EP',   stackBb: 35.0,  stackChips: 3500,  currentBetBb: 0.0, isHero: false, isFolded: true,  box: [720, 30, 790, 210] as [number, number, number, number] },
    ]
  },
  {
    name: 'Short Stack All-In no Pré-Flop',
    desc: 'Vilão shovou 14.0 BB all-in. Pote total de 17.5 BB.',
    potBb: 17.5,
    toCallBb: 14.0,
    dealerSeat: 3,
    seats: [
      { seatNumber: 1, playerName: 'Folded_1',    stackBb: 95.0,  stackChips: 9500,  currentBetBb: 0.0, isHero: false, isFolded: true,  box: [265, 30, 335, 210] as [number, number, number, number] },
      { seatNumber: 2, playerName: 'Folded_2',    stackBb: 78.0,  stackChips: 7800,  currentBetBb: 0.0, isHero: false, isFolded: true,  box: [170, 300, 240, 485] as [number, number, number, number] },
      { seatNumber: 3, playerName: 'BTN_Caller',  stackBb: 110.0, stackChips: 11000, currentBetBb: 0.0, isHero: false, isFolded: false, box: [265, 575, 335, 755] as [number, number, number, number] },
      { seatNumber: 4, playerName: 'AllInShove',  stackBb: 0.0,   stackChips: 0,     currentBetBb: 14.0, isHero: false, isFolded: false, box: [720, 575, 790, 755] as [number, number, number, number] },
      { seatNumber: 5, playerName: 'Hero (Você)', stackBb: 85.0,  stackChips: 8500,  currentBetBb: 1.0, isHero: true,  isFolded: false, box: [1190, 290, 1260, 495] as [number, number, number, number] },
      { seatNumber: 6, playerName: 'Folded_3',    stackBb: 60.0,  stackChips: 6000,  currentBetBb: 0.0, isHero: false, isFolded: true,  box: [720, 30, 790, 210] as [number, number, number, number] },
    ]
  }
];

export const TableNumericalOcrInspector: React.FC<{
  onNotify?: (title: string, message: string, severity: 'INFO' | 'WARN' | 'CRITICAL') => void;
}> = ({ onNotify }) => {
  const [potBb, setPotBb] = useState<number>(18.5);
  const [toCallBb, setToCallBb] = useState<number>(6.0);
  const [dealerSeat, setDealerSeat] = useState<number>(1);
  const [seats, setSeats] = useState<SeatData[]>(DEFAULT_SEATS);
  const [selectedSeatNumber, setSelectedSeatNumber] = useState<number>(5); // Default Hero
  const [potRoi, setPotRoi] = useState<[number, number, number, number]>([520, 270, 580, 515]);
  const [copiedPython, setCopiedPython] = useState<boolean>(false);

  // Compute Relative Positions starting from dealerSeat
  const computeSeatPosition = (seatNum: number): string => {
    const activeSeats = seats.filter(s => !s.isFolded && s.stackBb > 0 || s.currentBetBb > 0);
    const sortedActive = [...activeSeats].sort((a, b) => (a.seatNumber - dealerSeat + 6) % 6 - (b.seatNumber - dealerSeat + 6) % 6);
    const idx = sortedActive.findIndex(s => s.seatNumber === seatNum);
    if (idx === -1) return 'Fold';

    if (sortedActive.length === 2) {
      return idx === 0 ? 'BTN/SB' : 'BB';
    }

    const order6 = ['BTN', 'SB', 'BB', 'UTG', 'MP', 'CO'];
    if (sortedActive.length === 6) return order6[idx];
    if (sortedActive.length === 5) return ['BTN', 'SB', 'BB', 'UTG', 'CO'][idx];
    if (sortedActive.length === 4) return ['BTN', 'SB', 'BB', 'CO'][idx];
    if (sortedActive.length === 3) return ['BTN', 'SB', 'BB'][idx];
    return order6[idx % order6.length];
  };

  const heroSeatData = seats.find(s => s.isHero) || seats[4];
  const heroPos = computeSeatPosition(heroSeatData.seatNumber);

  // Math: Pot Odds & SPR
  const potOddsPercent = toCallBb > 0 ? Number(((toCallBb / (potBb + toCallBb)) * 100).toFixed(1)) : 0.0;
  const sprValue = potBb > 0 ? Number((heroSeatData.stackBb / potBb).toFixed(1)) : 99.0;

  const getSprAnalysis = (spr: number) => {
    if (spr <= 1.0) return { cat: 'Commit (All-in Fácil)', badge: 'bg-rose-950 text-rose-300 border-rose-700', desc: 'Pote já representa todo o stack. Qualquer Top Pair ou forte draw justifica shove/call direto.' };
    if (spr <= 4.0) return { cat: 'Low SPR (Decisão Rápida)', badge: 'bg-amber-950 text-amber-300 border-amber-700', desc: 'Stacks curtos em relação ao pote. Pouco espaço de manobra pós-flop.' };
    if (spr <= 13.0) return { cat: 'Médio SPR (Cautela)', badge: 'bg-emerald-950 text-emerald-300 border-emerald-700', desc: 'Profundidade padrão. Controle de pote com mãos marginais e blefes calculados.' };
    return { cat: 'Deep Stack (Posicional)', badge: 'bg-blue-950 text-blue-300 border-blue-700', desc: 'Muito stack por trás. Vantagem máxima para posição e mãos especulativas.' };
  };

  const sprInfo = getSprAnalysis(sprValue);

  const applyScenario = (scen: typeof PRESET_NUMERICAL_SCENARIOS[0]) => {
    setPotBb(scen.potBb);
    setToCallBb(scen.toCallBb);
    setDealerSeat(scen.dealerSeat);
    setSeats(scen.seats);
    onNotify?.("CENÁRIO APLICADO", `Cenário "${scen.name}" carregado com sucesso.`, "INFO");
  };

  const adjustSeatRoi = (seatNum: number, coordIdx: number, delta: number) => {
    setSeats(prev => prev.map(s => {
      if (s.seatNumber === seatNum) {
        const newBox = [...s.box] as [number, number, number, number];
        newBox[coordIdx] += delta;
        return { ...s, box: newBox };
      }
      return s;
    }));
  };

  const adjustPotRoi = (coordIdx: number, delta: number) => {
    setPotRoi(prev => {
      const cur = [...prev] as [number, number, number, number];
      cur[coordIdx] += delta;
      return cur;
    });
  };

  const copyPythonCode = () => {
    const code = `
# ROIs Numéricos da Mesa PPPoker (787x1470 px)
TOTAL_POT_ROI = (${potRoi.join(', ')})

SEAT_STACK_ROIS = {
${seats.map(s => `    ${s.seatNumber}: (${s.box.join(', ')}),  # Seat ${s.seatNumber} (${s.playerName})`).join('\n')}
}
`.trim();
    navigator.clipboard.writeText(code);
    setCopiedPython(true);
    setTimeout(() => setCopiedPython(false), 2000);
  };

  const handleTreemapSelect = (name: string, valueBb: number, isPot: boolean) => {
    if (isPot) {
      onNotify?.("POTE SELECIONADO NO TREEMAP", `Pote de ${valueBb.toFixed(1)} BB em foco.`, "INFO");
    } else {
      const match = seats.find(s => s.playerName === name);
      if (match) {
        setSelectedSeatNumber(match.seatNumber);
        onNotify?.("JOGADOR SELECIONADO NO TREEMAP", `Assento #${match.seatNumber} (${name}) com stack de ${valueBb.toFixed(1)} BB selecionado para calibração.`, "INFO");
      }
    }
  };

  const selectedSeat = seats.find(s => s.seatNumber === selectedSeatNumber) || seats[4];

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-80 h-full bg-gradient-to-l from-emerald-500/10 via-cyan-500/5 to-transparent pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <Coins className="w-5 h-5" />
              </span>
              <h2 className="text-xl font-bold text-slate-100 tracking-tight">
                OCR Numérico da Mesa, Stacks e Posições (Dealer D)
              </h2>
            </div>
            <p className="text-xs text-slate-400 max-w-2xl">
              Leitura OCR em tempo real do Pote Principal, Stacks dos 6 jogadores, apostas no pano, localização do botão de Dealer (D), dedução posicional automática (BTN, SB, BB, UTG, MP, CO), e cálculo matemático de <strong>Pot Odds</strong> e <strong>SPR</strong>.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={copyPythonCode}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 transition-colors shadow-sm cursor-pointer"
            >
              {copiedPython ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
              <span>{copiedPython ? 'Copiado!' : 'Copiar ROIs Python'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* D3 Treemap: Distribuição de Potes e Stacks das Mesas Ativas */}
      <TableTreemap
        currentTablePotBb={potBb}
        currentTableSeats={seats}
        onSelectEntity={handleTreemapSelect}
      />

      {/* Main Grid: Left (Table Visual with Dealer & Positions) + Right (Pot Odds, SPR & Calibration) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Visual Table Canvas with 6 Seats (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Mapeamento Visual da Mesa 6-Max
                </span>
                <span className="text-[11px] font-mono text-slate-400">
                  787 × 1470 px
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-emerald-400">
                  Hero no: <strong className="px-1.5 py-0.2 rounded bg-emerald-950 border border-emerald-800 font-bold">{heroPos}</strong>
                </span>
              </div>
            </div>

            {/* Table Mockup Container (Portrait 9:16.8 ratio) */}
            <div className="relative w-full aspect-[9/16] bg-gradient-to-b from-slate-950 via-[#0a1b14] to-slate-950 rounded-2xl border-2 border-slate-800 overflow-hidden flex flex-col justify-between p-3 select-none shadow-inner">
              {/* Outer Rail / Felt Border */}
              <div className="absolute inset-2 rounded-[36px] border border-emerald-900/40 bg-[#0d2218]/90 pointer-events-none" />
              <div className="absolute inset-5 rounded-[28px] border border-emerald-700/20 bg-radial from-[#123324] to-[#0a1e15] pointer-events-none" />

              {/* Top Watermark */}
              <div className="relative z-10 flex items-center justify-between text-[10px] font-mono text-emerald-500/60 px-2 pt-0.5">
                <span>PPPoker Mesa #7401</span>
                <span>Blinds: 50/100 (1 BB)</span>
              </div>

              {/* SEAT 2: Top Center */}
              <div className="relative z-10 flex justify-center">
                {(() => {
                  const s = seats[1];
                  const pos = computeSeatPosition(s.seatNumber);
                  const isDealer = s.seatNumber === dealerSeat;
                  return (
                    <div
                      onClick={() => setSelectedSeatNumber(s.seatNumber)}
                      className={`relative flex flex-col items-center px-3 py-1.5 rounded-xl border transition-all cursor-pointer ${
                        selectedSeatNumber === s.seatNumber
                          ? 'bg-slate-900 border-amber-400 ring-2 ring-amber-400/40 shadow-lg'
                          : 'bg-slate-950/90 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      {/* Dealer Button Badge (Clickable to move Dealer) */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDealerSeat(s.seatNumber);
                        }}
                        className={`absolute -top-2.5 -right-2.5 w-6 h-6 rounded-full font-black text-xs flex items-center justify-center border shadow-md transition-all cursor-pointer ${
                          isDealer
                            ? 'bg-amber-400 text-slate-950 border-amber-300 ring-2 ring-amber-400/50 scale-110'
                            : 'bg-slate-800 text-slate-400 border-slate-700 opacity-60 hover:opacity-100'
                        }`}
                        title="Clique para definir este assento como Dealer (D)"
                      >
                        D
                      </button>

                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.2 rounded text-[10px] font-black bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">
                          {pos}
                        </span>
                        <span className="text-xs font-bold text-slate-200">{s.playerName}</span>
                      </div>
                      <span className="text-xs font-mono font-bold text-emerald-400">{s.stackBb} BB</span>
                      {s.currentBetBb > 0 && (
                        <div className="mt-1 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-mono border border-amber-500/40">
                          Aposta: {s.currentBetBb} BB
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>

              {/* SEATS 1 & 3: Top Left & Top Right */}
              <div className="relative z-10 flex items-center justify-between px-2">
                {/* Seat 1 */}
                {(() => {
                  const s = seats[0];
                  const pos = computeSeatPosition(s.seatNumber);
                  const isDealer = s.seatNumber === dealerSeat;
                  return (
                    <div
                      onClick={() => setSelectedSeatNumber(s.seatNumber)}
                      className={`relative flex flex-col items-start px-2.5 py-1.5 rounded-xl border transition-all cursor-pointer max-w-[120px] ${
                        selectedSeatNumber === s.seatNumber
                          ? 'bg-slate-900 border-amber-400 ring-2 ring-amber-400/40 shadow-lg'
                          : 'bg-slate-950/90 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDealerSeat(s.seatNumber);
                        }}
                        className={`absolute -top-2 -right-2 w-5 h-5 rounded-full font-black text-[10px] flex items-center justify-center border shadow transition-all cursor-pointer ${
                          isDealer
                            ? 'bg-amber-400 text-slate-950 border-amber-300 ring-2 ring-amber-400/50 scale-110'
                            : 'bg-slate-800 text-slate-400 border-slate-700 opacity-60 hover:opacity-100'
                        }`}
                        title="Definir Dealer"
                      >
                        D
                      </button>
                      <div className="flex items-center gap-1">
                        <span className="px-1 py-0.2 rounded text-[9px] font-black bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">{pos}</span>
                        <span className="text-[11px] font-bold text-slate-200 truncate">{s.playerName}</span>
                      </div>
                      <span className="text-[11px] font-mono font-bold text-emerald-400">{s.stackBb} BB</span>
                      {s.currentBetBb > 0 && <span className="text-[9px] font-mono text-amber-300">Bet: {s.currentBetBb} BB</span>}
                    </div>
                  );
                })()}

                {/* Seat 3 */}
                {(() => {
                  const s = seats[2];
                  const pos = computeSeatPosition(s.seatNumber);
                  const isDealer = s.seatNumber === dealerSeat;
                  return (
                    <div
                      onClick={() => setSelectedSeatNumber(s.seatNumber)}
                      className={`relative flex flex-col items-end px-2.5 py-1.5 rounded-xl border transition-all cursor-pointer max-w-[120px] ${
                        selectedSeatNumber === s.seatNumber
                          ? 'bg-slate-900 border-amber-400 ring-2 ring-amber-400/40 shadow-lg'
                          : 'bg-slate-950/90 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDealerSeat(s.seatNumber);
                        }}
                        className={`absolute -top-2 -left-2 w-5 h-5 rounded-full font-black text-[10px] flex items-center justify-center border shadow transition-all cursor-pointer ${
                          isDealer
                            ? 'bg-amber-400 text-slate-950 border-amber-300 ring-2 ring-amber-400/50 scale-110'
                            : 'bg-slate-800 text-slate-400 border-slate-700 opacity-60 hover:opacity-100'
                        }`}
                        title="Definir Dealer"
                      >
                        D
                      </button>
                      <div className="flex items-center gap-1">
                        <span className="text-[11px] font-bold text-slate-200 truncate">{s.playerName}</span>
                        <span className="px-1 py-0.2 rounded text-[9px] font-black bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">{pos}</span>
                      </div>
                      <span className="text-[11px] font-mono font-bold text-emerald-400">{s.stackBb} BB</span>
                      {s.currentBetBb > 0 && <span className="text-[9px] font-mono text-amber-300">Bet: {s.currentBetBb} BB</span>}
                    </div>
                  );
                })()}
              </div>

              {/* CENTER: TOTAL POT DISPLAY */}
              <div className="relative z-10 flex flex-col items-center my-auto">
                <div
                  className="px-5 py-2 rounded-2xl bg-black/80 border-2 border-emerald-500/60 shadow-xl text-center space-y-0.5 backdrop-blur-sm"
                >
                  <span className="text-[10px] uppercase font-mono tracking-widest text-slate-400 block font-bold">
                    Pote Principal (Total Pot)
                  </span>
                  <div className="text-xl font-black font-mono text-amber-400 flex items-center justify-center gap-1.5">
                    <span>{potBb} BB</span>
                    <span className="text-xs text-slate-400 font-normal">({(potBb * 100).toLocaleString()} fichas)</span>
                  </div>
                  {toCallBb > 0 && (
                    <div className="text-[10px] font-mono text-cyan-300 pt-0.5 border-t border-slate-800">
                      Aposta a Pagar: <strong>{toCallBb} BB</strong> (Pot Odds: <strong>{potOddsPercent}%</strong>)
                    </div>
                  )}
                </div>
              </div>

              {/* SEATS 6 & 4: Middle Left & Middle Right */}
              <div className="relative z-10 flex items-center justify-between px-2">
                {/* Seat 6 */}
                {(() => {
                  const s = seats[5];
                  const pos = computeSeatPosition(s.seatNumber);
                  const isDealer = s.seatNumber === dealerSeat;
                  return (
                    <div
                      onClick={() => setSelectedSeatNumber(s.seatNumber)}
                      className={`relative flex flex-col items-start px-2.5 py-1.5 rounded-xl border transition-all cursor-pointer max-w-[120px] ${
                        s.isFolded ? 'opacity-40 bg-slate-950 border-slate-900' :
                        selectedSeatNumber === s.seatNumber
                          ? 'bg-slate-900 border-amber-400 ring-2 ring-amber-400/40 shadow-lg'
                          : 'bg-slate-950/90 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDealerSeat(s.seatNumber);
                        }}
                        className={`absolute -top-2 -right-2 w-5 h-5 rounded-full font-black text-[10px] flex items-center justify-center border shadow transition-all cursor-pointer ${
                          isDealer
                            ? 'bg-amber-400 text-slate-950 border-amber-300 ring-2 ring-amber-400/50 scale-110'
                            : 'bg-slate-800 text-slate-400 border-slate-700 opacity-60 hover:opacity-100'
                        }`}
                        title="Definir Dealer"
                      >
                        D
                      </button>
                      <div className="flex items-center gap-1">
                        <span className="px-1 py-0.2 rounded text-[9px] font-black bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">{pos}</span>
                        <span className="text-[11px] font-bold text-slate-200 truncate">{s.playerName}</span>
                      </div>
                      <span className="text-[11px] font-mono font-bold text-emerald-400">{s.isFolded ? 'Folded' : `${s.stackBb} BB`}</span>
                    </div>
                  );
                })()}

                {/* Seat 4 */}
                {(() => {
                  const s = seats[3];
                  const pos = computeSeatPosition(s.seatNumber);
                  const isDealer = s.seatNumber === dealerSeat;
                  return (
                    <div
                      onClick={() => setSelectedSeatNumber(s.seatNumber)}
                      className={`relative flex flex-col items-end px-2.5 py-1.5 rounded-xl border transition-all cursor-pointer max-w-[120px] ${
                        s.isFolded ? 'opacity-40 bg-slate-950 border-slate-900' :
                        selectedSeatNumber === s.seatNumber
                          ? 'bg-slate-900 border-amber-400 ring-2 ring-amber-400/40 shadow-lg'
                          : 'bg-slate-950/90 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDealerSeat(s.seatNumber);
                        }}
                        className={`absolute -top-2 -left-2 w-5 h-5 rounded-full font-black text-[10px] flex items-center justify-center border shadow transition-all cursor-pointer ${
                          isDealer
                            ? 'bg-amber-400 text-slate-950 border-amber-300 ring-2 ring-amber-400/50 scale-110'
                            : 'bg-slate-800 text-slate-400 border-slate-700 opacity-60 hover:opacity-100'
                        }`}
                        title="Definir Dealer"
                      >
                        D
                      </button>
                      <div className="flex items-center gap-1">
                        <span className="text-[11px] font-bold text-slate-200 truncate">{s.playerName}</span>
                        <span className="px-1 py-0.2 rounded text-[9px] font-black bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">{pos}</span>
                      </div>
                      <span className="text-[11px] font-mono font-bold text-emerald-400">{s.stackBb} BB</span>
                      {s.currentBetBb > 0 && <span className="text-[9px] font-mono text-amber-300">Bet: {s.currentBetBb} BB</span>}
                    </div>
                  );
                })()}
              </div>

              {/* SEAT 5: Bottom Center (Hero) */}
              <div className="relative z-10 flex justify-center mb-1">
                {(() => {
                  const s = seats[4];
                  const pos = computeSeatPosition(s.seatNumber);
                  const isDealer = s.seatNumber === dealerSeat;
                  return (
                    <div
                      onClick={() => setSelectedSeatNumber(s.seatNumber)}
                      className={`relative flex flex-col items-center px-4 py-2 rounded-2xl border-2 transition-all cursor-pointer shadow-xl ${
                        selectedSeatNumber === s.seatNumber
                          ? 'bg-slate-900 border-amber-400 ring-2 ring-amber-400/50 shadow-amber-400/20 scale-105'
                          : 'bg-slate-950 border-amber-500/60 hover:border-amber-400'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDealerSeat(s.seatNumber);
                        }}
                        className={`absolute -top-2.5 -right-2.5 w-6 h-6 rounded-full font-black text-xs flex items-center justify-center border shadow-md transition-all cursor-pointer ${
                          isDealer
                            ? 'bg-amber-400 text-slate-950 border-amber-300 ring-2 ring-amber-400/50 scale-110'
                            : 'bg-slate-800 text-slate-400 border-slate-700 opacity-60 hover:opacity-100'
                        }`}
                        title="Definir Dealer no Hero"
                      >
                        D
                      </button>

                      <div className="flex items-center gap-1.5">
                        <span className="px-2 py-0.5 rounded text-[10px] font-black bg-amber-500 text-slate-950 font-mono">
                          {pos}
                        </span>
                        <span className="text-xs font-bold text-amber-300">{s.playerName}</span>
                      </div>
                      <span className="text-sm font-mono font-black text-emerald-400">{s.stackBb} BB</span>
                      <span className="text-[10px] font-mono text-slate-400">SPR: {sprValue}</span>
                    </div>
                  );
                })()}
              </div>
            </div>

            {/* Quick Presets Bar */}
            <div className="pt-2 border-t border-slate-800 space-y-1.5">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Cenários Pré-Configurados Rápidos:
              </span>
              <div className="grid grid-cols-2 gap-1.5">
                {PRESET_NUMERICAL_SCENARIOS.map(scen => (
                  <button
                    key={scen.name}
                    onClick={() => applyScenario(scen)}
                    className="text-left p-2 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 transition-colors"
                  >
                    <div className="text-[11px] font-bold text-slate-200 truncate">{scen.name}</div>
                    <div className="text-[9px] text-slate-400 truncate">{scen.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Pot Odds & SPR Calculator + ROI Calibration (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          {/* Pot Odds & SPR Mathematical Engine */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider">
                  Calculadora de Pot Odds & SPR em Tempo Real
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-400">
                Hero: {heroPos} ({heroSeatData.stackBb} BB)
              </span>
            </div>

            {/* Metric Displays */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Pot Odds Card */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                    <Percent className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Pot Odds Necessário</span>
                  </span>
                  <span className="font-mono font-black text-cyan-300 text-lg">
                    {potOddsPercent}%
                  </span>
                </div>

                <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden border border-slate-800">
                  <div
                    className="bg-cyan-500 h-full rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(100, potOddsPercent * 2)}%` }}
                  />
                </div>

                <p className="text-[11px] text-slate-400 leading-snug">
                  Sua mão precisa ter no mínimo <strong>{potOddsPercent}%</strong> de equidade contra o range do vilão para o call ser lucrativo (+EV).
                </p>
              </div>

              {/* SPR Card */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                    <Coins className="w-3.5 h-3.5 text-amber-400" />
                    <span>Stack-to-Pot Ratio</span>
                  </span>
                  <span className="font-mono font-black text-amber-400 text-lg">
                    SPR {sprValue}
                  </span>
                </div>

                <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border ${sprInfo.badge}`}>
                  {sprInfo.cat}
                </span>

                <p className="text-[11px] text-slate-400 leading-snug">
                  {sprInfo.desc}
                </p>
              </div>
            </div>

            {/* Interactive Sizing Sliders for Testing */}
            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Pote Atual na Mesa (Pot BB):</span>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={1}
                    max={120}
                    step={0.5}
                    value={potBb}
                    onChange={(e) => setPotBb(Number(e.target.value))}
                    className="w-28 accent-emerald-500 cursor-pointer"
                  />
                  <strong className="text-emerald-400 font-bold w-14 text-right">{potBb} BB</strong>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-slate-400">Aposta Enfrentada (To Call BB):</span>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={0}
                    max={60}
                    step={0.5}
                    value={toCallBb}
                    onChange={(e) => setToCallBb(Number(e.target.value))}
                    className="w-28 accent-cyan-500 cursor-pointer"
                  />
                  <strong className="text-cyan-300 font-bold w-14 text-right">{toCallBb} BB</strong>
                </div>
              </div>
            </div>
          </div>

          {/* ROI Micro-Calibration for Selected Seat & Pot */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 font-sans">
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-emerald-400" />
                <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider">
                  Calibração de ROIs Numéricos: Assento #{selectedSeat.seatNumber}
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-400">
                {selectedSeat.playerName}
              </span>
            </div>

            {/* Pot ROI Micro-Tuner */}
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 font-bold">1. ROI Pote Total:</span>
                <span className="text-slate-400">[{potRoi.join(', ')}]</span>
              </div>
              <div className="grid grid-cols-4 gap-1.5 text-[11px]">
                <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                  <span className="text-slate-500">Y1: {potRoi[0]}</span>
                  <button onClick={() => adjustPotRoi(0, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                </div>
                <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                  <span className="text-slate-500">X1: {potRoi[1]}</span>
                  <button onClick={() => adjustPotRoi(1, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                </div>
                <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                  <span className="text-slate-500">Y2: {potRoi[2]}</span>
                  <button onClick={() => adjustPotRoi(2, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                </div>
                <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                  <span className="text-slate-500">X2: {potRoi[3]}</span>
                  <button onClick={() => adjustPotRoi(3, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                </div>
              </div>
            </div>

            {/* Selected Seat Stack ROI Micro-Tuner */}
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 font-bold">2. ROI Stack Seat #{selectedSeat.seatNumber}:</span>
                <span className="text-slate-400">[{selectedSeat.box.join(', ')}]</span>
              </div>
              <div className="grid grid-cols-4 gap-1.5 text-[11px]">
                <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                  <span className="text-slate-500">Y1: {selectedSeat.box[0]}</span>
                  <button onClick={() => adjustSeatRoi(selectedSeat.seatNumber, 0, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                </div>
                <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                  <span className="text-slate-500">X1: {selectedSeat.box[1]}</span>
                  <button onClick={() => adjustSeatRoi(selectedSeat.seatNumber, 1, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                </div>
                <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                  <span className="text-slate-500">Y2: {selectedSeat.box[2]}</span>
                  <button onClick={() => adjustSeatRoi(selectedSeat.seatNumber, 2, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                </div>
                <div className="p-1.5 rounded bg-slate-900 flex items-center justify-between">
                  <span className="text-slate-500">X2: {selectedSeat.box[3]}</span>
                  <button onClick={() => adjustSeatRoi(selectedSeat.seatNumber, 3, 2)} className="px-1 text-slate-300 hover:text-white">+</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
