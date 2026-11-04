import React, { useState, useEffect } from 'react';
import {
  Layers,
  Maximize2,
  Minimize2,
  RefreshCw,
  SlidersHorizontal,
  Volume2,
  VolumeX,
  Play,
  Pause,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Coins,
  Cpu,
  Monitor,
  Eye,
  Filter,
  Flame,
  Plus,
  Trash2,
  Download,
  Copy,
  Check,
  Zap,
  Target,
  Crosshair,
  Activity,
  Radio,
  TrendingUp,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { LiveDesktopMonitor } from './LiveDesktopMonitor';

export interface PokerCard {
  rank: string; // 'A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'
  suit: 's' | 'h' | 'd' | 'c'; // spades, hearts, diamonds, clubs (4-color: black, red, blue, green)
}

export interface PlayerSeat {
  seatNumber: number;
  playerName: string;
  chipsBb: number;
  isHero: boolean;
  isFolded: boolean;
  currentBetBb?: number;
  cards?: PokerCard[];
}

export interface TableItem {
  id: string;
  tableNumber: number;
  title: string;
  gameType: 'NLH' | 'PLO4' | 'PLO5' | 'MTT';
  blinds: string;
  hwnd: number;
  pid: number;
  monitorIndex: number;
  dpiScale: number; // 1.0, 1.25, 1.5, 2.0
  dpiValue: number; // 96, 120, 144, 192
  boxPhysical: [number, number, number, number]; // [x, y, w, h]
  boxLogical: [number, number, number, number];
  aspectRatio: number;
  status: 'HERO_TURN' | 'WAITING_ACTION' | 'ACTIVE_OBSERVING' | 'DISCONNECTED';
  heroSeat: number;
  heroPosition: 'BTN' | 'SB' | 'BB' | 'UTG' | 'MP' | 'CO';
  dealerSeat: number;
  activePlayersCount: number;
  maxPlayers: number;
  potBb: number;
  currentRound: 'PREFLOP' | 'FLOP' | 'TURN' | 'RIVER' | 'SHOWDOWN';
  boardCards: PokerCard[];
  heroCards: PokerCard[];
  seats: PlayerSeat[];
  timeBankSec: number;
  lastCaptureTime: string;
}

export interface PokerActivityEvent {
  id: string;
  timestamp: string;
  tableNumber: number;
  tableTitle: string;
  type: 'FOLD' | 'RAISE' | 'POT_AWARDED' | 'CALL' | 'ALL_IN' | 'CHECK';
  playerName: string;
  isHero: boolean;
  amountBb?: number;
  description: string;
  ocrConfidence: number;
}

const INITIAL_ACTIVITY_EVENTS: PokerActivityEvent[] = [
  {
    id: 'evt-1',
    timestamp: '12:41:02',
    tableNumber: 1,
    tableTitle: 'Mesa 1 (Diamante)',
    type: 'RAISE',
    playerName: 'Shark_Pro (CO)',
    isHero: false,
    amountBb: 6.0,
    description: 'Raise para 6.0 BB no Flop',
    ocrConfidence: 99.4
  },
  {
    id: 'evt-2',
    timestamp: '12:41:00',
    tableNumber: 3,
    tableTitle: 'Mesa 3 (Esmeralda)',
    type: 'POT_AWARDED',
    playerName: 'Hero (BTN)',
    isHero: true,
    amountBb: 48.5,
    description: 'Pot Awarded: Hero puxou 48.5 BB com Flush de A♠',
    ocrConfidence: 98.7
  },
  {
    id: 'evt-3',
    timestamp: '12:40:57',
    tableNumber: 2,
    tableTitle: 'Mesa 2 (Rubi)',
    type: 'FOLD',
    playerName: 'Fish_88 (UTG)',
    isHero: false,
    description: 'Player Folded pré-flop contra 3-bet',
    ocrConfidence: 99.8
  },
  {
    id: 'evt-4',
    timestamp: '12:40:54',
    tableNumber: 4,
    tableTitle: 'Mesa 4 (Safira)',
    type: 'ALL_IN',
    playerName: 'AggroDonkey (SB)',
    isHero: false,
    amountBb: 62.0,
    description: 'All-In Shove de 62.0 BB no Turn!',
    ocrConfidence: 99.1
  },
  {
    id: 'evt-5',
    timestamp: '12:40:50',
    tableNumber: 1,
    tableTitle: 'Mesa 1 (Diamante)',
    type: 'CALL',
    playerName: 'Hero (BTN)',
    isHero: true,
    amountBb: 2.0,
    description: 'Call 2.0 BB no Bordo A♠ K♥ 8♦',
    ocrConfidence: 99.6
  }
];

const INITIAL_TABLES: TableItem[] = [
  {
    id: 'tbl-1',
    tableNumber: 1,
    title: 'PPPoker - NLH 6-Max Blinds 1/2 (Mesa Diamante)',
    gameType: 'NLH',
    blinds: '1/2',
    hwnd: 101234,
    pid: 8420,
    monitorIndex: 1,
    dpiScale: 1.0,
    dpiValue: 96,
    boxPhysical: [100, 100, 787, 1470],
    boxLogical: [100, 100, 787, 1470],
    aspectRatio: 0.5354,
    status: 'HERO_TURN',
    heroSeat: 1,
    heroPosition: 'BTN',
    dealerSeat: 1,
    activePlayersCount: 6,
    maxPlayers: 6,
    potBb: 38.5,
    currentRound: 'FLOP',
    boardCards: [
      { rank: 'A', suit: 's' },
      { rank: 'K', suit: 'h' },
      { rank: '8', suit: 'd' }
    ],
    heroCards: [
      { rank: 'A', suit: 'h' },
      { rank: 'Q', suit: 's' }
    ],
    seats: [
      { seatNumber: 1, playerName: 'Hero (Você)', chipsBb: 145.0, isHero: true, isFolded: false, currentBetBb: 6.0 },
      { seatNumber: 2, playerName: 'SharkBR_01', chipsBb: 98.5, isHero: false, isFolded: false, currentBetBb: 2.0 },
      { seatNumber: 3, playerName: 'FishCaller', chipsBb: 62.0, isHero: false, isFolded: false, currentBetBb: 6.0 },
      { seatNumber: 4, playerName: 'ProAggro', chipsBb: 180.2, isHero: false, isFolded: true },
      { seatNumber: 5, playerName: 'TightSolid', chipsBb: 110.0, isHero: false, isFolded: true },
      { seatNumber: 6, playerName: 'LooseGun', chipsBb: 85.0, isHero: false, isFolded: true }
    ],
    timeBankSec: 12,
    lastCaptureTime: '0.1s atrás'
  },
  {
    id: 'tbl-2',
    tableNumber: 2,
    title: 'PPPoker - PLO4 Blinds 2/4 (High Roller Club)',
    gameType: 'PLO4',
    blinds: '2/4',
    hwnd: 101236,
    pid: 8420,
    monitorIndex: 1,
    dpiScale: 1.25,
    dpiValue: 120,
    boxPhysical: [920, 100, 984, 1838],
    boxLogical: [736, 80, 787, 1470],
    aspectRatio: 0.5354,
    status: 'WAITING_ACTION',
    heroSeat: 3,
    heroPosition: 'CO',
    dealerSeat: 2,
    activePlayersCount: 5,
    maxPlayers: 6,
    potBb: 94.0,
    currentRound: 'TURN',
    boardCards: [
      { rank: 'J', suit: 'c' },
      { rank: 'T', suit: 's' },
      { rank: '9', suit: 'h' },
      { rank: '2', suit: 'd' }
    ],
    heroCards: [
      { rank: 'K', suit: 's' },
      { rank: 'Q', suit: 'h' },
      { rank: 'J', suit: 'd' },
      { rank: 'T', suit: 'c' }
    ],
    seats: [
      { seatNumber: 1, playerName: 'OmahaKing', chipsBb: 240.0, isHero: false, isFolded: false, currentBetBb: 18.0 },
      { seatNumber: 2, playerName: 'ActionJunkie', chipsBb: 135.5, isHero: false, isFolded: false, currentBetBb: 18.0 },
      { seatNumber: 3, playerName: 'Hero (Você)', chipsBb: 215.0, isHero: true, isFolded: false, currentBetBb: 18.0 },
      { seatNumber: 4, playerName: 'VegasGrinder', chipsBb: 75.0, isHero: false, isFolded: true },
      { seatNumber: 5, playerName: 'PotMaster', chipsBb: 160.0, isHero: false, isFolded: false, currentBetBb: 18.0 },
      { seatNumber: 6, playerName: 'Seat Open', chipsBb: 0, isHero: false, isFolded: true }
    ],
    timeBankSec: 0,
    lastCaptureTime: '0.2s atrás'
  },
  {
    id: 'tbl-3',
    tableNumber: 3,
    title: 'PPPoker - MTT Deepstack 50K (Nível 4 - 200/400)',
    gameType: 'MTT',
    blinds: '200/400',
    hwnd: 101238,
    pid: 8420,
    monitorIndex: 2,
    dpiScale: 1.0,
    dpiValue: 96,
    boxPhysical: [100, 1600, 787, 1470],
    boxLogical: [100, 1600, 787, 1470],
    aspectRatio: 0.5354,
    status: 'ACTIVE_OBSERVING',
    heroSeat: 5,
    heroPosition: 'BB',
    dealerSeat: 4,
    activePlayersCount: 8,
    maxPlayers: 9,
    potBb: 12.0,
    currentRound: 'PREFLOP',
    boardCards: [],
    heroCards: [
      { rank: '7', suit: 'c' },
      { rank: '7', suit: 'd' }
    ],
    seats: [
      { seatNumber: 1, playerName: 'ChipLeader', chipsBb: 85.0, isHero: false, isFolded: false },
      { seatNumber: 2, playerName: 'ShortStack', chipsBb: 14.5, isHero: false, isFolded: true },
      { seatNumber: 3, playerName: 'BlindStealer', chipsBb: 42.0, isHero: false, isFolded: false, currentBetBb: 2.5 },
      { seatNumber: 4, playerName: 'RockPlayer', chipsBb: 36.0, isHero: false, isFolded: true },
      { seatNumber: 5, playerName: 'Hero (Você)', chipsBb: 55.0, isHero: true, isFolded: false, currentBetBb: 1.0 },
      { seatNumber: 6, playerName: 'MttWarrior', chipsBb: 29.0, isHero: false, isFolded: true }
    ],
    timeBankSec: 0,
    lastCaptureTime: '0.3s atrás'
  },
  {
    id: 'tbl-4',
    tableNumber: 4,
    title: 'PPPoker - NLH Micro 0.5/1 (Aquecimento Cash)',
    gameType: 'NLH',
    blinds: '0.5/1',
    hwnd: 101240,
    pid: 8420,
    monitorIndex: 2,
    dpiScale: 1.5,
    dpiValue: 144,
    boxPhysical: [920, 1600, 1180, 2205],
    boxLogical: [613, 1066, 787, 1470],
    aspectRatio: 0.5354,
    status: 'WAITING_ACTION',
    heroSeat: 2,
    heroPosition: 'SB',
    dealerSeat: 1,
    activePlayersCount: 6,
    maxPlayers: 6,
    potBb: 14.5,
    currentRound: 'RIVER',
    boardCards: [
      { rank: 'K', suit: 's' },
      { rank: '9', suit: 'c' },
      { rank: '4', suit: 'd' },
      { rank: '2', suit: 'h' },
      { rank: 'A', suit: 'c' }
    ],
    heroCards: [
      { rank: 'A', suit: 'd' },
      { rank: 'K', suit: 'c' }
    ],
    seats: [
      { seatNumber: 1, playerName: 'AggroFish', chipsBb: 94.0, isHero: false, isFolded: false, currentBetBb: 7.0 },
      { seatNumber: 2, playerName: 'Hero (Você)', chipsBb: 122.0, isHero: true, isFolded: false, currentBetBb: 7.0 },
      { seatNumber: 3, playerName: 'Maniac99', chipsBb: 45.0, isHero: false, isFolded: true },
      { seatNumber: 4, playerName: 'SlowRoller', chipsBb: 78.0, isHero: false, isFolded: true },
      { seatNumber: 5, playerName: 'NitPro', chipsBb: 150.0, isHero: false, isFolded: true },
      { seatNumber: 6, playerName: 'Grinder_RJ', chipsBb: 88.0, isHero: false, isFolded: true }
    ],
    timeBankSec: 0,
    lastCaptureTime: '0.1s atrás'
  }
];

interface MultiTableGridProps {
  onNotify?: (title: string, message: string, severity: 'INFO' | 'WARN' | 'CRITICAL') => void;
  onOpenCardInspector?: () => void;
  onOpenHeroActions?: () => void;
  isHumanTakeover?: boolean;
  onToggleTakeover?: () => void;
}

export const MultiTableGrid: React.FC<MultiTableGridProps> = ({
  onNotify,
  onOpenCardInspector,
  onOpenHeroActions,
  isHumanTakeover = false,
  onToggleTakeover
}) => {
  const [tables, setTables] = useState<TableItem[]>(INITIAL_TABLES);
  const [selectedTableId, setSelectedTableId] = useState<string>('tbl-1');
  const [layoutMode, setLayoutMode] = useState<'auto' | '2x2' | '3x2' | 'single' | 'list'>('auto');
  const [feltTheme, setFeltTheme] = useState<'emerald' | 'ocean' | 'carbon'>('emerald');
  const [heroActionOnlyFilter, setHeroActionOnlyFilter] = useState<boolean>(false);
  const [simulatedDpi, setSimulatedDpi] = useState<string>('AUTO');
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [soundOnHeroTurn, setSoundOnHeroTurn] = useState<boolean>(true);
  const [copiedTiling, setCopiedTiling] = useState<boolean>(false);
  const [showTilingModal, setShowTilingModal] = useState<boolean>(false);

  // Live Activity Feed State (Real-time OCR event stream across tables)
  const [activityEvents, setActivityEvents] = useState<PokerActivityEvent[]>(INITIAL_ACTIVITY_EVENTS);
  const [isLiveFeedActive, setIsLiveFeedActive] = useState<boolean>(true);
  const [feedFilter, setFeedFilter] = useState<'ALL' | 'HERO' | 'POTS_SHOVES' | 'FOLDS'>('ALL');
  const [isFeedCollapsed, setIsFeedCollapsed] = useState<boolean>(false);

  // Live Activity Feed Periodic Simulation Effect
  useEffect(() => {
    if (!isLiveFeedActive) return;

    const interval = setInterval(() => {
      const randomTableNum = Math.floor(Math.random() * Math.max(1, tables.length)) + 1;
      const targetTable = tables.find(t => t.tableNumber === randomTableNum) || tables[0];
      const now = new Date();
      const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

      const eventTemplates: {
        type: PokerActivityEvent['type'];
        playerName: string;
        isHero: boolean;
        amountBb?: number;
        description: string;
        ocrConfidence: number;
      }[] = [
        {
          type: 'FOLD',
          playerName: 'Villain_MP',
          isHero: false,
          description: 'Player Folded na street pré-flop',
          ocrConfidence: 99.8
        },
        {
          type: 'RAISE',
          playerName: 'GTO_Shark (CO)',
          isHero: false,
          amountBb: Number((Math.random() * 8 + 2.5).toFixed(1)),
          description: 'Raise para valor no Turn',
          ocrConfidence: 99.3
        },
        {
          type: 'POT_AWARDED',
          playerName: 'Hero (BTN)',
          isHero: true,
          amountBb: Number((Math.random() * 40 + 15).toFixed(1)),
          description: 'Pot Awarded: Hero levou o pote no Showdown!',
          ocrConfidence: 98.9
        },
        {
          type: 'ALL_IN',
          playerName: 'Maniac_SB',
          isHero: false,
          amountBb: Number((Math.random() * 50 + 40).toFixed(1)),
          description: 'All-In Shove enfrentado!',
          ocrConfidence: 99.1
        },
        {
          type: 'CALL',
          playerName: 'CallingStation',
          isHero: false,
          amountBb: Number((Math.random() * 6 + 2).toFixed(1)),
          description: 'Call na continuação da aposta',
          ocrConfidence: 99.5
        },
        {
          type: 'POT_AWARDED',
          playerName: 'Seat 2 (Reg_VIP)',
          isHero: false,
          amountBb: Number((Math.random() * 25 + 10).toFixed(1)),
          description: 'Pot Awarded: Venceu sem contestação',
          ocrConfidence: 99.0
        },
        {
          type: 'RAISE',
          playerName: 'Hero (BTN)',
          isHero: true,
          amountBb: Number((Math.random() * 10 + 3.0).toFixed(1)),
          description: 'Hero executou Raise / 3-Bet isolando oponente',
          ocrConfidence: 99.7
        }
      ];

      const template = eventTemplates[Math.floor(Math.random() * eventTemplates.length)];

      const newEvent: PokerActivityEvent = {
        id: `evt-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        timestamp: timeStr,
        tableNumber: targetTable ? targetTable.tableNumber : randomTableNum,
        tableTitle: targetTable ? targetTable.title.split(' - ')[1] || targetTable.title : `Mesa #${randomTableNum}`,
        type: template.type,
        playerName: template.playerName,
        isHero: template.isHero,
        amountBb: template.amountBb,
        description: template.description,
        ocrConfidence: template.ocrConfidence
      };

      setActivityEvents(prev => [newEvent, ...prev.slice(0, 39)]);
    }, 3200);

    return () => clearInterval(interval);
  }, [isLiveFeedActive, tables]);

  const handleInjectTestEvent = () => {
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    const testEvent: PokerActivityEvent = {
      id: `evt-manual-${Date.now()}`,
      timestamp: timeStr,
      tableNumber: 1,
      tableTitle: 'Mesa 1 (Diamante)',
      type: 'POT_AWARDED',
      playerName: 'Hero (BTN)',
      isHero: true,
      amountBb: 56.5,
      description: 'Pot Awarded: Hero puxou 56.5 BB com Full House!',
      ocrConfidence: 99.9
    };
    setActivityEvents(prev => [testEvent, ...prev.slice(0, 39)]);
    onNotify?.("EVENTO OCR INJETADO", "Pot Awarded de 56.5 BB injetado no feed em tempo real.", "INFO");
  };

  // Countdown timer para mesas que estão no turno do Hero
  useEffect(() => {
    const timer = setInterval(() => {
      setTables(prev =>
        prev.map(t => {
          if (t.status === 'HERO_TURN' && t.timeBankSec > 0) {
            return { ...t, timeBankSec: t.timeBankSec - 1 };
          }
          return t;
        })
      );
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleScanTables = () => {
    setIsScanning(true);
    onNotify?.("VARREDURA MULTI-MESAS", "Consultando janelas nativas do Windows e analisando DPI scaling...", "INFO");

    setTimeout(() => {
      setIsScanning(false);
      setTables(prev =>
        prev.map(t => ({
          ...t,
          lastCaptureTime: 'agora',
          status: t.id === 'tbl-1' ? 'HERO_TURN' : t.status
        }))
      );
      onNotify?.("VARREDURA CONCLUÍDA", `${tables.length} mesas ativas sincronizadas com sucesso. Resoluções e proporção 9:16.8 verificadas.`, "INFO");
    }, 500);
  };

  const handleSimulateHeroAction = (tableId: string, actionName: string) => {
    setTables(prev =>
      prev.map(t => {
        if (t.id === tableId) {
          const newPot = actionName === 'Fold' ? t.potBb : t.potBb + 12.0;
          return {
            ...t,
            status: 'WAITING_ACTION',
            potBb: newPot,
            timeBankSec: 0
          };
        }
        return t;
      })
    );
    onNotify?.("AÇÃO DO HERO EXECUTADA", `Mesa #${tableId.replace('tbl-', '')}: Ação '${actionName}' registrada e despachada.`, "INFO");
  };

  const handleToggleHeroTurnSimulation = (tableId: string) => {
    setTables(prev =>
      prev.map(t => {
        if (t.id === tableId) {
          const nextStatus = t.status === 'HERO_TURN' ? 'WAITING_ACTION' : 'HERO_TURN';
          return {
            ...t,
            status: nextStatus,
            timeBankSec: nextStatus === 'HERO_TURN' ? 15 : 0
          };
        }
        return t;
      })
    );
  };

  const handleAddSimulatedTable = () => {
    if (tables.length >= 6) {
      onNotify?.("LIMITE DE CAPACIDADE", "Capacidade máxima de 6 mesas simultâneas atingida.", "WARN");
      return;
    }
    const nextNum = tables.length + 1;
    const newId = `tbl-${nextNum}`;
    const newTable: TableItem = {
      id: newId,
      tableNumber: nextNum,
      title: `PPPoker - NLH 6-Max [2/5] (Mesa VIP #${nextNum})`,
      gameType: 'NLH',
      blinds: '2/5',
      hwnd: 101240 + nextNum * 2,
      pid: 8420,
      monitorIndex: nextNum > 3 ? 2 : 1,
      dpiScale: 1.0,
      dpiValue: 96,
      boxPhysical: [(nextNum - 1) * 320, 100, 787, 1470],
      boxLogical: [(nextNum - 1) * 320, 100, 787, 1470],
      aspectRatio: 0.5354,
      status: 'WAITING_ACTION',
      heroSeat: 1,
      heroPosition: 'CO',
      dealerSeat: 3,
      activePlayersCount: 6,
      maxPlayers: 6,
      potBb: 18.0,
      currentRound: 'FLOP',
      boardCards: [
        { rank: 'Q', suit: 's' },
        { rank: 'J', suit: 'd' },
        { rank: '3', suit: 'c' }
      ],
      heroCards: [
        { rank: 'A', suit: 's' },
        { rank: 'T', suit: 's' }
      ],
      seats: [
        { seatNumber: 1, playerName: 'Hero (Você)', chipsBb: 150.0, isHero: true, isFolded: false, currentBetBb: 4.0 },
        { seatNumber: 2, playerName: 'ProPlayer', chipsBb: 110.0, isHero: false, isFolded: false, currentBetBb: 4.0 },
        { seatNumber: 3, playerName: 'TightVIP', chipsBb: 90.0, isHero: false, isFolded: false, currentBetBb: 4.0 },
        { seatNumber: 4, playerName: 'Maniac', chipsBb: 220.0, isHero: false, isFolded: true },
        { seatNumber: 5, playerName: 'FishClub', chipsBb: 45.0, isHero: false, isFolded: true },
        { seatNumber: 6, playerName: 'Rock_BR', chipsBb: 130.0, isHero: false, isFolded: true }
      ],
      timeBankSec: 0,
      lastCaptureTime: 'recém-conectada'
    };

    setTables(prev => [...prev, newTable]);
    onNotify?.("NOVA MESA DETECTADA", `Mesa #${nextNum} adicionada ao grid de monitoramento.`, "INFO");
  };

  const handleRemoveTable = (tableId: string) => {
    setTables(prev => prev.filter(t => t.id !== tableId));
    onNotify?.("MESA DESCONECTADA", `Mesa removida do rastreamento ativo.`, "WARN");
  };

  const handleCopyTilingSuggestions = () => {
    const tilingPayload = tables.map((t, idx) => ({
      slot: idx + 1,
      table_id: t.id,
      title: t.title,
      hwnd: t.hwnd,
      target_box: [10 + (idx % 3) * 640, 10 + Math.floor(idx / 3) * 520, 620, 500]
    }));
    navigator.clipboard.writeText(JSON.stringify(tilingPayload, null, 2));
    setCopiedTiling(true);
    setTimeout(() => setCopiedTiling(false), 2000);
    onNotify?.("MOSAICO COPIADO", "Coordenadas de posicionamento copiadas para a área de transferência.", "INFO");
  };

  // Cores do baralho de 4 cores padrão profissional
  const renderCardSuit = (suit: 's' | 'h' | 'd' | 'c') => {
    switch (suit) {
      case 's': // Espadas: Preto
        return <span className="text-slate-900 font-black">♠</span>;
      case 'h': // Copas: Vermelho
        return <span className="text-rose-600 font-black">♥</span>;
      case 'd': // Ouros: Azul
        return <span className="text-blue-500 font-black">♦</span>;
      case 'c': // Paus: Verde
        return <span className="text-emerald-500 font-black">♣</span>;
    }
  };

  const renderCardBadge = (card: PokerCard, isLarge: boolean = false) => {
    return (
      <div
        key={`${card.rank}-${card.suit}`}
        className={`inline-flex items-center justify-center bg-white border border-slate-300 rounded shadow-sm font-mono font-bold leading-none select-none ${
          isLarge ? 'px-2 py-1.5 text-sm gap-1 min-w-[34px] min-h-[46px]' : 'px-1.5 py-1 text-xs gap-0.5 min-w-[26px] min-h-[34px]'
        }`}
      >
        <span className="text-slate-950 font-black">{card.rank}</span>
        {renderCardSuit(card.suit)}
      </div>
    );
  };

  // Filtro de mesas ativas
  const displayedTables = heroActionOnlyFilter
    ? tables.filter(t => t.status === 'HERO_TURN')
    : tables;

  const heroTurnCount = tables.filter(t => t.status === 'HERO_TURN').length;

  const feltThemes = {
    emerald: 'bg-emerald-950/80 border-emerald-800/80 shadow-emerald-950/40',
    ocean: 'bg-cyan-950/80 border-cyan-800/80 shadow-cyan-950/40',
    carbon: 'bg-slate-900/90 border-slate-700/80 shadow-black/50'
  };

  const filteredActivityEvents = activityEvents.filter(evt => {
    if (feedFilter === 'HERO') return evt.isHero;
    if (feedFilter === 'POTS_SHOVES') return evt.type === 'POT_AWARDED' || evt.type === 'ALL_IN';
    if (feedFilter === 'FOLDS') return evt.type === 'FOLD';
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Transmissão Direta da Mesa do Computador via Telemetria */}
      <LiveDesktopMonitor />

      {/* Top Multi-Table Header & Live Controls Strip */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-lg">
        {/* Left: Summary KPIs */}
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-sm text-slate-100">Rastreamento Multi-Mesas</h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-emerald-500 text-slate-950">
                  Fase 2
                </span>
              </div>
              <p className="text-xs text-slate-400">
                {tables.length} de 6 mesas ativas conectadas • DPI Aware v2
              </p>
            </div>
          </div>

          <div className="h-7 w-px bg-slate-800 hidden sm:block" />

          {/* Hero Action Alert Pill */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
            heroTurnCount > 0
              ? 'bg-emerald-950/80 border-emerald-500/80 text-emerald-300 ring-2 ring-emerald-500/30 animate-pulse'
              : 'bg-slate-950 border-slate-800 text-slate-400'
          }`}>
            <Flame className={`w-4 h-4 ${heroTurnCount > 0 ? 'text-emerald-400' : 'text-slate-500'}`} />
            <span>Sua Vez de Agir:</span>
            <span className="font-mono font-bold text-white bg-slate-800 px-1.5 py-0.2 rounded">
              {heroTurnCount} {heroTurnCount === 1 ? 'mesa' : 'mesas'}
            </span>
          </div>

          {/* Bot Pausado • Controle Manual Overlay Badge */}
          {isHumanTakeover && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border bg-amber-500/20 border-amber-500/70 text-amber-300 ring-2 ring-amber-500/40 animate-pulse shadow-lg">
              <Pause className="w-4 h-4 text-amber-400 shrink-0" />
              <div className="flex items-center gap-1.5">
                <span className="font-black text-xs uppercase tracking-wider text-amber-300">BOT PAUSADO</span>
                <span className="text-[10px] font-mono bg-amber-500/30 text-amber-200 px-1.5 py-0.5 rounded font-bold">
                  Operador no Controle
                </span>
              </div>
              {onToggleTakeover && (
                <button
                  onClick={onToggleTakeover}
                  className="ml-1 px-2 py-0.5 bg-amber-500 hover:bg-amber-400 text-slate-950 text-[10px] font-black rounded transition-colors shadow cursor-pointer"
                  title="Retomar controle autônomo do bot"
                >
                  Retomar (F12)
                </button>
              )}
            </div>
          )}
        </div>

        {/* Center / Right: Interactive Layout Switcher & Action Buttons */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Hero Action Filter Toggle */}
          <button
            onClick={() => setHeroActionOnlyFilter(!heroActionOnlyFilter)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all cursor-pointer ${
              heroActionOnlyFilter
                ? 'bg-emerald-500 text-slate-950 border-emerald-400 shadow-md font-bold'
                : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
            }`}
            title="Exibir apenas mesas onde é sua vez de agir (Hero Turn)"
          >
            <Filter className="w-3.5 h-3.5" />
            <span>Apenas Minha Vez</span>
          </button>

          {/* Grid Layout Switcher */}
          <div className="flex items-center p-0.5 rounded-lg bg-slate-950 border border-slate-800">
            <button
              onClick={() => setLayoutMode('auto')}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                layoutMode === 'auto' ? 'bg-slate-800 text-emerald-300 shadow-sm font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Mosaico Adaptativo (Distribui automaticamente as mesas)"
            >
              Mosaico Auto
            </button>
            <button
              onClick={() => setLayoutMode('2x2')}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                layoutMode === '2x2' ? 'bg-slate-800 text-emerald-300 shadow-sm font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Grade Quad (2x2)"
            >
              2x2 Quad
            </button>
            <button
              onClick={() => setLayoutMode('3x2')}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                layoutMode === '3x2' ? 'bg-slate-800 text-emerald-300 shadow-sm font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Grade Completa (3x2, até 6 mesas)"
            >
              3x2 Grid
            </button>
            <button
              onClick={() => setLayoutMode('single')}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                layoutMode === 'single' ? 'bg-slate-800 text-emerald-300 shadow-sm font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Foco Único na Mesa Selecionada"
            >
              Foco Único
            </button>
          </div>

          {/* Add Table Button */}
          <button
            onClick={handleAddSimulatedTable}
            disabled={tables.length >= 6}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            title="Simular conexão de nova mesa de jogo"
          >
            <Plus className="w-3.5 h-3.5 text-emerald-400" />
            <span>Mesa ({tables.length}/6)</span>
          </button>

          {/* Card Recognition / ROI Inspector shortcut */}
          {onOpenCardInspector && (
            <button
              onClick={onOpenCardInspector}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-emerald-300 hover:text-emerald-200 transition-colors cursor-pointer"
              title="Calibrar ROIs de cartas e baralho de 4 cores"
            >
              <Crosshair className="w-3.5 h-3.5 text-emerald-400" />
              <span className="hidden sm:inline">Calibrar ROIs</span>
            </button>
          )}

          {/* Hero Action Simulator shortcut */}
          {onOpenHeroActions && (
            <button
              onClick={onOpenHeroActions}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-amber-300 hover:text-amber-200 transition-colors cursor-pointer"
              title="Simular e calibrar botões de ação do Hero (Fold, Check, Call, Raise)"
            >
              <Flame className="w-3.5 h-3.5 text-amber-400" />
              <span className="hidden sm:inline">Botões de Ação</span>
            </button>
          )}

          {/* Scan Windows Now Button */}
          <button
            onClick={handleScanTables}
            disabled={isScanning}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs shadow-md transition-all cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-slate-950 ${isScanning ? 'animate-spin' : ''}`} />
            <span>{isScanning ? 'Escaneando...' : 'Escanear Mesas'}</span>
          </button>
        </div>
      </div>

      {/* Live Activity Feed (Real-Time OCR Event Stream Across Tables) */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-3 relative overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
          {/* Left: Stream Title & Live Pulse */}
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center">
              <span className={`w-3 h-3 rounded-full ${isLiveFeedActive ? 'bg-emerald-400 animate-ping' : 'bg-slate-600'}`} />
              <span className={`absolute w-2 h-2 rounded-full ${isLiveFeedActive ? 'bg-emerald-500' : 'bg-slate-500'}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="font-bold text-sm text-slate-100 flex items-center gap-1.5">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <span>Feed de Atividades OCR em Tempo Real</span>
                </h4>
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider ${
                  isLiveFeedActive
                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-700 animate-pulse'
                    : 'bg-slate-800 text-slate-400 border border-slate-700'
                }`}>
                  {isLiveFeedActive ? 'AO VIVO' : 'PAUSADO'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Eventos detectados pelas rotinas de OCR em tempo real: 'Player Folded', 'Raise to X', 'Pot Awarded' e Shoves
              </p>
            </div>
          </div>

          {/* Right: Controls & Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Stream Play/Pause Toggle */}
            <button
              onClick={() => setIsLiveFeedActive(!isLiveFeedActive)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all cursor-pointer ${
                isLiveFeedActive
                  ? 'bg-slate-950 border-emerald-600 text-emerald-300 hover:bg-slate-800'
                  : 'bg-emerald-500 text-slate-950 font-bold border-emerald-400 shadow-sm'
              }`}
              title={isLiveFeedActive ? 'Pausar fluxo de eventos OCR' : 'Retomar fluxo em tempo real'}
            >
              {isLiveFeedActive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              <span>{isLiveFeedActive ? 'Pausar' : 'Retomar Feed'}</span>
            </button>

            {/* Manual Inject Event */}
            <button
              onClick={handleInjectTestEvent}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 transition-colors cursor-pointer"
              title="Simular disparo imediato de evento de OCR"
            >
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span>Injetar Evento</span>
            </button>

            {/* Clear Feed */}
            <button
              onClick={() => setActivityEvents([])}
              className="p-1.5 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-rose-400 transition-colors"
              title="Limpar histórico de eventos"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>

            {/* Collapse/Expand */}
            <button
              onClick={() => setIsFeedCollapsed(!isFeedCollapsed)}
              className="p-1.5 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
              title={isFeedCollapsed ? 'Expandir feed' : 'Recolher feed'}
            >
              {isFeedCollapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {!isFeedCollapsed && (
          <>
            {/* Category Filter Chips */}
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px] font-mono text-slate-500 mr-1">Filtrar:</span>
                {(['ALL', 'HERO', 'POTS_SHOVES', 'FOLDS'] as const).map(filterKey => {
                  const count = activityEvents.filter(e => {
                    if (filterKey === 'HERO') return e.isHero;
                    if (filterKey === 'POTS_SHOVES') return e.type === 'POT_AWARDED' || e.type === 'ALL_IN';
                    if (filterKey === 'FOLDS') return e.type === 'FOLD';
                    return true;
                  }).length;
                  const labels: Record<string, string> = {
                    ALL: 'Todos os Eventos',
                    HERO: 'Apenas Hero',
                    POTS_SHOVES: 'Potes & Shoves',
                    FOLDS: 'Player Folded'
                  };
                  return (
                    <button
                      key={filterKey}
                      onClick={() => setFeedFilter(filterKey)}
                      className={`px-2.5 py-1 rounded-lg border text-xs font-mono transition-all cursor-pointer ${
                        feedFilter === filterKey
                          ? 'bg-emerald-950 text-emerald-200 border-emerald-500 font-bold shadow-sm'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                      }`}
                    >
                      {labels[filterKey]} ({count})
                    </button>
                  );
                })}
              </div>

              <div className="text-[11px] font-mono text-slate-500 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span>Buffer: {activityEvents.length}/40 eventos • Ciclo ~3.2s</span>
              </div>
            </div>

            {/* Scrolling Events Stream Container */}
            <div className="max-h-56 overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-slate-700">
              {filteredActivityEvents.length === 0 ? (
                <div className="p-6 text-center text-xs font-mono text-slate-500 bg-slate-950 rounded-xl border border-slate-800">
                  Nenhum evento registrado para o filtro selecionado. Aguardando novas detecções do OCR...
                </div>
              ) : (
                filteredActivityEvents.map(evt => {
                  const isFold = evt.type === 'FOLD';
                  const isPot = evt.type === 'POT_AWARDED';
                  const isRaise = evt.type === 'RAISE';
                  const isAllIn = evt.type === 'ALL_IN';
                  const isCall = evt.type === 'CALL';

                  const badgeStyle =
                    isPot ? 'bg-emerald-950 text-emerald-300 border-emerald-700' :
                    isAllIn ? 'bg-purple-950 text-purple-300 border-purple-700 animate-pulse' :
                    isRaise ? 'bg-amber-950 text-amber-300 border-amber-700' :
                    isFold ? 'bg-rose-950/60 text-rose-300 border-rose-800' :
                    isCall ? 'bg-blue-950 text-blue-300 border-blue-700' :
                    'bg-slate-900 text-slate-300 border-slate-700';

                  return (
                    <div
                      key={evt.id}
                      className={`p-2.5 rounded-xl border flex items-center justify-between gap-3 transition-all ${
                        evt.isHero
                          ? 'bg-emerald-950/20 border-emerald-500/40 shadow-sm'
                          : 'bg-slate-950 border-slate-800/90 hover:border-slate-700'
                      }`}
                    >
                      {/* Left: Time & Table & Action Badge */}
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="text-[11px] font-mono text-slate-500 shrink-0">
                          {evt.timestamp}
                        </span>

                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-900 border border-slate-800 text-slate-300 shrink-0">
                          Mesa #{evt.tableNumber}
                        </span>

                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border shrink-0 ${badgeStyle}`}>
                          {evt.type === 'POT_AWARDED' ? 'POT AWARDED' :
                           evt.type === 'ALL_IN' ? 'ALL-IN SHOVE' :
                           evt.type === 'RAISE' ? 'RAISE TO X' :
                           evt.type === 'FOLD' ? 'PLAYER FOLDED' :
                           evt.type}
                        </span>

                        <div className="truncate text-xs font-mono">
                          <span className={`font-bold mr-1.5 ${evt.isHero ? 'text-amber-300' : 'text-slate-200'}`}>
                            {evt.playerName}:
                          </span>
                          <span className="text-slate-300">
                            {evt.description}
                          </span>
                        </div>
                      </div>

                      {/* Right: Chip Amount & OCR Confidence Badge */}
                      <div className="flex items-center gap-3 shrink-0 font-mono text-xs">
                        {evt.amountBb !== undefined && (
                          <span className={`font-bold px-2 py-0.5 rounded border text-[11px] ${
                            isPot ? 'bg-emerald-950 text-emerald-300 border-emerald-600' :
                            isAllIn ? 'bg-purple-950 text-purple-300 border-purple-600' :
                            'bg-slate-900 text-amber-300 border-slate-700'
                          }`}>
                            {evt.amountBb} BB
                          </span>
                        )}
                        <span className="text-[10px] text-slate-500 hidden sm:inline" title="Confiança do modelo OCR">
                          OCR {evt.ocrConfidence}%
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </>
        )}
      </div>

      {/* Main Multi-Table Viewport */}
      {layoutMode === 'single' ? (
        /* Single Focus View: 1 Large Table with Sidebar of Other Tables */
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Big Selected Table (3 cols) */}
          <div className="lg:col-span-3">
            {(() => {
              const activeTbl = tables.find(t => t.id === selectedTableId) || tables[0];
              if (!activeTbl) return null;
              return (
                <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col">
                  {/* Table Header Strip */}
                  <div className="p-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="w-7 h-7 rounded-lg bg-emerald-500 text-slate-950 font-black text-xs flex items-center justify-center">
                        #{activeTbl.tableNumber}
                      </span>
                      <div>
                        <h4 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                          <span>{activeTbl.title}</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-emerald-400 border border-slate-700">
                            {activeTbl.gameType} {activeTbl.blinds}
                          </span>
                        </h4>
                        <p className="text-xs text-slate-400">
                          HWND: {activeTbl.hwnd} • PID: {activeTbl.pid} • Monitor {activeTbl.monitorIndex} • DPI: {activeTbl.dpiValue} ({activeTbl.dpiScale * 100}%)
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleToggleHeroTurnSimulation(activeTbl.id)}
                        className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-300 transition-colors"
                      >
                        Alternar Turno Hero
                      </button>
                      <button
                        onClick={() => setLayoutMode('auto')}
                        className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 transition-colors"
                        title="Voltar ao Mosaico"
                      >
                        <Minimize2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Table Big Visual Oval Arena */}
                  <div className="p-6 flex-1 flex flex-col items-center justify-center bg-slate-950/60 relative">
                    {/* Bot Pausado • Overlay de Intervenção Manual no Modo Foco */}
                    {isHumanTakeover && (
                      <div className="absolute inset-0 z-30 bg-slate-950/85 backdrop-blur-[2px] flex flex-col items-center justify-center p-6 text-center rounded-2xl border-2 border-amber-500/60 shadow-2xl animate-in fade-in duration-200">
                        <div className="p-3.5 bg-amber-500/20 rounded-full border border-amber-500/50 text-amber-400 mb-3 shadow-lg shadow-amber-500/20">
                          <Pause className="w-8 h-8 animate-pulse" />
                        </div>
                        <span className="font-black text-base tracking-wider uppercase text-amber-300">
                          BOT PAUSADO • OPERADOR NO CONTROLE TOTAL
                        </span>
                        <p className="text-xs text-slate-300 max-w-md mt-1.5 leading-relaxed">
                          Nenhuma ação ou clique de mouse será executado automaticamente pelo bot nesta mesa. Você tem a autonomia completa para clicar e tomar decisões.
                        </p>
                        <div className="mt-3.5 flex items-center gap-2.5">
                          <span className="px-2.5 py-1 rounded-md bg-amber-950/80 border border-amber-700/60 text-amber-200 font-mono text-[11px]">
                            Atalho: F12 ou Alt+P
                          </span>
                          {onToggleTakeover && (
                            <button
                              onClick={onToggleTakeover}
                              className="px-4 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black rounded-lg transition-colors shadow-lg cursor-pointer"
                            >
                              Retomar Ações do Bot
                            </button>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Status Alert Banner */}
                    {activeTbl.status === 'HERO_TURN' && (
                      <div className="w-full max-w-xl mb-4 p-3 rounded-xl bg-emerald-950/90 border border-emerald-500/80 flex items-center justify-between shadow-xl ring-2 ring-emerald-500/40 animate-pulse">
                        <div className="flex items-center gap-2.5">
                          <Flame className="w-5 h-5 text-emerald-400" />
                          <div>
                            <span className="font-black text-xs text-emerald-300 uppercase tracking-wide">
                              SUA VEZ DE AGIR • POSIÇÃO {activeTbl.heroPosition}
                            </span>
                            <p className="text-[11px] text-slate-300">Tempo de reflexão restante no timebank</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-lg font-black text-emerald-400">
                            {activeTbl.timeBankSec}s
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Poker Felt Oval Box */}
                    <div className={`w-full max-w-2xl aspect-[16/10] rounded-[100px] border-4 p-6 flex flex-col justify-between relative shadow-2xl transition-all ${feltThemes[feltTheme]}`}>
                      {/* Top Players Seats */}
                      <div className="flex justify-around items-center z-10">
                        {activeTbl.seats.slice(3, 6).map(seat => (
                          <div
                            key={seat.seatNumber}
                            className={`flex flex-col items-center p-2 rounded-xl border backdrop-blur-sm transition-all ${
                              seat.isHero
                                ? 'bg-emerald-900/80 border-emerald-400 ring-2 ring-emerald-500/50'
                                : seat.isFolded
                                ? 'bg-slate-900/40 border-slate-800 opacity-50'
                                : 'bg-slate-900/80 border-slate-700'
                            }`}
                          >
                            <span className="text-[10px] font-bold text-slate-300">
                              C{seat.seatNumber}: {seat.playerName}
                            </span>
                            <span className="text-xs font-mono font-bold text-amber-300">
                              {seat.chipsBb} BB
                            </span>
                            {seat.currentBetBb && (
                              <span className="text-[10px] font-mono text-cyan-300 mt-0.5">
                                Aposta: {seat.currentBetBb} BB
                              </span>
                            )}
                          </div>
                        ))}
                      </div>

                      {/* Center Board & Pot */}
                      <div className="flex flex-col items-center justify-center gap-2 z-10">
                        {/* Pot Chip Pile */}
                        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-950/80 border border-amber-500/40 text-xs font-mono font-bold text-amber-300 shadow">
                          <Coins className="w-3.5 h-3.5 text-amber-400" />
                          <span>POTE: {activeTbl.potBb.toFixed(1)} BB</span>
                          <span className="text-[10px] text-slate-400">({activeTbl.currentRound})</span>
                        </div>

                        {/* Board Community Cards */}
                        <div className="flex items-center gap-1.5 min-h-[50px] p-2 rounded-xl bg-slate-950/40 border border-slate-800/80">
                          {activeTbl.boardCards.length > 0 ? (
                            activeTbl.boardCards.map(card => renderCardBadge(card, true))
                          ) : (
                            <span className="text-xs text-slate-500 italic px-4">
                              Aguardando Flop...
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Bottom Players Seats & Hero */}
                      <div className="flex justify-around items-center z-10">
                        {activeTbl.seats.slice(0, 3).map(seat => (
                          <div
                            key={seat.seatNumber}
                            className={`flex flex-col items-center p-2.5 rounded-xl border backdrop-blur-sm transition-all ${
                              seat.isHero
                                ? 'bg-emerald-950/90 border-emerald-400 ring-2 ring-emerald-500/60 shadow-lg'
                                : seat.isFolded
                                ? 'bg-slate-900/40 border-slate-800 opacity-50'
                                : 'bg-slate-900/80 border-slate-700'
                            }`}
                          >
                            <div className="flex items-center gap-1.5 mb-1">
                              {activeTbl.dealerSeat === seat.seatNumber && (
                                <span className="w-4 h-4 rounded-full bg-white text-slate-950 font-black text-[9px] flex items-center justify-center shadow">
                                  D
                                </span>
                              )}
                              <span className="text-xs font-bold text-slate-200">
                                {seat.isHero ? '⭐ Hero (Você)' : `C${seat.seatNumber}: ${seat.playerName}`}
                              </span>
                              {seat.isHero && (
                                <span className="px-1.5 py-0.2 rounded text-[10px] font-black bg-emerald-500 text-slate-950">
                                  {activeTbl.heroPosition}
                                </span>
                              )}
                            </div>

                            <span className="text-sm font-mono font-bold text-amber-300">
                              {seat.chipsBb} BB
                            </span>

                            {/* Hero Cards Pocket Showcase */}
                            {seat.isHero && (
                              <div className="flex items-center gap-1 mt-1.5">
                                {activeTbl.heroCards.map(c => renderCardBadge(c, true))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Hero Action Decision Bar */}
                    {activeTbl.status === 'HERO_TURN' && (
                      <div className="mt-6 flex items-center gap-3">
                        <button
                          onClick={() => handleSimulateHeroAction(activeTbl.id, 'Fold')}
                          className="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-xs font-bold text-rose-300 transition-all shadow"
                        >
                          Fold (Desistir)
                        </button>
                        <button
                          onClick={() => handleSimulateHeroAction(activeTbl.id, 'Check/Call')}
                          className="px-6 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-slate-950 text-xs font-black transition-all shadow-lg"
                        >
                          Check / Pagar (6.0 BB)
                        </button>
                        <button
                          onClick={() => handleSimulateHeroAction(activeTbl.id, 'Raise')}
                          className="px-6 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black transition-all shadow-lg"
                        >
                          Apostar / Raise (18.5 BB)
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })()}
          </div>

          {/* Sidebar: Table Thumbnails (1 col) */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              Outras Mesas Conectadas ({tables.length - 1})
            </h4>
            {tables.map(t => (
              <div
                key={t.id}
                onClick={() => setSelectedTableId(t.id)}
                className={`p-3 rounded-xl border transition-all cursor-pointer ${
                  selectedTableId === t.id
                    ? 'bg-slate-800/90 border-emerald-500 ring-2 ring-emerald-500/30'
                    : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded bg-slate-800 text-slate-200 font-bold text-[10px] flex items-center justify-center">
                      #{t.tableNumber}
                    </span>
                    <span className="text-xs font-bold text-slate-200 truncate max-w-[140px]">
                      {t.title}
                    </span>
                  </div>
                  <span className={`px-1.5 py-0.2 rounded text-[9px] font-black uppercase ${
                    t.status === 'HERO_TURN'
                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-700 animate-pulse'
                      : 'bg-slate-800 text-slate-400'
                  }`}>
                    {t.status === 'HERO_TURN' ? 'AGIR' : 'OK'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                  <span>{t.gameType} {t.blinds}</span>
                  <span className="text-amber-300 font-bold">{t.potBb} BB</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* Mosaic / Grid Views (Auto, 2x2, 3x2) */
        <div className={`grid gap-4 ${
          layoutMode === '2x2'
            ? 'grid-cols-1 md:grid-cols-2'
            : layoutMode === '3x2'
            ? 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3'
            : displayedTables.length <= 2
            ? 'grid-cols-1 md:grid-cols-2'
            : displayedTables.length <= 4
            ? 'grid-cols-1 md:grid-cols-2'
            : 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3'
        }`}>
          {displayedTables.map(tbl => (
            <div
              key={tbl.id}
              className={`rounded-2xl border transition-all overflow-hidden flex flex-col shadow-xl ${
                tbl.status === 'HERO_TURN'
                  ? 'bg-slate-900 border-emerald-500/90 ring-2 ring-emerald-500/40 shadow-emerald-950/30'
                  : 'bg-slate-900/90 border-slate-800 hover:border-slate-700'
              }`}
            >
              {/* Card Header Strip */}
              <div className="p-3 bg-slate-950/90 border-b border-slate-800/80 flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`w-6 h-6 rounded-lg font-black text-xs flex items-center justify-center shrink-0 ${
                    tbl.status === 'HERO_TURN'
                      ? 'bg-emerald-500 text-slate-950 shadow-sm'
                      : 'bg-slate-800 text-slate-300'
                  }`}>
                    #{tbl.tableNumber}
                  </span>
                  <div className="min-w-0">
                    <h4 className="font-bold text-xs text-slate-100 truncate" title={tbl.title}>
                      {tbl.title}
                    </h4>
                    <div className="flex items-center gap-1.5 text-[10px] text-slate-400 font-mono">
                      <span>{tbl.gameType}</span>
                      <span>•</span>
                      <span>Blinds {tbl.blinds}</span>
                      <span>•</span>
                      <span>DPI {tbl.dpiScale * 100}%</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => {
                      setSelectedTableId(tbl.id);
                      setLayoutMode('single');
                    }}
                    className="p-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                    title="Focar nesta mesa em tela expandida"
                  >
                    <Maximize2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleRemoveTable(tbl.id)}
                    className="p-1 rounded-md bg-slate-800 hover:bg-rose-950/60 text-slate-400 hover:text-rose-300 transition-colors"
                    title="Remover mesa"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Status Indicator Bar */}
              <div className={`px-3 py-1.5 border-b text-xs flex items-center justify-between font-mono ${
                tbl.status === 'HERO_TURN'
                  ? 'bg-emerald-950/70 border-emerald-800/60 text-emerald-300 font-bold'
                  : 'bg-slate-950/50 border-slate-800/60 text-slate-400'
              }`}>
                <div className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-full ${
                    tbl.status === 'HERO_TURN' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'
                  }`} />
                  <span className="text-[11px]">
                    {tbl.status === 'HERO_TURN' ? 'SUA VEZ DE AGIR' : 'AGUARDANDO AÇÃO'}
                  </span>
                </div>
                {tbl.status === 'HERO_TURN' && (
                  <span className="text-[10px] font-black bg-emerald-500 text-slate-950 px-1.5 py-0.2 rounded">
                    {tbl.timeBankSec}s restantes
                  </span>
                )}
              </div>

              {/* Mini Poker Arena Oval */}
              <div className="p-4 flex-1 flex flex-col justify-between bg-slate-950/40 relative">
                {/* Bot Pausado • Card Overlay */}
                {isHumanTakeover && (
                  <div className="absolute inset-0 z-20 bg-slate-950/85 backdrop-blur-[2px] rounded-lg border-2 border-amber-500/60 flex flex-col items-center justify-center p-3 text-center transition-all animate-in fade-in duration-150">
                    <div className="p-2 rounded-full bg-amber-500/20 border border-amber-500/50 text-amber-400 mb-1.5 shadow-md shadow-amber-500/20">
                      <Pause className="w-5 h-5 animate-pulse" />
                    </div>
                    <span className="text-[11px] font-black uppercase tracking-wider text-amber-300">
                      BOT PAUSADO
                    </span>
                    <span className="text-[10px] text-slate-200 font-medium mt-0.5">
                      Controle Manual do Operador
                    </span>
                    <span className="text-[9px] text-amber-400/90 mt-0.5 font-mono">
                      Cliques Automáticos Bloqueados
                    </span>
                    {onToggleTakeover && (
                      <button
                        onClick={onToggleTakeover}
                        className="mt-2 px-2.5 py-1 bg-amber-500 hover:bg-amber-400 text-slate-950 text-[10px] font-black rounded transition-colors shadow cursor-pointer"
                        title="Retomar controle do bot nesta mesa"
                      >
                        Retomar (F12)
                      </button>
                    )}
                  </div>
                )}

                {/* Felt Canvas */}
                <div className={`w-full aspect-[16/9] rounded-[48px] border-2 p-3 flex flex-col justify-between relative shadow-inner ${feltThemes[feltTheme]}`}>
                  {/* Top Opponents */}
                  <div className="flex justify-around items-center text-[10px] z-10">
                    {tbl.seats.slice(3, 6).map(seat => (
                      <div
                        key={seat.seatNumber}
                        className={`px-2 py-1 rounded-lg border text-center font-mono ${
                          seat.isFolded ? 'bg-black/30 border-slate-800 opacity-40 text-slate-500' : 'bg-slate-950/70 border-slate-700 text-slate-200'
                        }`}
                      >
                        <div className="font-bold truncate max-w-[65px]">{seat.playerName}</div>
                        <div className="text-amber-300 text-[9px]">{seat.chipsBb} BB</div>
                      </div>
                    ))}
                  </div>

                  {/* Center: Pot & Board Cards */}
                  <div className="flex flex-col items-center justify-center gap-1 z-10">
                    <span className="px-2 py-0.5 rounded-full bg-black/60 border border-amber-500/30 text-[10px] font-mono font-bold text-amber-300">
                      POTE: {tbl.potBb.toFixed(1)} BB
                    </span>
                    <div className="flex items-center gap-1 min-h-[36px]">
                      {tbl.boardCards.length > 0 ? (
                        tbl.boardCards.map(c => renderCardBadge(c, false))
                      ) : (
                        <span className="text-[10px] text-slate-500 font-mono italic">
                          Pré-flop
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Bottom: Hero & Other Seats */}
                  <div className="flex justify-around items-center text-[10px] z-10">
                    {tbl.seats.slice(0, 3).map(seat => (
                      <div
                        key={seat.seatNumber}
                        className={`px-2 py-1 rounded-lg border text-center font-mono transition-all ${
                          seat.isHero
                            ? 'bg-emerald-950/90 border-emerald-400 ring-1 ring-emerald-500/50 text-emerald-200 shadow'
                            : seat.isFolded
                            ? 'bg-black/30 border-slate-800 opacity-40 text-slate-500'
                            : 'bg-slate-950/70 border-slate-700 text-slate-200'
                        }`}
                      >
                        <div className="font-bold flex items-center justify-center gap-1">
                          {tbl.dealerSeat === seat.seatNumber && (
                            <span className="w-3.5 h-3.5 rounded-full bg-white text-slate-950 font-black text-[8px] flex items-center justify-center">
                              D
                            </span>
                          )}
                          <span>{seat.isHero ? 'Hero' : seat.playerName.slice(0, 8)}</span>
                        </div>
                        <div className="text-amber-300 font-bold text-[9px]">{seat.chipsBb} BB</div>
                        {seat.isHero && (
                          <div className="flex items-center justify-center gap-0.5 mt-0.5">
                            {tbl.heroCards.map(c => renderCardBadge(c, false))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Quick Action Buttons for Hero Turn */}
                {tbl.status === 'HERO_TURN' && (
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <button
                      onClick={() => handleSimulateHeroAction(tbl.id, 'Fold')}
                      className="py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] font-bold text-rose-300 transition-colors"
                    >
                      Fold
                    </button>
                    <button
                      onClick={() => handleSimulateHeroAction(tbl.id, 'Check/Call')}
                      className="py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 text-[11px] font-black transition-colors"
                    >
                      Call
                    </button>
                    <button
                      onClick={() => handleSimulateHeroAction(tbl.id, 'Raise')}
                      className="py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-[11px] font-black transition-colors"
                    >
                      Raise
                    </button>
                  </div>
                )}
              </div>

              {/* Card Footer: Window Telemetry Drawer */}
              <div className="p-2.5 bg-slate-950/90 border-t border-slate-800 text-[10px] font-mono text-slate-400 flex items-center justify-between">
                <span>
                  Físico: {tbl.boxPhysical[2]}x{tbl.boxPhysical[3]} px
                </span>
                <span className="text-slate-500">
                  W/H: {tbl.aspectRatio}
                </span>
                <button
                  onClick={() => handleToggleHeroTurnSimulation(tbl.id)}
                  className="text-emerald-400 hover:text-emerald-300 underline font-sans text-[11px]"
                >
                  {tbl.status === 'HERO_TURN' ? 'Finalizar Turno' : 'Disparar Turno'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Bottom Auxiliary: DPI Matrix & OS Window Tiling Suggestions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: DPI Awareness Information Panel (1 col) */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Monitor className="w-4 h-4 text-emerald-400" />
            <h4 className="font-bold text-xs text-slate-100 uppercase tracking-wider">
              Arquitetura de DPI & Monitores
            </h4>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            O VisualPilot opera em modo <strong>Per-Monitor DPI Aware V2</strong>. As coordenadas físicas capturadas pelo desktop são normalizadas automaticamente para a matriz de 787x1470 px, garantindo que o robô clique com precisão milimétrica mesmo ao mover janelas entre monitores com escalas distintas (100%, 125% e 150%).
          </p>
          <div className="space-y-1.5 font-mono text-xs">
            <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800 text-slate-300">
              <span>Monitor Primário (1080p):</span>
              <span className="text-emerald-400 font-bold">96 DPI (100%)</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800 text-slate-300">
              <span>Monitor Secundário (4K):</span>
              <span className="text-cyan-400 font-bold">144 DPI (150%)</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800 text-slate-300">
              <span>Aspect Ratio Alvo:</span>
              <span className="text-amber-400 font-bold">0.535 (9:16.8)</span>
            </div>
          </div>
        </div>

        {/* Right: Desktop Window Tiling Suggestions (2 cols) */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-emerald-400" />
              <h4 className="font-bold text-xs text-slate-100 uppercase tracking-wider">
                Mapeamento de Coordenadas de Mosaico (Tiling sem Sobreposição)
              </h4>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleCopyTilingSuggestions}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors cursor-pointer"
              >
                {copiedTiling ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Copiado!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copiar Coordenadas</span>
                  </>
                )}
              </button>
              <a
                href="/multitable_snapshot.json"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors cursor-pointer"
              >
                <Download className="w-3.5 h-3.5 text-emerald-400" />
                <span>JSON</span>
              </a>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-2 font-semibold">Slot #</th>
                  <th className="pb-2 font-semibold">Mesa</th>
                  <th className="pb-2 font-semibold">Handle HWND</th>
                  <th className="pb-2 font-semibold">Target Box [X, Y, W, H]</th>
                  <th className="pb-2 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {tables.map((t, idx) => (
                  <tr key={t.id} className="hover:bg-slate-950/40">
                    <td className="py-2 text-emerald-400 font-bold">Slot #{idx + 1}</td>
                    <td className="py-2 text-slate-200 truncate max-w-[200px]">{t.title}</td>
                    <td className="py-2 text-slate-400">{t.hwnd}</td>
                    <td className="py-2 text-amber-300">
                      [{10 + (idx % 3) * 640}, {10 + Math.floor(idx / 3) * 520}, 620, 500]
                    </td>
                    <td className="py-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-sans font-bold ${
                        t.status === 'HERO_TURN' ? 'bg-emerald-950 text-emerald-300' : 'bg-slate-800 text-slate-400'
                      }`}>
                        {t.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
