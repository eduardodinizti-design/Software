import React, { useState, useMemo } from 'react';
import {
  Brain,
  Crosshair,
  TrendingUp,
  Coins,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Download,
  Copy,
  Check,
  SlidersHorizontal,
  Flame,
  Info,
  Layers,
  Zap,
  Play
} from 'lucide-react';
import { PreflopOpeningFrequencyDashboard } from './PreflopOpeningFrequencyDashboard';

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
const SUITS = [
  { symbol: '♠', name: 'spades', code: 's', color: 'text-slate-100', bg: 'bg-slate-800' },
  { symbol: '♥', name: 'hearts', code: 'h', color: 'text-rose-500', bg: 'bg-rose-950/40' },
  { symbol: '♦', name: 'diamonds', code: 'd', color: 'text-blue-400', bg: 'bg-blue-950/40' },
  { symbol: '♣', name: 'clubs', code: 'c', color: 'text-emerald-400', bg: 'bg-emerald-950/40' }
];

export interface HandStrategyData {
  hand: string;
  action: 'RAISE' | 'CALL' | 'FOLD' | 'ALL_IN';
  frequencies: { [action: string]: number };
  sizingBb?: number;
  evBb: number;
  category: 'VALUE_RAISE' | 'BLUFF_RAISE' | 'SPECULATIVE_CALL' | 'PURE_DEFENSE' | 'FOLD' | 'ALL_IN_PUSH';
  combos: number;
}

// Gera a matriz 13x13 canônica de 169 mãos
const build169Matrix = (): string[][] => {
  return RANKS.map((r1, i1) =>
    RANKS.map((r2, i2) => {
      if (i1 === i2) return `${r1}${r2}`;
      if (i1 < i2) return `${r1}${r2}s`;
      return `${r2}${r1}o`;
    })
  );
};

const MATRIX_169 = build169Matrix();

const getCombosCount = (hand: string): number => {
  if (hand.length === 2) return 6;
  if (hand.endsWith('s')) return 4;
  if (hand.endsWith('o')) return 12;
  return 0;
};

