import React, { useState, useEffect } from 'react';
import { 
  LayoutDashboard, PlayCircle, Layers, ScanLine, Activity, BarChart3, Settings, 
  ChevronDown, ChevronRight, ShieldCheck, Crosshair, FileText, Download, 
  AlertTriangle, Repeat, Eye, Sliders, TrendingUp, Cpu, MousePointerClick,
  CheckCircle2, RefreshCw, Terminal, Play, Pause, Square, Zap
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'multitable' | 'monitor' | 'ocr' | 'actions' | 'reports' | 'settings'>('overview');
  const [isSessionActive, setIsSessionActive] = useState(false);
  const [sessionPaused, setSessionPaused] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [tablesCount, setTablesCount] = useState(4);
  const [fpsMode, setFpsMode] = useState<'adaptive' | 'fixed30' | 'fixed60'>('adaptive');

  useEffect(() => {
    let interval: any;
    if (isSessionActive && !sessionPaused) {
      interval = setInterval(() => {
        setElapsedSeconds(prev => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isSessionActive, sessionPaused]);

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    const h = Math.floor(m / 60);
    return `${h.toString().padStart(2, '0')}:${(m % 60).toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-none">
      {/* Top Header */}
      <header className="bg-[#0b0f19] border-b border-slate-800/80 px-6 py-3 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent">
              VisualPilot v2.5.0
            </h1>
            <p className="text-[11px] text-slate-400">Central Operacional de Poker Multi-Mesas (PPPoker Unity)</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 flex items-center gap-3 text-xs">
            <span className="text-slate-400">Tempo de Sessão:</span>
            <span className="font-mono font-semibold text-emerald-400">{formatTime(elapsedSeconds)}</span>
          </div>

          <button
            onClick={() => {
              if (!isSessionActive) {
                setIsSessionActive(true);
                setSessionPaused(false);
              } else {
                setSessionPaused(!sessionPaused);
              }
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold shadow-lg transition-all cursor-pointer ${
              isSessionActive && !sessionPaused
                ? 'bg-amber-600/20 border border-amber-500/40 text-amber-300 hover:bg-amber-600/30'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/30'
            }`}
          >
            {isSessionActive && !sessionPaused ? (
              <>
                <Pause className="w-4 h-4" /> Pausar Bot
              </>
            ) : (
              <>
                <Play className="w-4 h-4" /> {isSessionActive ? 'Retomar Bot' : 'Iniciar Bot & OCR'}
              </>
            )}
          </button>
        </div>
      </header>

      {/* Main Layout: Sidebar + Content */}
      <div className="flex flex-1 overflow-hidden p-4 gap-4 h-[calc(100vh-4.5rem)]">
        {/* Sidebar */}
        <aside className="w-64 shrink-0 bg-[#080c14] border border-slate-800/80 rounded-xl flex flex-col justify-between shadow-xl overflow-hidden">
          <div className="p-3 space-y-1 overflow-y-auto">
            <button
              onClick={() => setActiveTab('overview')}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                activeTab === 'overview' ? 'bg-slate-800 text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <LayoutDashboard className="w-4 h-4" />
              <span>Visão Geral</span>
            </button>

            <button
              onClick={() => setActiveTab('multitable')}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                activeTab === 'multitable' ? 'bg-slate-800 text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>Grid Multi-Mesas (Auto-Tiling)</span>
            </button>

            <button
              onClick={() => setActiveTab('monitor')}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                activeTab === 'monitor' ? 'bg-slate-800 text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Activity className="w-4 h-4" />
              <span>Monitor Unity & FPS Throttling</span>
            </button>

            <button
              onClick={() => setActiveTab('ocr')}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                activeTab === 'ocr' ? 'bg-slate-800 text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <ScanLine className="w-4 h-4" />
              <span>OCR & Cache Temporal</span>
            </button>

            <button
              onClick={() => setActiveTab('actions')}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                activeTab === 'actions' ? 'bg-slate-800 text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Cpu className="w-4 h-4" />
              <span>State Machine & Ações</span>
            </button>

            <button
              onClick={() => setActiveTab('reports')}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                activeTab === 'reports' ? 'bg-slate-800 text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              <span>Telemetria & Relatórios</span>
            </button>

            <button
              onClick={() => setActiveTab('settings')}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                activeTab === 'settings' ? 'bg-slate-800 text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Settings className="w-4 h-4" />
              <span>Configurações & Binário .EXE</span>
            </button>
          </div>

          <div className="p-3 border-t border-slate-800 bg-[#06090f] text-[11px] text-slate-500">
            <div className="flex items-center justify-between">
              <span>Engine Status</span>
              <span className="font-mono text-emerald-400 flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                ONLINE
              </span>
            </div>
          </div>
        </aside>

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto bg-slate-900/60 border border-slate-800/80 rounded-xl p-6 shadow-2xl">
          <div className="max-w-6xl mx-auto space-y-6">
            {activeTab === 'overview' && (
              <>
                <div className="bg-gradient-to-r from-slate-900 to-[#0f172a] border border-slate-800 rounded-xl p-6 shadow-lg">
                  <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                    <LayoutDashboard className="w-6 h-6 text-emerald-400" />
                    Central Operacional VisualPilot
                  </h2>
                  <p className="text-sm text-slate-400 mt-1">
                    Sistema distribuído de automação e rastreamento visual para PPPoker em alta resolução com identidade persistente e baixa carga de CPU/GPU.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mt-6">
                    <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-4">
                      <span className="text-xs text-slate-400">Mesas Rastradas</span>
                      <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">{tablesCount} Ativas</div>
                    </div>
                    <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-4">
                      <span className="text-xs text-slate-400">Throttling de FPS</span>
                      <div className="text-2xl font-bold font-mono text-cyan-400 mt-1">10 / 30 FPS</div>
                    </div>
                    <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-4">
                      <span className="text-xs text-slate-400">Confiabilidade OCR</span>
                      <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">99.4%</div>
                    </div>
                    <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-4">
                      <span className="text-xs text-slate-400">Estado de Ação</span>
                      <div className="text-xl font-bold font-mono text-amber-400 mt-1">SUA VEZ (4s)</div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-5">
                    <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
                      <Layers className="w-4 h-4 text-emerald-400" />
                      Auto-Tiling Dinâmico (Grid 2x2)
                    </h3>
                    <p className="text-xs text-slate-400 mb-4">
                      Organização automática em mosaico sem sobreposição para até 6+ mesas simultâneas.
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      {[1, 2, 3, 4].map(n => (
                        <div key={n} className="bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs">
                          <div className="flex justify-between font-mono text-slate-300">
                            <span>Mesa #{n}</span>
                            <span className="text-emerald-400">Rastreando</span>
                          </div>
                          <div className="mt-2 text-slate-400 text-[11px]">Pote: 18.5 BB · Stacks: 100BB</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-5">
                    <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
                      <ScanLine className="w-4 h-4 text-cyan-400" />
                      OCR com Cache Temporal & Limiar
                    </h3>
                    <p className="text-xs text-slate-400 mb-4">
                      Estabilização temporal exigindo leituras consistentes em múltiplos frames para evitar falsos positivos nas animações do dealer.
                    </p>
                    <div className="space-y-2 text-xs font-mono">
                      <div className="flex justify-between bg-slate-900 p-2 rounded border border-slate-800">
                        <span className="text-slate-300">Pote Total (Slot 1)</span>
                        <span className="text-emerald-400">14.5 BB (Estável - 3 frames)</span>
                      </div>
                      <div className="flex justify-between bg-slate-900 p-2 rounded border border-slate-800">
                        <span className="text-slate-300">Stack Hero (Seat 5)</span>
                        <span className="text-emerald-400">100.0 BB (Conf: 99.1%)</span>
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}

            {activeTab === 'multitable' && (
              <div className="space-y-6">
                <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-6">
                  <h2 className="text-lg font-bold text-slate-100 mb-2">Grid de Mosaico Automático (Auto-Tiling)</h2>
                  <p className="text-xs text-slate-400 mb-4">Gerenciamento dinâmico de coordenadas para 1 a 6+ mesas em paralelo.</p>
                  
                  <div className="flex gap-3 mb-6">
                    {[1, 2, 4, 6].map(count => (
                      <button
                        key={count}
                        onClick={() => setTablesCount(count)}
                        className={`px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
                          tablesCount === count ? 'bg-emerald-600 text-white' : 'bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800'
                        }`}
                      >
                        {count} Mesas Ativas
                      </button>
                    ))}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    {Array.from({ length: tablesCount }).map((_, idx) => (
                      <div key={idx} className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col justify-between h-44">
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="text-emerald-400 font-bold">MESA #{idx + 1} (NLH 200)</span>
                          <span className="bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/20">SUA VEZ (3.8s)</span>
                        </div>
                        <div className="text-center my-auto">
                          <div className="text-sm font-semibold text-slate-200">A♠ K♥ 7♦</div>
                          <div className="text-xs text-slate-400 mt-1">Pote: 24.5 BB · Aposta: 8.0 BB</div>
                        </div>
                        <div className="flex justify-between text-[11px] text-slate-500 font-mono">
                          <span>Pos: BTN</span>
                          <span>FPS: 30 (Ativo)</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'monitor' && (
              <div className="space-y-6">
                <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-6">
                  <h2 className="text-lg font-bold text-slate-100 mb-2">Throttling de FPS & Carga de CPU/GPU</h2>
                  <p className="text-xs text-slate-400 mb-6">Otimização inteligente de captura de quadros da Unity Surface para multi-mesas pesadas.</p>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                    <button
                      onClick={() => setFpsMode('adaptive')}
                      className={`p-4 rounded-xl border text-left cursor-pointer transition-all ${
                        fpsMode === 'adaptive' ? 'bg-emerald-500/10 border-emerald-500/50 text-slate-100' : 'bg-slate-950 border-slate-800 text-slate-400'
                      }`}
                    >
                      <div className="font-semibold text-xs text-emerald-400">Adaptativo Inteligente (Recomendado)</div>
                      <div className="text-[11px] text-slate-400 mt-1">10 FPS em mesas inativas, 30 FPS na vez de agir. Economia de 70% de GPU.</div>
                    </button>
                    <button
                      onClick={() => setFpsMode('fixed30')}
                      className={`p-4 rounded-xl border text-left cursor-pointer transition-all ${
                        fpsMode === 'fixed30' ? 'bg-cyan-500/10 border-cyan-500/50 text-slate-100' : 'bg-slate-950 border-slate-800 text-slate-400'
                      }`}
                    >
                      <div className="font-semibold text-xs text-cyan-400">Fixo 30 FPS</div>
                      <div className="text-[11px] text-slate-400 mt-1">Taxa constante em todas as mesas ativas.</div>
                    </button>
                    <button
                      onClick={() => setFpsMode('fixed60')}
                      className={`p-4 rounded-xl border text-left cursor-pointer transition-all ${
                        fpsMode === 'fixed60' ? 'bg-purple-500/10 border-purple-500/50 text-slate-100' : 'bg-slate-950 border-slate-800 text-slate-400'
                      }`}
                    >
                      <div className="font-semibold text-xs text-purple-400">Alta Performance (60 FPS)</div>
                      <div className="text-[11px] text-slate-400 mt-1">Para monitores de alta taxa de atualização.</div>
                    </button>
                  </div>

                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs text-slate-300 space-y-2">
                    <div className="flex justify-between"><span>Uso de CPU Estimado:</span><span className="text-emerald-400">4.2%</span></div>
                    <div className="flex justify-between"><span>Uso de GPU (UnityWndClass):</span><span className="text-emerald-400">12.5%</span></div>
                    <div className="flex justify-between"><span>Latência Média de Captura:</span><span className="text-cyan-400">4.8 ms</span></div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'ocr' && (
              <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-6">
                <h2 className="text-lg font-bold text-slate-100 mb-2">Filtro de Confiabilidade & Cache no OCR</h2>
                <p className="text-xs text-slate-400 mb-6">Validação de limiar de confiança e estabilização temporal de 2 frames consecutivos.</p>
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-slate-400">Limiar Mínimo de Confiança:</span>
                    <span className="text-emerald-400 font-bold">85.0%</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-slate-400">Frames Consecutivos Necessários:</span>
                    <span className="text-emerald-400 font-bold">2 Frames</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Filtro de Animação do Dealer:</span>
                    <span className="text-cyan-400 font-bold">Ativo (Rejeição de Ruído)</span>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'actions' && (
              <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-6">
                <h2 className="text-lg font-bold text-slate-100 mb-2">State Machine & Gerenciamento de Turno</h2>
                <p className="text-xs text-slate-400 mb-6">Estados granulares (SUA_VEZ, AGUARDANDO, ALL_IN, FOLD) com alerta de timeout.</p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <div className="text-xs text-slate-400 font-mono">Estado Atual</div>
                    <div className="text-xl font-bold text-amber-400 mt-1">SUA_VEZ (Urgente)</div>
                    <div className="text-xs text-slate-400 mt-2">Timeout em: <strong className="text-red-400 font-mono">3.8s</strong></div>
                  </div>
                  <div className="bg-slate-950 border border-slate-800 p-4 rounded-xl">
                    <div className="text-xs text-slate-400 font-mono">Ações Automáticas</div>
                    <div className="text-xl font-bold text-emerald-400 mt-1">Beziér Natural (2.5s)</div>
                    <div className="text-xs text-slate-400 mt-2">Prevenção Anti-Ban Ativa</div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'reports' && (
              <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-6">
                <h2 className="text-lg font-bold text-slate-100 mb-2">Telemetria e Histórico de Sessões (JSONL)</h2>
                <p className="text-xs text-slate-400 mb-6">Logs persistentes de todas as mãos, potes e decisões salvos automaticamente em <code className="text-emerald-400">logs/sessions/</code>.</p>
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs text-slate-300">
                  <div>[2026-11-03T20:21:00Z] TABLE_DETECTED (tbl-1) - Box: [100, 100, 700, 1400]</div>
                  <div>[2026-11-03T20:21:02Z] OCR_STABLE_READ (pot) - Value: 16.0 BB (Conf: 99.4%)</div>
                  <div>[2026-11-03T20:21:05Z] STATE_TRANSITION (tbl-1) -> SUA_VEZ (Timer: 15s)</div>
                </div>
              </div>
            )}

            {activeTab === 'settings' && (
              <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-6 space-y-6">
                <h2 className="text-lg font-bold text-slate-100">Instalador & Executável (.ZIP / .EXE)</h2>
                <p className="text-xs text-slate-400">Baixe o pacote distribuível completo com o motor Python, scripts `.bat`/`.sh` e dependências.</p>
                <a
                  href="/downloads/VisualPilot_Bot_v1.0.zip"
                  download
                  className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/30 transition-all cursor-pointer"
                >
                  <Download className="w-4 h-4" /> Baixar Pacote Executável (VisualPilot_Bot_v1.0.zip)
                </a>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
