import React, { useState, useEffect } from 'react';
import {
  Brain,
  Cpu,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  Sliders,
  Play,
  Pause,
  RotateCcw,
  Download,
  Upload,
  Copy,
  Check,
  Zap,
  Sparkles,
  ShieldAlert,
  ShieldCheck,
  Coins,
  Flame,
  ArrowRight,
  Info,
  Layers,
  Database,
  BarChart2,
  RefreshCw,
  SlidersHorizontal,
  ChevronRight,
  Search,
  Filter,
  ThumbsUp,
  ThumbsDown,
  GitCommit,
  GitBranch,
  Workflow,
  Target,
  MessageSquare,
  ArrowUpRight,
  Plus,
  Scale
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
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
import { LinesOfPlayEvAnalysis } from './LinesOfPlayEvAnalysis';
import { SessionErrorHistoryInspector } from './SessionErrorHistoryInspector';

// Types
export interface TournamentRangeProfile {
  id: string;
  name: string;
  category: string;
  stackBb: number;
  description: string;
  positions: {
    [pos: string]: string[]; // list of combo notations, e.g. ["AA", "KK", "AKs"]
  };
}

export interface MoneyLeakItem {
  id: string;
  name: string;
  street: 'PREFLOP' | 'FLOP' | 'TURN' | 'RIVER';
  category: string;
  sampleSize: number;
  lossBbPer100: number;
  totalLossBb: number;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'RESOLVED';
  rootCause: string;
  suggestedFix: string;
  appliedFix: boolean;
}

export interface ProfitableLineItem {
  id: string;
  name: string;
  street: 'PREFLOP' | 'FLOP' | 'TURN' | 'RIVER';
  sampleSize: number;
  winrateBbPer100: number;
  totalProfitBb: number;
  successRatePct: number;
  highlight: string;
}

export interface SitePerformance {
  siteName: string;
  gameTypes: string;
  handsCount: number;
  winrateBb100: number;
  allInEvBb100: number;
  roiPct: number;
  profitChips: number;
  verdict: string;
  status: 'EXCELLENT' | 'GOOD' | 'NEUTRAL' | 'WARNING';
}

export interface HumanFeedbackHand {
  id: string;
  timestamp: string;
  table: string;
  heroCards: string; // e.g. "A♠ K♥"
  combo: string; // "AKo"
  position: 'UTG' | 'MP' | 'CO' | 'BTN' | 'SB' | 'BB';
  profileKey: string;
  preflopAction: string;
  vsAction: string;
  heroResponse: string;
  potBb: number;
  outcomeBb: number;
  feedback?: 'CORRECT' | 'MISTAKE';
  correctionAction?: string;
  notes?: string;
  weightDelta?: number;
}

export interface PlayedHandDetail {
  handId: string;
  holeCards: string; // e.g. "A♠ K♥"
  combo: string; // "AKo"
  position: string; // "BTN", "BB", etc.
  board: string; // runout
  potSizeBb: number;
  outcomeBb: number;
  showdown: boolean;
  result: 'WIN' | 'LOSS';
}

export interface LineOfPlay {
  id: string;
  name: string;
  shortName: string;
  sequence: string[];
  category: 'AGGRESSIVE_IP' | 'DEFENSE_OOP' | 'POT_CONTROL' | '3BET_POT' | 'PASSIVE_STATION';
  categoryLabel: string;
  sampleSize: number;
  winrateBb100: number;
  allInEvBb100: number;
  evDiff: number;
  successRatePct: number;
  totalProfitBb: number;
  verdict: string;
  status: 'EXCELLENT' | 'GOOD' | 'CRITICAL';
  recommendation: string;
  playedHands?: PlayedHandDetail[];
}

const DEFAULT_RANGE_PROFILES: TournamentRangeProfile[] = [
  {
    id: 'mtt_deep_40bb',
    name: 'MTT Regular / Deepstack (40-60 BB)',
    category: 'MTT Freezeout',
    stackBb: 45,
    description: 'Ranges GTO com foco em realização de equidade pós-flop e sizings 2.2x-2.5x.',
    positions: {
      UTG: ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', 'AKs', 'AQs', 'AJs', 'ATs', 'KQs', 'KJs', 'AKo', 'AQo'],
      MP:  ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'KQs', 'KJs', 'KTs', 'QJs', 'AKo', 'AQo', 'AJo'],
      CO:  ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A8s', 'A5s', 'A4s', 'KQs', 'KJs', 'KTs', 'QJs', 'QTs', 'JTs', 'T9s', 'AKo', 'AQo', 'AJo', 'ATo', 'KQo'],
      BTN: ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', '55', '44', '33', '22', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A8s', 'A7s', 'A6s', 'A5s', 'A4s', 'A3s', 'A2s', 'KQs', 'KJs', 'KTs', 'K9s', 'QJs', 'QTs', 'Q9s', 'JTs', 'J9s', 'T9s', 'T8s', '98s', '87s', '76s', '65s', 'AKo', 'AQo', 'AJo', 'ATo', 'A9o', 'KQo', 'KJo', 'KTo', 'QJo', 'QTo', 'JTo'],
      SB:  ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', '55', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A8s', 'A5s', 'A4s', 'A3s', 'KQs', 'KJs', 'KTs', 'QJs', 'QTs', 'JTs', 'T9s', 'AKo', 'AQo', 'AJo', 'ATo', 'KQo', 'KJo']
    }
  },
  {
    id: 'pko_bounty_25bb',
    name: 'PKO Bounty / Progressive Knockout (25 BB)',
    category: 'PKO Bounty',
    stackBb: 25,
    description: 'Ranges matematicamente estendidos para cobrir stacks menores e caçar bounties.',
    positions: {
      UTG: ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', 'AKs', 'AQs', 'AJs', 'ATs', 'KQs', 'AKo', 'AQo'],
      MP:  ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A5s', 'KQs', 'KJs', 'AKo', 'AQo', 'AJo'],
      CO:  ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', '55', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A8s', 'A7s', 'A5s', 'A4s', 'KQs', 'KJs', 'KTs', 'QJs', 'QTs', 'JTs', 'AKo', 'AQo', 'AJo', 'ATo', 'KQo', 'KJo'],
      BTN: ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', '55', '44', '33', '22', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A8s', 'A7s', 'A6s', 'A5s', 'A4s', 'A3s', 'A2s', 'KQs', 'KJs', 'KTs', 'K9s', 'K8s', 'QJs', 'QTs', 'Q9s', 'JTs', 'J9s', 'T9s', '98s', '87s', 'AKo', 'AQo', 'AJo', 'ATo', 'A9o', 'A8o', 'KQo', 'KJo', 'KTo', 'QJo', 'QTo', 'JTo', 'T9o'],
      SB:  ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A5s', 'A4s', 'KQs', 'KJs', 'QJs', 'AKo', 'AQo', 'AJo', 'KQo']
    }
  },
  {
    id: 'turbo_15bb_push_fold',
    name: 'Turbo / Short Stack (12-15 BB Push/Fold)',
    category: 'Turbo / Hyper',
    stackBb: 14,
    description: 'Equilíbrio de Nash estrito para All-in direto e re-steals lucrativos.',
    positions: {
      UTG: ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', 'AKs', 'AQs', 'AJs', 'ATs', 'AKo', 'AQo'],
      MP:  ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', 'AKs', 'AQs', 'AJs', 'ATs', 'KQs', 'AKo', 'AQo', 'AJo'],
      CO:  ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', '55', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A8s', 'A5s', 'KQs', 'KJs', 'QJs', 'AKo', 'AQo', 'AJo', 'ATo', 'KQo'],
      BTN: ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', '55', '44', '33', '22', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A8s', 'A7s', 'A6s', 'A5s', 'A4s', 'A3s', 'A2s', 'KQs', 'KJs', 'KTs', 'K9s', 'QJs', 'QTs', 'JTs', 'T9s', '98s', 'AKo', 'AQo', 'AJo', 'ATo', 'A9o', 'A8o', 'KQo', 'KJo', 'KTo', 'QJo'],
      SB:  ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', '55', '44', '33', '22', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A8s', 'A7s', 'A6s', 'A5s', 'A4s', 'A3s', 'A2s', 'KQs', 'KJs', 'KTs', 'K9s', 'K8s', 'QJs', 'QTs', 'Q9s', 'JTs', 'J9s', 'T9s', '98s', '87s', 'AKo', 'AQo', 'AJo', 'ATo', 'A9o', 'A8o', 'A7o', 'A5o', 'KQo', 'KJo', 'KTo', 'QJo', 'QTo', 'JTo']
    }
  }
];

const INITIAL_HANDS_FOR_FEEDBACK: HumanFeedbackHand[] = [
  {
    id: 'hand_10482',
    timestamp: '13:35:10',
    table: 'PPPoker Mesa #1 (Diamante)',
    heroCards: 'A♠ K♥',
    combo: 'AKo',
    position: 'BTN',
    profileKey: 'mtt_deep_40bb',
    preflopAction: 'Open Raise 2.2x',
    vsAction: 'SB 3-Bet Shove 18.0 BB',
    heroResponse: 'Call Shove 18.0 BB',
    potBb: 37.5,
    outcomeBb: +19.5,
    feedback: 'CORRECT',
    notes: 'Call 100% GTO com AKo vs shove de 18 BB do SB.',
    weightDelta: +0.10
  },
  {
    id: 'hand_10481',
    timestamp: '13:32:44',
    table: 'PPPoker Mesa #2 (Rubi)',
    heroCards: 'K♦ Q♠',
    combo: 'KQo',
    position: 'SB',
    profileKey: 'mtt_deep_40bb',
    preflopAction: 'Open Limp 1.0 BB',
    vsAction: 'BB Raise 3.5 BB',
    heroResponse: 'Call 2.5 BB',
    potBb: 7.0,
    outcomeBb: -3.5,
    feedback: 'MISTAKE',
    correctionAction: 'Deveria ter feito Open Raise 3.0x ou Fold (Limp é -EV)',
    notes: 'Completar no SB deu odds perfeitas ao BB para punir fora de posição.',
    weightDelta: -0.25
  },
  {
    id: 'hand_10480',
    timestamp: '13:28:15',
    table: 'PPPoker Mesa #3 (Esmeralda)',
    heroCards: '8♣ 7♣',
    combo: '87s',
    position: 'CO',
    profileKey: 'mtt_deep_40bb',
    preflopAction: 'Open Raise 2.0x',
    vsAction: 'BTN 3-Bet 6.5 BB',
    heroResponse: 'Fold',
    potBb: 9.5,
    outcomeBb: -2.0,
    feedback: 'CORRECT',
    notes: 'Fold disciplinado OOP contra 3-bet sem odds para spec play.',
    weightDelta: +0.05
  },
  {
    id: 'hand_10479',
    timestamp: '13:22:05',
    table: 'PPPoker Mesa #1 (Diamante)',
    heroCards: 'K♠ J♦',
    combo: 'KJo',
    position: 'MP',
    profileKey: 'mtt_deep_40bb',
    preflopAction: 'Open Raise 2.2x',
    vsAction: 'CO 3-Bet 7.0 BB',
    heroResponse: 'Call 4.8 BB',
    potBb: 15.5,
    outcomeBb: -7.0,
    feedback: 'MISTAKE',
    correctionAction: 'Deveria ter Foldado imediatamente contra 3-Bet em posição intermediária',
    notes: 'Call dominado com KJo fora de posição; leak grave.',
    weightDelta: -0.30
  },
  {
    id: 'hand_10478',
    timestamp: '13:18:40',
    table: 'PPPoker Mesa #4 (Safira)',
    heroCards: 'A♦ 5♦',
    combo: 'A5s',
    position: 'BTN',
    profileKey: 'pko_bounty_25bb',
    preflopAction: 'Open Raise 2.2x',
    vsAction: 'BB 3-Bet 8.0 BB',
    heroResponse: '4-Bet Shove 24.5 BB (All-in)',
    potBb: 33.5,
    outcomeBb: +9.0,
    feedback: undefined, // Pendente de avaliação
    notes: '4-Bet Bluff Shove de A5s com blockers de Ás contra blind agressivo.',
    weightDelta: 0
  }
];

