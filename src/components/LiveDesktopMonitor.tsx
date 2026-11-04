import React, { useState, useEffect, useRef } from 'react';
import {
  Monitor,
  Activity,
  Wifi,
  WifiOff,
  RefreshCw,
  Play,
  Pause,
  AlertCircle,
  CheckCircle2,
  Sliders,
  Maximize2,
  HardDrive,
  Cpu,
  Layers,
  ArrowRight,
  Shield,
  Eye,
  Camera,
  ExternalLink,
  UploadCloud,
  FileCode2,
  Radio
} from 'lucide-react';

interface TelemetryData {
  status: string;
  timestamp: string;
  mode: string;
  hand_counter: number;
  fps: number;
  table_title: string;
  table_resolution: string;
  window_found: boolean;
  is_hero_turn: boolean;
  is_human_takeover: boolean;
  hero_cards: string[];
  board_cards: string[];
  pot_bb: number;
  hero_position: string;
  recommended_action: string;
  recommended_sizing_bb: number;
  equity_pct: number;
  ev_bb: number;
  target_button_label: string;
  last_frame_b64?: string | null;
  last_status_message?: string;
}

export const LiveDesktopMonitor: React.FC = () => {
  const [telemetryUrl, setTelemetryUrl] = useState<string>('http://localhost:8000');
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isSimulated, setIsSimulated] = useState<boolean>(false);
  const [isPolling, setIsPolling] = useState<boolean>(true);
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [isPausing, setIsPausing] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Polling da telemetria
  useEffect(() => {
    if (!isPolling || isSimulated) return;

    let isMounted = true;
    const fetchTelemetry = async () => {
      try {
        const cleanUrl = telemetryUrl.replace(/\/+$/, '');
        const res = await fetch(`${cleanUrl}/api/telemetry`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' },
          signal: AbortSignal.timeout(2000),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: TelemetryData = await res.json();

        if (isMounted) {
          setTelemetry(data);
          setIsConnected(true);
          setLastUpdated(new Date());
          setConnectionError(null);
        }
      } catch (err: any) {
        if (isMounted) {
          setIsConnected(false);
          setConnectionError('Não foi possível conectar ao servidor de telemetria (porta 8000). Verifique se o VisualPilot está aberto no PC.');
        }
      }
    };

    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 1200);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [telemetryUrl, isPolling, isSimulated]);

  // Modo de Demonstração / Simulação para teste imediato
  useEffect(() => {
    if (!isSimulated) return;

    const interval = setInterval(() => {
      setTelemetry((prev) => {
        const nextHand = (prev?.hand_counter || 10) + 1;
        return {
          status: 'RUNNING',
          timestamp: new Date().toISOString(),
          mode: 'spectator',
          hand_counter: nextHand,
          fps: 4.2,
          table_title: 'PPPoker - Mesa de Demonstração',
          table_resolution: '1920x1080',
          window_found: true,
          is_hero_turn: true,
          is_human_takeover: false,
          hero_cards: ['As', 'Kh'],
          board_cards: ['Qc', 'Jd', '10s'],
          pot_bb: 24.5,
          hero_position: 'BTN',
          recommended_action: 'RAISE',
          recommended_sizing_bb: 5.5,
          equity_pct: 78.4,
          ev_bb: +4.82,
          target_button_label: 'Raise 5.5 BB',
          last_status_message: 'Transmissão simulada ativa. Leitura de mesa e GTO em operação contínua.',
        };
      });
      setIsConnected(true);
      setLastUpdated(new Date());
      setConnectionError(null);
    }, 2000);

    return () => clearInterval(interval);
  }, [isSimulated]);

  // Carregar arquivo local de telemetria manual
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const content = event.target?.result as string;
        const parsed = JSON.parse(content);
        setTelemetry(parsed);
        setIsConnected(true);
        setLastUpdated(new Date());
        setConnectionError(null);
      } catch (err) {
        setConnectionError('Arquivo JSON de telemetria inválido.');
      }
    };
    reader.readAsText(file);
  };

  // Alternar pausa / takeover
  const handleToggleTakeover = async (pause: boolean) => {
    setIsPausing(true);
    try {
      if (isSimulated) {
        setTelemetry(prev => prev ? { ...prev, is_human_takeover: pause } : null);
        setIsPausing(false);
        return;
      }
      const cleanUrl = telemetryUrl.replace(/\/+$/, '');
      const endpoint = pause ? '/api/takeover/pause' : '/api/takeover/resume';
      await fetch(`${cleanUrl}${endpoint}`, { method: 'POST', signal: AbortSignal.timeout(2000) });
      setTelemetry(prev => prev ? { ...prev, is_human_takeover: pause } : null);
    } catch (err) {
      // Ignora erro
    } finally {
      setIsPausing(false);
    }
  };

  const formatCard = (c: string): { text: string; colorClass: string } => {
    if (!c || c.length < 2) {
      return { text: c || '??', colorClass: 'text-slate-200 bg-slate-800 border-slate-700' };
    }
    const rank = c.slice(0, -1).toUpperCase();
    const suit = c.slice(-1).toLowerCase();
    const suitSymbol: Record<string, string> = { s: '♠', h: '♥', d: '♦', c: '♣' };
    const suitColor: Record<string, string> = {
      s: 'text-slate-100 bg-slate-900 border-slate-700',
      h: 'text-rose-400 bg-rose-950/40 border-rose-800',
      d: 'text-blue-400 bg-blue-950/40 border-blue-800',
      c: 'text-emerald-400 bg-emerald-950/40 border-emerald-800',
    };
    return {
      text: `${rank}${suitSymbol[suit] || suit}`,
      colorClass: suitColor[suit] || 'text-slate-200 bg-slate-800 border-slate-700',
    };
  };

  return (
    <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-5 shadow-2xl space-y-6">
      {/* 1. Cabeçalho de Conexão e Transmissão */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-slate-100">
                Monitoramento Remoto da Mesa (Seu Computador)
              </h3>
              <span className={`px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase border ${
                isConnected
                  ? 'bg-emerald-950/50 text-emerald-300 border-emerald-700'
                  : 'bg-amber-950/40 text-amber-300 border-amber-800'
              }`}>
                {isConnected ? 'ONLINE · TRANSMISSÃO ATIVA' : 'AGUARDANDO ROBÔ NO PC'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Acompanhe em tempo real o cliente PPPoker, leitura de cartas por visão computacional e decisões do robô
            </p>
          </div>
        </div>

        {/* Controles de URL e Modo */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center bg-[#070b13] border border-slate-700 rounded-lg px-2.5 py-1 text-xs">
            <Wifi className={`w-3.5 h-3.5 mr-2 ${isConnected ? 'text-emerald-400' : 'text-slate-500'}`} />
            <input
              type="text"
              value={telemetryUrl}
              onChange={(e) => setTelemetryUrl(e.target.value)}
              placeholder="http://localhost:8000"
              className="bg-transparent text-slate-200 focus:outline-none w-44 font-mono text-xs"
            />
          </div>

          <button
            onClick={() => setIsSimulated(!isSimulated)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors cursor-pointer border ${
              isSimulated
                ? 'bg-indigo-600 text-white border-indigo-500'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
            }`}
          >
            {isSimulated ? '✓ Simulação Ativa' : 'Testar Simulação'}
          </button>

          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors cursor-pointer border border-slate-700"
            title="Carregar arquivo telemetry.json exportado pelo bot"
          >
            <UploadCloud className="w-3.5 h-3.5 inline mr-1.5" />
            Carregar JSON
          </button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".json"
            className="hidden"
          />
        </div>
      </div>

      {/* Alerta de Desconexão com Instrução Direta e Prática */}
      {!isConnected && (
        <div className="bg-amber-950/20 border border-amber-800/60 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <h4 className="font-semibold text-amber-200">
              Como conectar a mesa do seu computador a este navegador:
            </h4>
            <ol className="list-decimal list-inside text-slate-300 space-y-1">
              <li>No seu computador com o PPPoker, abra o executável <strong>VisualPilot.exe</strong> ou dê dois cliques em <strong>MENU_INICIAR.bat</strong>.</li>
              <li>Escolha a <strong>Opção [1] (Modo Fantasma)</strong> ou <strong>Opção [2] (Modo Ao Vivo)</strong>. O bot iniciará e abrirá automaticamente a porta 8000 para transmissão.</li>
              <li>Se você estiver abrindo este navegador em <strong>outro computador ou celular</strong> na mesma rede Wi-Fi, substitua <code className="text-amber-300">localhost</code> acima pelo IP do seu PC (ex: <code className="text-amber-300">http://192.168.1.15:8000</code>).</li>
            </ol>
            <p className="text-slate-400 pt-1">
              Dica: Você também pode clicar no botão <strong>"Testar Simulação"</strong> para validar imediatamente todos os painéis e o fluxo de dados.
            </p>
          </div>
        </div>
      )}

      {/* 2. Visualização Dividida: Tela da Mesa (Esquerda) + Decisão GTO (Direita) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Lado Esquerdo: Captura Visual da Janela PPPoker (5 Colunas) */}
        <div className="lg:col-span-5 bg-[#070b13] border border-slate-800 rounded-lg p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs text-slate-400 pb-2 border-b border-slate-800">
              <span className="flex items-center gap-1.5 font-medium text-slate-200">
                <Camera className="w-4 h-4 text-emerald-400" />
                Transmissão da Janela PPPoker
              </span>
              <span className="font-mono text-slate-400">
                {telemetry?.table_resolution || '1920x1080'} · {telemetry?.fps ? `${telemetry.fps} FPS` : '0.0 FPS'}
              </span>
            </div>

            {/* Quadro de Imagem da Mesa */}
            <div className="mt-3 relative aspect-[9/16] max-h-[380px] w-full bg-[#03060c] border border-slate-800/90 rounded-lg flex items-center justify-center overflow-hidden">
              {telemetry?.last_frame_b64 ? (
                <img
                  src={`data:image/jpeg;base64,${telemetry.last_frame_b64}`}
                  alt="Mesa PPPoker ao vivo"
                  className="w-full h-full object-contain"
                />
              ) : isConnected ? (
                <div className="text-center p-4 space-y-2">
                  <div className="w-12 h-12 rounded-full border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400 bg-emerald-500/5 animate-pulse">
                    <Monitor className="w-6 h-6" />
                  </div>
                  <h5 className="text-xs font-semibold text-slate-200">Janela PPPoker Conectada</h5>
                  <p className="text-[11px] text-slate-400 max-w-[220px] mx-auto">
                    {telemetry?.last_status_message || 'Aguardando o robô processar o próximo frame de mesa...'}
                  </p>
                </div>
              ) : (
                <div className="text-center p-4 space-y-2">
                  <Monitor className="w-10 h-10 text-slate-700 mx-auto" />
                  <p className="text-xs text-slate-500">Nenhuma transmissão recebida.</p>
                  <p className="text-[10px] text-slate-600">Inicie o robô no PC para ver a tela aqui.</p>
                </div>
              )}

              {/* Badge de status sobreposto */}
              {isConnected && (
                <div className="absolute top-2 left-2 bg-slate-950/80 backdrop-blur-sm border border-slate-700/80 rounded px-2 py-0.5 flex items-center gap-1.5 text-[10px] text-emerald-400 font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                  AO VIVO
                </div>
              )}
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
            <span>Janela: <strong className="text-slate-200">{telemetry?.table_title || 'PPPoker'}</strong></span>
            <span>Mãos: <strong className="text-slate-200 font-mono">#{telemetry?.hand_counter || 0}</strong></span>
          </div>
        </div>

        {/* Lado Direito: Análise da Mão, Cartas e Decisão GTO (7 Colunas) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Card Principal de Decisão */}
          <div className="bg-[#070b13] border border-slate-800 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">
                  Ação Calculada pelo Motor GTO
                </span>
                <div className="flex items-center gap-3 mt-1">
                  <span className={`text-2xl font-bold font-mono ${
                    telemetry?.recommended_action === 'FOLD'
                      ? 'text-rose-400'
                      : telemetry?.recommended_action === 'CALL'
                      ? 'text-amber-400'
                      : 'text-emerald-400'
                  }`}>
                    {telemetry?.recommended_action || 'AGUARDANDO MESA'}
                    {telemetry?.recommended_sizing_bb ? ` ${telemetry.recommended_sizing_bb} BB` : ''}
                  </span>
                  {telemetry?.target_button_label && (
                    <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-xs font-mono">
                      Botão: {telemetry.target_button_label}
                    </span>
                  )}
                </div>
              </div>

              {/* Botão de Intervenção Humana / Pausa */}
              {telemetry?.is_human_takeover ? (
                <button
                  onClick={() => handleToggleTakeover(false)}
                  disabled={isPausing}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow transition-colors cursor-pointer"
                >
                  <Play className="w-3.5 h-3.5" />
                  Retomar Bot
                </button>
              ) : (
                <button
                  onClick={() => handleToggleTakeover(true)}
                  disabled={isPausing}
                  className="px-3 py-1.5 rounded-lg bg-amber-600/80 hover:bg-amber-600 text-white text-xs font-semibold flex items-center gap-1.5 shadow transition-colors cursor-pointer"
                >
                  <Pause className="w-3.5 h-3.5" />
                  Assumir Controle Manual
                </button>
              )}
            </div>

            {/* Cartas do Hero e Cartas Comunitárias */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3 border-t border-slate-800">
              {/* Suas Cartas (Hero Cards) */}
              <div className="bg-[#0b0f19] border border-slate-800/80 rounded p-3">
                <span className="text-[11px] text-slate-400 font-medium">Suas Cartas (Hero) · Pos: {telemetry?.hero_position || 'BTN'}</span>
                <div className="flex items-center gap-2 mt-2">
                  {telemetry?.hero_cards && telemetry.hero_cards.length > 0 ? (
                    telemetry.hero_cards.map((c, i) => {
                      const cardObj = formatCard(c);
                      return (
                        <span
                          key={i}
                          className={`px-2.5 py-1 rounded border font-mono font-bold text-sm shadow-sm ${cardObj.colorClass}`}
                        >
                          {cardObj.text}
                        </span>
                      );
                    })
                  ) : (
                    <span className="text-xs text-slate-500 font-mono">Aguardando leitura...</span>
                  )}
                </div>
              </div>

              {/* Bordo (Board) */}
              <div className="bg-[#0b0f19] border border-slate-800/80 rounded p-3">
                <span className="text-[11px] text-slate-400 font-medium">Bordo (Flop / Turn / River)</span>
                <div className="flex items-center gap-1.5 mt-2">
                  {telemetry?.board_cards && telemetry.board_cards.length > 0 ? (
                    telemetry.board_cards.map((c, i) => {
                      const cardObj = formatCard(c);
                      return (
                        <span
                          key={i}
                          className={`px-2 py-1 rounded border font-mono font-bold text-xs shadow-sm ${cardObj.colorClass}`}
                        >
                          {cardObj.text}
                        </span>
                      );
                    })
                  ) : (
                    <span className="text-xs text-slate-500 font-mono">Pré-Flop (Sem cartas)</span>
                  )}
                </div>
              </div>
            </div>

            {/* Métricas Numéricas de Jogo */}
            <div className="grid grid-cols-3 gap-3 pt-2 text-center">
              <div className="bg-[#0b0f19] border border-slate-800/60 rounded p-2.5">
                <span className="text-[10px] text-slate-400 uppercase">Pote da Mesa</span>
                <p className="text-base font-bold text-slate-100 font-mono mt-0.5">
                  {telemetry?.pot_bb ? `${telemetry.pot_bb.toFixed(1)} BB` : '0.0 BB'}
                </p>
              </div>

              <div className="bg-[#0b0f19] border border-slate-800/60 rounded p-2.5">
                <span className="text-[10px] text-slate-400 uppercase">Equidade Estimada</span>
                <p className="text-base font-bold text-emerald-400 font-mono mt-0.5">
                  {telemetry?.equity_pct ? `${telemetry.equity_pct.toFixed(1)}%` : '0.0%'}
                </p>
              </div>

              <div className="bg-[#0b0f19] border border-slate-800/60 rounded p-2.5">
                <span className="text-[10px] text-slate-400 uppercase">Valor Esperado (EV)</span>
                <p className="text-base font-bold text-blue-400 font-mono mt-0.5">
                  {telemetry?.ev_bb ? `${telemetry.ev_bb > 0 ? '+' : ''}${telemetry.ev_bb.toFixed(2)} BB` : '0.00 BB'}
                </p>
              </div>
            </div>

            {/* Mensagem de status e auditoria */}
            <div className="bg-[#090d16] border border-slate-800/80 rounded p-3 text-xs text-slate-300">
              <div className="flex items-center justify-between text-slate-400 mb-1">
                <span>Registro de Atividade da Mesa:</span>
                <span className="font-mono text-[11px]">
                  {lastUpdated ? lastUpdated.toLocaleTimeString() : '--:--:--'}
                </span>
              </div>
              <p className="font-mono text-slate-200">
                {telemetry?.last_status_message || (isConnected ? 'Monitoramento em execução contínua.' : 'Aguardando inicialização do VisualPilot no computador.')}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
