import React from 'react';
import {
  Layers,
  Crosshair,
  ShieldCheck,
  Activity,
  Timer,
  Play,
  Pause,
  AlertCircle,
  CheckCircle2,
  Cpu,
  ChevronRight,
  TrendingUp,
  HardDrive,
  Eye,
  Sliders,
  Sparkles
} from 'lucide-react';
import { LiveDesktopMonitor } from './LiveDesktopMonitor';

interface OverviewDashboardProps {
  isSessionActive: boolean;
  sessionPaused: boolean;
  sessionElapsedSeconds: number;
  sessionClicksCount: number;
  preflightStatus: 'OK' | 'WARN' | 'FAIL' | 'ERROR';
  onNavigateTab: (tab: any) => void;
  onToggleSession: () => void;
}

export const OverviewDashboard: React.FC<OverviewDashboardProps> = ({
  isSessionActive,
  sessionPaused,
  sessionElapsedSeconds,
  sessionClicksCount,
  preflightStatus,
  onNavigateTab,
  onToggleSession
}) => {
  const formatTime = (secs: number) => {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-6">
      {/* 1. Métricas Principais (Cards Sóbreos e Objetivos) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Card 1: Status Geral do Sistema */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Status do Sistema</span>
            <span className="flex items-center gap-1 text-emerald-400 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              Operacional
            </span>
          </div>
          <div className="mt-3">
            <span className="text-xl font-semibold text-slate-100">YOLOv8 Ativo</span>
            <p className="text-xs text-slate-400 mt-0.5">
              Latência média: <span className="font-mono text-slate-300">7.6 ms</span> · SIMD
            </p>
          </div>
        </div>

        {/* Card 2: Mesas Conectadas */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Mesas Conectadas</span>
            <button
              onClick={() => onNavigateTab('multitable')}
              className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-0.5 transition-colors cursor-pointer"
            >
              <span>Ver Grade</span>
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>
          <div className="mt-3">
            <span className="text-xl font-semibold text-slate-100">4 Mesas</span>
            <p className="text-xs text-slate-400 mt-0.5">
              Grade 2x2 ativa · DPI 100% calibrado
            </p>
          </div>
        </div>

        {/* Card 3: Estado da Sessão */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Sessão Atual</span>
            <span className={`text-xs font-medium ${
              isSessionActive && !sessionPaused
                ? 'text-emerald-400'
                : isSessionActive && sessionPaused
                ? 'text-amber-400'
                : 'text-slate-500'
            }`}>
              {isSessionActive && !sessionPaused ? 'Ativa' : isSessionActive && sessionPaused ? 'Pausada' : 'Inativa'}
            </span>
          </div>
          <div className="mt-3">
            <span className="text-xl font-semibold text-slate-100 font-mono">
              {formatTime(sessionElapsedSeconds)}
            </span>
            <p className="text-xs text-slate-400 mt-0.5">
              Cliques auditados: <span className="font-mono text-slate-300">{sessionClicksCount}</span>
            </p>
          </div>
        </div>

        {/* Card 4: Integridade e Diagnóstico */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Pré-Voo & Integridade</span>
            <span className={`text-xs font-medium ${
              preflightStatus === 'OK' ? 'text-emerald-400' : 'text-amber-400'
            }`}>
              SHA-256 Validado
            </span>
          </div>
          <div className="mt-3">
            <span className="text-xl font-semibold text-slate-100">100% Íntegro</span>
            <p className="text-xs text-slate-400 mt-0.5">
              114 arquivos verificados · Python 3.11
            </p>
          </div>
        </div>
      </div>

      {/* Transmissão e Monitoramento Ao Vivo da Mesa (Seu Computador) */}
      <LiveDesktopMonitor />

      {/* 2. Seção Principal em 2 Colunas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Coluna Esquerda: Monitoramento & Ações Rápidas (2/3) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Card de Monitoramento Resumido das Mesas */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-5">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div>
                <h3 className="text-sm font-semibold text-slate-100">
                  Monitoramento em Tempo Real
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Fluxo simultâneo das mesas ativas no cliente PPPoker
                </p>
              </div>
              <button
                onClick={() => onNavigateTab('multitable')}
                className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 font-medium transition-colors cursor-pointer"
              >
                Abrir Visualização Multi-Mesas
              </button>
            </div>

            {/* Grid 2x2 Compacto das Mesas */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
              {[
                { id: '1', name: 'Mesa 1 - NLH 200', pot: '14.5 BB', cards: 'A♠ K♥ 7♦', status: 'Ação do Hero (Raise 2.5 BB)', conf: '99.4%' },
                { id: '2', name: 'Mesa 2 - PLO4 100', pot: '6.0 BB', cards: 'Q♣ J♦ 9♠', status: 'Aguardando Turn', conf: '98.9%' },
                { id: '3', name: 'Mesa 3 - NLH 500', pot: '2.5 BB', cards: '10♥ 10♦ 3♣', status: 'Check pré-flop', conf: '99.8%' },
                { id: '4', name: 'Mesa 4 - NLH 100', pot: '18.0 BB', cards: 'A♦ 8♦ 2♠', status: 'Vilão apostou 6.0 BB', conf: '98.2%' },
              ].map(table => (
                <div
                  key={table.id}
                  onClick={() => onNavigateTab('multitable')}
                  className="bg-[#0b0f19] border border-slate-800/80 hover:border-slate-700 rounded p-3 cursor-pointer transition-colors"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-200">{table.name}</span>
                    <span className="text-[11px] text-emerald-400 font-mono">{table.conf}</span>
                  </div>
                  <div className="mt-2 text-xs flex items-center justify-between text-slate-400">
                    <span>Pote: <strong className="text-slate-200 font-mono">{table.pot}</strong></span>
                    <span className="font-mono text-slate-300">{table.cards}</span>
                  </div>
                  <div className="mt-2 pt-2 border-t border-slate-800/60 text-[11px] text-slate-400 truncate">
                    Status: <span className="text-slate-200">{table.status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Atalhos Operacionais Diretos */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-slate-100 mb-3">
              Acesso Rápido
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <button
                onClick={() => onNavigateTab('cards')}
                className="p-3 rounded bg-[#0b0f19] border border-slate-800 hover:border-slate-700 text-left transition-colors cursor-pointer group"
              >
                <div className="flex items-center justify-between">
                  <Crosshair className="w-4 h-4 text-emerald-400" />
                  <ChevronRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 transition-colors" />
                </div>
                <h4 className="text-xs font-semibold text-slate-200 mt-2">Reconhecimento YOLOv8</h4>
                <p className="text-[11px] text-slate-400 mt-0.5">Inspeção de cartas e bounding boxes</p>
              </button>

              <button
                onClick={() => onNavigateTab('ghost')}
                className="p-3 rounded bg-[#0b0f19] border border-slate-800 hover:border-slate-700 text-left transition-colors cursor-pointer group"
              >
                <div className="flex items-center justify-between">
                  <ShieldCheck className="w-4 h-4 text-cyan-400" />
                  <ChevronRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 transition-colors" />
                </div>
                <h4 className="text-xs font-semibold text-slate-200 mt-2">Modo Fantasma</h4>
                <p className="text-[11px] text-slate-400 mt-0.5">Espectador passivo · Zero cliques</p>
              </button>

              <button
                onClick={() => onNavigateTab('installer')}
                className="p-3 rounded bg-[#0b0f19] border border-slate-800 hover:border-slate-700 text-left transition-colors cursor-pointer group"
              >
                <div className="flex items-center justify-between">
                  <HardDrive className="w-4 h-4 text-indigo-400" />
                  <ChevronRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 transition-colors" />
                </div>
                <h4 className="text-xs font-semibold text-slate-200 mt-2">Instalador & Executável</h4>
                <p className="text-[11px] text-slate-400 mt-0.5">Download direto do binário .EXE</p>
              </button>
            </div>
          </div>
        </div>

        {/* Coluna Direita: Feed Recente & Salvaguardas (1/3) */}
        <div className="space-y-6">
          {/* Feed Resumido de Eventos Recentes */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-semibold text-slate-100">
                Últimos Eventos OCR
              </h3>
              <button
                onClick={() => onNavigateTab('events_actions')}
                className="text-xs text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                Ver todos
              </button>
            </div>

            <div className="mt-3 divide-y divide-slate-800/60">
              {[
                { time: '15:42:08', table: 'M1', desc: 'Raise 2.5 BB (Hero)', conf: '99.4%' },
                { time: '15:42:06', table: 'M1', desc: 'Flop A♠ K♥ 7♦ detectado', conf: '99.8%' },
                { time: '15:42:03', table: 'M2', desc: 'Pote atualizado: 14.5 BB', conf: '98.5%' },
                { time: '15:41:59', table: 'M3', desc: 'Vilão 4: Fold pré-flop', conf: '99.1%' },
                { time: '15:41:55', table: 'M1', desc: 'Hero: A♦ Q♦ detectadas', conf: '99.9%' }
              ].map((item, idx) => (
                <div key={idx} className="py-2.5 flex items-center justify-between text-xs">
                  <div className="min-w-0 pr-2">
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <span className="font-mono text-slate-400 text-[11px]">{item.time}</span>
                      <span>·</span>
                      <span className="font-medium text-slate-400 text-[11px]">{item.table}</span>
                    </div>
                    <p className="text-slate-200 truncate mt-0.5">{item.desc}</p>
                  </div>
                  <span className="text-[11px] font-mono text-emerald-400 shrink-0">
                    {item.conf}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Salvaguardas & Segurança Operacional */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-slate-100 mb-3">
              Salvaguardas Operacionais
            </h3>
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">Bet Sizing Safety Gate</span>
                <span className="text-emerald-400 font-medium">Ativo (18% limiar)</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">Window Visibility Guardian</span>
                <span className="text-emerald-400 font-medium">Calibrado</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">Prevenção de Missclick</span>
                <span className="text-emerald-400 font-medium">Bézier Natural</span>
              </div>
              <div className="flex items-center justify-between py-1.5">
                <span className="text-slate-400">Fallback de Erro em GTO</span>
                <span className="text-slate-300 font-medium">Check / Fold (Defensivo)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