// Tabelas GTO 6-Max
const GTO_RFI_RANGES: Record<string, Record<string, { [action: string]: number }>> = {
  UTG: {
    'AA': { RAISE: 1.0 }, 'KK': { RAISE: 1.0 }, 'QQ': { RAISE: 1.0 }, 'JJ': { RAISE: 1.0 },
    'TT': { RAISE: 1.0 }, '99': { RAISE: 1.0 }, '88': { RAISE: 1.0 }, '77': { RAISE: 1.0 },
    '66': { RAISE: 0.8, FOLD: 0.2 }, '55': { RAISE: 0.6, FOLD: 0.4 }, '44': { RAISE: 0.4, FOLD: 0.6 },
    '33': { RAISE: 0.2, FOLD: 0.8 }, '22': { RAISE: 0.2, FOLD: 0.8 },
    'AKs': { RAISE: 1.0 }, 'AQs': { RAISE: 1.0 }, 'AJs': { RAISE: 1.0 }, 'ATs': { RAISE: 1.0 },
    'A9s': { RAISE: 0.8, FOLD: 0.2 }, 'A8s': { RAISE: 0.6, FOLD: 0.4 }, 'A7s': { RAISE: 0.4, FOLD: 0.6 },
    'A6s': { RAISE: 0.4, FOLD: 0.6 }, 'A5s': { RAISE: 1.0 }, 'A4s': { RAISE: 0.9, FOLD: 0.1 },
    'A3s': { RAISE: 0.7, FOLD: 0.3 }, 'A2s': { RAISE: 0.5, FOLD: 0.5 },
    'KQs': { RAISE: 1.0 }, 'KJs': { RAISE: 1.0 }, 'KTs': { RAISE: 1.0 }, 'K9s': { RAISE: 0.6, FOLD: 0.4 },
    'QJs': { RAISE: 1.0 }, 'QTs': { RAISE: 1.0 }, 'Q9s': { RAISE: 0.5, FOLD: 0.5 },
    'JTs': { RAISE: 1.0 }, 'J9s': { RAISE: 0.6, FOLD: 0.4 },
    'T9s': { RAISE: 1.0 }, '98s': { RAISE: 0.8, FOLD: 0.2 }, '87s': { RAISE: 0.6, FOLD: 0.4 },
    '76s': { RAISE: 0.5, FOLD: 0.5 }, '65s': { RAISE: 0.4, FOLD: 0.6 }, '54s': { RAISE: 0.3, FOLD: 0.7 },
    'AKo': { RAISE: 1.0 }, 'AQo': { RAISE: 1.0 }, 'AJo': { RAISE: 1.0 }, 'ATo': { RAISE: 0.5, FOLD: 0.5 },
    'KQo': { RAISE: 1.0 }, 'KJo': { RAISE: 0.5, FOLD: 0.5 },
  },
  MP: {
    'AA': { RAISE: 1.0 }, 'KK': { RAISE: 1.0 }, 'QQ': { RAISE: 1.0 }, 'JJ': { RAISE: 1.0 },
    'TT': { RAISE: 1.0 }, '99': { RAISE: 1.0 }, '88': { RAISE: 1.0 }, '77': { RAISE: 1.0 },
    '66': { RAISE: 1.0 }, '55': { RAISE: 0.8, FOLD: 0.2 }, '44': { RAISE: 0.6, FOLD: 0.4 },
    '33': { RAISE: 0.5, FOLD: 0.5 }, '22': { RAISE: 0.4, FOLD: 0.6 },
    'AKs': { RAISE: 1.0 }, 'AQs': { RAISE: 1.0 }, 'AJs': { RAISE: 1.0 }, 'ATs': { RAISE: 1.0 },
    'A9s': { RAISE: 1.0 }, 'A8s': { RAISE: 0.8, FOLD: 0.2 }, 'A7s': { RAISE: 0.7, FOLD: 0.3 },
    'A6s': { RAISE: 0.6, FOLD: 0.4 }, 'A5s': { RAISE: 1.0 }, 'A4s': { RAISE: 1.0 },
    'A3s': { RAISE: 0.8, FOLD: 0.2 }, 'A2s': { RAISE: 0.7, FOLD: 0.3 },
    'KQs': { RAISE: 1.0 }, 'KJs': { RAISE: 1.0 }, 'KTs': { RAISE: 1.0 }, 'K9s': { RAISE: 0.8, FOLD: 0.2 },
    'K8s': { RAISE: 0.5, FOLD: 0.5 },
    'QJs': { RAISE: 1.0 }, 'QTs': { RAISE: 1.0 }, 'Q9s': { RAISE: 0.8, FOLD: 0.2 },
    'JTs': { RAISE: 1.0 }, 'J9s': { RAISE: 0.8, FOLD: 0.2 }, 'J8s': { RAISE: 0.4, FOLD: 0.6 },
    'T9s': { RAISE: 1.0 }, 'T8s': { RAISE: 0.6, FOLD: 0.4 },
    '98s': { RAISE: 1.0 }, '97s': { RAISE: 0.5, FOLD: 0.5 },
    '87s': { RAISE: 0.9, FOLD: 0.1 }, '76s': { RAISE: 0.8, FOLD: 0.2 },
    '65s': { RAISE: 0.7, FOLD: 0.3 }, '54s': { RAISE: 0.5, FOLD: 0.5 },
    'AKo': { RAISE: 1.0 }, 'AQo': { RAISE: 1.0 }, 'AJo': { RAISE: 1.0 }, 'ATo': { RAISE: 0.8, FOLD: 0.2 },
    'KQo': { RAISE: 1.0 }, 'KJo': { RAISE: 0.8, FOLD: 0.2 }, 'KTo': { RAISE: 0.4, FOLD: 0.6 },
    'QJo': { RAISE: 0.7, FOLD: 0.3 }, 'QTo': { RAISE: 0.3, FOLD: 0.7 },
  },
  CO: {
    'AA': { RAISE: 1.0 }, 'KK': { RAISE: 1.0 }, 'QQ': { RAISE: 1.0 }, 'JJ': { RAISE: 1.0 },
    'TT': { RAISE: 1.0 }, '99': { RAISE: 1.0 }, '88': { RAISE: 1.0 }, '77': { RAISE: 1.0 },
    '66': { RAISE: 1.0 }, '55': { RAISE: 1.0 }, '44': { RAISE: 0.9, FOLD: 0.1 },
    '33': { RAISE: 0.8, FOLD: 0.2 }, '22': { RAISE: 0.7, FOLD: 0.3 },
    'AKs': { RAISE: 1.0 }, 'AQs': { RAISE: 1.0 }, 'AJs': { RAISE: 1.0 }, 'ATs': { RAISE: 1.0 },
    'A9s': { RAISE: 1.0 }, 'A8s': { RAISE: 1.0 }, 'A7s': { RAISE: 1.0 },
    'A6s': { RAISE: 0.9, FOLD: 0.1 }, 'A5s': { RAISE: 1.0 }, 'A4s': { RAISE: 1.0 },
    'A3s': { RAISE: 1.0 }, 'A2s': { RAISE: 0.9, FOLD: 0.1 },
    'KQs': { RAISE: 1.0 }, 'KJs': { RAISE: 1.0 }, 'KTs': { RAISE: 1.0 }, 'K9s': { RAISE: 1.0 },
    'K8s': { RAISE: 0.9, FOLD: 0.1 }, 'K7s': { RAISE: 0.7, FOLD: 0.3 }, 'K6s': { RAISE: 0.5, FOLD: 0.5 },
    'K5s': { RAISE: 0.5, FOLD: 0.5 },
    'QJs': { RAISE: 1.0 }, 'QTs': { RAISE: 1.0 }, 'Q9s': { RAISE: 1.0 }, 'Q8s': { RAISE: 0.8, FOLD: 0.2 },
    'Q7s': { RAISE: 0.5, FOLD: 0.5 },
    'JTs': { RAISE: 1.0 }, 'J9s': { RAISE: 1.0 }, 'J8s': { RAISE: 0.8, FOLD: 0.2 },
    'J7s': { RAISE: 0.5, FOLD: 0.5 },
    'T9s': { RAISE: 1.0 }, 'T8s': { RAISE: 1.0 }, 'T7s': { RAISE: 0.6, FOLD: 0.4 },
    '98s': { RAISE: 1.0 }, '97s': { RAISE: 0.8, FOLD: 0.2 }, '96s': { RAISE: 0.5, FOLD: 0.5 },
    '87s': { RAISE: 1.0 }, '86s': { RAISE: 0.8, FOLD: 0.2 },
    '76s': { RAISE: 1.0 }, '75s': { RAISE: 0.6, FOLD: 0.4 },
    '65s': { RAISE: 1.0 }, '64s': { RAISE: 0.5, FOLD: 0.5 },
    '54s': { RAISE: 0.9, FOLD: 0.1 }, '43s': { RAISE: 0.5, FOLD: 0.5 },
    'AKo': { RAISE: 1.0 }, 'AQo': { RAISE: 1.0 }, 'AJo': { RAISE: 1.0 }, 'ATo': { RAISE: 1.0 },
    'A9o': { RAISE: 0.8, FOLD: 0.2 }, 'A8o': { RAISE: 0.4, FOLD: 0.6 },
    'KQo': { RAISE: 1.0 }, 'KJo': { RAISE: 1.0 }, 'KTo': { RAISE: 1.0 }, 'K9o': { RAISE: 0.4, FOLD: 0.6 },
    'QJo': { RAISE: 1.0 }, 'QTo': { RAISE: 0.9, FOLD: 0.1 }, 'Q9o': { RAISE: 0.3, FOLD: 0.7 },
    'JTo': { RAISE: 0.9, FOLD: 0.1 }, 'J9o': { RAISE: 0.4, FOLD: 0.6 },
    'T9o': { RAISE: 0.4, FOLD: 0.6 },
  },
  BTN: {
    'AA': { RAISE: 1.0 }, 'KK': { RAISE: 1.0 }, 'QQ': { RAISE: 1.0 }, 'JJ': { RAISE: 1.0 },
    'TT': { RAISE: 1.0 }, '99': { RAISE: 1.0 }, '88': { RAISE: 1.0 }, '77': { RAISE: 1.0 },
    '66': { RAISE: 1.0 }, '55': { RAISE: 1.0 }, '44': { RAISE: 1.0 }, '33': { RAISE: 1.0 }, '22': { RAISE: 1.0 },
    'AKs': { RAISE: 1.0 }, 'AQs': { RAISE: 1.0 }, 'AJs': { RAISE: 1.0 }, 'ATs': { RAISE: 1.0 },
    'A9s': { RAISE: 1.0 }, 'A8s': { RAISE: 1.0 }, 'A7s': { RAISE: 1.0 }, 'A6s': { RAISE: 1.0 },
    'A5s': { RAISE: 1.0 }, 'A4s': { RAISE: 1.0 }, 'A3s': { RAISE: 1.0 }, 'A2s': { RAISE: 1.0 },
    'KQs': { RAISE: 1.0 }, 'KJs': { RAISE: 1.0 }, 'KTs': { RAISE: 1.0 }, 'K9s': { RAISE: 1.0 },
    'K8s': { RAISE: 1.0 }, 'K7s': { RAISE: 1.0 }, 'K6s': { RAISE: 1.0 },
    'K5s': { RAISE: 1.0 }, 'K4s': { RAISE: 1.0 }, 'K3s': { RAISE: 0.9, FOLD: 0.1 },
    'K2s': { RAISE: 0.8, FOLD: 0.2 },
    'QJs': { RAISE: 1.0 }, 'QTs': { RAISE: 1.0 }, 'Q9s': { RAISE: 1.0 }, 'Q8s': { RAISE: 1.0 },
    'Q7s': { RAISE: 1.0 }, 'Q6s': { RAISE: 1.0 }, 'Q5s': { RAISE: 0.9, FOLD: 0.1 },
    'Q4s': { RAISE: 0.8, FOLD: 0.2 }, 'Q3s': { RAISE: 0.7, FOLD: 0.3 }, 'Q2s': { RAISE: 0.6, FOLD: 0.4 },
    'JTs': { RAISE: 1.0 }, 'J9s': { RAISE: 1.0 }, 'J8s': { RAISE: 1.0 }, 'J7s': { RAISE: 1.0 },
    'J6s': { RAISE: 0.8, FOLD: 0.2 }, 'J5s': { RAISE: 0.7, FOLD: 0.3 }, 'J4s': { RAISE: 0.6, FOLD: 0.4 },
    'T9s': { RAISE: 1.0 }, 'T8s': { RAISE: 1.0 }, 'T7s': { RAISE: 1.0 }, 'T6s': { RAISE: 0.8, FOLD: 0.2 },
    'T5s': { RAISE: 0.6, FOLD: 0.4 },
    '98s': { RAISE: 1.0 }, '97s': { RAISE: 1.0 }, '96s': { RAISE: 1.0 }, '95s': { RAISE: 0.6, FOLD: 0.4 },
    '87s': { RAISE: 1.0 }, '86s': { RAISE: 1.0 }, '85s': { RAISE: 0.9, FOLD: 0.1 }, '84s': { RAISE: 0.5, FOLD: 0.5 },
    '76s': { RAISE: 1.0 }, '75s': { RAISE: 1.0 }, '74s': { RAISE: 0.6, FOLD: 0.4 },
    '65s': { RAISE: 1.0 }, '64s': { RAISE: 0.9, FOLD: 0.1 }, '63s': { RAISE: 0.5, FOLD: 0.5 },
    '54s': { RAISE: 1.0 }, '53s': { RAISE: 0.8, FOLD: 0.2 }, '52s': { RAISE: 0.4, FOLD: 0.6 },
    '43s': { RAISE: 0.8, FOLD: 0.2 }, '32s': { RAISE: 0.4, FOLD: 0.6 },
    'AKo': { RAISE: 1.0 }, 'AQo': { RAISE: 1.0 }, 'AJo': { RAISE: 1.0 }, 'ATo': { RAISE: 1.0 },
    'A9o': { RAISE: 1.0 }, 'A8o': { RAISE: 1.0 }, 'A7o': { RAISE: 1.0 },
    'A6o': { RAISE: 0.8, FOLD: 0.2 }, 'A5o': { RAISE: 0.9, FOLD: 0.1 }, 'A4o': { RAISE: 0.8, FOLD: 0.2 },
    'A3o': { RAISE: 0.7, FOLD: 0.3 }, 'A2o': { RAISE: 0.6, FOLD: 0.4 },
    'KQo': { RAISE: 1.0 }, 'KJo': { RAISE: 1.0 }, 'KTo': { RAISE: 1.0 }, 'K9o': { RAISE: 1.0 },
    'K8o': { RAISE: 0.8, FOLD: 0.2 }, 'K7o': { RAISE: 0.6, FOLD: 0.4 }, 'K6o': { RAISE: 0.4, FOLD: 0.6 },
    'QJo': { RAISE: 1.0 }, 'QTo': { RAISE: 1.0 }, 'Q9o': { RAISE: 1.0 }, 'Q8o': { RAISE: 0.7, FOLD: 0.3 },
    'JTo': { RAISE: 1.0 }, 'J9o': { RAISE: 1.0 }, 'J8o': { RAISE: 0.6, FOLD: 0.4 },
    'T9o': { RAISE: 1.0 }, 'T8o': { RAISE: 0.6, FOLD: 0.4 },
    '98o': { RAISE: 0.9, FOLD: 0.1 }, '87o': { RAISE: 0.7, FOLD: 0.3 }, '76o': { RAISE: 0.5, FOLD: 0.5 },
  },
  SB: {
    'AA': { RAISE: 1.0 }, 'KK': { RAISE: 1.0 }, 'QQ': { RAISE: 1.0 }, 'JJ': { RAISE: 1.0 },
    'TT': { RAISE: 1.0 }, '99': { RAISE: 1.0 }, '88': { RAISE: 1.0 }, '77': { RAISE: 1.0 },
    '66': { RAISE: 1.0 }, '55': { RAISE: 0.9, FOLD: 0.1 }, '44': { RAISE: 0.8, FOLD: 0.2 },
    '33': { RAISE: 0.7, FOLD: 0.3 }, '22': { RAISE: 0.6, FOLD: 0.4 },
    'AKs': { RAISE: 1.0 }, 'AQs': { RAISE: 1.0 }, 'AJs': { RAISE: 1.0 }, 'ATs': { RAISE: 1.0 },
    'A9s': { RAISE: 1.0 }, 'A8s': { RAISE: 1.0 }, 'A7s': { RAISE: 1.0 }, 'A6s': { RAISE: 0.8, FOLD: 0.2 },
    'A5s': { RAISE: 1.0 }, 'A4s': { RAISE: 1.0 }, 'A3s': { RAISE: 0.9, FOLD: 0.1 }, 'A2s': { RAISE: 0.8, FOLD: 0.2 },
    'KQs': { RAISE: 1.0 }, 'KJs': { RAISE: 1.0 }, 'KTs': { RAISE: 1.0 }, 'K9s': { RAISE: 1.0 },
    'K8s': { RAISE: 0.8, FOLD: 0.2 }, 'K7s': { RAISE: 0.7, FOLD: 0.3 }, 'K6s': { RAISE: 0.6, FOLD: 0.4 },
    'QJs': { RAISE: 1.0 }, 'QTs': { RAISE: 1.0 }, 'Q9s': { RAISE: 1.0 }, 'Q8s': { RAISE: 0.8, FOLD: 0.2 },
    'JTs': { RAISE: 1.0 }, 'J9s': { RAISE: 1.0 }, 'J8s': { RAISE: 0.8, FOLD: 0.2 },
    'T9s': { RAISE: 1.0 }, 'T8s': { RAISE: 0.9, FOLD: 0.1 },
    '98s': { RAISE: 1.0 }, '97s': { RAISE: 0.8, FOLD: 0.2 },
    '87s': { RAISE: 1.0 }, '86s': { RAISE: 0.7, FOLD: 0.3 },
    '76s': { RAISE: 1.0 }, '65s': { RAISE: 0.8, FOLD: 0.2 }, '54s': { RAISE: 0.7, FOLD: 0.3 },
    'AKo': { RAISE: 1.0 }, 'AQo': { RAISE: 1.0 }, 'AJo': { RAISE: 1.0 }, 'ATo': { RAISE: 1.0 },
    'A9o': { RAISE: 0.8, FOLD: 0.2 }, 'A8o': { RAISE: 0.6, FOLD: 0.4 },
    'KQo': { RAISE: 1.0 }, 'KJo': { RAISE: 1.0 }, 'KTo': { RAISE: 0.8, FOLD: 0.2 },
    'QJo': { RAISE: 1.0 }, 'QTo': { RAISE: 0.7, FOLD: 0.3 },
    'JTo': { RAISE: 0.8, FOLD: 0.2 }, 'T9o': { RAISE: 0.6, FOLD: 0.4 },
  }
};

