import React from 'react';
import {
  Play,
  Pause,
  Square,
  Settings,
  Volume2,
  VolumeX,
  SlidersHorizontal,
  ChevronDown
} from 'lucide-react';

interface AppCleanHeaderProps {
  sessionName: string;
  isSessionActive: boolean;
  sessionPaused: boolean;
  onToggleSession: () => void;
  onPauseSession: () => void;
  onStopSession: () => void;
  onOpenSessionModal: () => void;
  onOpenSettings: () => void;
  soundEnabled: boolean;
  onToggleSound: () => void;
  pppokerConnected: boolean;
  pppokerPid: number | null;
}

export const AppCleanHeader: React.FC<AppCleanHeaderProps> = ({
  sessionName,
  isSessionActive,
  sessionPaused,
  onToggleSession,
  onPauseSession,
  onStopSession,
  onOpenSessionModal,
  onOpenSettings,
  soundEnabled,
  onToggleSound,
  pppokerConnected,
  pppokerPid
}) => {
  return (
    <header className="h-14 bg-[#080c14] border-b border-slate-800/80 px-5 flex items-center justify-between select-none z-30">
      {/* 1. Nome e Identidade VisualPilot + Sessão + Indicador de Conexão */}
      <div className="flex items-center gap-4">
        {/* Marca */}
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded bg-slate-800 border border-slate-700/80 flex items-center justify-center">
            <span className="font-mono font-bold text-xs text-emerald-400">VP</span>
          </div>
          <div>
            <span className="font-semibold text-sm tracking-tight text-slate-100">VisualPilot</span>
            <span className="text-[10px] text-slate-400 block -mt-1 font-mono">Enterprise</span>
          </div>
        </div>

        <div className="h-4 w-px bg-slate-800 hidden sm:block"></div>

        {/* Sessão Atualmente Selecionada */}
        <div className="flex items-center gap-2">
          <button
            onClick={onOpenSessionModal}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#0f172a] hover:bg-slate-800/80 border border-slate-800 text-xs text-slate-200 transition-colors cursor-pointer group"
            title="Clique para alterar parâmetros da sessão"
          >
            <span className="text-slate-400">Sessão:</span>
            <span className="font-medium text-slate-200">{sessionName || "Sessão Principal"}</span>
            <SlidersHorizontal className="w-3 h-3 text-slate-500 group-hover:text-slate-300 ml-0.5" />
          </button>

          {/* Status da Sessão (Ativa, Pausada ou Desconectada) */}
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium border border-slate-800 bg-[#0f172a]">
            <span className={`w-1.5 h-1.5 rounded-full ${
              isSessionActive && !sessionPaused
                ? 'bg-emerald-400'
                : isSessionActive && sessionPaused
                ? 'bg-amber-400'
                : 'bg-slate-500'
            }`} />
            <span className={
              isSessionActive && !sessionPaused
                ? 'text-emerald-400'
                : isSessionActive && sessionPaused
                ? 'text-amber-400'
                : 'text-slate-400'
            }>
              {isSessionActive && !sessionPaused ? 'Ativa' : isSessionActive && sessionPaused ? 'Pausada' : 'Desconectada'}
            </span>
          </div>

          {/* Indicador de Conexão com o Cliente PPPoker */}
          <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-400 pl-1">
            <span className={`w-1.5 h-1.5 rounded-full ${pppokerConnected ? 'bg-emerald-400' : 'bg-slate-600'}`} />
            <span>
              {pppokerConnected ? `PPPoker Online (PID #${pppokerPid || '8492'})` : 'PPPoker Offline'}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Área de Ações da Sessão + Atalhos de Configurações */}
      <div className="flex items-center gap-2">
        {/* Controles da Sessão (Iniciar, Pausar, Encerrar) Agrupados */}
        <div className="flex items-center bg-[#0f172a] border border-slate-800 rounded p-0.5">
          {!isSessionActive ? (
            <button
              onClick={onToggleSession}
              className="flex items-center gap-1.5 px-3 py-1 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-medium transition-colors cursor-pointer"
            >
              <Play className="w-3 h-3 fill-current" />
              <span>Iniciar Sessão</span>
            </button>
          ) : (
            <>
              {sessionPaused ? (
                <button
                  onClick={onPauseSession}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-medium transition-colors cursor-pointer"
                  title="Retomar processamento"
                >
                  <Play className="w-3 h-3 fill-current" />
                  <span className="hidden sm:inline">Retomar</span>
                </button>
              ) : (
                <button
                  onClick={onPauseSession}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-slate-800 text-amber-400 text-xs font-medium transition-colors cursor-pointer"
                  title="Pausar temporariamente"
                >
                  <Pause className="w-3 h-3" />
                  <span className="hidden sm:inline">Pausar</span>
                </button>
              )}

              <button
                onClick={onStopSession}
                className="flex items-center gap-1 px-2.5 py-1 rounded hover:bg-slate-800 text-slate-400 hover:text-rose-400 text-xs font-medium transition-colors cursor-pointer"
                title="Encerrar sessão"
              >
                <Square className="w-3 h-3" />
                <span className="hidden sm:inline">Encerrar</span>
              </button>
            </>
          )}
        </div>

        {/* Alternador de Áudio/Alarme Discreto */}
        <button
          onClick={onToggleSound}
          className="p-1.5 rounded hover:bg-slate-800/80 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          title={soundEnabled ? "Alarme sonoro ativo. Clique para silenciar." : "Alarme silenciado. Clique para ativar."}
        >
          {soundEnabled ? <Volume2 className="w-4 h-4 text-emerald-400" /> : <VolumeX className="w-4 h-4 text-slate-500" />}
        </button>

        {/* Acesso às Configurações */}
        <button
          onClick={onOpenSettings}
          className="p-1.5 rounded hover:bg-slate-800/80 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          title="Acessar Configurações e Instalação"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