const INITIAL_LINES_OF_PLAY: LineOfPlay[] = [
  {
    id: 'line_01',
    name: 'Open-Raise BTN -> C-Bet Flop -> 2nd Barrel Turn -> Value Bet River',
    shortName: 'RFI BTN -> 3x Barrel IP',
    sequence: ['RFI BTN (2.2x)', 'C-Bet Flop (33%)', 'Barrel Turn (65%)', 'Value River (75%)'],
    category: 'AGGRESSIVE_IP',
    categoryLabel: 'Agressiva em Posição (Triplo Barril)',
    sampleSize: 348,
    winrateBb100: +84.5,
    allInEvBb100: +88.2,
    evDiff: -3.7,
    successRatePct: 74.5,
    totalProfitBb: +294.0,
    verdict: 'MÁXIMO VALOR (+84.5 bb/100)',
    status: 'EXCELLENT',
    recommendation: 'Manter alta frequência de exploração. Linha de maior extração de fichas contra ranges passivos do field.',
    playedHands: [
      { handId: 'hand_10482', holeCards: 'A♠ K♥', combo: 'AKo', position: 'BTN', board: 'A♦ 8♣ 4♠ T♦ 2♥', potSizeBb: 37.5, outcomeBb: +19.5, showdown: true, result: 'WIN' },
      { handId: 'hand_10465', holeCards: 'K♠ Q♠', combo: 'KQs', position: 'BTN', board: 'K♦ 7♣ 2♠ 9♥ 4♦', potSizeBb: 42.0, outcomeBb: +24.0, showdown: true, result: 'WIN' },
      { handId: 'hand_10440', holeCards: 'A♣ J♣', combo: 'AJs', position: 'BTN', board: 'A♥ T♠ 3♦ 6♣ 8♠', potSizeBb: 31.0, outcomeBb: +16.5, showdown: false, result: 'WIN' }
    ]
  },
  {
    id: 'line_02',
    name: 'Defesa de Big Blind (BB) -> Check-Call Flop -> Check-Raise Turn',
    shortName: 'BB Def -> C/C Flop -> C/R Turn',
    sequence: ['BB Defense', 'Check-Call Flop', 'Check-Raise Turn (2.8x)'],
    category: 'DEFENSE_OOP',
    categoryLabel: 'Defesa Fora de Posição (Check-Raise)',
    sampleSize: 215,
    winrateBb100: +58.2,
    allInEvBb100: +54.0,
    evDiff: +4.2,
    successRatePct: 68.0,
    totalProfitBb: +125.1,
    verdict: 'VALOR SÓLIDO GTO (+58.2 bb/100)',
    status: 'EXCELLENT',
    recommendation: 'Excelente linha de contra-ataque. Punição severa de vilões que abusam de c-bet e dão check-behind no turn.',
    playedHands: [
      { handId: 'hand_10455', holeCards: '9♥ 8♥', combo: '98s', position: 'BB', board: 'T♦ 7♠ 2♣ J♥ 3♠', potSizeBb: 28.5, outcomeBb: +18.0, showdown: false, result: 'WIN' },
      { handId: 'hand_10432', holeCards: 'A♦ 4♦', combo: 'A4s', position: 'BB', board: '4♠ 4♥ K♣ 9♦ 2♥', potSizeBb: 34.0, outcomeBb: +21.5, showdown: true, result: 'WIN' }
    ]
  },
  {
    id: 'line_03',
    name: '3-Bet Shove Pré-Flop no Botão (BTN) vs Open do Cutoff (CO)',
    shortName: '3-Bet Shove BTN vs CO',
    sequence: ['Facing CO Open', '3-Bet Shove BTN (18-24 BB)'],
    category: '3BET_POT',
    categoryLabel: 'Re-Steal / Push Pré-Flop',
    sampleSize: 412,
    winrateBb100: +74.2,
    allInEvBb100: +72.0,
    evDiff: +2.2,
    successRatePct: 78.4,
    totalProfitBb: +305.7,
    verdict: 'ALTO RETORNO / FOLD EQUITY (+74.2 bb/100)',
    status: 'EXCELLENT',
    recommendation: 'Aproveita o range de abertura excessivamente largo do CO em torneios e satélites.',
    playedHands: [
      { handId: 'hand_10470', holeCards: 'A♠ Q♠', combo: 'AQs', position: 'BTN', board: 'Fold Pré-Flop (Sem Board)', potSizeBb: 7.5, outcomeBb: +4.5, showdown: false, result: 'WIN' },
      { handId: 'hand_10450', holeCards: 'T♣ T♦', combo: 'TT', position: 'BTN', board: 'J♠ 9♦ 4♣ 2♥ 5♠', potSizeBb: 45.0, outcomeBb: +22.5, showdown: true, result: 'WIN' },
      { handId: 'hand_10425', holeCards: 'A♥ 5♥', combo: 'A5s', position: 'BTN', board: 'Fold Pré-Flop (Sem Board)', potSizeBb: 6.5, outcomeBb: +3.5, showdown: false, result: 'WIN' }
    ]
  },
  {
    id: 'line_04',
    name: 'Open-Raise CO -> C-Bet Flop -> Check-Behind Turn -> River Bluff-Catch',
    shortName: 'RFI CO -> C-Bet -> Ck Turn -> Catch River',
    sequence: ['RFI CO (2.2x)', 'C-Bet Flop (33%)', 'Check-Behind Turn', 'River Call (Bluff-Catch)'],
    category: 'POT_CONTROL',
    categoryLabel: 'Controle de Pote com Catcher Marginal',
    sampleSize: 182,
    winrateBb100: +12.4,
    allInEvBb100: +15.1,
    evDiff: -2.7,
    successRatePct: 52.8,
    totalProfitBb: +22.5,
    verdict: 'MARGEM MODERADA (+12.4 bb/100)',
    status: 'GOOD',
    recommendation: 'Efetivo apenas quando o vilão demonstrar propensão a probe-bet agressivo no river.',
    playedHands: [
      { handId: 'hand_10438', holeCards: 'K♦ T♦', combo: 'KTs', position: 'CO', board: 'K♠ 8♣ 3♦ 7♥ 2♠', potSizeBb: 19.5, outcomeBb: +7.5, showdown: true, result: 'WIN' },
      { handId: 'hand_10420', holeCards: 'Q♥ J♥', combo: 'QJs', position: 'CO', board: 'A♦ Q♠ 4♣ 9♦ 6♥', potSizeBb: 22.0, outcomeBb: -9.0, showdown: true, result: 'LOSS' }
    ]
  },
  {
    id: 'line_05',
    name: 'Call 3-Bet Fora de Posição (OOP) -> Check-Fold Flop',
    shortName: 'Call 3-Bet OOP -> Check-Fold Flop',
    sequence: ['Open-Raise OOP', 'Facing 3-Bet', 'Call 3-Bet OOP', 'Check-Fold Flop'],
    category: 'PASSIVE_STATION',
    categoryLabel: 'Passiva Negativa OOP',
    sampleSize: 240,
    winrateBb100: -64.8,
    allInEvBb100: -62.0,
    evDiff: -2.8,
    successRatePct: 18.2,
    totalProfitBb: -155.5,
    verdict: 'LEAK CRÍTICO / DRENO (-64.8 bb/100)',
    status: 'CRITICAL',
    recommendation: 'Eliminar call 3-bet OOP com broadways offsuit. Substituir por 4-Bet Shove ou Fold direto.',
    playedHands: [
      { handId: 'hand_10479', holeCards: 'K♠ J♦', combo: 'KJo', position: 'MP', board: 'A♠ 8♦ 2♣ (Check-Fold)', potSizeBb: 15.5, outcomeBb: -7.0, showdown: false, result: 'LOSS' },
      { handId: 'hand_10461', holeCards: 'Q♠ T♠', combo: 'QTs', position: 'SB', board: 'K♥ 9♦ 3♣ (Check-Fold)', potSizeBb: 16.0, outcomeBb: -6.5, showdown: false, result: 'LOSS' }
    ]
  },
  {
    id: 'line_06',
    name: 'Check-Call Flop -> Check-Call Turn -> Check-Fold River',
    shortName: 'Check-Call Flop/Turn -> Fold River',
    sequence: ['Check-Call Flop', 'Check-Call Turn', 'Check-Fold River'],
    category: 'PASSIVE_STATION',
    categoryLabel: 'Linha Estação de Call Desfavorável',
    sampleSize: 164,
    winrateBb100: -48.2,
    allInEvBb100: -45.0,
    evDiff: -3.2,
    successRatePct: 24.1,
    totalProfitBb: -79.0,
    verdict: 'PREJUÍZO ACUMULADO (-48.2 bb/100)',
    status: 'CRITICAL',
    recommendation: 'Foldar já no turn quando o oponente demonstrar agressão tripla sem projeto de flush/straight sólido.',
    playedHands: [
      { handId: 'hand_10444', holeCards: 'A♣ 3♣', combo: 'A3s', position: 'BB', board: 'T♠ 8♥ 3♦ K♦ Q♠', potSizeBb: 26.5, outcomeBb: -11.0, showdown: false, result: 'LOSS' },
      { handId: 'hand_10412', holeCards: '7♦ 6♦', combo: '76s', position: 'BB', board: '9♣ 5♠ 2♥ J♦ A♠', potSizeBb: 24.0, outcomeBb: -9.5, showdown: false, result: 'LOSS' }
    ]
  }
];

const INITIAL_LEAKS: MoneyLeakItem[] = [
  {
    id: 'leak_01',
    name: 'Call 3-Bet Fora de Posição (OOP) com Broadways Offsuit',
    street: 'PREFLOP',
    category: 'PREFLOP_CALL_3BET',
    sampleSize: 284,
    lossBbPer100: -48.5,
    totalLossBb: -137.7,
    severity: 'CRITICAL',
    rootCause: 'Pagar 3-bet no SB ou MP com KJo, QJo e ATo resulta em dominância severa e realização de equidade < 62% pós-flop.',
    suggestedFix: 'Zerar frequência de call com broadways offsuit OOP; transformar mãos suited em 4-bet bluff e foldar offsuits.',
    appliedFix: false
  },
  {
    id: 'leak_02',
    name: 'C-Bet no Flop em Pote Multi-Way sem Equidade (Dry Air)',
    street: 'FLOP',
    category: 'POSTFLOP_CBET_MULTIWAY',
    sampleSize: 192,
    lossBbPer100: -36.2,
    totalLossBb: -69.5,
    severity: 'HIGH',
    rootCause: 'Apostar c-bet contra 2 ou mais vilões em bordos dinâmicos sem draws. A frequência de fold acumulado dos 2 vilões é de apenas 21%.',
    suggestedFix: 'Restringir c-bet multi-way a valor sólido (top pair com bom kicker+) e projetos com 8+ outs reais.',
    appliedFix: false
  },
  {
    id: 'leak_03',
    name: 'Check-Call Triplo no River com Par Médio / Catchers Marginais',
    street: 'RIVER',
    category: 'RIVER_BLUFF_CATCH',
    sampleSize: 145,
    lossBbPer100: -29.8,
    totalLossBb: -43.2,
    severity: 'MEDIUM',
    rootCause: 'O field médio do PPPoker sub-blefa o 3º barril no river em mais de 70%. Pagar com 2º par é EV negativo contra este perfil.',
    suggestedFix: 'Over-foldar no river contra apostas pesadas de vilões passivos sem histórico de blefe comprovado.',
    appliedFix: false
  },
  {
    id: 'leak_04',
    name: 'Open Limp do Small Blind com Mãos Marginais (SB Complete)',
    street: 'PREFLOP',
    category: 'PREFLOP_SB_STRATEGY',
    sampleSize: 110,
    lossBbPer100: -22.4,
    totalLossBb: -24.6,
    severity: 'MEDIUM',
    rootCause: 'Completar o blind dá odds perfeitas para o Big Blind dar raise agressivo (isolamento) com vantagem posicional.',
    suggestedFix: 'Adotar estratégia polarizada no SB: Raise 3.0x ou Fold, eliminando a linha passiva de limp.',
    appliedFix: false
  }
];

