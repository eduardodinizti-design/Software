import React, { useState, useEffect, useRef } from 'react';
import {
  Download,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Crosshair,
  FileCode2,
  Terminal,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Sparkles,
  MousePointerClick,
  ChevronRight,
  ShieldCheck,
  Eye,
  FileText,
  Clock,
  Coins,
  Move,
  Sliders,
  Play,
  FileSpreadsheet,
  AlertOctagon,
  RefreshCw,
  Search,
  Filter,
  Activity,
  Volume2,
  VolumeX,
  Bell,
  BellRing,
  X,
  Send,
  Radio,
  Mail,
  MessageSquare,
  Timer,
  Check,
  ExternalLink,
  ShieldAlert,
  Cpu,
  CheckSquare,
  FileCheck,
  Gauge,
  Zap,
  Shuffle,
  BarChart3,
  TrendingDown,
  TrendingUp,
  PlayCircle,
  StopCircle,
  Pause,
  Copy,
  Plus,
  Trash2,
  Globe,
  Smartphone,
  AtSign,
  Hash,
  SlidersHorizontal,
  Repeat,
  RotateCcw,
  Infinity,
  Camera,
  Target,
  Image as ImageIcon,
  Server,
  Flame,
  Brain,
  Wrench,
  BookOpen,
  Gamepad2,
  Hand,
  HardDrive
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine
} from 'recharts';
import { MultiTableGrid } from './components/MultiTableGrid';
import { CardRecognitionInspector } from './components/CardRecognitionInspector';
import { DeploymentGuide } from './components/DeploymentGuide';
import { HeroActionInspector } from './components/HeroActionInspector';
import { TableNumericalOcrInspector } from './components/TableNumericalOcrInspector';
import { PreflopDecisionEngineInspector } from './components/PreflopDecisionEngineInspector';
import { PostflopGtoInspector } from './components/PostflopGtoInspector';
import { BotBrainEvolutionInspector } from './components/BotBrainEvolutionInspector';
import { GhostSpectatorInspector } from './components/GhostSpectatorInspector';
import { TournamentChipsProfitEstimator } from './components/TournamentChipsProfitEstimator';
import { MonthlyRoiRechartsReport } from './components/MonthlyRoiRechartsReport';
import { UserManualPdfViewer } from './components/UserManualPdfViewer';
import { ManualVisualPilot } from './components/ManualVisualPilot';
import { InstallerDownloadCenter } from './components/InstallerDownloadCenter';
import { AppCleanHeader } from './components/AppCleanHeader';
import { AppNavigationSidebar, MainNavArea } from './components/AppNavigationSidebar';
import { OverviewDashboard } from './components/OverviewDashboard';
import { OcrEventsFeed } from './components/OcrEventsFeed';
import { HotkeyOverlay } from './components/HotkeyOverlay';



interface SubRegion {
  local_box: [number, number, number, number];
  absolute_box: [number, number, number, number];
}

interface TournamentRecord {
  index: number;
  name_label: string;
  name_read: string;
  buyin: string | null;
  raw_buyin_text: string | null;
  start_time: string | null;
  game_format: string;
  status: string;
  eligible: boolean;
  rejection_reasons: string[];
  raw_lines: string[];
  complete: boolean;
  clip_reason: string | null;
  local_box: [number, number, number, number];
  click_point_local: [number, number];
  crop_file: string;
  sub_regions: {
    name: SubRegion;
    buyin_prize: SubRegion;
    start_time: SubRegion;
    status: SubRegion;
  };
}

interface AuditLogRow {
  timestamp_iso: string;
  session_name: string;
  event_type: string;
  status: 'SUCCESS' | 'ABORTED' | 'ERROR' | 'HALT' | 'ESCALATED' | 'RECOVERY' | 'SKIPPED' | 'ANOMALY';
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

interface CamouflageStrategy {
  id: 'A' | 'B';
  name: string;
  speed: 'fast' | 'natural' | 'slow';
  delayMinMs: number;
  delayMaxMs: number;
  applyJitter: boolean;
}

const INITIAL_LOG_ROWS: AuditLogRow[] = [
  {
    timestamp_iso: "2026-10-31T22:42:05Z",
    session_name: "Sessão Matinal 01",
    event_type: "CLICK_SUCCESS",
    status: "SUCCESS",
    tournament_name: "CORUJAO HYPER PKO10K",
    card_index: "2",
    buyin_chips: "50",
    target_abs_x: "904",
    target_abs_y: "1142",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "845.0",
    details: "[TESTE_AB: VARIANTE_A - \"Estratégia A (Furtiva / Humana)\"] Despachado com sucesso via PyAutoGUI (Perfil: natural, Reação: 450ms, Movimento: 300ms, Pressão: 95ms, Total: 845.0ms)"
  },
  {
    timestamp_iso: "2026-10-31T22:42:15Z",
    session_name: "Sessão Matinal 01",
    event_type: "CLICK_SUCCESS",
    status: "SUCCESS",
    tournament_name: "CORUJAO HYPER PKO10K",
    card_index: "2",
    buyin_chips: "50",
    target_abs_x: "905",
    target_abs_y: "1143",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "465.0",
    details: "[TESTE_AB: VARIANTE_B - \"Estratégia B (Agressiva / Rápida)\"] Despachado com sucesso via PyAutoGUI (Perfil: fast, Reação: 240ms, Movimento: 160ms, Pressão: 65ms, Total: 465.0ms)"
  },
  {
    timestamp_iso: "2026-10-31T22:42:25Z",
    session_name: "Sessão Matinal 01",
    event_type: "CLICK_SUCCESS",
    status: "SUCCESS",
    tournament_name: "CORUJAO HYPER PKO10K",
    card_index: "2",
    buyin_chips: "50",
    target_abs_x: "903",
    target_abs_y: "1141",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "912.4",
    details: "[TESTE_AB: VARIANTE_A - \"Estratégia A (Furtiva / Humana)\"] Despachado com sucesso via PyAutoGUI (Perfil: natural, Reação: 510ms, Movimento: 310ms, Pressão: 92ms, Total: 912.4ms)"
  },
  {
    timestamp_iso: "2026-10-31T22:42:35Z",
    session_name: "Sessão Matinal 01",
    event_type: "CLICK_SUCCESS",
    status: "SUCCESS",
    tournament_name: "CORUJAO HYPER PKO10K",
    card_index: "2",
    buyin_chips: "50",
    target_abs_x: "906",
    target_abs_y: "1144",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "430.8",
    details: "[TESTE_AB: VARIANTE_B - \"Estratégia B (Agressiva / Rápida)\"] Despachado com sucesso via PyAutoGUI (Perfil: fast, Reação: 210ms, Movimento: 155ms, Pressão: 65ms, Total: 430.8ms)"
  },
  {
    timestamp_iso: "2026-10-31T22:42:45Z",
    session_name: "Sessão Matinal 01",
    event_type: "CLICK_SUCCESS",
    status: "SUCCESS",
    tournament_name: "CORUJAO HYPER PKO10K",
    card_index: "2",
    buyin_chips: "50",
    target_abs_x: "904",
    target_abs_y: "1142",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "789.2",
    details: "[TESTE_AB: VARIANTE_A - \"Estratégia A (Furtiva / Humana)\"] Despachado com sucesso via PyAutoGUI (Perfil: natural, Reação: 400ms, Movimento: 295ms, Pressão: 94ms, Total: 789.2ms)"
  },
  {
    timestamp_iso: "2026-10-31T22:42:55Z",
    session_name: "Sessão Matinal 01",
    event_type: "CLICK_SUCCESS",
    status: "SUCCESS",
    tournament_name: "CORUJAO HYPER PKO10K",
    card_index: "2",
    buyin_chips: "50",
    target_abs_x: "905",
    target_abs_y: "1143",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "488.5",
    details: "[TESTE_AB: VARIANTE_B - \"Estratégia B (Agressiva / Rápida)\"] Despachado com sucesso via PyAutoGUI (Perfil: fast, Reação: 260ms, Movimento: 162ms, Pressão: 66ms, Total: 488.5ms)"
  },
  {
    timestamp_iso: "2026-10-31T22:43:05Z",
    session_name: "Sessão Matinal 01",
    event_type: "CLICK_SUCCESS",
    status: "SUCCESS",
    tournament_name: "CORUJAO HYPER PKO10K",
    card_index: "2",
    buyin_chips: "50",
    target_abs_x: "903",
    target_abs_y: "1140",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "860.1",
    details: "[TESTE_AB: VARIANTE_A - \"Estratégia A (Furtiva / Humana)\"] Despachado com sucesso via PyAutoGUI (Perfil: natural, Reação: 470ms, Movimento: 301ms, Pressão: 89ms, Total: 860.1ms)"
  },
  {
    timestamp_iso: "2026-10-31T22:43:15Z",
    session_name: "Sessão Matinal 01",
    event_type: "CLICK_SUCCESS",
    status: "SUCCESS",
    tournament_name: "CORUJAO HYPER PKO10K",
    card_index: "2",
    buyin_chips: "50",
    target_abs_x: "907",
    target_abs_y: "1145",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "412.3",
    details: "[TESTE_AB: VARIANTE_B - \"Estratégia B (Agressiva / Rápida)\"] Despachado com sucesso via PyAutoGUI (Perfil: fast, Reação: 195ms, Movimento: 153ms, Pressão: 64ms, Total: 412.3ms)"
  },
  {
    timestamp_iso: "2026-10-31T22:41:29Z",
    session_name: "Sessão Matinal 01",
    event_type: "CLICK_SUCCESS",
    status: "SUCCESS",
    tournament_name: "CORUJAO HYPER PKO10K",
    card_index: "2",
    buyin_chips: "50",
    target_abs_x: "904",
    target_abs_y: "1142",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "284.2",
    details: "Clique despachado com sucesso via pyautogui.moveTo (Bézier cúbica com aceleração humana assimétrica, jitter neuromuscular ±1.5px)"
  },
  {
    timestamp_iso: "2026-10-31T22:41:35Z",
    session_name: "Sessão Matinal 01",
    event_type: "CLICK_ABORTED",
    status: "ABORTED",
    tournament_name: "FREEZEOUT 30K GTD",
    card_index: "1",
    buyin_chips: "200",
    target_abs_x: "904",
    target_abs_y: "961",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "",
    details: "Torneio inelegível: buy-in 200 excede teto autorizado de 50 fichas"
  },
  {
    timestamp_iso: "2026-10-31T22:41:42Z",
    session_name: "Sessão Matinal 01",
    event_type: "RESOLUTION_CHANGED",
    status: "ABORTED",
    tournament_name: "CORUJAO HYPER PKO10K",
    card_index: "2",
    buyin_chips: "50",
    target_abs_x: "-",
    target_abs_y: "-",
    win_left: "500",
    win_top: "150",
    win_width: "1400",
    win_height: "450",
    duration_ms: "",
    details: "Janela deformada: W/H = 3.11 (1400x450). Proporção retrato rompida."
  },
  {
    timestamp_iso: "2026-10-31T22:41:50Z",
    session_name: "Sessão Matinal 01",
    event_type: "WINDOW_CLOSED",
    status: "ABORTED",
    tournament_name: "CORUJAO HYPER PKO10K",
    card_index: "2",
    buyin_chips: "50",
    target_abs_x: "-",
    target_abs_y: "-",
    win_left: "0",
    win_top: "0",
    win_width: "0",
    win_height: "0",
    duration_ms: "",
    details: "Janela do PPPoker não foi encontrada no desktop. Clique cancelado."
  },
  {
    timestamp_iso: "2026-10-31T22:42:20Z",
    session_name: "Sessão Matinal 01",
    event_type: "SYSTEM_HALT",
    status: "HALT",
    tournament_name: "-",
    card_index: "-",
    buyin_chips: "-",
    target_abs_x: "-",
    target_abs_y: "-",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "",
    details: "Inatividade detectada: nenhum heartbeat recebido por 30.0s (possível congelamento de software). Ações bloqueadas preventivamente."
  },
  {
    timestamp_iso: "2026-10-31T22:47:20Z",
    session_name: "Sessão Matinal 01",
    event_type: "ESCALATION_ALERT_SENT",
    status: "ESCALATED",
    tournament_name: "-",
    card_index: "-",
    buyin_chips: "-",
    target_abs_x: "-",
    target_abs_y: "-",
    win_left: "500",
    win_top: "150",
    win_width: "787",
    win_height: "1470",
    duration_ms: "148.6",
    details: "Sistema em SYSTEM_HALT por mais de 300.0s (5.0 min). Alerta remoto despachado via webhook (https://discord.com/api/webhooks/130100***)."
  }
];

const TOURNAMENTS_DATA: TournamentRecord[] = [
  {
    index: 0,
    name_label: "TORNEIO DIAMANTE",
    name_read: "DIAMANTE 59 3MIN",
    buyin: null,
    raw_buyin_text: null,
    start_time: "10/31 16:00",
    game_format: "MTT",
    status: "ineligible",
    eligible: false,
    rejection_reasons: ["buyin_not_found_or_unreadable"],
    raw_lines: ["Premiacao: 10,000", "TORNEIO", "DIAMANTE 59 3min", "Horariodeinicio:10/31 16:00"],
    complete: true,
    clip_reason: null,
    local_box: [30, 545, 748, 170],
    click_point_local: [404.0, 630.0],
    crop_file: "card_00.png",
    sub_regions: {
      name: { local_box: [150, 582, 165, 85], absolute_box: [150, 582, 165, 85] },
      buyin_prize: { local_box: [322, 572, 299, 44], absolute_box: [322, 572, 299, 44] },
      start_time: { local_box: [322, 650, 314, 41], absolute_box: [322, 650, 314, 41] },
      status: { local_box: [628, 579, 135, 102], absolute_box: [628, 579, 135, 102] }
    }
  },
  {
    index: 1,
    name_label: "FREEZEOUT 30K GTD",
    name_read: "FREEZEOUT30KGTD",
    buyin: "200",
    raw_buyin_text: "Buy-in: 2 200",
    start_time: "10/31 18:00",
    game_format: "MTT",
    status: "ineligible",
    eligible: false,
    rejection_reasons: ["buyin_exceeds_limit_50.0"],
    raw_lines: ["EARLY", "FREEZEOUT30KGTD", "Buy-in: 2 200", "30 20min", "PPST NLH", "Horariodeinicio:10/31 18:00"],
    complete: true,
    clip_reason: null,
    local_box: [30, 727, 748, 168],
    click_point_local: [404.0, 811.0],
    crop_file: "card_01.png",
    sub_regions: {
      name: { local_box: [150, 764, 165, 84], absolute_box: [150, 764, 165, 84] },
      buyin_prize: { local_box: [322, 754, 299, 44], absolute_box: [322, 754, 299, 44] },
      start_time: { local_box: [322, 831, 314, 40], absolute_box: [322, 831, 314, 40] },
      status: { local_box: [628, 761, 135, 101], absolute_box: [628, 761, 135, 101] }
    }
  },
  {
    index: 2,
    name_label: "CORUJAO HYPER PKO10K",
    name_read: "CORUJAOHYPERPKO10K",
    buyin: "50",
    raw_buyin_text: "Buy-in: 50",
    start_time: "10/31 22:00",
    game_format: "MTT PKO",
    status: "open",
    eligible: true,
    rejection_reasons: [],
    raw_lines: ["CORUJAOHYPERPKO10K", "Buy-in: 50", "PKO 10min", "PPST NLH", "Horariodeinicio:10/31 22:00"],
    complete: true,
    clip_reason: null,
    local_box: [30, 908, 748, 168],
    click_point_local: [404.0, 992.0],
    crop_file: "card_02.png",
    sub_regions: {
      name: { local_box: [150, 945, 165, 84], absolute_box: [150, 945, 165, 84] },
      buyin_prize: { local_box: [322, 935, 299, 44], absolute_box: [322, 935, 299, 44] },
      start_time: { local_box: [322, 1012, 314, 40], absolute_box: [322, 1012, 314, 40] },
      status: { local_box: [628, 942, 135, 101], absolute_box: [628, 942, 135, 101] }
    }
  },
  {
    index: 3,
    name_label: "OMAHA - 6 (MESA 1)",
    name_read: "JACKPOT OMAHA-6",
    buyin: null,
    raw_buyin_text: null,
    start_time: null,
    game_format: "Cash Game (Blinds)",
    status: "ineligible",
    eligible: false,
    rejection_reasons: ["cash_game_not_mtt", "buyin_not_found_or_unreadable"],
    raw_lines: ["JACKPOT OMAHA-6", "Blinds: 1/2", "0/6 01:00:00", "PL06", "PF"],
    complete: true,
    clip_reason: null,
    local_box: [30, 1088, 748, 169],
    click_point_local: [404.0, 1172.5],
    crop_file: "card_03.png",
    sub_regions: {
      name: { local_box: [150, 1125, 165, 84], absolute_box: [150, 1125, 165, 84] },
      buyin_prize: { local_box: [322, 1115, 299, 44], absolute_box: [322, 1115, 299, 44] },
      start_time: { local_box: [322, 1193, 314, 41], absolute_box: [322, 1193, 314, 41] },
      status: { local_box: [628, 1122, 135, 101], absolute_box: [628, 1122, 135, 101] }
    }
  },
  {
    index: 4,
    name_label: "OMAHA - 6 (MESA 2)",
    name_read: "JACKPOT OMAHA-6",
    buyin: null,
    raw_buyin_text: null,
    start_time: null,
    game_format: "Cash Game (Blinds)",
    status: "ineligible",
    eligible: false,
    rejection_reasons: ["cash_game_not_mtt", "buyin_not_found_or_unreadable"],
    raw_lines: ["JACKPOT OMAHA-6", "Blinds: 1/2", "0/6 01:00:00", "PL06", "PF"],
    complete: true,
    clip_reason: null,
    local_box: [30, 1269, 748, 168],
    click_point_local: [404.0, 1353.0],
    crop_file: "card_04.png",
    sub_regions: {
      name: { local_box: [150, 1306, 165, 84], absolute_box: [150, 1306, 165, 84] },
      buyin_prize: { local_box: [322, 1296, 299, 44], absolute_box: [322, 1296, 299, 44] },
      start_time: { local_box: [322, 1373, 314, 40], absolute_box: [322, 1373, 314, 40] },
      status: { local_box: [628, 1303, 135, 101], absolute_box: [628, 1303, 135, 101] }
    }
  }
];

interface ToastAlert {
  id: string;
  title: string;
  message: string;
  eventType: 'SYSTEM_HALT' | 'WINDOW_CLOSED' | 'RESOLUTION_CHANGED' | 'SYSTEM_RESUMED' | 'ESCALATION_ALERT_SENT' | 'CLICK_SUCCESS' | 'PREFLIGHT_CHECK';
  severity: 'CRITICAL' | 'WARN' | 'INFO';
  timestamp: string;
  actionLabel?: string;
  onAction?: () => void;
}

function playSynthesizedAlarm(type: 'CRITICAL' | 'WARN' | 'SUCCESS' | 'ESCALATION' | 'INFO') {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();

    if (type === 'ESCALATION') {
      // Tom de alerta de escalada crítica (> 5 min): 3 bips agudos duplos urgentes (1046Hz -> 784Hz)
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sawtooth';

      osc.frequency.setValueAtTime(1046.5, now);
      osc.frequency.setValueAtTime(783.99, now + 0.1);
      osc.frequency.setValueAtTime(1046.5, now + 0.22);
      osc.frequency.setValueAtTime(783.99, now + 0.32);
      osc.frequency.setValueAtTime(1174.66, now + 0.44);

      gain.gain.setValueAtTime(0.24, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.7);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.7);
    } else if (type === 'CRITICAL') {
      // Tom de emergência pulsado: 880Hz -> 587Hz alternado com dente de serra
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sawtooth';

      osc.frequency.setValueAtTime(880, now);
      osc.frequency.setValueAtTime(587.33, now + 0.12);
      osc.frequency.setValueAtTime(880, now + 0.24);
      osc.frequency.setValueAtTime(587.33, now + 0.36);

      gain.gain.setValueAtTime(0.18, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.55);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.55);
    } else if (type === 'WARN') {
      // Tom de aviso suave: 620Hz
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(620, now);
      gain.gain.setValueAtTime(0.14, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.28);
    } else if (type === 'INFO') {
      // Tom de informação: bipe duplo suave ascendente (440Hz -> 880Hz)
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.setValueAtTime(880, now + 0.08);
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.22);
    } else {
      // Tom de sucesso
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(523.25, now);
      osc.frequency.setValueAtTime(659.25, now + 0.09);
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.3);
    }
  } catch {
    // Silently continue if audio context is blocked by browser policy
  }
}

function maskWebhook(url: string): string {
  if (!url) return "Nenhum (Local)";
  if (!url.includes("://")) return "***";
  const [proto, rest] = url.split("://");
  const parts = rest.split("/");
  if (parts.length <= 1) return `${proto}://${parts[0].slice(0, 4)}***`;
  const domain = parts[0];
  const maskedPath = parts.slice(1).map(p => p.length > 4 ? p.slice(0, 4) + '***' : '***').join('/');
  return `${proto}://${domain}/${maskedPath}`;
}

export interface NotificationChannel {
  id: string;
  name: string;
  provider: 'discord' | 'telegram' | 'email' | 'generic';
  enabled: boolean;
  endpoint: string;
  extraConfig: {
    discordUsername?: string;
    discordAvatar?: string;
    telegramToken?: string;
    telegramChatId?: string;
    emailRecipient?: string;
    authToken?: string;
  };
  lastStatus?: string;
  lastSentAt?: string;
}

export interface NotificationDispatchRecord {
  id: string;
  timestamp: string;
  severity: 'INFO' | 'WARN' | 'CRITICAL';
  title: string;
  details: string;
  channelNames: string[];
  httpStatus: number;
  deliveryTimeMs: number;
  payloadPreview: any;
}

export interface AntiDupItem {
  key: string;
  tournamentName: string;
  buyin: string;
  startTime: string;
  lastRegistered: string;
  status: 'REGISTERED' | 'INSUFFICIENT_FUNDS' | 'FAILED';
  count: number;
  sessionName: string;
}

export interface OrchestratorActivityLog {
  id: string;
  time: string;
  cycle: number;
  type: 'SCAN' | 'SKIP_DUP' | 'REGISTERING' | 'SUCCESS' | 'WAIT';
  message: string;
  tag?: string;
}

function buildCustomNotificationPayload(
  provider: string,
  severity: 'INFO' | 'WARN' | 'CRITICAL',
  title: string,
  details: string,
  sessionName: string,
  channel?: NotificationChannel
) {
  const dtIso = new Date().toISOString();
  const colorMap = {
    INFO: 3066993,     // Verde / Esmeralda (0x2ECC71)
    WARN: 16753920,    // Âmbar / Laranja (0xFFA500)
    CRITICAL: 15158332 // Vermelho Alerta (0xE74C3C)
  };
  const iconEmoji = severity === 'CRITICAL' ? '🚨' : severity === 'WARN' ? '⚠️' : '🔔';

  if (provider === 'discord') {
    return {
      username: channel?.extraConfig?.discordUsername || "VisualPilot Sentinel",
      avatar_url: channel?.extraConfig?.discordAvatar || "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=128&q=80",
      content: `${iconEmoji} **[VISUALPILOT: ${severity}]** ${title}`,
      embeds: [
        {
          title: `${iconEmoji} ${title}`,
          description: details,
          color: colorMap[severity],
          fields: [
            { name: "Severidade", value: severity, inline: true },
            { name: "Sessão Ativa", value: sessionName || "Sessão Principal", inline: true },
            { name: "Canal", value: channel?.name || "Webhook Discord", inline: true },
            { name: "Data / Hora UTC", value: dtIso, inline: false },
            { name: "Ação Operacional", value: severity === 'CRITICAL' ? "Verifique imediatamente o cliente PPPoker e o script Python no desktop." : "Evento operacional registrado no arquivo CSV de auditoria.", inline: false }
          ],
          footer: { text: "VisualPilot Módulo 4 • Sistema Multi-Canal de Notificações" },
          timestamp: dtIso
        }
      ]
    };
  }

  if (provider === 'telegram') {
    const chat = channel?.extraConfig?.telegramChatId || "-100123456789";
    return {
      chat_id: chat,
      parse_mode: "Markdown",
      text: `${iconEmoji} *[VISUALPILOT ${severity}]*\n*${title}*\n\n${details}\n\n🏷 *Sessão:* \`${sessionName || "Sessão Principal"}\`\n🕒 *UTC:* \`${dtIso}\`\n📡 *Canal:* \`${channel?.name || "Telegram Bot"}\`\n\n_${severity === 'CRITICAL' ? "Ação imediata recomendada no desktop do bot." : "Auditoria automática ativa."}_`
    };
  }

  return {
    event: `VISUALPILOT_${severity}_ALERT`,
    severity: severity,
    title: title,
    details: details,
    session_name: sessionName || "Sessão Principal",
    channel_id: channel?.id || "generic-webhook",
    recipient_email: channel?.extraConfig?.emailRecipient || "operador@pokerbot.com",
    timestamp_utc: dtIso,
    status: "DISPATCHED",
    system_metrics: {
      latency_overhead_ms: 12.4,
      watchdog_status: "HEALTHY",
      active_monitors: 1
    }
  };
}

function getPayloadPreview(provider: string, url: string, elapsedSec: number) {
  const dtIso = new Date().toISOString();
  const elapsedMin = (elapsedSec / 60).toFixed(1);

  if (provider === 'discord') {
    return {
      content: `🚨 **[ALERTA CRÍTICO: VISUALPILOT]** O bot entrou em **SYSTEM_HALT** há ${elapsedSec}s (~${elapsedMin} min)!`,
      embeds: [
        {
          title: "🚨 Paralisação Crítica do Bot (> 5 minutos)",
          description: `O bot paralisou a execução por ausência de pulsação há ${elapsedSec} segundos. Ações bloqueadas preventivamente no Windows.`,
          color: 15158332,
          fields: [
            { name: "Status", value: "SYSTEM_HALT", inline: true },
            { name: "Tempo Paralisado", value: `${elapsedSec}s (~${elapsedMin} min)`, inline: true },
            { name: "Proteção Ativa", value: "Cliques bloqueados", inline: true },
            { name: "Timestamp UTC", value: dtIso, inline: false },
            { name: "Instruções", value: "Acesse o desktop do bot e verifique se o PPPoker ou o script VisualPilot parou de responder.", inline: false }
          ],
          footer: { text: "VisualPilot Módulo 4 • Sistema de Escalada Watchdog" }
        }
      ]
    };
  }

  if (provider === 'telegram') {
    return {
      chat_id: "-100123456789",
      parse_mode: "Markdown",
      text: `🚨 *[VISUALPILOT CRITICAL]*\n*Paralisação Crítica do Bot (> 5 minutos)*\n\nO bot está paralisado há ${elapsedSec}s (~${elapsedMin} min) sem emitir pulsação de batimentos cardíacos.\n\n🛡 *Status:* Cliques bloqueados preventivamente no desktop.\n🕒 *UTC:* \`${dtIso}\`\n\n👉 _Acesse o computador do bot imediatamente para verificar a integridade._`
    };
  }

  return {
    event: "SYSTEM_HALT_ESCALATION",
    title: "Paralisação Crítica do Bot (> 5 minutos)",
    status: "ESCALATED",
    severity: "CRITICAL",
    elapsed_seconds: elapsedSec,
    elapsed_minutes: Number(elapsedMin),
    timestamp_utc: dtIso,
    details: `O bot está em SYSTEM_HALT por mais de ${elapsedSec}s sem pulsação ativa. Cliques bloqueados preventivamente.`,
    instructions: "Verifique o processo do bot e a janela PPPoker no desktop."
  };
}

export default function App() {
  const [selectedCard, setSelectedCard] = useState<TournamentRecord>(TOURNAMENTS_DATA[2]); // Default Corujão
  const [mainSection, setMainSection] = useState<MainNavArea>('overview');
  const [activeTab, setActiveTab] = useState<'overview' | 'ocr_feed' | 'multitable' | 'cards' | 'hero_actions' | 'table_numerical' | 'preflop_gto' | 'postflop_gto' | 'bot_brain' | 'monthly_roi' | 'tournament_profit' | 'ghost' | 'manual' | 'manual_facil' | 'orchestrator' | 'deployment' | 'register' | 'alerts' | 'audit' | 'clicker' | 'ocr' | 'visual' | 'guide' | 'installer'>('overview');

  const navigateToTab = (tab: any, section?: MainNavArea) => {
    setActiveTab(tab);
    if (section) {
      setMainSection(section);
    } else {
      if (tab === 'overview') setMainSection('overview');
      else if (['ghost', 'orchestrator', 'register', 'session_ctrl'].includes(tab)) setMainSection('sessions');
      else if (tab === 'multitable') setMainSection('multitable');
      else if (['cards', 'table_numerical', 'hero_actions', 'ocr', 'visual'].includes(tab)) setMainSection('ocr_recognition');
      else if (['ocr_feed', 'audit', 'clicker', 'alerts'].includes(tab)) setMainSection('events_actions');
      else if (['bot_brain', 'monthly_roi', 'tournament_profit', 'preflop_gto', 'postflop_gto'].includes(tab)) setMainSection('reports');
      else if (['installer', 'manual_facil', 'manual', 'deployment', 'guide'].includes(tab)) setMainSection('settings');
    }
  };
  const [showInstallerModal, setShowInstallerModal] = useState<boolean>(false);
  const [showInstallBanner, setShowInstallBanner] = useState<boolean>(true);
  const [zoomLevel, setZoomLevel] = useState<number>(1);

  // Continuous Loop Orchestrator State (lobby_orchestrator.py)
  const [orchIsRunning, setOrchIsRunning] = useState<boolean>(false);
  const [orchIsPaused, setOrchIsPaused] = useState<boolean>(false);
  const [orchLoopInterval, setOrchLoopInterval] = useState<number>(15);
  const [orchJitter, setOrchJitter] = useState<number>(3);
  const [orchMaxBuyin, setOrchMaxBuyin] = useState<number>(50);
  const [orchMaxIterations, setOrchMaxIterations] = useState<number>(0); // 0 = infinito
  const [orchDryRun, setOrchDryRun] = useState<boolean>(true);
  const [orchAutoRecovery, setOrchAutoRecovery] = useState<boolean>(true);
  const [orchCycleCount, setOrchCycleCount] = useState<number>(4);
  const [orchCountdown, setOrchCountdown] = useState<number>(15);
  const [orchTournamentsScanned, setOrchTournamentsScanned] = useState<number>(16);
  const [orchTournamentsEligible, setOrchTournamentsEligible] = useState<number>(12);
  const [orchTournamentsSkippedDup, setOrchTournamentsSkippedDup] = useState<number>(9);
  const [orchTournamentsRegistered, setOrchTournamentsRegistered] = useState<number>(3);
  const [orchActiveSubTab, setOrchActiveSubTab] = useState<'anti_dup' | 'logs' | 'config'>('anti_dup');

  const [antiDupRecords, setAntiDupRecords] = useState<AntiDupItem[]>([
    {
      key: "CORUJAOHYPERPKO10K_50_2300",
      tournamentName: "CORUJAO HYPER PKO10K",
      buyin: "50",
      startTime: "23:00",
      lastRegistered: "Há 4 min",
      status: "REGISTERED",
      count: 1,
      sessionName: "Sessão Matinal 01"
    },
    {
      key: "TARDEZINHAPKO5KGTD_10_1630",
      tournamentName: "TARDEZINHA PKO 5K GTD",
      buyin: "10",
      startTime: "16:30",
      lastRegistered: "Há 12 min",
      status: "REGISTERED",
      count: 1,
      sessionName: "Sessão Matinal 01"
    },
    {
      key: "PPPOKERSUPERCLASSIC20K_20_1400",
      tournamentName: "PPPOKER SUPER CLASSIC 20K",
      buyin: "20",
      startTime: "14:00",
      lastRegistered: "Há 18 min",
      status: "REGISTERED",
      count: 1,
      sessionName: "Sessão Matinal 01"
    }
  ]);

  const [orchActivityLogs, setOrchActivityLogs] = useState<OrchestratorActivityLog[]>([
    {
      id: "log-006",
      time: "22:52:15",
      cycle: 4,
      type: "SKIP_DUP",
      message: "Torneio 'CORUJAO HYPER PKO10K' (50 fichas) IGNORADO: Já inscrito no ciclo #1 (Anti-Duplicação ativa).",
      tag: "ANTI_DUP"
    },
    {
      id: "log-005",
      time: "22:52:14",
      cycle: 4,
      type: "SCAN",
      message: "Varredura do Lobby concluída: 4 cartões lidos, 3 elegíveis (MTT <= 50 fichas).",
      tag: "VARREDURA"
    },
    {
      id: "log-004",
      time: "22:51:58",
      cycle: 3,
      type: "WAIT",
      message: "Ciclo #3 finalizado em 1.1s. Aguardando intervalo de 15.0s (±3.0s jitter) para o ciclo #4...",
      tag: "INTERVALO"
    },
    {
      id: "log-003",
      time: "22:51:42",
      cycle: 2,
      type: "SUCCESS",
      message: "Inscrição confirmada: 'CORUJAO HYPER PKO10K' (Módulos 4 e 5 concluídos). Registrado no JSON persistente.",
      tag: "INSCRIÇÃO_OK"
    },
    {
      id: "log-002",
      time: "22:51:25",
      cycle: 1,
      type: "REGISTERING",
      message: "Detectado torneio elegível não inscrito: 'TARDEZINHA PKO 5K GTD'. Disparando PyAutoGUI suave...",
      tag: "DISPARO"
    },
    {
      id: "log-001",
      time: "22:51:10",
      cycle: 1,
      type: "SCAN",
      message: "Orquestrador de Ciclo Contínuo iniciado na sessão 'Sessão Matinal 01'. Janela PPPoker 787x1470 verificada.",
      tag: "INÍCIO"
    }
  ]);

  // Floating Game Session Live State
  const [isSessionActive, setIsSessionActive] = useState<boolean>(true);
  const [sessionPaused, setSessionPaused] = useState<boolean>(false);
  const [sessionElapsedSeconds, setSessionElapsedSeconds] = useState<number>(14 * 60 + 32);
  const [sessionClicksCount, setSessionClicksCount] = useState<number>(18);
  const [showSessionConfigModal, setShowSessionConfigModal] = useState<boolean>(false);
  const [sessionNewNameInput, setSessionNewNameInput] = useState<string>("");

  // Multi-Channel Notifications State (Tab Alertas e Notificações)
  const [channels, setChannels] = useState<NotificationChannel[]>([
    {
      id: "ch-discord",
      name: "Discord (#alertas-bot)",
      provider: "discord",
      enabled: true,
      endpoint: "https://discord.com/api/webhooks/13010023456789/VisualPilotAlertsBot",
      extraConfig: {
        discordUsername: "VisualPilot Sentinel",
        discordAvatar: "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=128&q=80"
      },
      lastStatus: "200 OK (Entregue)",
      lastSentAt: "Há 12 min"
    },
    {
      id: "ch-telegram",
      name: "Telegram (@VisualPilotAlertsBot)",
      provider: "telegram",
      enabled: true,
      endpoint: "https://api.telegram.org/bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/sendMessage",
      extraConfig: {
        telegramToken: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegramChatId: "-100123456789"
      },
      lastStatus: "200 OK (Entregue)",
      lastSentAt: "Há 12 min"
    },
    {
      id: "ch-email",
      name: "E-mail Operacional (Zapier / Make)",
      provider: "email",
      enabled: true,
      endpoint: "https://hooks.zapier.com/hooks/catch/9876543/email_alert_on_halt",
      extraConfig: {
        emailRecipient: "operador@pokerbot.com"
      },
      lastStatus: "200 OK (Entregue)",
      lastSentAt: "Há 2 horas"
    },
    {
      id: "ch-generic",
      name: "Servidor Central de Telemetria",
      provider: "generic",
      enabled: false,
      endpoint: "https://meuservidor.com/api/v1/alerts/visualpilot",
      extraConfig: {
        authToken: "Bearer vp_live_key_9981274"
      },
      lastStatus: "Silenciado (Inativo)",
      lastSentAt: "-"
    }
  ]);

  const [testSeverity, setTestSeverity] = useState<'INFO' | 'WARN' | 'CRITICAL'>('CRITICAL');
  const [testTitle, setTestTitle] = useState<string>("🚨 Paralisação Crítica do Bot (> 5 minutos)");
  const [testDetails, setTestDetails] = useState<string>("Inatividade prolongada detectada pelo watchdog de heartbeat. Cliques bloqueados no desktop preventivamente.");
  const [selectedChannelIds, setSelectedChannelIds] = useState<string[]>(["ch-discord", "ch-telegram", "ch-email"]);
  const [isDispatchingNotification, setIsDispatchingNotification] = useState<boolean>(false);
  const [activePreviewProvider, setActivePreviewProvider] = useState<'discord' | 'telegram' | 'generic'>('discord');
  const [copiedPayloadJson, setCopiedPayloadJson] = useState<boolean>(false);

  const [dispatchHistory, setDispatchHistory] = useState<NotificationDispatchRecord[]>([
    {
      id: "disp-001",
      timestamp: "22:47:20",
      severity: "CRITICAL",
      title: "Paralisação Crítica do Bot (> 5 minutos)",
      details: "Inatividade detectada: nenhum heartbeat recebido por 300.0s. Alerta de escalada remota despachado.",
      channelNames: ["Discord (#alertas-bot)", "Telegram (@VisualPilotAlertsBot)"],
      httpStatus: 200,
      deliveryTimeMs: 148.6,
      payloadPreview: {}
    },
    {
      id: "disp-002",
      timestamp: "22:30:15",
      severity: "WARN",
      title: "Variação de Resolução Detectada",
      details: "A janela do PPPoker sofreu leve redimensionamento para 850x1400. Fatores de escala ajustados.",
      channelNames: ["Telegram (@VisualPilotAlertsBot)"],
      httpStatus: 200,
      deliveryTimeMs: 112.2,
      payloadPreview: {}
    },
    {
      id: "disp-003",
      timestamp: "22:15:00",
      severity: "INFO",
      title: "Sessão de Jogo Iniciada",
      details: "Sessão 'Sessão Matinal 01' aberta pelo operador. Calibração da janela 787x1470 verificada.",
      channelNames: ["Discord (#alertas-bot)", "E-mail Operacional (Zapier / Make)"],
      httpStatus: 200,
      deliveryTimeMs: 185.0,
      payloadPreview: {}
    }
  ]);

  // Module 5: Registration State Machine State
  const [m5Step, setM5Step] = useState<number>(1); // 0: LOBBY, 1: DETAILS, 2: REGISTER_CLICK, 3: MODAL_CONFIRM, 4: REGISTERED, 5: RETURNED
  const [m5AutoRunning, setM5AutoRunning] = useState<boolean>(false);
  const [m5Scenario, setM5Scenario] = useState<'NORMAL' | 'INSUFFICIENT_FUNDS' | 'ALREADY_REGISTERED'>('NORMAL');
  const [m5StepLogs, setM5StepLogs] = useState<Array<{ step: string; status: string; time: string; durationMs: number; details: string }>>([
    {
      step: "WAIT_DETAIL_SCREEN",
      status: "SUCCESS",
      time: "22:42:10",
      durationMs: 284.5,
      details: "Transição identificada: Tela de Detalhes carregada com sucesso."
    }
  ]);

  // Logs state
  const [logRows, setLogRows] = useState<AuditLogRow[]>(INITIAL_LOG_ROWS);
  const [logFilter, setLogFilter] = useState<'ALL' | 'SUCCESS' | 'ABORTED' | 'HALT' | 'ESCALATED'>('ALL');
  // Painel Avançado: Calibração, Teste A/B e Diagnóstico (Toggle para focar 70% da tela em Estado da Janela e Log de Auditoria)
  const [showAdvancedAuditPanel, setShowAdvancedAuditPanel] = useState<boolean>(false);
  const [advancedActiveSubTab, setAdvancedActiveSubTab] = useState<'calibration' | 'camouflage' | 'preflight' | 'roi' | 'recovery'>('calibration');

  // Sound and Toast Notifications State
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);
  const [toasts, setToasts] = useState<ToastAlert[]>([
    {
      id: "init-halt-demo",
      title: "WATCHDOG MONITORANDO PULSAÇÃO",
      message: "Alarme sonoro, visual e vigilância remota ativos: inatividade (>30s) dispara SYSTEM_HALT e persistência (>5 min) aciona Webhook remoto.",
      eventType: "SYSTEM_HALT",
      severity: "INFO",
      timestamp: "Sistema Pronto"
    }
  ]);

  // Heartbeat Watchdog & Escalation State
  const [heartbeatActive, setHeartbeatActive] = useState<boolean>(true);
  const [lastBeatTime, setLastBeatTime] = useState<string>("agora (0.2s atrás)");

  // Webhook & Remote Escalation State
  const [webhookUrl, setWebhookUrl] = useState<string>("https://discord.com/api/webhooks/1301000000000000000/VisualPilotBotAlert");
  const [webhookProvider, setWebhookProvider] = useState<'discord' | 'telegram' | 'email' | 'generic'>('discord');
  const [escalationTimeout, setEscalationTimeout] = useState<number>(300); // 300s = 5 minutos
  const [haltElapsedSeconds, setHaltElapsedSeconds] = useState<number>(0);
  const [escalationSent, setEscalationSent] = useState<boolean>(false);
  const [isTestingWebhook, setIsTestingWebhook] = useState<boolean>(false);
  const [showPayloadPreview, setShowPayloadPreview] = useState<boolean>(false);

  const addToast = (alert: Omit<ToastAlert, 'id' | 'timestamp'>) => {
    const id = Math.random().toString(36).substring(2, 9);
    const timestamp = new Date().toLocaleTimeString();
    const newAlert: ToastAlert = { ...alert, id, timestamp };

    setToasts(prev => [newAlert, ...prev.slice(0, 4)]);

    if (soundEnabled) {
      if (alert.severity === 'CRITICAL') playSynthesizedAlarm('CRITICAL');
      else if (alert.severity === 'WARN') playSynthesizedAlarm('WARN');
      else playSynthesizedAlarm('SUCCESS');
    }
  };

  const dismissToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  // Interactive Window Coordinates Simulator State for Module 4
  const [winLeft, setWinLeft] = useState<number>(500);
  const [winTop, setWinTop] = useState<number>(150);
  const [winWidth, setWinWidth] = useState<number>(787);
  const [winHeight, setWinHeight] = useState<number>(1470);
  const [applyJitter, setApplyJitter] = useState<boolean>(true);
  // Validação de alça de janela ativa (HWND) e integridade do processo 'PPPoker.exe'
  const [hasWindowHandle, setHasWindowHandle] = useState<boolean>(true);
  const [isPppokerProcessRunning, setIsPppokerProcessRunning] = useState<boolean>(true);
  // Ref para rastrear geometria em tempo real lida diretamente da API do PyGetWindow (imune a stale closures)
  const winGeometryRef = useRef<{ left: number; top: number; width: number; height: number }>({
    left: winLeft,
    top: winTop,
    width: winWidth,
    height: winHeight
  });

  useEffect(() => {
    winGeometryRef.current = { left: winLeft, top: winTop, width: winWidth, height: winHeight };
  }, [winLeft, winTop, winWidth, winHeight]);

  // Session Identification State
  const [sessionName, setSessionName] = useState<string>("Sessão Matinal 01");
  const [sessionFilter, setSessionFilter] = useState<string>("ALL");

  // Intervenção Manual / Human Takeover (Pausa instantânea para o operador assumir as mesas)
  const [isHumanTakeover, setIsHumanTakeover] = useState<boolean>(false);

  // Click Speed & Camouflage Delay Settings
  const [clickSpeed, setClickSpeed] = useState<'fast' | 'natural' | 'slow'>('natural');
  const [randomDelayEnabled, setRandomDelayEnabled] = useState<boolean>(true);
  const [delayMinMs, setDelayMinMs] = useState<number>(350);
  const [delayMaxMs, setDelayMaxMs] = useState<number>(850);
  const [isSimulatingClick, setIsSimulatingClick] = useState<boolean>(false);
  const [clickLog, setClickLog] = useState<string>("");
  const [clickPhase, setClickPhase] = useState<'IDLE' | 'DELAY' | 'MOVING' | 'CLICKING' | 'DONE'>('IDLE');
  const [lastLatencyBreakdown, setLastLatencyBreakdown] = useState<{
    reactionMs: number;
    moveMs: number;
    pressMs: number;
    totalMs: number;
    speedLabel: string;
  } | null>(null);

  const [lastTrajectory, setLastTrajectory] = useState<{
    p0: { x: number; y: number };
    p1: { x: number; y: number };
    p2: { x: number; y: number };
    target: { x: number; y: number };
    distance: number;
    jitterPx: number;
    accelerationCurve: string;
  } | null>(null);

  // A/B Testing State for Camouflage Strategies
  const [abTestEnabled, setAbTestEnabled] = useState<boolean>(true);
  const [strategyA, setStrategyA] = useState<CamouflageStrategy>({
    id: 'A',
    name: 'Estratégia A (Furtiva / Humana)',
    speed: 'natural',
    delayMinMs: 350,
    delayMaxMs: 850,
    applyJitter: true
  });
  const [strategyB, setStrategyB] = useState<CamouflageStrategy>({
    id: 'B',
    name: 'Estratégia B (Agressiva / Rápida)',
    speed: 'fast',
    delayMinMs: 150,
    delayMaxMs: 380,
    applyJitter: true
  });
  const [nextAbVariant, setNextAbVariant] = useState<'A' | 'B'>('A');
  const [isAbBatchRunning, setIsAbBatchRunning] = useState<boolean>(false);
  const [abBatchProgress, setAbBatchProgress] = useState<{ current: number; total: number }>({ current: 0, total: 10 });

  // Auto-Recovery Mode Settings
  const [autoRecoveryEnabled, setAutoRecoveryEnabled] = useState<boolean>(true);
  const [pppokerExePath, setPppokerExePath] = useState<string>("C:\\Program Files (x86)\\PPPoker\\PPPoker.exe");
  const [isRecovering, setIsRecovering] = useState<boolean>(false);

  // Pre-Flight Verification State (check_init.cmd & check_env.py)
  const [preflightScenario, setPreflightScenario] = useState<'PERFECT' | 'MISSING_DEP' | 'CSV_AUTOCREATE' | 'WINDOW_MISSING' | 'WINDOW_MINIMIZED' | 'WINDOW_BLOCKED'>('PERFECT');
  const [preflightRunning, setPreflightRunning] = useState<boolean>(false);
  const [preflightExecuted, setPreflightExecuted] = useState<boolean>(true);
  const [preflightIsMinimized, setPreflightIsMinimized] = useState<boolean>(false);
  const [preflightIsBlocked, setPreflightIsBlocked] = useState<boolean>(false);
  const [preflightBlockingApp, setPreflightBlockingApp] = useState<string | null>(null);
  const [preflightOcrValid, setPreflightOcrValid] = useState<boolean>(true);
  const [preflightFrameStd, setPreflightFrameStd] = useState<number>(38.4);
  const [preflightOutput, setPreflightOutput] = useState<string[]>([
    "=================================================================",
    " VisualPilot - Verificação Prévia de Ambiente (check_init.cmd)",
    "=================================================================",
    " [ OK ] Versão do Python            -> Python 3.10.12 detectado (requer >= 3.8)",
    " [ OK ] Ambiente Virtual (.venv)    -> Executando em ambiente virtual isolado (.venv)",
    " [ OK ] Biblioteca PyAutoGUI        -> Instalada com sucesso (v0.9.54)",
    " [ OK ] Biblioteca PyGetWindow      -> Instalada com sucesso (v0.0.9)",
    " [ OK ] Biblioteca Pillow (PIL)     -> Instalada com sucesso (v10.3.0)",
    " [ OK ] Arquivo de Auditoria CSV    -> clicks_audit_2026-10-31.csv [EXISTS]: 14 colunas com fsync",
    " [ OK ] Janela do PPPoker           -> Localizada: 'PPPoker' em (500, 150) 787x1470 px",
    " [ OK ] Captura de Miniatura Frame  -> Salva em public/preflight_frame.png (787x1470 px, Score: 100%) [CALIBRADO]",
    "-----------------------------------------------------------------",
    " >> Status: AMBIENTE 100% PRONTO PARA O PRIMEIRO CLIQUE!",
    "================================================================="
  ]);
  const [preflightStatus, setPreflightStatus] = useState<'OK' | 'WARN' | 'ERROR'>('OK');

  // Frame Thumbnail & Visual Calibration Verification State (Módulo check_init.cmd / preflight_capture)
  const [preflightFrameCapturedAt, setPreflightFrameCapturedAt] = useState<string>("2026-10-31 23:15:30 BRT");
  const [preflightFrameUrl, setPreflightFrameUrl] = useState<string>("/preflight_frame.png");
  const [preflightCalibScore, setPreflightCalibScore] = useState<number>(100);
  const [preflightCalibStatus, setPreflightCalibStatus] = useState<'CALIBRATED' | 'WARN_DEVIATION' | 'DEFORMED' | 'NOT_FOUND'>('CALIBRATED');
  const [showCalibrationCrosshairs, setShowCalibrationCrosshairs] = useState<boolean>(true);
  const [showCalibrationCardsRoi, setShowCalibrationCardsRoi] = useState<boolean>(true);
  const [showCalibrationTargetPulse, setShowCalibrationTargetPulse] = useState<boolean>(true);
  const [isRecapturingFrame, setIsRecapturingFrame] = useState<boolean>(false);
  const [preflightFullscreenPreview, setPreflightFullscreenPreview] = useState<boolean>(false);

  // Estado e dados da Seção 'Passo a Passo de Instalação' no Guia Windows
  interface PythonPackageStatus {
    id: string;
    name: string;
    pipPackage: string;
    version: string;
    installed: boolean;
    required: boolean;
    description: string;
    moduleImport: string;
  }

  const [installationPackages, setInstallationPackages] = useState<PythonPackageStatus[]>([
    {
      id: 'pyautogui',
      name: 'PyAutoGUI',
      pipPackage: 'pyautogui',
      version: 'v0.9.54',
      installed: false,
      required: true,
      description: 'Movimentação do cursor, trajetórias Bézier com jitter neuromuscular e cliques físicos.',
      moduleImport: 'import pyautogui'
    },
    {
      id: 'pygetwindow',
      name: 'PyGetWindow',
      pipPackage: 'pygetwindow',
      version: 'v0.0.9',
      installed: false,
      required: true,
      description: 'Detecção da janela PPPoker, detecção de minimização/bloqueio e escala dinâmica.',
      moduleImport: 'import pygetwindow'
    },
    {
      id: 'pillow',
      name: 'Pillow (PIL)',
      pipPackage: 'pillow',
      version: 'v10.3.0',
      installed: false,
      required: true,
      description: 'Captura de frames em alta fidelidade e conversão RGB para motores de OCR e visão.',
      moduleImport: 'import PIL'
    },
    {
      id: 'numpy',
      name: 'NumPy',
      pipPackage: 'numpy',
      version: 'v1.26.4',
      installed: false,
      required: true,
      description: 'Cálculo de matrizes, gradientes espaciais e rejeição de ruído de feltro escuro.',
      moduleImport: 'import numpy'
    },
    {
      id: 'pytesseract',
      name: 'PyTesseract',
      pipPackage: 'pytesseract',
      version: 'v0.3.13',
      installed: false,
      required: true,
      description: 'Wrapper Tesseract OCR para leitura ótica de texto da mesa, nomes de torneios e buy-ins.',
      moduleImport: 'import pytesseract'
    },
    {
      id: 'mss',
      name: 'MSS',
      pipPackage: 'mss',
      version: 'v10.0.0',
      installed: false,
      required: true,
      description: 'Captura de tela ultrarrápida de alta taxa de quadros (60fps) no Windows.',
      moduleImport: 'import mss'
    },
    {
      id: 'opencv',
      name: 'OpenCV-Python',
      pipPackage: 'opencv-python',
      version: 'v4.9.0',
      installed: false,
      required: false,
      description: 'Segmentação avançada de retângulos dos cartões e calibração de proporção 9:16.8.',
      moduleImport: 'import cv2'
    }
  ]);

  const [isFixingInstallation, setIsFixingInstallation] = useState<boolean>(false);
  const [installationLogs, setInstallationLogs] = useState<string[]>([
    "# Diagnóstico inicial: Verificando integridade das dependências no ambiente virtual .venv...",
    "# Pacotes obrigatórios ('pyautogui', 'pygetwindow', 'pillow', 'numpy', 'pytesseract', 'mss') aguardando validação.",
    "# Clique em 'Corrigir Instalação' para rodar a instalação real ou baixar o script automático 'corrigir_instalacao.bat'."
  ]);
  const [silentCommandCopied, setSilentCommandCopied] = useState<boolean>(false);
  const [installationActiveStep, setInstallationActiveStep] = useState<number>(3);

  const handleFixInstallation = async () => {
    setIsFixingInstallation(true);
    setInstallationLogs([
      "=======================================================================",
      "  VISUALPILOT - INICIANDO PROCESSO REAL DE INSTALAÇÃO NO COMPUTADOR",
      "=======================================================================",
      "> Localizando interpretador no ambiente virtual isolado (.venv)...",
      "> Verificando disponibilidade de API local em /api/install-dependencies..."
    ]);

    let backendExecuted = false;
    try {
      const resp = await fetch('/api/install-dependencies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          packages: ['pyautogui', 'pygetwindow', 'pillow', 'numpy', 'pytesseract', 'mss', 'opencv-python', 'requests', 'pydantic']
        })
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data && data.logs) {
          setInstallationLogs(prev => [...prev, ...data.logs]);
          backendExecuted = true;
        }
      }
    } catch {
      // Backend não conectado ou rodando em preview web estático
    }

    // Se o backend não executou diretamente pelo servidor, baixa o instalador oficial e NÃO marca falso-positivo
    if (!backendExecuted) {
      const dlLink = document.createElement('a');
      dlLink.href = '/VisualPilot_Setup.exe';
      dlLink.download = 'VisualPilot_Setup.exe';
      document.body.appendChild(dlLink);
      dlLink.click();
      document.body.removeChild(dlLink);

      setInstallationLogs(prev => [
        ...prev,
        "> [DOWNLOAD INICIADO] O instalador executável oficial 'VisualPilot_Setup.exe' foi baixado para o seu computador.",
        "> [AVISO GOOGLE CHROME] Se o arquivo aparecer na pasta Downloads como 'Não confirmado .crdownload':",
        "  -> O Chrome pausa o download na finalização aguardando confirmação de segurança.",
        "  -> Pressione Ctrl + J no Chrome e clique em 'Manter arquivo' / 'Manter mesmo assim'.",
        "  -> (Ou baixe a versão Portátil .ZIP que o Chrome não bloqueia).",
        "> [PENDENTE DE EXECUÇÃO] Atenção: as dependências ainda NÃO estão instaladas na máquina física.",
        "> Instruções para concluir a instalação real no Windows:",
        "  1. Dê 2 cliques no arquivo 'VisualPilot_Setup.exe' baixado para instalar.",
        "  2. O instalador configurará o ambiente virtual (.venv) e instalará todas as bibliotecas.",
        "=======================================================================",
        "> Status: Instalação física pendente de execução pelo usuário."
      ]);

      // Integridade estrita: NÃO marca como instalado antes da execução real!
      setInstallationPackages(prev => prev.map(p => ({ ...p, installed: false })));
      setIsFixingInstallation(false);
      setInstallationActiveStep(2);

      addToast({
        title: "INSTALADOR BAIXADO (53 MB)",
        message: "Se o Chrome pausar como .crdownload, pressione Ctrl+J e clique em 'Manter mesmo assim'.",
        eventType: "PREFLIGHT_CHECK",
        severity: "WARN"
      });
      return;
    }

    setInstallationPackages(prev => prev.map(p => ({ ...p, installed: true })));
    setIsFixingInstallation(false);
    setInstallationActiveStep(4);

    if (soundEnabled) {
      playSynthesizedAlarm('SUCCESS');
    }

    addToast({
      title: "INSTALAÇÃO CONCLUÍDA",
      message: "Todas as dependências foram instaladas e validadas com sucesso.",
      eventType: "PREFLIGHT_CHECK",
      severity: "INFO"
    });
  };

  const handleCopySilentCommand = () => {
    const cmd = `.venv\\Scripts\\python.exe -m pip install pyautogui pygetwindow pillow numpy pytesseract mss opencv-python requests pydantic`;
    navigator.clipboard.writeText(cmd);
    setSilentCommandCopied(true);
    addToast({
      title: "COMANDO COPIADO!",
      message: "Comando completo com pytesseract copiado. Cole no terminal CMD ou PowerShell do Windows.",
      eventType: "CLICK_SUCCESS",
      severity: "INFO"
    });
    setTimeout(() => setSilentCommandCopied(false), 2500);
  };

  const handleTogglePackage = (pkgId: string) => {
    setInstallationPackages(prev =>
      prev.map(p => (p.id === pkgId ? { ...p, installed: !p.installed } : p))
    );
  };

  const recapturePreflightFrame = () => {
    setIsRecapturingFrame(true);
    addToast({
      title: "CAPTURA DE FRAME EM ANDAMENTO",
      message: "check_init.cmd inspecionando janela PPPoker no desktop e capturando miniatura 787x1470...",
      eventType: "CLICK_SUCCESS",
      severity: "INFO"
    });

    setTimeout(() => {
      setIsRecapturingFrame(false);
      const nowStr = new Date().toLocaleTimeString('pt-BR') + ' BRT';
      setPreflightFrameCapturedAt(nowStr);
      setPreflightCalibScore(100);
      setPreflightCalibStatus('CALIBRATED');
      setPreflightFrameUrl(`/preflight_frame.png?t=${Date.now()}`);
      if (soundEnabled) {
        playSynthesizedAlarm('SUCCESS');
      }
      addToast({
        title: "FRAME CAPTURADO COM SUCESSO",
        message: `Miniatura salva em public/preflight_frame.png! Resolução 787x1470 px e proporção 9:16.8 100% calibradas.`,
        eventType: "CLICK_SUCCESS",
        severity: "INFO"
      });

      setPreflightOutput(prev => [
        ...prev.slice(0, -2),
        ` [ OK ] Recaptura de Frame      -> Miniatura atualizada às ${nowStr} (787x1470 px, Score: 100%) [CALIBRADO]`,
        prev[prev.length - 2],
        prev[prev.length - 1]
      ]);
    }, 650);
  };

  const runPreflightCheck = (scenario = preflightScenario) => {
    setPreflightRunning(true);
    setPreflightExecuted(false);

    setTimeout(() => {
      let lines: string[] = [];
      let finalStatus: 'OK' | 'WARN' | 'ERROR' = 'OK';

      if (scenario === 'PERFECT') {
        lines = [
          "=================================================================",
          " VisualPilot - Verificação Prévia de Ambiente e Janela (check_init.cmd)",
          "=================================================================",
          " [ OK ] Versão do Python            -> Python 3.10.12 detectado (requer >= 3.8)",
          " [ OK ] Ambiente Virtual (.venv)    -> Executando em ambiente virtual isolado (.venv)",
          " [ OK ] Biblioteca PyAutoGUI        -> Instalada com sucesso (v0.9.54)",
          " [ OK ] Biblioteca PyGetWindow      -> Instalada com sucesso (v0.0.9)",
          " [ OK ] Biblioteca Pillow (PIL)     -> Instalada com sucesso (v10.3.0)",
          " [ OK ] Arquivo de Auditoria CSV    -> clicks_audit_2026-11-02.csv [EXISTS]: 14 colunas com fsync",
          " [ OK ] Janela do PPPoker           -> Localizada: em (500, 150) 787x1470 px | 1º Plano: Sim | Desobstruída: Sim",
          " [ OK ] Verificação de Oclusão      -> Desobstruída: nenhuma janela sobreposta no Z-Order",
          " [ OK ] Captura de Frame para OCR   -> Salva em public/preflight_frame.png [Válida para OCR: Sim, Contraste std: 38.4]",
          "-----------------------------------------------------------------",
          " >> Status: AMBIENTE 100% PRONTO COM FRAME VÁLIDO PARA OCR!",
          "================================================================="
        ];
        finalStatus = 'OK';
        setPreflightIsMinimized(false);
        setPreflightIsBlocked(false);
        setPreflightBlockingApp(null);
        setPreflightOcrValid(true);
        setPreflightFrameStd(38.4);
        setPreflightCalibScore(100);
        setPreflightCalibStatus('CALIBRATED');
        setPreflightFrameCapturedAt(new Date().toLocaleTimeString('pt-BR') + ' BRT');
        addToast({
          title: "PRÉ-VOO: AMBIENTE ÍNTEGRO & DESOBSTRUÍDO",
          message: "check_init.cmd validou que o PPPoker está em primeiro plano, sem oclusões e com frame válido para o OCR.",
          eventType: "CLICK_SUCCESS",
          severity: "INFO"
        });
      } else if (scenario === 'MISSING_DEP') {
        lines = [
          "=================================================================",
          " VisualPilot - Verificação Prévia de Ambiente e Janela (check_init.cmd)",
          "=================================================================",
          " [ OK ] Versão do Python            -> Python 3.10.12 detectado (requer >= 3.8)",
          " [ OK ] Ambiente Virtual (.venv)    -> Executando em ambiente virtual isolado (.venv)",
          " [ OK ] Biblioteca PyAutoGUI        -> Instalada com sucesso (v0.9.54)",
          " [FALHA] Biblioteca PyGetWindow     -> Ausente: ModuleNotFoundError: No module named 'pygetwindow'",
          " [ OK ] Biblioteca Pillow (PIL)     -> Instalada com sucesso (v10.3.0)",
          " [ OK ] Arquivo de Auditoria CSV    -> clicks_audit_2026-11-02.csv [EXISTS]: íntegro",
          " [FALHA] Janela do PPPoker          -> Dependência 'pygetwindow' ausente para localização",
          " [FALHA] Captura de Frame para OCR  -> Bloqueado: pygetwindow ausente para localizar limites da janela",
          "-----------------------------------------------------------------",
          " >> Status: ERRO CRÍTICO ENCONTRADO! Corrija os erros antes de iniciar:",
          "    * PyGetWindow não encontrado: No module named 'pygetwindow'",
          " Dica: Execute 'preparar.cmd' para instalar as dependências ausentes.",
          "================================================================="
        ];
        finalStatus = 'ERROR';
        setPreflightIsMinimized(false);
        setPreflightIsBlocked(false);
        setPreflightBlockingApp(null);
        setPreflightOcrValid(false);
        setPreflightFrameStd(0.0);
        setPreflightCalibScore(0);
        setPreflightCalibStatus('NOT_FOUND');
        addToast({
          title: "PRÉ-VOO: DEPENDÊNCIA AUSENTE",
          message: "Biblioteca pygetwindow ausente! O bot impediu a execução de cliques. Execute preparar.cmd.",
          eventType: "SYSTEM_HALT",
          severity: "CRITICAL"
        });
      } else if (scenario === 'CSV_AUTOCREATE') {
        lines = [
          "=================================================================",
          " VisualPilot - Verificação Prévia de Ambiente e Janela (check_init.cmd)",
          "=================================================================",
          " [ OK ] Versão do Python            -> Python 3.10.12 detectado (requer >= 3.8)",
          " [ OK ] Ambiente Virtual (.venv)    -> Executando em ambiente virtual isolado (.venv)",
          " [ OK ] Biblioteca PyAutoGUI        -> Instalada com sucesso (v0.9.54)",
          " [ OK ] Biblioteca PyGetWindow      -> Instalada com sucesso (v0.0.9)",
          " [ OK ] Biblioteca Pillow (PIL)     -> Instalada com sucesso (v10.3.0)",
          " [ OK ] Arquivo de Auditoria CSV    -> clicks_audit_2026-11-02.csv [INITIALIZED]: Criado e validado com cabeçalho de 14 colunas",
          " [ OK ] Janela do PPPoker           -> Localizada: 'PPPoker' em (500, 150) 787x1470 px | Desobstruída",
          " [ OK ] Captura de Frame para OCR   -> Salva em public/preflight_frame.png (787x1470 px, Score: 100%) [CALIBRADO]",
          "-----------------------------------------------------------------",
          " >> Status: ARQUIVO CSV INICIALIZADO COM SUCESSO! Pronto para gravar.",
          "================================================================="
        ];
        finalStatus = 'OK';
        setPreflightIsMinimized(false);
        setPreflightIsBlocked(false);
        setPreflightBlockingApp(null);
        setPreflightOcrValid(true);
        setPreflightFrameStd(38.4);
        setPreflightCalibScore(100);
        setPreflightCalibStatus('CALIBRATED');
        setPreflightFrameCapturedAt(new Date().toLocaleTimeString('pt-BR') + ' BRT');
        addToast({
          title: "PRÉ-VOO: CSV AUTO-CRIADO",
          message: "Arquivo clicks_audit_2026-11-02.csv não existia e foi gerado com as 14 colunas obrigatórias.",
          eventType: "SYSTEM_RESUMED",
          severity: "INFO"
        });
      } else if (scenario === 'WINDOW_MISSING') {
        lines = [
          "=================================================================",
          " VisualPilot - Verificação Prévia de Ambiente e Janela (check_init.cmd)",
          "=================================================================",
          " [ OK ] Versão do Python            -> Python 3.10.12 detectado (requer >= 3.8)",
          " [ OK ] Ambiente Virtual (.venv)    -> Executando em ambiente virtual isolado (.venv)",
          " [ OK ] Biblioteca PyAutoGUI        -> Instalada com sucesso (v0.9.54)",
          " [ OK ] Biblioteca PyGetWindow      -> Instalada com sucesso (v0.0.9)",
          " [ OK ] Biblioteca Pillow (PIL)     -> Instalada com sucesso (v10.3.0)",
          " [ OK ] Arquivo de Auditoria CSV    -> clicks_audit_2026-11-02.csv [EXISTS]: 14 colunas",
          " [WARN] Janela do PPPoker           -> Janela PPPoker não está visível no momento. Abra o PPPoker antes de clicar.",
          " [WARN] Captura de Frame para OCR   -> PPPoker fechado. Usando frame de referência simulado para conferência.",
          "-----------------------------------------------------------------",
          " >> Status: AMBIENTE PRONTO COM AVISOS (Abra o PPPoker antes de clicar)",
          "================================================================="
        ];
        finalStatus = 'WARN';
        setPreflightIsMinimized(false);
        setPreflightIsBlocked(false);
        setPreflightBlockingApp(null);
        setPreflightOcrValid(false);
        setPreflightFrameStd(0.0);
        setPreflightCalibScore(50);
        setPreflightCalibStatus('WARN_DEVIATION');
        addToast({
          title: "PRÉ-VOO: JANELA NÃO ABERTA",
          message: "check_init alertou: O PPPoker ainda não foi aberto no Windows. Abra-o antes do primeiro clique.",
          eventType: "WINDOW_CLOSED",
          severity: "WARN"
        });
      } else if (scenario === 'WINDOW_MINIMIZED') {
        lines = [
          "=================================================================",
          " VisualPilot - Verificação Prévia de Ambiente e Janela (check_init.cmd)",
          "=================================================================",
          " [ OK ] Versão do Python            -> Python 3.10.12 detectado (requer >= 3.8)",
          " [ OK ] Ambiente Virtual (.venv)    -> Executando em ambiente virtual isolado (.venv)",
          " [ OK ] Bibliotecas & Dependências  -> PyAutoGUI, PyGetWindow, Pillow, Numpy [OK]",
          " [ OK ] Arquivo de Auditoria CSV    -> clicks_audit_2026-11-02.csv [EXISTS]: 14 colunas",
          " [WARN] Janela do PPPoker           -> DETECTADA, MAS ESTÁ MINIMIZADA NA BARRA DE TAREFAS! (IsIconic: True)",
          " [FALHA] Captura de Frame para OCR  -> DESCARTADA preventivamente! Janela minimizada gera tela preta sem conteúdo.",
          "-----------------------------------------------------------------",
          " [!] ALERTA CRÍTICO: Janela do PPPoker está MINIMIZADA!",
          "     Restaure a janela na barra de tarefas antes de disparar o bot para garantir OCR válido.",
          " >> Status: AVISO DE MINIMIZAÇÃO! Frame não capturado para evitar dados falsos no OCR.",
          "================================================================="
        ];
        finalStatus = 'WARN';
        setPreflightIsMinimized(true);
        setPreflightIsBlocked(false);
        setPreflightBlockingApp(null);
        setPreflightOcrValid(false);
        setPreflightFrameStd(0.0);
        setPreflightCalibScore(0);
        setPreflightCalibStatus('WARN_DEVIATION');
        addToast({
          title: "PRÉ-VOO: JANELA MINIMIZADA",
          message: "check_init.cmd detectou que o PPPoker está minimizado! O frame de OCR foi descartado para evitar dados falsos.",
          eventType: "WINDOW_CLOSED",
          severity: "WARN"
        });
      } else if (scenario === 'WINDOW_BLOCKED') {
        lines = [
          "=================================================================",
          " VisualPilot - Verificação Prévia de Ambiente e Janela (check_init.cmd)",
          "=================================================================",
          " [ OK ] Versão do Python            -> Python 3.10.12 detectado (requer >= 3.8)",
          " [ OK ] Ambiente Virtual (.venv)    -> Executando em ambiente virtual isolado (.venv)",
          " [ OK ] Bibliotecas & Dependências  -> PyAutoGUI, PyGetWindow, Pillow, Numpy [OK]",
          " [ OK ] Arquivo de Auditoria CSV    -> clicks_audit_2026-11-02.csv [EXISTS]: 14 colunas",
          " [FALHA] Janela do PPPoker          -> BLOQUEADA por outra janela: 'Google Chrome' (42.5% de sobreposição no Z-Order)",
          " [FALHA] Captura de Frame para OCR  -> DESCARTADA preventivamente! Captura registraria a janela do navegador.",
          "-----------------------------------------------------------------",
          " [!] ALERTA DE BLOQUEIO: Janela PPPoker coberta por 'Google Chrome'!",
          "     Minimize ou afaste o navegador para que o PPPoker fique totalmente visível e desobstruído.",
          " >> Status: ERRO DE BLOQUEIO! Frame cancelado para proteger o motor de OCR.",
          "================================================================="
        ];
        finalStatus = 'ERROR';
        setPreflightIsMinimized(false);
        setPreflightIsBlocked(true);
        setPreflightBlockingApp("Google Chrome (PID 14220)");
        setPreflightOcrValid(false);
        setPreflightFrameStd(4.2);
        setPreflightCalibScore(0);
        setPreflightCalibStatus('DEFORMED');
        addToast({
          title: "PRÉ-VOO: JANELA BLOQUEADA POR OUTRO APP",
          message: "O PPPoker está coberto por 'Google Chrome'! Frame descartado para evitar OCR com dados de outra janela.",
          eventType: "SYSTEM_HALT",
          severity: "CRITICAL"
        });
      }

      setPreflightOutput(lines);
      setPreflightStatus(finalStatus);
      setPreflightExecuted(true);
      setPreflightRunning(false);
    }, 600);
  };

  const downloadAuditCsv = (rowsToExport: AuditLogRow[], filterName?: string) => {
    const headers = [
      "timestamp_iso",
      "session_name",
      "event_type",
      "status",
      "tournament_name",
      "card_index",
      "buyin_chips",
      "target_abs_x",
      "target_abs_y",
      "win_left",
      "win_top",
      "win_width",
      "win_height",
      "duration_ms",
      "details"
    ];

    const escapeField = (val: string | number | null | undefined): string => {
      if (val === null || val === undefined) return '';
      const str = String(val);
      if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    const csvLines = [
      headers.join(','),
      ...rowsToExport.map(r => [
        escapeField(r.timestamp_iso),
        escapeField(r.session_name || "Sessão Principal"),
        escapeField(r.event_type),
        escapeField(r.status),
        escapeField(r.tournament_name),
        escapeField(r.card_index),
        escapeField(r.buyin_chips),
        escapeField(r.target_abs_x),
        escapeField(r.target_abs_y),
        escapeField(r.win_left),
        escapeField(r.win_top),
        escapeField(r.win_width),
        escapeField(r.win_height),
        escapeField(r.duration_ms),
        escapeField(r.details)
      ].join(','))
    ];

    // UTF-8 BOM (\uFEFF) garante que acentuações e caracteres especiais abram perfeitamente no Excel
    const csvContent = "\uFEFF" + csvLines.join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const dateStr = new Date().toISOString().split('T')[0];
    const suffix = filterName && filterName !== 'ALL' ? `_${filterName.toLowerCase()}` : '';
    const filename = `clicks_audit_${dateStr}${suffix}.csv`;

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    addToast({
      title: "DOWNLOAD DO ARQUIVO CSV",
      message: `Arquivo ${filename} baixado com ${rowsToExport.length} registros para auditoria e arquivamento manual.`,
      eventType: "PREFLIGHT_CHECK",
      severity: "INFO"
    });
  };

  /**
   * Recalcula dinamicamente scaleX e scaleY baseado na leitura instantânea da API do PyGetWindow
   * (lendo as dimensões reais atuais da janela ou da ref síncrona), garantindo que o bot corrija
   * as coordenadas instantaneamente caso a janela do PPPoker seja redimensionada ou movida enquanto
   * o orquestrador está rodando.
   */
  interface DynamicScalingResult {
    winLeft: number;
    winTop: number;
    winWidth: number;
    winHeight: number;
    scaleX: number;
    scaleY: number;
    scaledLocalX: number;
    scaledLocalY: number;
    absX: number;
    absY: number;
    isWithinBounds: boolean;
    scaleRatioFormatted: string;
    hasActiveHandle: boolean;
    isProcessAlive: boolean;
    handleError?: string;
  }

  const recalculateDynamicWindowScale = (
    localPoint: [number, number] = selectedCard.click_point_local,
    capturedSize: [number, number] = [787.0, 1470.0],
    overrideGeometry?: { left?: number; top?: number; width?: number; height?: number }
  ): DynamicScalingResult => {
    // 0. Validação adicional obrigatória: verificar se o processo 'PPPoker.exe' ainda possui uma alça de janela ativa (HWND)
    const globalPyWin = (typeof window !== 'undefined' && (window as any).__PYGETWINDOW_LAST_RECT__) || null;
    const globalHandle = (typeof window !== 'undefined' && (window as any).__PYPOKER_WINDOW_HANDLE_ACTIVE__) ?? hasWindowHandle;
    const isProcessAlive = (typeof window !== 'undefined' && (window as any).__PYPOKER_PROCESS_ALIVE__) ?? isPppokerProcessRunning;

    const curLeft = overrideGeometry?.left ?? globalPyWin?.left ?? winGeometryRef.current.left;
    const curTop = overrideGeometry?.top ?? globalPyWin?.top ?? winGeometryRef.current.top;
    const curWidth = overrideGeometry?.width ?? globalPyWin?.width ?? winGeometryRef.current.width;
    const curHeight = overrideGeometry?.height ?? globalPyWin?.height ?? winGeometryRef.current.height;

    // Se o processo encerrou, a alça HWND foi destruída ou as dimensões colapsaram a 0
    const hasActiveWindowHandle = globalHandle && isProcessAlive && curWidth > 0 && curHeight > 0;

    if (!hasActiveWindowHandle) {
      const errReason = !isProcessAlive
        ? "Processo 'PPPoker.exe' não está ativo no sistema Windows."
        : !globalHandle
        ? "Processo 'PPPoker.exe' perdeu a alça de janela ativa (HWND nulo ou invalidado)."
        : "Janela do PPPoker está fechada ou com dimensões colapsadas (0x0 px).";

      return {
        winLeft: 0,
        winTop: 0,
        winWidth: 0,
        winHeight: 0,
        scaleX: 0,
        scaleY: 0,
        scaledLocalX: 0,
        scaledLocalY: 0,
        absX: 0,
        absY: 0,
        isWithinBounds: false,
        hasActiveHandle: false,
        isProcessAlive: isProcessAlive,
        handleError: `[VAL_ALÇA_PPPOKER]: ${errReason} Cálculo de escala cancelado preventivamente.`,
        scaleRatioFormatted: "INDISPONÍVEL (Sem alça ativa para 'PPPoker.exe')"
      };
    }

    // 1. Recálculo dinâmico das razões de escala
    const curScaleX = curWidth / capturedSize[0];
    const curScaleY = curHeight / capturedSize[1];

    // 2. Tradução das coordenadas locais para absolutas de desktop
    const dynScaledLocalX = localPoint[0] * curScaleX;
    const dynScaledLocalY = localPoint[1] * curScaleY;
    const dynAbsX = Math.round(curLeft + dynScaledLocalX);
    const dynAbsY = Math.round(curTop + dynScaledLocalY);

    // 3. Verificação de limites físicos da janela com margem de segurança de 8px
    const margin = 8;
    const isWithin = (
      dynAbsX >= curLeft + margin &&
      dynAbsX <= curLeft + curWidth - margin &&
      dynAbsY >= curTop + margin &&
      dynAbsY <= curTop + curHeight - margin
    );

    return {
      winLeft: curLeft,
      winTop: curTop,
      winWidth: curWidth,
      winHeight: curHeight,
      scaleX: curScaleX,
      scaleY: curScaleY,
      scaledLocalX: dynScaledLocalX,
      scaledLocalY: dynScaledLocalY,
      absX: dynAbsX,
      absY: dynAbsY,
      isWithinBounds: isWithin,
      hasActiveHandle: true,
      isProcessAlive: true,
      scaleRatioFormatted: `scaleX=${curScaleX.toFixed(4)}x, scaleY=${curScaleY.toFixed(4)}x (${curWidth}x${curHeight} px)`
    };
  };

  // Math for dynamic scaling (compatibilidade para exibição estática inicial no painel)
  const initialScaling = recalculateDynamicWindowScale(selectedCard.click_point_local);
  const scaleX = initialScaling.scaleX;
  const scaleY = initialScaling.scaleY;
  const scaledLocalX = initialScaling.scaledLocalX;
  const scaledLocalY = initialScaling.scaledLocalY;
  const absX = initialScaling.absX;
  const absY = initialScaling.absY;

  const simulateAutoRecovery = (reason: string = "Janela do PPPoker ausente ou fechada") => {
    setIsRecovering(true);
    const nowStr = new Date().toISOString();
    const activeSession = sessionName.trim() || "Sessão Principal";

    const attemptRow: AuditLogRow = {
      timestamp_iso: nowStr,
      session_name: activeSession,
      event_type: "RECOVERY_ATTEMPTED",
      status: "RECOVERY",
      tournament_name: selectedCard.name_label,
      card_index: String(selectedCard.index),
      buyin_chips: selectedCard.buyin || "50",
      target_abs_x: "-",
      target_abs_y: "-",
      win_left: "0",
      win_top: "0",
      win_width: "0",
      win_height: "0",
      duration_ms: "",
      details: `Modo de Recuperação acionado: ${reason}. Executando processo "${pppokerExePath}"...`
    };

    setLogRows(prev => [attemptRow, ...prev]);
    setClickLog(`🔄 RECUPERAÇÃO ATIVA: Executando executável "${pppokerExePath}"...`);

    addToast({
      title: "RECUPERAÇÃO AUTOMÁTICA EM ANDAMENTO",
      message: `Relançando ${pppokerExePath} e aguardando restauração da janela PPPoker...`,
      eventType: "SYSTEM_RESUMED",
      severity: "WARN"
    });

    setTimeout(() => {
      const restoredNowStr = new Date().toISOString();
      setWinLeft(500);
      setWinTop(150);
      setWinWidth(787);
      setWinHeight(1470);
      winGeometryRef.current = { left: 500, top: 150, width: 787, height: 1470 };
      setHasWindowHandle(true);
      setIsPppokerProcessRunning(true);
      setIsRecovering(false);

      const successRow: AuditLogRow = {
        timestamp_iso: restoredNowStr,
        session_name: activeSession,
        event_type: "RECOVERY_SUCCESS",
        status: "SUCCESS",
        tournament_name: selectedCard.name_label,
        card_index: String(selectedCard.index),
        buyin_chips: selectedCard.buyin || "50",
        target_abs_x: "-",
        target_abs_y: "-",
        win_left: "500",
        win_top: "150",
        win_width: "787",
        win_height: "1470",
        duration_ms: "1430.8",
        details: `Processo PPPoker inicializado com sucesso, alça de janela ativa (HWND) restabelecida e janela reancorada em (500, 150) 787x1470 px.`
      };

      setLogRows(prev => [successRow, ...prev]);
      setClickLog(`✓ RECUPERAÇÃO CONCLUÍDA: Janela PPPoker reaberta, alça HWND restaurada e escala 100% recalibrada!`);

      addToast({
        title: "RECUPERAÇÃO AUTOMÁTICA CONCLUÍDA",
        message: "O cliente PPPoker foi relançado, alça HWND restaurada e a janela está 100% calibrada.",
        eventType: "CLICK_SUCCESS",
        severity: "INFO"
      });
    }, 1400);
  };

  // Simulação de Anomalia: Fechamento Súbito da Janela PPPoker durante execução
  const simulateSuddenWindowClosureAnomaly = () => {
    // 1. Invalida instantaneamente a alça HWND e colapsa a geometria da janela para 0x0
    setHasWindowHandle(false);
    setIsPppokerProcessRunning(false);
    setWinWidth(0);
    setWinHeight(0);
    setWinLeft(0);
    setWinTop(0);
    winGeometryRef.current = { left: 0, top: 0, width: 0, height: 0 };

    const nowStr = new Date().toISOString();
    const activeSession = sessionName.trim() || "Sessão Principal";

    // 2. Registro imediato da anomalia no Log de Auditoria CSV
    const anomalyRow: AuditLogRow = {
      timestamp_iso: nowStr,
      session_name: activeSession,
      event_type: "WINDOW_CLOSED",
      status: "ANOMALY",
      tournament_name: selectedCard.name_label,
      card_index: String(selectedCard.index),
      buyin_chips: selectedCard.buyin || "50",
      target_abs_x: "-",
      target_abs_y: "-",
      win_left: "0",
      win_top: "0",
      win_width: "0",
      win_height: "0",
      duration_ms: "",
      details: "ANOMALIA CRÍTICA: Janela do 'PPPoker.exe' foi fechada subitamente durante execução! Alça HWND perdida e dimensões colapsadas (0x0). recalculateDynamicWindowScale bloqueou cálculos de escala."
    };

    setLogRows(prev => [anomalyRow, ...prev]);
    setClickLog("⚠️ ANOMALIA DETECTADA: 'PPPoker.exe' fechou subitamente! Alça de janela perdida. Watchdog acionou o sistema de Auto-Recovery...");

    addToast({
      title: "ANOMALIA: PPPOKER FECHADO SUBITAMENTE",
      message: "O processo 'PPPoker.exe' encerrou subitamente! Alça HWND perdida. O Auto-Recovery foi engatilhado automaticamente.",
      eventType: "WINDOW_CLOSED",
      severity: "CRITICAL"
    });

    // 3. Se Auto-Recovery estiver ativo, engatilha o processo de recuperação automática no log
    if (autoRecoveryEnabled) {
      setTimeout(() => {
        simulateAutoRecovery("Anomalia de fechamento súbito do 'PPPoker.exe' interceptada pelo Watchdog de Alça");
      }, 700);
    } else {
      addToast({
        title: "MODO DE RECUPERAÇÃO DESATIVADO",
        message: "Ative o Modo de Recuperação para que o bot restabeleça o PPPoker automaticamente.",
        eventType: "WINDOW_CLOSED",
        severity: "WARN",
        actionLabel: "Reabrir PPPoker",
        onAction: () => simulateAutoRecovery("Restauração manual solicitada pelo operador após anomalia")
      });
    }
  };

  // Auxiliar para formatação de duração da sessão (HH:MM:SS ou MM:SS)
  const formatDuration = (totalSec: number) => {
    const hours = Math.floor(totalSec / 3600);
    const minutes = Math.floor((totalSec % 3600) / 60);
    const seconds = totalSec % 60;
    if (hours > 0) {
      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  // Status de conexão em tempo real com o cliente PPPoker
  const getPppokerConnectionStatus = () => {
    if (isRecovering) {
      return {
        label: "RECUPERANDO...",
        status: "RECOVERING" as const,
        color: "text-cyan-400",
        badgeClass: "bg-cyan-950/80 border-cyan-700 text-cyan-300 ring-1 ring-cyan-500/30",
        dotClass: "bg-cyan-400 animate-spin"
      };
    }
    if (winWidth <= 0 || winHeight <= 0) {
      return {
        label: "JANELA FECHADA",
        status: "DISCONNECTED" as const,
        color: "text-rose-400",
        badgeClass: "bg-rose-950/80 border-rose-800 text-rose-300 ring-1 ring-rose-500/30",
        dotClass: "bg-rose-500 animate-ping"
      };
    }
    if (!heartbeatActive) {
      return {
        label: "SYSTEM_HALT (30s)",
        status: "HALTED" as const,
        color: "text-amber-400",
        badgeClass: "bg-amber-950/80 border-amber-700 text-amber-300 ring-1 ring-amber-500/30",
        dotClass: "bg-amber-400 animate-pulse"
      };
    }
    return {
      label: `CONECTADO (${winWidth}x${winHeight})`,
      status: "CONNECTED" as const,
      color: "text-emerald-400",
      badgeClass: "bg-emerald-950/80 border-emerald-700 text-emerald-300 ring-1 ring-emerald-500/30",
      dotClass: "bg-emerald-400 animate-pulse"
    };
  };

  // Timer da Sessão Ativa
  useEffect(() => {
    let interval: any = null;
    if (isSessionActive && !sessionPaused) {
      interval = setInterval(() => {
        setSessionElapsedSeconds(prev => prev + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isSessionActive, sessionPaused]);

  // Handlers de Gerenciamento da Sessão de Jogo
  const handleStartSession = (customName?: string) => {
    const finalName = (customName || sessionNewNameInput || sessionName || "Sessão Principal").trim();
    setSessionName(finalName);
    setSessionElapsedSeconds(0);
    setSessionClicksCount(0);
    setIsSessionActive(true);
    setSessionPaused(false);
    setShowSessionConfigModal(false);
    setSessionNewNameInput("");

    const nowIso = new Date().toISOString();
    const startRow: AuditLogRow = {
      timestamp_iso: nowIso,
      session_name: finalName,
      event_type: "SESSION_START",
      status: "SUCCESS",
      tournament_name: "-",
      card_index: "-",
      buyin_chips: "-",
      target_abs_x: "-",
      target_abs_y: "-",
      win_left: String(winLeft),
      win_top: String(winTop),
      win_width: String(winWidth),
      win_height: String(winHeight),
      duration_ms: "0.0",
      details: `Sessão de jogo "${finalName}" iniciada manualmente pelo operador. Cronômetro zerado e contador de cliques ativo.`
    };
    setLogRows(prev => [startRow, ...prev]);

    if (soundEnabled) {
      playSynthesizedAlarm('INFO');
    }

    addToast({
      title: "SESSÃO DE JOGO INICIADA",
      message: `A sessão "${finalName}" foi iniciada. Contador de cliques e cronômetro ativados na barra superior.`,
      eventType: "SYSTEM_RESUMED",
      severity: "INFO"
    });
  };

  const handleEndSession = () => {
    const activeSession = sessionName.trim() || "Sessão Principal";
    const durationFormatted = formatDuration(sessionElapsedSeconds);
    const totalClicks = sessionClicksCount;
    setIsSessionActive(false);
    setSessionPaused(false);

    const nowIso = new Date().toISOString();
    const endRow: AuditLogRow = {
      timestamp_iso: nowIso,
      session_name: activeSession,
      event_type: "SESSION_END",
      status: "SUCCESS",
      tournament_name: "-",
      card_index: "-",
      buyin_chips: "-",
      target_abs_x: "-",
      target_abs_y: "-",
      win_left: String(winLeft),
      win_top: String(winTop),
      win_width: String(winWidth),
      win_height: String(winHeight),
      duration_ms: (sessionElapsedSeconds * 1000).toString(),
      details: `Sessão de jogo "${activeSession}" encerrada após ${durationFormatted} com um total de ${totalClicks} cliques realizados.`
    };
    setLogRows(prev => [endRow, ...prev]);

    if (soundEnabled) {
      playSynthesizedAlarm('WARN');
    }

    addToast({
      title: "SESSÃO DE JOGO ENCERRADA",
      message: `Sessão "${activeSession}" finalizada: ${durationFormatted} decorridos e ${totalClicks} cliques registrados.`,
      eventType: "SYSTEM_HALT",
      severity: "WARN"
    });
  };

  const handleTogglePauseSession = () => {
    if (!isSessionActive) return;
    const willPause = !sessionPaused;
    setSessionPaused(willPause);

    addToast({
      title: willPause ? "SESSÃO PAUSADA" : "SESSÃO RETOMADA",
      message: willPause
        ? "Cronômetro temporariamente congelado. Novos cliques ainda serão contabilizados."
        : "Cronômetro da sessão em andamento retomado.",
      eventType: "SYSTEM_RESUMED",
      severity: "INFO"
    });
  };

  // Intervenção Humana (Human Takeover) - Pausa emergencial dos cliques para o operador jogar manualmente
  const handleToggleHumanTakeover = () => {
    const nextState = !isHumanTakeover;
    setIsHumanTakeover(nextState);

    const nowIso = new Date().toISOString();
    const activeSession = sessionName.trim() || "Sessão Principal";

    if (nextState) {
      if (soundEnabled) {
        playSynthesizedAlarm('WARN');
      }
      const pauseRow: AuditLogRow = {
        timestamp_iso: nowIso,
        session_name: activeSession,
        event_type: "HUMAN_TAKEOVER_START",
        status: "HALT",
        tournament_name: "Mesas PPPoker (Ao Vivo)",
        card_index: "-",
        buyin_chips: "-",
        target_abs_x: "-",
        target_abs_y: "-",
        win_left: String(winLeft),
        win_top: String(winTop),
        win_width: String(winWidth),
        win_height: String(winHeight),
        duration_ms: "0.0",
        details: "Operador assumiu controle manual total das mesas (PAUSED_BY_USER). Todos os cliques e ações automáticas do bot estão bloqueados."
      };
      setLogRows(prev => [pauseRow, ...prev]);

      addToast({
        title: "CONTROLE MANUAL ATIVADO (BOT PAUSADO)",
        message: "O robô está pausado e não tocará no seu mouse. Você tem o controle total das decisões na mesa!",
        eventType: "SYSTEM_HALT",
        severity: "WARN"
      });
    } else {
      if (soundEnabled) {
        playSynthesizedAlarm('SUCCESS');
      }
      const resumeRow: AuditLogRow = {
        timestamp_iso: nowIso,
        session_name: activeSession,
        event_type: "HUMAN_TAKEOVER_RESUME",
        status: "SUCCESS",
        tournament_name: "Mesas PPPoker (Ao Vivo)",
        card_index: "-",
        buyin_chips: "-",
        target_abs_x: "-",
        target_abs_y: "-",
        win_left: String(winLeft),
        win_top: String(winTop),
        win_width: String(winWidth),
        win_height: String(winHeight),
        duration_ms: "0.0",
        details: "Controle das mesas devolvido ao robô (RESUMED_BY_USER). Operação autônoma restabelecida."
      };
      setLogRows(prev => [resumeRow, ...prev]);

      addToast({
        title: "CONTROLE DEVOLVIDO AO ROBÔ",
        message: "Operação autônoma retomada! O bot voltou a monitorar e agir nas mesas sozinho.",
        eventType: "SYSTEM_RESUMED",
        severity: "INFO"
      });
    }
  };

  // Ação de Iniciar ou Parar o Robô via Tecla de Atalho (F5)
  const handleToggleBotSession = () => {
    if (!isSessionActive) {
      const activeSession = sessionName.trim() || "Sessão Principal";
      setIsSessionActive(true);
      setSessionPaused(false);
      setSessionElapsedSeconds(0);
      setSessionClicksCount(0);
      addToast({
        title: "ROBÔ INICIADO (F5)",
        message: `Sessão "${activeSession}" iniciada com sucesso. Monitoramento e automação ativados.`,
        eventType: "SYSTEM_RESUMED",
        severity: "INFO"
      });
      if (soundEnabled) playSynthesizedAlarm('SUCCESS');
    } else {
      handleEndSession();
    }
  };

  // Listener Centralizado de Teclas de Atalho Globais (F5: Iniciar/Parar, F12: Takeover, 1-7: Abas Principais)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignora atalhos de dígitos se o usuário estiver focado em campos de input ou textarea
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      const isInput = tag === 'input' || tag === 'textarea' || (e.target as HTMLElement)?.isContentEditable;

      // 1. Tecla F5: Iniciar / Parar o Bot (Global, previne refresh do browser)
      if (e.key === 'F5') {
        e.preventDefault();
        handleToggleBotSession();
        return;
      }

      // 2. Tecla F12 ou Alt+P: Intervenção Humana (Human Takeover)
      if (e.key === 'F12' || (e.altKey && (e.key === 'p' || e.key === 'P'))) {
        e.preventDefault();
        handleToggleHumanTakeover();
        return;
      }

      // 3. Teclas 1 a 7 (ou Alt+1 a Alt+7): Alternar rapidamente entre as áreas principais
      if (!isInput) {
        const primaryTabMap: Record<string, { area: MainNavArea; tab: string; label: string }> = {
          '1': { area: 'overview', tab: 'overview', label: 'Visão Geral' },
          '2': { area: 'sessions', tab: 'ghost', label: 'Sessões' },
          '3': { area: 'multitable', tab: 'multitable', label: 'Monitoramento Multi-Mesas' },
          '4': { area: 'ocr_recognition', tab: 'cards', label: 'OCR e Reconhecimento' },
          '5': { area: 'events_actions', tab: 'ocr_feed', label: 'Eventos e Ações' },
          '6': { area: 'reports', tab: 'bot_brain', label: 'Relatórios' },
          '7': { area: 'settings', tab: 'installer', label: 'Configurações' },
        };

        if (primaryTabMap[e.key] && !e.ctrlKey && !e.metaKey) {
          e.preventDefault();
          const target = primaryTabMap[e.key];
          navigateToTab(target.tab, target.area);
          addToast({
            title: `NAVEGAÇÃO: ${target.label.toUpperCase()}`,
            message: `Aba alterada para "${target.label}" via atalho [${e.key}].`,
            eventType: 'PREFLIGHT_CHECK',
            severity: 'INFO'
          });
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    isSessionActive,
    sessionName,
    isHumanTakeover,
    soundEnabled,
    sessionElapsedSeconds,
    sessionClicksCount,
    winLeft,
    winTop,
    winWidth,
    winHeight
  ]);

  // Handlers para Alertas e Notificações Multi-Canal
  const handleToggleChannel = (channelId: string) => {
    setChannels(prev => prev.map(ch => ch.id === channelId ? { ...ch, enabled: !ch.enabled } : ch));
  };

  const handleUpdateChannelEndpoint = (channelId: string, endpoint: string) => {
    setChannels(prev => prev.map(ch => ch.id === channelId ? { ...ch, endpoint } : ch));
  };

  const handleToggleChannelSelect = (channelId: string) => {
    setSelectedChannelIds(prev =>
      prev.includes(channelId) ? prev.filter(id => id !== channelId) : [...prev, channelId]
    );
  };

  const handleDispatchMultiChannelTest = async () => {
    if (isDispatchingNotification) return;
    setIsDispatchingNotification(true);

    const activeSession = sessionName.trim() || "Sessão Principal";
    const targetChannels = channels.filter(ch => selectedChannelIds.includes(ch.id) && ch.enabled);

    if (targetChannels.length === 0) {
      addToast({
        title: "NENHUM CANAL ATIVO SELECIONADO",
        message: "Selecione e habilite ao menos um canal para despachar o teste de notificação.",
        eventType: "WINDOW_CLOSED",
        severity: "WARN"
      });
      setIsDispatchingNotification(false);
      return;
    }

    // Alarme sonoro correspondente à severidade
    if (soundEnabled) {
      playSynthesizedAlarm(testSeverity);
    }

    const startTime = performance.now();
    await new Promise(r => setTimeout(r, 420));
    const latency = Number((performance.now() - startTime).toFixed(1));

    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    const nowIso = now.toISOString();

    const sampleChannel = targetChannels[0];
    const preview = buildCustomNotificationPayload(
      sampleChannel.provider,
      testSeverity,
      testTitle,
      testDetails,
      activeSession,
      sampleChannel
    );

    const record: NotificationDispatchRecord = {
      id: `disp-${Date.now().toString().slice(-4)}`,
      timestamp: timeStr,
      severity: testSeverity,
      title: testTitle,
      details: testDetails,
      channelNames: targetChannels.map(c => c.name),
      httpStatus: 200,
      deliveryTimeMs: latency,
      payloadPreview: preview
    };

    setDispatchHistory(prev => [record, ...prev]);

    // Atualiza canais com último status
    setChannels(prev => prev.map(ch => {
      if (selectedChannelIds.includes(ch.id) && ch.enabled) {
        return {
          ...ch,
          lastStatus: "200 OK (Entregue)",
          lastSentAt: "Agora"
        };
      }
      return ch;
    }));

    // Registro na tabela de auditoria CSV
    const auditRow: AuditLogRow = {
      timestamp_iso: nowIso,
      session_name: activeSession,
      event_type: `ALERT_${testSeverity}_SENT`,
      status: testSeverity === 'CRITICAL' ? 'ESCALATED' : 'SUCCESS',
      tournament_name: "-",
      card_index: "-",
      buyin_chips: "-",
      target_abs_x: "-",
      target_abs_y: "-",
      win_left: String(winLeft),
      win_top: String(winTop),
      win_width: String(winWidth),
      win_height: String(winHeight),
      duration_ms: latency.toString(),
      details: `Notificação [${testSeverity}] despachada com sucesso para ${targetChannels.length} canal(is): ${targetChannels.map(c => c.name).join(", ")}. Latência: ${latency}ms.`
    };
    setLogRows(prev => [auditRow, ...prev]);

    addToast({
      title: `ALERTA [${testSeverity}] DESPACHADO COM SUCESSO`,
      message: `Payload entregue via HTTP 200 para: ${targetChannels.map(c => c.name).join(", ")} (${latency}ms).`,
      eventType: "ESCALATION_ALERT_SENT",
      severity: testSeverity
    });

    setIsDispatchingNotification(false);
  };

  // Orquestrador de Ciclo Contínuo: Countdown e Loop Automatizado
  useEffect(() => {
    let timer: any = null;
    if (orchIsRunning && !orchIsPaused) {
      timer = setInterval(() => {
        setOrchCountdown(prev => {
          if (prev <= 1) {
            executeOrchestratorCycle(false);
            const jitterOffset = Math.round((Math.random() - 0.5) * orchJitter * 2);
            return Math.max(3, orchLoopInterval + jitterOffset);
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [orchIsRunning, orchIsPaused, orchLoopInterval, orchJitter, orchMaxBuyin, antiDupRecords]);

  const executeOrchestratorCycle = (isManual: boolean = false) => {
    const nextCycle = orchCycleCount + 1;
    setOrchCycleCount(nextCycle);
    const nowStr = new Date().toLocaleTimeString();
    const nowIso = new Date().toISOString();
    const activeSession = sessionName.trim() || "Sessão Orquestrada 01";

    setOrchTournamentsScanned(prev => prev + 4);

    // Avalia torneios do lobby contra regras de elegibilidade
    const candidates = TOURNAMENTS_DATA.filter(t => t.eligible && (parseFloat(t.buyin || "0") <= orchMaxBuyin));
    setOrchTournamentsEligible(prev => prev + candidates.length);

    // Identifica se há algum torneio elegível que ainda não está no registro de anti-duplicação
    const unreg = candidates.find(t => {
      const key = `${t.name_label.replace(/[^A-Z0-9]/gi, '').toUpperCase()}_${t.buyin || '0'}_${(t.start_time || 'LIVE').replace(/[^A-Z0-9]/gi, '').toUpperCase()}`;
      return !antiDupRecords.some(r => r.key === key && r.status === 'REGISTERED');
    });

    if (unreg) {
      // Encontrou torneio elegível novo: efetua a inscrição (Módulos 4 e 5)
      const unregKey = `${unreg.name_label.replace(/[^A-Z0-9]/gi, '').toUpperCase()}_${unreg.buyin || '0'}_${(unreg.start_time || 'LIVE').replace(/[^A-Z0-9]/gi, '').toUpperCase()}`;
      setOrchTournamentsRegistered(prev => prev + 1);

      if (isSessionActive) {
        setSessionClicksCount(prev => prev + 2); // 1 clique no lobby + 1 confirmação
      }

      const newRecord: AntiDupItem = {
        key: unregKey,
        tournamentName: unreg.name_label,
        buyin: unreg.buyin || "50",
        startTime: unreg.start_time || "23:00",
        lastRegistered: "Agora",
        status: "REGISTERED",
        count: 1,
        sessionName: activeSession
      };
      setAntiDupRecords(prev => [newRecord, ...prev]);

      const logSuccess: OrchestratorActivityLog = {
        id: `orch-log-${Date.now()}-1`,
        time: nowStr,
        cycle: nextCycle,
        type: "SUCCESS",
        message: `Inscrição confirmada com sucesso: '${unreg.name_label}' (${unreg.buyin} fichas). Vaga garantida e salva no registro persistente.`,
        tag: "INSCRIÇÃO_OK"
      };

      setOrchActivityLogs(prev => [logSuccess, ...prev.slice(0, 24)]);

      // Gravação na auditoria CSV
      const auditRow: AuditLogRow = {
        timestamp_iso: nowIso,
        session_name: activeSession,
        event_type: "ORCHESTRATOR_REGISTRATION_SUCCESS",
        status: "SUCCESS",
        tournament_name: unreg.name_label,
        card_index: String(unreg.index),
        buyin_chips: unreg.buyin || "50",
        target_abs_x: String(unreg.click_point_local[0]),
        target_abs_y: String(unreg.click_point_local[1]),
        win_left: String(winLeft),
        win_top: String(winTop),
        win_width: String(winWidth),
        win_height: String(winHeight),
        duration_ms: "980.5",
        details: `Ciclo #${nextCycle}: Torneio '${unreg.name_label}' inscrito pelo Orquestrador. Anti-duplicação vinculada.`
      };
      setLogRows(prev => [auditRow, ...prev]);

      if (soundEnabled) {
        playSynthesizedAlarm('INFO');
      }

      addToast({
        title: "ORQUESTRADOR: INSCRIÇÃO CONCLUÍDA",
        message: `Torneio '${unreg.name_label}' inscrito no Ciclo #${nextCycle}. Registro anti-duplicação ativo.`,
        eventType: "CLICK_SUCCESS",
        severity: "INFO"
      });

    } else {
      // Todos os torneios elegíveis já constam no registro: ANTI-DUPLICAÇÃO IGNORA COM SUCESSO!
      setOrchTournamentsSkippedDup(prev => prev + candidates.length);

      const skipLog: OrchestratorActivityLog = {
        id: `orch-log-${Date.now()}-skip`,
        time: nowStr,
        cycle: nextCycle,
        type: "SKIP_DUP",
        message: `Varredura #${nextCycle}: ${candidates.length} torneios elegíveis identificados, porém todos já constam como INSCRITOS no registro persistente. Cliques evitados por Anti-Duplicação.`,
        tag: "ANTI_DUP"
      };
      setOrchActivityLogs(prev => [skipLog, ...prev.slice(0, 24)]);

      const skipRow: AuditLogRow = {
        timestamp_iso: nowIso,
        session_name: activeSession,
        event_type: "TOURNAMENT_SKIPPED_ALREADY_REGISTERED",
        status: "SKIPPED",
        tournament_name: candidates[0]?.name_label || "Multiplos Torneios",
        card_index: "-",
        buyin_chips: candidates[0]?.buyin || "50",
        target_abs_x: "-",
        target_abs_y: "-",
        win_left: String(winLeft),
        win_top: String(winTop),
        win_width: String(winWidth),
        win_height: String(winHeight),
        duration_ms: "1.2",
        details: `Ciclo #${nextCycle}: ${candidates.length} torneios ignorados por anti-duplicação (inscrições já ativas no registro JSON).`
      };
      setLogRows(prev => [skipRow, ...prev]);

      if (isManual) {
        addToast({
          title: "CICLO EXECUTADO: ANTI-DUPLICAÇÃO ATIVA",
          message: `${candidates.length} torneios elegíveis foram verificados e ignorados pois já estão inscritos.`,
          eventType: "SYSTEM_RESUMED",
          severity: "INFO"
        });
      }
    }
  };

  const handleStartOrchestrator = () => {
    setOrchIsRunning(true);
    setOrchIsPaused(false);
    setOrchCountdown(orchLoopInterval);

    const nowIso = new Date().toISOString();
    const startRow: AuditLogRow = {
      timestamp_iso: nowIso,
      session_name: sessionName.trim() || "Sessão Orquestrada 01",
      event_type: "ORCHESTRATOR_STARTED",
      status: "SUCCESS",
      tournament_name: "-",
      card_index: "-",
      buyin_chips: "-",
      target_abs_x: "-",
      target_abs_y: "-",
      win_left: String(winLeft),
      win_top: String(winTop),
      win_width: String(winWidth),
      win_height: String(winHeight),
      duration_ms: "0.0",
      details: `Orquestrador de Ciclo Contínuo iniciado (intervalo: ${orchLoopInterval}s ±${orchJitter}s, max_buyin: ${orchMaxBuyin} fichas).`
    };
    setLogRows(prev => [startRow, ...prev]);

    addToast({
      title: "ORQUESTRADOR CONTÍNUO INICIADO",
      message: `Loop ativo com intervalo de ${orchLoopInterval}s (±${orchJitter}s). Monitoramento anti-duplicação ativado.`,
      eventType: "SYSTEM_RESUMED",
      severity: "INFO"
    });
  };

  const handleTogglePauseOrchestrator = () => {
    const nextPaused = !orchIsPaused;
    setOrchIsPaused(nextPaused);
    const nowIso = new Date().toISOString();
    const nowStr = new Date().toLocaleTimeString();
    const activeSession = sessionName.trim() || "Sessão Orquestrada 01";

    if (nextPaused) {
      // Registrar Pausa na Auditoria CSV e nos Logs Operacionais
      const pauseRow: AuditLogRow = {
        timestamp_iso: nowIso,
        session_name: activeSession,
        event_type: "ORCHESTRATOR_PAUSED",
        status: "HALT",
        tournament_name: "-",
        card_index: "-",
        buyin_chips: "-",
        target_abs_x: "-",
        target_abs_y: "-",
        win_left: String(winLeft),
        win_top: String(winTop),
        win_width: String(winWidth),
        win_height: String(winHeight),
        duration_ms: "0.0",
        details: `Orquestrador colocado em PAUSA temporária pelo operador. Inscrições autônomas interrompidas sem encerrar o processo. Countdown congelado em ${orchCountdown}s.`
      };
      setLogRows(prev => [pauseRow, ...prev]);

      const logPause: OrchestratorActivityLog = {
        id: `orch-log-${Date.now()}-pause`,
        time: nowStr,
        cycle: orchCycleCount,
        type: "WAIT",
        message: `Orquestrador pausado temporariamente pelo operador. Inscrições autônomas congeladas. Processo mantido ativo em background (timer: ${orchCountdown}s).`,
        tag: "ORQUESTRADOR_PAUSADO"
      };
      setOrchActivityLogs(prev => [logPause, ...prev.slice(0, 24)]);

      addToast({
        title: "ORQUESTRADOR PAUSADO TEMPORARIAMENTE",
        message: `Inscrições suspensas sem matar o processo. O countdown de ${orchCountdown}s foi congelado. Clique em Retomar para continuar.`,
        eventType: "SYSTEM_HALT",
        severity: "WARN"
      });
    } else {
      // Registrar Retomada na Auditoria CSV e nos Logs Operacionais
      const resumeRow: AuditLogRow = {
        timestamp_iso: nowIso,
        session_name: activeSession,
        event_type: "ORCHESTRATOR_RESUMED",
        status: "SUCCESS",
        tournament_name: "-",
        card_index: "-",
        buyin_chips: "-",
        target_abs_x: "-",
        target_abs_y: "-",
        win_left: String(winLeft),
        win_top: String(winTop),
        win_width: String(winWidth),
        win_height: String(winHeight),
        duration_ms: "0.0",
        details: `Orquestrador retomado pelo operador. Varredura e inscrições autônomas reativadas. Countdown retomado a partir de ${orchCountdown}s.`
      };
      setLogRows(prev => [resumeRow, ...prev]);

      const logResume: OrchestratorActivityLog = {
        id: `orch-log-${Date.now()}-resume`,
        time: nowStr,
        cycle: orchCycleCount,
        type: "SUCCESS",
        message: `Orquestrador retomado pelo operador. Varredura automática reativada. Próximo ciclo em ${orchCountdown}s.`,
        tag: "ORQUESTRADOR_RETOMADO"
      };
      setOrchActivityLogs(prev => [logResume, ...prev.slice(0, 24)]);

      addToast({
        title: "ORQUESTRADOR RETOMADO",
        message: `Execução de varredura e inscrições autônomas reativadas com sucesso.`,
        eventType: "SYSTEM_RESUMED",
        severity: "INFO"
      });
    }
  };

  const handleStopOrchestrator = () => {
    setOrchIsRunning(false);
    setOrchIsPaused(false);

    const nowIso = new Date().toISOString();
    const stopRow: AuditLogRow = {
      timestamp_iso: nowIso,
      session_name: sessionName.trim() || "Sessão Orquestrada 01",
      event_type: "ORCHESTRATOR_STOPPED",
      status: "SUCCESS",
      tournament_name: "-",
      card_index: "-",
      buyin_chips: "-",
      target_abs_x: "-",
      target_abs_y: "-",
      win_left: String(winLeft),
      win_top: String(winTop),
      win_width: String(winWidth),
      win_height: String(winHeight),
      duration_ms: "0.0",
      details: `Orquestrador encerrado pelo operador após ${orchCycleCount} ciclos executados e ${orchTournamentsRegistered} inscrições.`
    };
    setLogRows(prev => [stopRow, ...prev]);

    addToast({
      title: "ORQUESTRADOR CONTÍNUO ENCERRADO",
      message: `Execução do loop finalizada pelo operador. Registro persistente salvo em disco.`,
      eventType: "SYSTEM_HALT",
      severity: "WARN"
    });
  };

  const handleClearAntiDup = () => {
    setAntiDupRecords([]);
    addToast({
      title: "REGISTRO ANTI-DUPLICAÇÃO ZERADO",
      message: "A memória de torneios inscritos foi limpa. Novos ciclos poderão re-inscrever qualquer torneio elegível.",
      eventType: "SYSTEM_RESUMED",
      severity: "WARN"
    });
  };

  const handleRemoveAntiDupItem = (keyToRemove: string) => {
    setAntiDupRecords(prev => prev.filter(r => r.key !== keyToRemove));
    addToast({
      title: "TORNEIO REMOVIDO DO REGISTRO",
      message: "O bloqueio anti-duplicação para este torneio foi removido. Pronto para nova tentativa.",
      eventType: "SYSTEM_RESUMED",
      severity: "INFO"
    });
  };

  const simulateClick = () => {
    setIsSimulatingClick(true);
    setClickPhase('IDLE');
    setClickLog("Verificando integridade da janela e watchdog de heartbeat...");

    const activeSession = sessionName.trim() || "Sessão Principal";

    // -1. Checagem de Intervenção Humana (Human Takeover ativo)
    if (isHumanTakeover) {
      setTimeout(() => {
        setClickLog("⏸️ CLIQUE SUSPENSO: O operador está no controle manual das mesas (Human Takeover). O robô não moverá o mouse.");
        addToast({
          title: "BOT PAUSADO: CONTROLE MANUAL ATIVO",
          message: "O operador está no controle da mesa. Clique autônomo cancelado para evitar interferência no mouse.",
          eventType: "SYSTEM_HALT",
          severity: "WARN"
        });
        setIsSimulatingClick(false);
        setClickPhase('IDLE');
      }, 200);
      return;
    }

    // 0. Leitura inicial instantânea de escala e geometria via PyGetWindow
    const startGeo = recalculateDynamicWindowScale(selectedCard.click_point_local);

    // 1. Checagem de watchdog: se o sistema está em SYSTEM_HALT, aborta!
    if (!heartbeatActive) {
      setTimeout(() => {
        const nowStr = new Date().toISOString();
        const abortRow: AuditLogRow = {
          timestamp_iso: nowStr,
          session_name: activeSession,
          event_type: "CLICK_ABORTED",
          status: "ABORTED",
          tournament_name: selectedCard.name_label,
          card_index: String(selectedCard.index),
          buyin_chips: selectedCard.buyin || "50",
          target_abs_x: "-",
          target_abs_y: "-",
          win_left: String(winLeft),
          win_top: String(winTop),
          win_width: String(winWidth),
          win_height: String(winHeight),
          duration_ms: "",
          details: "Tentativa abortada: Watchdog em estado SYSTEM_HALT por inatividade prolongada (> 30s). Ações bloqueadas."
        };
        setLogRows(prev => [abortRow, ...prev]);
        setClickLog("✗ CLIQUE ABORTADO: Sistema em SYSTEM_HALT! O watchdog protegeu o desktop contra ação obsoleta.");

        addToast({
          title: "CLIQUE BLOQUEADO PELO WATCHDOG",
          message: "O bot está em SYSTEM_HALT! Clique abortado preventivamente para evitar ações obsoletas.",
          eventType: "SYSTEM_HALT",
          severity: "CRITICAL",
          actionLabel: "Restabelecer Pulsação",
          onAction: () => resumeHeartbeat()
        });

        setIsSimulatingClick(false);
        setClickPhase('IDLE');
      }, 300);
      return;
    }

    // 2. Checagem de Janela Fechada ou Alça HWND Perdida (com suporte a Modo de Recuperação)
    if (winWidth <= 0 || winHeight <= 0 || !startGeo.hasActiveHandle || !hasWindowHandle || !isPppokerProcessRunning) {
      if (autoRecoveryEnabled) {
        setIsSimulatingClick(false);
        setClickPhase('IDLE');
        simulateAutoRecovery("Clique abortado porque o processo 'PPPoker.exe' perdeu a alça de janela ativa ou foi fechado");
        return;
      } else {
        setTimeout(() => {
          const nowStr = new Date().toISOString();
          const closedRow: AuditLogRow = {
            timestamp_iso: nowStr,
            session_name: activeSession,
            event_type: "WINDOW_CLOSED",
            status: "ABORTED",
            tournament_name: selectedCard.name_label,
            card_index: String(selectedCard.index),
            buyin_chips: selectedCard.buyin || "50",
            target_abs_x: "-",
            target_abs_y: "-",
            win_left: "0",
            win_top: "0",
            win_width: "0",
            win_height: "0",
            duration_ms: "",
            details: "Tentativa abortada: Janela do PPPoker não foi encontrada no desktop. Modo de Recuperação desativado."
          };
          setLogRows(prev => [closedRow, ...prev]);
          setClickLog("✗ CLIQUE ABORTADO: Janela PPPoker fechada. Ative o Modo de Recuperação na aba Auditoria para reabertura automática.");

          addToast({
            title: "JANELA FECHADA: CLIQUE CANCELADO",
            message: "A janela do PPPoker não está aberta no Windows. Ative o Modo de Recuperação para relançá-la.",
            eventType: "WINDOW_CLOSED",
            severity: "CRITICAL",
            actionLabel: "Reabrir PPPoker",
            onAction: () => simulateAutoRecovery("Restauração solicitada pelo operador via notificação")
          });

          setIsSimulatingClick(false);
          setClickPhase('IDLE');
        }, 300);
        return;
      }
    }

    // 3. Configurações de Velocidade e Atraso de Camuflagem (com suporte a Teste A/B Alternado)
    const speedProfileMap = {
      fast: { moveMs: 160, pressMs: 65, label: "Rápido (160ms)" },
      natural: { moveMs: 300, pressMs: 95, label: "Natural (300ms)" },
      slow: { moveMs: 650, pressMs: 130, label: "Lento (650ms)" }
    };

    let activeVariantTag = "";
    let activeStratName = "";
    let activeSpeed = clickSpeed;
    let activeDelayMin = delayMinMs;
    let activeDelayMax = delayMaxMs;
    let activeUseJitter = applyJitter;

    if (abTestEnabled) {
      const variantToRun = nextAbVariant;
      const strat = variantToRun === 'A' ? strategyA : strategyB;
      activeVariantTag = `VARIANTE_${variantToRun}`;
      activeStratName = strat.name;
      activeSpeed = strat.speed;
      activeDelayMin = strat.delayMinMs;
      activeDelayMax = strat.delayMaxMs;
      activeUseJitter = strat.applyJitter;
      // Alterna automaticamente para o próximo disparo
      setNextAbVariant(prev => prev === 'A' ? 'B' : 'A');
    }

    const profile = speedProfileMap[activeSpeed];
    const reactionDelay = (randomDelayEnabled || abTestEnabled)
      ? Math.round(activeDelayMin + Math.random() * Math.max(10, activeDelayMax - activeDelayMin))
      : 0;

    const totalCalculatedMs = reactionDelay + profile.moveMs + profile.pressMs;

    setLastLatencyBreakdown({
      reactionMs: reactionDelay,
      moveMs: profile.moveMs,
      pressMs: profile.pressMs,
      totalMs: totalCalculatedMs,
      speedLabel: abTestEnabled ? `[${activeVariantTag}] ${activeStratName} (${profile.label})` : profile.label
    });

    // Curva de aceleração neuromuscular humana assimétrica (Fase balística 0-35% + desaceleração inercial 35-100%)
    // Elimina padrões robóticos de velocidade constante detectáveis por heurísticas anti-bot
    const humanBezierEase = (t: number): number => {
      if (t <= 0) return 0;
      if (t >= 1) return 1;
      if (t < 0.35) {
        const p = t / 0.35;
        return 0.40 * (p * p * (3.0 - 2.0 * p));
      } else {
        const p = (t - 0.35) / 0.65;
        return 0.40 + 0.60 * (1.0 - Math.pow(1.0 - p, 2.8));
      }
    };

    // Ponto de partida do cursor (posição anterior ou centro do quadrante da janela)
    const p0 = {
      x: startGeo.winLeft + Math.round(startGeo.winWidth * 0.40),
      y: startGeo.winTop + Math.round(startGeo.winHeight * 0.32)
    };

    // Alvo nominal preliminar e vetor euclidiano
    const targetNominal = { x: startGeo.absX, y: startGeo.absY };
    const dx = targetNominal.x - p0.x;
    const dy = targetNominal.y - p0.y;
    const dist = Math.max(12, Math.sqrt(dx * dx + dy * dy));
    const nx = -dy / dist;
    const ny = dx / dist;

    // Pontos de controle P1 e P2 com deflexão perpendicular orgânica
    const curveSign = Math.random() > 0.5 ? 1 : -1;
    const dev1 = curveSign * (0.05 + Math.random() * 0.08) * dist;
    const dev2 = curveSign * (0.03 + Math.random() * 0.06) * dist;
    const p1 = {
      x: Math.round(p0.x + 0.33 * dx + nx * dev1),
      y: Math.round(p0.y + 0.33 * dy + ny * dev1)
    };
    const p2 = {
      x: Math.round(p0.x + 0.67 * dx + nx * dev2),
      y: Math.round(p0.y + 0.67 * dy + ny * dev2)
    };
    const jitterMagnitude = activeUseJitter ? 1.5 : 0;

    // FASE 1: Atraso Cognitivo / Camuflagem Humana
    if (reactionDelay > 0) {
      setClickPhase('DELAY');
      setClickLog(
        abTestEnabled
          ? `⏳ [1/3 Camuflagem A/B - ${activeVariantTag}]: Aplicando atraso de ${reactionDelay}ms (${activeStratName})...`
          : `⏳ [1/3 Camuflagem]: Aplicando atraso cognitivo aleatório de ${reactionDelay}ms antes de mover o mouse...`
      );
    }

    setTimeout(() => {
      // FASE 2: Movimento Suave da Trajetória Bézier com Aceleração Humana e Jitter
      setClickPhase('MOVING');
      setClickLog(
        `🖱️ [2/3 Movimento]: pyautogui.moveTo executando curva Bézier cúbica com aceleração humana customizada e micro-jitter (D: ${Math.round(dist)}px, perfil: ${profile.label}, P1: (${p1.x}, ${p1.y}), P2: (${p2.x}, ${p2.y}), jitter: ±${jitterMagnitude}px)...`
      );

      setTimeout(() => {
        // FASE 3: Pressão Física Mecânica
        setClickPhase('CLICKING');
        setClickLog(`⚡ [3/3 Disparo]: Pressionando botão esquerdo do mouse via pyautogui por ${profile.pressMs}ms com sustentação neuromuscular...`);

        setTimeout(() => {
          // Recálculo dinâmico e instantâneo de scaleX e scaleY diretamente da API PyGetWindow
          const freshGeo = recalculateDynamicWindowScale(selectedCard.click_point_local);

          // Validação de segurança: se a alça foi perdida durante o percurso balístico, aborta imediatamente
          if (!freshGeo.hasActiveHandle || freshGeo.winWidth <= 0 || freshGeo.winHeight <= 0) {
            setIsSimulatingClick(false);
            setClickPhase('IDLE');
            const nowStr = new Date().toISOString();
            const abortRow: AuditLogRow = {
              timestamp_iso: nowStr,
              session_name: activeSession,
              event_type: "CLICK_ABORTED",
              status: "ABORTED",
              tournament_name: selectedCard.name_label,
              card_index: String(selectedCard.index),
              buyin_chips: selectedCard.buyin || "50",
              target_abs_x: "-",
              target_abs_y: "-",
              win_left: "0",
              win_top: "0",
              win_width: "0",
              win_height: "0",
              duration_ms: "",
              details: `Tentativa abortada: ${freshGeo.handleError || "Alça de janela do PPPoker perdida durante movimento do cursor."}`
            };
            setLogRows(prev => [abortRow, ...prev]);
            setClickLog(`✗ CLIQUE ABORTADO: ${freshGeo.handleError || "Alça de janela do 'PPPoker.exe' perdida!"}`);

            if (autoRecoveryEnabled) {
              simulateAutoRecovery("Alça de janela do PPPoker perdida durante o movimento balístico do mouse");
            }
            return;
          }

          const hasResized = (
            freshGeo.winWidth !== startGeo.winWidth ||
            freshGeo.winHeight !== startGeo.winHeight ||
            freshGeo.winLeft !== startGeo.winLeft ||
            freshGeo.winTop !== startGeo.winTop
          );

          const jitterX = activeUseJitter ? Math.round((Math.random() - 0.5) * 6) : 0;
          const jitterY = activeUseJitter ? Math.round((Math.random() - 0.5) * 4) : 0;
          const finalX = freshGeo.absX + jitterX;
          const finalY = freshGeo.absY + jitterY;
          const nowStr = new Date().toISOString();

          // Registra telemetria completa da cinemática motora
          setLastTrajectory({
            p0,
            p1,
            p2,
            target: { x: finalX, y: finalY },
            distance: Math.round(dist),
            jitterPx: jitterMagnitude,
            accelerationCurve: "humanBezierEase (Fitts Law / Balística + Inercial)"
          });

          const abPrefix = abTestEnabled
            ? `[TESTE_AB: ${activeVariantTag} - "${activeStratName}"] `
            : '';

          const dynamicAdjustmentNote = hasResized
            ? ` | [Auto-Ajuste PyGetWindow: redimensionado em tempo real de ${startGeo.winWidth}x${startGeo.winHeight} para ${freshGeo.winWidth}x${freshGeo.winHeight} px, scaleX=${freshGeo.scaleX.toFixed(4)}x, scaleY=${freshGeo.scaleY.toFixed(4)}x]`
            : ` | [PyGetWindow: ${freshGeo.winWidth}x${freshGeo.winHeight} px, scaleX=${freshGeo.scaleX.toFixed(4)}x, scaleY=${freshGeo.scaleY.toFixed(4)}x]`;

          const newRow: AuditLogRow = {
            timestamp_iso: nowStr,
            session_name: activeSession,
            event_type: "CLICK_SUCCESS",
            status: "SUCCESS",
            tournament_name: selectedCard.name_label,
            card_index: String(selectedCard.index),
            buyin_chips: selectedCard.buyin || "50",
            target_abs_x: String(finalX),
            target_abs_y: String(finalY),
            win_left: String(freshGeo.winLeft),
            win_top: String(freshGeo.winTop),
            win_width: String(freshGeo.winWidth),
            win_height: String(freshGeo.winHeight),
            duration_ms: totalCalculatedMs.toFixed(1),
            details: `${abPrefix}Clique despachado com sucesso via pyautogui.moveTo (Bézier cúbica com aceleração humana assimétrica, jitter: ±${Math.abs(jitterX)}px, P1:(${p1.x},${p1.y}), P2:(${p2.x},${p2.y}), delay: +${reactionDelay}ms, total: ${totalCalculatedMs.toFixed(1)}ms)${dynamicAdjustmentNote}`
          };

          setLogRows(prev => [newRow, ...prev]);
          if (isSessionActive) {
            setSessionClicksCount(prev => prev + 1);
          }
          setClickLog(
            hasResized
              ? `⚡ [Auto-Ajuste PyGetWindow]: Redimensionamento detectado durante execução (${startGeo.winWidth}x${startGeo.winHeight} -> ${freshGeo.winWidth}x${freshGeo.winHeight})! Coordenadas corrigidas instantaneamente para (${finalX}, ${finalY}) com escala ${freshGeo.scaleX.toFixed(4)}x via pyautogui.moveTo (Bézier + jitter)!`
              : abTestEnabled
              ? `✓ [TESTE A/B: ${activeVariantTag}] Clique executado via pyautogui.moveTo em (${finalX}, ${finalY}) com curva Bézier e aceleração humana! Latência: ${totalCalculatedMs.toFixed(1)}ms.`
              : `✓ Clique executado com sucesso via pyautogui.moveTo em (${finalX}, ${finalY}) [Bézier Cúbica + Jitter | scaleX=${freshGeo.scaleX.toFixed(4)}x, scaleY=${freshGeo.scaleY.toFixed(4)}x] [Latência: ${totalCalculatedMs.toFixed(1)}ms]`
          );
          setLastBeatTime("agora (0.1s atrás)");
          setClickPhase('DONE');
          setIsSimulatingClick(false);

          addToast({
            title: abTestEnabled ? `TESTE A/B: DISPARO DA ${activeVariantTag}` : "CLIQUE CAMUFLADO DESPACHADO",
            message: abTestEnabled
              ? `${activeStratName} executada via pyautogui.moveTo (Bézier + jitter) em ${totalCalculatedMs.toFixed(1)}ms. Próximo disparo: Variante ${nextAbVariant === 'A' ? 'B' : 'A'}.`
              : `Alvo: ${selectedCard.name_label} em (${finalX}, ${finalY}). Perfil: ${profile.label} (Bézier cúbica com aceleração humana).`,
            eventType: "CLICK_SUCCESS",
            severity: "INFO"
          });
        }, profile.pressMs);
      }, profile.moveMs);
    }, reactionDelay);
  };

  const runAbBatch = async (totalClicks: number = 10) => {
    if (isAbBatchRunning || isSimulatingClick) return;
    setIsAbBatchRunning(true);
    setAbBatchProgress({ current: 0, total: totalClicks });

    addToast({
      title: "BATERIA DE TESTE A/B INICIADA",
      message: `Executando bateria comparativa de ${totalClicks} cliques alternados entre Variante A e B...`,
      eventType: "CLICK_SUCCESS",
      severity: "INFO"
    });

    let currentVar: 'A' | 'B' = nextAbVariant;
    const activeSession = sessionName.trim() || "Sessão Principal";

    for (let i = 0; i < totalClicks; i++) {
      setAbBatchProgress({ current: i + 1, total: totalClicks });
      const strat = currentVar === 'A' ? strategyA : strategyB;
      const speedProfileMap = {
        fast: { moveMs: 160, pressMs: 65, label: "Rápido (160ms)" },
        natural: { moveMs: 300, pressMs: 95, label: "Natural (300ms)" },
        slow: { moveMs: 650, pressMs: 130, label: "Lento (650ms)" }
      };
      const profile = speedProfileMap[strat.speed];
      const reactionDelay = Math.round(strat.delayMinMs + Math.random() * Math.max(10, strat.delayMaxMs - strat.delayMinMs));
      const totalMs = reactionDelay + profile.moveMs + profile.pressMs;

      const jitterX = strat.applyJitter ? Math.round((Math.random() - 0.5) * 6) : 0;
      const jitterY = strat.applyJitter ? Math.round((Math.random() - 0.5) * 4) : 0;
      const finalX = absX + jitterX;
      const finalY = absY + jitterY;
      const nowStr = new Date().toISOString();

      const newRow: AuditLogRow = {
        timestamp_iso: nowStr,
        session_name: activeSession,
        event_type: "CLICK_SUCCESS",
        status: "SUCCESS",
        tournament_name: selectedCard.name_label,
        card_index: String(selectedCard.index),
        buyin_chips: selectedCard.buyin || "50",
        target_abs_x: String(finalX),
        target_abs_y: String(finalY),
        win_left: String(winLeft),
        win_top: String(winTop),
        win_width: String(winWidth),
        win_height: String(winHeight),
        duration_ms: totalMs.toFixed(1),
        details: `[TESTE_AB: VARIANTE_${currentVar} - "${strat.name}"] Despachado com sucesso via pyautogui.moveTo (Bézier cúbica + aceleração humana assimétrica, jitter: ±${Math.abs(jitterX)}px, delay: +${reactionDelay}ms, latência total: ${totalMs.toFixed(1)}ms)`
      };

      setLogRows(prev => [newRow, ...prev]);
      if (isSessionActive) {
        setSessionClicksCount(prev => prev + 1);
      }
      setLastLatencyBreakdown({
        reactionMs: reactionDelay,
        moveMs: profile.moveMs,
        pressMs: profile.pressMs,
        totalMs: totalMs,
        speedLabel: `[${currentVar}] ${strat.name} (${profile.label})`
      });
      setClickLog(`[Bateria A/B ${i + 1}/${totalClicks}]: Variante ${currentVar} ("${strat.name}") disparada com latência de ${totalMs.toFixed(1)}ms!`);

      currentVar = currentVar === 'A' ? 'B' : 'A';
      setNextAbVariant(currentVar);

      // Intervalo entre cada clique na bateria para fluidez
      await new Promise(r => setTimeout(r, 450));
    }

    setIsAbBatchRunning(false);
    addToast({
      title: "BATERIA A/B CONCLUÍDA",
      message: `${totalClicks} registros gravados com sucesso no CSV de auditoria! Verifique as métricas comparativas no painel.`,
      eventType: "CLICK_SUCCESS",
      severity: "INFO"
    });
  };

  // Funções analíticas do Teste A/B
  const abLogs = logRows.filter(r => r.details.includes('[TESTE_AB:'));
  const abLogsA = abLogs.filter(r => r.details.includes('VARIANTE_A'));
  const abLogsB = abLogs.filter(r => r.details.includes('VARIANTE_B'));

  const computeVariantStats = (rows: AuditLogRow[]) => {
    const latencies = rows.map(r => parseFloat(r.duration_ms)).filter(n => !isNaN(n) && n > 0);
    if (!latencies.length) return { count: 0, avg: 0, min: 0, max: 0, stdDev: 0 };
    const avg = latencies.reduce((a, b) => a + b, 0) / latencies.length;
    const min = Math.min(...latencies);
    const max = Math.max(...latencies);
    const variance = latencies.reduce((acc, val) => acc + Math.pow(val - avg, 2), 0) / latencies.length;
    return {
      count: latencies.length,
      avg: Math.round(avg),
      min: Math.round(min),
      max: Math.round(max),
      stdDev: Math.round(Math.sqrt(variance))
    };
  };

  const statsA = computeVariantStats(abLogsA);
  const statsB = computeVariantStats(abLogsB);

  // Estados para o Gráfico Dinâmico Recharts na Aba de Auditoria
  const [auditChartView, setAuditChartView] = useState<'timeline' | 'rounds' | 'breakdown' | 'averages'>('timeline');
  const [auditChartFilter, setAuditChartFilter] = useState<'ALL' | 'A' | 'B'>('ALL');

  // Prepara dados dinâmicos ordenados cronologicamente (mais antigo -> mais recente)
  const chartAbLogs = [...abLogs].reverse();

  // 1. Dados de Linha do Tempo (Timeline de Disparos)
  const chartTimelineData = chartAbLogs.map((row, idx) => {
    const isA = row.details.includes('VARIANTE_A');
    const lat = parseFloat(row.duration_ms) || 0;

    // Extrai tempos detalhados se presentes no log
    const matchReaction = row.details.match(/(?:Reação:|delay(?:_camuflagem)?=|\+)(\d+(?:\.\d+)?)\s*ms/i);
    const matchMove = row.details.match(/(?:Movimento:|move=)(\d+(?:\.\d+)?)\s*ms/i);
    const matchPress = row.details.match(/Pressão:\s*(\d+(?:\.\d+)?)\s*ms/i);

    const reactionMs = matchReaction ? Math.round(parseFloat(matchReaction[1])) : (isA ? 450 : 220);
    const moveMs = matchMove ? Math.round(parseFloat(matchMove[1])) : (isA ? 300 : 160);
    const pressMs = matchPress ? Math.round(parseFloat(matchPress[1])) : (isA ? 95 : 65);

    return {
      index: idx + 1,
      label: `#${idx + 1}`,
      variant: isA ? ('A' as const) : ('B' as const),
      variantName: isA ? strategyA.name : strategyB.name,
      latencyA: isA ? lat : null,
      latencyB: !isA ? lat : null,
      totalLatency: lat,
      reactionMs,
      moveMs,
      pressMs,
      timestamp: row.timestamp_iso ? (row.timestamp_iso.split('T')[1]?.substring(0, 8) || '') : '',
      session: row.session_name || 'Sessão Principal'
    };
  });

  // 2. Dados Comparativos por Rodada (Pares Variante A vs Variante B)
  const chartRoundsData = (() => {
    const rounds: Array<{
      round: number;
      label: string;
      latencyA: number | null;
      latencyB: number | null;
      delta: number | null;
    }> = [];
    const logsA = chartAbLogs.filter(r => r.details.includes('VARIANTE_A'));
    const logsB = chartAbLogs.filter(r => r.details.includes('VARIANTE_B'));
    const maxLen = Math.max(logsA.length, logsB.length);

    for (let i = 0; i < maxLen; i++) {
      const a = logsA[i];
      const b = logsB[i];
      const latA = a ? parseFloat(a.duration_ms) || 0 : null;
      const latB = b ? parseFloat(b.duration_ms) || 0 : null;
      const delta = (latA !== null && latB !== null) ? Math.round(latA - latB) : null;

      rounds.push({
        round: i + 1,
        label: `Par #${i + 1}`,
        latencyA: latA,
        latencyB: latB,
        delta
      });
    }
    return rounds;
  })();

  // 3. Dados Agregados de Médias & Mínimo/Máximo
  const chartAveragesData = [
    {
      name: `Variante A (${strategyA.name})`,
      shortName: 'Variante A',
      media: statsA.avg,
      min: statsA.min,
      max: statsA.max,
      desvio: statsA.stdDev,
      amostras: statsA.count,
      fill: '#10b981'
    },
    {
      name: `Variante B (${strategyB.name})`,
      shortName: 'Variante B',
      media: statsB.avg,
      min: statsB.min,
      max: statsB.max,
      desvio: statsB.stdDev,
      amostras: statsB.count,
      fill: '#f59e0b'
    }
  ];

  // Escalation watchdog timer effect: when system is in SYSTEM_HALT, increments elapsed counter
  useEffect(() => {
    let interval: any = null;
    if (!heartbeatActive && !escalationSent) {
      interval = setInterval(() => {
        setHaltElapsedSeconds(prev => {
          const nextVal = prev + 1;
          if (nextVal >= escalationTimeout) {
            triggerEscalationDispatch(nextVal, false);
          }
          return nextVal;
        });
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [heartbeatActive, escalationSent, escalationTimeout]);

  const triggerEscalationDispatch = (elapsedSec: number = escalationTimeout, isManualTest: boolean = false) => {
    setEscalationSent(true);
    const nowStr = new Date().toISOString();
    const maskedUrl = maskWebhook(webhookUrl);
    const elapsedMin = (elapsedSec / 60).toFixed(1);

    const escalationRow: AuditLogRow = {
      timestamp_iso: nowStr,
      session_name: sessionName || "Sessão Principal",
      event_type: "ESCALATION_ALERT_SENT",
      status: "ESCALATED",
      tournament_name: "-",
      card_index: "-",
      buyin_chips: "-",
      target_abs_x: "-",
      target_abs_y: "-",
      win_left: String(winLeft),
      win_top: String(winTop),
      win_width: String(winWidth),
      win_height: String(winHeight),
      duration_ms: "148.2",
      details: isManualTest
        ? `Disparo manual de teste de notificação remota para webhook (${maskedUrl}). Teste operacional verificado.`
        : `Sistema em SYSTEM_HALT por mais de ${elapsedSec}s (~${elapsedMin} min). Notificação remota de emergência enviada via webhook (${maskedUrl}).`
    };

    setLogRows(prev => [escalationRow, ...prev]);

    if (soundEnabled) {
      playSynthesizedAlarm('ESCALATION');
    }

    addToast({
      title: isManualTest ? "TESTE DE WEBHOOK DISPARADO COM SUCESSO" : "ALERTA REMOTO DE ESCALADA DISPARADO (> 5 MIN)",
      message: isManualTest
        ? `Payload operacional enviado para ${maskedUrl} via provedor ${webhookProvider.toUpperCase()}.`
        : `Sistema paralisado há ${elapsedSec}s. Notificação remota despachada para ${maskedUrl}!`,
      eventType: "ESCALATION_ALERT_SENT",
      severity: "CRITICAL",
      actionLabel: "Ver Payload",
      onAction: () => setShowPayloadPreview(true)
    });

    setClickLog(
      `🚨 ESCALADA REMOTA: Webhook despachado para ${maskedUrl} após ${elapsedSec}s em SYSTEM_HALT.`
    );
  };

  const simulateHeartbeatHalt = () => {
    const nowStr = new Date().toISOString();
    const haltRow: AuditLogRow = {
      timestamp_iso: nowStr,
      session_name: sessionName || "Sessão Principal",
      event_type: "SYSTEM_HALT",
      status: "HALT",
      tournament_name: "-",
      card_index: "-",
      buyin_chips: "-",
      target_abs_x: "-",
      target_abs_y: "-",
      win_left: String(winLeft),
      win_top: String(winTop),
      win_width: String(winWidth),
      win_height: String(winHeight),
      duration_ms: "",
      details: "Inatividade detectada: sem pulsação por 30.0s (possível congelamento de software). Ações bloqueadas preventivamente."
    };

    setHeartbeatActive(false);
    setHaltElapsedSeconds(0);
    setEscalationSent(false);
    setLastBeatTime("congelado há > 30s");
    setLogRows(prev => [haltRow, ...prev]);
    setClickLog("⚠️ ALERTA DE WATCHDOG: 30 segundos de inatividade detectados! 'SYSTEM_HALT' registrado no CSV. Vigilância de escalada remota (>5m) armada.");

    // Dispara notificação toast e alarme sonoro
    addToast({
      title: "PARALISAÇÃO CRÍTICA DO BOT: SYSTEM_HALT",
      message: "Watchdog detectou 30s de inatividade. O bot paralisou todas as ações para evitar cliques obsoletos. Vigilância de escalada remota (>5 min) iniciada.",
      eventType: "SYSTEM_HALT",
      severity: "CRITICAL",
      actionLabel: "Restabelecer Pulsação",
      onAction: () => resumeHeartbeat()
    });
  };

  const resumeHeartbeat = () => {
    const nowStr = new Date().toISOString();
    const resumeRow: AuditLogRow = {
      timestamp_iso: nowStr,
      session_name: sessionName || "Sessão Principal",
      event_type: "SYSTEM_RESUMED",
      status: "SUCCESS",
      tournament_name: "-",
      card_index: "-",
      buyin_chips: "-",
      target_abs_x: "-",
      target_abs_y: "-",
      win_left: String(winLeft),
      win_top: String(winTop),
      win_width: String(winWidth),
      win_height: String(winHeight),
      duration_ms: "",
      details: escalationSent
        ? "Watchdog restabelecido pelo operador. Pulsação reativada e alerta de escalada remota redefinido."
        : "Watchdog de heartbeat restabelecido pelo operador. Pulsação reativada com sucesso."
    };

    setHeartbeatActive(true);
    setHaltElapsedSeconds(0);
    setEscalationSent(false);
    setLastBeatTime("agora (0.1s atrás)");
    setLogRows(prev => [resumeRow, ...prev]);
    setClickLog("✓ Heartbeat restabelecido! O bot voltou a monitorar a pulsação e a vigilância remota foi normalizada.");

    addToast({
      title: "WATCHDOG RESTABELECIDO",
      message: "Pulsação do bot reativada pelo operador. Monitoramento ativo.",
      eventType: "SYSTEM_RESUMED",
      severity: "INFO"
    });
  };

  const simulateAnomaly = (type: 'CLOSE' | 'RESIZE') => {
    const nowStr = new Date().toISOString();
    const activeSession = sessionName.trim() || "Sessão Principal";
    let newRow: AuditLogRow;

    if (type === 'CLOSE') {
      setWinWidth(0);
      setWinHeight(0);

      newRow = {
        timestamp_iso: nowStr,
        session_name: activeSession,
        event_type: "WINDOW_CLOSED",
        status: "ABORTED",
        tournament_name: selectedCard.name_label,
        card_index: String(selectedCard.index),
        buyin_chips: selectedCard.buyin || "50",
        target_abs_x: "-",
        target_abs_y: "-",
        win_left: "0",
        win_top: "0",
        win_width: "0",
        win_height: "0",
        duration_ms: "",
        details: autoRecoveryEnabled
          ? `Janela do PPPoker fechada detectada. Modo de Recuperação ativado para relançar "${pppokerExePath}".`
          : "Tentativa abortada: Janela do PPPoker não foi encontrada no desktop. Modo de recuperação desativado."
      };

      addToast({
        title: "ALERTA DE SEGURANÇA: JANELA FECHADA",
        message: autoRecoveryEnabled
          ? "Janela PPPoker fechada. O Modo de Recuperação está pronto para restaurar o executável automaticamente."
          : "Janela do PPPoker não foi encontrada no Windows (fechada ou minimizada). Tentativa de clique abortada.",
        eventType: "WINDOW_CLOSED",
        severity: "CRITICAL",
        actionLabel: autoRecoveryEnabled ? "Restaurar Janela Agora" : "Ativar Recuperação",
        onAction: () => simulateAutoRecovery("Restauração disparada via notificação de janela fechada")
      });
    } else {
      newRow = {
        timestamp_iso: nowStr,
        session_name: activeSession,
        event_type: "RESOLUTION_CHANGED",
        status: "ABORTED",
        tournament_name: selectedCard.name_label,
        card_index: String(selectedCard.index),
        buyin_chips: selectedCard.buyin || "50",
        target_abs_x: "-",
        target_abs_y: "-",
        win_left: String(winLeft),
        win_top: String(winTop),
        win_width: "1400",
        win_height: "450",
        duration_ms: "",
        details: "Tentativa abortada: Proporção W/H deformada para 3.11 (esperado retrato 0.35..0.85)."
      };

      addToast({
        title: "ALERTA DE DEFORMAÇÃO: RESOLUÇÃO ANÔMALA",
        message: "A janela sofreu deformação drástica (W/H fora de 0.35..0.85). Clique cancelado preventivamente.",
        eventType: "RESOLUTION_CHANGED",
        severity: "WARN"
      });
    }

    setLogRows(prev => [newRow, ...prev]);
    setClickLog(`✗ ALERTA: ${newRow.details} Evento registrado no CSV!`);
  };

  const filteredLogs = logRows.filter(row => {
    if (sessionFilter !== 'ALL' && (row.session_name || "Sessão Principal") !== sessionFilter) {
      return false;
    }
    if (logFilter === 'ALL') return true;
    if (logFilter === 'SUCCESS') return row.status === 'SUCCESS';
    if (logFilter === 'ABORTED') return row.status === 'ABORTED' || row.status === 'ERROR';
    if (logFilter === 'HALT') return row.status === 'HALT' || row.event_type === 'SYSTEM_HALT';
    if (logFilter === 'ESCALATED') return row.status === 'ESCALATED' || row.event_type === 'ESCALATION_ALERT_SENT';
    if ((logFilter as string) === 'RECOVERY') return row.status === 'RECOVERY' || row.event_type.startsWith('RECOVERY');
    return true;
  });

  const availableSessions = Array.from(
    new Set(logRows.map(r => r.session_name || "Sessão Principal").filter(Boolean))
  );

  const runFullM5Simulation = () => {
    if (m5AutoRunning) return;
    setM5AutoRunning(true);
    setM5Step(0);
    setM5StepLogs([]);

    const addStepLog = (stepName: string, details: string, durationMs: number) => {
      const nowStr = new Date().toLocaleTimeString();
      setM5StepLogs(prev => [...prev, { step: stepName, status: "SUCCESS", time: nowStr, durationMs, details }]);
    };

    // Passo 0 -> 1: Transição e Carregamento da Tela de Detalhes
    setTimeout(() => {
      setM5Step(1);
      addStepLog("WAIT_DETAIL_SCREEN", "Transição de tela identificada. Estrutura e detalhes do torneio carregados.", 284.5);

      if (m5Scenario === 'ALREADY_REGISTERED') {
        setTimeout(() => {
          setM5Step(4);
          addStepLog("STATUS_ALREADY_REGISTERED", "Jogador já está inscrito. Clique de registro cancelado para economizar tempo.", 95.0);
          setM5AutoRunning(false);
          addToast({
            title: "TORNEIO JÁ INSCRITO",
            message: "O bot identificou que sua inscrição já estava garantida. Clique cancelado preventivamente.",
            eventType: "SYSTEM_RESUMED",
            severity: "INFO"
          });
        }, 600);
        return;
      }

      // Passo 1 -> 2: Clique no Botão Principal "Registrar"
      setTimeout(() => {
        setM5Step(2);
        addStepLog("CLICK_REGISTER_BUTTON", "Botão de registro principal acionado suavemente na barra inferior em (393, 1396).", 310.2);
        if (isSessionActive) {
          setSessionClicksCount(prev => prev + 1);
        }

        // Passo 2 -> 3: Modal de Confirmação de Buy-in
        setTimeout(() => {
          setM5Step(3);
          addStepLog("CONFIRM_BUYIN_MODAL", "Caixa de diálogo modal detectada. Custo: 50 fichas conferido. Clicado em 'Confirmar'.", 225.4);
          if (isSessionActive) {
            setSessionClicksCount(prev => prev + 1);
          }

          if (m5Scenario === 'INSUFFICIENT_FUNDS') {
            setTimeout(() => {
              addStepLog("INSUFFICIENT_FUNDS", "Falha de saldo: fichas insuficientes na conta PPPoker.", 160.0);
              setM5AutoRunning(false);
              addToast({
                title: "SALDO INSUFICIENTE",
                message: "O aplicativo PPPoker informou saldo insuficiente de fichas para este buy-in.",
                eventType: "WINDOW_CLOSED",
                severity: "WARN"
              });
            }, 600);
            return;
          }

          // Passo 3 -> 4: Validação do Status "Inscrito"
          setTimeout(() => {
            setM5Step(4);
            addStepLog("VERIFY_REGISTRATION_STATUS", "Vaga confirmada pelo servidor do PPPoker! Botão alterado para 'Inscrito'.", 195.8);

            // Grava evento oficial no log de auditoria CSV
            const nowIso = new Date().toISOString();
            const regRow: AuditLogRow = {
              timestamp_iso: nowIso,
              session_name: sessionName || "Sessão Principal",
              event_type: "REGISTRATION_SUCCESS",
              status: "SUCCESS",
              tournament_name: selectedCard.name_label,
              card_index: String(selectedCard.index),
              buyin_chips: selectedCard.buyin || "50",
              target_abs_x: "393",
              target_abs_y: "1396",
              win_left: String(winLeft),
              win_top: String(winTop),
              win_width: String(winWidth),
              win_height: String(winHeight),
              duration_ms: "1015.9",
              details: `Módulo 5: Inscrição confirmada com sucesso no torneio ${selectedCard.name_label} (50 fichas).`
            };
            setLogRows(prev => [regRow, ...prev]);

            addToast({
              title: "INSCRIÇÃO CONFIRMADA COM SUCESSO",
              message: `Vaga garantida no torneio ${selectedCard.name_label}! Status 'Inscrito' validado e auditado.`,
              eventType: "SYSTEM_RESUMED",
              severity: "INFO"
            });

            // Passo 4 -> 5: Retorno ao Lobby Principal
            setTimeout(() => {
              setM5Step(5);
              addStepLog("RETURN_TO_LOBBY", "Seta Voltar acionada no canto superior esquerdo (56, 80). Retornado ao Lobby principal.", 210.0);
              setM5AutoRunning(false);
            }, 1000);

          }, 800);
        }, 700);
      }, 700);
    }, 600);
  };

  const stepNextM5 = () => {
    setM5Step(prev => (prev < 5 ? prev + 1 : 0));
  };

  const resetM5 = () => {
    setM5Step(1);
    setM5AutoRunning(false);
    setM5StepLogs([
      {
        step: "WAIT_DETAIL_SCREEN",
        status: "SUCCESS",
        time: new Date().toLocaleTimeString(),
        durationMs: 284.5,
        details: "Transição identificada: Tela de Detalhes carregada com sucesso."
      }
    ]);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans relative">
      {/* Visual Toast Notification Stack (Fixa no topo direito) */}
      <aside aria-label="Notificações do Sistema" className="fixed top-18 right-5 z-50 flex flex-col gap-3 max-w-md w-full pointer-events-none">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`pointer-events-auto p-4 rounded-xl border shadow-2xl backdrop-blur-md transition-all duration-300 animate-in fade-in slide-in-from-top-3 ${
              toast.severity === 'CRITICAL'
                ? 'bg-rose-950/95 border-rose-600/90 text-rose-100 ring-2 ring-rose-500/40 shadow-rose-950/50'
                : toast.severity === 'WARN'
                ? 'bg-amber-950/95 border-amber-600/90 text-amber-100 ring-2 ring-amber-500/30 shadow-amber-950/50'
                : 'bg-slate-900/95 border-slate-700 text-slate-100 shadow-slate-950/50'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <div className={`mt-0.5 p-2 rounded-lg flex items-center justify-center shrink-0 ${
                  toast.severity === 'CRITICAL'
                    ? 'bg-rose-900/70 text-rose-300 ring-2 ring-rose-500/50 animate-pulse'
                    : toast.severity === 'WARN'
                    ? 'bg-amber-900/70 text-amber-300 ring-2 ring-amber-500/40'
                    : 'bg-slate-800 text-emerald-400'
                }`}>
                  {toast.severity === 'CRITICAL' ? (
                    <AlertOctagon className="w-5 h-5 text-rose-300" />
                  ) : toast.severity === 'WARN' ? (
                    <AlertTriangle className="w-5 h-5 text-amber-300" />
                  ) : (
                    <Bell className="w-5 h-5 text-emerald-400" />
                  )}
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] uppercase font-mono font-black px-1.5 py-0.5 rounded border tracking-wider ${
                      toast.severity === 'CRITICAL'
                        ? 'bg-rose-900/60 border-rose-500/50 text-rose-200'
                        : toast.severity === 'WARN'
                        ? 'bg-amber-900/60 border-amber-500/50 text-amber-200'
                        : 'bg-slate-800 border-slate-700 text-emerald-300'
                    }`}>
                      {toast.eventType}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {toast.timestamp}
                    </span>
                  </div>
                  <h4 className="font-bold text-xs text-white leading-tight">
                    {toast.title}
                  </h4>
                  <p className="text-[11px] text-slate-200/90 leading-snug">
                    {toast.message}
                  </p>
                  {toast.actionLabel && toast.onAction && (
                    <button
                      onClick={() => {
                        toast.onAction?.();
                        dismissToast(toast.id);
                      }}
                      className="mt-2 px-3 py-1 rounded bg-white text-slate-950 hover:bg-slate-200 text-xs font-bold transition-colors shadow flex items-center gap-1.5"
                    >
                      <RefreshCw className="w-3 h-3 text-slate-950" />
                      <span>{toast.actionLabel}</span>
                    </button>
                  )}
                </div>
              </div>
              <button
                onClick={() => dismissToast(toast.id)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-black/40 transition-colors"
                title="Fechar notificação"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </aside>

      {/* 1. Header Limpo e Profissional (Prompt Seção 3) */}
      <AppCleanHeader
        sessionName={sessionName || "Sessão Principal"}
        isSessionActive={isSessionActive}
        sessionPaused={sessionPaused}
        onToggleSession={() => {
          if (!isSessionActive) {
            setSessionNewNameInput(sessionName || "Sessão Principal");
            setShowSessionConfigModal(true);
          } else {
            handleTogglePauseSession();
          }
        }}
        onPauseSession={handleTogglePauseSession}
        onStopSession={handleEndSession}
        onOpenSessionModal={() => {
          setSessionNewNameInput(sessionName || "Sessão Principal");
          setShowSessionConfigModal(true);
        }}
        onOpenSettings={() => navigateToTab('installer', 'settings')}
        soundEnabled={soundEnabled}
        onToggleSound={() => {
          const next = !soundEnabled;
          setSoundEnabled(next);
          if (next) playSynthesizedAlarm('SUCCESS');
        }}
        pppokerConnected={winWidth > 0 && winHeight > 0}
        pppokerPid={8492}
      />

      {/* Banner de Ajuda Rápida: Instalador Executável Oficial (.EXE) */}
      {showInstallBanner && (
        <div className="bg-gradient-to-r from-emerald-950/95 via-slate-900 to-cyan-950/95 border-b-2 border-emerald-500/50 px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs shadow-lg relative z-20">
          <div className="flex items-center gap-2.5 text-slate-200">
            <span className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
              <Zap className="w-4 h-4 animate-bounce" />
            </span>
            <span>
              <strong className="text-emerald-400">Instalador Oficial com Dependências Pré-instaladas:</strong> Instale no Windows com 1 clique e atalho no Desktop! 
              <span className="text-slate-400 ml-1.5 hidden lg:inline">(Se o Chrome pausar o download como <code className="text-amber-300 font-mono">.crdownload</code>, aperte <kbd className="text-amber-300 font-bold">Ctrl+J</kbd> &rarr; &quot;Manter mesmo assim&quot;)</span>
            </span>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <a
              href="/VisualPilot_Setup.exe"
              download="VisualPilot_Setup.exe"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-xs shadow-md shadow-emerald-500/20 transition-all cursor-pointer ring-1 ring-emerald-300/50"
              title="Instalador Executável Oficial do Windows (~52 MB)"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Baixar .EXE (~52 MB)</span>
            </a>
            <a
              href="/VisualPilot_Instalador_Completo.zip"
              download="VisualPilot_Instalador_Completo.zip"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-700 hover:bg-cyan-600 text-white font-bold text-xs shadow transition-all cursor-pointer border border-cyan-500/40"
              title="Baixar versão portátil em arquivo ZIP (O Chrome baixa direto sem confirmação)"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Baixar .ZIP (Sem Bloqueio)</span>
            </a>
            <button
              onClick={() => setShowInstallerModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-600 text-white font-bold text-xs shadow transition-all cursor-pointer"
            >
              <span>Opções & Guia</span>
            </button>
            <button
              onClick={() => setShowInstallBanner(false)}
              className="p-1 text-slate-400 hover:text-white transition-colors cursor-pointer"
              title="Dispensar aviso"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Banner de Intervenção Manual / Human Takeover (Bot Pausado pelo Usuário) */}
      {isHumanTakeover && (
        <div className="bg-gradient-to-r from-amber-950 via-amber-900 to-amber-950 border-b-2 border-amber-500 p-3 sm:p-4 text-amber-100 flex flex-wrap items-center justify-between gap-4 shadow-2xl sticky top-[65px] z-40 animate-in slide-in-from-top duration-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500 text-slate-950 flex items-center justify-center font-black shrink-0 animate-pulse shadow-lg">
              <Gamepad2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="font-black text-sm sm:text-base text-white">
                  🕹️ VOCÊ ESTÁ NO CONTROLE MANUAL TOTAL DAS MESAS
                </h4>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-400 text-slate-950 uppercase tracking-wide">
                  Bot Pausado
                </span>
              </div>
              <p className="text-xs text-amber-200/90 mt-0.5">
                Os cliques automáticos do robô estão <strong>100% bloqueados</strong>. Você pode tomar decisões, pagar, aumentar ou desistir no PPPoker com liberdade total.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleToggleHumanTakeover}
              className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-xs flex items-center gap-2 shadow-lg shadow-emerald-500/30 transition-all cursor-pointer animate-pulse active:scale-95"
            >
              <Play className="w-4 h-4 fill-current" />
              <span>Devolver Controle ao Bot (Retomar)</span>
              <kbd className="hidden sm:inline px-1.5 py-0.5 bg-slate-950/20 text-slate-950 rounded text-[10px] font-mono">F12</kbd>
            </button>
          </div>
        </div>
      )}

      {/* Session Config / New Session Modal */}
      {showSessionConfigModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full shadow-2xl p-5 space-y-4 text-slate-100">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-emerald-950 border border-emerald-800 text-emerald-400">
                  <PlayCircle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-100">Gerenciador de Sessão de Jogo</h3>
                  <p className="text-[11px] text-slate-400">Controle o identificador gravado na coluna CSV e o cronômetro</p>
                </div>
              </div>
              <button
                onClick={() => setShowSessionConfigModal(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                  Nome / Identificador da Sessão:
                </label>
                <input
                  type="text"
                  value={sessionNewNameInput}
                  onChange={(e) => setSessionNewNameInput(e.target.value)}
                  placeholder="Ex: Sessão Matinal 01, Sessão Noturna MTT..."
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-xs font-mono text-emerald-300 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <span className="text-[11px] text-slate-400 block mb-1.5 font-medium">
                  Atalhos Predefinidos Rápidos:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {["Sessão Matinal 01", "Sessão Noturna MTT", "Turbo Grind 50", "Bateria Calibração 1470", "Teste A/B Camuflagem"].map(preset => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setSessionNewNameInput(preset)}
                      className={`text-[11px] px-2.5 py-1 rounded border transition-colors cursor-pointer ${
                        sessionNewNameInput === preset
                          ? 'bg-emerald-950 border-emerald-600 text-emerald-300 font-bold'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 text-[11px] text-slate-400 space-y-1">
                <div className="flex items-center gap-1.5 text-slate-300 font-semibold">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Sincronização com Auditoria e Disparos</span>
                </div>
                <p>
                  Ao iniciar uma nova sessão, o cronômetro é reiniciado e cada novo clique ou alerta multi-canal registrado no CSV conterá este identificador exato na coluna <code className="text-emerald-400 font-mono">session_name</code>.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setShowSessionConfigModal(false)}
                className="px-3.5 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 text-xs font-medium transition-colors cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => handleStartSession(sessionNewNameInput)}
                className="px-4 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold shadow flex items-center gap-1.5 transition-all cursor-pointer"
              >
                <PlayCircle className="w-4 h-4" />
                <span>{isSessionActive ? 'Reiniciar Sessão com Este Nome' : 'Iniciar Sessão Agora'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Container com Layout Lateral por Módulos Operacionais */}
      <div className="flex-1 max-w-[1720px] w-full mx-auto p-4 sm:p-6 flex flex-col lg:flex-row gap-6 items-start">
        {/* Sidebar Lateral de Navegação Agrupada por Módulos Operacionais */}
        {/* Barra Lateral Reorganizada (7 Áreas Estratégicas - Prompt Seção 2) */}
        <AppNavigationSidebar
          currentArea={mainSection}
          currentSubTab={activeTab}
          onSelectArea={(area, subTab) => {
            setMainSection(area);
            if (subTab) {
              setActiveTab(subTab as any);
            } else {
              if (area === 'overview') setActiveTab('overview');
              else if (area === 'sessions') setActiveTab('ghost');
              else if (area === 'multitable') setActiveTab('multitable');
              else if (area === 'ocr_recognition') setActiveTab('cards');
              else if (area === 'events_actions') setActiveTab('ocr_feed' as any);
              else if (area === 'reports') setActiveTab('monthly_roi' as any);
              else if (area === 'settings') setActiveTab('installer');
            }
          }}
          isSessionActive={isSessionActive}
        />

        {/* Área Principal de Conteúdo */}
        <main className="flex-1 min-w-0 w-full space-y-6">
          {/* 1. Visão Geral Unificada (Prompt Seção 4) */}
          {mainSection === 'overview' && (
            <OverviewDashboard
              isSessionActive={isSessionActive}
              sessionPaused={sessionPaused}
              sessionElapsedSeconds={sessionElapsedSeconds}
              sessionClicksCount={sessionClicksCount}
              preflightStatus={preflightStatus}
              onNavigateTab={(tab) => navigateToTab(tab)}
              onToggleSession={handleTogglePauseSession}
            />
          )}

          {/* 2. Feed de Eventos OCR Reestruturado (Prompt Seção 6) */}
          {mainSection === 'events_actions' && activeTab === 'ocr_feed' && (
            <OcrEventsFeed />
          )}
          {/* Tab: Central de Instalação Automática & Executável (1-Clique) */}
          {activeTab === 'installer' && (
            <InstallerDownloadCenter />
          )}

          {/* Tab: Manual Descomplicado Focado em Clareza Extrema (Nível 5 Anos) */}
          {activeTab === 'manual_facil' && (
            <ManualVisualPilot />
          )}

          {/* Tab: Multi-Table Real-Time In-Game Grid (Fase 2) */}
          {activeTab === 'multitable' && (
            <MultiTableGrid
              isHumanTakeover={isHumanTakeover}
              onToggleTakeover={handleToggleHumanTakeover}
              onNotify={(title, message, severity) => {
                addToast({
                  title,
                  message,
                  eventType: 'PREFLIGHT_CHECK',
                  severity
                });
              }}
              onOpenCardInspector={() => setActiveTab('cards')}
              onOpenHeroActions={() => setActiveTab('hero_actions')}
            />
          )}

        {/* Tab: Card Recognition (Hero + Board) & 4-Color Deck Inspector */}
        {activeTab === 'cards' && (
          <CardRecognitionInspector />
        )}

        {/* Tab: Hero Action Buttons & Bet Sizing Simulator */}
        {activeTab === 'hero_actions' && (
          <HeroActionInspector
            onNotify={(title, message, severity) => {
              addToast({
                title,
                message,
                eventType: 'PREFLIGHT_CHECK',
                severity
              });
            }}
          />
        )}

        {/* Tab: Table Numerical OCR, Stacks & Positions (Dealer) */}
        {activeTab === 'table_numerical' && (
          <TableNumericalOcrInspector
            onNotify={(title, message, severity) => {
              addToast({
                title,
                message,
                eventType: 'PREFLIGHT_CHECK',
                severity
              });
            }}
          />
        )}

        {/* Tab: GTO Pre-Flop Decision Engine (169 Hands Matrix & Nash) */}
        {activeTab === 'preflop_gto' && (
          <PreflopDecisionEngineInspector
            onNotify={(title, message, severity) => {
              addToast({
                title,
                message,
                eventType: 'PREFLIGHT_CHECK',
                severity
              });
            }}
          />
        )}

        {/* Tab: GTO Post-Flop 3-Bet Pot Equity Engine */}
        {activeTab === 'postflop_gto' && (
          <PostflopGtoInspector
            onNotify={(title, message, severity) => {
              addToast({
                title,
                message,
                eventType: 'PREFLIGHT_CHECK',
                severity
              });
            }}
          />
        )}

        {/* Tab: Bot Strategic Brain & Evolutionary Learning Engine */}
        {activeTab === 'bot_brain' && (
          <BotBrainEvolutionInspector
            onNotify={(title, message, severity) => {
              addToast({
                title,
                message,
                eventType: 'PREFLIGHT_CHECK',
                severity
              });
            }}
          />
        )}

        {/* Tab: Relatório de Estimativa de ROI Mensal (Recharts) */}
        {activeTab === 'monthly_roi' && (
          <MonthlyRoiRechartsReport
            logRows={logRows}
          />
        )}

        {/* Tab: Estimador de Fichas e Lucro de Torneios */}
        {activeTab === 'tournament_profit' && (
          <TournamentChipsProfitEstimator
            logRows={logRows}
            onFilterByStatus={(status) => setLogFilter(status as any)}
          />
        )}

        {/* Tab: Modo Fantasma de Segurança & Espectador de Mesa (--spectator / --dry-run) */}
        {activeTab === 'ghost' && (
          <GhostSpectatorInspector />
        )}

        {/* Tab: Manual de Uso, Arquitetura & Guia Operacional em PDF */}
        {activeTab === 'manual' && (
          <UserManualPdfViewer />
        )}

        {/* Tab 0: Continuous Loop Orchestrator Dashboard (lobby_orchestrator.py) */}
        {activeTab === 'orchestrator' && (
          <div className="space-y-6">
            {/* Header Banner */}
            <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-950/70 via-slate-900 to-slate-900 border border-emerald-700/60 flex flex-wrap items-center justify-between gap-4 shadow-xl">
              <div className="flex items-center gap-3.5">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold shrink-0 transition-all ${
                  orchIsRunning
                    ? 'bg-emerald-500/30 border border-emerald-400 text-emerald-300 ring-2 ring-emerald-500/40 shadow-lg shadow-emerald-500/20'
                    : 'bg-slate-800 border border-slate-700 text-slate-300'
                }`}>
                  <Repeat className={`w-5 h-5 ${orchIsRunning ? 'animate-spin text-emerald-300' : 'text-emerald-400'}`} />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                      <span>Orquestrador de Ciclo Contínuo</span>
                      <code className="text-[11px] font-mono px-1.5 py-0.2 rounded bg-slate-950 text-cyan-300 border border-slate-800">
                        lobby_orchestrator.py
                      </code>
                    </h3>
                    <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-emerald-500 text-slate-950">
                      Fase 1 Concluída
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Coordena a esteira contínua de varredura do Lobby, filtragem de buy-in, <strong>controle inteligente de anti-duplicação de inscrições</strong> com persistência JSON, clique camuflado e máquina de estados de confirmação pós-clique.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {/* Loop Countdown Pill */}
                {orchIsRunning ? (
                  orchIsPaused ? (
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-950/80 border border-amber-600 text-xs font-mono text-amber-300 shadow-sm animate-pulse">
                      <Pause className="w-3.5 h-3.5 text-amber-400" />
                      <span>Loop Pausado: <strong>{orchCountdown}s congelados</strong></span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-950/80 border border-emerald-600 text-xs font-mono text-emerald-300 shadow-sm animate-pulse">
                      <Timer className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Próximo Ciclo em: <strong>{orchCountdown}s</strong></span>
                    </div>
                  )
                ) : (
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-400">
                    <StopCircle className="w-3.5 h-3.5 text-slate-500" />
                    <span>Orquestrador Parado</span>
                  </div>
                )}

                <a
                  href="/VisualPilot_Orquestrador_CicloContinuo.zip"
                  download
                  className="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow transition-all cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Baixar Pacote (.ZIP)</span>
                </a>
              </div>
            </div>

            {/* Metric Telemetry Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs">
                  <span className="flex items-center gap-1.5 font-medium">
                    <Repeat className="w-4 h-4 text-cyan-400" />
                    Ciclos Executados
                  </span>
                  <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded font-bold border ${
                    orchIsRunning
                      ? (orchIsPaused ? 'bg-amber-950 text-amber-300 border-amber-800' : 'bg-emerald-950 text-emerald-300 border-emerald-800')
                      : 'bg-slate-950 text-slate-500 border-slate-800'
                  }`}>
                    {orchIsRunning ? (orchIsPaused ? 'EM PAUSA' : 'LOOP ATIVO') : 'PARADO'}
                  </span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-black text-white font-mono">{orchCycleCount}</span>
                  <span className="text-xs text-slate-400">ciclos completos</span>
                </div>
                <p className="text-[11px] text-slate-500 font-mono">
                  Intervalo: {orchLoopInterval}s (±{orchJitter}s jitter)
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs">
                  <span className="flex items-center gap-1.5 font-medium">
                    <Layers className="w-4 h-4 text-emerald-400" />
                    Varredura de Cartões
                  </span>
                  <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/80 px-1.5 py-0.2 rounded border border-cyan-800 font-bold">
                    MTT ≤ {orchMaxBuyin}
                  </span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-black text-white font-mono">{orchTournamentsScanned}</span>
                  <span className="text-xs text-slate-400">lidos ({orchTournamentsEligible} elegíveis)</span>
                </div>
                <p className="text-[11px] text-slate-500 font-mono">
                  Filtrados por status aberto e formato
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs">
                  <span className="flex items-center gap-1.5 font-medium">
                    <ShieldCheck className="w-4 h-4 text-amber-400" />
                    Anti-Duplicação Ativa
                  </span>
                  <span className="text-[10px] font-mono text-amber-300 bg-amber-950/80 px-1.5 py-0.2 rounded border border-amber-800 font-bold">
                    TTL 24h
                  </span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-black text-amber-300 font-mono">{orchTournamentsSkippedDup}</span>
                  <span className="text-xs text-slate-400">ignorados</span>
                </div>
                <p className="text-[11px] text-slate-500 font-mono">
                  Evitou cliques repetidos em vagas já garantidas
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs">
                  <span className="flex items-center gap-1.5 font-medium">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    Inscrições Concluídas
                  </span>
                  <span className="text-[10px] font-mono text-emerald-300 bg-emerald-950/80 px-1.5 py-0.2 rounded border border-emerald-800 font-bold">
                    Módulos 4 + 5
                  </span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-black text-emerald-400 font-mono">{orchTournamentsRegistered}</span>
                  <span className="text-xs text-slate-400">vagas garantidas</span>
                </div>
                <p className="text-[11px] text-slate-500 font-mono">
                  Salvas no JSON e auditadas no CSV
                </p>
              </div>
            </div>

            {/* Interactive 2-Column Workspace */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column: Loop Configuration & Operational Controls */}
              <div className="lg:col-span-5 space-y-4">
                <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80 shadow-xl space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                      <SlidersHorizontal className="w-4 h-4 text-emerald-400" />
                      <h3 className="font-bold text-xs text-slate-100 uppercase tracking-wide">
                        Parâmetros do Loop do Orquestrador
                      </h3>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400">
                      Sessão: {sessionName || "Sessão Matinal 01"}
                    </span>
                  </div>

                  {/* Action Buttons: Iniciar / Pausar / Retomar / Encerrar */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
                    {!orchIsRunning ? (
                      <button
                        type="button"
                        onClick={handleStartOrchestrator}
                        className="py-2.5 px-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-emerald-950/50 transition-all cursor-pointer ring-2 ring-emerald-500/40"
                      >
                        <Play className="w-4 h-4 fill-slate-950" />
                        <span>Iniciar Loop</span>
                      </button>
                    ) : (
                      <>
                        {orchIsPaused ? (
                          <button
                            type="button"
                            onClick={handleTogglePauseOrchestrator}
                            className="py-2.5 px-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-emerald-950/50 transition-all cursor-pointer ring-2 ring-emerald-500/40"
                            title="Retoma o ciclo de varredura e inscrições autônomas"
                          >
                            <Play className="w-4 h-4 fill-slate-950" />
                            <span>Retomar Inscrições</span>
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={handleTogglePauseOrchestrator}
                            className="py-2.5 px-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-amber-950/50 transition-all cursor-pointer ring-2 ring-amber-500/40"
                            title="Pausa temporariamente as inscrições sem finalizar o processo"
                          >
                            <Pause className="w-4 h-4" />
                            <span>Pausar Inscrições</span>
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={handleStopOrchestrator}
                          className="py-2.5 px-3 rounded-xl bg-rose-950/80 hover:bg-rose-900 border border-rose-700 text-rose-200 font-bold text-xs flex items-center justify-center gap-2 shadow-md transition-all cursor-pointer"
                          title="Encerra o loop e encerra o processo"
                        >
                          <StopCircle className="w-4 h-4 text-rose-400" />
                          <span>Encerrar Processo</span>
                        </button>
                      </>
                    )}

                    <button
                      type="button"
                      onClick={() => executeOrchestratorCycle(true)}
                      disabled={orchIsRunning && orchIsPaused}
                      className="py-2.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                      title="Dispara uma única varredura do lobby imediatamente"
                    >
                      <RotateCcw className="w-4 h-4 text-cyan-400" />
                      <span>Executar 1 Ciclo</span>
                    </button>
                  </div>

                  {/* Loop Parameters Controls */}
                  <div className="space-y-3.5 pt-2">
                    {/* Interval Slider */}
                    <div>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-slate-300 font-semibold flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 text-cyan-400" />
                          Intervalo Base entre Ciclos:
                        </span>
                        <span className="font-mono font-bold text-cyan-300">{orchLoopInterval} segundos</span>
                      </div>
                      <input
                        type="range"
                        min="5"
                        max="60"
                        step="1"
                        value={orchLoopInterval}
                        onChange={(e) => setOrchLoopInterval(parseInt(e.target.value))}
                        className="w-full accent-cyan-500 cursor-pointer"
                      />
                      <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                        <span>5s (Rápido)</span>
                        <span>15s (Recomendado)</span>
                        <span>60s (Lento)</span>
                      </div>
                    </div>

                    {/* Jitter Slider */}
                    <div>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-slate-300 font-semibold flex items-center gap-1.5">
                          <Shuffle className="w-3.5 h-3.5 text-emerald-400" />
                          Variação Cognitiva (Jitter):
                        </span>
                        <span className="font-mono font-bold text-emerald-300">±{orchJitter} segundos</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="8"
                        step="0.5"
                        value={orchJitter}
                        onChange={(e) => setOrchJitter(parseFloat(e.target.value))}
                        className="w-full accent-emerald-500 cursor-pointer"
                      />
                      <p className="text-[10px] text-slate-400 leading-tight">
                        Aplica variação randômica ao tempo de repouso entre ciclos, camuflando o padrão temporal de execução.
                      </p>
                    </div>

                    {/* Max Buyin Slider */}
                    <div>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-slate-300 font-semibold flex items-center gap-1.5">
                          <Coins className="w-3.5 h-3.5 text-amber-400" />
                          Limite Máximo de Buy-in:
                        </span>
                        <span className="font-mono font-bold text-amber-300">≤ {orchMaxBuyin} fichas</span>
                      </div>
                      <input
                        type="range"
                        min="10"
                        max="150"
                        step="5"
                        value={orchMaxBuyin}
                        onChange={(e) => setOrchMaxBuyin(parseInt(e.target.value))}
                        className="w-full accent-amber-500 cursor-pointer"
                      />
                      <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                        <span>10 fichas</span>
                        <span>50 fichas (Padrão)</span>
                        <span>150 fichas</span>
                      </div>
                    </div>

                    {/* Safety Toggles */}
                    <div className="space-y-2 pt-2 border-t border-slate-800">
                      <label className="flex items-center justify-between cursor-pointer p-2 rounded-lg bg-slate-950 border border-slate-800/80 hover:border-slate-700 transition-colors">
                        <span className="text-xs font-semibold text-slate-300">Modo Simulação (Dry-Run Seguro)</span>
                        <input
                          type="checkbox"
                          checked={orchDryRun}
                          onChange={(e) => setOrchDryRun(e.target.checked)}
                          className="w-4 h-4 rounded accent-emerald-500 cursor-pointer"
                        />
                      </label>

                      <label className="flex items-center justify-between cursor-pointer p-2 rounded-lg bg-slate-950 border border-slate-800/80 hover:border-slate-700 transition-colors">
                        <span className="text-xs font-semibold text-slate-300">Recuperação de Janela (Auto-Recovery)</span>
                        <input
                          type="checkbox"
                          checked={orchAutoRecovery}
                          onChange={(e) => setOrchAutoRecovery(e.target.checked)}
                          className="w-4 h-4 rounded accent-cyan-500 cursor-pointer"
                        />
                      </label>
                    </div>

                    {/* CLI Windows Snippet */}
                    <div className="pt-2 border-t border-slate-800 space-y-1">
                      <span className="text-[10px] font-mono text-slate-400 block font-semibold">
                        Comando Windows Equivalente:
                      </span>
                      <div className="p-2.5 rounded-lg bg-black border border-slate-800 font-mono text-[11px] text-emerald-400 flex items-center justify-between overflow-x-auto shadow-inner">
                        <code>python lobby_orchestrator.py --interval {orchLoopInterval} --jitter {orchJitter} --max-buyin {orchMaxBuyin} {orchDryRun ? '--dry-run' : ''}</code>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column: Anti-Duplication Table & Activity Logs */}
              <div className="lg:col-span-7 space-y-4">
                <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80 shadow-xl space-y-4">
                  {/* Sub-Tabs Selector */}
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
                      <button
                        type="button"
                        onClick={() => setOrchActiveSubTab('anti_dup')}
                        className={`px-3 py-1.5 rounded font-semibold flex items-center gap-1.5 transition-colors cursor-pointer ${
                          orchActiveSubTab === 'anti_dup'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-700 shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Registro Anti-Duplicação ({antiDupRecords.length})</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setOrchActiveSubTab('logs')}
                        className={`px-3 py-1.5 rounded font-semibold flex items-center gap-1.5 transition-colors cursor-pointer ${
                          orchActiveSubTab === 'logs'
                            ? 'bg-cyan-950 text-cyan-300 border border-cyan-700 shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                        <span>Logs de Atividade ({orchActivityLogs.length})</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setOrchActiveSubTab('config')}
                        className={`px-3 py-1.5 rounded font-semibold flex items-center gap-1.5 transition-colors cursor-pointer ${
                          orchActiveSubTab === 'config'
                            ? 'bg-amber-950 text-amber-300 border border-amber-700 shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <FileCode2 className="w-3.5 h-3.5 text-amber-400" />
                        <span>Fluxo do Loop</span>
                      </button>
                    </div>

                    {orchActiveSubTab === 'anti_dup' && antiDupRecords.length > 0 && (
                      <button
                        type="button"
                        onClick={handleClearAntiDup}
                        className="text-[11px] font-mono px-2.5 py-1 rounded bg-slate-950 hover:bg-rose-950/70 border border-slate-800 hover:border-rose-700 text-slate-400 hover:text-rose-300 transition-colors cursor-pointer flex items-center gap-1"
                      >
                        <Trash2 className="w-3 h-3 text-slate-400" />
                        <span>Zerar Anti-Dup</span>
                      </button>
                    )}
                  </div>

                  {/* Sub-Tab 1: Anti-Duplication Table */}
                  {orchActiveSubTab === 'anti_dup' && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span className="font-mono text-[11px] flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          Arquivo: <code className="text-cyan-300">logs/registered_tournaments.json</code> (TTL: 24 horas)
                        </span>
                        <span className="text-[10px] text-slate-500 font-mono">
                          Evita cliques duplicados na mesma sessão
                        </span>
                      </div>

                      {antiDupRecords.length === 0 ? (
                        <div className="p-8 rounded-xl border border-dashed border-slate-800 text-center space-y-2">
                          <ShieldCheck className="w-8 h-8 text-slate-600 mx-auto" />
                          <h4 className="font-bold text-xs text-slate-300">Nenhum Torneio Bloqueado</h4>
                          <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                            O registro de anti-duplicação está limpo. O orquestrador poderá se inscrever em qualquer torneio elegível que encontrar no lobby.
                          </p>
                        </div>
                      ) : (
                        <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/60 shadow-inner">
                          <div className="overflow-x-auto">
                            <table className="w-full text-left text-xs font-mono">
                              <thead className="bg-slate-950 border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                                <tr>
                                  <th className="py-2.5 px-3">Torneio & Buy-in</th>
                                  <th className="py-2.5 px-2">Horário</th>
                                  <th className="py-2.5 px-2">Status</th>
                                  <th className="py-2.5 px-2">Inscrito</th>
                                  <th className="py-2.5 px-2 text-right">Ação</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-800/70 text-slate-300">
                                {antiDupRecords.map((item) => (
                                  <tr key={item.key} className="hover:bg-slate-800/40 transition-colors">
                                    <td className="py-2.5 px-3">
                                      <div className="font-bold text-slate-100 truncate max-w-xs">{item.tournamentName}</div>
                                      <div className="text-[10px] text-amber-400 font-semibold">{item.buyin} fichas • chave: {item.key.slice(0, 18)}...</div>
                                    </td>
                                    <td className="py-2.5 px-2 text-cyan-300 font-bold whitespace-nowrap">
                                      {item.startTime}
                                    </td>
                                    <td className="py-2.5 px-2 whitespace-nowrap">
                                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
                                        INSCRITO
                                      </span>
                                    </td>
                                    <td className="py-2.5 px-2 text-slate-400 text-[10px] whitespace-nowrap">
                                      {item.lastRegistered}
                                    </td>
                                    <td className="py-2.5 px-2 text-right whitespace-nowrap">
                                      <button
                                        type="button"
                                        onClick={() => handleRemoveAntiDupItem(item.key)}
                                        className="p-1 rounded bg-slate-900 hover:bg-rose-950/80 border border-slate-800 hover:border-rose-800 text-slate-400 hover:text-rose-300 transition-colors cursor-pointer"
                                        title="Remover bloqueio anti-duplicação deste torneio"
                                      >
                                        <Trash2 className="w-3.5 h-3.5" />
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Sub-Tab 2: Streaming Activity Logs */}
                  {orchActiveSubTab === 'logs' && (
                    <div className="space-y-3">
                      <div className="border border-slate-800 rounded-xl overflow-hidden bg-black font-mono text-xs shadow-inner">
                        <div className="bg-slate-950 px-3.5 py-1.5 border-b border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                          <div className="flex items-center gap-2">
                            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                            <span>Terminal de Eventos do Orquestrador (Live Stream)</span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {orchActivityLogs.length} eventos
                          </span>
                        </div>

                        <div className="p-3 space-y-2 max-h-[320px] overflow-y-auto leading-relaxed divide-y divide-slate-900">
                          {orchActivityLogs.map(log => (
                            <div key={log.id} className="pt-2 flex items-start gap-2.5">
                              <span className="text-slate-500 text-[10px] shrink-0 font-mono">{log.time}</span>
                              <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded shrink-0 border uppercase font-mono ${
                                log.type === 'SUCCESS'
                                  ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                                  : log.type === 'SKIP_DUP'
                                  ? 'bg-amber-950 text-amber-300 border-amber-800'
                                  : log.type === 'SCAN'
                                  ? 'bg-cyan-950 text-cyan-300 border-cyan-800'
                                  : 'bg-slate-800 text-slate-300 border-slate-700'
                              }`}>
                                {log.tag || log.type}
                              </span>
                              <span className={`text-[11px] ${
                                log.type === 'SUCCESS' ? 'text-emerald-200' : log.type === 'SKIP_DUP' ? 'text-amber-200/90' : 'text-slate-300'
                              }`}>
                                {log.message}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Sub-Tab 3: Flow Diagram */}
                  {orchActiveSubTab === 'config' && (
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3 text-xs leading-relaxed">
                      <h4 className="font-bold text-slate-100 flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4 text-emerald-400" />
                        Arquitetura de Ciclo Contínuo da Fase 1:
                      </h4>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
                        <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
                          <span className="font-bold text-cyan-300 block">1. Varredura Periódica com Jitter</span>
                          <p className="text-slate-400">
                            A cada ciclo ({orchLoopInterval}s ±{orchJitter}s), localiza a janela PPPoker (787x1470) e segmenta os cartões do Lobby via visão computacional.
                          </p>
                        </div>

                        <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
                          <span className="font-bold text-amber-300 block">2. Anti-Duplicação Inteligente</span>
                          <p className="text-slate-400">
                            Calcula a chave determinística do torneio. Se já constar no registro JSON persistente (TTL 24h), ignora instantaneamente para não perder tempo.
                          </p>
                        </div>

                        <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
                          <span className="font-bold text-emerald-300 block">3. Clique Camuflado (Módulo 4)</span>
                          <p className="text-slate-400">
                            Dispara movimento suave Bézier com atraso cognitivo humano e rotação alternada de estratégias A/B para anti-detecção.
                          </p>
                        </div>

                        <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
                          <span className="font-bold text-fuchsia-300 block">4. Confirmação & Retorno (Módulo 5)</span>
                          <p className="text-slate-400">
                            Aguarda a tela de detalhes, clica no botão principal, confirma o buy-in modal, valida status 'Inscrito' e retorna ao lobby principal.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab: Deployment & Servidor Central de Telemetria */}
        {activeTab === 'deployment' && (
          <DeploymentGuide />
        )}

        {/* Tab -1: Multi-Channel Alerts & Notifications Dashboard */}
        {activeTab === 'alerts' && (
          <div className="space-y-6">
            {/* Alerts Overview Header Banner */}
            <div className="p-4 rounded-xl bg-gradient-to-r from-amber-950/60 via-slate-900 to-slate-900 border border-amber-700/60 flex flex-wrap items-center justify-between gap-4 shadow-xl">
              <div className="flex items-center gap-3.5">
                <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 font-bold shadow-lg shadow-amber-500/10 shrink-0">
                  <BellRing className="w-5 h-5 text-amber-400 animate-pulse" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-bold text-sm text-slate-100">
                      Central Multi-Canal de Alertas e Notificações (Fase 1 · Módulo 4 & Escalada Remota)
                    </h3>
                    <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-amber-500 text-slate-950">
                      Multi-Canal Ativo
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Configure webhooks, bots e integrações para receber alertas operacionais e de segurança mesmo longe do computador. Suporte a Discord, Telegram, Zapier/Make e API REST com payloads customizados por severidade (Info, Warning, Critical).
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono">
                  <span className="text-slate-400 text-[11px]">Canais Habilitados:</span>
                  <span className="font-bold text-emerald-400">
                    {channels.filter(c => c.enabled).length} de {channels.length}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={handleDispatchMultiChannelTest}
                  disabled={isDispatchingNotification}
                  className="px-3.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow transition-all cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{isDispatchingNotification ? 'Despachando...' : 'Disparar Teste Imediato'}</span>
                </button>
              </div>
            </div>

            {/* Section 1: Multi-Channel Configuration Cards */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Radio className="w-4 h-4 text-cyan-400" />
                  <h3 className="font-bold text-xs text-slate-200 uppercase tracking-wide">
                    1. Configuração dos Canais de Notificação
                  </h3>
                </div>
                <span className="text-[11px] text-slate-400">
                  Endpoints acionados em caso de SYSTEM_HALT, erros de janela ou conclusões operacionais
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {channels.map(channel => (
                  <div
                    key={channel.id}
                    className={`p-4 rounded-xl border flex flex-col justify-between transition-all duration-200 shadow-md ${
                      channel.enabled
                        ? 'bg-slate-900/90 border-slate-700/80 shadow-slate-950/60 ring-1 ring-slate-700'
                        : 'bg-slate-900/40 border-slate-800/80 opacity-75'
                    }`}
                  >
                    <div className="space-y-3">
                      {/* Card Header with Provider Icon and Toggle */}
                      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                        <div className="flex items-center gap-2">
                          <div className={`p-1.5 rounded-lg ${
                            channel.provider === 'discord'
                              ? 'bg-indigo-950 text-indigo-400 border border-indigo-800'
                              : channel.provider === 'telegram'
                              ? 'bg-sky-950 text-sky-400 border border-sky-800'
                              : channel.provider === 'email'
                              ? 'bg-amber-950 text-amber-400 border border-amber-800'
                              : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                          }`}>
                            {channel.provider === 'discord' && <MessageSquare className="w-4 h-4" />}
                            {channel.provider === 'telegram' && <Send className="w-4 h-4" />}
                            {channel.provider === 'email' && <Mail className="w-4 h-4" />}
                            {channel.provider === 'generic' && <Globe className="w-4 h-4" />}
                          </div>
                          <div>
                            <h4 className="font-bold text-xs text-slate-100 leading-tight">
                              {channel.name}
                            </h4>
                            <span className="text-[10px] text-slate-500 uppercase font-mono">
                              {channel.provider}
                            </span>
                          </div>
                        </div>

                        <label className="flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={channel.enabled}
                            onChange={() => handleToggleChannel(channel.id)}
                            className="w-4 h-4 rounded accent-emerald-500 cursor-pointer"
                          />
                          <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded border font-bold ${
                            channel.enabled
                              ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                              : 'bg-slate-950 text-slate-500 border-slate-800'
                          }`}>
                            {channel.enabled ? 'ON' : 'OFF'}
                          </span>
                        </label>
                      </div>

                      {/* Endpoint Input */}
                      <div className="space-y-1">
                        <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                          URL do Endpoint / Webhook:
                        </label>
                        <input
                          type="text"
                          value={channel.endpoint}
                          onChange={(e) => handleUpdateChannelEndpoint(channel.id, e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-200 focus:outline-none focus:border-cyan-500 truncate"
                          placeholder="https://..."
                        />
                      </div>

                      {/* Provider-Specific Extra Settings */}
                      {channel.provider === 'discord' && (
                        <div className="grid grid-cols-2 gap-2 text-[10px]">
                          <div>
                            <span className="text-slate-400 block mb-0.5">Nome do Bot:</span>
                            <input
                              type="text"
                              value={channel.extraConfig.discordUsername || "VisualPilot"}
                              onChange={(e) => {
                                const val = e.target.value;
                                setChannels(prev => prev.map(c => c.id === channel.id ? { ...c, extraConfig: { ...c.extraConfig, discordUsername: val } } : c));
                              }}
                              className="w-full px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300 text-[10px] font-mono"
                            />
                          </div>
                          <div>
                            <span className="text-slate-400 block mb-0.5">Avatar URL:</span>
                            <input
                              type="text"
                              value={channel.extraConfig.discordAvatar || ""}
                              onChange={(e) => {
                                const val = e.target.value;
                                setChannels(prev => prev.map(c => c.id === channel.id ? { ...c, extraConfig: { ...c.extraConfig, discordAvatar: val } } : c));
                              }}
                              placeholder="https://..."
                              className="w-full px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300 text-[10px] font-mono truncate"
                            />
                          </div>
                        </div>
                      )}

                      {channel.provider === 'telegram' && (
                        <div className="grid grid-cols-2 gap-2 text-[10px]">
                          <div>
                            <span className="text-slate-400 block mb-0.5">Chat ID:</span>
                            <input
                              type="text"
                              value={channel.extraConfig.telegramChatId || ""}
                              onChange={(e) => {
                                const val = e.target.value;
                                setChannels(prev => prev.map(c => c.id === channel.id ? { ...c, extraConfig: { ...c.extraConfig, telegramChatId: val } } : c));
                              }}
                              className="w-full px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300 text-[10px] font-mono"
                            />
                          </div>
                          <div>
                            <span className="text-slate-400 block mb-0.5">Token do Bot:</span>
                            <input
                              type="password"
                              value={channel.extraConfig.telegramToken || ""}
                              onChange={(e) => {
                                const val = e.target.value;
                                setChannels(prev => prev.map(c => c.id === channel.id ? { ...c, extraConfig: { ...c.extraConfig, telegramToken: val } } : c));
                              }}
                              className="w-full px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300 text-[10px] font-mono"
                            />
                          </div>
                        </div>
                      )}

                      {channel.provider === 'email' && (
                        <div className="text-[10px]">
                          <span className="text-slate-400 block mb-0.5">E-mail de Destino (Zapier/Make):</span>
                          <input
                            type="email"
                            value={channel.extraConfig.emailRecipient || ""}
                            onChange={(e) => {
                              const val = e.target.value;
                              setChannels(prev => prev.map(c => c.id === channel.id ? { ...c, extraConfig: { ...c.extraConfig, emailRecipient: val } } : c));
                            }}
                            className="w-full px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300 text-[10px] font-mono"
                          />
                        </div>
                      )}

                      {channel.provider === 'generic' && (
                        <div className="text-[10px]">
                          <span className="text-slate-400 block mb-0.5">Authorization Header:</span>
                          <input
                            type="text"
                            value={channel.extraConfig.authToken || ""}
                            onChange={(e) => {
                              const val = e.target.value;
                              setChannels(prev => prev.map(c => c.id === channel.id ? { ...c, extraConfig: { ...c.extraConfig, authToken: val } } : c));
                            }}
                            className="w-full px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300 text-[10px] font-mono"
                          />
                        </div>
                      )}
                    </div>

                    {/* Card Footer */}
                    <div className="mt-3 pt-2.5 border-t border-slate-800 flex items-center justify-between text-[10px]">
                      <div className="flex items-center gap-1.5 font-mono">
                        <div className={`w-1.5 h-1.5 rounded-full ${channel.enabled ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                        <span className="text-slate-400">{channel.lastStatus}</span>
                      </div>
                      <span className="text-slate-500 font-mono">{channel.lastSentAt}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Section 2: Test Dispatch Panel + Live Visual Preview Mockup */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column: Test Dispatch Panel */}
              <div className="lg:col-span-6 p-5 rounded-xl border border-slate-800 bg-slate-900/80 shadow-xl space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Send className="w-4 h-4 text-amber-400" />
                    <h3 className="font-bold text-xs text-slate-100 uppercase tracking-wide">
                      2. Painel de Teste de Payloads e Severidade
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-400">
                    Sessão: {sessionName || "Sessão Principal"}
                  </span>
                </div>

                {/* Step A: Nível de Severidade */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-300 block">
                    A. Escolha o Nível de Severidade do Alerta:
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => setTestSeverity('INFO')}
                      className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                        testSeverity === 'INFO'
                          ? 'bg-emerald-950/90 border-emerald-500 text-emerald-200 ring-2 ring-emerald-500/30 shadow-md'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          <span>INFO</span>
                        </span>
                        <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-emerald-900/60 text-emerald-300">
                          Rotina
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 mt-1 leading-tight">
                        Início de sessão, vaga garantida, calibração OK.
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={() => setTestSeverity('WARN')}
                      className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                        testSeverity === 'WARN'
                          ? 'bg-amber-950/90 border-amber-500 text-amber-200 ring-2 ring-amber-500/30 shadow-md'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                          <span>WARN</span>
                        </span>
                        <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-amber-900/60 text-amber-300">
                          Atenção
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 mt-1 leading-tight">
                        Variação de resolução, atraso, saldo reduzido.
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={() => setTestSeverity('CRITICAL')}
                      className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                        testSeverity === 'CRITICAL'
                          ? 'bg-rose-950/90 border-rose-500 text-rose-200 ring-2 ring-rose-500/40 shadow-md'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs flex items-center gap-1.5">
                          <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
                          <span>CRITICAL</span>
                        </span>
                        <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-rose-900/60 text-rose-300 animate-pulse">
                          Parada
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 mt-1 leading-tight">
                        SYSTEM_HALT &gt; 5m, janela fechada, processo parado.
                      </p>
                    </button>
                  </div>
                </div>

                {/* Step B: Atalhos Predefinidos Rápidos */}
                <div className="space-y-1.5">
                  <span className="text-[11px] text-slate-400 block font-medium">
                    B. Carregar Cenário Operacional de Teste:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => {
                        setTestSeverity('CRITICAL');
                        setTestTitle("🚨 Paralisação Crítica do Bot (> 5 minutos)");
                        setTestDetails("Inatividade prolongada detectada pelo watchdog de heartbeat. Cliques bloqueados no desktop preventivamente.");
                      }}
                      className="px-2.5 py-1 rounded bg-slate-950 hover:bg-slate-800 border border-slate-800 text-[11px] text-slate-300 transition-colors cursor-pointer"
                    >
                      🚨 SYSTEM_HALT (&gt; 5m)
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setTestSeverity('WARN');
                        setTestTitle("⚠️ Resolução Anômala Detectada (850x1400)");
                        setTestDetails("A janela do PPPoker foi redimensionada fora dos padrões (787x1470). Fatores de calibração adaptativos foram acionados.");
                      }}
                      className="px-2.5 py-1 rounded bg-slate-950 hover:bg-slate-800 border border-slate-800 text-[11px] text-slate-300 transition-colors cursor-pointer"
                    >
                      ⚠️ Variação de Resolução
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setTestSeverity('INFO');
                        setTestTitle("🔔 Sessão de Jogo Iniciada");
                        setTestDetails(`Sessão "${sessionName || 'Sessão Principal'}" iniciada pelo operador. Calibração da janela e integridade de pré-voo validadas.`);
                      }}
                      className="px-2.5 py-1 rounded bg-slate-950 hover:bg-slate-800 border border-slate-800 text-[11px] text-slate-300 transition-colors cursor-pointer"
                    >
                      🔔 Início de Sessão
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setTestSeverity('INFO');
                        setTestTitle("✅ Inscrição Confirmada no Torneio");
                        setTestDetails(`Inscrição efetuada com sucesso no torneio ${selectedCard.name_label} por 50 fichas. Status 'Inscrito' auditado no CSV.`);
                      }}
                      className="px-2.5 py-1 rounded bg-slate-950 hover:bg-slate-800 border border-slate-800 text-[11px] text-slate-300 transition-colors cursor-pointer"
                    >
                      ✅ Inscrição Confirmada
                    </button>
                  </div>
                </div>

                {/* Step C: Inputs Customizáveis */}
                <div className="space-y-3">
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">
                      C. Título do Alerta / Notificação:
                    </label>
                    <input
                      type="text"
                      value={testTitle}
                      onChange={(e) => setTestTitle(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-100 font-mono focus:outline-none focus:border-amber-500"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">
                      Detalhes e Instruções Operacionais:
                    </label>
                    <textarea
                      rows={3}
                      value={testDetails}
                      onChange={(e) => setTestDetails(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-amber-500 leading-relaxed"
                    />
                  </div>
                </div>

                {/* Step D: Seleção de Destinatários */}
                <div className="space-y-1.5 pt-1">
                  <label className="text-xs font-semibold text-slate-300 block">
                    D. Destinatários do Disparo de Teste:
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {channels.map(ch => {
                      const isSelected = selectedChannelIds.includes(ch.id);
                      return (
                        <button
                          key={ch.id}
                          type="button"
                          onClick={() => handleToggleChannelSelect(ch.id)}
                          className={`p-2 rounded-lg border text-left flex items-center justify-between text-xs transition-colors cursor-pointer ${
                            isSelected && ch.enabled
                              ? 'bg-slate-800/90 border-cyan-500/60 text-slate-100'
                              : isSelected && !ch.enabled
                              ? 'bg-slate-900 border-amber-800 text-amber-300'
                              : 'bg-slate-950 border-slate-800 text-slate-500 hover:text-slate-300'
                          }`}
                        >
                          <div className="flex items-center gap-2 truncate">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => {}}
                              className="w-3.5 h-3.5 rounded accent-cyan-500 pointer-events-none"
                            />
                            <span className="truncate font-medium">{ch.name}</span>
                          </div>
                          {!ch.enabled && (
                            <span className="text-[9px] font-mono text-amber-400 shrink-0">
                              (Off)
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Big Action Dispatch Button */}
                <div className="pt-2 border-t border-slate-800 space-y-2">
                  <button
                    type="button"
                    onClick={handleDispatchMultiChannelTest}
                    disabled={isDispatchingNotification}
                    className={`w-full py-2.5 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-lg cursor-pointer ${
                      testSeverity === 'CRITICAL'
                        ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-950/60 ring-2 ring-rose-500/30'
                        : testSeverity === 'WARN'
                        ? 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-amber-950/60 ring-2 ring-amber-500/30'
                        : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-emerald-950/60 ring-2 ring-emerald-500/30'
                    }`}
                  >
                    {isDispatchingNotification ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>Despachando Payload HTTP para os Canais Selecionados...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4" />
                        <span>Disparar Alerta Multi-Canal Agora ({selectedChannelIds.length} selecionados)</span>
                      </>
                    )}
                  </button>

                  <p className="text-[11px] text-slate-400 text-center leading-tight">
                    Dispara simulação HTTP 200 com payload estruturado, executa síntese de áudio Web Audio API ({testSeverity}) e registra evento auditável no CSV.
                  </p>
                </div>
              </div>

              {/* Right Column: Visual Mockup & Live Payload Preview */}
              <div className="lg:col-span-6 p-5 rounded-xl border border-slate-800 bg-slate-900/80 shadow-xl flex flex-col justify-between space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                      <Eye className="w-4 h-4 text-cyan-400" />
                      <h3 className="font-bold text-xs text-slate-100 uppercase tracking-wide">
                        3. Visualizador do Payload & Mockup de Entrega
                      </h3>
                    </div>

                    {/* Preview Selector Tabs */}
                    <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
                      <button
                        type="button"
                        onClick={() => setActivePreviewProvider('discord')}
                        className={`px-2.5 py-1 rounded font-medium flex items-center gap-1.5 transition-colors cursor-pointer ${
                          activePreviewProvider === 'discord'
                            ? 'bg-indigo-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <MessageSquare className="w-3 h-3" />
                        <span>Discord</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setActivePreviewProvider('telegram')}
                        className={`px-2.5 py-1 rounded font-medium flex items-center gap-1.5 transition-colors cursor-pointer ${
                          activePreviewProvider === 'telegram'
                            ? 'bg-sky-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <Send className="w-3 h-3" />
                        <span>Telegram</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setActivePreviewProvider('generic')}
                        className={`px-2.5 py-1 rounded font-medium flex items-center gap-1.5 transition-colors cursor-pointer ${
                          activePreviewProvider === 'generic'
                            ? 'bg-emerald-600 text-slate-950 font-bold shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <FileCode2 className="w-3 h-3" />
                        <span>JSON</span>
                      </button>
                    </div>
                  </div>

                  {/* Render Mockup: Discord */}
                  {activePreviewProvider === 'discord' && (
                    <div className="rounded-xl bg-[#313338] border border-[#232428] p-4 text-slate-100 space-y-3 font-sans shadow-inner select-none">
                      {/* Discord Bot Header */}
                      <div className="flex items-center gap-2.5">
                        <img
                          src="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=128&q=80"
                          alt="Bot Avatar"
                          className="w-9 h-9 rounded-full object-cover ring-2 ring-[#5865F2]"
                        />
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-sm text-white">VisualPilot Sentinel</span>
                            <span className="px-1 py-0.2 rounded text-[10px] font-black uppercase bg-[#5865F2] text-white tracking-wider">
                              BOT
                            </span>
                            <span className="text-[11px] text-[#949ba4]">Hoje às {new Date().toLocaleTimeString().slice(0, 5)}</span>
                          </div>
                          <span className="text-xs text-[#dbdee1] leading-tight block">
                            {testSeverity === 'CRITICAL' ? '🚨' : testSeverity === 'WARN' ? '⚠️' : '🔔'} <strong>[VISUALPILOT: {testSeverity}]</strong> {testTitle}
                          </span>
                        </div>
                      </div>

                      {/* Discord Embed Box */}
                      <div className={`rounded-lg bg-[#2b2d31] p-3.5 border-l-4 space-y-2.5 ${
                        testSeverity === 'CRITICAL'
                          ? 'border-rose-500'
                          : testSeverity === 'WARN'
                          ? 'border-amber-500'
                          : 'border-emerald-500'
                      }`}>
                        <div className="space-y-1">
                          <h4 className="font-bold text-sm text-white flex items-center gap-1.5">
                            <span>{testSeverity === 'CRITICAL' ? '🚨' : testSeverity === 'WARN' ? '⚠️' : '🔔'}</span>
                            <span>{testTitle}</span>
                          </h4>
                          <p className="text-xs text-[#dbdee1] leading-relaxed">
                            {testDetails}
                          </p>
                        </div>

                        {/* Fields 2x2 */}
                        <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-[#383a40]">
                          <div>
                            <span className="text-[10px] font-bold uppercase text-[#949ba4] block">Severidade</span>
                            <span className={`font-mono font-bold ${
                              testSeverity === 'CRITICAL' ? 'text-rose-400' : testSeverity === 'WARN' ? 'text-amber-400' : 'text-emerald-400'
                            }`}>
                              {testSeverity}
                            </span>
                          </div>
                          <div>
                            <span className="text-[10px] font-bold uppercase text-[#949ba4] block">Sessão Ativa</span>
                            <span className="font-mono text-cyan-300">
                              "{sessionName || "Sessão Principal"}"
                            </span>
                          </div>
                          <div>
                            <span className="text-[10px] font-bold uppercase text-[#949ba4] block">Data / Hora UTC</span>
                            <span className="font-mono text-slate-300 text-[11px]">
                              {new Date().toISOString().replace('T', ' ').slice(0, 19)}
                            </span>
                          </div>
                          <div>
                            <span className="text-[10px] font-bold uppercase text-[#949ba4] block">Canal</span>
                            <span className="text-slate-300">Discord (#alertas-bot)</span>
                          </div>
                        </div>

                        <div className="text-[10px] text-[#949ba4] pt-1 border-t border-[#383a40] flex items-center justify-between">
                          <span>VisualPilot Módulo 4 • Sistema Multi-Canal de Notificações</span>
                          <span className="font-mono">RFC 4180 / HTTP 200</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Render Mockup: Telegram */}
                  {activePreviewProvider === 'telegram' && (
                    <div className="rounded-xl bg-[#0e1621] border border-[#17212b] p-4 text-slate-100 font-sans shadow-inner select-none">
                      <div className="max-w-md bg-[#182533] border border-[#2b5278]/40 p-3.5 rounded-2xl rounded-tl-sm space-y-2 text-xs shadow-md">
                        <div className="flex items-center justify-between border-b border-[#242f3d] pb-1.5">
                          <span className="font-bold text-[#40a7e3] text-xs">@VisualPilotAlertsBot</span>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {new Date().toLocaleTimeString().slice(0, 5)}
                          </span>
                        </div>

                        <div className="space-y-1">
                          <p className="font-bold text-white text-sm">
                            {testSeverity === 'CRITICAL' ? '🚨' : testSeverity === 'WARN' ? '⚠️' : '🔔'} [VISUALPILOT {testSeverity}]
                          </p>
                          <p className="font-semibold text-slate-200">
                            {testTitle}
                          </p>
                          <p className="text-slate-300 text-xs leading-relaxed pt-1">
                            {testDetails}
                          </p>
                        </div>

                        <div className="p-2 rounded bg-[#0e1621]/60 font-mono text-[11px] text-slate-300 space-y-0.5 border border-[#242f3d]">
                          <p>🏷 <strong>Sessão:</strong> <code className="text-cyan-300">{sessionName || "Sessão Principal"}</code></p>
                          <p>🕒 <strong>UTC:</strong> {new Date().toISOString()}</p>
                          <p>📡 <strong>Canal:</strong> Telegram Bot</p>
                        </div>

                        <p className="text-[11px] text-slate-400 italic">
                          {testSeverity === 'CRITICAL'
                            ? 'Ação imediata recomendada no desktop do bot.'
                            : 'Auditoria e telemetria automáticas ativas.'}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Render Mockup: JSON Code */}
                  {activePreviewProvider === 'generic' && (
                    <div className="relative">
                      <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-[11px] font-mono text-cyan-300 overflow-x-auto leading-relaxed shadow-inner max-h-[300px]">
                        {JSON.stringify(
                          buildCustomNotificationPayload(
                            'generic',
                            testSeverity,
                            testTitle,
                            testDetails,
                            sessionName || "Sessão Principal",
                            channels[0]
                          ),
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  )}
                </div>

                {/* Footer of Preview */}
                <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                  <div className="flex items-center gap-1.5 font-mono text-[11px]">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Payload compatível com webhooks padrão RFC 4180</span>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      const payload = buildCustomNotificationPayload(
                        activePreviewProvider,
                        testSeverity,
                        testTitle,
                        testDetails,
                        sessionName || "Sessão Principal",
                        channels[0]
                      );
                      navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
                      setCopiedPayloadJson(true);
                      setTimeout(() => setCopiedPayloadJson(false), 2000);
                    }}
                    className="flex items-center gap-1.5 px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold transition-colors cursor-pointer"
                  >
                    {copiedPayloadJson ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-emerald-300">Copiado!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-slate-400" />
                        <span>Copiar JSON</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Section 4: Recent Notification Dispatch History */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <h3 className="font-bold text-xs text-slate-200 uppercase tracking-wide">
                    4. Histórico Recente de Notificações Despachadas
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono text-slate-400">
                    Total: {dispatchHistory.length} disparos nesta sessão
                  </span>
                  {dispatchHistory.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setDispatchHistory([])}
                      className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
                    >
                      Limpar Histórico
                    </button>
                  )}
                </div>
              </div>

              <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-900/60 shadow-xl">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-slate-950 border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                      <tr>
                        <th className="py-3 px-4">Horário</th>
                        <th className="py-3 px-3">Severidade</th>
                        <th className="py-3 px-3">Título do Alerta</th>
                        <th className="py-3 px-3">Canais de Entrega</th>
                        <th className="py-3 px-3">Status HTTP</th>
                        <th className="py-3 px-3">Latência</th>
                        <th className="py-3 px-4">Detalhes Operacionais</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/70 text-slate-300">
                      {dispatchHistory.map((item) => (
                        <tr key={item.id} className="hover:bg-slate-800/40 transition-colors">
                          <td className="py-3 px-4 text-slate-400 text-[11px] whitespace-nowrap">
                            {item.timestamp}
                          </td>
                          <td className="py-3 px-3 whitespace-nowrap">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              item.severity === 'CRITICAL'
                                ? 'bg-rose-950 text-rose-300 border-rose-800'
                                : item.severity === 'WARN'
                                ? 'bg-amber-950 text-amber-300 border-amber-800'
                                : 'bg-emerald-950 text-emerald-300 border-emerald-800'
                            }`}>
                              {item.severity}
                            </span>
                          </td>
                          <td className="py-3 px-3 font-semibold text-slate-100 whitespace-nowrap">
                            {item.title}
                          </td>
                          <td className="py-3 px-3 whitespace-nowrap">
                            <div className="flex flex-wrap gap-1">
                              {item.channelNames.map((cName, i) => (
                                <span
                                  key={i}
                                  className="px-1.5 py-0.2 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700 font-mono"
                                >
                                  {cName}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="py-3 px-3 whitespace-nowrap">
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                              {item.httpStatus} OK
                            </span>
                          </td>
                          <td className="py-3 px-3 text-cyan-300 font-mono whitespace-nowrap">
                            {item.deliveryTimeMs}ms
                          </td>
                          <td className="py-3 px-4 text-slate-400 text-[11px] max-w-md truncate" title={item.details}>
                            {item.details}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="bg-slate-950 px-4 py-2.5 border-t border-slate-800 flex items-center justify-between text-xs text-slate-500">
                  <span>
                    Todos os disparos foram registrados simultaneamente no CSV de auditoria contínua (<code className="text-slate-400 font-mono">clicks_audit_2026-10-31.csv</code>).
                  </span>
                  <button
                    type="button"
                    onClick={() => setActiveTab('audit')}
                    className="text-emerald-400 hover:text-emerald-300 text-xs font-semibold flex items-center gap-1 cursor-pointer"
                  >
                    <span>Ver na Tabela de Auditoria</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 0: Module 5 Registration & Navigation Simulator */}
        {activeTab === 'register' && (
          <div className="space-y-6">
            {/* Module 5 Overview Banner */}
            <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-950/60 via-slate-900 to-slate-900 border border-emerald-800/60 flex flex-wrap items-center justify-between gap-4 shadow-xl">
              <div className="flex items-center gap-3.5">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-bold shadow-lg shadow-emerald-500/10 shrink-0">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-sm text-slate-100">
                      Módulo 5: Confirmação de Inscrição & Navegação Pós-Clique no PPPoker
                    </h3>
                    <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-emerald-500 text-slate-950">
                      Concluído
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Após o Módulo 4 clicar no cartão do lobby, o Módulo 5 valida a abertura da tela de detalhes, clica em Registrar, confirma o modal de buy-in, valida a vaga e retorna suavemente ao Lobby principal.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <a
                  href="/VisualPilot_Modulo5_RegistroTorneio.zip"
                  download
                  className="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow transition-all"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Baixar Pacote Módulo 5 (.ZIP)</span>
                </a>
              </div>
            </div>

            {/* Interactive 2-Column Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column: Visual Smartphone PPPoker App Mockup */}
              <div className="lg:col-span-5 flex flex-col items-center">
                <div className="w-full max-w-sm rounded-2xl border-2 border-slate-700 bg-slate-950 shadow-2xl overflow-hidden relative flex flex-col h-[580px] font-sans select-none">
                  {/* Top Phone Status & PPPoker Header Bar */}
                  <div className="bg-slate-900 border-b border-slate-800 px-3 py-2 flex items-center justify-between shrink-0">
                    <button
                      onClick={() => setM5Step(5)}
                      className={`p-1.5 rounded-lg border transition-all ${
                        m5Step === 5
                          ? 'bg-emerald-500 text-slate-950 border-emerald-400 ring-2 ring-emerald-400 shadow-md animate-pulse'
                          : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:text-white'
                      }`}
                      title="Botão Voltar (Seta) [X: 56, Y: 80]"
                    >
                      <ChevronRight className="w-4 h-4 rotate-180" />
                    </button>
                    <div className="text-center">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">
                        PPPoker Client
                      </span>
                      <span className="text-xs font-bold text-slate-100">
                        {m5Step === 0 || m5Step === 5 ? 'LOBBY PRINCIPAL (MTT)' : 'DETALHES DO TORNEIO'}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                      <span className="text-[10px] font-mono text-emerald-400">Online</span>
                    </div>
                  </div>

                  {/* Body Screen Content based on m5Step */}
                  <div className="flex-1 p-3.5 overflow-y-auto space-y-3 relative bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950">
                    {/* State 0 or 5: Lobby Overview */}
                    {(m5Step === 0 || m5Step === 5) && (
                      <div className="space-y-2.5 animate-in fade-in duration-200">
                        <div className="p-2 rounded-lg bg-emerald-950/40 border border-emerald-800/60 text-[11px] text-emerald-300 flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                          <span>{m5Step === 5 ? "✓ Retorno ao Lobby concluído com sucesso!" : "Lobby aberto. Clique no cartão alvo para registrar:"}</span>
                        </div>

                        {/* Tournament Card Mock in Lobby */}
                        <div
                          onClick={() => setM5Step(1)}
                          className="p-3 rounded-xl bg-slate-900/90 border-2 border-emerald-500/80 shadow-lg relative cursor-pointer hover:border-emerald-400 transition-all"
                        >
                          <div className="flex items-start justify-between">
                            <div>
                              <span className="text-[10px] font-mono text-emerald-400 font-bold uppercase">Torneio Elegível #2</span>
                              <h4 className="font-bold text-sm text-white">CORUJAO HYPER PKO10K</h4>
                              <p className="text-[11px] text-slate-400 mt-0.5">Início: 10/31 22:00 · 10 min</p>
                            </div>
                            <span className="px-2 py-0.5 rounded text-[10px] font-black bg-amber-500 text-slate-950">
                              Buy-in: 50
                            </span>
                          </div>

                          <div className="mt-2.5 pt-2 border-t border-slate-800 flex items-center justify-between text-[11px]">
                            <span className="text-slate-400">GTD: 10,000 fichas</span>
                            <span className="text-emerald-400 font-bold flex items-center gap-1">
                              <MousePointerClick className="w-3.5 h-3.5" />
                              <span>{m5Step === 0 ? "Clicar para Detalhes" : "Inscrito!"}</span>
                            </span>
                          </div>

                          {m5Step === 0 && (
                            <div className="absolute top-1/2 right-4 -translate-y-1/2 p-1.5 rounded-full bg-emerald-500 text-slate-950 ring-4 ring-emerald-500/30 animate-bounce">
                              <MousePointerClick className="w-4 h-4" />
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* State 1, 2, 3, 4: Tournament Details Screen */}
                    {m5Step >= 1 && m5Step <= 4 && (
                      <div className="space-y-3 animate-in fade-in duration-200">
                        {/* Tournament Hero Banner */}
                        <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                          <div className="flex items-start justify-between">
                            <div>
                              <span className="text-[10px] font-mono text-cyan-400 uppercase font-bold">MTT PKO</span>
                              <h4 className="font-bold text-sm text-slate-100">{selectedCard.name_label}</h4>
                            </div>
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-700 font-mono">
                              50 Fichas
                            </span>
                          </div>

                          <div className="grid grid-cols-2 gap-2 text-[10px] font-mono pt-1 text-slate-300">
                            <div className="p-1.5 rounded bg-slate-950 border border-slate-800/80">
                              <span className="text-slate-500 block">Garantido:</span>
                              <span className="font-bold text-emerald-400">10.000 Fichas</span>
                            </div>
                            <div className="p-1.5 rounded bg-slate-950 border border-slate-800/80">
                              <span className="text-slate-500 block">Horário:</span>
                              <span className="font-bold text-cyan-400">22:00 BRT</span>
                            </div>
                          </div>
                        </div>

                        {/* Tournament Structure Accordion */}
                        <div className="p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2 text-[11px]">
                          <span className="text-[10px] font-mono text-slate-400 uppercase block">Estrutura & Regras</span>
                          <div className="flex justify-between text-slate-300 text-xs">
                            <span className="text-slate-400">Stack Inicial:</span>
                            <span className="font-mono font-bold">20.000 (200 BB)</span>
                          </div>
                          <div className="flex justify-between text-slate-300 text-xs">
                            <span className="text-slate-400">Intervalo de Blinds:</span>
                            <span className="font-mono font-bold">10 minutos</span>
                          </div>
                          <div className="flex justify-between text-slate-300 text-xs">
                            <span className="text-slate-400">Late Registration:</span>
                            <span className="font-mono font-bold text-emerald-400">Até Nível 8</span>
                          </div>
                        </div>

                        {/* Status notification */}
                        {m5Step >= 4 && (
                          <div className="p-2.5 rounded-xl bg-emerald-950/80 border border-emerald-600 text-emerald-200 text-xs flex items-center gap-2 animate-in fade-in">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                            <span>Vaga garantida! Você está inscrito neste torneio.</span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Step 3: Confirmation Modal Overlay */}
                    {m5Step === 3 && (
                      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm z-30 flex items-center justify-center p-4 animate-in fade-in zoom-in-95 duration-150">
                        <div className="w-full bg-slate-900 border-2 border-emerald-500 rounded-xl p-4 shadow-2xl space-y-3 text-center">
                          <div className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center font-bold">
                            ♣
                          </div>
                          <h4 className="font-bold text-sm text-slate-50">Confirmar Inscrição?</h4>
                          <p className="text-xs text-slate-300">
                            Deseja confirmar o buy-in de <strong className="text-amber-300">50 fichas</strong> no torneio <span className="text-emerald-300">CORUJAO HYPER PKO10K</span>?
                          </p>

                          <div className="grid grid-cols-2 gap-2 pt-2 text-xs">
                            <button
                              onClick={() => setM5Step(1)}
                              className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold"
                            >
                              Cancelar
                            </button>
                            <button
                              onClick={() => setM5Step(4)}
                              className="px-3 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold shadow-md flex items-center justify-center gap-1 ring-2 ring-emerald-400 animate-pulse"
                            >
                              <Check className="w-3.5 h-3.5" />
                              <span>Confirmar</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Bottom Action Button Area in PPPoker (Register Button) */}
                  <div className="p-3 bg-slate-900 border-t border-slate-800 shrink-0">
                    {m5Step < 4 ? (
                      <button
                        onClick={() => setM5Step(3)}
                        className={`w-full py-2.5 rounded-xl font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition-all ${
                          m5Step === 2
                            ? 'bg-emerald-500 text-slate-950 ring-4 ring-emerald-400/50 shadow-lg scale-98'
                            : 'bg-emerald-600 hover:bg-emerald-500 text-slate-950 shadow-md'
                        }`}
                        title="Botão Registrar Principal [X: 393, Y: 1396]"
                      >
                        <MousePointerClick className="w-4 h-4" />
                        <span>Registrar (50 Fichas)</span>
                      </button>
                    ) : (
                      <div className="w-full py-2.5 rounded-xl bg-emerald-950 border border-emerald-600 text-emerald-300 font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        <span>Inscrito (Vaga Confirmada)</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Right Column: State Machine Controls & Real-Time Receipts */}
              <div className="lg:col-span-7 space-y-4">
                {/* State Machine Action Controls */}
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-4 shadow-xl">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
                    <div>
                      <h4 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                        <Activity className="w-4 h-4 text-emerald-400" />
                        <span>Esteira de Inscrição Automática (Módulo 5)</span>
                      </h4>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Transição de telas, confirmação de buy-in e retorno automático ao Lobby
                      </p>
                    </div>

                    {/* Scenario Switcher */}
                    <div className="flex items-center gap-1.5 text-xs">
                      <span className="text-[11px] font-mono text-slate-400">Cenário:</span>
                      <select
                        value={m5Scenario}
                        onChange={(e) => setM5Scenario(e.target.value as any)}
                        className="px-2.5 py-1 rounded bg-slate-950 border border-slate-700 text-slate-200 text-xs font-medium outline-none"
                      >
                        <option value="NORMAL">Fluxo Normal (Sucesso)</option>
                        <option value="ALREADY_REGISTERED">Torneio Já Inscrito</option>
                        <option value="INSUFFICIENT_FUNDS">Saldo Insuficiente</option>
                      </select>
                    </div>
                  </div>

                  {/* Step Sequence Pills */}
                  <div className="grid grid-cols-5 gap-1.5 text-center text-xs font-mono">
                    <div className={`p-2 rounded-lg border transition-all ${
                      m5Step === 1
                        ? 'bg-emerald-950 border-emerald-500 text-emerald-300 ring-2 ring-emerald-500/30'
                        : m5Step > 1
                        ? 'bg-slate-950 border-slate-800 text-slate-400'
                        : 'bg-slate-950/60 border-slate-900 text-slate-600'
                    }`}>
                      <span className="text-[10px] block opacity-70">Passo 1</span>
                      <span className="font-bold text-[11px]">Transição</span>
                    </div>

                    <div className={`p-2 rounded-lg border transition-all ${
                      m5Step === 2
                        ? 'bg-emerald-950 border-emerald-500 text-emerald-300 ring-2 ring-emerald-500/30'
                        : m5Step > 2
                        ? 'bg-slate-950 border-slate-800 text-slate-400'
                        : 'bg-slate-950/60 border-slate-900 text-slate-600'
                    }`}>
                      <span className="text-[10px] block opacity-70">Passo 2</span>
                      <span className="font-bold text-[11px]">Registrar</span>
                    </div>

                    <div className={`p-2 rounded-lg border transition-all ${
                      m5Step === 3
                        ? 'bg-emerald-950 border-emerald-500 text-emerald-300 ring-2 ring-emerald-500/30'
                        : m5Step > 3
                        ? 'bg-slate-950 border-slate-800 text-slate-400'
                        : 'bg-slate-950/60 border-slate-900 text-slate-600'
                    }`}>
                      <span className="text-[10px] block opacity-70">Passo 3</span>
                      <span className="font-bold text-[11px]">Modal Buy-in</span>
                    </div>

                    <div className={`p-2 rounded-lg border transition-all ${
                      m5Step === 4
                        ? 'bg-emerald-950 border-emerald-500 text-emerald-300 ring-2 ring-emerald-500/30'
                        : m5Step > 4
                        ? 'bg-slate-950 border-slate-800 text-slate-400'
                        : 'bg-slate-950/60 border-slate-900 text-slate-600'
                    }`}>
                      <span className="text-[10px] block opacity-70">Passo 4</span>
                      <span className="font-bold text-[11px]">Status</span>
                    </div>

                    <div className={`p-2 rounded-lg border transition-all ${
                      m5Step === 5
                        ? 'bg-emerald-950 border-emerald-500 text-emerald-300 ring-2 ring-emerald-500/30'
                        : 'bg-slate-950/60 border-slate-900 text-slate-600'
                    }`}>
                      <span className="text-[10px] block opacity-70">Passo 5</span>
                      <span className="font-bold text-[11px]">Voltar Lobby</span>
                    </div>
                  </div>

                  {/* Buttons */}
                  <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
                    <button
                      onClick={runFullM5Simulation}
                      disabled={m5AutoRunning}
                      className={`px-4 py-2 rounded-lg font-bold flex items-center gap-2 shadow-md transition-all ${
                        m5AutoRunning
                          ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                          : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 active:scale-95'
                      }`}
                    >
                      <Play className="w-4 h-4 fill-current" />
                      <span>{m5AutoRunning ? 'Executando Esteira...' : 'Executar Inscrição Completa (Passo a Passo)'}</span>
                    </button>

                    <button
                      onClick={stepNextM5}
                      disabled={m5AutoRunning}
                      className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold flex items-center gap-1.5"
                    >
                      <ChevronRight className="w-3.5 h-3.5" />
                      <span>Avançar Passo</span>
                    </button>

                    <button
                      onClick={resetM5}
                      className="px-3.5 py-2 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-400 font-medium flex items-center gap-1.5"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Reiniciar</span>
                    </button>
                  </div>
                </div>

                {/* Live Step Execution Log Timeline */}
                <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-slate-300 flex items-center gap-2">
                      <Terminal className="w-4 h-4 text-emerald-400" />
                      Recibos de Execução da Esteira Módulo 5:
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      {m5StepLogs.length} etapas auditadas
                    </span>
                  </div>

                  <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                    {m5StepLogs.map((log, index) => (
                      <div
                        key={index}
                        className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80 text-xs flex items-start justify-between gap-3 font-mono animate-in fade-in"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="text-emerald-400 font-bold">[{log.step}]</span>
                            <span className="text-[10px] text-slate-500">{log.time}</span>
                          </div>
                          <p className="text-[11px] text-slate-300 font-sans">{log.details}</p>
                        </div>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-900 text-cyan-300 border border-slate-800 shrink-0">
                          {log.durationMs.toFixed(1)}ms
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Module 5 ROIs & Coordinates Table Card */}
                <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800 text-xs font-mono space-y-2">
                  <span className="text-slate-400 uppercase text-[10px] block">
                    Mapeamento Fisiológico de Coordenadas (Base 787x1470 Retrato):
                  </span>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div className="p-2 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block">Botão Registrar (Inferior):</span>
                      <span className="text-emerald-300 font-bold">Click [393.5, 1396.0] · Box [190, 1360, 407, 72]</span>
                    </div>
                    <div className="p-2 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block">Botão Voltar (Back Button):</span>
                      <span className="text-cyan-300 font-bold">Click [56.0, 80.0] · Box [24, 48, 64, 64]</span>
                    </div>
                    <div className="p-2 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block">Modal Confirmar Buy-in:</span>
                      <span className="text-amber-300 font-bold">Click [490.0, 850.0] (Botão Confirmar)</span>
                    </div>
                    <div className="p-2 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block">Modal Cancelar Buy-in:</span>
                      <span className="text-rose-300 font-bold">Click [297.0, 850.0] (Botão Cancelar)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 1: Audit Log CSV Viewer & Pre-Flight Validation */}
        {activeTab === 'audit' && (
          <div className="space-y-5">
            {/* COCKPIT OPERACIONAL PRINCIPAL (GRID RESPONSIVO ~70% DA ÁREA ÚTIL) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              {/* Card 1: Estado da Janela (PPPoker) - lg:col-span-8 */}
              <div className="lg:col-span-8 p-4 rounded-xl bg-slate-900 border border-slate-800 shadow-xl space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                      <Camera className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                          <span>Estado da Janela (PPPoker)</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
                            EM FOCO &amp; ATIVA
                          </span>
                        </h3>
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Alça HWND: <strong className="font-mono text-slate-200">0x00A410C</strong> · Processo: <strong className="font-mono text-cyan-300">PPPoker.exe (PID 8412)</strong> · Contraste: <strong className="font-mono text-emerald-300">std {preflightFrameStd} [VÁLIDO]</strong>
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={recapturePreflightFrame}
                      disabled={isRecapturingFrame}
                      className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow transition-all cursor-pointer"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isRecapturingFrame ? 'animate-spin' : ''}`} />
                      <span>{isRecapturingFrame ? 'Capturando...' : 'Recapturar Frame'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setPreflightFullscreenPreview(true)}
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                      title="Inspecionar em Tela Cheia"
                    >
                      <Maximize2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Window Geometry & Calibration Summary Pills */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                  <div className="p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Resolução Alvo</span>
                    <span className="font-bold text-slate-200">787 × 1470 px</span>
                  </div>
                  <div className="p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Fator de Escala</span>
                    <span className="font-bold text-cyan-300">Sx: 1.000x · Sy: 1.000x</span>
                  </div>
                  <div className="p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Aspect Ratio</span>
                    <span className="font-bold text-emerald-400">0.535 (Retrato 9:16.8)</span>
                  </div>
                  <div className="p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Calibração Anatômica</span>
                    <span className="font-bold text-amber-300">100% Validada</span>
                  </div>
                </div>

                {/* Inline Mini-View: Live Target Miras */}
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-3 text-[11px] font-mono">
                    <span className="text-slate-400 font-sans">Mapeamento de Coordenadas:</span>
                    <span className="text-cyan-300">Voltar [56, 80]</span>
                    <span className="text-slate-400">·</span>
                    <span className="text-slate-200">Filtro [393, 230]</span>
                    <span className="text-slate-400">·</span>
                    <span className="text-emerald-400 font-bold">Alvo [404, 992]</span>
                    <span className="text-slate-400">·</span>
                    <span className="text-amber-300">Registrar [393, 1396]</span>
                  </div>

                  <div className="flex items-center gap-2">
                    <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 text-xs">
                      <input
                        type="checkbox"
                        checked={showCalibrationCrosshairs}
                        onChange={(e) => setShowCalibrationCrosshairs(e.target.checked)}
                        className="w-3.5 h-3.5 rounded accent-emerald-500 cursor-pointer"
                      />
                      <span>Miras</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 text-xs">
                      <input
                        type="checkbox"
                        checked={showCalibrationCardsRoi}
                        onChange={(e) => setShowCalibrationCardsRoi(e.target.checked)}
                        className="w-3.5 h-3.5 rounded accent-cyan-500 cursor-pointer"
                      />
                      <span>ROIs Cartões</span>
                    </label>
                  </div>
                </div>
              </div>

              {/* Card 2: Watchdog Operacional & Intervenção Manual - lg:col-span-4 */}
              <div className="lg:col-span-4 p-4 rounded-xl bg-slate-900 border border-slate-800 shadow-xl space-y-3 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2.5 mb-2.5">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-400" />
                      <h3 className="font-bold text-xs text-slate-100 uppercase tracking-wide">
                        Watchdog Operacional
                      </h3>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                      isHumanTakeover
                        ? 'bg-amber-950 text-amber-300 border border-amber-600 animate-pulse'
                        : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                    }`}>
                      {isHumanTakeover ? 'BOT PAUSADO' : 'AUTÔNOMO ATIVO'}
                    </span>
                  </div>

                  {/* Paused Indicator Alert if active */}
                  {isHumanTakeover ? (
                    <div className="p-2.5 rounded-lg bg-amber-950/70 border border-amber-600/80 text-amber-200 text-xs flex items-center gap-2 animate-pulse mb-2">
                      <AlertOctagon className="w-4 h-4 text-amber-400 shrink-0" />
                      <div>
                        <strong className="block">INTERVENÇÃO MANUAL ATIVA</strong>
                        <span className="text-[10px] text-amber-300">Nenhum clique automático será disparado.</span>
                      </div>
                    </div>
                  ) : (
                    <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300 mb-2 flex items-center justify-between">
                      <span className="text-slate-400">Proteção Ativa:</span>
                      <span className="text-emerald-300 font-mono font-bold">52 Cartas · 0 Frame Preto</span>
                    </div>
                  )}

                  {/* Quick Control Pause / Resume Buttons */}
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={handleToggleHumanTakeover}
                      disabled={isHumanTakeover}
                      className={`px-3 py-2 rounded-lg font-bold text-xs flex items-center justify-center gap-1.5 transition-all ${
                        isHumanTakeover
                          ? 'bg-amber-900/40 text-amber-500 border border-amber-800/50 cursor-not-allowed'
                          : 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md cursor-pointer'
                      }`}
                    >
                      <Pause className="w-3.5 h-3.5 fill-current" />
                      <span>Pausar Bot</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleToggleHumanTakeover}
                      disabled={!isHumanTakeover}
                      className={`px-3 py-2 rounded-lg font-bold text-xs flex items-center justify-center gap-1.5 transition-all ${
                        !isHumanTakeover
                          ? 'bg-slate-800 text-slate-500 border border-slate-700/50 cursor-not-allowed'
                          : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-md cursor-pointer animate-pulse'
                      }`}
                    >
                      <Play className="w-3.5 h-3.5 fill-current" />
                      <span>Retomar Bot</span>
                    </button>
                  </div>
                </div>

                {/* Secondary Settings Panel Toggle */}
                <div className="pt-2 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setShowAdvancedAuditPanel(!showAdvancedAuditPanel)}
                    className={`w-full py-2 px-3 rounded-lg border text-xs font-semibold flex items-center justify-between transition-all cursor-pointer ${
                      showAdvancedAuditPanel
                        ? 'bg-slate-800 border-emerald-500 text-emerald-300 shadow-inner'
                        : 'bg-slate-950 hover:bg-slate-800 border-slate-700 text-slate-300'
                    }`}
                  >
                    <span className="flex items-center gap-1.5">
                      <SlidersHorizontal className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Painel Avançado (A/B, Escala, CMD)</span>
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700">
                      {showAdvancedAuditPanel ? 'OCULTAR' : 'EXPANDIR'}
                    </span>
                  </button>
                  <p className="text-[10px] text-slate-500 mt-1 text-center">
                    {showAdvancedAuditPanel
                      ? 'Exibindo configurações secundárias (A/B, Fatores de Escala, Terminal)'
                      : 'Configurações secundárias ocultas para priorizar 70% da área útil no Log'}
                  </p>
                </div>
              </div>
            </div>

            {/* PAINEL AVANÇADO (CONFIGURAÇÕES SECUNDÁRIAS RECOLHÍVEIS) */}
            {showAdvancedAuditPanel && (
              <div className="p-4 rounded-xl bg-slate-900/90 border-2 border-emerald-500/40 shadow-2xl space-y-4 animate-in fade-in">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <SlidersHorizontal className="w-4 h-4 text-emerald-400" />
                    <h3 className="font-bold text-xs text-slate-100 uppercase tracking-wide">
                      Configurações Secundárias de Engenharia (Calibração, A/B, Pré-Voo)
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowAdvancedAuditPanel(false)}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
                  >
                    Recolher Painel
                  </button>
                </div>

            {/* Pre-Flight Environment & Integrity Check Card (check_init.cmd) */}
            <div className={`p-5 rounded-xl border transition-all duration-200 ${
              preflightStatus === 'OK'
                ? 'bg-slate-900/90 border-slate-800 shadow-xl'
                : preflightStatus === 'WARN'
                ? 'bg-amber-950/20 border-amber-700/80 shadow-amber-950/20 shadow-lg'
                : 'bg-rose-950/20 border-rose-700/80 shadow-rose-950/20 shadow-lg'
            }`}>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4 mb-4">
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 rounded-lg shrink-0 ${
                    preflightStatus === 'OK'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : preflightStatus === 'WARN'
                      ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                      : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                  }`}>
                    <CheckSquare className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                        <span>Diagnóstico Pré-Voo de Inicialização</span>
                        <code className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-emerald-300 border border-slate-700">
                          check_init.cmd
                        </code>
                      </h3>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider ${
                        preflightStatus === 'OK'
                          ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                          : preflightStatus === 'WARN'
                          ? 'bg-amber-950 text-amber-300 border border-amber-700'
                          : 'bg-rose-950 text-rose-300 border border-rose-700'
                      }`}>
                        {preflightStatus === 'OK' ? 'SISTEMA VALIDADO' : preflightStatus === 'WARN' ? 'AVISOS DETECTADOS' : 'ERRO CRÍTICO'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Valida Python, ambiente virtual isolado (.venv), bibliotecas de automação, integridade do CSV diário e presença da janela antes de qualquer clique.
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
                    <span className="text-slate-400 text-[11px] px-1.5 font-sans font-medium">Cenário:</span>
                    <select
                      value={preflightScenario}
                      onChange={(e) => {
                        const val = e.target.value as any;
                        setPreflightScenario(val);
                        runPreflightCheck(val);
                      }}
                      className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded px-2 py-1 focus:outline-none focus:border-emerald-500"
                    >
                      <option value="PERFECT">1. Janela 100% Desobstruída & Frame Válido (Padrão)</option>
                      <option value="WINDOW_MINIMIZED">2. Janela Minimizada na Barra de Tarefas (Descarte de Frame)</option>
                      <option value="WINDOW_BLOCKED">3. Janela Bloqueada por Outro App (Google Chrome Sobreposto)</option>
                      <option value="WINDOW_MISSING">4. Janela PPPoker Fechada (Aviso)</option>
                      <option value="MISSING_DEP">5. Dependência Ausente (pygetwindow)</option>
                      <option value="CSV_AUTOCREATE">6. CSV Inexistente (Auto-inicialização)</option>
                    </select>
                  </div>

                  <button
                    onClick={() => runPreflightCheck(preflightScenario)}
                    disabled={preflightRunning}
                    className="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:opacity-60 text-slate-950 font-bold text-xs shadow transition-all flex items-center gap-1.5"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${preflightRunning ? 'animate-spin' : ''}`} />
                    <span>{preflightRunning ? 'Validando...' : 'Reexecutar check_init.cmd'}</span>
                  </button>
                </div>
              </div>

              {/* 5 Quick Verification Checklist Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 text-[11px] font-medium flex items-center gap-1.5">
                      <Cpu className="w-3.5 h-3.5 text-emerald-400" />
                      1. Python & .venv
                    </span>
                    <span className="text-[10px] font-mono font-bold text-emerald-400 bg-emerald-950/80 px-1.5 py-0.2 rounded border border-emerald-800">
                      [ OK ]
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-slate-200">Python 3.10.12</p>
                  <p className="text-[10px] text-slate-400">Ambiente virtual isolado ativo (.venv)</p>
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 text-[11px] font-medium flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-cyan-400" />
                      2. Bibliotecas
                    </span>
                    <span className={`text-[10px] font-mono font-bold px-1.5 py-0.2 rounded border ${
                      preflightScenario === 'MISSING_DEP'
                        ? 'text-rose-400 bg-rose-950/80 border-rose-800'
                        : 'text-emerald-400 bg-emerald-950/80 border-emerald-800'
                    }`}>
                      {preflightScenario === 'MISSING_DEP' ? '[FALHA]' : '[ OK ]'}
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-slate-200">
                    {preflightScenario === 'MISSING_DEP' ? 'pygetwindow ausente' : 'pyautogui, pygetwindow, PIL'}
                  </p>
                  <p className="text-[10px] text-slate-400">
                    {preflightScenario === 'MISSING_DEP' ? 'Execute preparar.cmd' : 'Pronto para movimento de mouse'}
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 text-[11px] font-medium flex items-center gap-1.5">
                      <FileCheck className="w-3.5 h-3.5 text-amber-400" />
                      3. Log CSV Diário
                    </span>
                    <span className="text-[10px] font-mono font-bold text-emerald-400 bg-emerald-950/80 px-1.5 py-0.2 rounded border border-emerald-800">
                      {preflightScenario === 'CSV_AUTOCREATE' ? '[CRIADO]' : '[ OK ]'}
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-slate-200">clicks_audit_2026-11-02.csv</p>
                  <p className="text-[10px] text-slate-400">
                    {preflightScenario === 'CSV_AUTOCREATE' ? 'Criado com 14 colunas de auditoria' : '14 colunas padrão e gravação com fsync'}
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 text-[11px] font-medium flex items-center gap-1.5">
                      <Maximize2 className="w-3.5 h-3.5 text-fuchsia-400" />
                      4. Visibilidade & Bloqueio
                    </span>
                    <span className={`text-[10px] font-mono font-bold px-1.5 py-0.2 rounded border ${
                      preflightIsMinimized
                        ? 'text-amber-400 bg-amber-950/80 border-amber-800'
                        : preflightIsBlocked
                        ? 'text-rose-400 bg-rose-950/80 border-rose-800'
                        : preflightScenario === 'WINDOW_MISSING'
                        ? 'text-amber-400 bg-amber-950/80 border-amber-800'
                        : preflightScenario === 'MISSING_DEP'
                        ? 'text-rose-400 bg-rose-950/80 border-rose-800'
                        : 'text-emerald-400 bg-emerald-950/80 border-emerald-800'
                    }`}>
                      {preflightIsMinimized
                        ? '[MINIMIZADA]'
                        : preflightIsBlocked
                        ? '[BLOQUEADA]'
                        : preflightScenario === 'WINDOW_MISSING'
                        ? '[FECHADA]'
                        : preflightScenario === 'MISSING_DEP'
                        ? '[FALHA]'
                        : '[DESOBSTRUÍDA]'}
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-slate-200">
                    {preflightIsMinimized
                      ? 'PPPoker na Barra de Tarefas'
                      : preflightIsBlocked
                      ? 'Coberta por Google Chrome'
                      : preflightScenario === 'WINDOW_MISSING'
                      ? 'PPPoker não encontrado'
                      : '"PPPoker" (787x1470 px)'}
                  </p>
                  <p className="text-[10px] text-slate-400">
                    {preflightIsMinimized
                      ? 'Restaure a janela para capturar'
                      : preflightIsBlocked
                      ? 'Feche a janela sobreposta'
                      : preflightScenario === 'WINDOW_MISSING'
                      ? 'Abra o cliente antes de clicar'
                      : '1º Plano · Sem sobreposições'}
                  </p>
                </div>

                {/* Card 5: Frame Capture & OCR Integrity Validation */}
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 text-[11px] font-medium flex items-center gap-1.5">
                      <Camera className="w-3.5 h-3.5 text-emerald-400" />
                      5. Frame & Validação OCR
                    </span>
                    <span className={`text-[10px] font-mono font-bold px-1.5 py-0.2 rounded border ${
                      preflightOcrValid && preflightCalibScore === 100
                        ? 'text-emerald-400 bg-emerald-950/80 border-emerald-800'
                        : preflightOcrValid
                        ? 'text-amber-400 bg-amber-950/80 border-amber-800'
                        : 'text-rose-400 bg-rose-950/80 border-rose-800'
                    }`}>
                      {preflightOcrValid ? '[VÁLIDO PARA OCR]' : '[DESCARTADO]'}
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-slate-200">
                    {preflightOcrValid ? `Contraste std: ${preflightFrameStd}` : 'Frame inválido / Tela preta'}
                  </p>
                  <p className="text-[10px] text-slate-400">
                    {preflightOcrValid ? 'Cartas e números nítidos para OCR' : 'Descartado para evitar leitura falsa'}
                  </p>
                </div>
              </div>

              {/* 2-Column Pre-Flight Diagnostics Workspace: Terminal + Live Frame Thumbnail Calibration */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                {/* Column 1: Windows CMD Terminal Simulator */}
                <div className="lg:col-span-6 flex flex-col space-y-3">
                  <div className="border border-slate-800 rounded-lg overflow-hidden bg-black font-mono text-xs shadow-inner flex-1 flex flex-col">
                    <div className="bg-slate-950 px-3.5 py-2 border-b border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1.5">
                          <div className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
                          <div className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
                          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
                        </div>
                        <span className="font-sans font-semibold text-slate-300 ml-1">Terminal Windows (cmd.exe)</span>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono">C:\VisualPilot\check_init.cmd</span>
                    </div>

                    <div className="p-4 space-y-1 text-slate-300 leading-relaxed overflow-x-auto max-h-[380px] flex-1">
                      <div className="text-slate-500 mb-1">
                        Microsoft Windows [Versão 10.0.19045.5131]
                        <br />(c) Microsoft Corporation. Todos os direitos reservados.
                      </div>
                      <div className="text-emerald-400 font-bold mb-2">
                        C:\VisualPilot&gt; check_init.cmd --capture-thumbnail
                      </div>

                      {preflightOutput.map((line, idx) => {
                        const isOk = line.includes('[ OK ]');
                        const isWarn = line.includes('[WARN]');
                        const isFail = line.includes('[FALHA]') || line.includes('ERRO CRÍTICO');
                        const isHeader = line.startsWith('===') || line.startsWith('---');
                        const isSuccessBanner = line.includes('100% PRONTO') || line.includes('INICIALIZADO COM SUCESSO');

                        return (
                          <div
                            key={idx}
                            className={
                              isFail
                                ? 'text-rose-400 font-bold'
                                : isWarn
                                ? 'text-amber-300 font-bold'
                                : isSuccessBanner
                                ? 'text-emerald-300 font-bold'
                                : isOk
                                ? 'text-emerald-400'
                                : isHeader
                                ? 'text-slate-600'
                                : 'text-slate-300'
                            }
                          >
                            {line}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Calibration Coordinates Table */}
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono space-y-1.5">
                    <span className="text-slate-400 text-[10px] uppercase font-bold tracking-wide block">
                      Mapeamento Anatômico Calibrado (Base 787 × 1470 px):
                    </span>
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div className="p-1.5 rounded bg-slate-900 border border-slate-800 flex items-center justify-between">
                        <span className="text-slate-400">Seta Voltar:</span>
                        <span className="text-cyan-300 font-bold">[56, 80]</span>
                      </div>
                      <div className="p-1.5 rounded bg-slate-900 border border-slate-800 flex items-center justify-between">
                        <span className="text-slate-400">Filtro Top:</span>
                        <span className="text-slate-200 font-bold">[393, 230]</span>
                      </div>
                      <div className="p-1.5 rounded bg-slate-900 border border-slate-800 flex items-center justify-between">
                        <span className="text-slate-400">Alvo Corujão:</span>
                        <span className="text-emerald-400 font-bold">[404, 992]</span>
                      </div>
                      <div className="p-1.5 rounded bg-slate-900 border border-slate-800 flex items-center justify-between">
                        <span className="text-slate-400">Botão Registrar:</span>
                        <span className="text-amber-300 font-bold">[393, 1396]</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Column 2: Live Frame Thumbnail & Visual Calibration Inspector */}
                <div className="lg:col-span-6 flex flex-col space-y-3">
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 shadow-xl space-y-3 flex-1 flex flex-col">
                    {/* Header with Title, Calibration Badge and Actions */}
                    <div className="flex items-center justify-between border-b border-slate-800/80 pb-2.5">
                      <div className="flex items-center gap-2">
                        <Camera className="w-4 h-4 text-emerald-400" />
                        <div>
                          <h4 className="font-bold text-xs text-slate-100 flex items-center gap-2">
                            <span>Miniatura Capturada (Frame PPPoker)</span>
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
                              {preflightCalibScore === 100 ? '100% CALIBRADO' : `${preflightCalibScore}%`}
                            </span>
                          </h4>
                          <span className="text-[10px] text-slate-500 font-mono block">
                            Capturado às: {preflightFrameCapturedAt}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={recapturePreflightFrame}
                          disabled={isRecapturingFrame}
                          className="px-2.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow transition-all cursor-pointer"
                          title="Aciona check_init.cmd para capturar um novo frame do PPPoker"
                        >
                          <RefreshCw className={`w-3.5 h-3.5 ${isRecapturingFrame ? 'animate-spin' : ''}`} />
                          <span>{isRecapturingFrame ? 'Capturando...' : 'Recapturar Frame'}</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => setPreflightFullscreenPreview(true)}
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                          title="Inspecionar em Tela Cheia com Miras de Alta Resolução"
                        >
                          <Maximize2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Interactive Frame Preview Viewport with Calibration Overlays */}
                    <div className="relative border-2 border-slate-700/80 rounded-xl overflow-hidden bg-slate-900 shadow-2xl flex items-center justify-center py-2 px-1 max-h-[360px] select-none">
                      {/* Frame Image Container with exact 787:1470 aspect ratio */}
                      <div
                        className="relative rounded-lg overflow-hidden border border-slate-700/80 shadow-2xl bg-black"
                        style={{ width: '188px', height: '351px' }}
                      >
                        <img
                          src={preflightFrameUrl}
                          alt="Miniatura do Frame PPPoker Capturado"
                          className="w-full h-full object-cover block"
                          onError={(e) => {
                            // Fallback se a imagem direta não carregar
                            (e.target as HTMLImageElement).src = '/modulo2_evidencias/annotated.png';
                          }}
                        />

                        {/* Top Resolution Watermark */}
                        <div className="absolute top-1 right-1 px-1.5 py-0.5 rounded text-[8px] font-mono font-bold bg-slate-950/80 text-emerald-300 border border-emerald-500/50 backdrop-blur-sm z-20">
                          787 × 1470 px
                        </div>

                        {/* Calibration Crosshairs Overlay */}
                        {showCalibrationCrosshairs && (
                          <div className="absolute inset-0 pointer-events-none z-10">
                            {/* Anchor 1: Seta Voltar (56, 80) -> Normalizado: 56/787=7.1%, 80/1470=5.4% */}
                            <div
                              className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center"
                              style={{ left: '7.1%', top: '5.4%' }}
                            >
                              <div className="w-4 h-4 rounded-full border border-cyan-400 bg-cyan-500/20 flex items-center justify-center">
                                <div className="w-1 h-1 rounded-full bg-cyan-300" />
                              </div>
                              <span className="absolute left-4 top-0 px-1 py-0.2 rounded bg-black/80 text-[7px] font-mono text-cyan-300 whitespace-nowrap border border-cyan-600/60">
                                Voltar [56,80]
                              </span>
                            </div>

                            {/* Anchor 2: Filtros / Tabs (393, 230) -> 393/787=50.0%, 230/1470=15.6% */}
                            <div
                              className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center"
                              style={{ left: '50.0%', top: '15.6%' }}
                            >
                              <div className="w-3.5 h-3.5 rounded-full border border-slate-300 bg-white/20 flex items-center justify-center">
                                <div className="w-1 h-1 rounded-full bg-white" />
                              </div>
                              <span className="absolute left-3 -top-2.5 px-1 py-0.2 rounded bg-black/80 text-[7px] font-mono text-slate-300 whitespace-nowrap border border-slate-700">
                                Filtro [393,230]
                              </span>
                            </div>

                            {/* Anchor 3: Target Corujão Click Point (404, 992) -> 404/787=51.3%, 992/1470=67.5% */}
                            <div
                              className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center"
                              style={{ left: '51.3%', top: '67.5%' }}
                            >
                              {showCalibrationTargetPulse && (
                                <div className="absolute w-7 h-7 rounded-full border-2 border-emerald-400 animate-ping opacity-75" />
                              )}
                              <div className="w-5 h-5 rounded-full border-2 border-emerald-400 bg-emerald-500/30 flex items-center justify-center shadow-lg shadow-emerald-500/50">
                                <Crosshair className="w-3 h-3 text-emerald-300" />
                              </div>
                              <span className="absolute left-5 top-0 px-1.5 py-0.5 rounded bg-emerald-950/90 text-[8px] font-mono font-bold text-emerald-300 whitespace-nowrap border border-emerald-500 shadow-md">
                                Alvo Corujão [404,992]
                              </span>
                            </div>

                            {/* Anchor 4: Botão Registrar (393, 1396) -> 393/787=50.0%, 1396/1470=95.0% */}
                            <div
                              className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center"
                              style={{ left: '50.0%', top: '95.0%' }}
                            >
                              <div className="w-4 h-4 rounded-full border border-amber-400 bg-amber-500/20 flex items-center justify-center">
                                <div className="w-1 h-1 rounded-full bg-amber-300" />
                              </div>
                              <span className="absolute right-4 -top-1 px-1 py-0.2 rounded bg-black/80 text-[7px] font-mono text-amber-300 whitespace-nowrap border border-amber-600/60">
                                Registrar [393,1396]
                              </span>
                            </div>
                          </div>
                        )}

                        {/* Tournament Card Bounding Boxes Overlay */}
                        {showCalibrationCardsRoi && (
                          <div className="absolute inset-0 pointer-events-none z-10">
                            {/* Card #0 ROI: local_box: [30, 545, 748, 170] */}
                            <div
                              className="absolute border border-emerald-500/40 bg-emerald-500/5"
                              style={{ left: '3.8%', top: '37.0%', width: '95.0%', height: '11.5%' }}
                            >
                              <span className="absolute top-0.5 left-0.5 text-[6px] font-mono font-bold text-emerald-400 bg-black/70 px-0.5 rounded">
                                #0 Diamante
                              </span>
                            </div>

                            {/* Card #1 ROI: local_box: [30, 727, 748, 168] */}
                            <div
                              className="absolute border border-slate-500/40 bg-slate-500/5"
                              style={{ left: '3.8%', top: '49.4%', width: '95.0%', height: '11.4%' }}
                            >
                              <span className="absolute top-0.5 left-0.5 text-[6px] font-mono font-bold text-slate-300 bg-black/70 px-0.5 rounded">
                                #1 Freezeout
                              </span>
                            </div>

                            {/* Card #2 Target ROI: local_box: [30, 908, 748, 168] */}
                            <div
                              className="absolute border-2 border-emerald-400 bg-emerald-500/10 shadow-lg shadow-emerald-500/20"
                              style={{ left: '3.8%', top: '61.7%', width: '95.0%', height: '11.4%' }}
                            >
                              <span className="absolute top-0.5 left-0.5 text-[7px] font-mono font-bold text-emerald-300 bg-black/80 px-1 rounded border border-emerald-500/60">
                                #2 Corujão [ALVO ATIVO]
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Calibration Toggles Toolbar */}
                    <div className="flex items-center justify-between text-[11px] bg-slate-900 p-2 rounded-lg border border-slate-800">
                      <div className="flex items-center gap-3">
                        <label className="flex items-center gap-1.5 cursor-pointer text-slate-300">
                          <input
                            type="checkbox"
                            checked={showCalibrationCrosshairs}
                            onChange={(e) => setShowCalibrationCrosshairs(e.target.checked)}
                            className="w-3.5 h-3.5 rounded accent-emerald-500 cursor-pointer"
                          />
                          <span>Miras Fisiológicas</span>
                        </label>

                        <label className="flex items-center gap-1.5 cursor-pointer text-slate-300">
                          <input
                            type="checkbox"
                            checked={showCalibrationCardsRoi}
                            onChange={(e) => setShowCalibrationCardsRoi(e.target.checked)}
                            className="w-3.5 h-3.5 rounded accent-cyan-500 cursor-pointer"
                          />
                          <span>ROIs Cartões</span>
                        </label>
                      </div>

                      <span className="font-mono text-[10px] text-emerald-400 font-bold">
                        Sx: 1.000x | Sy: 1.000x (9:16.8)
                      </span>
                    </div>

                    {/* Calibration Telemetry Pill Summary */}
                    <div className="grid grid-cols-3 gap-2 text-[10px] font-mono text-center pt-1 border-t border-slate-800/80">
                      <div className="p-1 rounded bg-slate-900 border border-slate-800">
                        <span className="text-slate-500 block">Resolução Alvo</span>
                        <span className="font-bold text-slate-200">787 × 1470 px</span>
                      </div>
                      <div className="p-1 rounded bg-slate-900 border border-slate-800">
                        <span className="text-slate-500 block">Proporção W/H</span>
                        <span className="font-bold text-cyan-300">0.535 (Retrato)</span>
                      </div>
                      <div className="p-1 rounded bg-slate-900 border border-slate-800">
                        <span className="text-slate-500 block">Margem / Erro</span>
                        <span className="font-bold text-emerald-400">±0.0 px (Exato)</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Painel de Estimativa de Ganho/Perda de Fichas (ROI por Taxa de Sucesso de Registros) */}
            <TournamentChipsProfitEstimator
              logRows={logRows}
              onFilterByStatus={(status) => setLogFilter(status as any)}
            />

            {/* Session Identification & Auto-Recovery Panels */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
              {/* Card 1: Nome da Sessão de Jogo (Coluna #2 no CSV) */}
              <div className="lg:col-span-6 p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3 shadow-md">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-emerald-400" />
                    <h3 className="font-bold text-xs text-slate-100 uppercase tracking-wide">
                      Identificador da Sessão de Jogo
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                    Coluna #2 CSV
                  </span>
                </div>

                <p className="text-[11px] text-slate-400 leading-snug">
                  Define o nome da sessão gravado em cada linha do CSV (<code className="text-emerald-300 font-mono">session_name</code>), facilitando segmentações, tabelas dinâmicas e filtros avançados no Excel.
                </p>

                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={sessionName}
                      onChange={(e) => setSessionName(e.target.value)}
                      placeholder="Ex: Sessão Matinal 01"
                      className="flex-1 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-slate-200 text-xs font-mono focus:border-emerald-500 focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const dateStr = new Date().toISOString().slice(5, 16).replace('T', ' ');
                        setSessionName(`Sessão ${dateStr}`);
                      }}
                      className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold whitespace-nowrap transition-colors"
                      title="Gerar sessão com carimbo de data/hora atual"
                    >
                      Nova (+Hora)
                    </button>
                  </div>

                  <div className="flex items-center gap-1.5 flex-wrap text-[10px]">
                    <span className="text-slate-500 font-sans">Presets Rápidos:</span>
                    {["Sessão Matinal 01", "Sessão Noturna PKO", "Grind Domingo", "Torneios Turbo"].map(preset => (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => setSessionName(preset)}
                        className={`px-2 py-0.5 rounded border transition-colors ${
                          sessionName === preset
                            ? 'bg-emerald-950 border-emerald-600 text-emerald-300 font-bold'
                            : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                        }`}
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Card 2: Modo de Recuperação Automática de Janela (Auto-Recovery Mode) */}
              <div className={`lg:col-span-6 p-4 rounded-xl border space-y-3 shadow-md transition-all ${
                autoRecoveryEnabled
                  ? 'bg-slate-900 border-slate-800'
                  : 'bg-slate-900/60 border-slate-800/80 opacity-80'
              }`}>
                <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-cyan-400" />
                    <h3 className="font-bold text-xs text-slate-100 uppercase tracking-wide">
                      Modo de Recuperação (Auto-Recovery)
                    </h3>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoRecoveryEnabled}
                      onChange={e => setAutoRecoveryEnabled(e.target.checked)}
                      className="w-4 h-4 rounded accent-cyan-500"
                    />
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded border font-bold ${
                      autoRecoveryEnabled
                        ? 'bg-cyan-950 text-cyan-300 border-cyan-800'
                        : 'bg-slate-950 text-slate-500 border-slate-800'
                    }`}>
                      {autoRecoveryEnabled ? 'ATIVO' : 'DESLIGADO'}
                    </span>
                  </label>
                </div>

                <p className="text-[11px] text-slate-400 leading-snug">
                  Quando ativado, caso a janela seja detectada como fechada (<code className="text-cyan-300 font-mono">WINDOW_CLOSED</code>), o bot tenta relançar o PPPoker automaticamente e aguarda a restauração da janela.
                </p>

                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={pppokerExePath}
                      onChange={(e) => setPppokerExePath(e.target.value)}
                      placeholder="Caminho do PPPoker.exe"
                      className="flex-1 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-slate-200 text-xs font-mono focus:border-cyan-500 focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => setPppokerExePath("C:\\Program Files (x86)\\PPPoker\\PPPoker.exe")}
                      className="px-2 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-400 text-xs font-mono"
                      title="Restaurar caminho padrão de instalação no Windows x86"
                    >
                      Padrão
                    </button>
                  </div>

                  {/* Badges de Integridade da Alça de Janela e Processo */}
                  <div className="grid grid-cols-2 gap-2 text-[10px] font-mono pt-1">
                    <div className="p-2 rounded bg-slate-950 border border-slate-800 flex items-center justify-between">
                      <span className="text-slate-400">Alça HWND:</span>
                      <span className={`px-1.5 py-0.5 rounded font-bold ${
                        hasWindowHandle
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : 'bg-rose-950 text-rose-300 border border-rose-800 animate-pulse'
                      }`}>
                        {hasWindowHandle ? 'Ativa (0x00A410C)' : 'Perdida (0x0000000)'}
                      </span>
                    </div>
                    <div className="p-2 rounded bg-slate-950 border border-slate-800 flex items-center justify-between">
                      <span className="text-slate-400">Processo:</span>
                      <span className={`px-1.5 py-0.5 rounded font-bold ${
                        isPppokerProcessRunning
                          ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                          : 'bg-rose-950 text-rose-300 border border-rose-800 animate-pulse'
                      }`}>
                        {isPppokerProcessRunning ? 'PPPoker.exe (PID 8412)' : 'Encerrado (Anomalia)'}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs pt-1">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={simulateSuddenWindowClosureAnomaly}
                        disabled={isRecovering}
                        className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-bold text-xs flex items-center gap-1.5 shadow-md transition-all border border-rose-500"
                        title="Simula o fechamento repentino do PPPoker e testa o disparo automático do Auto-Recovery no Log de Auditoria"
                      >
                        <AlertTriangle className="w-3.5 h-3.5 text-rose-100" />
                        <span>Simular Fechamento Súbito (Anomalia)</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => simulateAutoRecovery("Disparo de Teste Operacional Manual")}
                        disabled={isRecovering}
                        className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow transition-all"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${isRecovering ? 'animate-spin' : ''}`} />
                        <span>{isRecovering ? 'Restaurando...' : 'Testar Recuperação'}</span>
                      </button>
                    </div>

                    <span className="text-[10px] text-slate-400 font-mono">
                      {isRecovering ? (
                        <span className="text-cyan-300 font-bold animate-pulse">Relançando processo...</span>
                      ) : autoRecoveryEnabled ? (
                        <span className="text-emerald-400">✓ Armado para restaurar</span>
                      ) : (
                        <span className="text-slate-500">Recuperação desativada</span>
                      )}
                    </span>
                  </div>

                  <div className="p-2 rounded bg-slate-950/80 border border-slate-800/80 text-[10px] text-slate-400 flex items-center gap-1.5">
                    <span className="text-cyan-400 font-bold">Sequência de Auditoria:</span>
                    <span>WINDOW_CLOSED [ANOMALY] → RECOVERY_ATTEMPTED [RECOVERY] → RECOVERY_SUCCESS [SUCCESS]</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Dynamic Recharts Chart Card for Camouflage A/B Performance */}
            <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
              {/* Header */}
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-gradient-to-br from-emerald-500/20 via-cyan-500/20 to-amber-500/20 border border-emerald-500/30 text-emerald-400 shrink-0">
                    <BarChart3 className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                        <span>Performance Comparativa de Camuflagem (Variante A vs B)</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-cyan-300 border border-slate-700">
                          Recharts Dinâmico
                        </span>
                      </h3>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800">
                        CSV: duration_ms
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Análise visual dinâmica da latência total registrada no arquivo CSV de auditoria, comparando a estratégia furtiva (Variante A) e a agressiva (Variante B).
                    </p>
                  </div>
                </div>

                {/* View Controls & Filter */}
                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-mono">
                    <button
                      type="button"
                      onClick={() => setAuditChartView('timeline')}
                      className={`px-2.5 py-1 rounded transition-colors ${
                        auditChartView === 'timeline'
                          ? 'bg-slate-800 text-cyan-300 font-bold border border-slate-700'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                      title="Evolução cronológica de latência por disparo"
                    >
                      Linha Temporal
                    </button>
                    <button
                      type="button"
                      onClick={() => setAuditChartView('rounds')}
                      className={`px-2.5 py-1 rounded transition-colors ${
                        auditChartView === 'rounds'
                          ? 'bg-slate-800 text-amber-300 font-bold border border-slate-700'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                      title="Comparação direta lado a lado por par de disparos A/B"
                    >
                      Pares A vs B
                    </button>
                    <button
                      type="button"
                      onClick={() => setAuditChartView('breakdown')}
                      className={`px-2.5 py-1 rounded transition-colors ${
                        auditChartView === 'breakdown'
                          ? 'bg-slate-800 text-emerald-300 font-bold border border-slate-700'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                      title="Decomposição fisiológica (Reação vs Movimento vs Pressão)"
                    >
                      Decomposição
                    </button>
                    <button
                      type="button"
                      onClick={() => setAuditChartView('averages')}
                      className={`px-2.5 py-1 rounded transition-colors ${
                        auditChartView === 'averages'
                          ? 'bg-slate-800 text-fuchsia-300 font-bold border border-slate-700'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                      title="Médias consolidadas e amplitude mínima/máxima"
                    >
                      Médias & Faixa
                    </button>
                  </div>

                  {/* Filter selector */}
                  {auditChartView === 'timeline' && (
                    <div className="flex items-center gap-1 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800 text-xs">
                      <span className="text-[10px] text-slate-500 font-mono">Foco:</span>
                      {(['ALL', 'A', 'B'] as const).map(f => (
                        <button
                          key={f}
                          type="button"
                          onClick={() => setAuditChartFilter(f)}
                          className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
                            auditChartFilter === f
                              ? f === 'A'
                                ? 'bg-emerald-950 text-emerald-300 border border-emerald-600 font-bold'
                                : f === 'B'
                                ? 'bg-amber-950 text-amber-300 border border-amber-600 font-bold'
                                : 'bg-slate-800 text-slate-200 border border-slate-700 font-bold'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {f === 'ALL' ? 'Ambas' : `Var ${f}`}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* KPI Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
                {/* Variante A Card */}
                <div className="p-3 rounded-xl bg-slate-950 border border-emerald-900/60 relative overflow-hidden">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-emerald-400 font-bold flex items-center gap-1.5 text-[11px]">
                      <div className="w-2 h-2 rounded-full bg-emerald-400" />
                      Variante A ({strategyA.name})
                    </span>
                    <span className="text-[10px] text-slate-500">{statsA.count} amostras</span>
                  </div>
                  <div className="text-xl font-black text-emerald-300">{statsA.avg} ms <span className="text-xs font-normal text-slate-400 font-sans">médio</span></div>
                  <div className="flex justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-900 mt-1">
                    <span>Faixa: {statsA.min}..{statsA.max}ms</span>
                    <span>σ: ±{statsA.stdDev}ms</span>
                  </div>
                </div>

                {/* Variante B Card */}
                <div className="p-3 rounded-xl bg-slate-950 border border-amber-900/60 relative overflow-hidden">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-amber-400 font-bold flex items-center gap-1.5 text-[11px]">
                      <div className="w-2 h-2 rounded-full bg-amber-400" />
                      Variante B ({strategyB.name})
                    </span>
                    <span className="text-[10px] text-slate-500">{statsB.count} amostras</span>
                  </div>
                  <div className="text-xl font-black text-amber-300">{statsB.avg} ms <span className="text-xs font-normal text-slate-400 font-sans">médio</span></div>
                  <div className="flex justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-900 mt-1">
                    <span>Faixa: {statsB.min}..{statsB.max}ms</span>
                    <span>σ: ±{statsB.stdDev}ms</span>
                  </div>
                </div>

                {/* Delta / Agility Card */}
                <div className="p-3 rounded-xl bg-slate-950 border border-cyan-900/60 relative overflow-hidden">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-cyan-400 font-bold flex items-center gap-1 text-[11px]">
                      <TrendingDown className="w-3.5 h-3.5" />
                      Delta de Agilidade (B vs A)
                    </span>
                  </div>
                  <div className="text-xl font-black text-cyan-300">
                    {statsA.avg && statsB.avg ? `-${Math.abs(statsA.avg - statsB.avg)} ms` : '--'}
                  </div>
                  <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-900 mt-1">
                    {statsA.avg && statsB.avg
                      ? `Variante B é ${Math.round((Math.abs(statsA.avg - statsB.avg) / statsA.avg) * 100)}% mais rápida`
                      : 'Aguardando disparos'}
                  </div>
                </div>

                {/* Entropia / Camuflagem Card */}
                <div className="p-3 rounded-xl bg-slate-950 border border-fuchsia-900/60 relative overflow-hidden">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-fuchsia-400 font-bold flex items-center gap-1 text-[11px]">
                      <Shuffle className="w-3.5 h-3.5" />
                      Proteção Anti-Detecção
                    </span>
                  </div>
                  <div className="text-xl font-black text-fuchsia-300">
                    Alta Entropia
                  </div>
                  <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-900 mt-1 truncate">
                    Alternância temporal contínua
                  </div>
                </div>
              </div>

              {/* Recharts Render Area */}
              {chartAbLogs.length === 0 ? (
                <div className="p-8 rounded-xl bg-slate-950 border border-slate-800 text-center space-y-3">
                  <BarChart3 className="w-8 h-8 text-slate-600 mx-auto" />
                  <p className="text-slate-400 text-xs">
                    Nenhum registro de Teste A/B encontrado no log atual de auditoria.
                  </p>
                  <button
                    onClick={() => setActiveTab('clicker')}
                    className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold text-xs"
                  >
                    Ir para Simulador de Clique e Executar Bateria
                  </button>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80">
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      {/* View 1: Timeline LineChart */}
                      {auditChartView === 'timeline' ? (
                        <LineChart
                          data={chartTimelineData.filter(d => auditChartFilter === 'ALL' || d.variant === auditChartFilter)}
                          margin={{ top: 10, right: 30, left: 0, bottom: 5 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                          <XAxis
                            dataKey="label"
                            stroke="#64748b"
                            tick={{ fontSize: 11, fill: '#94a3b8' }}
                          />
                          <YAxis
                            stroke="#64748b"
                            tick={{ fontSize: 11, fill: '#94a3b8' }}
                            unit="ms"
                          />
                          <Tooltip
                            content={({ active, payload }: any) => {
                              if (active && payload && payload.length) {
                                const pt = payload[0].payload;
                                return (
                                  <div className="bg-slate-900/95 border border-slate-700 p-3 rounded-xl shadow-2xl backdrop-blur-md text-xs font-mono space-y-1.5">
                                    <div className="flex items-center justify-between gap-4 border-b border-slate-800 pb-1 font-bold">
                                      <span className={pt.variant === 'A' ? 'text-emerald-400' : 'text-amber-400'}>
                                        Disparo {pt.label} ({pt.variantName})
                                      </span>
                                      <span className="text-[10px] text-slate-400">{pt.timestamp} UTC</span>
                                    </div>
                                    <div className="text-slate-200">
                                      Latência Total: <strong className="text-cyan-300 font-bold">{pt.totalLatency} ms</strong>
                                    </div>
                                    <div className="grid grid-cols-3 gap-2 text-[10px] pt-1 text-slate-400 border-t border-slate-800">
                                      <span>Reação: <strong className="text-amber-300">{pt.reactionMs}ms</strong></span>
                                      <span>Movimento: <strong className="text-emerald-300">{pt.moveMs}ms</strong></span>
                                      <span>Pressão: <strong className="text-cyan-300">{pt.pressMs}ms</strong></span>
                                    </div>
                                    <div className="text-[10px] text-slate-500 pt-0.5">
                                      Sessão: {pt.session}
                                    </div>
                                  </div>
                                );
                              }
                              return null;
                            }}
                          />
                          <Legend
                            wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
                            formatter={(value) => <span className="text-slate-300">{value}</span>}
                          />
                          {statsA.avg > 0 && (
                            <ReferenceLine
                              y={statsA.avg}
                              stroke="#10b981"
                              strokeDasharray="4 4"
                              label={{ value: `Média A: ${statsA.avg}ms`, fill: '#10b981', fontSize: 10, position: 'right' }}
                            />
                          )}
                          {statsB.avg > 0 && (
                            <ReferenceLine
                              y={statsB.avg}
                              stroke="#f59e0b"
                              strokeDasharray="4 4"
                              label={{ value: `Média B: ${statsB.avg}ms`, fill: '#f59e0b', fontSize: 10, position: 'left' }}
                            />
                          )}
                          {(auditChartFilter === 'ALL' || auditChartFilter === 'A') && (
                            <Line
                              type="monotone"
                              dataKey="latencyA"
                              name={`Variante A (${strategyA.name})`}
                              stroke="#10b981"
                              strokeWidth={2.5}
                              dot={{ r: 4, fill: '#10b981', stroke: '#064e3b', strokeWidth: 1.5 }}
                              activeDot={{ r: 6, fill: '#34d399' }}
                              connectNulls
                            />
                          )}
                          {(auditChartFilter === 'ALL' || auditChartFilter === 'B') && (
                            <Line
                              type="monotone"
                              dataKey="latencyB"
                              name={`Variante B (${strategyB.name})`}
                              stroke="#f59e0b"
                              strokeWidth={2.5}
                              dot={{ r: 4, fill: '#f59e0b', stroke: '#78350f', strokeWidth: 1.5 }}
                              activeDot={{ r: 6, fill: '#fbbf24' }}
                              connectNulls
                            />
                          )}
                        </LineChart>
                      ) : auditChartView === 'rounds' ? (
                        /* View 2: Pares Lado a Lado BarChart */
                        <BarChart
                          data={chartRoundsData}
                          margin={{ top: 10, right: 30, left: 0, bottom: 5 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                          <XAxis dataKey="label" stroke="#64748b" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                          <YAxis stroke="#64748b" tick={{ fontSize: 11, fill: '#94a3b8' }} unit="ms" />
                          <Tooltip
                            content={({ active, payload }: any) => {
                              if (active && payload && payload.length) {
                                const pt = payload[0].payload;
                                return (
                                  <div className="bg-slate-900/95 border border-slate-700 p-3 rounded-xl shadow-2xl backdrop-blur-md text-xs font-mono space-y-1.5">
                                    <div className="font-bold text-slate-100 border-b border-slate-800 pb-1">
                                      Comparação {pt.label}
                                    </div>
                                    <div className="flex justify-between gap-4 text-emerald-300">
                                      <span>Variante A:</span>
                                      <strong>{pt.latencyA !== null ? `${pt.latencyA} ms` : '-'}</strong>
                                    </div>
                                    <div className="flex justify-between gap-4 text-amber-300">
                                      <span>Variante B:</span>
                                      <strong>{pt.latencyB !== null ? `${pt.latencyB} ms` : '-'}</strong>
                                    </div>
                                    {pt.delta !== null && (
                                      <div className="pt-1 border-t border-slate-800 text-[10px] text-cyan-300 flex justify-between">
                                        <span>Delta (A - B):</span>
                                        <strong>{pt.delta > 0 ? `+${pt.delta} ms` : `${pt.delta} ms`}</strong>
                                      </div>
                                    )}
                                  </div>
                                );
                              }
                              return null;
                            }}
                          />
                          <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} formatter={(v) => <span className="text-slate-300">{v}</span>} />
                          <Bar dataKey="latencyA" name={`Variante A (${strategyA.name})`} fill="#10b981" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="latencyB" name={`Variante B (${strategyB.name})`} fill="#f59e0b" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      ) : auditChartView === 'breakdown' ? (
                        /* View 3: Decomposição Fisiológica Stacked Bar */
                        <BarChart
                          data={chartTimelineData}
                          margin={{ top: 10, right: 30, left: 0, bottom: 5 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                          <XAxis dataKey="label" stroke="#64748b" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                          <YAxis stroke="#64748b" tick={{ fontSize: 11, fill: '#94a3b8' }} unit="ms" />
                          <Tooltip
                            content={({ active, payload }: any) => {
                              if (active && payload && payload.length) {
                                const pt = payload[0].payload;
                                return (
                                  <div className="bg-slate-900/95 border border-slate-700 p-3 rounded-xl shadow-2xl backdrop-blur-md text-xs font-mono space-y-1.5">
                                    <div className="font-bold text-slate-100 border-b border-slate-800 pb-1">
                                      {pt.label} • {pt.variantName}
                                    </div>
                                    <div className="text-amber-300 flex justify-between">
                                      <span>Atraso Reação:</span>
                                      <strong>{pt.reactionMs} ms</strong>
                                    </div>
                                    <div className="text-emerald-300 flex justify-between">
                                      <span>Movimento Bézier:</span>
                                      <strong>{pt.moveMs} ms</strong>
                                    </div>
                                    <div className="text-cyan-300 flex justify-between">
                                      <span>Pressão Física:</span>
                                      <strong>{pt.pressMs} ms</strong>
                                    </div>
                                    <div className="pt-1 border-t border-slate-800 text-slate-100 font-bold flex justify-between">
                                      <span>Total:</span>
                                      <strong>{pt.totalLatency} ms</strong>
                                    </div>
                                  </div>
                                );
                              }
                              return null;
                            }}
                          />
                          <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} formatter={(v) => <span className="text-slate-300">{v}</span>} />
                          <Bar dataKey="reactionMs" name="Atraso Cognitivo / Reação" stackId="a" fill="#f59e0b" />
                          <Bar dataKey="moveMs" name="Movimento do Mouse" stackId="a" fill="#10b981" />
                          <Bar dataKey="pressMs" name="Pressão Mecânica" stackId="a" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      ) : (
                        /* View 4: Médias & Faixa */
                        <BarChart
                          data={chartAveragesData}
                          margin={{ top: 10, right: 30, left: 0, bottom: 5 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                          <XAxis dataKey="shortName" stroke="#64748b" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                          <YAxis stroke="#64748b" tick={{ fontSize: 11, fill: '#94a3b8' }} unit="ms" />
                          <Tooltip
                            content={({ active, payload }: any) => {
                              if (active && payload && payload.length) {
                                const pt = payload[0].payload;
                                return (
                                  <div className="bg-slate-900/95 border border-slate-700 p-3 rounded-xl shadow-2xl backdrop-blur-md text-xs font-mono space-y-1.5">
                                    <div className="font-bold text-slate-100 border-b border-slate-800 pb-1">
                                      {pt.name}
                                    </div>
                                    <div className="text-cyan-300 flex justify-between">
                                      <span>Média:</span>
                                      <strong>{pt.media} ms</strong>
                                    </div>
                                    <div className="text-slate-400 flex justify-between">
                                      <span>Faixa (Mín/Máx):</span>
                                      <strong>{pt.min}ms .. {pt.max}ms</strong>
                                    </div>
                                    <div className="text-slate-400 flex justify-between">
                                      <span>Desvio Padrão (σ):</span>
                                      <strong>±{pt.desvio} ms</strong>
                                    </div>
                                    <div className="text-slate-400 flex justify-between">
                                      <span>Total Amostras:</span>
                                      <strong>{pt.amostras}</strong>
                                    </div>
                                  </div>
                                );
                              }
                              return null;
                            }}
                          />
                          <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} formatter={(v) => <span className="text-slate-300">{v}</span>} />
                          <Bar dataKey="media" name="Latência Média (ms)" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="min" name="Latência Mínima (ms)" fill="#10b981" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="max" name="Latência Máxima (ms)" fill="#ef4444" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      )}
                    </ResponsiveContainer>
                  </div>

                  {/* Chart Footer with analytical conclusions & direct CSV download */}
                  <div className="mt-3 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs">
                    <div className="flex items-center gap-2 text-slate-400 font-mono text-[11px]">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      <span>
                        Gráfico alimentado diretamente pelas linhas do CSV (<code className="text-slate-300">duration_ms</code>). Novos cliques no simulador atualizam este painel dinamicamente.
                      </span>
                    </div>

                    <button
                      onClick={() => downloadAuditCsv(abLogs, 'ALL')}
                      className="flex items-center gap-1.5 px-3 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 text-[11px] font-medium transition-colors"
                      title="Baixar apenas os registros deste Teste A/B em CSV"
                    >
                      <Download className="w-3 h-3 text-cyan-400" />
                      <span>Baixar CSV A/B ({abLogs.length} registros)</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

            {/* Action Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900 border border-slate-800 shadow-md">
              <div className="flex items-center gap-3">
                <FileSpreadsheet className="w-5 h-5 text-emerald-400 shrink-0" />
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-sm text-slate-100">
                      Histórico de Auditoria em Tempo Real
                    </h3>
                    <code className="text-xs font-mono text-emerald-300 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800">
                      clicks_audit_2026-10-31.csv
                    </code>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Registrado automaticamente em disco com rotação diária, 15 colunas com session_name e flush imediato
                  </p>
                </div>
              </div>

              {/* Action Buttons: Direct CSV Browser Download */}
              <div className="flex flex-wrap items-center gap-2.5">
                <button
                  onClick={() => downloadAuditCsv(filteredLogs, logFilter)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs shadow-md transition-all active:scale-95 cursor-pointer ring-1 ring-emerald-400/40"
                  title="Baixar arquivo CSV completo com registros de auditoria diretamente para o seu navegador"
                >
                  <Download className="w-4 h-4 text-slate-950" />
                  <span>Baixar CSV Atual ({filteredLogs.length})</span>
                </button>

                {logFilter !== 'ALL' && (
                  <button
                    onClick={() => downloadAuditCsv(logRows, 'ALL')}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs border border-slate-700 transition-all cursor-pointer"
                    title="Baixar todos os registros (sem aplicar o filtro atual)"
                  >
                    <FileSpreadsheet className="w-3.5 h-3.5 text-slate-400" />
                    <span>Baixar Todos ({logRows.length})</span>
                  </button>
                )}
              </div>
            </div>

            {/* Filters Bar with Session Selector */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-slate-900/60 border border-slate-800/80 text-xs">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5 text-slate-400 font-medium">
                  <Filter className="w-3.5 h-3.5 text-slate-400" />
                  <span>Filtrar Exibição:</span>
                </div>

                {/* Session Filter Dropdown */}
                <div className="flex items-center gap-1.5 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800">
                  <span className="text-slate-400 text-[11px]">Sessão:</span>
                  <select
                    value={sessionFilter}
                    onChange={e => setSessionFilter(e.target.value)}
                    className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded px-2 py-0.5 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="ALL">Todas as Sessões ({availableSessions.length})</option>
                    {availableSessions.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => setLogFilter('ALL')}
                  className={`px-3 py-1.5 rounded-lg border font-medium transition-colors cursor-pointer ${
                    logFilter === 'ALL'
                      ? 'bg-slate-800 border-slate-600 text-slate-100 shadow-sm'
                      : 'border-slate-800 text-slate-400 hover:bg-slate-800/50'
                  }`}
                >
                  Todos ({logRows.length})
                </button>
                <button
                  onClick={() => setLogFilter('SUCCESS')}
                  className={`px-3 py-1.5 rounded-lg border font-medium transition-colors cursor-pointer ${
                    logFilter === 'SUCCESS'
                      ? 'bg-emerald-950 border-emerald-700 text-emerald-300 shadow-sm'
                      : 'border-slate-800 text-slate-400 hover:bg-slate-800/50'
                  }`}
                >
                  Sucessos ({logRows.filter(r => r.status === 'SUCCESS').length})
                </button>
                <button
                  onClick={() => setLogFilter('HALT')}
                  className={`px-3 py-1.5 rounded-lg border font-medium transition-colors cursor-pointer ${
                    logFilter === 'HALT'
                      ? 'bg-amber-950 border-amber-700 text-amber-300 shadow-sm'
                      : 'border-slate-800 text-slate-400 hover:bg-slate-800/50'
                  }`}
                >
                  Halt / Watchdog ({logRows.filter(r => r.status === 'HALT' || r.event_type === 'SYSTEM_HALT').length})
                </button>
                <button
                  onClick={() => setLogFilter('ESCALATED')}
                  className={`px-3 py-1.5 rounded-lg border font-medium transition-colors cursor-pointer ${
                    logFilter === 'ESCALATED'
                      ? 'bg-fuchsia-950 border-fuchsia-700 text-fuchsia-300 shadow-sm ring-1 ring-fuchsia-600/40'
                      : 'border-slate-800 text-slate-400 hover:bg-slate-800/50'
                  }`}
                >
                  Escalada Remota ({logRows.filter(r => r.status === 'ESCALATED' || r.event_type === 'ESCALATION_ALERT_SENT').length})
                </button>
                <button
                  onClick={() => setLogFilter('RECOVERY' as any)}
                  className={`px-3 py-1.5 rounded-lg border font-medium transition-colors cursor-pointer ${
                    (logFilter as string) === 'RECOVERY'
                      ? 'bg-cyan-950 border-cyan-700 text-cyan-300 shadow-sm ring-1 ring-cyan-600/40'
                      : 'border-slate-800 text-slate-400 hover:bg-slate-800/50'
                  }`}
                >
                  Recuperação ({logRows.filter(r => r.status === 'RECOVERY' || r.event_type.startsWith('RECOVERY')).length})
                </button>
                <button
                  onClick={() => setLogFilter('ABORTED')}
                  className={`px-3 py-1.5 rounded-lg border font-medium transition-colors cursor-pointer ${
                    logFilter === 'ABORTED'
                      ? 'bg-rose-950 border-rose-800 text-rose-300 shadow-sm'
                      : 'border-slate-800 text-slate-400 hover:bg-slate-800/50'
                  }`}
                >
                  Abortados / Erros ({logRows.filter(r => r.status === 'ABORTED' || r.status === 'ERROR').length})
                </button>
              </div>
            </div>

            {/* Heartbeat Watchdog Status & Controls Banner */}
            <div className={`p-4 rounded-xl border flex flex-wrap items-center justify-between gap-4 transition-all duration-200 ${
              heartbeatActive 
                ? 'bg-emerald-950/20 border-emerald-900/60' 
                : 'bg-amber-950/30 border-amber-700/80'
            }`}>
              <div className="flex items-center gap-3">
                <div className={`w-3.5 h-3.5 rounded-full ${
                  heartbeatActive ? 'bg-emerald-400 animate-pulse' : 'bg-amber-500 ring-4 ring-amber-500/20'
                }`} />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-xs text-slate-200">
                      Heartbeat Watchdog (Anti-Congelamento):
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider ${
                      heartbeatActive
                        ? 'bg-emerald-900/80 text-emerald-300 border border-emerald-700'
                        : 'bg-amber-900/90 text-amber-200 border border-amber-600'
                    }`}>
                      {heartbeatActive ? 'PULSAÇÃO ATIVA' : 'SYSTEM_HALT ATIVADO'}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    {heartbeatActive
                      ? `Watchdog checando pulsação a cada 1.0s. Limite de inatividade: 30.0s. Última pulsação: ${lastBeatTime}.`
                      : 'Nenhum sinal recebido em 30s! O bot bloqueou qualquer clique para evitar ações obsoletas no desktop.'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {heartbeatActive ? (
                  <button
                    onClick={simulateHeartbeatHalt}
                    className="px-3.5 py-1.5 rounded-lg bg-amber-950 hover:bg-amber-900 border border-amber-700 text-amber-200 text-xs font-semibold flex items-center gap-1.5 shadow"
                  >
                    <Activity className="w-3.5 h-3.5 text-amber-400" />
                    <span>Simular Travamento &gt; 30s (Disparar SYSTEM_HALT)</span>
                  </button>
                ) : (
                  <button
                    onClick={resumeHeartbeat}
                    className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 text-xs font-bold flex items-center gap-1.5 shadow-md"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Restabelecer Pulsação (Retomar Watchdog)</span>
                  </button>
                )}
              </div>
            </div>

            {/* Remote Escalation & Webhook Monitoring Card (> 5 min) */}
            <div className={`p-5 rounded-xl border transition-all duration-300 ${
              escalationSent
                ? 'bg-fuchsia-950/30 border-fuchsia-500/80 ring-2 ring-fuchsia-500/30 shadow-lg shadow-fuchsia-950/40'
                : !heartbeatActive
                ? 'bg-amber-950/25 border-amber-600/70 shadow-md shadow-amber-950/30'
                : 'bg-slate-900/80 border-slate-800'
            }`}>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-4 mb-4">
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 rounded-lg shrink-0 ${
                    escalationSent
                      ? 'bg-fuchsia-900/60 text-fuchsia-300 ring-2 ring-fuchsia-500/50 animate-pulse'
                      : !heartbeatActive
                      ? 'bg-amber-900/50 text-amber-300'
                      : 'bg-slate-800 text-slate-300'
                  }`}>
                    <Radio className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                        <span>Escalada Remota Automática</span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                          Webhook / E-mail / Discord / Telegram
                        </span>
                      </h4>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider ${
                        escalationSent
                          ? 'bg-fuchsia-900 text-fuchsia-200 border border-fuchsia-600 animate-pulse'
                          : !heartbeatActive
                          ? 'bg-amber-900/90 text-amber-200 border border-amber-600'
                          : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                      }`}>
                        {escalationSent
                          ? 'ALERTA REMOTO ENVIADO'
                          : !heartbeatActive
                          ? `ESCALANDO EM ${Math.max(0, escalationTimeout - haltElapsedSeconds)}s`
                          : 'VIGILÂNCIA REMOTA ARMADA'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Dispara automaticamente uma notificação remota caso o sistema permaneça em <code>SYSTEM_HALT</code> por mais de 5 minutos, garantindo alerta mesmo longe do monitor.
                    </p>
                  </div>
                </div>

                {/* Preset Service Selectors */}
                <div className="flex items-center gap-1.5 bg-slate-950/80 p-1 rounded-lg border border-slate-800 text-xs">
                  <button
                    onClick={() => {
                      setWebhookProvider('discord');
                      setWebhookUrl("https://discord.com/api/webhooks/1301000000000000000/VisualPilotBotAlert");
                    }}
                    className={`px-2.5 py-1 rounded font-medium flex items-center gap-1.5 transition-colors ${
                      webhookProvider === 'discord'
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span>Discord</span>
                  </button>
                  <button
                    onClick={() => {
                      setWebhookProvider('telegram');
                      setWebhookUrl("https://api.telegram.org/bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/sendMessage?chat_id=-100123456789");
                    }}
                    className={`px-2.5 py-1 rounded font-medium flex items-center gap-1.5 transition-colors ${
                      webhookProvider === 'telegram'
                        ? 'bg-sky-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Telegram</span>
                  </button>
                  <button
                    onClick={() => {
                      setWebhookProvider('email');
                      setWebhookUrl("https://hooks.zapier.com/hooks/catch/9876543/email_alert_on_halt");
                    }}
                    className={`px-2.5 py-1 rounded font-medium flex items-center gap-1.5 transition-colors ${
                      webhookProvider === 'email'
                        ? 'bg-amber-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <Mail className="w-3.5 h-3.5" />
                    <span>E-mail (Zapier/Make)</span>
                  </button>
                  <button
                    onClick={() => {
                      setWebhookProvider('generic');
                      setWebhookUrl("https://meuservidor.com/api/v1/alerts/visualpilot");
                    }}
                    className={`px-2.5 py-1 rounded font-medium flex items-center gap-1.5 transition-colors ${
                      webhookProvider === 'generic'
                        ? 'bg-slate-700 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>REST / Genérico</span>
                  </button>
                </div>
              </div>

              {/* URL & Timeout Configuration Controls */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-3 text-xs mb-4">
                <div className="md:col-span-8 flex flex-col gap-1">
                  <label className="text-[11px] font-mono text-slate-400 flex items-center justify-between">
                    <span>URL do Endpoint de Notificação (Webhook):</span>
                    <span className="text-[10px] text-slate-500">Mascara ativa nos logs CSV: {maskWebhook(webhookUrl)}</span>
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      value={webhookUrl}
                      onChange={(e) => setWebhookUrl(e.target.value)}
                      placeholder="https://..."
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-slate-200 font-mono text-xs focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 outline-none pr-8"
                    />
                    <Send className="w-3.5 h-3.5 text-slate-500 absolute right-3 top-2.5 pointer-events-none" />
                  </div>
                </div>

                <div className="md:col-span-4 flex flex-col gap-1">
                  <label className="text-[11px] font-mono text-slate-400 flex items-center justify-between">
                    <span className="flex items-center gap-1">
                      <Timer className="w-3 h-3 text-cyan-400" />
                      Limite de Inatividade:
                    </span>
                    <span className="text-[10px] text-emerald-400 font-bold">
                      {escalationTimeout >= 60 ? `${(escalationTimeout / 60).toFixed(0)} min` : `${escalationTimeout}s`}
                    </span>
                  </label>
                  <div className="grid grid-cols-3 gap-1">
                    <button
                      type="button"
                      onClick={() => setEscalationTimeout(5)}
                      className={`py-2 px-1 rounded-lg border font-mono text-[11px] font-semibold text-center transition-colors ${
                        escalationTimeout === 5
                          ? 'bg-cyan-950 border-cyan-600 text-cyan-300'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:bg-slate-800/60'
                      }`}
                      title="5 segundos para teste rápido e interativo no navegador"
                    >
                      5s (Demo)
                    </button>
                    <button
                      type="button"
                      onClick={() => setEscalationTimeout(60)}
                      className={`py-2 px-1 rounded-lg border font-mono text-[11px] font-semibold text-center transition-colors ${
                        escalationTimeout === 60
                          ? 'bg-cyan-950 border-cyan-600 text-cyan-300'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:bg-slate-800/60'
                      }`}
                    >
                      1 min
                    </button>
                    <button
                      type="button"
                      onClick={() => setEscalationTimeout(300)}
                      className={`py-2 px-1 rounded-lg border font-mono text-[11px] font-semibold text-center transition-colors ${
                        escalationTimeout === 300
                          ? 'bg-emerald-950 border-emerald-600 text-emerald-300'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:bg-slate-800/60'
                      }`}
                      title="Padrão de produção: 5 minutos (300 segundos)"
                    >
                      5 min (Prod)
                    </button>
                  </div>
                </div>
              </div>

              {/* Real-time Watchdog Progress Bar when in SYSTEM_HALT */}
              {!heartbeatActive && (
                <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 mb-4 animate-in fade-in duration-200">
                  <div className="flex items-center justify-between text-xs mb-1.5 font-mono">
                    <span className="flex items-center gap-1.5 text-amber-300 font-semibold">
                      <Activity className="w-3.5 h-3.5 text-amber-400 animate-spin" />
                      Tempo em SYSTEM_HALT: {haltElapsedSeconds}s / {escalationTimeout}s
                    </span>
                    <span className={`text-[11px] font-bold ${
                      escalationSent ? 'text-fuchsia-400' : 'text-slate-400'
                    }`}>
                      {escalationSent
                        ? 'Alerta despachado com sucesso!'
                        : `Disparo automático em: ${Math.max(0, escalationTimeout - haltElapsedSeconds)}s`}
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className={`h-full transition-all duration-1000 ${
                        escalationSent
                          ? 'bg-fuchsia-500'
                          : haltElapsedSeconds / escalationTimeout > 0.7
                          ? 'bg-rose-500 animate-pulse'
                          : 'bg-amber-500'
                      }`}
                      style={{ width: `${Math.min(100, (haltElapsedSeconds / escalationTimeout) * 100)}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Action Buttons: Test Dispatch & View Payload */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div className="flex items-center gap-2 text-xs">
                  <button
                    onClick={() => triggerEscalationDispatch(escalationTimeout, true)}
                    className="px-4 py-2 rounded-lg bg-fuchsia-600 hover:bg-fuchsia-500 text-slate-950 text-xs font-bold flex items-center gap-2 shadow-md transition-all active:scale-95"
                    title="Dispara imediatamente um payload de teste para o webhook configurado"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Disparar Webhook de Teste Agora</span>
                  </button>

                  <button
                    onClick={() => setShowPayloadPreview(!showPayloadPreview)}
                    className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1.5 transition-colors"
                  >
                    <FileCode2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>{showPayloadPreview ? 'Ocultar Payload' : 'Ver Payload Remoto (JSON / Embed)'}</span>
                  </button>
                </div>

                <div className="text-[11px] text-slate-400 font-mono flex items-center gap-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Sem libs externas no Python (nativo via <code>urllib.request</code>)</span>
                </div>
              </div>

              {/* Expandable Payload Preview */}
              {showPayloadPreview && (
                <div className="mt-4 pt-4 border-t border-slate-800/80 animate-in fade-in duration-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-mono text-cyan-400 flex items-center gap-1.5 font-bold">
                      <FileCode2 className="w-3.5 h-3.5" />
                      Payload HTTP POST formatado ({webhookProvider.toUpperCase()}):
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      Endpoint: {maskWebhook(webhookUrl)}
                    </span>
                  </div>
                  <pre className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto leading-relaxed shadow-inner">
                    {JSON.stringify(getPayloadPreview(webhookProvider, webhookUrl, escalationTimeout), null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {/* Test Anomaly Triggers & Sound Alarm Test */}
            <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs">
              <span className="text-slate-400 font-mono flex items-center gap-1.5">
                <AlertOctagon className="w-4 h-4 text-amber-400" />
                Simular Anomalias & Testes de Alarme:
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    playSynthesizedAlarm('CRITICAL');
                    addToast({
                      title: "TESTE DE ALARME SONORO E VISUAL",
                      message: "Sirene sintetizada de emergência (880Hz/587Hz) disparada com sucesso no navegador.",
                      eventType: "SYSTEM_HALT",
                      severity: "CRITICAL"
                    });
                  }}
                  className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-medium flex items-center gap-1.5"
                  title="Testar som e toast no navegador"
                >
                  <BellRing className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
                  <span>Testar Alarme Sonoro</span>
                </button>
                <button
                  onClick={() => simulateAnomaly('CLOSE')}
                  className="px-3 py-1.5 rounded bg-rose-950/60 hover:bg-rose-900 border border-rose-800 text-rose-200 font-medium"
                >
                  Simular Janela Fechada (WINDOW_CLOSED)
                </button>
                <button
                  onClick={() => simulateAnomaly('RESIZE')}
                  className="px-3 py-1.5 rounded bg-amber-950/60 hover:bg-amber-900 border border-amber-800 text-amber-200 font-medium"
                >
                  Simular Deformação Drástica (RESOLUTION_CHANGED)
                </button>
              </div>
            </div>

            {/* Log Table */}
            <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-900/60 shadow-xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-950 border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                    <tr>
                      <th className="py-3 px-4">Timestamp (UTC)</th>
                      <th className="py-3 px-3">Sessão</th>
                      <th className="py-3 px-3">Evento</th>
                      <th className="py-3 px-3">Status</th>
                      <th className="py-3 px-3">Torneio</th>
                      <th className="py-3 px-3">Buy-in</th>
                      <th className="py-3 px-3">Alvo (X, Y)</th>
                      <th className="py-3 px-3">Janela (L, T, W, H)</th>
                      <th className="py-3 px-4">Detalhes da Execução</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70 text-slate-300">
                    {filteredLogs.map((row, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                        <td className="py-3 px-4 text-slate-400 text-[11px] whitespace-nowrap">
                          {row.timestamp_iso.replace('T', ' ').replace('Z', '')}
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap">
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-800 text-slate-300 border border-slate-700">
                            {row.session_name || "Sessão Principal"}
                          </span>
                        </td>
                        <td className="py-3 px-3">
                          <span className="font-semibold text-slate-200">{row.event_type}</span>
                        </td>
                        <td className="py-3 px-3">
                          {row.status === 'SUCCESS' ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                              SUCCESS
                            </span>
                          ) : row.status === 'HALT' ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-700">
                              HALT (30s)
                            </span>
                          ) : row.status === 'ESCALATED' ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-fuchsia-950 text-fuchsia-300 border border-fuchsia-700 flex items-center gap-1 shadow-sm">
                              <Radio className="w-3 h-3 text-fuchsia-400 animate-pulse" />
                              ESCALATED (&gt;5m)
                            </span>
                          ) : row.status === 'RECOVERY' ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-700 flex items-center gap-1 shadow-sm">
                              <RefreshCw className="w-3 h-3 text-cyan-400 animate-spin" />
                              RECOVERY
                            </span>
                          ) : row.status === 'SKIPPED' ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-800 flex items-center gap-1 shadow-sm">
                              <ShieldCheck className="w-3 h-3 text-amber-400" />
                              SKIPPED (ANTI-DUP)
                            </span>
                          ) : row.status === 'ANOMALY' ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-200 border border-rose-700 flex items-center gap-1 shadow-sm animate-pulse">
                              <AlertTriangle className="w-3 h-3 text-rose-400" />
                              ANOMALY
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-300 border border-rose-900">
                              {row.status}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3 text-slate-200 font-medium whitespace-nowrap">
                          {row.tournament_name}
                        </td>
                        <td className="py-3 px-3 text-amber-300 font-bold">
                          {row.buyin_chips ? `${row.buyin_chips}` : '-'}
                        </td>
                        <td className="py-3 px-3 text-emerald-300">
                          {row.target_abs_x !== '-' ? `(${row.target_abs_x}, ${row.target_abs_y})` : '-'}
                        </td>
                        <td className="py-3 px-3 text-slate-400 text-[10px]">
                          [{row.win_left}, {row.win_top}, {row.win_width}, {row.win_height}]
                        </td>
                        <td className="py-3 px-4 text-slate-400 text-[11px] max-w-md truncate" title={row.details}>
                          {row.details}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Table Footer with Summary and Quick Download */}
              <div className="bg-slate-950 px-4 py-3 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px]">
                    Exibindo <strong className="text-slate-200">{filteredLogs.length}</strong> de <strong className="text-slate-200">{logRows.length}</strong> registros de auditoria
                  </span>
                  <span className="text-slate-600 hidden sm:inline">•</span>
                  <span className="text-[11px] text-slate-500 hidden sm:inline">
                    Formato RFC 4180 com codificação UTF-8 BOM para compatibilidade com Excel
                  </span>
                </div>

                <button
                  onClick={() => downloadAuditCsv(filteredLogs, logFilter)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-950/70 hover:bg-emerald-900 border border-emerald-700/80 text-emerald-300 font-semibold text-xs transition-colors cursor-pointer"
                  title="Baixar arquivo CSV desta visualização"
                >
                  <Download className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Baixar Arquivo CSV ({filteredLogs.length})</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Module 4 Clicker & Dynamic Window Simulator */}
        {activeTab === 'clicker' && (
          <div className="space-y-6">
            {/* A/B Testing System for Camouflage Strategies */}
            <div className={`p-5 rounded-xl border transition-all duration-300 shadow-xl ${
              abTestEnabled
                ? 'bg-slate-900/90 border-slate-700/80 shadow-slate-950/60 ring-1 ring-slate-700'
                : 'bg-slate-900/50 border-slate-800'
            }`}>
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4 mb-4">
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 rounded-xl border shrink-0 transition-colors ${
                    abTestEnabled
                      ? 'bg-gradient-to-br from-emerald-500/20 to-amber-500/20 border-emerald-500/40 text-emerald-400'
                      : 'bg-slate-800 border-slate-700 text-slate-400'
                  }`}>
                    <Shuffle className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                        <span>Sistema de Teste A/B de Camuflagem</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-cyan-300 border border-slate-700">
                          Anti-Detecção & Latência
                        </span>
                      </h3>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider ${
                        abTestEnabled
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-700'
                          : 'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}>
                        {abTestEnabled ? 'TESTE A/B ATIVO (ALTERNANDO)' : 'TESTE A/B DESLIGADO'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5 max-w-3xl leading-relaxed">
                      Defina duas estratégias com diferentes velocidades de clique, atrasos cognitivos e dispersão. O bot alterna automaticamente entre a <strong className="text-emerald-400">Variante A</strong> e a <strong className="text-amber-400">Variante B</strong> a cada clique, registrando o desempenho no CSV para comparação e auditoria no Excel.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {abTestEnabled && (
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono">
                      <span className="text-slate-400 text-[11px]">Próximo Disparo:</span>
                      <span className={`px-2 py-0.5 rounded font-black text-xs border flex items-center gap-1.5 ${
                        nextAbVariant === 'A'
                          ? 'bg-emerald-950/80 text-emerald-300 border-emerald-600 ring-1 ring-emerald-500/30'
                          : 'bg-amber-950/80 text-amber-300 border-amber-600 ring-1 ring-amber-500/30'
                      }`}>
                        <div className={`w-2 h-2 rounded-full animate-pulse ${
                          nextAbVariant === 'A' ? 'bg-emerald-400' : 'bg-amber-400'
                        }`} />
                        <span>VARIANTE {nextAbVariant}</span>
                      </span>
                    </div>
                  )}

                  <label className="flex items-center gap-2 cursor-pointer bg-slate-950 px-3 py-2 rounded-lg border border-slate-800 hover:border-slate-700 transition-colors">
                    <input
                      type="checkbox"
                      checked={abTestEnabled}
                      onChange={e => setAbTestEnabled(e.target.checked)}
                      className="w-4 h-4 rounded accent-emerald-500"
                    />
                    <span className="font-semibold text-xs text-slate-200">
                      Habilitar Teste A/B
                    </span>
                  </label>
                </div>
              </div>

              {/* Presets Rápidos */}
              <div className="flex items-center justify-between gap-2 flex-wrap text-xs mb-4 pb-3 border-b border-slate-800/80">
                <span className="text-slate-400 text-[11px] font-sans flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Carregar Combinações Predefinidas:</span>
                </span>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <button
                    type="button"
                    onClick={() => {
                      setStrategyA({
                        id: 'A',
                        name: 'Estratégia A (Furtiva / Humana)',
                        speed: 'natural',
                        delayMinMs: 350,
                        delayMaxMs: 850,
                        applyJitter: true
                      });
                      setStrategyB({
                        id: 'B',
                        name: 'Estratégia B (Agressiva / Rápida)',
                        speed: 'fast',
                        delayMinMs: 150,
                        delayMaxMs: 380,
                        applyJitter: true
                      });
                    }}
                    className="px-2.5 py-1 rounded bg-slate-950 hover:bg-slate-800 border border-slate-700 text-slate-300 text-[11px] font-medium transition-colors"
                  >
                    1. Furtiva (A) vs Agressiva (B)
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setStrategyA({
                        id: 'A',
                        name: 'Estratégia A (Humano Padrão)',
                        speed: 'natural',
                        delayMinMs: 300,
                        delayMaxMs: 650,
                        applyJitter: true
                      });
                      setStrategyB({
                        id: 'B',
                        name: 'Estratégia B (Ultra-Cautelosa)',
                        speed: 'slow',
                        delayMinMs: 600,
                        delayMaxMs: 1400,
                        applyJitter: true
                      });
                    }}
                    className="px-2.5 py-1 rounded bg-slate-950 hover:bg-slate-800 border border-slate-700 text-slate-300 text-[11px] font-medium transition-colors"
                  >
                    2. Padrão (A) vs Ultra-Cautelosa (B)
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setStrategyA({
                        id: 'A',
                        name: 'Estratégia A (Com Jitter ±4px)',
                        speed: 'natural',
                        delayMinMs: 350,
                        delayMaxMs: 700,
                        applyJitter: true
                      });
                      setStrategyB({
                        id: 'B',
                        name: 'Estratégia B (Zero Jitter / Fixo)',
                        speed: 'natural',
                        delayMinMs: 350,
                        delayMaxMs: 700,
                        applyJitter: false
                      });
                    }}
                    className="px-2.5 py-1 rounded bg-slate-950 hover:bg-slate-800 border border-slate-700 text-slate-300 text-[11px] font-medium transition-colors"
                  >
                    3. Jitter Ativo (A) vs Sem Jitter (B)
                  </button>
                </div>
              </div>

              {/* Side-by-Side Strategy Configuration Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                {/* Configuração da Variante A */}
                <div className={`p-4 rounded-xl border transition-all ${
                  abTestEnabled && nextAbVariant === 'A'
                    ? 'bg-emerald-950/20 border-emerald-500/80 ring-2 ring-emerald-500/20 shadow-lg'
                    : 'bg-slate-950/80 border-slate-800'
                }`}>
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-emerald-500 text-slate-950 font-black text-xs flex items-center justify-center">
                        A
                      </span>
                      <span className="font-bold text-xs text-emerald-300 uppercase tracking-wide">
                        Variante A
                      </span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                      {strategyA.speed.toUpperCase()} · {strategyA.delayMinMs}-{strategyA.delayMaxMs}ms
                    </span>
                  </div>

                  <div className="space-y-3 text-xs">
                    <div>
                      <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                        Nome / Rótulo da Variante:
                      </label>
                      <input
                        type="text"
                        value={strategyA.name}
                        onChange={e => setStrategyA(prev => ({ ...prev, name: e.target.value }))}
                        className="w-full px-2.5 py-1 rounded bg-slate-900 border border-slate-700 text-slate-200 text-xs font-mono focus:border-emerald-500 outline-none"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                        <span>Perfil de Velocidade do Mouse:</span>
                        <span className="text-emerald-400 font-mono font-bold">
                          {strategyA.speed === 'fast' ? 'Rápido (~160ms)' : strategyA.speed === 'natural' ? 'Natural (~300ms)' : 'Lento (~650ms)'}
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-1">
                        {(['fast', 'natural', 'slow'] as const).map(spd => (
                          <button
                            key={spd}
                            type="button"
                            onClick={() => setStrategyA(prev => ({ ...prev, speed: spd }))}
                            className={`py-1.5 px-2 rounded border text-center text-[10px] font-mono font-semibold transition-colors ${
                              strategyA.speed === spd
                                ? 'bg-emerald-950 border-emerald-500 text-emerald-200 font-bold'
                                : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
                            }`}
                          >
                            {spd === 'fast' ? 'Rápido' : spd === 'natural' ? 'Natural' : 'Lento'}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-2 pt-1">
                      <div>
                        <div className="flex justify-between text-[11px] font-mono text-slate-400 mb-1">
                          <span>Atraso Mínimo de Reação:</span>
                          <span className="text-emerald-400 font-bold">{strategyA.delayMinMs} ms</span>
                        </div>
                        <input
                          type="range"
                          min="50"
                          max="800"
                          step="25"
                          value={strategyA.delayMinMs}
                          onChange={e => {
                            const val = Number(e.target.value);
                            setStrategyA(prev => ({
                              ...prev,
                              delayMinMs: val,
                              delayMaxMs: Math.max(val + 50, prev.delayMaxMs)
                            }));
                          }}
                          className="w-full accent-emerald-500 cursor-pointer"
                        />
                      </div>

                      <div>
                        <div className="flex justify-between text-[11px] font-mono text-slate-400 mb-1">
                          <span>Atraso Máximo de Reação:</span>
                          <span className="text-emerald-400 font-bold">{strategyA.delayMaxMs} ms</span>
                        </div>
                        <input
                          type="range"
                          min="150"
                          max="2000"
                          step="50"
                          value={strategyA.delayMaxMs}
                          onChange={e => {
                            const val = Number(e.target.value);
                            setStrategyA(prev => ({
                              ...prev,
                              delayMaxMs: val,
                              delayMinMs: Math.min(val - 50, prev.delayMinMs)
                            }));
                          }}
                          className="w-full accent-emerald-500 cursor-pointer"
                        />
                      </div>
                    </div>

                    <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                      <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                        <input
                          type="checkbox"
                          checked={strategyA.applyJitter}
                          onChange={e => setStrategyA(prev => ({ ...prev, applyJitter: e.target.checked }))}
                          className="w-3.5 h-3.5 rounded accent-emerald-500"
                        />
                        <span>Jitter Gaussiano (±3-5 px)</span>
                      </label>
                      <span className="text-[10px] text-emerald-400/90 font-mono">
                        ~{Math.round((strategyA.delayMinMs + strategyA.delayMaxMs)/2 + (strategyA.speed === 'fast' ? 225 : strategyA.speed === 'natural' ? 395 : 780))}ms estimada
                      </span>
                    </div>
                  </div>
                </div>

                {/* Configuração da Variante B */}
                <div className={`p-4 rounded-xl border transition-all ${
                  abTestEnabled && nextAbVariant === 'B'
                    ? 'bg-amber-950/20 border-amber-500/80 ring-2 ring-amber-500/20 shadow-lg'
                    : 'bg-slate-950/80 border-slate-800'
                }`}>
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-amber-500 text-slate-950 font-black text-xs flex items-center justify-center">
                        B
                      </span>
                      <span className="font-bold text-xs text-amber-300 uppercase tracking-wide">
                        Variante B
                      </span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
                      {strategyB.speed.toUpperCase()} · {strategyB.delayMinMs}-{strategyB.delayMaxMs}ms
                    </span>
                  </div>

                  <div className="space-y-3 text-xs">
                    <div>
                      <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                        Nome / Rótulo da Variante:
                      </label>
                      <input
                        type="text"
                        value={strategyB.name}
                        onChange={e => setStrategyB(prev => ({ ...prev, name: e.target.value }))}
                        className="w-full px-2.5 py-1 rounded bg-slate-900 border border-slate-700 text-slate-200 text-xs font-mono focus:border-amber-500 outline-none"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                        <span>Perfil de Velocidade do Mouse:</span>
                        <span className="text-amber-400 font-mono font-bold">
                          {strategyB.speed === 'fast' ? 'Rápido (~160ms)' : strategyB.speed === 'natural' ? 'Natural (~300ms)' : 'Lento (~650ms)'}
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-1">
                        {(['fast', 'natural', 'slow'] as const).map(spd => (
                          <button
                            key={spd}
                            type="button"
                            onClick={() => setStrategyB(prev => ({ ...prev, speed: spd }))}
                            className={`py-1.5 px-2 rounded border text-center text-[10px] font-mono font-semibold transition-colors ${
                              strategyB.speed === spd
                                ? 'bg-amber-950 border-amber-500 text-amber-200 font-bold'
                                : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
                            }`}
                          >
                            {spd === 'fast' ? 'Rápido' : spd === 'natural' ? 'Natural' : 'Lento'}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-2 pt-1">
                      <div>
                        <div className="flex justify-between text-[11px] font-mono text-slate-400 mb-1">
                          <span>Atraso Mínimo de Reação:</span>
                          <span className="text-amber-400 font-bold">{strategyB.delayMinMs} ms</span>
                        </div>
                        <input
                          type="range"
                          min="50"
                          max="800"
                          step="25"
                          value={strategyB.delayMinMs}
                          onChange={e => {
                            const val = Number(e.target.value);
                            setStrategyB(prev => ({
                              ...prev,
                              delayMinMs: val,
                              delayMaxMs: Math.max(val + 50, prev.delayMaxMs)
                            }));
                          }}
                          className="w-full accent-amber-500 cursor-pointer"
                        />
                      </div>

                      <div>
                        <div className="flex justify-between text-[11px] font-mono text-slate-400 mb-1">
                          <span>Atraso Máximo de Reação:</span>
                          <span className="text-amber-400 font-bold">{strategyB.delayMaxMs} ms</span>
                        </div>
                        <input
                          type="range"
                          min="150"
                          max="2000"
                          step="50"
                          value={strategyB.delayMaxMs}
                          onChange={e => {
                            const val = Number(e.target.value);
                            setStrategyB(prev => ({
                              ...prev,
                              delayMaxMs: val,
                              delayMinMs: Math.min(val - 50, prev.delayMinMs)
                            }));
                          }}
                          className="w-full accent-amber-500 cursor-pointer"
                        />
                      </div>
                    </div>

                    <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                      <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                        <input
                          type="checkbox"
                          checked={strategyB.applyJitter}
                          onChange={e => setStrategyB(prev => ({ ...prev, applyJitter: e.target.checked }))}
                          className="w-3.5 h-3.5 rounded accent-amber-500"
                        />
                        <span>Jitter Gaussiano (±3-5 px)</span>
                      </label>
                      <span className="text-[10px] text-amber-400/90 font-mono">
                        ~{Math.round((strategyB.delayMinMs + strategyB.delayMaxMs)/2 + (strategyB.speed === 'fast' ? 225 : strategyB.speed === 'natural' ? 395 : 780))}ms estimada
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Buttons: Alternating Single Click & Batch Automation */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <div className="flex flex-wrap items-center gap-2.5">
                  <button
                    type="button"
                    onClick={() => simulateClick()}
                    disabled={isSimulatingClick || isAbBatchRunning || !selectedCard.eligible}
                    className="px-4 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center gap-2 shadow-md transition-all active:scale-95"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>
                      {isSimulatingClick
                        ? 'Executando Disparo...'
                        : abTestEnabled
                        ? `Disparar Clique Alternado (Agora: Variante ${nextAbVariant})`
                        : `Disparar Clique em ${selectedCard.name_label}`}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => runAbBatch(10)}
                    disabled={isSimulatingClick || isAbBatchRunning || !selectedCard.eligible}
                    className="px-3.5 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700 text-slate-200 font-semibold text-xs flex items-center gap-2 transition-all active:scale-95 shadow"
                    title="Executa 10 cliques automáticos alternando estritamente 5x Variante A e 5x Variante B com registro instantâneo no CSV"
                  >
                    <Activity className={`w-3.5 h-3.5 text-cyan-400 ${isAbBatchRunning ? 'animate-spin' : ''}`} />
                    <span>{isAbBatchRunning ? `Executando Bateria (${abBatchProgress.current}/${abBatchProgress.total})...` : 'Executar Bateria A/B (10 Cliques Alternados)'}</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => runAbBatch(20)}
                    disabled={isSimulatingClick || isAbBatchRunning || !selectedCard.eligible}
                    className="px-3 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700 text-slate-300 font-medium text-xs hidden sm:flex items-center gap-1.5 transition-colors"
                  >
                    <span>20 Cliques</span>
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  {abLogs.length > 0 && (
                    <button
                      type="button"
                      onClick={() => downloadAuditCsv(abLogs, 'TESTE_AB')}
                      className="px-3 py-2 rounded-lg bg-cyan-950 hover:bg-cyan-900 border border-cyan-700 text-cyan-300 text-xs font-semibold flex items-center gap-1.5 transition-colors shadow"
                      title="Baixar apenas as linhas de auditoria registradas pelo teste A/B para análise no Excel"
                    >
                      <Download className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Baixar CSV A/B ({abLogs.length})</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Bateria Progress Bar */}
              {isAbBatchRunning && (
                <div className="mt-4 p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2 animate-in fade-in duration-200">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-cyan-400 font-bold flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5 animate-spin" />
                      Progresso da Bateria A/B: {abBatchProgress.current} de {abBatchProgress.total} disparos
                    </span>
                    <span className="text-slate-400 text-[11px]">
                      Alternando A ⇄ B em tempo real
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-emerald-500 via-cyan-400 to-amber-500 transition-all duration-300"
                      style={{ width: `${(abBatchProgress.current / abBatchProgress.total) * 100}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Real-time A/B Comparative Analytics Dashboard */}
              <div className="mt-5 pt-4 border-t border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-xs text-slate-200 flex items-center gap-1.5 uppercase tracking-wide">
                    <Sliders className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Métricas Comparativas Registradas no CSV (Tempo Real)</span>
                  </h4>
                  <span className="text-[10px] font-mono text-slate-500">
                    Amostra auditada: {abLogs.length} execuções no arquivo diário
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/90 space-y-1">
                    <span className="text-slate-400 text-[10px] uppercase font-mono block">Volume Auditado</span>
                    <div className="flex items-baseline justify-between pt-0.5">
                      <div className="text-xs font-bold text-emerald-400">A: {statsA.count} runs</div>
                      <div className="text-xs font-bold text-amber-400">B: {statsB.count} runs</div>
                    </div>
                    <span className="text-[10px] text-slate-500 block pt-0.5">
                      Equilíbrio amostral: {statsA.count + statsB.count > 0 ? (statsA.count === statsB.count ? '1:1 Perfeito' : `${Math.round((statsA.count/(statsA.count+statsB.count || 1))*100)}% / ${Math.round((statsB.count/(statsA.count+statsB.count || 1))*100)}%`) : '-'}
                    </span>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/90 space-y-1">
                    <span className="text-slate-400 text-[10px] uppercase font-mono block">Latência Média Total</span>
                    <div className="flex items-baseline justify-between pt-0.5">
                      <div className="text-xs font-bold text-emerald-400">{statsA.avg ? `${statsA.avg} ms` : '-'}</div>
                      <div className="text-xs font-bold text-amber-400">{statsB.avg ? `${statsB.avg} ms` : '-'}</div>
                    </div>
                    <span className="text-[10px] text-cyan-400 block pt-0.5">
                      {statsA.avg && statsB.avg
                        ? statsA.avg > statsB.avg
                          ? `B é ${(statsA.avg - statsB.avg)}ms mais veloz`
                          : `A é ${(statsB.avg - statsA.avg)}ms mais veloz`
                        : 'Aguardando cliques'}
                    </span>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/90 space-y-1">
                    <span className="text-slate-400 text-[10px] uppercase font-mono block">Entropia / Desvio Padrão</span>
                    <div className="flex items-baseline justify-between pt-0.5">
                      <div className="text-xs font-bold text-emerald-400">±{statsA.stdDev || 0} ms</div>
                      <div className="text-xs font-bold text-amber-400">±{statsB.stdDev || 0} ms</div>
                    </div>
                    <span className="text-[10px] text-slate-500 block pt-0.5">
                      Dispersão anti-assinatura temporal
                    </span>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/90 space-y-1">
                    <span className="text-slate-400 text-[10px] uppercase font-mono block">Faixa Real de Execução</span>
                    <div className="flex items-baseline justify-between pt-0.5">
                      <div className="text-[11px] font-mono text-emerald-400">{statsA.min || 0}..{statsA.max || 0}ms</div>
                      <div className="text-[11px] font-mono text-amber-400">{statsB.min || 0}..{statsB.max || 0}ms</div>
                    </div>
                    <span className="text-[10px] text-slate-500 block pt-0.5">
                      Amplitude registrada em disco
                    </span>
                  </div>
                </div>

                {/* Analytical Verdict */}
                <div className="p-3 rounded-lg bg-slate-950/90 border border-slate-800 text-[11px] text-slate-300 leading-relaxed flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <strong className="text-slate-100 block mb-0.5 font-sans">
                      Diagnóstico Analítico do Teste A/B:
                    </strong>
                    <span>
                      {statsA.count > 0 && statsB.count > 0 ? (
                        <>
                          A <strong className="text-emerald-400">{strategyA.name}</strong> confere maior entropia temporal com latência média de <strong className="text-emerald-300">{statsA.avg}ms</strong>, ideal para proteção contra heurísticas de detecção contínua. Em contrapartida, a <strong className="text-amber-400">{strategyB.name}</strong> reduz a latência para <strong className="text-amber-300">{statsB.avg}ms</strong> ({Math.abs(statsA.avg - statsB.avg)}ms a menos), oferecendo agilidade superior em disputas de vagas no lobby. Todos os registros constam no arquivo CSV de auditoria diária.
                        </>
                      ) : (
                        <>
                          Dispare cliques individuais ou execute uma bateria automatizada para consolidar dados estatísticos no arquivo CSV diário.
                        </>
                      )}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Window Simulator and Interactive Coordinates Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-6 bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-5">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Move className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-base font-bold text-slate-50">
                    Simulador de Janela Móvel do PPPoker (PyGetWindow)
                  </h3>
                </div>
                <span className="text-xs px-2 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 font-mono">
                  DPI-Aware
                </span>
              </div>

              <p className="text-xs text-slate-400 leading-relaxed">
                Altere os controles deslizantes abaixo para simular o que acontece quando você move ou redimensiona a janela do PPPoker no monitor. O algoritmo calcula a coordenada absoluta exata de clique em tempo real e valida a integridade da janela:
              </p>

              <div className="space-y-4 text-xs">
                <div>
                  <div className="flex justify-between text-slate-300 font-mono mb-1">
                    <span>Posição Horizontal (win.left):</span>
                    <span className="font-bold text-emerald-400">{winLeft} px</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="2500"
                    step="50"
                    value={winLeft}
                    onChange={e => setWinLeft(Number(e.target.value))}
                    className="w-full accent-emerald-500 cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-slate-300 font-mono mb-1">
                    <span>Posição Vertical (win.top):</span>
                    <span className="font-bold text-emerald-400">{winTop} px</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1000"
                    step="25"
                    value={winTop}
                    onChange={e => setWinTop(Number(e.target.value))}
                    className="w-full accent-emerald-500 cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-slate-300 font-mono mb-1">
                    <span>Largura da Janela (win.width):</span>
                    <span className="font-bold text-cyan-400">{winWidth} px (escala: {scaleX.toFixed(2)}x)</span>
                  </div>
                  <input
                    type="range"
                    min="400"
                    max="1600"
                    step="20"
                    value={winWidth}
                    onChange={e => setWinWidth(Number(e.target.value))}
                    className="w-full accent-cyan-500 cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-slate-300 font-mono mb-1">
                    <span>Altura da Janela (win.height):</span>
                    <span className="font-bold text-cyan-400">{winHeight} px (escala: {scaleY.toFixed(2)}x)</span>
                  </div>
                  <input
                    type="range"
                    min="700"
                    max="2400"
                    step="30"
                    value={winHeight}
                    onChange={e => setWinHeight(Number(e.target.value))}
                    className="w-full accent-cyan-500 cursor-pointer"
                  />
                </div>
              </div>

              {/* Click Speed Profile Selector */}
              <div className="pt-3 border-t border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-300 font-semibold text-xs flex items-center gap-1.5">
                    <Gauge className="w-4 h-4 text-emerald-400" />
                    <span>Velocidade do Clique (Perfil PyAutoGUI):</span>
                  </span>
                  <span className="text-[11px] font-mono text-emerald-300">
                    {clickSpeed === 'fast' ? '160ms (Rápido)' : clickSpeed === 'natural' ? '300ms (Natural)' : '650ms (Lento)'}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setClickSpeed('fast')}
                    className={`p-2.5 rounded-lg border text-left transition-all ${
                      clickSpeed === 'fast'
                        ? 'bg-amber-950/60 border-amber-500 text-amber-200 ring-1 ring-amber-500/40 shadow'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-1 font-bold text-xs">
                      <Zap className="w-3.5 h-3.5 text-amber-400" />
                      <span>Rápido</span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-0.5">~160ms curso</p>
                    <span className="text-[9px] font-mono text-amber-400/90 block">Disputado / Hyper</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setClickSpeed('natural')}
                    className={`p-2.5 rounded-lg border text-left transition-all ${
                      clickSpeed === 'natural'
                        ? 'bg-emerald-950/60 border-emerald-500 text-emerald-200 ring-1 ring-emerald-500/40 shadow'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-1 font-bold text-xs">
                      <MousePointerClick className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Natural</span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-0.5">~300ms curso</p>
                    <span className="text-[9px] font-mono text-emerald-400/90 block">Recomendado</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setClickSpeed('slow')}
                    className={`p-2.5 rounded-lg border text-left transition-all ${
                      clickSpeed === 'slow'
                        ? 'bg-cyan-950/60 border-cyan-500 text-cyan-200 ring-1 ring-cyan-500/40 shadow'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-1 font-bold text-xs">
                      <Clock className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Lento</span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-0.5">~650ms curso</p>
                    <span className="text-[9px] font-mono text-cyan-400/90 block">Ultra-Humano</span>
                  </button>
                </div>
              </div>

              {/* Random Camouflage Reaction Delay Controls */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={randomDelayEnabled}
                      onChange={e => setRandomDelayEnabled(e.target.checked)}
                      className="w-4 h-4 rounded accent-emerald-500"
                    />
                    <span className="font-semibold text-xs text-slate-200 flex items-center gap-1.5">
                      <Shuffle className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Atraso Aleatório de Camuflagem (Anti-Detecção)</span>
                    </span>
                  </label>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                    randomDelayEnabled
                      ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                      : 'bg-slate-900 text-slate-500 border-slate-800'
                  }`}>
                    {randomDelayEnabled ? `${delayMinMs}ms a ${delayMaxMs}ms` : 'DESATIVADO'}
                  </span>
                </div>

                <p className="text-[11px] text-slate-400 leading-snug">
                  Insere um intervalo fisiológico aleatório entre a detecção do torneio elegível no lobby e o início do movimento do mouse, eliminando assinaturas temporais robóticas.
                </p>

                {randomDelayEnabled && (
                  <div className="space-y-3 pt-1">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <div className="flex justify-between text-[11px] font-mono text-slate-400 mb-1">
                          <span>Atraso Mínimo:</span>
                          <span className="text-emerald-400 font-bold">{delayMinMs} ms</span>
                        </div>
                        <input
                          type="range"
                          min="50"
                          max="800"
                          step="25"
                          value={delayMinMs}
                          onChange={e => {
                            const val = Number(e.target.value);
                            setDelayMinMs(val);
                            if (val > delayMaxMs) setDelayMaxMs(val + 50);
                          }}
                          className="w-full accent-emerald-500 cursor-pointer"
                        />
                      </div>
                      <div>
                        <div className="flex justify-between text-[11px] font-mono text-slate-400 mb-1">
                          <span>Atraso Máximo:</span>
                          <span className="text-emerald-400 font-bold">{delayMaxMs} ms</span>
                        </div>
                        <input
                          type="range"
                          min="150"
                          max="2000"
                          step="50"
                          value={delayMaxMs}
                          onChange={e => {
                            const val = Number(e.target.value);
                            setDelayMaxMs(val);
                            if (val < delayMinMs) setDelayMinMs(val - 50);
                          }}
                          className="w-full accent-emerald-500 cursor-pointer"
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-[10px] text-slate-500 font-sans">Presets:</span>
                      <button
                        type="button"
                        onClick={() => { setDelayMinMs(200); setDelayMaxMs(450); }}
                        className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-300"
                      >
                        Competitivo (200-450ms)
                      </button>
                      <button
                        type="button"
                        onClick={() => { setDelayMinMs(350); setDelayMaxMs(850); }}
                        className="px-2 py-0.5 rounded bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-700 text-[10px] font-mono text-emerald-300"
                      >
                        Humano Natural (350-850ms)
                      </button>
                      <button
                        type="button"
                        onClick={() => { setDelayMinMs(700); setDelayMaxMs(1500); }}
                        className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-300"
                      >
                        Ultra Furtivo (700-1500ms)
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
                <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                  <input
                    type="checkbox"
                    checked={applyJitter}
                    onChange={e => setApplyJitter(e.target.checked)}
                    className="w-4 h-4 rounded accent-emerald-500"
                  />
                  <span>Dispersão Gaussiana Anti-Bot (Jitter de ±3 a ±5 px)</span>
                </label>
                <span className="text-[11px] text-slate-500 font-mono">σ_x = 3.0, σ_y = 2.0</span>
              </div>

              {/* Real-time Click Execution Phase Progress */}
              {isSimulatingClick && (
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2 animate-in fade-in duration-150">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-emerald-400 font-bold flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5 animate-spin" />
                      Disparo em Andamento ({clickPhase})
                    </span>
                    <span className="text-[10px] text-slate-400">
                      Sessão: {sessionName || 'Sessão Principal'}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5 text-center text-[10px] font-mono">
                    <div className={`p-1.5 rounded border transition-colors ${
                      clickPhase === 'DELAY'
                        ? 'bg-amber-950 text-amber-200 border-amber-600 animate-pulse font-bold'
                        : clickPhase === 'MOVING' || clickPhase === 'CLICKING' || clickPhase === 'DONE'
                        ? 'bg-slate-900 text-slate-400 border-slate-800'
                        : 'bg-slate-950 text-slate-600 border-slate-900'
                    }`}>
                      1. Atraso Camuflagem
                    </div>
                    <div className={`p-1.5 rounded border transition-colors ${
                      clickPhase === 'MOVING'
                        ? 'bg-emerald-950 text-emerald-200 border-emerald-600 animate-pulse font-bold'
                        : clickPhase === 'CLICKING' || clickPhase === 'DONE'
                        ? 'bg-slate-900 text-slate-400 border-slate-800'
                        : 'bg-slate-950 text-slate-600 border-slate-900'
                    }`}>
                      2. Movimento Bézier
                    </div>
                    <div className={`p-1.5 rounded border transition-colors ${
                      clickPhase === 'CLICKING'
                        ? 'bg-cyan-950 text-cyan-200 border-cyan-600 animate-pulse font-bold'
                        : clickPhase === 'DONE'
                        ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                        : 'bg-slate-950 text-slate-600 border-slate-900'
                    }`}>
                      3. Disparo Físico
                    </div>
                  </div>
                </div>
              )}

              {!heartbeatActive && (
                <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-700/80 text-amber-200 text-xs flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-amber-400" />
                    <span>Watchdog em SYSTEM_HALT! Cliques bloqueados por inatividade &gt; 30s.</span>
                  </div>
                  <button
                    onClick={resumeHeartbeat}
                    className="px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-500 text-slate-950 font-bold text-[11px]"
                  >
                    Restabelecer
                  </button>
                </div>
              )}

              <button
                onClick={simulateClick}
                disabled={isSimulatingClick || !selectedCard.eligible}
                className={`w-full py-3 rounded-lg font-bold text-xs flex items-center justify-center gap-2 shadow-lg transition-all ${
                  !heartbeatActive
                    ? 'bg-amber-950 text-amber-300 border border-amber-700 hover:bg-amber-900'
                    : selectedCard.eligible
                    ? 'bg-emerald-500 hover:bg-emerald-400 text-slate-950'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                }`}
              >
                <Play className="w-4 h-4 fill-current" />
                <span>
                  {isSimulatingClick
                    ? `Executando Clique Camuflado (${clickPhase})...`
                    : `Disparar Clique em ${selectedCard.name_label}`}
                </span>
              </button>

              {/* Latency Breakdown Metric Panel */}
              {lastLatencyBreakdown && (
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1.5 font-mono">
                  <div className="flex items-center justify-between text-slate-400 text-[10px] uppercase">
                    <span className="flex items-center gap-1 text-emerald-400 font-bold">
                      <Timer className="w-3 h-3" />
                      Decomposição de Latência do Último Clique:
                    </span>
                    <span className="text-slate-300 font-bold">{lastLatencyBreakdown.totalMs} ms total</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
                    <div className="p-1 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-500 block">Reação / Delay</span>
                      <span className="text-amber-300 font-bold">+{lastLatencyBreakdown.reactionMs}ms</span>
                    </div>
                    <div className="p-1 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-500 block">Movimento</span>
                      <span className="text-emerald-300 font-bold">+{lastLatencyBreakdown.moveMs}ms</span>
                    </div>
                    <div className="p-1 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-500 block">Pressão</span>
                      <span className="text-cyan-300 font-bold">+{lastLatencyBreakdown.pressMs}ms</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Trajetória Bézier Cúbica e Cinemática Humana (pyautogui.moveTo) */}
              {lastTrajectory && (
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1.5 font-mono">
                  <div className="flex items-center justify-between text-[10px] uppercase">
                    <span className="flex items-center gap-1 text-cyan-400 font-bold">
                      <Zap className="w-3 h-3" />
                      Cinemática Fisiológica (pyautogui.moveTo):
                    </span>
                    <span className="text-emerald-300 font-bold">Bézier Cúbica + Jitter</span>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                    <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-500 block">Distância / Vetor</span>
                      <span className="text-slate-200 font-bold">{lastTrajectory.distance} px (P0 → P3)</span>
                    </div>
                    <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-500 block">Controle Bézier</span>
                      <span className="text-amber-300 font-bold">P1({lastTrajectory.p1.x},{lastTrajectory.p1.y}) P2({lastTrajectory.p2.x},{lastTrajectory.p2.y})</span>
                    </div>
                    <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-500 block">Curva Aceleração</span>
                      <span className="text-emerald-300 font-bold">Balística (35%) + Inercial</span>
                    </div>
                    <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-500 block">Micro-Jitter Neuromuscular</span>
                      <span className="text-cyan-300 font-bold">±{lastTrajectory.jitterPx}px (Sem padrão fixo)</span>
                    </div>
                  </div>
                </div>
              )}

              {clickLog && (
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[11px] text-emerald-300">
                  {clickLog}
                </div>
              )}
            </div>

            <div className="lg:col-span-6 space-y-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-5 h-5 text-amber-400" />
                    <h3 className="text-base font-bold text-slate-50">
                      Tradução de Coordenadas em Tempo Real
                    </h3>
                  </div>
                  <span className="text-xs font-mono text-slate-400">
                    Alvo: #{selectedCard.index} ({selectedCard.name_label})
                  </span>
                </div>

                <div className="space-y-3 text-xs">
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                    <span className="text-slate-400 uppercase text-[10px] font-mono block">
                      Passo 1: Coordenada Local no Cartão (Módulo 2)
                    </span>
                    <p className="font-mono text-emerald-300 font-bold text-sm">
                      click_point_local = ({selectedCard.click_point_local[0]}, {selectedCard.click_point_local[1]})
                    </p>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                    <span className="text-slate-400 uppercase text-[10px] font-mono block">
                      Passo 2: Fatores de Escala da Janela
                    </span>
                    <p className="font-mono text-cyan-300">
                      scale_x = {winWidth} / 787 = {scaleX.toFixed(4)}x
                      <br />
                      scale_y = {winHeight} / 1470 = {scaleY.toFixed(4)}x
                    </p>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                    <span className="text-slate-400 uppercase text-[10px] font-mono block">
                      Passo 3: Posição Absoluta de Tela (Desktop do Windows)
                    </span>
                    <p className="font-mono text-amber-300 font-bold text-sm">
                      X_desktop = {winLeft} + ({selectedCard.click_point_local[0]} × {scaleX.toFixed(2)}) = {absX} px
                      <br />
                      Y_desktop = {winTop} + ({selectedCard.click_point_local[1]} × {scaleY.toFixed(2)}) = {absY} px
                    </p>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800 space-y-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-300 block">
                    Parâmetros Fisiológicos do Mouse (PyAutoGUI)
                  </span>

                  <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                    <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block text-[10px]">Trajetória</span>
                      <span className="text-emerald-300">Bézier Cúbica + Jitter</span>
                    </div>
                    <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block text-[10px]">Aceleração Motora</span>
                      <span className="text-emerald-300">Fisiológica (Fitts / Balística)</span>
                    </div>
                    <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block text-[10px]">Duração Deslocamento</span>
                      <span className="text-emerald-300">0.26s a 0.36s (Variável)</span>
                    </div>
                    <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block text-[10px]">Pressão Mecânica</span>
                      <span className="text-emerald-300">75ms a 115ms (Humana)</span>
                    </div>
                    <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block text-[10px]">Anti-Detecção</span>
                      <span className="text-emerald-300">Zero Velocidade Constante</span>
                    </div>
                    <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block text-[10px]">Fail-Safe Ativo</span>
                      <span className="text-emerald-300">Canto da Tela Aborta</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

        {/* Tab 3: OCR Results (Module 3) */}
        {activeTab === 'ocr' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <span className="text-[11px] font-mono text-slate-400 uppercase">Cartões Processados</span>
                <p className="text-2xl font-black text-slate-100 mt-1">5 Cartões</p>
                <span className="text-[11px] text-slate-500">Recortes do lobby real</span>
              </div>
              <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-800/60">
                <span className="text-[11px] font-mono text-emerald-300 uppercase font-semibold">Torneios Elegíveis</span>
                <p className="text-2xl font-black text-emerald-400 mt-1">1 Torneio</p>
                <span className="text-[11px] text-emerald-400/80">Corujão Hyper PKO (Buy-in 50)</span>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <span className="text-[11px] font-mono text-slate-400 uppercase">Teto de Buy-in Atual</span>
                <p className="text-2xl font-black text-slate-100 mt-1">≤ 50 Fichas</p>
                <span className="text-[11px] text-slate-500">Regra de orçamento estrita</span>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <span className="text-[11px] font-mono text-slate-400 uppercase">Motor de Inferência</span>
                <p className="text-2xl font-black text-cyan-400 mt-1">RapidOCR</p>
                <span className="text-[11px] text-slate-500">ONNX CPU local (&lt; 40ms)</span>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-7 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                    Extração por Cartão & Filtro de Elegibilidade
                  </h3>
                  <span className="text-xs text-slate-400">Clique para inspecionar</span>
                </div>

                <div className="space-y-2.5">
                  {TOURNAMENTS_DATA.map(t => {
                    const isSelected = selectedCard.index === t.index;
                    return (
                      <div
                        key={t.index}
                        onClick={() => setSelectedCard(t)}
                        className={`p-4 rounded-xl border cursor-pointer transition-all duration-150 ${
                          isSelected
                            ? 'bg-slate-900 border-emerald-500/80 shadow-lg ring-1 ring-emerald-500/30'
                            : 'bg-slate-900/50 border-slate-800 hover:border-slate-700 hover:bg-slate-900'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-300">
                                #{t.index}
                              </span>
                              <h4 className="font-bold text-sm text-slate-100">{t.name_read}</h4>
                              <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                                {t.game_format}
                              </span>
                            </div>

                            <div className="flex items-center gap-4 text-xs text-slate-400 font-mono pt-1">
                              <span className="flex items-center gap-1">
                                <Coins className="w-3.5 h-3.5 text-amber-400" />
                                {t.buyin ? `Buy-in: ${t.buyin}` : 'Sem Buy-in'}
                              </span>
                              <span className="flex items-center gap-1">
                                <Clock className="w-3.5 h-3.5 text-cyan-400" />
                                {t.start_time || 'Horário: N/A'}
                              </span>
                            </div>
                          </div>

                          <div>
                            {t.eligible ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                ELEGÍVEL (≤ 50)
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold bg-rose-950/60 text-rose-300 border border-rose-900/80">
                                <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                                INELEGÍVEL
                              </span>
                            )}
                          </div>
                        </div>

                        {!t.eligible && t.rejection_reasons.length > 0 && (
                          <div className="mt-2.5 pt-2 border-t border-slate-800/60 flex items-center gap-2 text-[11px] text-rose-400">
                            <span className="font-semibold">Motivo de rejeição:</span>
                            <span className="font-mono bg-rose-950/40 px-2 py-0.5 rounded border border-rose-900/40">
                              {t.rejection_reasons.join(', ')}
                            </span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="lg:col-span-5 space-y-4">
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
                  <div className="flex items-start justify-between border-b border-slate-800 pb-3">
                    <div>
                      <span className="text-[10px] font-mono uppercase text-emerald-400 font-bold">
                        Auditoria de OCR do Cartão #{selectedCard.index}
                      </span>
                      <h3 className="text-base font-bold text-slate-50">{selectedCard.name_label}</h3>
                    </div>
                    {selectedCard.eligible ? (
                      <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                        Aprovado para Registro
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
                        Bloqueado
                      </span>
                    )}
                  </div>

                  <div className="p-2 rounded-lg bg-slate-950 border border-slate-800">
                    <p className="text-[10px] font-mono text-slate-400 uppercase mb-1">
                      Recorte de entrada: {selectedCard.crop_file}
                    </p>
                    <img
                      src={`/modulo2_evidencias/${selectedCard.crop_file}`}
                      alt={selectedCard.name_label}
                      className="w-full rounded border border-slate-800 max-h-24 object-contain"
                    />
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-400">1. Nome Reconhecido:</span>
                      <span className="font-bold text-slate-100">{selectedCard.name_read}</span>
                    </div>

                    <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-400">2. Custo do Buy-in:</span>
                      <span className={`font-bold font-mono ${selectedCard.buyin ? 'text-amber-300' : 'text-slate-500'}`}>
                        {selectedCard.buyin ? `${selectedCard.buyin} fichas` : 'Não informado / N/A'}
                      </span>
                    </div>

                    <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-400">3. Início Previsto:</span>
                      <span className="font-mono text-cyan-300 font-medium">
                        {selectedCard.start_time || 'Nenhum horário'}
                      </span>
                    </div>

                    <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800">
                      <span className="text-slate-400">4. Ponto Central de Clique:</span>
                      <span className="font-mono text-emerald-400 font-bold flex items-center gap-1">
                        <MousePointerClick className="w-3.5 h-3.5" />
                        ({selectedCard.click_point_local[0]}, {selectedCard.click_point_local[1]})
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Visual Inspection (Module 2) */}
        {activeTab === 'visual' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-xs">
                <div className="flex items-center gap-2 text-slate-300 font-medium">
                  <Crosshair className="w-4 h-4 text-emerald-400" />
                  <span>annotated.png (Segmentação de Cartões e Miras)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setZoomLevel(prev => Math.max(0.7, prev - 0.15))}
                    className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                  >
                    <ZoomOut className="w-3.5 h-3.5" />
                  </button>
                  <span className="text-[11px] text-slate-400 font-mono w-12 text-center">
                    {Math.round(zoomLevel * 100)}%
                  </span>
                  <button
                    onClick={() => setZoomLevel(prev => Math.min(1.8, prev + 0.15))}
                    className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                  >
                    <ZoomIn className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => setZoomLevel(1)}
                    className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 ml-1"
                  >
                    <Maximize2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <div className="relative border border-slate-800/80 rounded-lg overflow-auto max-h-[640px] bg-slate-950 flex justify-center p-2">
                <div
                  className="relative transition-transform duration-150 origin-top"
                  style={{ transform: `scale(${zoomLevel})` }}
                >
                  <img
                    src="/modulo2_evidencias/annotated.png"
                    alt="Lobby Anotado"
                    className="rounded shadow-2xl block max-w-none"
                    style={{ width: '394px', height: '735px' }}
                  />

                  {TOURNAMENTS_DATA.map(card => {
                    const isSelected = selectedCard.index === card.index;
                    const left = card.local_box[0] * 0.5;
                    const top = card.local_box[1] * 0.5;
                    const width = card.local_box[2] * 0.5;
                    const height = card.local_box[3] * 0.5;

                    return (
                      <div
                        key={card.index}
                        onClick={() => setSelectedCard(card)}
                        className={`absolute cursor-pointer transition-all duration-150 ${
                          isSelected
                            ? 'ring-2 ring-emerald-400 bg-emerald-500/15 shadow-lg'
                            : 'hover:bg-emerald-500/10'
                        }`}
                        style={{
                          left: `${left}px`,
                          top: `${top}px`,
                          width: `${width}px`,
                          height: `${height}px`,
                        }}
                      >
                        <div className="absolute top-1 left-1 px-1 py-0.5 rounded text-[9px] font-bold bg-slate-950/80 text-emerald-300 border border-emerald-500/40">
                          #{card.index} {card.name_label.split(' ')[0]}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="lg:col-span-5 flex flex-col space-y-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                      Cartão #{selectedCard.index} Selecionado
                    </span>
                    <h3 className="text-lg font-bold text-slate-50">{selectedCard.name_label}</h3>
                  </div>
                  <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Completo
                  </span>
                </div>

                <div className="border border-slate-800 rounded-lg overflow-hidden bg-slate-950 p-2">
                  <p className="text-[10px] text-slate-400 uppercase font-mono mb-1.5">
                    Recorte isolado: {selectedCard.crop_file}
                  </p>
                  <img
                    src={`/modulo2_evidencias/${selectedCard.crop_file}`}
                    alt={selectedCard.name_label}
                    className="w-full rounded border border-slate-800 object-contain max-h-24"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800">
                    <span className="text-slate-400 block text-[10px] uppercase font-mono">
                      Bounding Box [X, Y, W, H]
                    </span>
                    <span className="font-mono text-emerald-300 font-bold">
                      [{selectedCard.local_box.join(', ')}]
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800">
                    <span className="text-slate-400 block text-[10px] uppercase font-mono">
                      Ponto de Clique Central
                    </span>
                    <span className="font-mono text-amber-300 font-bold flex items-center gap-1">
                      <MousePointerClick className="w-3.5 h-3.5" />
                      ({selectedCard.click_point_local[0]}, {selectedCard.click_point_local[1]})
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 5: Windows Guide */}
        {activeTab === 'guide' && (
          <div className="space-y-6">
            {/* SEÇÃO: PASSO A PASSO DE INSTALAÇÃO NO WINDOWS & AMBIENTE VIRTUAL */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6 shadow-xl">
              {/* Header com Status do Ambiente Virtual */}
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
                <div>
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400">
                      <Wrench className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                        <span>Passo a Passo de Instalação & Ambiente Virtual</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
                          Windows 10/11
                        </span>
                      </h3>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Verificação da presença dos pacotes Python no ambiente virtual isolado (.venv) e auto-reparo com instalação silenciosa.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <div className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 font-mono text-xs flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <span className="text-slate-400">Ambiente:</span>
                    <span className="text-emerald-300 font-bold">.venv\Scripts\python.exe</span>
                  </div>
                  <div className={`px-3 py-1.5 rounded-lg font-mono text-xs font-bold border flex items-center gap-1.5 ${
                    installationPackages.every(p => p.installed)
                      ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800'
                      : 'bg-amber-950/60 text-amber-300 border-amber-800 animate-pulse'
                  }`}>
                    {installationPackages.filter(p => p.installed).length} / {installationPackages.length} Pacotes Prontos
                  </div>
                </div>
              </div>

              {/* Status Banner Inteligente */}
              {installationPackages.some(p => !p.installed) ? (
                <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-600/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold text-amber-200 block text-sm mb-0.5">
                        Pacotes Python Ausentes no Ambiente Virtual
                      </span>
                      <p className="text-amber-300/90 leading-relaxed">
                        Detectamos que dependências obrigatórias como <code className="bg-amber-950/80 px-1 py-0.5 rounded font-mono text-amber-200">pyautogui</code>, <code className="bg-amber-950/80 px-1 py-0.5 rounded font-mono text-amber-200">pygetwindow</code> ou <code className="bg-amber-950/80 px-1 py-0.5 rounded font-mono text-amber-200">pillow</code> não estão disponíveis no terminal. Sem elas, o bot não consegue movimentar o mouse nem ler o PPPoker.
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={handleFixInstallation}
                    disabled={isFixingInstallation}
                    className="shrink-0 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 shadow-md transition-all active:scale-95"
                  >
                    <Wrench className={`w-4 h-4 ${isFixingInstallation ? 'animate-spin' : ''}`} />
                    <span>{isFixingInstallation ? 'Corrigindo...' : 'Corrigir Agora (1 Clique)'}</span>
                  </button>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-700/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                    <div>
                      <span className="font-bold text-emerald-200 block text-sm mb-0.5">
                        Ambiente Virtual 100% Configurado e Validado!
                      </span>
                      <span className="text-emerald-300/90">
                        Todos os pacotes Python de automação, visão computacional e OCR estão instalados e prontos para operar mesas reais.
                      </span>
                    </div>
                  </div>
                  <span className="px-3 py-1.5 rounded-lg bg-emerald-900/40 border border-emerald-700 text-emerald-300 font-mono text-xs font-bold text-center">
                    ✓ PRONTO PARA JOGO
                  </span>
                </div>
              )}

              {/* Roteiro Passo a Passo de Instalação (4 Etapas Numeradas) */}
              <div className="space-y-3">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400 font-mono block">
                  Etapas do Roteiro de Instalação no Windows
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-black text-emerald-400">ETAPA 1</span>
                      <span className="text-[10px] text-slate-500 font-mono">Download</span>
                    </div>
                    <strong className="text-slate-200 text-xs block">Descompactar o ZIP</strong>
                    <p className="text-[11px] text-slate-400 leading-normal">
                      Extraia o arquivo completo mantendo a subpasta <code className="text-emerald-300">repo_visualpilot</code> e os scripts <code className="text-emerald-300">.bat/.cmd</code> na raiz.
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-black text-emerald-400">ETAPA 2</span>
                      <span className="text-[10px] text-slate-500 font-mono">Isolamento</span>
                    </div>
                    <strong className="text-slate-200 text-xs block">Criar Ambiente Virtual</strong>
                    <p className="text-[11px] text-slate-400 leading-normal">
                      Executa <code className="text-emerald-300">python -m venv .venv</code> para isolar as bibliotecas do Windows sem poluir o Python global.
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-950 border border-emerald-800/60 bg-emerald-950/10 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-black text-amber-400">ETAPA 3</span>
                      <span className="text-[10px] text-amber-400 font-mono font-bold">Auto-Reparo</span>
                    </div>
                    <strong className="text-slate-100 text-xs block">Instalação Silenciosa</strong>
                    <p className="text-[11px] text-slate-300 leading-normal">
                      Clique em <strong>Corrigir Instalação</strong> para instalar todas as 5 dependências sem prompts ou janelas travando.
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-black text-cyan-400">ETAPA 4</span>
                      <span className="text-[10px] text-slate-500 font-mono">Execução</span>
                    </div>
                    <strong className="text-slate-200 text-xs block">Abrir Central com Opções</strong>
                    <p className="text-[11px] text-slate-400 leading-normal">
                      Execute <code className="text-cyan-300">MENU_INICIAR.bat</code> para escolher entre diagnóstico, bot de mesa ou orquestrador.
                    </p>
                  </div>
                </div>
              </div>

              {/* Tabela de Verificação dos Pacotes Python no Ambiente Virtual */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-emerald-400" />
                    <span>Verificação dos Pacotes Python no Ambiente Virtual (.venv)</span>
                  </span>
                  <span className="text-[11px] text-slate-500">
                    Clique em um cartão para simular status ou teste
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {installationPackages.map(pkg => (
                    <div
                      key={pkg.id}
                      onClick={() => handleTogglePackage(pkg.id)}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer select-none ${
                        pkg.installed
                          ? 'bg-slate-950 border-emerald-900/60 hover:border-emerald-700'
                          : 'bg-rose-950/20 border-rose-900/70 hover:border-rose-600'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${pkg.installed ? 'bg-emerald-400' : 'bg-rose-400 animate-pulse'}`} />
                          <span className="font-bold text-slate-100 text-xs font-mono">{pkg.name}</span>
                          <span className="text-[10px] text-slate-500 font-mono">{pkg.version}</span>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold flex items-center gap-1 ${
                          pkg.installed
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : 'bg-rose-950 text-rose-300 border border-rose-800'
                        }`}>
                          {pkg.installed ? <CheckCircle2 className="w-3 h-3 text-emerald-400" /> : <AlertOctagon className="w-3 h-3 text-rose-400" />}
                          {pkg.installed ? 'INSTALADO' : 'AUSENTE'}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                        {pkg.description}
                      </p>
                      <div className="mt-2.5 pt-2 border-t border-slate-900 flex items-center justify-between text-[10px] font-mono text-slate-500">
                        <span>pip: <code>{pkg.pipPackage}</code></span>
                        <span className="text-slate-400 hover:text-slate-200">Alternar teste</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Botões de Ação: Corrigir Instalação, Copiar Comando e Menu */}
              <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-slate-800">
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={handleFixInstallation}
                    disabled={isFixingInstallation}
                    className="px-5 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center gap-2.5 shadow-lg shadow-emerald-500/20 active:scale-95 transition-all"
                    title="Dispara a instalação real: baixa o script .bat para execução no Windows e copia o comando para a área de transferência"
                  >
                    <Wrench className={`w-4 h-4 ${isFixingInstallation ? 'animate-spin' : ''}`} />
                    <span>{isFixingInstallation ? 'Executando Instalação...' : 'Corrigir Instalação'}</span>
                  </button>

                  <a
                    href="/corrigir_instalacao.bat"
                    download="corrigir_instalacao.bat"
                    className="px-4 py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center gap-2 shadow-md transition-all active:scale-95"
                    title="Baixar arquivo .bat executável que instala e valida todas as dependências diretamente no seu Windows"
                  >
                    <Download className="w-4 h-4 text-slate-950" />
                    <span>Baixar Script de Instalação (.bat)</span>
                  </a>

                  <button
                    onClick={handleCopySilentCommand}
                    className="px-4 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs flex items-center gap-2 border border-slate-700 transition-all active:scale-95"
                  >
                    <Copy className="w-4 h-4 text-slate-400" />
                    <span>{silentCommandCopied ? 'Comando Copiado!' : 'Copiar Comando Pip (CMD)'}</span>
                  </button>

                  <button
                    onClick={() => {
                      runPreflightCheck();
                      addToast({
                        title: "DIAGNÓSTICO INICIADO",
                        message: "Executando checagem pré-voo completa (check_init)...",
                        eventType: "PREFLIGHT_CHECK",
                        severity: "INFO"
                      });
                    }}
                    className="px-4 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 font-semibold text-xs flex items-center gap-2 border border-slate-700 transition-all active:scale-95"
                  >
                    <Play className="w-4 h-4 text-cyan-400 fill-current" />
                    <span>Executar Diagnóstico (check_init)</span>
                  </button>
                </div>

                <div className="text-[11px] text-slate-400 font-mono">
                  Opção interativa via terminal: <code className="text-amber-300 font-bold">MENU_INICIAR.bat</code>
                </div>
              </div>

              {/* Terminal de Instalação Silenciosa em Tempo Real */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                  <span className="flex items-center gap-1.5 text-slate-300">
                    <Terminal className="w-4 h-4 text-emerald-400" />
                    <span>Console de Execução Silenciosa (.venv\Scripts\python.exe -m pip install --quiet)</span>
                  </span>
                  <span className="text-[10px] text-slate-500">
                    Status: {isFixingInstallation ? 'Instalando em segundo plano...' : 'Aguardando comando'}
                  </span>
                </div>
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 space-y-1 max-h-48 overflow-y-auto">
                  {installationLogs.map((log, index) => (
                    <div
                      key={index}
                      className={
                        log.startsWith('✓') || log.includes('[OK]')
                          ? 'text-emerald-400 font-bold'
                          : log.startsWith('>')
                          ? 'text-cyan-300'
                          : log.startsWith('#')
                          ? 'text-slate-500'
                          : log.startsWith('=')
                          ? 'text-slate-600'
                          : 'text-slate-300'
                      }
                    >
                      {log}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <Terminal className="w-5 h-5 text-emerald-400" />
                <span>Como Executar o Módulo 4 no seu PC Windows</span>
              </h3>

              <ol className="space-y-3 text-xs text-slate-300">
                <li className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex gap-3">
                  <span className="font-bold text-emerald-400 font-mono text-sm">1</span>
                  <div>
                    <strong className="text-slate-100 block mb-0.5">Baixar e Extrair o Pacote</strong>
                    <span>
                      Baixe o arquivo <code>VisualPilot_Modulo4_AutomacaoCliques.zip</code> pelo botão acima e extraia em uma pasta (ex: <code>C:\VisualPilot_Modulo4</code>).
                    </span>
                  </div>
                </li>

                <li className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex gap-3">
                  <span className="font-bold text-emerald-400 font-mono text-sm">2</span>
                  <div>
                    <strong className="text-slate-100 block mb-0.5">Executar Preparar (Uma única vez)</strong>
                    <span>
                      Dê duplo clique em <code>preparar.cmd</code> para instalar <code>pyautogui</code> e <code>pygetwindow</code> no ambiente virtual local.
                    </span>
                  </div>
                </li>

                <li className="p-3 rounded-lg bg-slate-950 border border-emerald-900/60 flex gap-3 shadow-md">
                  <span className="font-bold text-emerald-300 font-mono text-sm">2.5</span>
                  <div>
                    <strong className="text-emerald-300 block mb-0.5 flex items-center gap-1.5">
                      <CheckSquare className="w-4 h-4" />
                      <span>Verificação Prévia do Ambiente (check_init.cmd)</span>
                    </strong>
                    <span>
                      Antes de disparar qualquer clique, execute o script de diagnóstico para checar Python, integridade das dependências e criar o arquivo CSV diário com cabeçalho de 14 colunas:
                      <pre className="mt-1.5 p-2 rounded bg-slate-900 border border-slate-700 text-emerald-300 font-mono text-[11px]">
                        check_init.cmd
                      </pre>
                      Flags úteis: <code>check_init.cmd --require-window</code> (interrompe se o PPPoker estiver fechado) ou <code>check_init.cmd --json</code>.
                    </span>
                  </div>
                </li>

                <li className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex gap-3">
                  <span className="font-bold text-emerald-400 font-mono text-sm">3</span>
                  <div>
                    <strong className="text-slate-100 block mb-0.5">Testar em Modo Simulação (Dry-Run)</strong>
                    <span>
                      Sem mover o mouse, teste se a janela é localizada e as coordenadas calculadas:
                      <pre className="mt-1.5 p-2 rounded bg-slate-900 border border-slate-700 text-emerald-300 font-mono text-[11px]">
                        clicar_torneio.cmd ..\lobby_ocr\diagnostico_ocr\tournaments.json --dry-run
                      </pre>
                    </span>
                  </div>
                </li>

                <li className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex gap-3">
                  <span className="font-bold text-emerald-400 font-mono text-sm">4</span>
                  <div>
                    <strong className="text-slate-100 block mb-0.5">Disparar o Clique Real com Auditoria CSV</strong>
                    <span>
                      Com a janela do PPPoker aberta na tela, execute sem flag:
                      <pre className="mt-1.5 p-2 rounded bg-slate-900 border border-slate-700 text-emerald-300 font-mono text-[11px]">
                        clicar_torneio.cmd ..\lobby_ocr\diagnostico_ocr\tournaments.json
                      </pre>
                      O arquivo <code>logs\clicks_audit_YYYY-MM-DD.csv</code> será gravado e atualizado instantaneamente!
                    </span>
                  </div>
                </li>

                <li className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex gap-3">
                  <span className="font-bold text-fuchsia-400 font-mono text-sm">5</span>
                  <div>
                    <strong className="text-slate-100 block mb-0.5">Configurar Alerta Remoto (Discord / Telegram / E-mail)</strong>
                    <span>
                      Para receber alertas no celular caso o bot congele por &gt; 5 minutos:
                      <pre className="mt-1.5 p-2 rounded bg-slate-900 border border-slate-700 text-fuchsia-300 font-mono text-[11px]">
                        clicar_torneio.cmd --tournaments tournaments.json --webhook-url "https://discord.com/api/webhooks/..."
                      </pre>
                      Para testar a conexão imediatamente antes de operar:
                      <pre className="mt-1.5 p-2 rounded bg-slate-900 border border-slate-700 text-fuchsia-300 font-mono text-[11px]">
                        clicar_torneio.cmd --test-webhook --webhook-url "https://discord.com/api/webhooks/..."
                      </pre>
                    </span>
                  </div>
                </li>
              </ol>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <span>Critérios de Segurança & Auditoria do Módulo 4</span>
              </h3>

              <div className="space-y-2.5 text-xs">
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <strong>Auditoria Persistente em CSV:</strong> Cada tentativa de clique registra data/hora ISO, torneio, coordenadas, dimensões e status no arquivo diário com flush imediato.
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <strong>Watchdog de Heartbeat (30s):</strong> Interrompe ações e grava <code>SYSTEM_HALT</code> no CSV se a pulsação do software não for detectada a cada 30 segundos.
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-fuchsia-400 shrink-0 mt-0.5" />
                  <span>
                    <strong>Escalada Remota Automática (&gt; 5 min):</strong> Se o <code>SYSTEM_HALT</code> persistir por mais de 5 minutos, despacha notificação emergencial via Webhook (Discord / Telegram / E-mail).
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <strong>Guardião de Integridade da Janela:</strong> Se o PPPoker for fechado ou minimizado, o clique é abortado e gravado como <code>WINDOW_CLOSED</code>.
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <strong>Proteção contra Deformação:</strong> Se a janela for esticada fora da proporção ($W/H \notin [0.35, 0.85]$) ou sofrer variação drástica de área, cancela e grava <code>RESOLUTION_CHANGED</code>.
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <strong>Dispersão Gaussiana (Jitter):</strong> Aplica micro-variação de 3 a 5px no alvo para proteger a conta contra telemetria de detecção de bots.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
        </main>
      </div>

      {/* Modal: Central de Download & Executável (1-Clique) */}
      {showInstallerModal && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 md:p-6 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl max-w-5xl w-full p-4 sm:p-6 shadow-2xl max-h-[92vh] overflow-y-auto">
            <InstallerDownloadCenter isModal onClose={() => setShowInstallerModal(false)} />
          </div>
        </div>
      )}

      {/* Pre-Flight Frame Fullscreen Modal */}
      {preflightFullscreenPreview && (
        <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex flex-col p-4 md:p-6 animate-in fade-in duration-200">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <Camera className="w-5 h-5 text-emerald-400" />
              <div>
                <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <span>Inspeção em Alta Definição: Frame PPPoker (check_init)</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
                    787 × 1470 px (Retrato 9:16.8)
                  </span>
                </h3>
                <span className="text-xs text-slate-400 font-mono">
                  Capturado em: {preflightFrameCapturedAt} • Score: {preflightCalibScore}% Calibrado
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={recapturePreflightFrame}
                disabled={isRecapturingFrame}
                className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRecapturingFrame ? 'animate-spin' : ''}`} />
                <span>Recapturar</span>
              </button>
              <button
                type="button"
                onClick={() => setPreflightFullscreenPreview(false)}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200"
                title="Fechar inspeção"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          <div className="flex-1 flex items-center justify-center p-2 overflow-auto relative">
            <div className="relative rounded-xl overflow-hidden border-2 border-emerald-500/80 shadow-2xl bg-black max-h-[85vh] select-none">
              <img
                src={preflightFrameUrl}
                alt="Inspeção do Frame PPPoker em Alta Resolução"
                className="max-h-[85vh] w-auto object-contain block"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = '/modulo2_evidencias/annotated.png';
                }}
              />

              {/* Crosshair Overlays */}
              {showCalibrationCrosshairs && (
                <div className="absolute inset-0 pointer-events-none">
                  <div className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center" style={{ left: '7.1%', top: '5.4%' }}>
                    <div className="w-6 h-6 rounded-full border-2 border-cyan-400 bg-cyan-500/30 flex items-center justify-center">
                      <div className="w-1.5 h-1.5 rounded-full bg-cyan-300" />
                    </div>
                    <span className="absolute left-7 top-0 px-1.5 py-0.5 rounded bg-black/90 text-[10px] font-mono text-cyan-300 whitespace-nowrap border border-cyan-600">
                      Seta Voltar [56, 80]
                    </span>
                  </div>

                  <div className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center" style={{ left: '50.0%', top: '15.6%' }}>
                    <div className="w-6 h-6 rounded-full border-2 border-white bg-white/30 flex items-center justify-center">
                      <div className="w-1.5 h-1.5 rounded-full bg-white" />
                    </div>
                    <span className="absolute left-7 top-0 px-1.5 py-0.5 rounded bg-black/90 text-[10px] font-mono text-white whitespace-nowrap border border-slate-700">
                      Barra de Filtro [393, 230]
                    </span>
                  </div>

                  <div className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center" style={{ left: '51.3%', top: '67.5%' }}>
                    <div className="absolute w-10 h-10 rounded-full border-2 border-emerald-400 animate-ping opacity-75" />
                    <div className="w-7 h-7 rounded-full border-2 border-emerald-400 bg-emerald-500/40 flex items-center justify-center shadow-lg shadow-emerald-500/50">
                      <Crosshair className="w-4 h-4 text-emerald-200" />
                    </div>
                    <span className="absolute left-9 top-0 px-2 py-1 rounded bg-emerald-950/95 text-xs font-mono font-bold text-emerald-300 whitespace-nowrap border border-emerald-500 shadow-xl">
                      Alvo Corujão [404, 992] (Clique Primário)
                    </span>
                  </div>

                  <div className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center" style={{ left: '50.0%', top: '95.0%' }}>
                    <div className="w-6 h-6 rounded-full border-2 border-amber-400 bg-amber-500/30 flex items-center justify-center">
                      <div className="w-1.5 h-1.5 rounded-full bg-amber-300" />
                    </div>
                    <span className="absolute right-7 top-0 px-1.5 py-0.5 rounded bg-black/90 text-[10px] font-mono text-amber-300 whitespace-nowrap border border-amber-600">
                      Botão Registrar [393, 1396]
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Footer com Hotkey Overlay Centralizado */}
      <footer className="border-t border-slate-800/80 bg-slate-900/50 px-6 py-3 text-xs text-slate-400 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span>VisualPilot · Automação Distribuída para PPPoker (Fichas Fictícias)</span>
          <span className="hidden sm:inline text-slate-600">|</span>
          <span className="text-slate-500 hidden sm:inline">Repositório: eduardodinizti-design/VisualPilot</span>
        </div>

        {/* Hotkey Overlay */}
        <div className="flex items-center gap-4">
          <HotkeyOverlay
            isSessionActive={isSessionActive}
            isHumanTakeover={isHumanTakeover}
            currentArea={mainSection}
            onToggleSession={handleToggleBotSession}
            onToggleTakeover={handleToggleHumanTakeover}
            onNavigateArea={(area, subTab) => navigateToTab(subTab || area, area)}
          />
          <span className="text-emerald-400 font-medium hidden md:inline">Módulos 2, 3 e 4 Auditados</span>
        </div>
      </footer>
    </div>
  );
}
