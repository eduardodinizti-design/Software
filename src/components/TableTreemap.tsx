import React, { useState, useRef, useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import {
  Flame,
  Coins,
  Layers,
  ZoomIn,
  Eye,
  Filter,
  Maximize2,
  Sparkles,
  Info
} from 'lucide-react';
import { SeatData } from './TableNumericalOcrInspector';

export interface MultiTableData {
  tableId: string;
  tableName: string;
  potBb: number;
  gameType: string;
  blinds: string;
  seats: {
    name: string;
    stackBb: number;
    isHero: boolean;
    isFolded: boolean;
    position?: string;
  }[];
}

interface TreemapNodeDatum {
  name: string;
  category: 'pot' | 'hero' | 'villain' | 'short_stack';
  tableId?: string;
  tableName?: string;
  value: number; // BB
  chips?: number;
  position?: string;
  isPot?: boolean;
  isHero?: boolean;
  children?: TreemapNodeDatum[];
}

// Exemplos realistas de mesas ativas para a visão multi-mesas integrada
const MOCK_ACTIVE_TABLES: MultiTableData[] = [
  {
    tableId: 'tbl-1',
    tableName: 'Mesa #1 (NLH 50/100)',
    potBb: 18.5,
    gameType: 'NLH',
    blinds: '50/100',
    seats: [
      { name: 'DealerPro', stackBb: 105.0, isHero: false, isFolded: false, position: 'BTN' },
      { name: 'ShortBlind', stackBb: 38.0, isHero: false, isFolded: false, position: 'SB' },
      { name: 'BigBlind_BR', stackBb: 92.0, isHero: false, isFolded: false, position: 'BB' },
      { name: 'AggroUTG', stackBb: 140.0, isHero: false, isFolded: false, position: 'UTG' },
      { name: 'Hero (Você)', stackBb: 115.0, isHero: true, isFolded: false, position: 'CO' },
      { name: 'NitPlayer', stackBb: 75.0, isHero: false, isFolded: true, position: 'MP' }
    ]
  },
  {
    tableId: 'tbl-2',
    tableName: 'Mesa #2 (PLO4 200/400)',
    potBb: 64.0,
    gameType: 'PLO4',
    blinds: '200/400',
    seats: [
      { name: 'OmahaKing', stackBb: 240.0, isHero: false, isFolded: false, position: 'UTG' },
      { name: 'ActionJunkie', stackBb: 135.5, isHero: false, isFolded: false, position: 'MP' },
      { name: 'Hero (Você)', stackBb: 215.0, isHero: true, isFolded: false, position: 'CO' },
      { name: 'VegasGrinder', stackBb: 22.0, isHero: false, isFolded: true, position: 'BTN' },
      { name: 'PotMaster', stackBb: 160.0, isHero: false, isFolded: false, position: 'SB' }
    ]
  },
  {
    tableId: 'tbl-3',
    tableName: 'Mesa #3 (MTT Deepstack)',
    potBb: 36.5,
    gameType: 'MTT',
    blinds: '500/1000',
    seats: [
      { name: 'ChipLeader', stackBb: 185.0, isHero: false, isFolded: false, position: 'BTN' },
      { name: 'Shorty', stackBb: 14.0, isHero: false, isFolded: false, position: 'SB' },
      { name: 'Hero (Você)', stackBb: 68.0, isHero: true, isFolded: false, position: 'BB' },
      { name: 'TightGrinder', stackBb: 95.0, isHero: false, isFolded: false, position: 'UTG' }
    ]
  },
  {
    tableId: 'tbl-4',
    tableName: 'Mesa #4 (NLH Turbo 25/50)',
    potBb: 8.0,
    gameType: 'NLH',
    blinds: '25/50',
    seats: [
      { name: 'AggroFish', stackBb: 94.0, isHero: false, isFolded: false, position: 'BTN' },
      { name: 'Hero (Você)', stackBb: 122.0, isHero: true, isFolded: false, position: 'SB' },
      { name: 'Maniac99', stackBb: 45.0, isHero: false, isFolded: false, position: 'BB' }
    ]
  }
];

export const TableTreemap: React.FC<{
  currentTablePotBb: number;
  currentTableSeats: SeatData[];
  onSelectEntity?: (name: string, valueBb: number, isPot: boolean) => void;
}> = ({ currentTablePotBb, currentTableSeats, onSelectEntity }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewScope, setViewScope] = useState<'all_tables' | 'current_table'>('all_tables');
  const [filterMode, setFilterMode] = useState<'all' | 'pots_only' | 'big_pots'>('all');
  const [hoveredNode, setHoveredNode] = useState<{
    name: string;
    tableName: string;
    valueBb: number;
    chips: number;
    category: string;
    position?: string;
    percentTotal: number;
    x: number;
    y: number;
  } | null>(null);

  // Compute hierarchical tree data
  const hierarchyData = useMemo<TreemapNodeDatum>(() => {
    if (viewScope === 'current_table') {
      const children: TreemapNodeDatum[] = [
        {
          name: 'POTE PRINCIPAL',
          category: 'pot',
          tableName: 'Mesa em Foco',
          value: Math.max(0.5, currentTablePotBb),
          chips: currentTablePotBb * 100,
          isPot: true
        },
        ...currentTableSeats
          .filter(s => !s.isFolded && s.stackBb > 0)
          .map(s => ({
            name: s.playerName,
            category: s.isHero ? 'hero' as const : s.stackBb < 25 ? 'short_stack' as const : 'villain' as const,
            tableName: 'Mesa em Foco',
            value: Math.max(0.5, s.stackBb),
            chips: s.stackChips || s.stackBb * 100,
            isHero: s.isHero,
            isPot: false
          }))
      ];

      return {
        name: 'root',
        category: 'villain',
        value: 0,
        children
      };
    }

    // Multi-tables view (Mesas 1 a 6)
    // Synchronize Table 1 with live currentTablePotBb and currentTableSeats
    const tables: MultiTableData[] = MOCK_ACTIVE_TABLES.map(t => {
      if (t.tableId === 'tbl-1') {
        return {
          ...t,
          potBb: currentTablePotBb,
          seats: currentTableSeats.map(s => ({
            name: s.playerName,
            stackBb: s.stackBb,
            isHero: s.isHero,
            isFolded: s.isFolded
          }))
        };
      }
      return t;
    });

    const tableChildren: TreemapNodeDatum[] = tables.map(table => {
      const items: TreemapNodeDatum[] = [];

      // Add Pot
      if (filterMode !== 'all' && filterMode === 'big_pots' && table.potBb < 20) {
        // Skip small pots in big_pots filter
      } else {
        items.push({
          name: `POTE (${table.potBb} BB)`,
          category: 'pot',
          tableName: table.tableName,
          tableId: table.tableId,
          value: Math.max(1, table.potBb),
          chips: table.potBb * 100,
          isPot: true
        });
      }

      // Add Players Stacks if not 'pots_only'
      if (filterMode === 'all') {
        table.seats
          .filter(s => !s.isFolded && s.stackBb > 0)
          .forEach(s => {
            items.push({
              name: s.name,
              category: s.isHero ? 'hero' : s.stackBb < 25 ? 'short_stack' : 'villain',
              tableName: table.tableName,
              tableId: table.tableId,
              value: Math.max(1, s.stackBb),
              chips: s.stackBb * 100,
              position: s.position,
              isHero: s.isHero,
              isPot: false
            });
          });
      }

      return {
        name: table.tableName,
        category: 'villain',
        tableName: table.tableName,
        tableId: table.tableId,
        value: 0,
        children: items
      };
    });

    return {
      name: 'Mundo Multi-Mesas',
      category: 'villain',
      value: 0,
      children: tableChildren
    };
  }, [viewScope, filterMode, currentTablePotBb, currentTableSeats]);

  // Total Capital for Percentage calculation
  const totalCapitalBb = useMemo(() => {
    let sum = 0;
    const recurse = (node: TreemapNodeDatum) => {
      if (node.children) {
        node.children.forEach(recurse);
      } else if (node.value) {
        sum += node.value;
      }
    };
    recurse(hierarchyData);
    return Math.max(1, sum);
  }, [hierarchyData]);

  // Layout D3 Treemap SVG
  const [dimensions, setDimensions] = useState({ width: 700, height: 380 });

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        if (width > 0) {
          setDimensions({ width, height: Math.max(340, Math.round(width * 0.44)) });
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const leaves = useMemo(() => {
    const root = d3
      .hierarchy<TreemapNodeDatum>(hierarchyData)
      .sum(d => d.value)
      .sort((a, b) => (b.value || 0) - (a.value || 0));

    const treemapLayout = d3
      .treemap<TreemapNodeDatum>()
      .size([dimensions.width, dimensions.height])
      .paddingOuter(4)
      .paddingTop(viewScope === 'all_tables' ? 22 : 4)
      .paddingInner(3)
      .round(true);

    const rectangularRoot = treemapLayout(root);
    return rectangularRoot.leaves();
  }, [hierarchyData, dimensions, viewScope]);

  // Parent groups for header labels in multi-table view
  const tableGroups = useMemo(() => {
    if (viewScope !== 'all_tables') return [];
    const root = d3
      .hierarchy<TreemapNodeDatum>(hierarchyData)
      .sum(d => d.value)
      .sort((a, b) => (b.value || 0) - (a.value || 0));

    const treemapLayout = d3
      .treemap<TreemapNodeDatum>()
      .size([dimensions.width, dimensions.height])
      .paddingOuter(4)
      .paddingTop(22)
      .paddingInner(3)
      .round(true);

    const rectangularRoot = treemapLayout(root);
    return rectangularRoot.children || [];
  }, [hierarchyData, dimensions, viewScope]);

  // Node Color Mapper
  const getNodeFill = (d: d3.HierarchyRectangularNode<TreemapNodeDatum>) => {
    if (d.data.isPot) {
      // Hot Amber / Golden gradient for Pots
      return d.data.value >= 30
        ? 'url(#pot-gradient-hot)'
        : 'url(#pot-gradient-standard)';
    }
    if (d.data.isHero) {
      // Vibrant Emerald for Hero
      return 'url(#hero-gradient)';
    }
    if (d.data.category === 'short_stack') {
      return '#c2410c'; // Warm orange-red for short stack
    }
    // Villains / regular stacks: slate to dark cyan
    return '#1e293b';
  };

  const getNodeStroke = (d: d3.HierarchyRectangularNode<TreemapNodeDatum>) => {
    if (d.data.isPot) return d.data.value >= 30 ? '#f59e0b' : '#d97706';
    if (d.data.isHero) return '#10b981';
    if (d.data.category === 'short_stack') return '#ea580c';
    return '#334155';
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
      {/* Header with Title and Control Badges */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30">
              <Flame className="w-4 h-4" />
            </span>
            <h3 className="font-bold text-sm text-slate-100 tracking-tight flex items-center gap-2">
              <span>Mapa de Calor D3 (Treemap): Distribuição de Potes & Stacks</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-950 text-amber-300 border border-amber-800">
                Multi-Mesas Ativas
              </span>
            </h3>
          </div>
          <p className="text-xs text-slate-400">
            A área de cada bloco é proporcional ao montante de fichas em Big Blinds (BB). Identifique instantaneamente onde estão os <strong>maiores potes em disputa</strong>.
          </p>
        </div>

        {/* View Switchers & Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Scope Toggle */}
          <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs font-semibold">
            <button
              onClick={() => setViewScope('all_tables')}
              className={`px-3 py-1 rounded-lg transition-all ${
                viewScope === 'all_tables'
                  ? 'bg-amber-500 text-slate-950 shadow-sm font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Todas as Mesas (1-4)
            </button>
            <button
              onClick={() => setViewScope('current_table')}
              className={`px-3 py-1 rounded-lg transition-all ${
                viewScope === 'current_table'
                  ? 'bg-amber-500 text-slate-950 shadow-sm font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Mesa em Foco
            </button>
          </div>

          {/* Filter Toggle */}
          <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs font-semibold">
            <button
              onClick={() => setFilterMode('all')}
              className={`px-2.5 py-1 rounded-lg transition-all ${
                filterMode === 'all'
                  ? 'bg-slate-800 text-slate-100 border border-slate-700'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Exibir potes e stacks de todos os jogadores"
            >
              Potes & Stacks
            </button>
            <button
              onClick={() => setFilterMode('pots_only')}
              className={`px-2.5 py-1 rounded-lg transition-all ${
                filterMode === 'pots_only'
                  ? 'bg-slate-800 text-amber-300 border border-amber-600/50'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Filtrar apenas os potes ativos nas mesas"
            >
              Apenas Potes
            </button>
          </div>
        </div>
      </div>

      {/* Legend Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded bg-gradient-to-br from-amber-400 to-amber-600 border border-amber-300 shadow-sm" />
            <span className="text-slate-300 font-bold">Pote Ativo (Em Disputa)</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded bg-gradient-to-br from-emerald-400 to-emerald-600 border border-emerald-300 shadow-sm" />
            <span className="text-emerald-300 font-bold">Hero (Seu Stack)</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded bg-slate-800 border border-slate-700" />
            <span className="text-slate-400">Stacks dos Vilões</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded bg-orange-700 border border-orange-600" />
            <span className="text-orange-300">Short Stack (&lt;25 BB)</span>
          </div>
        </div>

        <div className="text-slate-400 text-[11px]">
          Capital Total Mapeado: <strong className="text-emerald-400 font-bold">{totalCapitalBb.toFixed(1)} BB</strong>
        </div>
      </div>

      {/* Treemap SVG Canvas Container */}
      <div
        ref={containerRef}
        className="w-full relative bg-slate-950 border border-slate-800/90 rounded-2xl overflow-hidden shadow-inner select-none"
        style={{ minHeight: '340px' }}
      >
        <svg
          width={dimensions.width}
          height={dimensions.height}
          className="w-full h-auto block"
        >
          <defs>
            {/* Standard Pot Gradient (Golden Amber) */}
            <linearGradient id="pot-gradient-standard" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#b45309" />
              <stop offset="50%" stopColor="#d97706" />
              <stop offset="100%" stopColor="#92400e" />
            </linearGradient>

            {/* Hot Pot Gradient (> 30 BB, Electric Amber) */}
            <linearGradient id="pot-gradient-hot" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f59e0b" />
              <stop offset="50%" stopColor="#fbbf24" />
              <stop offset="100%" stopColor="#d97706" />
            </linearGradient>

            {/* Hero Stack Gradient (Emerald) */}
            <linearGradient id="hero-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#059669" />
              <stop offset="100%" stopColor="#047857" />
            </linearGradient>
          </defs>

          {/* Table Group Headers in Multi-Table View */}
          {tableGroups.map((group, gIdx) => {
            const gx = group.x0 || 0;
            const gy = group.y0 || 0;
            const gw = (group.x1 || 0) - gx;
            return (
              <g key={gIdx} className="pointer-events-none">
                {/* Background outline for the whole table container */}
                <rect
                  x={gx}
                  y={gy}
                  width={gw}
                  height={(group.y1 || 0) - gy}
                  fill="none"
                  stroke="#334155"
                  strokeWidth={1.5}
                  strokeDasharray="3 3"
                  rx={6}
                />
                {/* Header label text */}
                <text
                  x={gx + 8}
                  y={gy + 14}
                  fill="#94a3b8"
                  fontSize="11"
                  fontWeight="bold"
                  fontFamily="monospace"
                >
                  {group.data.name}
                </text>
              </g>
            );
          })}

          {/* Treemap Rectangles (Leaves) */}
          {leaves.map((leaf, idx) => {
            const x = leaf.x0;
            const y = leaf.y0;
            const w = leaf.x1 - leaf.x0;
            const h = leaf.y1 - leaf.y0;
            const isPot = leaf.data.isPot;
            const isHero = leaf.data.isHero;
            const val = leaf.data.value;
            const fill = getNodeFill(leaf);
            const stroke = getNodeStroke(leaf);

            // Display conditions based on rect size
            const showTitle = w > 45 && h > 28;
            const showValue = w > 55 && h > 42;
            const showChips = w > 80 && h > 58;

            return (
              <g
                key={idx}
                className="cursor-pointer transition-transform duration-100 group"
                onClick={() => onSelectEntity?.(leaf.data.name, leaf.data.value, !!leaf.data.isPot)}
                onMouseEnter={(e) => {
                  const rect = containerRef.current?.getBoundingClientRect();
                  const relX = e.clientX - (rect?.left || 0);
                  const relY = e.clientY - (rect?.top || 0);
                  setHoveredNode({
                    name: leaf.data.name,
                    tableName: leaf.data.tableName || '',
                    valueBb: leaf.data.value,
                    chips: leaf.data.chips || leaf.data.value * 100,
                    category: isPot ? 'Pote Ativo' : isHero ? 'Hero (Você)' : leaf.data.category === 'short_stack' ? 'Short Stack' : 'Vilão',
                    position: leaf.data.position,
                    percentTotal: Number(((leaf.data.value / totalCapitalBb) * 100).toFixed(1)),
                    x: relX,
                    y: relY
                  });
                }}
                onMouseLeave={() => setHoveredNode(null)}
              >
                {/* Main Rectangle */}
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={isPot ? 2 : 1}
                  rx={4}
                  className={`transition-all ${
                    isPot && val >= 30
                      ? 'filter drop-shadow-[0_0_8px_rgba(245,158,11,0.4)]'
                      : 'hover:brightness-115'
                  }`}
                />

                {/* Pot Flame or Sparkle Icon in top right */}
                {isPot && w > 36 && h > 36 && (
                  <text
                    x={x + w - 16}
                    y={y + 16}
                    fontSize="12"
                    fill={val >= 30 ? '#fef08a' : '#fde68a'}
                    textAnchor="middle"
                  >
                    🔥
                  </text>
                )}

                {/* Hero Star Badge */}
                {isHero && w > 36 && h > 36 && (
                  <text
                    x={x + w - 16}
                    y={y + 16}
                    fontSize="11"
                    fill="#6ee7b7"
                    textAnchor="middle"
                  >
                    ★
                  </text>
                )}

                {/* Content Inside Rectangle */}
                {showTitle && (
                  <text
                    x={x + 6}
                    y={y + 16}
                    fill={isPot ? (val >= 30 ? '#0f172a' : '#ffffff') : isHero ? '#ffffff' : '#f1f5f9'}
                    fontSize={w > 120 ? '12' : '10'}
                    fontWeight="bold"
                    fontFamily="monospace"
                    className="select-none pointer-events-none"
                  >
                    {leaf.data.name.length > Math.floor(w / 8)
                      ? leaf.data.name.slice(0, Math.floor(w / 8) - 1) + '…'
                      : leaf.data.name}
                  </text>
                )}

                {showValue && (
                  <text
                    x={x + 6}
                    y={y + 32}
                    fill={isPot ? (val >= 30 ? '#0f172a' : '#fef08a') : isHero ? '#a7f3d0' : '#38bdf8'}
                    fontSize={w > 120 ? '13' : '11'}
                    fontWeight="black"
                    fontFamily="monospace"
                    className="select-none pointer-events-none"
                  >
                    {val.toFixed(1)} BB
                  </text>
                )}

                {showChips && (
                  <text
                    x={x + 6}
                    y={y + 47}
                    fill={isPot ? (val >= 30 ? '#1e293b' : '#fde68a') : '#94a3b8'}
                    fontSize="9"
                    fontFamily="monospace"
                    className="select-none pointer-events-none"
                  >
                    {(val * 100).toLocaleString()} fichas
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* Floating Custom Tooltip on Hover */}
        {hoveredNode && (
          <div
            className="absolute z-30 pointer-events-none p-3 rounded-xl bg-slate-900/95 border border-slate-700 shadow-2xl backdrop-blur-md text-xs font-mono space-y-1 transform -translate-x-1/2 -translate-y-full animate-in fade-in duration-100"
            style={{
              left: Math.min(Math.max(120, hoveredNode.x), dimensions.width - 120),
              top: Math.max(70, hoveredNode.y - 12)
            }}
          >
            <div className="flex items-center gap-1.5 border-b border-slate-800 pb-1">
              <span className={`w-2.5 h-2.5 rounded-full ${
                hoveredNode.category === 'Pote Ativo'
                  ? 'bg-amber-400'
                  : hoveredNode.category === 'Hero (Você)'
                  ? 'bg-emerald-400'
                  : 'bg-cyan-400'
              }`} />
              <strong className="text-slate-100">{hoveredNode.name}</strong>
              {hoveredNode.position && (
                <span className="px-1.5 py-0.2 rounded text-[10px] bg-slate-800 text-cyan-300 border border-slate-700">
                  {hoveredNode.position}
                </span>
              )}
            </div>

            <div className="space-y-0.5 text-[11px] text-slate-300">
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-400">Mesa:</span>
                <span className="text-slate-200 font-bold">{hoveredNode.tableName}</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-400">Montante:</span>
                <strong className="text-emerald-400">{hoveredNode.valueBb.toFixed(1)} BB</strong>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-400">Fichas:</span>
                <span className="text-slate-200">{hoveredNode.chips.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-400">Tipo:</span>
                <span className="text-amber-300">{hoveredNode.category}</span>
              </div>
              <div className="flex items-center justify-between gap-4 pt-1 border-t border-slate-800 text-[10px]">
                <span className="text-slate-500">Participação no Capital:</span>
                <span className="text-cyan-300 font-bold">{hoveredNode.percentTotal}%</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