const INITIAL_PROFITABLE_LINES: ProfitableLineItem[] = [
  {
    id: 'profit_01',
    name: '3-Bet Shove no Botão (BTN) vs Open do Cutoff (CO)',
    street: 'PREFLOP',
    sampleSize: 412,
    winrateBbPer100: +74.2,
    totalProfitBb: +305.7,
    successRatePct: 78.4,
    highlight: 'Extração máxima de fold equity e fichas mortas no pote com stacks de 18-25 BB enfrentando opens largos do CO.'
  },
  {
    id: 'profit_02',
    name: 'C-Bet Pequena (33% Pot) em Bordos Desconectados / Secos com Ás ou Rei',
    street: 'FLOP',
    sampleSize: 680,
    winrateBbPer100: +52.1,
    totalProfitBb: +354.3,
    successRatePct: 69.2,
    highlight: 'Excelente risco-retorno. Gera fold imediato de ranges marginais do big blind investindo pouco.'
  },
  {
    id: 'profit_03',
    name: 'Delay C-Bet no Turn após Check-Check no Flop em Posição (IP)',
    street: 'TURN',
    sampleSize: 320,
    winrateBbPer100: +44.8,
    totalProfitBb: +143.4,
    successRatePct: 64.5,
    highlight: 'Punição imediata do range de check fraco do vilão no turn ao perceber fraqueza confirmada.'
  },
  {
    id: 'profit_04',
    name: 'Isolamento de Limpers com Mãos Premium em Posição Tardia',
    street: 'PREFLOP',
    sampleSize: 260,
    winrateBbPer100: +61.5,
    totalProfitBb: +159.9,
    successRatePct: 72.0,
    highlight: 'Gera potes inflados heads-up contra jogadores recreativos com ranges amplos e dominados.'
  }
];

const INITIAL_SITE_PERFORMANCE: SitePerformance[] = [
  {
    siteName: 'PPPoker (Clube Diamante)',
    gameTypes: 'MTT PKO / Freezeout',
    handsCount: 58420,
    winrateBb100: +11.8,
    allInEvBb100: +13.2,
    roiPct: 34.5,
    profitChips: 84200.0,
    verdict: 'ALTAMENTE LUCRATIVO',
    status: 'EXCELLENT'
  },
  {
    siteName: 'PPPoker (Liga Suprema)',
    gameTypes: 'Cash Game 6-Max',
    handsCount: 42100,
    winrateBb100: +8.4,
    allInEvBb100: +9.1,
    roiPct: 22.0,
    profitChips: 35400.0,
    verdict: 'LUCRATIVO COM BOA MARGEM',
    status: 'GOOD'
  },
  {
    siteName: 'ClubGG / Upoker',
    gameTypes: 'PKO Mystery Bounty',
    handsCount: 13430,
    winrateBb100: +14.6,
    allInEvBb100: +15.4,
    roiPct: 42.1,
    profitChips: 58200.0,
    verdict: 'EXTREMAMENTE LUCRATIVO (FIELD SOFT)',
    status: 'EXCELLENT'
  },
  {
    siteName: 'PokerStars (MTT Micro/Low)',
    gameTypes: 'Turbo MTT',
    handsCount: 28900,
    winrateBb100: +4.2,
    allInEvBb100: +5.8,
    roiPct: 14.8,
    profitChips: 12150.0,
    verdict: 'COMPETITIVO (GTO ESTREITO)',
    status: 'NEUTRAL'
  }
];

const EVOLUTION_GRAPH_DATA = [
  { session: 'Sessão 1', actualBb100: 3.2, evBb100: 4.1, trainingLoss: 1.82 },
  { session: 'Sessão 2', actualBb100: 2.8, evBb100: 4.9, trainingLoss: 1.54 },
  { session: 'Sessão 3', actualBb100: 5.4, evBb100: 6.2, trainingLoss: 1.25 },
  { session: 'Sessão 4', actualBb100: 4.9, evBb100: 7.0, trainingLoss: 0.98 },
  { session: 'Sessão 5', actualBb100: 7.2, evBb100: 8.4, trainingLoss: 0.74 },
  { session: 'Sessão 6', actualBb100: 8.6, evBb100: 9.8, trainingLoss: 0.58 },
  { session: 'Sessão 7', actualBb100: 8.1, evBb100: 10.5, trainingLoss: 0.45 },
  { session: 'Sessão 8', actualBb100: 9.4, evBb100: 11.8, trainingLoss: 0.34 }
];