// BB Defesa vs BTN
const BB_DEFENSE_VS_BTN: Record<string, { [action: string]: number }> = {
  'AA': { RAISE: 1.0 }, 'KK': { RAISE: 1.0 }, 'QQ': { RAISE: 1.0 }, 'JJ': { RAISE: 0.9, CALL: 0.1 },
  'TT': { RAISE: 0.6, CALL: 0.4 }, '99': { CALL: 0.9, RAISE: 0.1 }, '88': { CALL: 1.0 },
  '77': { CALL: 1.0 }, '66': { CALL: 1.0 }, '55': { CALL: 1.0 }, '44': { CALL: 1.0 },
  '33': { CALL: 0.8, FOLD: 0.2 }, '22': { CALL: 0.7, FOLD: 0.3 },
  'AKs': { RAISE: 1.0 }, 'AQs': { RAISE: 1.0 }, 'AJs': { RAISE: 0.8, CALL: 0.2 },
  'ATs': { CALL: 0.8, RAISE: 0.2 }, 'A9s': { CALL: 1.0 }, 'A8s': { CALL: 1.0 },
  'A7s': { CALL: 1.0 }, 'A6s': { CALL: 1.0 }, 'A5s': { RAISE: 0.6, CALL: 0.4 },
  'A4s': { RAISE: 0.5, CALL: 0.5 }, 'A3s': { CALL: 0.8, RAISE: 0.2 }, 'A2s': { CALL: 0.8, RAISE: 0.2 },
  'KQs': { RAISE: 0.7, CALL: 0.3 }, 'KJs': { CALL: 0.8, RAISE: 0.2 }, 'KTs': { CALL: 1.0 },
  'K9s': { CALL: 1.0 }, 'K8s': { CALL: 1.0 }, 'K7s': { CALL: 0.8, FOLD: 0.2 },
  'QJs': { CALL: 0.8, RAISE: 0.2 }, 'QTs': { CALL: 1.0 }, 'Q9s': { CALL: 1.0 },
  'JTs': { CALL: 1.0 }, 'J9s': { CALL: 1.0 }, 'T9s': { CALL: 1.0 }, 'T8s': { CALL: 1.0 },
  '98s': { CALL: 1.0 }, '97s': { CALL: 0.9, FOLD: 0.1 }, '87s': { CALL: 1.0 },
  '76s': { CALL: 1.0 }, '65s': { CALL: 1.0 }, '54s': { CALL: 0.9, FOLD: 0.1 },
  'AKo': { RAISE: 1.0 }, 'AQo': { RAISE: 0.8, CALL: 0.2 }, 'AJo': { CALL: 0.8, RAISE: 0.2 },
  'ATo': { CALL: 1.0 }, 'A9o': { CALL: 0.9, FOLD: 0.1 }, 'A8o': { CALL: 0.7, FOLD: 0.3 },
  'KQo': { CALL: 0.8, RAISE: 0.2 }, 'KJo': { CALL: 1.0 }, 'KTo': { CALL: 0.9, FOLD: 0.1 },
  'QJo': { CALL: 1.0 }, 'QTo': { CALL: 0.8, FOLD: 0.2 }, 'JTo': { CALL: 0.8, FOLD: 0.2 },
};

