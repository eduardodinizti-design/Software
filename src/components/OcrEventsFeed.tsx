import React, { useState, useMemo } from 'react';
import {
  Search,
  Filter,
  Download,
  Trash2,
  Pause,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Activity,
  SlidersHorizontal,
  ChevronDown,
  ArrowUpDown
} from 'lucide-react';

export interface OcrEventItem {
  id: string;
  timestamp: string;
  tableId: string;
  tableName: string;
  eventType: 'PLAYER_ACTION' | 'CARD_DETECTION' | 'POT_UPDATE' | 'STACK_CHANGE' | 'SYSTEM_ALERT';
  player: string;
  isHero: boolean;
  mainInfo: string;
  confidence: number; // 0.0 a 1.0
  details?: string;
}

const INITIAL_EVENTS: OcrEventItem[] = [
  {
    id: 'evt-01',
    timestamp: '15:42:08',
    tableId: 'table-1',
    tableName: 'Mesa 1 (NLH 200)',
    eventType: 'PLAYER_ACTION',
    player: 'Hero',
    isHero: true,
    mainInfo: 'Raise para 2.5 BB (5.00)',
    confidence: 0.994,
    details: 'Bet Sizing Safety Gate verificado. Botão calibrado em (428, 792).'
  },
  {
    id: 'evt-02',
    timestamp: '15:42:06',
    tableId: 'table-1',
    tableName: 'Mesa 1 (NLH 200)',
    eventType: 'CARD_DETECTION',
    player: 'Mesa',
    isHero: false,
    mainInfo: 'Flop: A♠ K♥ 7♦',
    confidence: 0.998,
    details: 'YOLOv8 Nano SIMD latência 7.6ms. Bounding boxes [140, 260, 380].'
  },
  {
    id: 'evt-03',
    timestamp: '15:42:03',
    tableId: 'table-2',
    tableName: 'Mesa 2 (PLO4 100)',
    eventType: 'POT_UPDATE',
    player: 'Pote',
    isHero: false,
    mainInfo: 'Pote total atualizado para 14.5 BB',
    confidence: 0.985,
    details: 'Segmentação numérica ROI Pote Central.'
  },
  {
    id: 'evt-04',
    timestamp: '15:41:59',
    tableId: 'table-3',
    tableName: 'Mesa 3 (NLH 500)',
    eventType: 'PLAYER_ACTION',
    player: 'Vilão 4 (CO)',
    isHero: false,
    mainInfo: 'Fold pré-flop',
    confidence: 0.991,
    details: 'Mudança de opacidade e avatar em grayscale.'
  },
  {
    id: 'evt-05',
    timestamp: '15:41:55',
    tableId: 'table-1',
    tableName: 'Mesa 1 (NLH 200)',
    eventType: 'CARD_DETECTION',
    player: 'Hero',
    isHero: true,
    mainInfo: 'Cartas da mão: A♦ Q♦ (suited)',
    confidence: 0.999,
    details: 'Detecção instantânea no deal. Equidade Monte Carlo: 68.4%.'
  },
  {
    id: 'evt-06',
    timestamp: '15:41:50',
    tableId: 'table-4',
    tableName: 'Mesa 4 (NLH 100)',
    eventType: 'STACK_CHANGE',
    player: 'Vilão 2 (BB)',
    isHero: false,
    mainInfo: 'Stack: 98.2 BB (+12.0 BB)',
    confidence: 0.978,
    details: 'OCR tesseract filtrado via regex decimal.'
  },
  {
    id: 'evt-07',
    timestamp: '15:41:44',
    tableId: 'table-2',
    tableName: 'Mesa 2 (PLO4 100)',
    eventType: 'PLAYER_ACTION',
    player: 'Vilão 1 (BTN)',
    isHero: false,
    mainInfo: 'Call 3.0 BB',
    confidence: 0.989,
    details: 'Fichas no pano detectadas na coordenada relativa.'
  },
  {
    id: 'evt-08',
    timestamp: '15:41:38',
    tableId: 'table-1',
    tableName: 'Mesa 1 (NLH 200)',
    eventType: 'POT_UPDATE',
    player: 'Pote',
    isHero: false,
    mainInfo: 'Pote pré-flop: 4.5 BB',
    confidence: 0.996,
    details: 'Leitura estável sem oscilação por 3 frames.'
  },
  {
    id: 'evt-09',
    timestamp: '15:41:30',
    tableId: 'table-3',
    tableName: 'Mesa 3 (NLH 500)',
    eventType: 'PLAYER_ACTION',
    player: 'Hero',
    isHero: true,
    mainInfo: 'Check no Big Blind',
    confidence: 0.995,
    details: 'Opção gratuita (zero bet). Ação imediata humanizada 840ms.'
  },
  {
    id: 'evt-10',
    timestamp: '15:41:22',
    tableId: 'table-4',
    tableName: 'Mesa 4 (NLH 100)',
    eventType: 'CARD_DETECTION',
    player: 'Mesa',
    isHero: false,
    mainInfo: 'Turn: 9♣ (Board: A♠ K♥ 7♦ 9♣)',
    confidence: 0.993,
    details: 'Detecção de 4ª carta comunitária. Draw de flush completado.'
  },
  {
    id: 'evt-11',
    timestamp: '15:41:15',
    tableId: 'table-2',
    tableName: 'Mesa 2 (PLO4 100)',
    eventType: 'SYSTEM_ALERT',
    player: 'Sistema',
    isHero: false,
    mainInfo: 'Sincronização de janela mantida (DPI 100%)',
    confidence: 1.0,
    details: 'Window Visibility Guardian: janela focada e desimpedida.'
  },
  {
    id: 'evt-12',
    timestamp: '15:41:04',
    tableId: 'table-1',
    tableName: 'Mesa 1 (NLH 200)',
    eventType: 'PLAYER_ACTION',
    player: 'Vilão 5 (SB)',
    isHero: false,
    mainInfo: 'Bet 1.8 BB',
    confidence: 0.982,
    details: 'Lead out no flop contra 2 jogadores.'
  }
];