export const BotBrainEvolutionInspector: React.FC<{
  onNotify?: (title: string, message: string, severity: 'INFO' | 'WARN' | 'CRITICAL') => void;
}> = ({ onNotify }) => {
  const [activeSubTab, setActiveSubTab] = useState<'overview' | 'human_feedback' | 'lines_of_play' | 'preflop_feeder' | 'leak_finder' | 'site_analytics' | 'postflop_adaptive'>('overview');

  // Brain State
  const [modelVersion, setModelVersion] = useState<string>('Neural Brain v2.4 (Evolutivo)');
  const [totalHandsAnalyzed, setTotalHandsAnalyzed] = useState<number>(142850);
  const [globalWinrate, setGlobalWinrate] = useState<number>(9.4);
  const [convergenceRate, setConvergenceRate] = useState<number>(96.4);
  const [epochsCount, setEpochsCount] = useState<number>(420);

  // Training & Learning Rate Weights Configuration
  const [isTraining, setIsTraining] = useState<boolean>(false);
  const [trainingProgress, setTrainingProgress] = useState<number>(0);
  const [trainingEpochsTarget, setTrainingEpochsTarget] = useState<number>(50);
  const [learningRate, setLearningRate] = useState<number>(0.08);
  const [feedbackWeightCorrect, setFeedbackWeightCorrect] = useState<number>(0.12);
  const [feedbackWeightMistake, setFeedbackWeightMistake] = useState<number>(-0.28);
  const [postflopInfluenceMultiplier, setPostflopInfluenceMultiplier] = useState<number>(1.8);
  const [momentumDamping, setMomentumDamping] = useState<number>(0.90);
  const [learningPreset, setLearningPreset] = useState<'CONSERVATIVE' | 'BALANCED' | 'AGGRESSIVE'>('BALANCED');

  // Range Feeder State
  const [rangeProfiles, setRangeProfiles] = useState<TournamentRangeProfile[]>(DEFAULT_RANGE_PROFILES);
  const [selectedProfileId, setSelectedProfileId] = useState<string>('mtt_deep_40bb');
  const [selectedPosition, setSelectedPosition] = useState<string>('BTN');
  const [importJsonText, setImportJsonText] = useState<string>('');
  const [showImportModal, setShowImportModal] = useState<boolean>(false);
  const [copiedProfileJson, setCopiedProfileJson] = useState<boolean>(false);

  // Human Feedback State
  const [feedbackHands, setFeedbackHands] = useState<HumanFeedbackHand[]>(INITIAL_HANDS_FOR_FEEDBACK);
  const [selectedHandForModal, setSelectedHandForModal] = useState<HumanFeedbackHand | null>(null);
  const [correctionNoteInput, setCorrectionNoteInput] = useState<string>('');
  const [correctionActionInput, setCorrectionActionInput] = useState<string>('Fold');

  // Lines of Play State
  const [linesOfPlay, setLinesOfPlay] = useState<LineOfPlay[]>(INITIAL_LINES_OF_PLAY);
  const [lineCategoryFilter, setLineCategoryFilter] = useState<'ALL' | 'PROFITABLE' | 'UNPROFITABLE' | 'AGGRESSIVE_IP' | 'DEFENSE_OOP' | '3BET_POT'>('ALL');
  const [showExportLinesModal, setShowExportLinesModal] = useState<boolean>(false);
  const [exportedLinesJson, setExportedLinesJson] = useState<string>('');
  const [copiedExportJson, setCopiedExportJson] = useState<boolean>(false);
  const [expandedLineHandId, setExpandedLineHandId] = useState<string | null>(null);

  // Leaks & Profitable Lines State
  const [leaks, setLeaks] = useState<MoneyLeakItem[]>(INITIAL_LEAKS);
  const [profitableLines, setProfitableLines] = useState<ProfitableLineItem[]>(INITIAL_PROFITABLE_LINES);
  const [siteAnalytics, setSiteAnalytics] = useState<SitePerformance[]>(INITIAL_SITE_PERFORMANCE);

  // Postflop Adaptive Weights
  const [postflopWeights, setPostflopWeights] = useState({
    cbetDryIp: 72,
    cbetWetIp: 44,
    cbetMultiway: 22,
    turnBarrelBluff: 38,
    riverBluffCatch: 32,
    checkRaiseFlop: 14
  });

  // Helper to render 4-color cards
  const render4ColorCard = (cardStr: string) => {
    const parts = cardStr.trim().split(' ');
    return (
      <div className="inline-flex items-center gap-1">
        {parts.map((c, i) => {
          const rank = c.slice(0, -1);
          const suit = c.slice(-1);
          const suitStyle =
            suit === '♠' ? 'text-slate-100 bg-slate-900 border-slate-700 shadow-sm' :
            suit === '♥' ? 'text-rose-400 bg-rose-950/60 border-rose-800 shadow-sm' :
            suit === '♦' ? 'text-blue-400 bg-blue-950/60 border-blue-800 shadow-sm' :
            'text-emerald-400 bg-emerald-950/60 border-emerald-800 shadow-sm';

          return (
            <span
              key={i}
              className={`inline-flex items-center justify-center px-1.5 py-0.5 rounded text-xs font-mono font-black border ${suitStyle}`}
            >
              <span>{rank}</span>
              <span className="ml-0.5">{suit}</span>
            </span>
          );
        })}
      </div>
    );
  };

  // Preset switcher for Learning Rate
  const applyLearningPreset = (preset: 'CONSERVATIVE' | 'BALANCED' | 'AGGRESSIVE') => {
    setLearningPreset(preset);
    if (preset === 'CONSERVATIVE') {
      setLearningRate(0.03);
      setFeedbackWeightCorrect(0.06);
      setFeedbackWeightMistake(-0.15);
      setPostflopInfluenceMultiplier(1.2);
      setMomentumDamping(0.95);
      onNotify?.("PRESET CONSERVADOR ATIVADO", "Learning Rate definida para 0.03 (GTO Estrito com evolução lenta e segura).", "INFO");
    } else if (preset === 'BALANCED') {
      setLearningRate(0.08);
      setFeedbackWeightCorrect(0.12);
      setFeedbackWeightMistake(-0.28);
      setPostflopInfluenceMultiplier(1.8);
      setMomentumDamping(0.90);
      onNotify?.("PRESET EQUILIBRADO ATIVADO", "Learning Rate definida para 0.08 (Equilíbrio entre GTO e adaptação humana).", "INFO");
    } else {
      setLearningRate(0.16);
      setFeedbackWeightCorrect(0.22);
      setFeedbackWeightMistake(-0.45);
      setPostflopInfluenceMultiplier(3.0);
      setMomentumDamping(0.80);
      onNotify?.("PRESET AGRESSIVO ATIVADO", "Learning Rate definida para 0.16 (Adaptação rápida a exploits do field).", "WARN");
    }
  };

  // Human Feedback Handler: Acerto
  const handleRateHandCorrect = (handId: string) => {
    const calculatedDelta = Number((feedbackWeightCorrect * (learningRate / 0.08)).toFixed(2));

    setFeedbackHands(prev =>
      prev.map(h => {
        if (h.id === handId) {
          return {
            ...h,
            feedback: 'CORRECT',
            weightDelta: calculatedDelta,
            notes: h.notes || `Decisão humana: jogada correta (+EV). Peso reforçado com Learning Rate ${learningRate}.`
          };
        }
        return h;
      })
    );

    // Ajusta também pesos pós-flop suavemente
    setPostflopWeights(prev => ({
      ...prev,
      cbetDryIp: Math.min(90, Number((prev.cbetDryIp + 0.5 * postflopInfluenceMultiplier).toFixed(1)))
    }));

    const target = feedbackHands.find(h => h.id === handId);
    onNotify?.(
      "ACERTO CONFIRMADO",
      `Mão ${target?.combo} em ${target?.position}: Decisão aprovada! Frequência e peso pré-flop reforçados em +${calculatedDelta} (LR: ${learningRate}).`,
      "INFO"
    );
  };

  // Human Feedback Handler: Erro
  const handleRateHandMistake = (handId: string, customCorrection?: string, customNote?: string) => {
    const calculatedDelta = Number((feedbackWeightMistake * (learningRate / 0.08)).toFixed(2));

    setFeedbackHands(prev =>
      prev.map(h => {
        if (h.id === handId) {
          return {
            ...h,
            feedback: 'MISTAKE',
            correctionAction: customCorrection || 'Deveria ter feito Fold imediatamente',
            weightDelta: calculatedDelta,
            notes: customNote || `Decisão humana: erro tático (-EV). Frequência penalizada com Learning Rate ${learningRate}.`
          };
        }
        return h;
      })
    );

    // Ajuste pós-flop corretivo
    setPostflopWeights(prev => ({
      ...prev,
      cbetMultiway: Math.max(10, Number((prev.cbetMultiway - 1.0 * postflopInfluenceMultiplier).toFixed(1))),
      riverBluffCatch: Math.max(15, Number((prev.riverBluffCatch - 1.0 * postflopInfluenceMultiplier).toFixed(1)))
    }));

    const target = feedbackHands.find(h => h.id === handId);
    setSelectedHandForModal(null);
    onNotify?.(
      "ERRO REGISTRADO & PESO AJUSTADO",
      `Mão ${target?.combo} em ${target?.position}: Falha registrada! O cérebro reduziu o peso desta ação (${calculatedDelta}) com Learning Rate ${learningRate}.`,
      "WARN"
    );
  };

  // Simulate New Hand for Feedback
  const handleSimulateNewHand = () => {
    const sampleCombos = [
      { cards: 'A♣ 5♣', combo: 'A5s', pos: 'BTN', pre: 'Open Raise 2.2x', vs: 'BB 3-Bet 8.5 BB', resp: 'Call 6.3 BB', pot: 17.5, out: -8.5 },
      { cards: 'Q♠ J♠', combo: 'QJs', pos: 'CO', pre: 'Open Raise 2.0x', vs: 'BTN Flat Call', resp: 'C-Bet 2.2 BB Flop', pot: 9.0, out: +4.5 },
      { cards: '9♥ 9♦', combo: '99', pos: 'MP', pre: 'Open Raise 2.2x', vs: 'CO 3-Bet Shove 15.0 BB', resp: 'Call 12.8 BB', pot: 32.0, out: +17.0 },
      { cards: 'A♠ T♥', combo: 'ATo', pos: 'SB', pre: 'Open Limp 1.0 BB', vs: 'BB Raise 3.5 BB', resp: 'Fold', pot: 4.5, out: -1.0 }
    ];
    const picked = sampleCombos[Math.floor(Math.random() * sampleCombos.length)];
    const newHand: HumanFeedbackHand = {
      id: `hand_${Date.now().toString().slice(-5)}`,
      timestamp: new Date().toLocaleTimeString('pt-BR'),
      table: 'PPPoker Mesa #1 (Diamante)',
      heroCards: picked.cards,
      combo: picked.combo,
      position: picked.pos as any,
      profileKey: selectedProfileId,
      preflopAction: picked.pre,
      vsAction: picked.vs,
      heroResponse: picked.resp,
      potBb: picked.pot,
      outcomeBb: picked.out,
      feedback: undefined,
      weightDelta: 0
    };

    setFeedbackHands(prev => [newHand, ...prev]);
    onNotify?.("NOVA MÃO PARA AUDITORIA", `Mão ${picked.combo} (${picked.pos}) adicionada para receber seu feedback humano.`, "INFO");
  };

  // Training Loop Handler
  const handleStartTrainingCycle = () => {
    setIsTraining(true);
    setTrainingProgress(0);
    onNotify?.("TREINAMENTO INICIADO", `Executando ciclo de ${trainingEpochsTarget} épocas com retroalimentação de EV (+${learningRate} taxa de aprendizado).`, "INFO");

    let progress = 0;
    const interval = setInterval(() => {
      progress += 20;
      setTrainingProgress(progress);

      if (progress >= 100) {
        clearInterval(interval);
        setIsTraining(false);
        setEpochsCount(prev => prev + trainingEpochsTarget);
        setGlobalWinrate(prev => Number((prev + 0.6).toFixed(1)));
        setConvergenceRate(prev => Math.min(99.2, Number((prev + 0.8).toFixed(1))));
        setTotalHandsAnalyzed(prev => prev + trainingEpochsTarget * 120);

        // Auto-refine postflop weights based on training feedback
        setPostflopWeights(prev => ({
          ...prev,
          cbetDryIp: Math.min(85, prev.cbetDryIp + 2),
          cbetMultiway: Math.max(12, prev.cbetMultiway - 3),
          riverBluffCatch: Math.max(20, prev.riverBluffCatch - 2)
        }));

        onNotify?.("CICLO DE AUTO-TREINO CONCLUÍDO", `O cérebro evoluiu! Winrate projetado subiu para +${(globalWinrate + 0.6).toFixed(1)} bb/100 e a convergência atingiu ${(convergenceRate + 0.8).toFixed(1)}%.`, "INFO");
      }
    }, 400);
  };

  // Auto-Fix Leak Handler
  const handleApplyLeakFix = (leakId: string) => {
    setLeaks(prev =>
      prev.map(leak => {
        if (leak.id === leakId) {
          const reducedLoss = Number((leak.lossBbPer100 * 0.25).toFixed(1));
          return {
            ...leak,
            lossBbPer100: reducedLoss,
            totalLossBb: Number((leak.totalLossBb * 0.3).toFixed(1)),
            severity: 'RESOLVED',
            appliedFix: true
          };
        }
        return leak;
      })
    );
    const targetLeak = leaks.find(l => l.id === leakId);
    onNotify?.("LEAK CORRIGIDO COM SUCESSO", `Política de ação para '${targetLeak?.name}' recalibrada no cérebro. Perda estancada.`, "INFO");
  };

  // Import Range JSON Handler
  const handleImportRangeJson = () => {
    try {
      const parsed = JSON.parse(importJsonText);
      if (!parsed.name || !parsed.positions) {
        throw new Error("Formato inválido. O JSON deve conter 'name' e 'positions'.");
      }
      const newProfile: TournamentRangeProfile = {
        id: `profile_${Date.now()}`,
        name: parsed.name,
        category: parsed.category || 'Personalizado Externo',
        stackBb: parsed.stackBb || 30,
        description: parsed.description || 'Perfil de ranges alimentado externamente de outro software.',
        positions: parsed.positions
      };
      setRangeProfiles(prev => [...prev, newProfile]);
      setSelectedProfileId(newProfile.id);
      setShowImportModal(false);
      setImportJsonText('');
      onNotify?.("RANGES IMPORTADOS", `Perfil '${newProfile.name}' carregado e alimentado no cérebro com sucesso.`, "INFO");
    } catch (err: any) {
      onNotify?.("FALHA NA IMPORTAÇÃO", err.message || "Erro de sintaxe JSON.", "CRITICAL");
    }
  };

  // Export Lines of Play with Hands JSON
  const handleExportLinesOfPlay = (downloadFile: boolean = true) => {
    const profitableCount = linesOfPlay.filter(l => l.winrateBb100 > 0).length;
    const unprofitableCount = linesOfPlay.filter(l => l.winrateBb100 <= 0).length;
    const totalHands = linesOfPlay.reduce((acc, l) => acc + l.sampleSize, 0);
    const netChipsBb = Number(linesOfPlay.reduce((acc, l) => acc + l.totalProfitBb, 0).toFixed(1));
    const avgWinrate = Number((linesOfPlay.reduce((acc, l) => acc + l.winrateBb100, 0) / linesOfPlay.length).toFixed(1));

    const exportPayload = {
      export_metadata: {
        system: "VisualPilot PPPoker Brain & Evolutionary Engine",
        version: "2.4.0",
        format: "LinesOfPlay_Aggregate_v1.0",
        exported_at: new Date().toISOString(),
        total_lines_tracked: linesOfPlay.length,
        compatible_systems: [
          "PioSolver Range Importer",
          "GTO Wizard Range Manager",
          "PokerRanger / Equilab",
          "VisualPilot Custom Solvers"
        ],
        summary: {
          total_lines_tracked: linesOfPlay.length,
          profitable_lines: profitableCount,
          unprofitable_lines: unprofitableCount,
          total_hands_analyzed: totalHands,
          net_profit_bb: netChipsBb,
          average_winrate_bb100: avgWinrate
        }
      },
      lines_of_play: linesOfPlay.map(line => ({
        id: line.id,
        name: line.name,
        short_name: line.shortName,
        sequence: line.sequence,
        category: line.category,
        category_label: line.categoryLabel,
        sample_size: line.sampleSize,
        winrate_bb_100: line.winrateBb100,
        all_in_ev_bb_100: line.allInEvBb100,
        ev_diff: line.evDiff,
        success_rate_pct: line.successRatePct,
        total_profit_bb: line.totalProfitBb,
        verdict: line.verdict,
        status: line.status,
        recommendation: line.recommendation,
        played_hands: (line.playedHands || []).map(h => ({
          hand_id: h.handId,
          hole_cards: h.holeCards,
          combo: h.combo,
          position: h.position,
          board: h.board,
          pot_size_bb: h.potSizeBb,
          outcome_bb: h.outcomeBb,
          showdown: h.showdown,
          result: h.result
        }))
      }))
    };

    const jsonString = JSON.stringify(exportPayload, null, 2);
    setExportedLinesJson(jsonString);

    if (downloadFile) {
      const blob = new Blob([jsonString], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `visualpilot_lines_of_play_export_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }

    setShowExportLinesModal(true);
    onNotify?.(
      "ESTATÍSTICAS EXPORTADAS",
      `JSON gerado com sucesso contendo ${linesOfPlay.length} linhas de jogo e detalhes das mãos para integração externa.`,
      "INFO"
    );
  };

  // Filtered Lines of Play
  const filteredLinesOfPlay = linesOfPlay.filter(l => {
    if (lineCategoryFilter === 'PROFITABLE') return l.winrateBb100 > 0;
    if (lineCategoryFilter === 'UNPROFITABLE') return l.winrateBb100 <= 0;
    if (lineCategoryFilter === 'AGGRESSIVE_IP') return l.category === 'AGGRESSIVE_IP';
    if (lineCategoryFilter === 'DEFENSE_OOP') return l.category === 'DEFENSE_OOP';
    if (lineCategoryFilter === '3BET_POT') return l.category === '3BET_POT';
    return true;
  });

  // Current Selected Profile
  const currentProfile = rangeProfiles.find(p => p.id === selectedProfileId) || rangeProfiles[0];
  const currentRangeHands = currentProfile.positions[selectedPosition] || [];

  // Metrics for Human Feedback
  const pendingFeedbackCount = feedbackHands.filter(h => !h.feedback).length;
  const correctCount = feedbackHands.filter(h => h.feedback === 'CORRECT').length;
  const mistakeCount = feedbackHands.filter(h => h.feedback === 'MISTAKE').length;

  return (
    <div className="space-y-6">
      {/* Top Brain Status Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-full bg-gradient-to-l from-purple-500/10 via-indigo-500/5 to-transparent pointer-events-none" />
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 relative z-10">
          <div className="flex items-center gap-3.5">
            <div className="p-2.5 rounded-xl bg-purple-500/20 text-purple-400 border border-purple-500/30 shrink-0">
              <Cpu className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-slate-100 tracking-tight">
                  Cérebro Estratégico & Aprendizado Evolutivo
                </h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-950 text-purple-300 border border-purple-700">
                  {modelVersion}
                </span>
              </div>
              <p className="text-xs text-slate-400 max-w-3xl">
                Base central de inteligência: treinado em todos os ranges pré-flop, retroalimentação humana (Acerto/Erro pós-mão), análise detalhada por linhas de jogo, detector ativo de leaks financeiros e auto-adaptação pós-sessão.
              </p>
            </div>
          </div>

          {/* Quick KPIs & Action Button */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs">
              <span className="text-[10px] text-slate-500 block">Total de Mãos</span>
              <span className="font-bold text-slate-200">{totalHandsAnalyzed.toLocaleString('pt-BR')}</span>
            </div>

            <div className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs">
              <span className="text-[10px] text-slate-500 block">Winrate Global</span>
              <span className="font-black text-emerald-400">+{globalWinrate} bb/100</span>
            </div>

            <button
              onClick={handleStartTrainingCycle}
              disabled={isTraining}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-xs shadow-lg shadow-purple-500/20 transition-all disabled:opacity-50 cursor-pointer"
            >
              {isTraining ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              <span>{isTraining ? `Treinando (${trainingProgress}%)` : 'Executar Auto-Treino'}</span>
            </button>
          </div>
        </div>

        {/* Training Progress Bar */}
        {isTraining && (
          <div className="mt-4 pt-3 border-t border-slate-800/80 space-y-1">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-purple-300 flex items-center gap-1.5 font-bold">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-purple-400" />
                <span>Simulando rodadas de aprendizado por reforço e convergência de política...</span>
              </span>
              <span className="text-emerald-400 font-bold">{trainingProgress}%</span>
            </div>
            <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden border border-purple-900/50 p-0.5">
              <div
                className="h-full bg-gradient-to-r from-purple-500 via-indigo-500 to-emerald-400 rounded-full transition-all duration-300"
                style={{ width: `${trainingProgress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Sub-Tabs Navigation */}
      <div className="flex items-center gap-1.5 p-1 bg-slate-900 border border-slate-800 rounded-xl overflow-x-auto">
        <button
          onClick={() => setActiveSubTab('overview')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 cursor-pointer ${
            activeSubTab === 'overview'
              ? 'bg-purple-950 text-purple-200 border border-purple-600 shadow-sm font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <BarChart2 className="w-3.5 h-3.5" />
          <span>Visão Geral & Treinamento</span>
        </button>

        {/* NEW SUB-TAB 1: Human Feedback (RLHF) */}
        <button
          onClick={() => setActiveSubTab('human_feedback')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 cursor-pointer ${
            activeSubTab === 'human_feedback'
              ? 'bg-purple-950 text-purple-200 border border-purple-600 shadow-sm font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <ThumbsUp className="w-3.5 h-3.5 text-emerald-400" />
          <span className="flex items-center gap-1.5">
            <span>Feedback Humano (Acerto/Erro)</span>
            {pendingFeedbackCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold bg-amber-500 text-slate-950 animate-pulse">
                {pendingFeedbackCount}
              </span>
            )}
          </span>
        </button>

        {/* NEW SUB-TAB 2: Lines of Play Performance */}
        <button
          onClick={() => setActiveSubTab('lines_of_play')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 cursor-pointer ${
            activeSubTab === 'lines_of_play'
              ? 'bg-purple-950 text-purple-200 border border-purple-600 shadow-sm font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <Workflow className="w-3.5 h-3.5 text-cyan-400" />
          <span>Performance por Linha de Jogo</span>
        </button>

        <button
          onClick={() => setActiveSubTab('preflop_feeder')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 cursor-pointer ${
            activeSubTab === 'preflop_feeder'
              ? 'bg-purple-950 text-purple-200 border border-purple-600 shadow-sm font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Alimentador de Ranges</span>
        </button>

        <button
          onClick={() => setActiveSubTab('leak_finder')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 cursor-pointer ${
            activeSubTab === 'leak_finder'
              ? 'bg-purple-950 text-purple-200 border border-purple-600 shadow-sm font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          <span>Detector de Leaks</span>
        </button>

        <button
          onClick={() => setActiveSubTab('site_analytics')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 cursor-pointer ${
            activeSubTab === 'site_analytics'
              ? 'bg-purple-950 text-purple-200 border border-purple-600 shadow-sm font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <Coins className="w-3.5 h-3.5 text-emerald-400" />
          <span>Performance por Site</span>
        </button>

        <button
          onClick={() => setActiveSubTab('postflop_adaptive')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 cursor-pointer ${
            activeSubTab === 'postflop_adaptive'
              ? 'bg-purple-950 text-purple-200 border border-purple-600 shadow-sm font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <Sliders className="w-3.5 h-3.5 text-cyan-400" />
          <span>Adaptação Pós-Flop</span>
        </button>
      </div>

      {/* SUB-TAB: HUMAN FEEDBACK (ACERTO / ERRO) */}
      {activeSubTab === 'human_feedback' && (
        <div className="space-y-6">
          {/* Header & Feedback Stats Strip */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-lg">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <ThumbsUp className="w-4 h-4" />
                </div>
                <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider">
                  Sistema de Feedback Humano pós-mão (RLHF & Calibração de Pesos)
                </h3>
              </div>
              <p className="text-xs text-slate-400">
                Avalie cada jogada do bot como <strong>Acerto (+EV)</strong> ou <strong>Erro (-EV)</strong>. O cérebro ajusta instantaneamente os pesos e a frequência daquele combo nas tabelas pré-flop.
              </p>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono">
                <span className="text-emerald-400 font-bold flex items-center gap-1">
                  <ThumbsUp className="w-3.5 h-3.5" /> {correctCount} Acertos
                </span>
                <span className="text-slate-600">|</span>
                <span className="text-rose-400 font-bold flex items-center gap-1">
                  <ThumbsDown className="w-3.5 h-3.5" /> {mistakeCount} Erros
                </span>
              </div>

              <button
                onClick={handleSimulateNewHand}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition-colors shadow-sm cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Simular Nova Mão Jogada</span>
              </button>
            </div>
          </div>

          {/* Learning Rate & Human Feedback Weights Configuration Section */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-purple-500/20 text-purple-400 border border-purple-500/30">
                  <SlidersHorizontal className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider font-mono">
                    Configuração da Taxa de Aprendizado (Learning Rate) & Pesos do Feedback
                  </h3>
                  <p className="text-xs text-slate-400">
                    Defina a intensidade com que o feedback humano (acertos e erros) ajusta os pesos nos ranges pré-flop e frequências pós-flop.
                  </p>
                </div>
              </div>

              {/* Quick Presets */}
              <div className="flex items-center gap-1.5 font-mono text-xs flex-wrap">
                <span className="text-[10px] text-slate-500 uppercase font-bold mr-1">Presets:</span>
                <button
                  type="button"
                  onClick={() => applyLearningPreset('CONSERVATIVE')}
                  className={`px-2.5 py-1 rounded-lg border transition-all cursor-pointer ${
                    learningPreset === 'CONSERVATIVE'
                      ? 'bg-purple-950 text-purple-200 border-purple-500 font-bold shadow-sm'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Conservador (0.03)
                </button>
                <button
                  type="button"
                  onClick={() => applyLearningPreset('BALANCED')}
                  className={`px-2.5 py-1 rounded-lg border transition-all cursor-pointer ${
                    learningPreset === 'BALANCED'
                      ? 'bg-purple-950 text-purple-200 border-purple-500 font-bold shadow-sm'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Equilibrado (0.08)
                </button>
                <button
                  type="button"
                  onClick={() => applyLearningPreset('AGGRESSIVE')}
                  className={`px-2.5 py-1 rounded-lg border transition-all cursor-pointer ${
                    learningPreset === 'AGGRESSIVE'
                      ? 'bg-purple-950 text-purple-200 border-purple-500 font-bold shadow-sm'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Agressivo / Rápido (0.16)
                </button>
              </div>
            </div>

            {/* 4 Interactive Configuration Sliders */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-mono text-xs">
              {/* Slider 1: Global Learning Rate */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 font-bold">Taxa Global (η):</span>
                  <span className="text-purple-300 font-black">{learningRate.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={0.01}
                  max={0.25}
                  step={0.01}
                  value={learningRate}
                  onChange={(e) => setLearningRate(Number(e.target.value))}
                  className="w-full accent-purple-500 bg-slate-900 h-1.5 rounded cursor-pointer"
                />
                <span className="text-[10px] text-slate-500 block leading-tight">
                  Velocidade geral com que cada mão modifica as tabelas do modelo.
                </span>
              </div>

              {/* Slider 2: Pre-Flop Correct Weight */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-emerald-400 font-bold">Peso Acerto Pré-Flop:</span>
                  <span className="text-emerald-400 font-black">+{feedbackWeightCorrect.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={0.02}
                  max={0.30}
                  step={0.01}
                  value={feedbackWeightCorrect}
                  onChange={(e) => setFeedbackWeightCorrect(Number(e.target.value))}
                  className="w-full accent-emerald-500 bg-slate-900 h-1.5 rounded cursor-pointer"
                />
                <span className="text-[10px] text-slate-500 block leading-tight">
                  Acréscimo de frequência na matriz para ações aprovadas como Acerto.
                </span>
              </div>

              {/* Slider 3: Pre-Flop Mistake Weight */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-rose-400 font-bold">Peso Erro Pré-Flop:</span>
                  <span className="text-rose-400 font-black">{feedbackWeightMistake.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={-0.60}
                  max={-0.10}
                  step={0.02}
                  value={feedbackWeightMistake}
                  onChange={(e) => setFeedbackWeightMistake(Number(e.target.value))}
                  className="w-full accent-rose-500 bg-slate-900 h-1.5 rounded cursor-pointer"
                />
                <span className="text-[10px] text-slate-500 block leading-tight">
                  Penalidade aplicada no peso do combo ao classificar como Erro.
                </span>
              </div>

              {/* Slider 4: Postflop Multiplier */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-cyan-400 font-bold">Influência Pós-Flop:</span>
                  <span className="text-cyan-300 font-black">{postflopInfluenceMultiplier.toFixed(1)}x</span>
                </div>
                <input
                  type="range"
                  min={1.0}
                  max={4.0}
                  step={0.2}
                  value={postflopInfluenceMultiplier}
                  onChange={(e) => setPostflopInfluenceMultiplier(Number(e.target.value))}
                  className="w-full accent-cyan-500 bg-slate-900 h-1.5 rounded cursor-pointer"
                />
                <span className="text-[10px] text-slate-500 block leading-tight">
                  Multiplicador que propaga o feedback para frequências de C-Bet e Bluff-Catch.
                </span>
              </div>
            </div>

            {/* Formula & Impact Summary Banner */}
            <div className="p-3 rounded-xl bg-purple-950/20 border border-purple-900/40 text-[11px] text-slate-300 flex flex-wrap items-center justify-between gap-2 font-mono">
              <span className="flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                <span>
                  Fórmula em Execução: <strong>ΔPeso = Peso_Base × (η / 0.08)</strong> • Próximo Acerto: <strong className="text-emerald-400">+{(feedbackWeightCorrect * (learningRate / 0.08)).toFixed(2)}</strong> • Próximo Erro: <strong className="text-rose-400">{(feedbackWeightMistake * (learningRate / 0.08)).toFixed(2)}</strong>
                </span>
              </span>
              <span className="text-purple-300 font-bold bg-purple-900/50 px-2 py-0.5 rounded border border-purple-700">
                Amortecimento de Momentum: {(momentumDamping * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Session Error History & Failure Categorization Component */}
          <SessionErrorHistoryInspector onNotify={onNotify} />

          {/* Hands Feed for Human Review */}
          <div className="space-y-3">
            {feedbackHands.map(hand => {
              const isCorrect = hand.feedback === 'CORRECT';
              const isMistake = hand.feedback === 'MISTAKE';
              const isPending = !hand.feedback;

              return (
                <div
                  key={hand.id}
                  className={`p-4 rounded-2xl border transition-all ${
                    isPending
                      ? 'bg-slate-900 border-amber-500/50 shadow-md ring-1 ring-amber-500/20'
                      : isCorrect
                      ? 'bg-slate-950 border-emerald-800/80'
                      : 'bg-slate-950 border-rose-800/80'
                  }`}
                >
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    {/* Left: Hand Details, Cards & Situation */}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span className="text-xs font-mono font-bold text-slate-400">{hand.timestamp}</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
                          {hand.table}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-950 text-purple-300 border border-purple-700">
                          {hand.position}
                        </span>

                        {/* Status Badge */}
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${
                          isCorrect ? 'bg-emerald-950 text-emerald-300 border-emerald-600' :
                          isMistake ? 'bg-rose-950 text-rose-300 border-rose-600' :
                          'bg-amber-950 text-amber-300 border-amber-600 animate-pulse'
                        }`}>
                          {isCorrect ? '✓ AVALIADO: ACERTO (+EV)' :
                           isMistake ? '✗ AVALIADO: ERRO (-EV)' :
                           'PENDENTE DE AUDITORIA'}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 flex-wrap">
                        {/* 4-Color Card Badge */}
                        <div className="flex items-center gap-1.5 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800">
                          <span className="text-[10px] font-mono uppercase text-slate-500 mr-1">Cartas:</span>
                          {render4ColorCard(hand.heroCards)}
                          <span className="text-xs font-mono font-bold text-slate-200 ml-1">({hand.combo})</span>
                        </div>

                        {/* Actions Flow */}
                        <div className="text-xs font-mono flex items-center gap-1.5 text-slate-300 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
                          <span className="text-slate-400">Ação Hero:</span>
                          <strong className="text-emerald-400">{hand.preflopAction}</strong>
                          <span className="text-slate-600">→</span>
                          <span className="text-slate-400">Vilão:</span>
                          <span className="text-amber-300">{hand.vsAction}</span>
                          <span className="text-slate-600">→</span>
                          <span className="text-slate-400">Resposta:</span>
                          <strong className="text-cyan-300">{hand.heroResponse}</strong>
                        </div>

                        {/* Outcome Chips */}
                        <div className="text-xs font-mono px-2 py-1 rounded-lg bg-slate-950 border border-slate-800">
                          <span className="text-slate-400 mr-1">Resultado:</span>
                          <strong className={hand.outcomeBb >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                            {hand.outcomeBb >= 0 ? `+${hand.outcomeBb}` : hand.outcomeBb} BB
                          </strong>
                          <span className="text-slate-500 text-[10px] ml-1">(Pote: {hand.potBb} BB)</span>
                        </div>
                      </div>

                      {/* Notes / Feedback Details */}
                      {hand.notes && (
                        <div className="text-xs font-mono text-slate-400 flex items-start gap-1.5 bg-slate-950/60 p-2 rounded-xl border border-slate-800/60">
                          <MessageSquare className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
                          <div>
                            <span>{hand.notes}</span>
                            {hand.correctionAction && (
                              <div className="text-amber-400 font-bold mt-0.5">
                                Ação Corretiva: {hand.correctionAction}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Right: Human Feedback Decision Buttons */}
                    <div className="flex sm:flex-col items-end justify-center gap-2 shrink-0">
                      <div className="flex items-center gap-2">
                        {/* Button Acerto */}
                        <button
                          onClick={() => handleRateHandCorrect(hand.id)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-sm ${
                            isCorrect
                              ? 'bg-emerald-500 text-slate-950 border border-emerald-400'
                              : 'bg-slate-950 hover:bg-emerald-950 border border-slate-700 text-emerald-400 hover:border-emerald-600'
                          }`}
                          title="Avaliar como Acerto (+EV) e aumentar peso do combo no range"
                        >
                          <ThumbsUp className="w-3.5 h-3.5" />
                          <span>Acerto (+EV)</span>
                        </button>

                        {/* Button Erro */}
                        <button
                          onClick={() => {
                            setSelectedHandForModal(hand);
                            setCorrectionActionInput(hand.correctionAction || 'Fold');
                            setCorrectionNoteInput(hand.notes || '');
                          }}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-sm ${
                            isMistake
                              ? 'bg-rose-500 text-white border border-rose-400'
                              : 'bg-slate-950 hover:bg-rose-950 border border-slate-700 text-rose-400 hover:border-rose-600'
                          }`}
                          title="Avaliar como Erro (-EV) e reduzir peso do combo no range"
                        >
                          <ThumbsDown className="w-3.5 h-3.5" />
                          <span>Erro (-EV)</span>
                        </button>
                      </div>

                      {/* Weight Delta Indicator */}
                      {hand.weightDelta !== undefined && hand.weightDelta !== 0 && (
                        <div className="text-[11px] font-mono text-right">
                          <span className="text-slate-500 mr-1">Ajuste no Range:</span>
                          <strong className={hand.weightDelta > 0 ? 'text-emerald-400' : 'text-rose-400'}>
                            {hand.weightDelta > 0 ? `+${hand.weightDelta.toFixed(2)}` : hand.weightDelta.toFixed(2)} peso
                          </strong>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* SUB-TAB: LINES OF PLAY PERFORMANCE (PERFORMANCE POR LINHA DE JOGO) */}
      {activeSubTab === 'lines_of_play' && (
        <div className="space-y-6">
          {/* Header & Filters */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <Workflow className="w-4 h-4 text-cyan-400" />
                  <span>Performance e Rentabilidade por Linha de Jogo (Line of Play)</span>
                </h3>
                <p className="text-xs text-slate-400">
                  Rastreamento sequencial das ações tomadas pré-flop e pós-flop para identificar as linhas mais lucrativas vs drenos de fichas
                </p>
              </div>

              {/* Actions & Filter Chips */}
              <div className="flex items-center gap-2.5 flex-wrap">
                <button
                  onClick={() => handleExportLinesOfPlay(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs transition-colors shadow-sm cursor-pointer"
                  title="Exportar estatísticas agregadas de Win/Loss e detalhes das mãos jogadas em JSON"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Exportar JSON (Linhas + Mãos)</span>
                </button>

                <div className="h-5 w-px bg-slate-800 hidden sm:block" />

                <div className="flex items-center gap-1.5 flex-wrap">
                  {(['ALL', 'PROFITABLE', 'UNPROFITABLE', 'AGGRESSIVE_IP', 'DEFENSE_OOP', '3BET_POT'] as const).map(cat => {
                    const labels: Record<string, string> = {
                      ALL: 'Todas as Linhas',
                      PROFITABLE: 'Apenas Lucrativas (+EV)',
                      UNPROFITABLE: 'Apenas com Prejuízo (-EV)',
                      AGGRESSIVE_IP: 'Agressivas IP',
                      DEFENSE_OOP: 'Defesas OOP',
                      '3BET_POT': '3-Bet / Shoves'
                    };
                    return (
                      <button
                        key={cat}
                        onClick={() => setLineCategoryFilter(cat)}
                        className={`px-2.5 py-1 rounded-lg border text-xs font-mono transition-all cursor-pointer ${
                          lineCategoryFilter === cat
                            ? 'bg-cyan-950 text-cyan-200 border-cyan-500 font-bold shadow-sm'
                            : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                        }`}
                      >
                        {labels[cat]}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Recharts BarChart: Winrate bb/100 by Line of Play */}
            <div className="space-y-2">
              <span className="text-xs font-mono text-slate-400 uppercase font-bold tracking-wider block">
                Winrate Comparativo por Linha (bb/100):
              </span>
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={linesOfPlay} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis type="number" stroke="#64748b" tick={{ fontSize: 11 }} />
                    <YAxis dataKey="shortName" type="category" width={190} stroke="#94a3b8" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '12px' }}
                      itemStyle={{ color: '#f8fafc' }}
                      formatter={(val: any) => [`${val} bb/100`, 'Winrate']}
                    />
                    <ReferenceLine x={0} stroke="#475569" strokeWidth={1.5} />
                    <Bar dataKey="winrateBb100" radius={[0, 4, 4, 0]}>
                      {linesOfPlay.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.winrateBb100 >= 0 ? '#10b981' : '#f43f5e'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* EV Comparison Analysis Component: Expected vs Real EV (Bar Charts) */}
          <LinesOfPlayEvAnalysis onNotify={onNotify} />

          {/* Lines of Play Cards List */}
          <div className="space-y-3">
            {filteredLinesOfPlay.map(line => {
              const isProfit = line.winrateBb100 >= 0;
              return (
                <div
                  key={line.id}
                  className={`p-4 rounded-2xl border transition-all ${
                    isProfit
                      ? 'bg-slate-950 border-emerald-800/80 hover:border-emerald-700'
                      : 'bg-slate-950 border-rose-800/80 hover:border-rose-700'
                  }`}
                >
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    {/* Left: Sequence and Description */}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${
                          line.status === 'EXCELLENT' ? 'bg-emerald-950 text-emerald-300 border-emerald-700' :
                          line.status === 'GOOD' ? 'bg-cyan-950 text-cyan-300 border-cyan-700' :
                          'bg-rose-950 text-rose-300 border-rose-700'
                        }`}>
                          {line.verdict}
                        </span>

                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-900 border border-slate-800 text-slate-300">
                          {line.categoryLabel}
                        </span>

                        <span className="text-xs font-bold text-slate-100">{line.name}</span>
                      </div>

                      {/* Sequence Flow Badges */}
                      <div className="flex items-center gap-1.5 flex-wrap pt-1 font-mono text-xs">
                        {line.sequence.map((step, idx) => (
                          <React.Fragment key={idx}>
                            <span className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 font-bold shadow-sm">
                              {step}
                            </span>
                            {idx < line.sequence.length - 1 && (
                              <ArrowRight className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                            )}
                          </React.Fragment>
                        ))}
                      </div>

                      {/* Strategic Recommendation */}
                      <p className="text-xs text-slate-400 leading-relaxed max-w-3xl pt-1">
                        <strong className="text-slate-300">Diagnóstico Tático: </strong>
                        {line.recommendation}
                      </p>

                      {/* Toggle Hands Button */}
                      <div className="pt-2 flex items-center justify-between">
                        <button
                          onClick={() => setExpandedLineHandId(expandedLineHandId === line.id ? null : line.id)}
                          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs font-mono text-cyan-300 transition-colors cursor-pointer"
                        >
                          <ChevronRight className={`w-3.5 h-3.5 text-cyan-400 transition-transform ${expandedLineHandId === line.id ? 'rotate-90' : ''}`} />
                          <span>{expandedLineHandId === line.id ? 'Ocultar Detalhes das Mãos' : `Ver Mãos Amostrais (${line.playedHands?.length || 0})`}</span>
                        </button>

                        {line.playedHands && line.playedHands.length > 0 && (
                          <span className="text-[11px] font-mono text-slate-500">
                            {line.playedHands.filter(h => h.result === 'WIN').length} vitórias • {line.playedHands.filter(h => h.result === 'LOSS').length} derrotas
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Right: Key Performance Metrics */}
                    <div className="flex sm:flex-col items-end justify-center gap-2 shrink-0 font-mono text-xs">
                      <div className="text-right">
                        <span className="text-[10px] text-slate-500 block">Winrate Médio</span>
                        <span className={`text-lg font-black ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isProfit ? `+${line.winrateBb100}` : line.winrateBb100} bb/100
                        </span>
                      </div>

                      <div className="text-right text-[11px] text-slate-400 space-y-0.5">
                        <div>Amostra: <strong className="text-slate-200">{line.sampleSize} mãos</strong></div>
                        <div>Taxa Sucesso: <strong className="text-cyan-300">{line.successRatePct}%</strong></div>
                        <div>Lucro Total: <strong className={isProfit ? 'text-emerald-400' : 'text-rose-400'}>
                          {line.totalProfitBb >= 0 ? `+${line.totalProfitBb}` : line.totalProfitBb} BB
                        </strong></div>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Hand History for this Line */}
                  {expandedLineHandId === line.id && line.playedHands && line.playedHands.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-slate-800/80 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider">
                          Mãos Jogadas com esta Linha (Exportáveis para Range Solver):
                        </span>
                        <span className="text-[11px] font-mono text-purple-400">
                          Formatado para PioSolver / GTO Wizard / Equilab
                        </span>
                      </div>

                      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/70">
                        <table className="w-full text-left text-xs font-mono">
                          <thead>
                            <tr className="border-b border-slate-800 text-slate-400 bg-slate-900/50">
                              <th className="p-2.5">ID Mão</th>
                              <th className="p-2.5">Cartas (Hero)</th>
                              <th className="p-2.5">Combo</th>
                              <th className="p-2.5">Posição</th>
                              <th className="p-2.5">Board Runout</th>
                              <th className="p-2.5 text-right">Pote (BB)</th>
                              <th className="p-2.5 text-right">Resultado (BB)</th>
                              <th className="p-2.5 text-center">Showdown</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 text-slate-300">
                            {line.playedHands.map(hand => (
                              <tr key={hand.handId} className="hover:bg-slate-900/30">
                                <td className="p-2.5 font-bold text-slate-400">{hand.handId}</td>
                                <td className="p-2.5">{render4ColorCard(hand.holeCards)}</td>
                                <td className="p-2.5 font-bold text-amber-300">{hand.combo}</td>
                                <td className="p-2.5 text-slate-200">{hand.position}</td>
                                <td className="p-2.5 text-slate-300">{hand.board}</td>
                                <td className="p-2.5 text-right text-slate-300">{hand.potSizeBb.toFixed(1)} BB</td>
                                <td className={`p-2.5 text-right font-black ${hand.outcomeBb >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                  {hand.outcomeBb >= 0 ? `+${hand.outcomeBb.toFixed(1)}` : hand.outcomeBb.toFixed(1)} BB
                                </td>
                                <td className="p-2.5 text-center">
                                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${hand.showdown ? 'bg-purple-950 text-purple-300 border border-purple-800' : 'bg-slate-900 text-slate-400 border border-slate-800'}`}>
                                    {hand.showdown ? 'SD' : 'Sem SD'}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* SUB-TAB: Overview & Evolutionary Training Lab */}
      {activeSubTab === 'overview' && (
        <div className="space-y-6">
          {/* Recharts Curve: Actual bb/100 vs All-in EV vs Training Loss */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                  <span>Curva de Evolução: Lucro Realizado vs All-in EV (bb/100)</span>
                </h3>
                <p className="text-xs text-slate-400">
                  Acompanhamento da convergência do bot após ciclos de aprendizado e correção de erros
                </p>
              </div>

              <div className="flex items-center gap-4 text-xs font-mono">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                  <span className="text-slate-300">Lucro Real (bb/100)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-purple-400" />
                  <span className="text-slate-300">All-in EV Esperado</span>
                </div>
              </div>
            </div>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={EVOLUTION_GRAPH_DATA}>
                  <defs>
                    <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.4}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0.0}/>
                    </linearGradient>
                    <linearGradient id="colorEv" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#a855f7" stopOpacity={0.4}/>
                      <stop offset="95%" stopColor="#a855f7" stopOpacity={0.0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="session" stroke="#64748b" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '12px' }}
                    itemStyle={{ color: '#f8fafc' }}
                  />
                  <Area type="monotone" dataKey="actualBb100" name="Lucro Real (bb/100)" stroke="#10b981" strokeWidth={2.5} fillOpacity={1} fill="url(#colorActual)" />
                  <Area type="monotone" dataKey="evBb100" name="All-in EV (bb/100)" stroke="#a855f7" strokeWidth={2.5} fillOpacity={1} fill="url(#colorEv)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Training Control Strip & Diagnostics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Control 1: Training Parameters */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
              <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
                <SlidersHorizontal className="w-4 h-4 text-purple-400" />
                <h4 className="font-bold text-xs text-slate-100 uppercase tracking-wider">
                  Parâmetros de Treinamento
                </h4>
              </div>

              <div className="space-y-3 text-xs font-mono">
                <div>
                  <div className="flex justify-between text-slate-400 mb-1">
                    <span>Épocas por Ciclo:</span>
                    <strong className="text-purple-300">{trainingEpochsTarget} épocas</strong>
                  </div>
                  <input
                    type="range"
                    min={10}
                    max={200}
                    step={10}
                    value={trainingEpochsTarget}
                    onChange={(e) => setTrainingEpochsTarget(Number(e.target.value))}
                    className="w-full accent-purple-500 bg-slate-950 h-1.5 rounded cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-slate-400 mb-1">
                    <span>Taxa de Aprendizado (LR):</span>
                    <strong className="text-purple-300">{learningRate}</strong>
                  </div>
                  <input
                    type="range"
                    min={0.01}
                    max={0.15}
                    step={0.01}
                    value={learningRate}
                    onChange={(e) => setLearningRate(Number(e.target.value))}
                    className="w-full accent-purple-500 bg-slate-950 h-1.5 rounded cursor-pointer"
                  />
                </div>

                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-slate-400">
                  <span className="text-slate-300 font-bold block mb-0.5">Aprendizado por Reforço (RL):</span>
                  Simula cenários em paralelo contra o histórico de vilões, reajustando os pesos nas decisões pré e pós-flop para maximizar EV.
                </div>
              </div>
            </div>

            {/* Control 2: Evolution KPIs */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
              <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
                <Brain className="w-4 h-4 text-emerald-400" />
                <h4 className="font-bold text-xs text-slate-100 uppercase tracking-wider">
                  Métricas de Convergência
                </h4>
              </div>

              <div className="space-y-2 text-xs font-mono">
                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Épocas Concluídas:</span>
                  <span className="font-bold text-purple-300">{epochsCount}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Convergência GTO:</span>
                  <span className="font-bold text-emerald-400">{convergenceRate}%</span>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Leaks Críticos Ativos:</span>
                  <span className="font-bold text-amber-400">{leaks.filter(l => l.severity !== 'RESOLVED').length} pendentes</span>
                </div>
              </div>
            </div>

            {/* Control 3: Quick Action Hub */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
                  <Zap className="w-4 h-4 text-amber-400" />
                  <h4 className="font-bold text-xs text-slate-100 uppercase tracking-wider">
                    Ciclo de Auto-Aperfeiçoamento
                  </h4>
                </div>
                <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                  Ao final de cada sessão, o bot processa as mãos jogadas, identifica as decisões que causaram perda de fichas e recalibra sua política de ação.
                </p>
              </div>

              <button
                onClick={handleStartTrainingCycle}
                disabled={isTraining}
                className="w-full py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition-colors flex items-center justify-center gap-2 cursor-pointer shadow-md"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isTraining ? 'animate-spin' : ''}`} />
                <span>{isTraining ? 'Treinando Modelo...' : 'Treinar Modelo com Mãos da Sessão'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB: Pre-Flop Range Feeder & External Importer */}
      {activeSubTab === 'preflop_feeder' && (
        <div className="space-y-5">
          {/* Header Strip with Import/Export Controls */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3 shadow-lg">
            <div>
              <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                <Database className="w-4 h-4 text-purple-400" />
                <span>Alimentador de Ranges Pré-Flop por Torneio & Posição</span>
              </h3>
              <p className="text-xs text-slate-400">
                Alimente a inteligência pré-flop do bot importando dados de solvers ou do seu sistema externo
              </p>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => setShowImportModal(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs transition-colors cursor-pointer shadow-sm"
              >
                <Upload className="w-3.5 h-3.5" />
                <span>Importar Ranges (JSON/CSV)</span>
              </button>

              <button
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(currentProfile, null, 2));
                  setCopiedProfileJson(true);
                  setTimeout(() => setCopiedProfileJson(false), 2000);
                  onNotify?.("RANGES COPIADOS", "Ranges do perfil ativo copiados em formato JSON.", "INFO");
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold transition-colors cursor-pointer"
              >
                {copiedProfileJson ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedProfileJson ? 'Copiado!' : 'Copiar JSON'}</span>
              </button>
            </div>
          </div>

          {/* Profile & Position Selectors */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Tournament Profile Picker */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2.5">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider block font-mono">
                1. Selecionar Perfil do Torneio / Estrutura:
              </label>
              <div className="space-y-2">
                {rangeProfiles.map(p => (
                  <button
                    key={p.id}
                    onClick={() => setSelectedProfileId(p.id)}
                    className={`w-full text-left p-3 rounded-xl border transition-all cursor-pointer ${
                      selectedProfileId === p.id
                        ? 'bg-purple-950/70 border-purple-500 text-purple-200 shadow-md'
                        : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs">{p.name}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-900 border border-slate-800 text-purple-300">
                        {p.stackBb} BB
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1">{p.description}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Position Picker & Range Overview */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider block font-mono">
                2. Posição na Mesa (Hero Range):
              </label>
              <div className="grid grid-cols-5 gap-2">
                {['UTG', 'MP', 'CO', 'BTN', 'SB'].map(pos => (
                  <button
                    key={pos}
                    onClick={() => setSelectedPosition(pos)}
                    className={`py-2 rounded-xl font-mono text-xs font-bold border transition-all cursor-pointer ${
                      selectedPosition === pos
                        ? 'bg-emerald-500 text-slate-950 border-emerald-400 shadow-md'
                        : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
                    }`}
                  >
                    {pos}
                  </button>
                ))}
              </div>

              {/* Range Combos Count & Percentage */}
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2 font-mono text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Total de Combos no Range:</span>
                  <span className="font-bold text-emerald-400">{currentRangeHands.length} tipos de mãos</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Frequência Estimada de Abertura:</span>
                  <span className="font-bold text-purple-300">
                    {((currentRangeHands.length / 169) * 100).toFixed(1)}% do baralho
                  </span>
                </div>
              </div>

              {/* Hand Badges Grid */}
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 max-h-48 overflow-y-auto space-y-1">
                <span className="text-[10px] text-slate-500 font-mono uppercase block mb-1">
                  Mãos autorizadas para abertura / raise em {selectedPosition}:
                </span>
                <div className="flex flex-wrap gap-1">
                  {currentRangeHands.map(hand => {
                    const isPair = hand.length === 2 && hand[0] === hand[1];
                    const isSuited = hand.endsWith('s');
                    const badgeClass = isPair
                      ? 'bg-emerald-950 text-emerald-300 border-emerald-700 font-bold'
                      : isSuited
                      ? 'bg-cyan-950 text-cyan-300 border-cyan-700'
                      : 'bg-slate-900 text-slate-300 border-slate-800';

                    return (
                      <span key={hand} className={`px-2 py-0.5 rounded text-[11px] font-mono border ${badgeClass}`}>
                        {hand}
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB: Leak Detector & Financial Lines */}
      {activeSubTab === 'leak_finder' && (
        <div className="space-y-6">
          {/* Section 1: Money Leaks */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30">
                  <TrendingDown className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider">
                    Linhas de Maior Prejuízo Financeiro (Leaks Detectados)
                  </h3>
                  <p className="text-xs text-slate-400">
                    Situações recorrentes onde o bot está perdendo fichas de forma inconsistente com o GTO
                  </p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-lg bg-rose-950 text-rose-300 border border-rose-800 font-mono text-xs font-bold">
                {leaks.filter(l => l.severity !== 'RESOLVED').length} Leaks Ativos
              </span>
            </div>

            <div className="space-y-3">
              {leaks.map(leak => {
                const isResolved = leak.severity === 'RESOLVED';
                return (
                  <div
                    key={leak.id}
                    className={`p-4 rounded-xl border transition-all ${
                      isResolved
                        ? 'bg-slate-950/60 border-slate-800 opacity-75'
                        : leak.severity === 'CRITICAL'
                        ? 'bg-rose-950/20 border-rose-700/60 shadow-md'
                        : 'bg-amber-950/20 border-amber-700/60 shadow-md'
                    }`}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${
                            isResolved
                              ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                              : leak.severity === 'CRITICAL'
                              ? 'bg-rose-950 text-rose-300 border-rose-700'
                              : 'bg-amber-950 text-amber-300 border-amber-700'
                          }`}>
                            {isResolved ? 'CORRIGIDO' : leak.severity}
                          </span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-900 border border-slate-800 text-slate-400">
                            {leak.street}
                          </span>
                          <h4 className="font-bold text-xs text-slate-200">{leak.name}</h4>
                        </div>
                        <p className="text-xs text-slate-400 leading-relaxed max-w-3xl">
                          <strong className="text-slate-300">Causa Raiz: </strong>{leak.rootCause}
                        </p>
                        <p className="text-xs text-emerald-400 leading-relaxed max-w-3xl">
                          <strong>Solução Recomendada: </strong>{leak.suggestedFix}
                        </p>
                      </div>

                      <div className="flex sm:flex-col items-end justify-between sm:justify-center gap-2 shrink-0">
                        <div className="text-right font-mono">
                          <span className="text-[10px] text-slate-500 block">Impacto no Winrate</span>
                          <span className={`text-base font-black ${isResolved ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {leak.lossBbPer100} bb/100
                          </span>
                          <span className="text-[10px] text-slate-500 block">({leak.sampleSize} amostras)</span>
                        </div>

                        {!isResolved ? (
                          <button
                            onClick={() => handleApplyLeakFix(leak.id)}
                            className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition-colors shadow flex items-center gap-1 cursor-pointer"
                          >
                            <ShieldCheck className="w-3.5 h-3.5" />
                            <span>Aplicar Correção no Bot</span>
                          </button>
                        ) : (
                          <span className="text-xs font-mono text-emerald-400 flex items-center gap-1 font-bold">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Política Calibrada</span>
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Section 2: Most Profitable Lines */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <TrendingUp className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider">
                    Linhas Mais Lucrativas (Maior Extração de EV)
                  </h3>
                  <p className="text-xs text-slate-400">
                    Situações de jogo altamente lucrativas onde o bot está superando o field
                  </p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-lg bg-emerald-950 text-emerald-300 border border-emerald-800 font-mono text-xs font-bold">
                {profitableLines.length} Linhas de Alto Lucro
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {profitableLines.map(line => (
                <div key={line.id} className="p-4 rounded-xl bg-slate-950 border border-slate-800/90 space-y-2 hover:border-emerald-800/60 transition-all">
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-700">
                      {line.street}
                    </span>
                    <span className="text-sm font-mono font-black text-emerald-400">
                      +{line.winrateBbPer100} bb/100
                    </span>
                  </div>

                  <h4 className="font-bold text-xs text-slate-200">{line.name}</h4>
                  <p className="text-[11px] text-slate-400">{line.highlight}</p>

                  <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between font-mono text-[11px] text-slate-400">
                    <span>Taxa de Sucesso: <strong className="text-emerald-300">{line.successRatePct}%</strong></span>
                    <span>Lucro Total: <strong className="text-emerald-300">+{line.totalProfitBb} BB</strong></span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB: Site Performance & Profitable Situations */}
      {activeSubTab === 'site_analytics' && (
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <Coins className="w-4 h-4 text-emerald-400" />
                  <span>Análise de Lucratividade por Plataforma & Clube</span>
                </h3>
                <p className="text-xs text-slate-400">
                  Comparativo de winrate, ROI de torneios e volume de mãos por site/aplicativo de poker
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="pb-2.5 font-semibold">Plataforma / Clube</th>
                    <th className="pb-2.5 font-semibold">Modalidades</th>
                    <th className="pb-2.5 font-semibold">Volume (Mãos)</th>
                    <th className="pb-2.5 font-semibold">Winrate Real</th>
                    <th className="pb-2.5 font-semibold">All-in EV</th>
                    <th className="pb-2.5 font-semibold">ROI Torneios</th>
                    <th className="pb-2.5 font-semibold">Lucro Fichas</th>
                    <th className="pb-2.5 font-semibold">Diagnóstico</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {siteAnalytics.map(site => (
                    <tr key={site.siteName} className="hover:bg-slate-950/40">
                      <td className="py-3 font-bold text-slate-100">{site.siteName}</td>
                      <td className="py-3 text-slate-400">{site.gameTypes}</td>
                      <td className="py-3">{site.handsCount.toLocaleString('pt-BR')}</td>
                      <td className="py-3 font-bold text-emerald-400">+{site.winrateBb100} bb/100</td>
                      <td className="py-3 font-bold text-purple-400">+{site.allInEvBb100} bb/100</td>
                      <td className="py-3 font-bold text-cyan-400">+{site.roiPct}%</td>
                      <td className="py-3 font-black text-amber-300">+{site.profitChips.toLocaleString('pt-BR')}</td>
                      <td className="py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-sans font-bold ${
                          site.status === 'EXCELLENT'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-700'
                            : site.status === 'GOOD'
                            ? 'bg-cyan-950 text-cyan-300 border border-cyan-700'
                            : 'bg-slate-800 text-slate-300 border border-slate-700'
                        }`}>
                          {site.verdict}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB: Post-Flop Adaptive Calibration by Session */}
      {activeSubTab === 'postflop_adaptive' && (
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-cyan-400" />
                  <span>Ajuste Adaptativo de Frequências Pós-Flop por Sessão</span>
                </h3>
                <p className="text-xs text-slate-400">
                  Calibre as frequências de c-bet, barrels e defesas do bot com base no aprendizado das sessões recentes
                </p>
              </div>

              <button
                onClick={() => {
                  onNotify?.("CHECKPOINT DO CÉREBRO SALVO", "Pesos e frequências adaptativas gravados no modelo 'brain_weights.json'.", "INFO");
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition-colors shadow-sm cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Salvar Checkpoint (Pesos)</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Slider 1: C-Bet Dry IP */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 font-mono text-xs">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-200">C-Bet em Bordos Secos (Em Posição):</span>
                  <span className="text-cyan-400 font-bold">{postflopWeights.cbetDryIp}%</span>
                </div>
                <input
                  type="range"
                  min={40}
                  max={95}
                  value={postflopWeights.cbetDryIp}
                  onChange={(e) => setPostflopWeights({ ...postflopWeights, cbetDryIp: Number(e.target.value) })}
                  className="w-full accent-cyan-500 bg-slate-900 h-1.5 rounded cursor-pointer"
                />
                <span className="text-[10px] text-slate-500 block">Alta frequência exploratória em texturas A/K-high secas.</span>
              </div>

              {/* Slider 2: C-Bet Wet IP */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 font-mono text-xs">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-200">C-Bet em Bordos Conectados/Molhados:</span>
                  <span className="text-cyan-400 font-bold">{postflopWeights.cbetWetIp}%</span>
                </div>
                <input
                  type="range"
                  min={20}
                  max={70}
                  value={postflopWeights.cbetWetIp}
                  onChange={(e) => setPostflopWeights({ ...postflopWeights, cbetWetIp: Number(e.target.value) })}
                  className="w-full accent-cyan-500 bg-slate-900 h-1.5 rounded cursor-pointer"
                />
                <span className="text-[10px] text-slate-500 block">Controle de pote e proteção de range com equidade vulnerável.</span>
              </div>

              {/* Slider 3: C-Bet Multi-Way */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 font-mono text-xs">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-200">C-Bet em Potes Multi-Way (3+ Players):</span>
                  <span className="text-cyan-400 font-bold">{postflopWeights.cbetMultiway}%</span>
                </div>
                <input
                  type="range"
                  min={10}
                  max={50}
                  value={postflopWeights.cbetMultiway}
                  onChange={(e) => setPostflopWeights({ ...postflopWeights, cbetMultiway: Number(e.target.value) })}
                  className="w-full accent-cyan-500 bg-slate-900 h-1.5 rounded cursor-pointer"
                />
                <span className="text-[10px] text-slate-500 block">Reduzido para evitar queimar fichas sem equidade contra múltiplos oponentes.</span>
              </div>

              {/* Slider 4: River Bluff-Catch */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 font-mono text-xs">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-200">Limiar de Bluff-Catch no River:</span>
                  <span className="text-cyan-400 font-bold">{postflopWeights.riverBluffCatch}%</span>
                </div>
                <input
                  type="range"
                  min={15}
                  max={60}
                  value={postflopWeights.riverBluffCatch}
                  onChange={(e) => setPostflopWeights({ ...postflopWeights, riverBluffCatch: Number(e.target.value) })}
                  className="w-full accent-cyan-500 bg-slate-900 h-1.5 rounded cursor-pointer"
                />
                <span className="text-[10px] text-slate-500 block">Ajuste de over-fold contra a tendência de sub-blefe do field no river.</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Range Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full shadow-2xl p-5 space-y-4 text-slate-100">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Upload className="w-5 h-5 text-purple-400" />
                <h3 className="font-bold text-sm text-slate-100">Importar Ranges de Outro Sistema</h3>
              </div>
              <button onClick={() => setShowImportModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <p className="text-xs text-slate-400">
              Cole abaixo o JSON exportado do seu solver ou sistema externo com os ranges por posição:
            </p>

            <textarea
              rows={8}
              value={importJsonText}
              onChange={(e) => setImportJsonText(e.target.value)}
              placeholder={`{\n  "name": "Meu Range PKO Turbo 20BB",\n  "category": "PKO Bounty",\n  "stackBb": 20,\n  "positions": {\n    "UTG": ["AA", "KK", "QQ", "AKs"],\n    "BTN": ["AA", "KK", "QQ", "JJ", "AKs", "AKo", "76s"]\n  }\n}`}
              className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-emerald-300 placeholder-slate-600 focus:outline-none focus:border-purple-500"
            />

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => setShowImportModal(false)}
                className="px-3.5 py-1.5 rounded-lg border border-slate-700 text-slate-300 text-xs font-medium"
              >
                Cancelar
              </button>
              <button
                onClick={handleImportRangeJson}
                className="px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs shadow"
              >
                Alimentar Cérebro Agora
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Human Feedback Mistake Correction Modal */}
      {selectedHandForModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full shadow-2xl p-5 space-y-4 text-slate-100">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <ThumbsDown className="w-5 h-5 text-rose-400" />
                <div>
                  <h3 className="font-bold text-sm text-slate-100">Classificar Mão como Erro (-EV)</h3>
                  <span className="text-[11px] font-mono text-slate-400">
                    Mão: {selectedHandForModal.combo} ({selectedHandForModal.position}) • Ação: {selectedHandForModal.preflopAction}
                  </span>
                </div>
              </div>
              <button onClick={() => setSelectedHandForModal(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">
                  Qual seria a jogada matematicamente correta (Ação Recomendada)?
                </label>
                <select
                  value={correctionActionInput}
                  onChange={(e) => setCorrectionActionInput(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs font-mono text-amber-300 focus:outline-none focus:border-rose-500"
                >
                  <option value="Deveria ter dado Fold imediatamente">Fold Obrigatório pré-flop</option>
                  <option value="Deveria ter feito Open Raise 3.0x ou Fold (Limp é -EV)">Raise 3.0x (Eliminar Limp)</option>
                  <option value="Deveria ter aplicado 3-Bet Shove Direto">3-Bet Shove Direto (Re-steal)</option>
                  <option value="Deveria ter dado Check-Behind no Flop para controle de pote">Check-Behind Flop (Pot Control)</option>
                  <option value="Deveria ter Foldado no River contra o 3º Barril">Over-Fold no River</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">
                  Observações e Justificativa Humana para o Bot:
                </label>
                <textarea
                  rows={3}
                  value={correctionNoteInput}
                  onChange={(e) => setCorrectionNoteInput(e.target.value)}
                  placeholder="Ex: Call com mãos offsuit dominadas fora de posição contra jogador agressivo..."
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-rose-500"
                />
              </div>

              <div className="p-3 rounded-xl bg-rose-950/30 border border-rose-900/50 text-[11px] text-rose-300 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span>
                  O peso de <strong>{selectedHandForModal.combo}</strong> na posição <strong>{selectedHandForModal.position}</strong> será reduzido em <strong>-0.25</strong>. Se atingir zero, a mão será removida do range de abertura.
                </span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => setSelectedHandForModal(null)}
                className="px-3.5 py-1.5 rounded-lg border border-slate-700 text-slate-300 text-xs font-medium cursor-pointer"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleRateHandMistake(selectedHandForModal.id, correctionActionInput, correctionNoteInput)}
                className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shadow flex items-center gap-1.5 cursor-pointer"
              >
                <Check className="w-4 h-4" />
                <span>Salvar Avaliação & Recalibrar Range</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Lines of Play JSON Export Modal */}
      {showExportLinesModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 backdrop-blur-md p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full shadow-2xl p-6 space-y-4 text-slate-100 animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-purple-500/20 text-purple-400 border border-purple-500/30">
                  <Workflow className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-100">
                    Exportação: Win/Loss por Linha de Jogo (JSON)
                  </h3>
                  <p className="text-xs text-slate-400">
                    Estatísticas agregadas e histórico detalhado de mãos para importação no seu sistema externo de ranges
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowExportLinesModal(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Quick Metrics Strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-xs">
              <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-[10px] text-slate-500 block">Linhas Rastreadas</span>
                <span className="text-sm font-bold text-purple-300">{linesOfPlay.length} sequências</span>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-[10px] text-slate-500 block">Volume Total</span>
                <span className="text-sm font-bold text-slate-200">{linesOfPlay.reduce((acc, l) => acc + l.sampleSize, 0)} mãos</span>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-[10px] text-slate-500 block">Lucro Agregado</span>
                <span className="text-sm font-bold text-emerald-400">+{linesOfPlay.reduce((acc, l) => acc + l.totalProfitBb, 0).toFixed(1)} BB</span>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-[10px] text-slate-500 block">Mãos Detalhadas</span>
                <span className="text-sm font-bold text-cyan-300">
                  {linesOfPlay.reduce((acc, l) => acc + (l.playedHands?.length || 0), 0)} registradas
                </span>
              </div>
            </div>

            {/* Compatibility Note */}
            <div className="p-2.5 rounded-xl bg-purple-950/30 border border-purple-900/40 text-[11px] text-purple-300 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                <span>Compatibilidade: PioSolver, GTO Wizard Range Importer, Equilab, PokerRanger & Solvers Customizados</span>
              </span>
              <span className="font-mono text-[10px] bg-purple-900/60 px-2 py-0.5 rounded text-purple-200 border border-purple-700">
                v1.0 (Com Runouts & Combos)
              </span>
            </div>

            {/* JSON Code Viewer */}
            <div className="relative">
              <pre className="max-h-72 overflow-y-auto p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-[11px] font-mono text-emerald-400/90 leading-relaxed selection:bg-purple-900 selection:text-white">
                {exportedLinesJson}
              </pre>
            </div>

            {/* Modal Actions */}
            <div className="flex flex-wrap items-center justify-between gap-2.5 pt-3 border-t border-slate-800">
              <div className="text-[11px] text-slate-500 font-mono">
                Arquivo baixado como <strong className="text-slate-400">visualpilot_lines_of_play_export.json</strong>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(exportedLinesJson);
                    setCopiedExportJson(true);
                    setTimeout(() => setCopiedExportJson(false), 2000);
                    onNotify?.("JSON COPIADO", "Estrutura de linhas de jogo copiada para a área de transferência.", "INFO");
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold transition-colors cursor-pointer"
                >
                  {copiedExportJson ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedExportJson ? 'Copiado!' : 'Copiar JSON'}</span>
                </button>

                <button
                  onClick={() => {
                    const blob = new Blob([exportedLinesJson], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `visualpilot_lines_of_play_export_${new Date().toISOString().slice(0, 10)}.json`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    onNotify?.("DOWNLOAD REINICIADO", "Arquivo JSON gerado e salvo novamente no computador.", "INFO");
                  }}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition-colors shadow cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Baixar Arquivo .JSON</span>
                </button>

                <button
                  onClick={() => setShowExportLinesModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 text-xs font-medium hover:bg-slate-800 cursor-pointer"
                >
                  Fechar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