// Nash Equilibrium 15 BB
const NASH_15BB_BTN: Record<string, { [action: string]: number }> = {
  'AA': { ALL_IN: 1.0 }, 'KK': { ALL_IN: 1.0 }, 'QQ': { ALL_IN: 1.0 }, 'JJ': { ALL_IN: 1.0 },
  'TT': { ALL_IN: 1.0 }, '99': { ALL_IN: 1.0 }, '88': { ALL_IN: 1.0 }, '77': { ALL_IN: 1.0 },
  '66': { ALL_IN: 1.0 }, '55': { ALL_IN: 1.0 }, '44': { ALL_IN: 1.0 }, '33': { ALL_IN: 1.0 }, '22': { ALL_IN: 1.0 },
  'AKs': { ALL_IN: 1.0 }, 'AQs': { ALL_IN: 1.0 }, 'AJs': { ALL_IN: 1.0 }, 'ATs': { ALL_IN: 1.0 },
  'A9s': { ALL_IN: 1.0 }, 'A8s': { ALL_IN: 1.0 }, 'A7s': { ALL_IN: 1.0 }, 'A6s': { ALL_IN: 1.0 },
  'A5s': { ALL_IN: 1.0 }, 'A4s': { ALL_IN: 1.0 }, 'A3s': { ALL_IN: 1.0 }, 'A2s': { ALL_IN: 1.0 },
  'KQs': { ALL_IN: 1.0 }, 'KJs': { ALL_IN: 1.0 }, 'KTs': { ALL_IN: 1.0 }, 'K9s': { ALL_IN: 1.0 },
  'K8s': { ALL_IN: 1.0 }, 'K7s': { ALL_IN: 0.8, FOLD: 0.2 }, 'K6s': { ALL_IN: 0.7, FOLD: 0.3 },
  'QJs': { ALL_IN: 1.0 }, 'QTs': { ALL_IN: 1.0 }, 'Q9s': { ALL_IN: 1.0 }, 'Q8s': { ALL_IN: 0.8, FOLD: 0.2 },
  'JTs': { ALL_IN: 1.0 }, 'J9s': { ALL_IN: 1.0 }, 'J8s': { ALL_IN: 0.8, FOLD: 0.2 },
  'T9s': { ALL_IN: 1.0 }, 'T8s': { ALL_IN: 0.8, FOLD: 0.2 },
  '98s': { ALL_IN: 1.0 }, '87s': { ALL_IN: 0.8, FOLD: 0.2 },
  'AKo': { ALL_IN: 1.0 }, 'AQo': { ALL_IN: 1.0 }, 'AJo': { ALL_IN: 1.0 }, 'ATo': { ALL_IN: 1.0 },
  'A9o': { ALL_IN: 1.0 }, 'A8o': { ALL_IN: 0.9, FOLD: 0.1 }, 'A7o': { ALL_IN: 0.8, FOLD: 0.2 },
  'KQo': { ALL_IN: 1.0 }, 'KJo': { ALL_IN: 1.0 }, 'KTo': { ALL_IN: 0.9, FOLD: 0.1 },
  'QJo': { ALL_IN: 1.0 }, 'QTo': { ALL_IN: 0.8, FOLD: 0.2 },
};