export const OcrEventsFeed: React.FC = () => {
  const [events, setEvents] = useState<OcrEventItem[]>(INITIAL_EVENTS);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTable, setSelectedTable] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [isLiveStream, setIsLiveStream] = useState(true);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  // Filtragem objetiva
  const filteredEvents = useMemo(() => {
    return events.filter(evt => {
      // Filtro de mesa
      if (selectedTable !== 'all' && evt.tableId !== selectedTable) {
        return false;
      }
      // Filtro de tipo
      if (selectedType !== 'all' && evt.eventType !== selectedType) {
        return false;
      }
      // Busca textual
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesInfo = evt.mainInfo.toLowerCase().includes(q);
        const matchesPlayer = evt.player.toLowerCase().includes(q);
        const matchesTable = evt.tableName.toLowerCase().includes(q);
        return matchesInfo || matchesPlayer || matchesTable;
      }
      return true;
    });
  }, [events, selectedTable, selectedType, searchQuery]);

  // Exportar CSV limpo
  const handleExportCsv = () => {
    const headers = ['Horario', 'Mesa', 'Tipo_Evento', 'Jogador', 'Informacao_Principal', 'Confianca_OCR'];
    const rows = filteredEvents.map(e => [
      e.timestamp,
      e.tableName,
      e.eventType,
      e.player,
      `"${e.mainInfo.replace(/"/g, '""')}"`,
      `${(e.confidence * 100).toFixed(1)}%`
    ]);
    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `visualpilot_eventos_ocr_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleClear = () => {
    setEvents([]);
  };

  const handleReset = () => {
    setEvents(INITIAL_EVENTS);
  };

  const getEventBadge = (type: OcrEventItem['eventType']) => {
    switch (type) {
      case 'PLAYER_ACTION':
        return <span className="text-slate-200">Ação</span>;
      case 'CARD_DETECTION':
        return <span className="text-emerald-400">Cartas</span>;
      case 'POT_UPDATE':
        return <span className="text-amber-400">Pote</span>;
      case 'STACK_CHANGE':
        return <span className="text-cyan-400">Stack</span>;
      case 'SYSTEM_ALERT':
        return <span className="text-slate-400">Sistema</span>;
    }
  };

  return (
    <div className="space-y-4">
      {/* Barra Superior de Filtros e Controles */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Filtros à Esquerda */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Busca Textual */}
          <div className="relative min-w-[200px]">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Filtrar por jogador ou ação..."
              className="w-full pl-8 pr-3 py-1.5 bg-[#0b0f19] border border-slate-700/80 rounded text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-slate-500 text-xs"
            />
          </div>

          {/* Seletor de Mesa */}
          <div className="flex items-center gap-1.5 text-slate-400">
            <span>Mesa:</span>
            <select
              value={selectedTable}
              onChange={e => setSelectedTable(e.target.value)}
              className="bg-[#0b0f19] border border-slate-700/80 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-slate-500 cursor-pointer text-xs"
            >
              <option value="all">Todas as Mesas</option>
              <option value="table-1">Mesa 1 (NLH 200)</option>
              <option value="table-2">Mesa 2 (PLO4 100)</option>
              <option value="table-3">Mesa 3 (NLH 500)</option>
              <option value="table-4">Mesa 4 (NLH 100)</option>
            </select>
          </div>

          {/* Seletor de Tipo de Evento */}
          <div className="flex items-center gap-1.5 text-slate-400">
            <span>Tipo:</span>
            <select
              value={selectedType}
              onChange={e => setSelectedType(e.target.value)}
              className="bg-[#0b0f19] border border-slate-700/80 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-slate-500 cursor-pointer text-xs"
            >
              <option value="all">Todos os Tipos</option>
              <option value="PLAYER_ACTION">Ações de Jogador</option>
              <option value="CARD_DETECTION">Detecção de Cartas</option>
              <option value="POT_UPDATE">Atualizações de Pote</option>
              <option value="STACK_CHANGE">Variações de Stack</option>
              <option value="SYSTEM_ALERT">Alertas do Sistema</option>
            </select>
          </div>
        </div>

        {/* Controles à Direita */}
        <div className="flex items-center gap-2">
          {/* Indicador de Transmissão */}
          <button
            onClick={() => setIsLiveStream(!isLiveStream)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded border text-xs font-medium transition-colors ${
              isLiveStream
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-slate-800 border-slate-700 text-slate-400'
            }`}
          >
            {isLiveStream ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            <span>{isLiveStream ? 'Transmissão Ativa' : 'Pausado'}</span>
          </button>

          {/* Exportar CSV */}
          <button
            onClick={handleExportCsv}
            disabled={filteredEvents.length === 0}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 font-medium disabled:opacity-50 transition-colors"
            title="Exportar registros filtrados em arquivo CSV"
          >
            <Download className="w-3 h-3 text-slate-400" />
            <span>CSV</span>
          </button>

          {/* Limpar / Restaurar */}
          {events.length === 0 ? (
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-2 py-1.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300"
              title="Restaurar eventos de demonstração"
            >
              <RotateCcw className="w-3 h-3" />
            </button>
          ) : (
            <button
              onClick={handleClear}
              className="flex items-center gap-1.5 px-2 py-1.5 rounded bg-slate-800/80 hover:bg-rose-950/60 border border-slate-700 hover:border-rose-700/60 text-slate-400 hover:text-rose-300 transition-colors"
              title="Limpar feed atual"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* Tabela de Eventos Limpa e de Alta Legibilidade */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-[#0b0f19] text-slate-400 font-medium">
                <th className="py-2.5 px-3 w-24">Horário</th>
                <th className="py-2.5 px-3 w-40">Mesa</th>
                <th className="py-2.5 px-3 w-28">Tipo</th>
                <th className="py-2.5 px-3 w-32">Jogador</th>
                <th className="py-2.5 px-3">Informação Principal</th>
                <th className="py-2.5 px-3 w-28 text-right">Confiança</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500 font-sans">
                    Nenhum evento corresponde aos filtros selecionados.
                  </td>
                </tr>
              ) : (
                filteredEvents.map(evt => {
                  const isSelected = selectedEventId === evt.id;
                  const isHighConf = evt.confidence >= 0.98;
                  return (
                    <tr
                      key={evt.id}
                      onClick={() => setSelectedEventId(isSelected ? null : evt.id)}
                      className={`hover:bg-slate-800/40 transition-colors cursor-pointer ${
                        isSelected ? 'bg-slate-800/60' : ''
                      }`}
                    >
                      {/* Horário */}
                      <td className="py-2 px-3 text-slate-400 whitespace-nowrap">
                        {evt.timestamp}
                      </td>

                      {/* Mesa */}
                      <td className="py-2 px-3 font-sans text-slate-300 whitespace-nowrap">
                        {evt.tableName}
                      </td>

                      {/* Tipo */}
                      <td className="py-2 px-3 font-sans whitespace-nowrap">
                        {getEventBadge(evt.eventType)}
                      </td>

                      {/* Jogador */}
                      <td className="py-2 px-3 font-sans whitespace-nowrap">
                        <span className={evt.isHero ? 'font-semibold text-emerald-400' : 'text-slate-300'}>
                          {evt.player}
                        </span>
                      </td>

                      {/* Informação Principal */}
                      <td className="py-2 px-3 font-sans text-slate-100">
                        <div className="flex flex-col">
                          <span>{evt.mainInfo}</span>
                          {isSelected && evt.details && (
                            <span className="text-[11px] text-slate-400 mt-1 font-mono">
                              ↳ Detalhes: {evt.details}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Confiança */}
                      <td className="py-2 px-3 text-right whitespace-nowrap">
                        <span className={`font-semibold ${
                          isHighConf ? 'text-emerald-400' : 'text-amber-400'
                        }`}>
                          {(evt.confidence * 100).toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Rodapé Informativo */}
        <div className="bg-[#0b0f19] border-t border-slate-800 px-3 py-2 flex items-center justify-between text-[11px] text-slate-500">
          <span>
            Mostrando {filteredEvents.length} de {events.length} eventos registrados
          </span>
          <span className="font-mono">
            Motor de Reconhecimento: YOLOv8 Nano SIMD · Taxa de Amostragem: 12 fps
          </span>
        </div>
      </div>
    </div>
  );
};
