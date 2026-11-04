import React, { useState } from 'react';
import {
  LayoutDashboard,
  PlayCircle,
  Layers,
  ScanLine,
  Activity,
  BarChart3,
  Settings,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Crosshair,
  FileText,
  Download,
  AlertTriangle,
  Repeat,
  Eye,
  Sliders,
  TrendingUp,
  Cpu,
  MousePointerClick
} from 'lucide-react';

export type MainNavArea =
  | 'overview'
  | 'sessions'
  | 'multitable'
  | 'ocr_recognition'
  | 'events_actions'
  | 'reports'
  | 'settings';

interface AppNavigationSidebarProps {
  currentArea: MainNavArea;
  currentSubTab: string;
  onSelectArea: (area: MainNavArea, subTab?: string) => void;
  isSessionActive: boolean;
}

export const AppNavigationSidebar: React.FC<AppNavigationSidebarProps> = ({
  currentArea,
  currentSubTab,
  onSelectArea,
  isSessionActive
}) => {
  // Estado dos grupos expansíveis
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({
    sessions: true,
    ocr_recognition: true,
    events_actions: true,
    reports: false,
    settings: false
  });

  const toggleGroup = (key: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedGroups(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <aside className="w-full lg:w-64 bg-[#080c14] border border-slate-800/80 rounded-xl flex flex-col justify-between shrink-0 select-none lg:sticky lg:top-20 shadow-xl overflow-hidden">
      {/* Lista de Navegação Principal */}
      <div className="p-3 space-y-1 overflow-y-auto">
        {/* 1. Visão Geral */}
        <button
          onClick={() => onSelectArea('overview')}
          className={`w-full flex items-center gap-2.5 px-3 py-2 rounded text-xs font-medium transition-colors text-left cursor-pointer ${
            currentArea === 'overview'
              ? 'bg-slate-800 text-slate-100'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850/50'
          }`}
        >
          <LayoutDashboard className={`w-4 h-4 ${currentArea === 'overview' ? 'text-emerald-400' : 'text-slate-400'}`} />
          <span>Visão Geral</span>
        </button>

        {/* 2. Sessões (Expansível) */}
        <div>
          <div
            onClick={() => onSelectArea('sessions', 'session_ctrl')}
            className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs font-medium transition-colors cursor-pointer ${
              currentArea === 'sessions'
                ? 'bg-slate-800/80 text-slate-100'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850/50'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <PlayCircle className={`w-4 h-4 ${currentArea === 'sessions' ? 'text-emerald-400' : 'text-slate-400'}`} />
              <span>Sessões</span>
            </div>
            <button
              type="button"
              onClick={(e) => toggleGroup('sessions', e)}
              className="p-0.5 text-slate-500 hover:text-slate-300 transition-colors"
            >
              {expandedGroups.sessions ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
          </div>

          {expandedGroups.sessions && (
            <div className="ml-6 pl-2.5 my-1 space-y-0.5 border-l border-slate-800 text-xs">
              <button
                onClick={() => onSelectArea('sessions', 'session_ctrl')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'sessions' && (currentSubTab === 'session_ctrl' || !currentSubTab)
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Parâmetros da Sessão
              </button>
              <button
                onClick={() => onSelectArea('sessions', 'ghost')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'sessions' && currentSubTab === 'ghost'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Modo Fantasma (Espectador)
              </button>
              <button
                onClick={() => onSelectArea('sessions', 'preflop_gto')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'sessions' && currentSubTab === 'preflop_gto'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Motor de Decisão GTO
              </button>
              <button
                onClick={() => onSelectArea('sessions', 'orchestrator')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'sessions' && currentSubTab === 'orchestrator'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Orquestrador de Torneios
              </button>
            </div>
          )}
        </div>

        {/* 3. Monitoramento Multi-Mesas (Item Central sem subitens para foco rápido) */}
        <button
          onClick={() => onSelectArea('multitable')}
          className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs font-medium transition-colors text-left cursor-pointer ${
            currentArea === 'multitable'
              ? 'bg-slate-800 text-slate-100'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850/50'
          }`}
        >
          <div className="flex items-center gap-2.5">
            <Layers className={`w-4 h-4 ${currentArea === 'multitable' ? 'text-emerald-400' : 'text-slate-400'}`} />
            <span>Monitoramento Multi-Mesas</span>
          </div>
          <span className="text-[10px] font-mono text-slate-400">1-6</span>
        </button>

        {/* 4. OCR e Reconhecimento (Expansível) */}
        <div>
          <div
            onClick={() => onSelectArea('ocr_recognition', 'cards')}
            className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs font-medium transition-colors cursor-pointer ${
              currentArea === 'ocr_recognition'
                ? 'bg-slate-800/80 text-slate-100'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850/50'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <ScanLine className={`w-4 h-4 ${currentArea === 'ocr_recognition' ? 'text-emerald-400' : 'text-slate-400'}`} />
              <span>OCR e Reconhecimento</span>
            </div>
            <button
              type="button"
              onClick={(e) => toggleGroup('ocr_recognition', e)}
              className="p-0.5 text-slate-500 hover:text-slate-300 transition-colors"
            >
              {expandedGroups.ocr_recognition ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
          </div>

          {expandedGroups.ocr_recognition && (
            <div className="ml-6 pl-2.5 my-1 space-y-0.5 border-l border-slate-800 text-xs">
              <button
                onClick={() => onSelectArea('ocr_recognition', 'cards')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'ocr_recognition' && (currentSubTab === 'cards' || !currentSubTab)
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                YOLOv8 Nano (Cartas)
              </button>
              <button
                onClick={() => onSelectArea('ocr_recognition', 'table_numerical')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'ocr_recognition' && currentSubTab === 'table_numerical'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                OCR Numérico (Potes & Apostas)
              </button>
              <button
                onClick={() => onSelectArea('ocr_recognition', 'hero_actions')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'ocr_recognition' && currentSubTab === 'hero_actions'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Ações do Hero
              </button>
              <button
                onClick={() => onSelectArea('ocr_recognition', 'ocr')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'ocr_recognition' && currentSubTab === 'ocr'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Segmentação do Lobby
              </button>
            </div>
          )}
        </div>

        {/* 5. Eventos e Ações (Expansível) */}
        <div>
          <div
            onClick={() => onSelectArea('events_actions', 'ocr_feed')}
            className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs font-medium transition-colors cursor-pointer ${
              currentArea === 'events_actions'
                ? 'bg-slate-800/80 text-slate-100'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850/50'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <Activity className={`w-4 h-4 ${currentArea === 'events_actions' ? 'text-emerald-400' : 'text-slate-400'}`} />
              <span>Eventos e Ações</span>
            </div>
            <button
              type="button"
              onClick={(e) => toggleGroup('events_actions', e)}
              className="p-0.5 text-slate-500 hover:text-slate-300 transition-colors"
            >
              {expandedGroups.events_actions ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
          </div>

          {expandedGroups.events_actions && (
            <div className="ml-6 pl-2.5 my-1 space-y-0.5 border-l border-slate-800 text-xs">
              <button
                onClick={() => onSelectArea('events_actions', 'ocr_feed')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'events_actions' && (currentSubTab === 'ocr_feed' || !currentSubTab)
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Feed de Eventos OCR
              </button>
              <button
                onClick={() => onSelectArea('events_actions', 'audit')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'events_actions' && currentSubTab === 'audit'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Registro de Auditoria
              </button>
              <button
                onClick={() => onSelectArea('events_actions', 'clicker')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'events_actions' && currentSubTab === 'clicker'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Calibração de Cliques & DPI
              </button>
              <button
                onClick={() => onSelectArea('events_actions', 'alerts')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'events_actions' && currentSubTab === 'alerts'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Alertas e Anomalias
              </button>
            </div>
          )}
        </div>

        {/* 6. Relatórios (Expansível) */}
        <div>
          <div
            onClick={() => onSelectArea('reports', 'monthly_roi')}
            className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs font-medium transition-colors cursor-pointer ${
              currentArea === 'reports'
                ? 'bg-slate-800/80 text-slate-100'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850/50'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <BarChart3 className={`w-4 h-4 ${currentArea === 'reports' ? 'text-emerald-400' : 'text-slate-400'}`} />
              <span>Relatórios</span>
            </div>
            <button
              type="button"
              onClick={(e) => toggleGroup('reports', e)}
              className="p-0.5 text-slate-500 hover:text-slate-300 transition-colors"
            >
              {expandedGroups.reports ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
          </div>

          {expandedGroups.reports && (
            <div className="ml-6 pl-2.5 my-1 space-y-0.5 border-l border-slate-800 text-xs">
              <button
                onClick={() => onSelectArea('reports', 'monthly_roi')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer flex items-center justify-between ${
                  currentArea === 'reports' && (currentSubTab === 'monthly_roi' || !currentSubTab)
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>Estimativa de ROI Mensal</span>
                <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold">
                  RECHARTS
                </span>
              </button>
              <button
                onClick={() => onSelectArea('reports', 'tournament_profit')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'reports' && currentSubTab === 'tournament_profit'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Estimador de Fichas e Lucro
              </button>
              <button
                onClick={() => onSelectArea('reports', 'bot_brain')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'reports' && currentSubTab === 'bot_brain'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Evolução do Bot Brain
              </button>
            </div>
          )}
        </div>

        {/* 7. Configurações (Expansível) */}
        <div>
          <div
            onClick={() => onSelectArea('settings', 'installer')}
            className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs font-medium transition-colors cursor-pointer ${
              currentArea === 'settings'
                ? 'bg-slate-800/80 text-slate-100'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850/50'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <Settings className={`w-4 h-4 ${currentArea === 'settings' ? 'text-emerald-400' : 'text-slate-400'}`} />
              <span>Configurações</span>
            </div>
            <button
              type="button"
              onClick={(e) => toggleGroup('settings', e)}
              className="p-0.5 text-slate-500 hover:text-slate-300 transition-colors"
            >
              {expandedGroups.settings ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
          </div>

          {expandedGroups.settings && (
            <div className="ml-6 pl-2.5 my-1 space-y-0.5 border-l border-slate-800 text-xs">
              <button
                onClick={() => onSelectArea('settings', 'installer')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'settings' && (currentSubTab === 'installer' || !currentSubTab)
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Instalador & Executável (.EXE)
              </button>
              <button
                onClick={() => onSelectArea('settings', 'manual_facil')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'settings' && currentSubTab === 'manual_facil'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Manual de Instruções
              </button>
              <button
                onClick={() => onSelectArea('settings', 'deployment')}
                className={`w-full text-left py-1 px-2 rounded text-[11px] transition-colors cursor-pointer ${
                  currentArea === 'settings' && currentSubTab === 'deployment'
                    ? 'text-emerald-400 font-medium bg-emerald-500/10'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Guia de Arquitetura & Deploy
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Rodapé da Barra Lateral */}
      <div className="p-3 border-t border-slate-800/80 bg-[#06090f] text-[11px] text-slate-500">
        <div className="flex items-center justify-between">
          <span>VisualPilot v2.5.0</span>
          <span className="font-mono text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            SHA-256 OK
          </span>
        </div>
      </div>
    </aside>
  );
};