export const PreflopDecisionEngineInspector: React.FC<{
  onNotify?: (title: string, message: string, severity: 'INFO' | 'WARN' | 'CRITICAL') => void;
}> = ({ onNotify }) => {
  // Configurações do Spot
  const [selectedPosition, setSelectedPosition] = useState<string>('CO');
  const [selectedSpot, setSelectedSpot] = useState<'RFI' | 'VS_RFI' | 'VS_3BET' | 'PUSH_FOLD'>('RFI');
  const [selectedStackBb, setSelectedStackBb] = useState<number>(100);
  const [vsPosition, setVsPosition] = useState<string>('UTG');

  // Mão do Hero
  const [heroCard1, setHeroCard1] = useState<string>('Ah');
  const [heroCard2, setHeroCard2] = useState<string>('Kd');
  const [selectedMatrixHand, setSelectedMatrixHand] = useState<string | null>('AKo');

  // Simulação Monte Carlo rápida
  const [simulationRunning, setSimulationRunning] = useState<boolean>(false);
  const [simResults, setSimResults] = useState<{
    trials: number;
    distribution: Record<string, number>;
    raisePct: number;
    callPct: number;
    foldPct: number;
    allInPct: number;
  } | null>(null);

  const [copiedPython, setCopiedPython] = useState<boolean>(false);

  // Calcula formato canônico da mão do Hero
  const canonicalHeroHand = useMemo<string>(() => {
    if (!heroCard1 || !heroCard2) return 'AKo';
    const r1 = heroCard1[0].toUpperCase();
    const s1 = heroCard1[1].toLowerCase();
    const r2 = heroCard2[0].toUpperCase();
    const s2 = heroCard2[1].toLowerCase();

    if (r1 === r2) return `${r1}${r2}`;

    const v1 = 14 - RANKS.indexOf(r1);
    const v2 = 14 - RANKS.indexOf(r2);
    const high = v1 > v2 ? r1 : r2;
    const low = v1 > v2 ? r2 : r1;
    const suffix = s1 === s2 ? 's' : 'o';
    return `${high}${low}${suffix}`;
  }, [heroCard1, heroCard2]);

  // Carrega tabela de estratégia conforme os seletores
  const currentRangeTable = useMemo<Record<string, { [action: string]: number }>>(() => {
    if (selectedSpot === 'PUSH_FOLD' || selectedStackBb <= 18) {
      return NASH_15BB_BTN;
    }
    if (selectedSpot === 'VS_RFI') {
      return selectedPosition === 'BB' ? BB_DEFENSE_VS_BTN : GTO_RFI_RANGES['BTN'];
    }
    if (selectedSpot === 'VS_3BET') {
      return BB_DEFENSE_VS_BTN;
    }
    return GTO_RFI_RANGES[selectedPosition] || GTO_RFI_RANGES['CO'];
  }, [selectedPosition, selectedSpot, selectedStackBb]);

  // Gera dados completos para as 169 mãos
  const matrixHandData = useMemo<Record<string, HandStrategyData>>(() => {
    const data: Record<string, HandStrategyData> = {};

    for (let r = 0; r < 13; r++) {
      for (let c = 0; c < 13; c++) {
        const hand = MATRIX_169[r][c];
        const combos = getCombosCount(hand);
        const entry = currentRangeTable[hand];

        if (!entry) {
          data[hand] = {
            hand,
            action: 'FOLD',
            frequencies: { FOLD: 1.0 },
            sizingBb: 0,
            evBb: 0,
            category: 'FOLD',
            combos
          };
          continue;
        }

        const dominantAction = Object.keys(entry).reduce((a, b) =>
          entry[a] > entry[b] ? a : b
        ) as 'RAISE' | 'CALL' | 'FOLD' | 'ALL_IN';

        let cat: HandStrategyData['category'] = 'FOLD';
        let sizing = 0;
        let ev = 0;

        if (dominantAction === 'ALL_IN') {
          cat = 'ALL_IN_PUSH';
          sizing = selectedStackBb;
          ev = 1.45;
        } else if (dominantAction === 'RAISE') {
          if (['AA', 'KK', 'QQ', 'JJ', 'AKs', 'AKo'].includes(hand)) {
            cat = 'VALUE_RAISE';
            ev = 3.2;
          } else if (hand.startsWith('A') && hand.endsWith('s') && ['2', '3', '4', '5'].includes(hand[1])) {
            cat = 'BLUFF_RAISE';
            ev = 0.65;
          } else {
            cat = 'VALUE_RAISE';
            ev = 1.1;
          }
          sizing = selectedPosition === 'BTN' ? 2.0 : 2.3;
        } else if (dominantAction === 'CALL') {
          cat = hand.endsWith('s') ? 'SPECULATIVE_CALL' : 'PURE_DEFENSE';
          sizing = 2.0;
          ev = 0.85;
        }

        data[hand] = {
          hand,
          action: dominantAction,
          frequencies: entry,
          sizingBb: sizing,
          evBb: ev,
          category: cat,
          combos
        };
      }
    }
    return data;
  }, [currentRangeTable, selectedStackBb, selectedPosition]);

  // Estatísticas do Range
  const rangeStats = useMemo(() => {
    let raiseCombos = 0;
    let callCombos = 0;
    let foldCombos = 0;
    let allinCombos = 0;

    Object.values(matrixHandData).forEach(strat => {
      const rf = strat.frequencies['RAISE'] || 0;
      const cf = strat.frequencies['CALL'] || 0;
      const ff = strat.frequencies['FOLD'] || 0;
      const af = strat.frequencies['ALL_IN'] || 0;

      raiseCombos += strat.combos * rf;
      callCombos += strat.combos * cf;
      foldCombos += strat.combos * ff;
      allinCombos += strat.combos * af;
    });

    const totalCombos = 1326;
    const playedCombos = Math.round(raiseCombos + callCombos + allinCombos);

    return {
      playedCombos,
      percentage: Number(((playedCombos / totalCombos) * 100).toFixed(1)),
      raisePercent: Number(((raiseCombos / totalCombos) * 100).toFixed(1)),
      callPercent: Number(((callCombos / totalCombos) * 100).toFixed(1)),
      foldPercent: Number(((foldCombos / totalCombos) * 100).toFixed(1)),
      allinPercent: Number(((allinCombos / totalCombos) * 100).toFixed(1))
    };
  }, [matrixHandData]);

  // Recomendação do Hero
  const heroRecommendation = useMemo(() => {
    const hand = canonicalHeroHand;
    const strat = matrixHandData[hand];

    if (!strat || strat.action === 'FOLD') {
      return {
        action: 'FOLD',
        actionLabel: 'Fold Puro',
        sizing: '0.0 BB',
        badge: 'bg-slate-800 text-slate-300 border-slate-700',
        ev: '+0.00 BB',
        rationale: `A mão ${hand} não tem equidade suficiente e está fora do range GTO em ${selectedPosition}.`,
        mix: { FOLD: 1.0 },
        inRange: false
      };
    }

    let actionLabel = 'Fold';
    let badge = 'bg-slate-800 text-slate-300 border-slate-700';

    if (strat.action === 'RAISE') {
      actionLabel = `Raise para ${strat.sizingBb || 2.3} BB`;
      badge = 'bg-rose-950 text-rose-300 border-rose-700 shadow-rose-950/50';
    } else if (strat.action === 'CALL') {
      actionLabel = `Call (Pagar 2.0 BB)`;
      badge = 'bg-emerald-950 text-emerald-300 border-emerald-700 shadow-emerald-950/50';
    } else if (strat.action === 'ALL_IN') {
      actionLabel = `Push All-in (${selectedStackBb} BB)`;
      badge = 'bg-amber-950 text-amber-300 border-amber-600 shadow-amber-950/50';
    }

    const freqStr = Object.entries(strat.frequencies)
      .map(([act, freq]) => `${act}: ${Math.round(freq * 100)}%`)
      .join(' / ');

    return {
      action: strat.action,
      actionLabel,
      sizing: `${strat.sizingBb || 0} BB`,
      badge,
      ev: `+${strat.evBb.toFixed(2)} BB`,
      rationale: `Estratégia GTO recomendada: ${actionLabel} (${freqStr}). Combos disponíveis: ${strat.combos}.`,
      mix: strat.frequencies,
      inRange: true
    };
  }, [canonicalHeroHand, matrixHandData, selectedPosition, selectedStackBb]);

  // Mão em Foco do Inspecionador
  const inspectedHand = selectedMatrixHand ? matrixHandData[selectedMatrixHand] : null;

  // Botão para gerar mão aleatória do Hero
  const pickRandomHeroHand = () => {
    const deck: string[] = [];
    RANKS.forEach(r => {
      SUITS.forEach(s => deck.push(`${r}${s.code}`));
    });

    const idx1 = Math.floor(Math.random() * deck.length);
    const card1 = deck.splice(idx1, 1)[0];
    const idx2 = Math.floor(Math.random() * deck.length);
    const card2 = deck.splice(idx2, 1)[0];

    setHeroCard1(card1);
    setHeroCard2(card2);
  };

  // Simulação Monte Carlo rápida de 500 mãos
  const runMonteCarloSimulation = () => {
    setSimulationRunning(true);
    setTimeout(() => {
      const counts: Record<string, number> = { RAISE: 0, CALL: 0, FOLD: 0, ALL_IN: 0 };
      const trials = 500;

      for (let i = 0; i < trials; i++) {
        // Escolhe duas cartas aleatórias
        const deck: string[] = [];
        RANKS.forEach(r => {
          SUITS.forEach(s => deck.push(`${r}${s.code}`));
        });
        const c1 = deck.splice(Math.floor(Math.random() * deck.length), 1)[0];
        const c2 = deck.splice(Math.floor(Math.random() * deck.length), 1)[0];

        const r1 = c1[0].toUpperCase();
        const s1 = c1[1].toLowerCase();
        const r2 = c2[0].toUpperCase();
        const s2 = c2[1].toLowerCase();

        let h = `${r1}${r2}`;
        if (r1 !== r2) {
          const v1 = 14 - RANKS.indexOf(r1);
          const v2 = 14 - RANKS.indexOf(r2);
          const high = v1 > v2 ? r1 : r2;
          const low = v1 > v2 ? r2 : r1;
          h = `${high}${low}${s1 === s2 ? 's' : 'o'}`;
        }

        const strat = matrixHandData[h];
        const act = strat ? strat.action : 'FOLD';
        counts[act] = (counts[act] || 0) + 1;
      }

      setSimResults({
        trials,
        distribution: counts,
        raisePct: Number(((counts.RAISE / trials) * 100).toFixed(1)),
        callPct: Number(((counts.CALL / trials) * 100).toFixed(1)),
        foldPct: Number(((counts.FOLD / trials) * 100).toFixed(1)),
        allInPct: Number(((counts.ALL_IN / trials) * 100).toFixed(1))
      });
      setSimulationRunning(false);
      onNotify?.("SIMULAÇÃO CONCLUÍDA", `500 mãos simuladas em ${selectedPosition} (${selectedSpot}).`, "INFO");
    }, 350);
  };

  const copyPythonCode = () => {
    const code = `
from visualpilot.pppoker.preflop_decision_engine import PreflopDecisionEngine

engine = PreflopDecisionEngine()

# Avaliar mão do Hero: ${heroCard1}, ${heroCard2}
result = engine.evaluate_hand(
    hero_cards=["${heroCard1}", "${heroCard2}"],
    position="${selectedPosition}",
    spot="${selectedSpot}",
    stack_bb=${selectedStackBb}.0,
    vs_position="${vsPosition}"
)

print(f"Decisão: {result.recommended_action} ({result.recommended_sizing_label})")
print(f"Frequências: {result.strategy_mix}")
print(f"EV Estimado: {result.ev_bb} BB")
`.trim();
    navigator.clipboard.writeText(code);
    setCopiedPython(true);
    setTimeout(() => setCopiedPython(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-80 h-full bg-gradient-to-l from-rose-500/10 via-amber-500/5 to-transparent pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30">
                <Brain className="w-5 h-5" />
              </span>
              <h2 className="text-xl font-bold text-slate-100 tracking-tight">
                Motor de Decisão Pré-Flop (Tabelas GTO por Posição)
              </h2>
            </div>
            <p className="text-xs text-slate-400 max-w-3xl">
              Matriz completa de 169 mãos canônicas (1326 combos) calibrada com solvers GTO modernos (6-Max/9-Max). Resolução de ações puras e mistas ponderadas para <strong>Open Raise (RFI)</strong>, <strong>Defesa vs RFI</strong>, <strong>3-Bet / 4-Bet</strong> e <strong>Push/Fold Nash Equilibrium</strong>.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={copyPythonCode}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 transition-colors shadow-sm cursor-pointer"
            >
              {copiedPython ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
              <span>{copiedPython ? 'Copiado!' : 'Copiar Snippet Python'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Interactive Opening Frequency Dashboard: Ideal GTO vs Bot Current Frequency */}
      <PreflopOpeningFrequencyDashboard onNotify={onNotify} />

      {/* Control Panel: Position, Spot, Stack and Opponent */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Position Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-mono">
              Posição do Hero:
            </span>
            <div className="flex items-center gap-1">
              {['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB'].map(pos => (
                <button
                  key={pos}
                  onClick={() => setSelectedPosition(pos)}
                  className={`px-3 py-1 rounded-lg text-xs font-bold font-mono transition-all cursor-pointer ${
                    selectedPosition === pos
                      ? 'bg-rose-500 text-white shadow-md shadow-rose-500/30'
                      : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {pos}
                </button>
              ))}
            </div>
          </div>

          {/* Spot Scenario Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-mono">
              Spot:
            </span>
            <div className="flex items-center gap-1">
              {[
                { id: 'RFI', label: 'Open Raise (RFI)' },
                { id: 'VS_RFI', label: 'vs Open (Cold Call / 3-Bet)' },
                { id: 'VS_3BET', label: 'vs 3-Bet (4-Bet / Call)' },
                { id: 'PUSH_FOLD', label: 'Push/Fold (Nash 15 BB)' }
              ].map(s => (
                <button
                  key={s.id}
                  onClick={() => setSelectedSpot(s.id as any)}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                    selectedSpot === s.id
                      ? 'bg-cyan-600 text-white shadow-md shadow-cyan-600/30'
                      : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Stack Depth */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider font-mono">
              Stack:
            </span>
            <div className="flex items-center gap-1">
              {[100, 50, 25, 15].map(stk => (
                <button
                  key={stk}
                  onClick={() => setSelectedStackBb(stk)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
                    selectedStackBb === stk
                      ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30'
                      : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {stk} BB
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Range Statistics Highlights Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-3 border-t border-slate-800/80 font-mono text-xs">
          <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[10px] text-slate-400 block uppercase">Frequência Total</span>
            <span className="text-base font-black text-rose-400">{rangeStats.percentage}%</span>
            <span className="text-[10px] text-slate-500 block">({rangeStats.playedCombos} / 1326 combos)</span>
          </div>

          <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[10px] text-rose-400 block uppercase">Raise Freq</span>
            <span className="text-base font-black text-rose-400">{rangeStats.raisePercent}%</span>
            <span className="text-[10px] text-slate-500 block">Abertura / 3-Bet</span>
          </div>

          <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[10px] text-emerald-400 block uppercase">Call Freq</span>
            <span className="text-base font-black text-emerald-400">{rangeStats.callPercent}%</span>
            <span className="text-[10px] text-slate-500 block">Cold Call / Flat</span>
          </div>

          <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[10px] text-amber-400 block uppercase">All-in Freq</span>
            <span className="text-base font-black text-amber-400">{rangeStats.allinPercent}%</span>
            <span className="text-[10px] text-slate-500 block">Push Nash</span>
          </div>

          <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[10px] text-slate-400 block uppercase">Fold Freq</span>
            <span className="text-base font-black text-slate-300">{rangeStats.foldPercent}%</span>
            <span className="text-[10px] text-slate-500 block">Descarte Puro</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Left Matrix 13x13 (7 cols) + Right Live Hero Hand & Solver (5 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: 13x13 GTO Matrix (7 cols) */}
        <div className="lg:col-span-7 space-y-3">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono">
                  Matriz Canônica GTO 13×13 ({selectedPosition} · {selectedSpot})
                </span>
              </div>
              <div className="flex items-center gap-3 text-[11px] font-mono">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded bg-rose-600 inline-block" />
                  <span className="text-slate-300">Raise</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded bg-emerald-600 inline-block" />
                  <span className="text-slate-300">Call</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded bg-amber-500 inline-block" />
                  <span className="text-slate-300">Shove</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded bg-slate-800 inline-block" />
                  <span className="text-slate-500">Fold</span>
                </div>
              </div>
            </div>

            {/* 13x13 Matrix Canvas */}
            <div className="overflow-x-auto select-none">
              <div className="grid grid-cols-13 gap-1 min-w-[520px]">
                {MATRIX_169.map((row, rIdx) =>
                  row.map((hand, cIdx) => {
                    const data = matrixHandData[hand];
                    const isSelected = selectedMatrixHand === hand;
                    const isHeroHand = canonicalHeroHand === hand;

                    // Frequências para renderizar split gradient ou cor única
                    const rf = data?.frequencies['RAISE'] || 0;
                    const cf = data?.frequencies['CALL'] || 0;
                    const af = data?.frequencies['ALL_IN'] || 0;
                    const ff = data?.frequencies['FOLD'] || 0;

                    let bgStyle: React.CSSProperties = {};
                    if (data?.action === 'FOLD') {
                      bgStyle = { backgroundColor: '#0f172a' };
                    } else if (af > 0.5) {
                      bgStyle = { backgroundColor: '#d97706' };
                    } else if (rf > 0.9) {
                      bgStyle = { backgroundColor: '#e11d48' };
                    } else if (cf > 0.9) {
                      bgStyle = { backgroundColor: '#059669' };
                    } else {
                      // Mixed gradient
                      const rPct = Math.round(rf * 100);
                      const cPct = Math.round(cf * 100);
                      bgStyle = {
                        background: `linear-gradient(to right, #e11d48 0%, #e11d48 ${rPct}%, #059669 ${rPct}%, #059669 ${rPct + cPct}%, #0f172a ${rPct + cPct}%, #0f172a 100%)`
                      };
                    }

                    return (
                      <button
                        key={hand}
                        type="button"
                        onClick={() => setSelectedMatrixHand(hand)}
                        style={bgStyle}
                        className={`h-9 flex flex-col items-center justify-center rounded transition-all cursor-pointer relative group text-[10px] font-mono font-bold ${
                          isSelected
                            ? 'ring-2 ring-white z-20 scale-105 shadow-lg'
                            : 'hover:scale-105 hover:z-10 border border-slate-900/40'
                        }`}
                        title={`${hand}: ${data?.action} (Combos: ${data?.combos})`}
                      >
                        {isHeroHand && (
                          <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-cyan-400 ring-2 ring-cyan-300 animate-ping" />
                        )}
                        <span
                          className={`leading-none ${
                            data?.action === 'FOLD' ? 'text-slate-600' : 'text-white drop-shadow'
                          }`}
                        >
                          {hand}
                        </span>
                      </button>
                    );
                  })
                )}
              </div>
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono pt-1">
              <span>Diagonal: Pares (AA-22)</span>
              <span>Superior-Direita: Suited (s)</span>
              <span>Inferior-Esquerda: Offsuit (o)</span>
            </div>
          </div>

          {/* Hand Details Card when a Cell is Clicked */}
          {inspectedHand && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-2 font-mono text-xs">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-slate-950 text-white font-black text-sm border border-slate-700">
                    {inspectedHand.hand}
                  </span>
                  <span className="text-slate-400">
                    {inspectedHand.hand.length === 2 ? 'Par de Bolso' : inspectedHand.hand.endsWith('s') ? 'Mão Suited' : 'Mão Offsuit'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">Combinações:</span>
                  <span className="font-bold text-emerald-400">{inspectedHand.combos} combos</span>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Ação Dominante</span>
                  <span className="font-bold text-slate-200">{inspectedHand.action}</span>
                </div>

                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Sizing Indicado</span>
                  <span className="font-bold text-cyan-300">{inspectedHand.sizingBb ? `${inspectedHand.sizingBb} BB` : 'N/A'}</span>
                </div>

                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">EV Estimado</span>
                  <span className="font-bold text-emerald-400">+{inspectedHand.evBb} BB</span>
                </div>

                <div className="p-2 rounded bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">Categoria</span>
                  <span className="font-bold text-amber-300 text-[11px] truncate">{inspectedHand.category}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Hero Live Hand & Real-Time GTO Evaluator (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Hero Hand Interactive Inspector */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Crosshair className="w-4 h-4 text-rose-400" />
                <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider font-mono">
                  Avaliador em Tempo Real do Hero
                </h3>
              </div>
              <button
                type="button"
                onClick={pickRandomHeroHand}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 transition-colors cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span>Mão Aleatória</span>
              </button>
            </div>

            {/* Hero Hole Cards Visual Display */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-around">
              {/* Card 1 */}
              <div className="flex flex-col items-center gap-1.5">
                <span className="text-[10px] uppercase font-mono text-slate-400 font-bold">Carta 1</span>
                <div className="w-16 h-24 rounded-xl bg-slate-900 border-2 border-slate-700 shadow-xl flex flex-col justify-between p-2">
                  <div className="flex justify-between items-center">
                    <span className="font-black font-mono text-lg text-white">{heroCard1[0]}</span>
                    <span className="text-sm">
                      {heroCard1[1] === 's' ? '♠' : heroCard1[1] === 'h' ? '♥' : heroCard1[1] === 'd' ? '♦' : '♣'}
                    </span>
                  </div>
                  <div className="text-center text-xl">
                    {heroCard1[1] === 's' ? '♠' : heroCard1[1] === 'h' ? '♥' : heroCard1[1] === 'd' ? '♦' : '♣'}
                  </div>
                  <div className="text-right text-[10px] text-slate-400 font-mono uppercase">{heroCard1}</div>
                </div>
              </div>

              <div className="text-slate-600 font-black text-2xl">+</div>

              {/* Card 2 */}
              <div className="flex flex-col items-center gap-1.5">
                <span className="text-[10px] uppercase font-mono text-slate-400 font-bold">Carta 2</span>
                <div className="w-16 h-24 rounded-xl bg-slate-900 border-2 border-slate-700 shadow-xl flex flex-col justify-between p-2">
                  <div className="flex justify-between items-center">
                    <span className="font-black font-mono text-lg text-white">{heroCard2[0]}</span>
                    <span className="text-sm">
                      {heroCard2[1] === 's' ? '♠' : heroCard2[1] === 'h' ? '♥' : heroCard2[1] === 'd' ? '♦' : '♣'}
                    </span>
                  </div>
                  <div className="text-center text-xl">
                    {heroCard2[1] === 's' ? '♠' : heroCard2[1] === 'h' ? '♥' : heroCard2[1] === 'd' ? '♦' : '♣'}
                  </div>
                  <div className="text-right text-[10px] text-slate-400 font-mono uppercase">{heroCard2}</div>
                </div>
              </div>

              {/* Equated Canonical Hand Pill */}
              <div className="flex flex-col items-center gap-1">
                <span className="text-[10px] font-mono text-slate-400">Canônico:</span>
                <span className="px-3 py-1 rounded-xl bg-cyan-950 border border-cyan-800 text-cyan-300 font-mono font-black text-base shadow">
                  {canonicalHeroHand}
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  {getCombosCount(canonicalHeroHand)} combos
                </span>
              </div>
            </div>

            {/* Quick Hand Card Selectors */}
            <div className="space-y-1.5 font-mono text-xs">
              <span className="text-[10px] text-slate-400 uppercase font-bold">Seletor Rápido de Cartas:</span>
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={heroCard1}
                  onChange={(e) => setHeroCard1(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-slate-200 text-xs font-mono"
                >
                  {['Ah', 'As', 'Ad', 'Ac', 'Kh', 'Ks', 'Kd', 'Qh', 'Qs', 'Jh', 'Th', '9h', '8h', '7h'].map(c => (
                    <option key={c} value={c}>Carta 1: {c}</option>
                  ))}
                </select>

                <select
                  value={heroCard2}
                  onChange={(e) => setHeroCard2(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-slate-200 text-xs font-mono"
                >
                  {['Kd', 'Ks', 'Kh', 'Kc', 'Qd', 'Jd', 'Td', '9d', '8d', '7d', '6d', '5d', '4d', '2c'].map(c => (
                    <option key={c} value={c}>Carta 2: {c}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* GTO Solver Decision Output */}
            <div className={`p-4 rounded-xl border-2 space-y-3 ${heroRecommendation.badge}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Zap className="w-5 h-5 text-amber-400" />
                  <span className="font-bold text-xs uppercase tracking-wider font-mono">
                    Recomendação GTO
                  </span>
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono font-black bg-black/40">
                  {heroRecommendation.ev}
                </span>
              </div>

              <div className="space-y-1">
                <div className="text-xl font-black font-mono tracking-tight">
                  {heroRecommendation.actionLabel}
                </div>
                <p className="text-xs text-slate-300 leading-snug">
                  {heroRecommendation.rationale}
                </p>
              </div>

              {/* Frequencies breakdown bar */}
              <div className="space-y-1 pt-1 font-mono text-[10px]">
                <div className="flex items-center justify-between text-slate-400">
                  <span>Distribuição Ponderada:</span>
                  <span>
                    {Object.entries(heroRecommendation.mix)
                      .map(([act, f]) => `${act}: ${Math.round(f * 100)}%`)
                      .join(' | ')}
                  </span>
                </div>
                <div className="h-2 rounded-full overflow-hidden flex bg-slate-900 border border-slate-800">
                  {Object.entries(heroRecommendation.mix).map(([act, f]) => {
                    const color = act === 'RAISE' ? 'bg-rose-500' : act === 'CALL' ? 'bg-emerald-500' : act === 'ALL_IN' ? 'bg-amber-500' : 'bg-slate-700';
                    return (
                      <div
                        key={act}
                        style={{ width: `${f * 100}%` }}
                        className={`h-full ${color}`}
                        title={`${act}: ${Math.round(f * 100)}%`}
                      />
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Monte Carlo Quick Simulation */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2">
                <Flame className="w-4 h-4 text-amber-400" />
                <span className="font-bold text-xs text-slate-200 uppercase tracking-wider font-mono">
                  Simulador de Mãos Aleatórias (500 Mãos)
                </span>
              </div>
              <button
                type="button"
                onClick={runMonteCarloSimulation}
                disabled={simulationRunning}
                className="flex items-center gap-1 px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold text-xs transition-colors cursor-pointer disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5" />
                <span>{simulationRunning ? 'Simulando...' : 'Rodar Teste'}</span>
              </button>
            </div>

            {simResults ? (
              <div className="space-y-2 font-mono text-xs">
                <div className="grid grid-cols-4 gap-1.5 text-center">
                  <div className="p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-rose-400 block">RAISE</span>
                    <span className="font-black text-rose-400">{simResults.raisePct}%</span>
                    <span className="text-[9px] text-slate-500 block">({simResults.distribution.RAISE})</span>
                  </div>
                  <div className="p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-emerald-400 block">CALL</span>
                    <span className="font-black text-emerald-400">{simResults.callPct}%</span>
                    <span className="text-[9px] text-slate-500 block">({simResults.distribution.CALL})</span>
                  </div>
                  <div className="p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-amber-400 block">SHOVE</span>
                    <span className="font-black text-amber-400">{simResults.allInPct}%</span>
                    <span className="text-[9px] text-slate-500 block">({simResults.distribution.ALL_IN})</span>
                  </div>
                  <div className="p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">FOLD</span>
                    <span className="font-black text-slate-300">{simResults.foldPct}%</span>
                    <span className="text-[9px] text-slate-500 block">({simResults.distribution.FOLD})</span>
                  </div>
                </div>
                <p className="text-[11px] text-slate-400 leading-snug">
                  Distribuição estocástica compatível com a frequência teórica calculada pelo solver GTO para {selectedPosition}.
                </p>
              </div>
            ) : (
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
                <span>Clique em "Rodar Teste" para testar 500 mãos contra a estratégia GTO de {selectedPosition}.</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
