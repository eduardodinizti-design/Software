import React, { useState } from 'react';
import {
  Keyboard,
  Play,
  Square,
  ShieldAlert,
  Layers,
  ChevronUp,
  ChevronDown,
  Info,
  X
} from 'lucide-react';
import { MainNavArea } from './AppNavigationSidebar';

interface HotkeyOverlayProps {
  isSessionActive: boolean;
  isHumanTakeover: boolean;
  currentArea: MainNavArea;
  onToggleSession: () => void;
  onToggleTakeover: () => void;
  onNavigateArea: (area: MainNavArea, subTab?: string) => void;
}

export const HotkeyOverlay: React.FC<HotkeyOverlayProps> = ({
  isSessionActive,
  isHumanTakeover,
  currentArea,
  onToggleSession,
  onToggleTakeover,
  onNavigateArea
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  const navShortcuts: { key: string; label: string; area: MainNavArea; subTab: string }[] = [
    { key: '1', label: 'Visão Geral', area: 'overview', subTab: 'overview' },
    { key: '2', label: 'Sessões', area: 'sessions', subTab: 'ghost' },
    { key: '3', label: 'Multi-Mesas', area: 'multitable', subTab: 'multitable' },
    { key: '4', label: 'OCR & Reconhecimento', area: 'ocr_recognition', subTab: 'cards' },
    { key: '5', label: 'Eventos & Ações', area: 'events_actions', subTab: 'ocr_feed' },
    { key: '6', label: 'Relatórios', area: 'reports', subTab: 'bot_brain' },
    { key: '7', label: 'Configurações', area: 'settings', subTab: 'installer' },
  ];

  return (
    <div className="relative">
      {/* Modal / Popover Expandido com Todos os Atalhos */}
      {isExpanded && (
        <div className="absolute bottom-full right-0 mb-3 w-80 sm:w-96 bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl p-4 z-50 text-xs text-slate-200 animate-in fade-in slide-in-from-bottom-2 duration-150">
          <div className="flex items-center justify-between pb-2.5 border-b border-slate-800">
            <div className="flex items-center gap-2 font-semibold text-slate-100">
              <Keyboard className="w-4 h-4 text-emerald-400" />
              <span>Atalhos de Teclado Globais</span>
            </div>
            <button
              onClick={() => setIsExpanded(false)}
              className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
              title="Fechar"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="py-3 space-y-3">
            {/* Controles Críticos de Operação */}
            <div>
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 block mb-1.5">
                Controles Críticos
              </span>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between p-1.5 rounded bg-slate-950/60 border border-slate-800">
                  <div className="flex items-center gap-2">
                    <kbd className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 font-mono text-[11px] font-bold text-slate-100 shadow-sm">
                      F5
                    </kbd>
                    <span>Iniciar / Parar Robô</span>
                  </div>
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                    isSessionActive ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-slate-800 text-slate-400'
                  }`}>
                    {isSessionActive ? 'RODANDO' : 'PARADO'}
                  </span>
                </div>

                <div className="flex items-center justify-between p-1.5 rounded bg-slate-950/60 border border-slate-800">
                  <div className="flex items-center gap-2">
                    <kbd className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 font-mono text-[11px] font-bold text-amber-300 shadow-sm">
                      F12
                    </kbd>
                    <span>Intervenção Humana (Takeover)</span>
                  </div>
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                    isHumanTakeover ? 'bg-amber-950 text-amber-300 border border-amber-800' : 'bg-slate-800 text-slate-400'
                  }`}>
                    {isHumanTakeover ? 'HUMANO ATIVO' : 'AUTÔNOMO'}
                  </span>
                </div>
              </div>
            </div>

            {/* Alternância Rápida de Abas Principais */}
            <div>
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 block mb-1.5">
                Alternar Áreas Principais (Teclas 1 a 7)
              </span>
              <div className="grid grid-cols-2 gap-1.5">
                {navShortcuts.map(item => {
                  const isCurrent = currentArea === item.area;
                  return (
                    <button
                      key={item.key}
                      onClick={() => {
                        onNavigateArea(item.area, item.subTab);
                        setIsExpanded(false);
                      }}
                      className={`flex items-center gap-2 p-1.5 rounded border text-left cursor-pointer transition-colors ${
                        isCurrent
                          ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                          : 'bg-slate-950/40 border-slate-800 hover:border-slate-700 text-slate-300 hover:text-slate-100'
                      }`}
                    >
                      <kbd className="px-1.5 py-0.2 rounded bg-slate-800 border border-slate-700 font-mono text-[10px] font-bold text-slate-200 shrink-0">
                        {item.key}
                      </kbd>
                      <span className="truncate text-[11px]">{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
            <span className="flex items-center gap-1">
              <Info className="w-3.5 h-3.5 text-slate-400" />
              Atalho rápido: <kbd className="px-1 py-0.2 font-mono bg-slate-800 rounded text-[10px]">?</kbd> para abrir/fechar
            </span>
          </div>
        </div>
      )}

      {/* Barra Compacta no Rodapé (Hotkey Overlay) */}
      <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-800 rounded-lg px-2.5 py-1 text-[11px] backdrop-blur-sm">
        <button
          onClick={() => setIsExpanded(prev => !prev)}
          className="flex items-center gap-1.5 text-slate-300 hover:text-slate-100 font-medium transition-colors cursor-pointer mr-1"
          title="Ver todos os atalhos de teclado (ou pressione ?)"
        >
          <Keyboard className="w-3.5 h-3.5 text-emerald-400" />
          <span className="hidden sm:inline">Atalhos:</span>
          {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
        </button>

        {/* F5 Shortcut Button */}
        <button
          onClick={onToggleSession}
          className={`flex items-center gap-1.5 px-2 py-0.5 rounded border cursor-pointer transition-colors ${
            isSessionActive
              ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300 hover:bg-emerald-900/60'
              : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
          title="Pressione F5 para iniciar ou parar o robô"
        >
          <kbd className="px-1 py-0.2 rounded bg-slate-800 border border-slate-700 font-mono text-[10px] font-bold text-slate-200">
            F5
          </kbd>
          <span className="font-medium hidden md:inline">
            {isSessionActive ? 'Parar Bot' : 'Iniciar Bot'}
          </span>
          <span className={`w-1.5 h-1.5 rounded-full ${isSessionActive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
        </button>

        {/* F12 Shortcut Button */}
        <button
          onClick={onToggleTakeover}
          className={`flex items-center gap-1.5 px-2 py-0.5 rounded border cursor-pointer transition-colors ${
            isHumanTakeover
              ? 'bg-amber-950/60 border-amber-500/50 text-amber-300 hover:bg-amber-900/60'
              : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
          title="Pressione F12 para assumir ou devolver o controle manual (Takeover)"
        >
          <kbd className="px-1 py-0.2 rounded bg-slate-800 border border-slate-700 font-mono text-[10px] font-bold text-amber-300">
            F12
          </kbd>
          <span className="font-medium hidden md:inline">Takeover</span>
          <span className={`w-1.5 h-1.5 rounded-full ${isHumanTakeover ? 'bg-amber-400 animate-ping' : 'bg-slate-500'}`} />
        </button>

        {/* 1-7 Tabs Shortcut Indicator */}
        <div className="hidden lg:flex items-center gap-1 pl-1 border-l border-slate-800 text-slate-400">
          <kbd className="px-1 py-0.2 rounded bg-slate-800 border border-slate-700 font-mono text-[10px] text-slate-300">
            1-7
          </kbd>
          <span className="text-[10px]">Abas</span>
        </div>
      </div>
    </div>
  );
};
