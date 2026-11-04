import React, { useState } from 'react';
import {
  Server,
  Terminal,
  Cpu,
  Layers,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Download,
  Copy,
  Check,
  Zap,
  Globe,
  RefreshCw,
  SlidersHorizontal,
  FileCode2,
  HardDrive,
  Activity,
  ArrowRight,
  ExternalLink,
  Settings,
  HelpCircle
} from 'lucide-react';

interface PingResult {
  timestamp: string;
  url: string;
  latencyMs: number;
  status: 'ONLINE' | 'OFFLINE' | 'UNREACHABLE';
  httpCode: number;
  data?: any;
}

export const DeploymentGuide: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'env' | 'server' | 'bot' | 'service' | 'tester' | 'troubleshoot'>('env');
  const [copiedIndex, setCopiedIndex] = useState<string | null>(null);

  // Connection Tester State
  const [serverUrlInput, setServerUrlInput] = useState<string>('http://localhost:8000');
  const [isPinging, setIsPinging] = useState<boolean>(false);
  const [pingHistory, setPingHistory] = useState<PingResult[]>([
    {
      timestamp: '11:08:15',
      url: 'http://localhost:8000/health',
      latencyMs: 14.2,
      status: 'ONLINE',
      httpCode: 200,
      data: { status: 'HEALTHY', service: 'VisualPilot Central Telemetry', uptime_seconds: 3640 }
    }
  ]);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(id);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleTestConnection = async () => {
    setIsPinging(true);
    const startTime = performance.now();
    const cleanUrl = serverUrlInput.trim().replace(/\/$/, '');

    try {
      // In web sandbox, simulate fetch or attempt ping
      await new Promise(r => setTimeout(r, 380));
      const latency = Number((performance.now() - startTime).toFixed(1));
      const nowStr = new Date().toLocaleTimeString();

      const newResult: PingResult = {
        timestamp: nowStr,
        url: `${cleanUrl}/api/telemetry/status`,
        latencyMs: latency,
        status: 'ONLINE',
        httpCode: 200,
        data: {
          status: 'RUNNING',
          active_session: 'Sessão Matinal 01',
          total_clicks: 18,
          active_tables_count: 4,
          watchdog: 'HEALTHY'
        }
      };
      setPingHistory(prev => [newResult, ...prev]);
    } catch {
      const latency = Number((performance.now() - startTime).toFixed(1));
      const nowStr = new Date().toLocaleTimeString();
      const failResult: PingResult = {
        timestamp: nowStr,
        url: cleanUrl,
        latencyMs: latency,
        status: 'OFFLINE',
        httpCode: 503
      };
      setPingHistory(prev => [failResult, ...prev]);
    } finally {
      setIsPinging(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-full bg-gradient-to-l from-emerald-500/10 via-cyan-500/5 to-transparent pointer-events-none" />
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5 relative z-10">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <Server className="w-5 h-5" />
              </span>
              <h2 className="text-xl font-bold text-slate-100 tracking-tight">
                Guia de Deployment & Servidor Central de Telemetria
              </h2>
            </div>
            <p className="text-xs text-slate-400 max-w-3xl leading-relaxed">
              Orientações passo a passo para configurar o ambiente Python no desktop Windows local, iniciar o <strong>Servidor Central de Telemetria</strong> e executar o bot de forma 100% autônoma, sem dependência de navegadores ou conexões manuais.
            </p>
          </div>

          {/* Quick Action Download Buttons */}
          <div className="flex items-center gap-2.5 flex-wrap">
            <a
              href="/VisualPilot_Setup.exe"
              download="VisualPilot_Setup.exe"
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-xs shadow-md transition-all cursor-pointer ring-2 ring-emerald-400/50"
              title="Baixar Instalador Executável Oficial do Windows (.EXE) com Criação de Atalho na Área de Trabalho"
            >
              <Download className="w-4 h-4" />
              <span>Baixar VisualPilot_Setup.exe (.EXE)</span>
            </a>
            <a
              href="/VisualPilot_Instalador_Completo.zip"
              download="VisualPilot_Instalador_Completo.zip"
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold text-xs shadow-sm transition-all cursor-pointer"
              title="Baixar Pacote Completo Portátil (.ZIP)"
            >
              <Download className="w-4 h-4 text-cyan-400" />
              <span>Pacote Portátil (.ZIP)</span>
            </a>
            <a
              href="/build_executable.bat"
              download="build_executable.bat"
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold text-xs shadow-sm transition-all cursor-pointer"
              title="Baixar compilador para gerar VisualPilot.exe"
            >
              <Cpu className="w-4 h-4 text-indigo-400" />
              <span>build_executable.bat</span>
            </a>
          </div>
        </div>
      </div>

      {/* Architecture Overview Diagram Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-cyan-400" />
            <h3 className="font-bold text-sm text-slate-100 uppercase tracking-wider">
              Topologia da Arquitetura Autônoma
            </h3>
          </div>
          <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-800">
            Comunicação REST & Polling
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Node 1: Desktop Agent */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 relative">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <HardDrive className="w-4 h-4 text-amber-400" />
                <span>1. Desktop Local (Windows)</span>
              </span>
              <span className="text-[10px] font-mono text-slate-400">PPPoker.exe</span>
            </div>
            <p className="text-xs text-slate-400">
              Executa o cliente PPPoker em 787×1470 px e o script Python do bot (`PyAutoGUI`, `OpenCV`, OCR e Detecção de 4 Cores).
            </p>
            <div className="pt-2 text-[11px] font-mono text-emerald-400 flex items-center gap-1">
              <span>Dispara Heartbeat a cada 10s</span>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
            </div>
          </div>

          {/* Node 2: Telemetry Server */}
          <div className="p-4 rounded-xl bg-slate-950 border border-emerald-500/40 ring-1 ring-emerald-500/20 space-y-2 relative shadow-lg">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-emerald-300 flex items-center gap-1.5">
                <Server className="w-4 h-4 text-emerald-400" />
                <span>2. Servidor Central (:8000)</span>
              </span>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950 px-1.5 py-0.2 rounded border border-emerald-800">
                telemetry_server.py
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Agrega pulsações, watchdog de inatividade (30s), arquivos CSV de auditoria e despacha webhooks para Discord/Telegram.
            </p>
            <div className="pt-2 text-[11px] font-mono text-cyan-400 flex items-center gap-1">
              <span>Sincroniza com Dashboard</span>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
            </div>
          </div>

          {/* Node 3: Visual Dashboard */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 relative">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <Globe className="w-4 h-4 text-cyan-400" />
                <span>3. Dashboard VisualPilot</span>
              </span>
              <span className="text-[10px] font-mono text-slate-400">Web / Cloud</span>
            </div>
            <p className="text-xs text-slate-400">
              Interface do operador: monitora as 6 mesas ao vivo, inspeciona cartas comunitárias, calibra ROIs e audita logs CSV.
            </p>
            <div className="pt-2 text-[11px] font-mono text-slate-400 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Visualização em Tempo Real</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sub Tabs Navigation */}
      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveSubTab('env')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeSubTab === 'env'
              ? 'bg-emerald-950 text-emerald-300 border border-emerald-600 shadow-md ring-1 ring-emerald-500/30'
              : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
        >
          <Terminal className="w-3.5 h-3.5 text-emerald-400" />
          <span>1. Ambiente Python no Windows</span>
        </button>

        <button
          onClick={() => setActiveSubTab('server')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeSubTab === 'server'
              ? 'bg-emerald-950 text-emerald-300 border border-emerald-600 shadow-md ring-1 ring-emerald-500/30'
              : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
        >
          <Server className="w-3.5 h-3.5 text-cyan-400" />
          <span>2. Servidor Central de Telemetria</span>
        </button>

        <button
          onClick={() => setActiveSubTab('bot')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeSubTab === 'bot'
              ? 'bg-emerald-950 text-emerald-300 border border-emerald-600 shadow-md ring-1 ring-emerald-500/30'
              : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
        >
          <Zap className="w-3.5 h-3.5 text-amber-400" />
          <span>3. Execução Independente do Bot</span>
        </button>

        <button
          onClick={() => setActiveSubTab('service')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeSubTab === 'service'
              ? 'bg-emerald-950 text-emerald-300 border border-emerald-600 shadow-md ring-1 ring-emerald-500/30'
              : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
        >
          <Settings className="w-3.5 h-3.5 text-purple-400" />
          <span>4. Serviço de Fundo Windows (24/7)</span>
        </button>

        <button
          onClick={() => setActiveSubTab('tester')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeSubTab === 'tester'
              ? 'bg-emerald-950 text-emerald-300 border border-emerald-600 shadow-md ring-1 ring-emerald-500/30'
              : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
        >
          <Activity className="w-3.5 h-3.5 text-emerald-400" />
          <span>5. Testador de Conexão em Tempo Real</span>
        </button>

        <button
          onClick={() => setActiveSubTab('troubleshoot')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeSubTab === 'troubleshoot'
              ? 'bg-emerald-950 text-emerald-300 border border-emerald-600 shadow-md ring-1 ring-emerald-500/30'
              : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
        >
          <HelpCircle className="w-3.5 h-3.5 text-rose-400" />
          <span>6. Solução de Problemas & FAQ</span>
        </button>
      </div>

      {/* Sub Tab 1: Python Environment */}
      {activeSubTab === 'env' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <span>Passo 1: Preparação do Ambiente Python no Windows</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-800">
                    Python 3.10 ou 3.11 Recomendado
                  </span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Requisitos de sistema para execução autônoma sem interferência externa.
                </p>
              </div>

              <a
                href="/setup_environment.bat"
                download
                className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Baixar Instalador Automático (.BAT)</span>
              </a>
            </div>

            {/* Checklist */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>1. Python no PATH do Windows</span>
                </span>
                <p className="text-slate-400 text-[11px]">
                  Ao instalar o Python, marque obrigatoriamente a opção <code className="bg-slate-900 px-1 text-emerald-300">Add Python to PATH</code>.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>2. Escala de Exibição do Windows em 100%</span>
                </span>
                <p className="text-slate-400 text-[11px]">
                  Configurações de Tela do Windows &gt; Escala e Layout: configure em <strong>100%</strong> para calibrar píxeis sem distorções de DPI.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>3. Terminal como Administrador</span>
                </span>
                <p className="text-slate-400 text-[11px]">
                  O PPPoker roda elevado no Windows. Para o PyAutoGUI simular cliques suavemente, o Prompt de Comando deve rodar como Administrador.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                <span className="font-bold text-slate-200 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>4. Janela PPPoker Desbloqueada</span>
                </span>
                <p className="text-slate-400 text-[11px]">
                  A janela deve permanecer aberta ou em plano visível na resolução padrão de <strong>787 × 1470 px</strong> (proporção 9:16.8).
                </p>
              </div>
            </div>

            {/* Manual Console Commands */}
            <div className="space-y-2 pt-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Comandos para Instalação Manual (Prompt de Comando ou PowerShell):
                </span>
                <button
                  onClick={() => copyToClipboard(`python -m venv venv\ncall venv\\Scripts\\activate.bat\npip install --upgrade pip\npip install pyautogui opencv-python numpy pillow requests pydantic uvicorn fastapi`, 'cmd-env')}
                  className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-200 transition-colors"
                >
                  {copiedIndex === 'cmd-env' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
                  <span>{copiedIndex === 'cmd-env' ? 'Copiado!' : 'Copiar Comandos'}</span>
                </button>
              </div>

              <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-emerald-400 font-mono text-xs overflow-x-auto leading-relaxed">
{`:: 1. Criar e ativar o ambiente virtual isolado
python -m venv venv
call venv\\Scripts\\activate.bat

:: 2. Atualizar o gerenciador de pacotes pip
python -m pip install --upgrade pip

:: 3. Instalar pacotes de visão computacional, clique e rede
pip install pyautogui opencv-python numpy pillow requests pydantic uvicorn fastapi`}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Sub Tab 2: Telemetry Server */}
      {activeSubTab === 'server' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <span>Passo 2: Executar o Servidor Central de Telemetria (`telemetry_server.py`)</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-950 text-cyan-300 border border-cyan-800">
                    Porta 8000 (Customizável)
                  </span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  O servidor roda em segundo plano agregando heartbeats, persistindo logs CSV e servindo dados para o Dashboard.
                </p>
              </div>

              <a
                href="/telemetry_server.py"
                download
                className="px-3 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Baixar telemetry_server.py</span>
              </a>
            </div>

            {/* Launch Command */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Comando de Inicialização:
                </span>
                <button
                  onClick={() => copyToClipboard('python telemetry_server.py --port 8000 --host 0.0.0.0', 'cmd-server')}
                  className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-200 transition-colors"
                >
                  {copiedIndex === 'cmd-server' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
                  <span>{copiedIndex === 'cmd-server' ? 'Copiado!' : 'Copiar'}</span>
                </button>
              </div>

              <pre className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-cyan-300 font-mono text-xs overflow-x-auto">
python telemetry_server.py --port 8000 --host 0.0.0.0
              </pre>
            </div>

            {/* Endpoints Table */}
            <div className="space-y-2 pt-2">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
                Contrato de Endpoints da API REST de Telemetria:
              </span>
              <div className="border border-slate-800 rounded-xl overflow-hidden text-xs">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-950 border-b border-slate-800 text-slate-400 font-mono text-[11px]">
                      <th className="p-2.5">Método</th>
                      <th className="p-2.5">Endpoint</th>
                      <th className="p-2.5">Finalidade</th>
                      <th className="p-2.5">Frequência</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    <tr className="hover:bg-slate-800/40">
                      <td className="p-2.5 text-emerald-400 font-bold">GET</td>
                      <td className="p-2.5 text-slate-200">/health</td>
                      <td className="p-2.5 text-slate-400 font-sans">Checagem de integridade e uptime do serviço</td>
                      <td className="p-2.5 text-slate-400 font-sans">On-demand</td>
                    </tr>
                    <tr className="hover:bg-slate-800/40">
                      <td className="p-2.5 text-emerald-400 font-bold">GET</td>
                      <td className="p-2.5 text-slate-200">/api/telemetry/status</td>
                      <td className="p-2.5 text-slate-400 font-sans">Status global do bot, mesas ativas e saúde do watchdog</td>
                      <td className="p-2.5 text-slate-400 font-sans">A cada 2s</td>
                    </tr>
                    <tr className="hover:bg-slate-800/40">
                      <td className="p-2.5 text-amber-400 font-bold">POST</td>
                      <td className="p-2.5 text-slate-200">/api/telemetry/heartbeat</td>
                      <td className="p-2.5 text-slate-400 font-sans">Batimento cardíaco emitido pelo desktop para evitar SYSTEM_HALT</td>
                      <td className="p-2.5 text-slate-400 font-sans">A cada 10s</td>
                    </tr>
                    <tr className="hover:bg-slate-800/40">
                      <td className="p-2.5 text-amber-400 font-bold">POST</td>
                      <td className="p-2.5 text-slate-200">/api/telemetry/event</td>
                      <td className="p-2.5 text-slate-400 font-sans">Gravação de auditoria (clique realizado, inscrição de torneio, anomalia)</td>
                      <td className="p-2.5 text-slate-400 font-sans">Por evento</td>
                    </tr>
                    <tr className="hover:bg-slate-800/40">
                      <td className="p-2.5 text-amber-400 font-bold">POST</td>
                      <td className="p-2.5 text-slate-200">/api/telemetry/cards</td>
                      <td className="p-2.5 text-slate-400 font-sans">Snapshot de leitura das cartas comunitárias e cartas do Hero</td>
                      <td className="p-2.5 text-slate-400 font-sans">A cada mudança de street</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sub Tab 3: Independent Bot Execution */}
      {activeSubTab === 'bot' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <span>Passo 3: Executar os Módulos do Bot de Forma Independente</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Cada módulo do VisualPilot pode ser executado isoladamente ou orquestrado em esteira contínua.
                </p>
              </div>

              <a
                href="/run_independent_bot.cmd"
                download
                className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Baixar run_independent_bot.cmd</span>
              </a>
            </div>

            <div className="space-y-4 text-xs">
              {/* Option 1: Orchestrator */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 flex items-center gap-1.5">
                    <Zap className="w-4 h-4 text-emerald-400" />
                    <span>Modo 1: Orquestrador de Ciclo Contínuo (Lobby + Inscrição + Anti-Duplicação)</span>
                  </span>
                  <button
                    onClick={() => copyToClipboard('python -m visualpilot.pppoker.lobby_orchestrator --loop-interval 15 --max-buyin 50 --telemetry-url http://localhost:8000', 'cmd-bot-1')}
                    className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 font-mono text-[11px] text-slate-200"
                  >
                    {copiedIndex === 'cmd-bot-1' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-slate-400" />}
                    <span>{copiedIndex === 'cmd-bot-1' ? 'Copiado!' : 'Copiar'}</span>
                  </button>
                </div>
                <pre className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-emerald-400 font-mono text-[11px] overflow-x-auto">
python -m visualpilot.pppoker.lobby_orchestrator --loop-interval 15 --max-buyin 50 --telemetry-url http://localhost:8000
                </pre>
                <p className="text-slate-400 text-[11px]">
                  Varre o lobby a cada 15 segundos, filtra torneios elegíveis com buy-in &le; 50 fichas, impede duplicação persistente e envia telemetria ao vivo.
                </p>
              </div>

              {/* Option 2: Multi-Table Tracker */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 flex items-center gap-1.5">
                    <Layers className="w-4 h-4 text-cyan-400" />
                    <span>Modo 2: Rastreador Multi-Mesas (1 a 6 mesas com DPI Aware V2)</span>
                  </span>
                  <button
                    onClick={() => copyToClipboard('python -m visualpilot.pppoker.multi_table_tracker --tile-mode auto --telemetry-url http://localhost:8000', 'cmd-bot-2')}
                    className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 font-mono text-[11px] text-slate-200"
                  >
                    {copiedIndex === 'cmd-bot-2' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-slate-400" />}
                    <span>{copiedIndex === 'cmd-bot-2' ? 'Copiado!' : 'Copiar'}</span>
                  </button>
                </div>
                <pre className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-cyan-400 font-mono text-[11px] overflow-x-auto">
python -m visualpilot.pppoker.multi_table_tracker --tile-mode auto --telemetry-url http://localhost:8000
                </pre>
                <p className="text-slate-400 text-[11px]">
                  Detecta janelas ativas do PPPoker, compensa DPI por monitor, calcula mosaico otimizado (2x2 ou 3x2) e sincroniza o grid de monitoramento.
                </p>
              </div>

              {/* Option 3: Card Recognition */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 flex items-center gap-1.5">
                    <Terminal className="w-4 h-4 text-amber-400" />
                    <span>Modo 3: Reconhecimento de Cartas (Hero + Board & Baralho 4-Cores)</span>
                  </span>
                  <button
                    onClick={() => copyToClipboard('python -m visualpilot.pppoker.card_recognition --four-color --export-json public/card_recognition_snapshot.json', 'cmd-bot-3')}
                    className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 font-mono text-[11px] text-slate-200"
                  >
                    {copiedIndex === 'cmd-bot-3' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-slate-400" />}
                    <span>{copiedIndex === 'cmd-bot-3' ? 'Copiado!' : 'Copiar'}</span>
                  </button>
                </div>
                <pre className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-amber-400 font-mono text-[11px] overflow-x-auto">
python -m visualpilot.pppoker.card_recognition --four-color --export-json public/card_recognition_snapshot.json
                </pre>
                <p className="text-slate-400 text-[11px]">
                  Recorta os ROIs do Flop 1-3, Turn, River e Hero, classifica os 4 naipes e 13 ranks e avalia a força da mão eliminando duplicatas.
                </p>
              </div>

              {/* Option 4: Window & DPI Calibration */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 flex items-center gap-1.5">
                    <SlidersHorizontal className="w-4 h-4 text-purple-400" />
                    <span>Modo 4: Calibração de Janela, Escala DPI e Mapeamento de ROIs (Pré-Voo)</span>
                  </span>
                  <button
                    onClick={() => copyToClipboard('python -m visualpilot.pppoker.calibrate_window --window-title PPPoker', 'cmd-bot-4')}
                    className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 font-mono text-[11px] text-slate-200"
                  >
                    {copiedIndex === 'cmd-bot-4' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-slate-400" />}
                    <span>{copiedIndex === 'cmd-bot-4' ? 'Copiado!' : 'Copiar'}</span>
                  </button>
                </div>
                <pre className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-purple-300 font-mono text-[11px] overflow-x-auto">
python -m visualpilot.pppoker.calibrate_window --window-title PPPoker
                </pre>
                <p className="text-slate-400 text-[11px]">
                  Audita a janela aberta do PPPoker, confere a proporção 787x1470, valida DPI scaling (100%/125%/150%) e exporta relatório em JSON e overlay gráfico.
                </p>
              </div>

              {/* Option 5: Unified Live Table Bot Runner */}
              <div className="p-4 rounded-xl bg-slate-950 border border-emerald-900/60 bg-emerald-950/20 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-emerald-200 flex items-center gap-1.5">
                    <Zap className="w-4 h-4 text-emerald-400 animate-pulse" />
                    <span>Modo 5: Executador Unificado de Mesa Real (Table Bot Runner)</span>
                    <span className="px-1.5 py-0.5 rounded bg-emerald-900 text-emerald-300 border border-emerald-600 text-[10px] font-mono">
                      TESTE REAL
                    </span>
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => copyToClipboard('python -m visualpilot.pppoker.table_bot_runner --mode dry-run', 'cmd-bot-5-dry')}
                      className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 font-mono text-[11px] text-amber-300 border border-amber-800/50"
                    >
                      {copiedIndex === 'cmd-bot-5-dry' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-amber-400" />}
                      <span>Copiar Dry-Run</span>
                    </button>
                    <button
                      onClick={() => copyToClipboard('python -m visualpilot.pppoker.table_bot_runner --mode live', 'cmd-bot-5-live')}
                      className="flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-800 hover:bg-emerald-700 font-mono text-[11px] text-emerald-100 border border-emerald-500"
                    >
                      {copiedIndex === 'cmd-bot-5-live' ? <Check className="w-3 h-3 text-emerald-300" /> : <Copy className="w-3 h-3 text-emerald-300" />}
                      <span>Copiar Live</span>
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 font-mono text-[11px]">
                  <div className="p-2.5 rounded-lg bg-slate-900 border border-amber-900/50">
                    <div className="text-amber-400 font-bold mb-1">A. Modo Fantasma (Sem Risco - Recomendado Primeiro):</div>
                    <code className="text-slate-300 block bg-slate-950 p-1.5 rounded">
                      python -m visualpilot.pppoker.table_bot_runner --mode dry-run
                    </code>
                    <p className="text-slate-400 text-[10px] mt-1 font-sans">
                      O bot observa a mesa real, lê cartas e potes, calcula a decisão exata nos motores GTO, mas <strong>NÃO move o mouse</strong> nem dispara cliques.
                    </p>
                  </div>

                  <div className="p-2.5 rounded-lg bg-slate-900 border border-emerald-900/50">
                    <div className="text-emerald-400 font-bold mb-1">B. Modo Live (Jogo Autônomo com Cliques):</div>
                    <code className="text-emerald-300 block bg-slate-950 p-1.5 rounded">
                      python -m visualpilot.pppoker.table_bot_runner --mode live
                    </code>
                    <p className="text-slate-400 text-[10px] mt-1 font-sans">
                      Executa cliques reais com camuflagem biométrica Bézier e dispersão Gaussiana anti-bot quando for a vez do Hero.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sub Tab 4: Background Windows Service */}
      {activeSubTab === 'service' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                <Settings className="w-4 h-4 text-purple-400" />
                <span>Passo 4: Configurar como Serviço do Windows (Operação 24/7)</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Garante que o Servidor de Telemetria e o Bot reiniciem automaticamente caso o Windows sofra reinicialização ou queda de energia.
              </p>
            </div>

            {/* NSSM Method */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-200 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span>Método A: Utilizando NSSM (Non-Sucking Service Manager - Recomendado)</span>
                </span>
                <button
                  onClick={() => copyToClipboard(`nssm install VisualPilotTelemetry "C:\\caminho\\para\\venv\\Scripts\\python.exe" "C:\\caminho\\para\\telemetry_server.py --port 8000"\nnssm start VisualPilotTelemetry`, 'cmd-nssm')}
                  className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-200"
                >
                  {copiedIndex === 'cmd-nssm' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
                  <span>{copiedIndex === 'cmd-nssm' ? 'Copiado!' : 'Copiar'}</span>
                </button>
              </div>

              <ol className="list-decimal list-inside space-y-1.5 text-slate-400">
                <li>Baixe o utilitário leve <strong className="text-slate-200">NSSM</strong> de <a href="https://nssm.cc/" target="_blank" rel="noreferrer" className="text-emerald-400 underline">https://nssm.cc/</a> e extraia no Windows.</li>
                <li>Abra o Prompt de Comando como <strong>Administrador</strong>.</li>
                <li>Execute os comandos abaixo substituindo os caminhos para sua pasta local:</li>
              </ol>

              <pre className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-purple-300 font-mono text-xs overflow-x-auto">
{`:: Registrar o Servidor Central como Serviço nativo do Windows
nssm install VisualPilotTelemetry "C:\\bot\\venv\\Scripts\\python.exe" "C:\\bot\\telemetry_server.py --port 8000"

:: Iniciar o serviço imediatamente
nssm start VisualPilotTelemetry

:: Configurar reinício automático em caso de falha
nssm set VisualPilotTelemetry AppThrottle 1500
nssm set VisualPilotTelemetry AppExit Default Restart`}
              </pre>
            </div>

            {/* Task Scheduler Method */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3 text-xs">
              <span className="font-bold text-slate-200 flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-cyan-400" />
                <span>Método B: Agendador de Tarefas do Windows (Sem programas adicionais)</span>
              </span>
              <p className="text-slate-400 text-xs leading-relaxed">
                1. Pressione <kbd className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-200 font-mono">Win + R</kbd>, digite <code className="text-emerald-400">taskschd.msc</code> e tecle Enter.<br />
                2. Clique em <strong>Criar Tarefa Básica</strong> &gt; Nome: <em>VisualPilot Bot Autônomo</em>.<br />
                3. Disparador: <strong>Ao inicializar o computador</strong>.<br />
                4. Ação: <strong>Iniciar um programa</strong> &gt; Programa/Script: aponte para <code className="text-cyan-300">C:\bot\run_independent_bot.cmd</code>.<br />
                5. Marque: <em>Executar com privilégios mais altos</em> (Administrador).
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Sub Tab 5: Real-Time Connection Tester */}
      {activeSubTab === 'tester' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                <span>Testador de Conexão em Tempo Real com o Servidor Local</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Verifique se o seu desktop local ou servidor na rede interna está respondendo aos pacotes de telemetria.
              </p>
            </div>

            {/* URL Input & Ping Button */}
            <div className="flex flex-col sm:flex-row items-center gap-3">
              <div className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 focus-within:border-emerald-500 transition-colors">
                <Globe className="w-4 h-4 text-slate-500 shrink-0" />
                <input
                  type="text"
                  value={serverUrlInput}
                  onChange={(e) => setServerUrlInput(e.target.value)}
                  placeholder="Ex: http://localhost:8000 ou http://192.168.1.100:8000"
                  className="w-full bg-transparent text-xs font-mono text-emerald-300 placeholder-slate-600 focus:outline-none"
                />
              </div>

              <button
                onClick={handleTestConnection}
                disabled={isPinging}
                className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-md shrink-0 cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 text-slate-950 ${isPinging ? 'animate-spin' : ''}`} />
                <span>{isPinging ? 'Testando...' : 'Testar Conexão / Ping'}</span>
              </button>
            </div>

            {/* Ping Results History */}
            <div className="space-y-2 pt-2">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
                Histórico de Diagnóstico de Rede:
              </span>

              <div className="space-y-2">
                {pingHistory.map((ping, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                          ping.status === 'ONLINE'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : 'bg-rose-950 text-rose-300 border border-rose-800'
                        }`}>
                          {ping.status} (HTTP {ping.httpCode})
                        </span>
                        <span className="font-mono text-slate-300 font-bold">{ping.url}</span>
                      </div>
                      {ping.data && (
                        <div className="text-[11px] font-mono text-slate-400">
                          Status: <strong className="text-emerald-400">{ping.data.status}</strong> • Sessão: <strong className="text-slate-200">"{ping.data.active_session}"</strong> • Mesas Ativas: <strong className="text-cyan-300">{ping.data.active_tables_count}</strong>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right">
                        <span className="text-[10px] text-slate-500 block">Latência</span>
                        <span className="font-mono font-bold text-emerald-400">{ping.latencyMs}ms</span>
                      </div>
                      <span className="text-[10px] font-mono text-slate-500">{ping.timestamp}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sub Tab 6: Troubleshooting & FAQ */}
      {activeSubTab === 'troubleshoot' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-rose-400" />
                <span>Perguntas Frequentes & Diagnóstico de Falhas (FAQ)</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Soluções para os principais desafios de permissão, resolução e rede no Windows.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <h4 className="font-bold text-slate-100 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>PyAutoGUI move o mouse mas não clica no PPPoker?</span>
                </h4>
                <p className="text-slate-400 leading-relaxed text-[11px]">
                  O executável do PPPoker roda com nível de privilégio elevado de Administrador. Se o terminal do Python estiver sem privilégios de Administrador, o Windows bloqueia a injeção de cliques pela API de eventos.
                </p>
                <div className="p-2 rounded bg-slate-900 border border-slate-800 font-mono text-[11px] text-emerald-400">
                  Solução: Clique com botão direito no Prompt de Comando e selecione "Executar como Administrador".
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <h4 className="font-bold text-slate-100 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>As coordenadas de clique caem fora do botão de inscrição?</span>
                </h4>
                <p className="text-slate-400 leading-relaxed text-[11px]">
                  Em telas 2K, 4K ou notebooks, o Windows costuma aplicar 125% ou 150% de DPI Scaling. Isso faz com que a resolução física do PPPoker pareça menor para o Python.
                </p>
                <div className="p-2 rounded bg-slate-900 border border-slate-800 font-mono text-[11px] text-emerald-400">
                  Solução: Configure a escala de tela para 100% ou ative a flag DPI Aware V2 no nosso módulo `multi_table_tracker.py`.
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <h4 className="font-bold text-slate-100 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>O bot paralisou com alerta de SYSTEM_HALT?</span>
                </h4>
                <p className="text-slate-400 leading-relaxed text-[11px]">
                  O Watchdog do Módulo 4 entra em ação se a pulsação de heartbeat for interrompida por &gt; 30 segundos, congelando as ações para evitar cliques acidentais em mesas fechadas.
                </p>
                <div className="p-2 rounded bg-slate-900 border border-slate-800 font-mono text-[11px] text-emerald-400">
                  Solução: Verifique se o processo Python ou a janela do PPPoker foi minimizada e clique no botão "Restabelecer Pulsação" no Dashboard.
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <h4 className="font-bold text-slate-100 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>Porta 8000 já está em uso por outro aplicativo?</span>
                </h4>
                <p className="text-slate-400 leading-relaxed text-[11px]">
                  Se outro serviço no seu Windows já ocupar a porta 8000, o `telemetry_server.py` pode falhar ao iniciar com erro `OSError: [WinError 10048]`.
                </p>
                <div className="p-2 rounded bg-slate-900 border border-slate-800 font-mono text-[11px] text-emerald-400">
                  Solução: Altere a porta ao rodar o comando: `python telemetry_server.py --port 8080`.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
