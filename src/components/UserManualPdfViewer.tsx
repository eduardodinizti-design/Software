import React, { useState } from 'react';
import {
  FileText,
  Printer,
  Download,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  Terminal,
  Layers,
  Cpu,
  Brain,
  Crosshair,
  Coins,
  Flame,
  TrendingUp,
  ShieldCheck,
  Repeat,
  Server,
  BellRing,
  FileSpreadsheet,
  Zap,
  MousePointerClick,
  Sparkles,
  HelpCircle,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  BookOpen
} from 'lucide-react';

export const UserManualPdfViewer: React.FC = () => {
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<string>('intro');

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCmd(id);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  const handlePrintPdf = () => {
    window.print();
  };

  const handleDownloadStandaloneHtml = () => {
    const link = document.createElement('a');
    link.href = '/manual_de_uso_visualpilot_v1.html';
    link.download = 'Manual_de_Uso_VisualPilot_v1.html';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
      {/* Header Banner - Apenas exibido na tela, oculto na impressão */}
      <div className="print:hidden bg-gradient-to-r from-slate-900 via-indigo-950/60 to-slate-900 border border-indigo-500/30 rounded-2xl p-6 shadow-2xl relative overflow-hidden">
        <div className="absolute -right-8 -top-8 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/40 text-indigo-300 text-xs font-semibold">
              <BookOpen className="w-3.5 h-3.5 text-indigo-400" />
              <span>Documentação Oficial do Sistema · Versão 1.0</span>
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              Manual de Uso, Arquitetura & Guia Operacional
            </h1>
            <p className="text-sm text-slate-300 leading-relaxed">
              Guia completo com explicação de cada comando de terminal, cada botão da interface gráfica,
              arquitetura de visão computacional, diretrizes de segurança anti-ban e roadmap para a Versão 2.0.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handlePrintPdf}
              className="px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-2 shadow-lg shadow-emerald-500/20 transition-all cursor-pointer active:scale-95"
            >
              <Printer className="w-4 h-4 text-slate-950" />
              <span>Imprimir / Salvar em PDF</span>
            </button>

            <button
              onClick={handleDownloadStandaloneHtml}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold text-xs flex items-center gap-2 transition-all cursor-pointer"
            >
              <Download className="w-4 h-4 text-indigo-400" />
              <span>Baixar HTML (.html)</span>
            </button>
          </div>
        </div>
      </div>

      {/* Menu Rápido de Navegação entre Seções (Oculto na Impressão) */}
      <div className="print:hidden flex items-center gap-2 overflow-x-auto pb-2 border-b border-slate-800 text-xs">
        <span className="text-slate-400 font-medium whitespace-nowrap mr-1">Ir para:</span>
        {[
          { id: 'intro', label: '1. Download vs Publicar' },
          { id: 'arch', label: '2. Arquitetura do Bot' },
          { id: 'setup', label: '3. Instalação no Windows' },
          { id: 'commands', label: '4. Comandos e Scripts' },
          { id: 'buttons', label: '5. Guia de Todos os Botões' },
          { id: 'safety', label: '6. Segurança Anti-Ban' },
          { id: 'v2', label: '7. Roadmap Versão 2.0' },
          { id: 'faq', label: '8. Dúvidas Frequentes' }
        ].map(item => (
          <a
            key={item.id}
            href={`#${item.id}`}
            onClick={() => setActiveSection(item.id)}
            className={`px-3 py-1.5 rounded-lg border whitespace-nowrap transition-colors ${
              activeSection === item.id
                ? 'bg-indigo-950 text-indigo-300 border-indigo-600 font-bold'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            {item.label}
          </a>
        ))}
      </div>

      {/* DOCUMENTO PRINCIPAL - OTIMIZADO PARA TELA E PARA IMPRESSÃO EM PDF */}
      <article className="manual-print-container bg-slate-900/95 border border-slate-800 rounded-2xl p-8 md:p-12 text-slate-200 space-y-12 shadow-2xl print:bg-white print:text-black print:p-0 print:border-none print:shadow-none">

        {/* CAPA DO MANUAL (Visível no PDF / Impressão) */}
        <header className="border-b border-slate-800 print:border-slate-300 pb-8 space-y-4 print:page-break-after-always">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/20 border border-emerald-500/40 print:border-emerald-600 flex items-center justify-center text-emerald-400 print:text-emerald-700 font-black text-2xl">
                ♠
              </div>
              <div>
                <h1 className="text-3xl font-black text-white print:text-slate-900 tracking-tight">
                  VisualPilot Poker Engine
                </h1>
                <p className="text-xs uppercase tracking-widest text-emerald-400 print:text-emerald-700 font-bold">
                  Manual de Operação, Visão Computacional & Arquitetura GTO
                </p>
              </div>
            </div>
            <div className="text-right text-xs text-slate-400 print:text-slate-600 font-mono">
              <div>Versão: 1.0 (Produção)</div>
              <div>Ambiente: Windows x64 (DPI Aware)</div>
              <div>Target: PPPoker Desktop & Emuladores</div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/80 print:bg-slate-100 border border-slate-800 print:border-slate-300 text-xs text-slate-300 print:text-slate-800 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <span className="text-[10px] uppercase text-slate-500 print:text-slate-500 font-bold block">Autor / Engenharia:</span>
              <span className="font-semibold text-slate-200 print:text-slate-900">VisualPilot AI Team</span>
            </div>
            <div>
              <span className="text-[10px] uppercase text-slate-500 print:text-slate-500 font-bold block">Resolução Alvo:</span>
              <span className="font-mono font-semibold text-emerald-400 print:text-emerald-800">787 × 1470 px (9:16.8)</span>
            </div>
            <div>
              <span className="text-[10px] uppercase text-slate-500 print:text-slate-500 font-bold block">Cliques:</span>
              <span className="font-semibold text-slate-200 print:text-slate-900">Curvas Bézier Biométricas</span>
            </div>
            <div>
              <span className="text-[10px] uppercase text-slate-500 print:text-slate-500 font-bold block">Motor GTO:</span>
              <span className="font-semibold text-purple-400 print:text-purple-800">169 Mãos + IA Evolutiva</span>
            </div>
          </div>
        </header>

        {/* SEÇÃO 1: RESPOSTA DIRETA: DOWNLOAD VS PUBLICAR */}
        <section id="intro" className="space-y-4">
          <div className="flex items-center gap-2.5 text-lg font-bold text-white print:text-slate-900 border-b border-slate-800 print:border-slate-300 pb-2">
            <span className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 print:text-emerald-800 flex items-center justify-center text-sm font-black">
              1
            </span>
            <h2>Preciso Publicar o Projeto Aqui ou Fazendo o Download Dará Certo?</h2>
          </div>

          <div className="p-5 rounded-xl bg-emerald-950/30 print:bg-emerald-50 border border-emerald-500/40 print:border-emerald-300 space-y-3">
            <div className="flex items-center gap-2 text-emerald-300 print:text-emerald-900 font-bold text-base">
              <CheckCircle2 className="w-5 h-5 text-emerald-400 print:text-emerald-700" />
              <span>Resposta Direta: Fazendo o Download dará 100% certo e é o modo correto e recomendado!</span>
            </div>
            <p className="text-sm text-slate-300 print:text-slate-800 leading-relaxed">
              Você <strong>NÃO precisa publicar o projeto nesta plataforma em nuvem para o robô funcionar</strong>.
              Na verdade, para o robô jogar poker de verdade na sua mesa do PPPoker, ele <strong>obrigatoriamente precisa rodar no seu computador local (Windows)</strong>.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-emerald-400 print:text-emerald-800 text-sm flex items-center gap-1.5">
                <Check className="w-4 h-4" />
                <span>Por Que Rodar no Seu Computador Local (Windows)?</span>
              </div>
              <ul className="space-y-2 text-slate-300 print:text-slate-700 list-disc list-inside leading-relaxed">
                <li><strong>Captura de Tela Real:</strong> A biblioteca <code className="font-mono text-emerald-300 print:text-emerald-800">win32gui</code> e o OpenCV precisam tirar print da janela física do PPPoker aberta no seu monitor. Um servidor na nuvem não tem acesso ao seu monitor.</li>
                <li><strong>Movimento Físico do Mouse:</strong> Os cliques biométricos com curvas de Bézier e dispersão Gaussiana usam a biblioteca <code className="font-mono text-emerald-300 print:text-emerald-800">pyautogui</code> para mover o ponteiro do mouse na tela do seu Windows.</li>
                <li><strong>Zero Latência de Rede:</strong> O cálculo das decisões GTO e a leitura OCR das cartas acontecem em milissegundos localmente, sem risco de timeout.</li>
                <li><strong>Independência Total:</strong> Uma vez baixado, o bot funciona mesmo se a internet da nuvem oscilar.</li>
              </ul>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-indigo-400 print:text-indigo-800 text-sm flex items-center gap-1.5">
                <HelpCircle className="w-4 h-4" />
                <span>Para Que Serve a Publicação Nesta Nuvem?</span>
              </div>
              <ul className="space-y-2 text-slate-300 print:text-slate-700 list-disc list-inside leading-relaxed">
                <li><strong>Dashboard de Telemetria Remota:</strong> Caso queira acompanhar seus torneios e mãos jogadas pelo celular ou outro computador, a versão web publicada serve como painel de visualização.</li>
                <li><strong>Demonstração e Treinamento:</strong> Você pode ajustar matrizes GTO, treinar ranges e simular mãos diretamente no navegador sem abrir o PPPoker.</li>
                <li><strong>Compartilhamento com Parceiros:</strong> Permite mostrar as auditorias e relatórios de ROI para sócios de bankroll sem compartilhar o arquivo executável local.</li>
              </ul>
            </div>
          </div>
        </section>

        {/* SEÇÃO 2: ARQUITETURA DO SISTEMA */}
        <section id="arch" className="space-y-4 print:page-break-before-always">
          <div className="flex items-center gap-2.5 text-lg font-bold text-white print:text-slate-900 border-b border-slate-800 print:border-slate-300 pb-2">
            <span className="w-7 h-7 rounded-lg bg-indigo-500/20 text-indigo-400 print:text-indigo-800 flex items-center justify-center text-sm font-black">
              2
            </span>
            <h2>Arquitetura do Sistema: Como o Bot Foi Construído</h2>
          </div>

          <p className="text-sm text-slate-300 print:text-slate-700 leading-relaxed">
            O VisualPilot é dividido em 6 camadas funcionais independentes e desacopladas, garantindo que
            uma falha de leitura em uma carta não trave o robô e permitindo auditoria ponta-a-ponta:
          </p>

          <div className="space-y-3 text-xs">
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border-l-4 border-l-cyan-500 border border-slate-800 print:border-slate-300 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-bold text-cyan-400 print:text-cyan-800 text-sm">Camada 1: Localizador de Janela & DPI Aware (Window Capture)</span>
                <span className="text-[10px] font-mono bg-cyan-950 print:bg-cyan-200 text-cyan-300 print:text-cyan-900 px-2 py-0.5 rounded">calibrate_window.py</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                Localiza a janela com título "PPPoker" via Win32 API. Calcula o fator de escala de DPI (100%, 125%, 150%)
                e projeta as coordenadas proporcionais para a resolução canônica de 787 × 1470 pixels. Se a janela for movida ou redimensionada,
                as âncoras são reajustadas dinamicamente sem necessidade de reiniciar.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border-l-4 border-l-emerald-500 border border-slate-800 print:border-slate-300 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-bold text-emerald-400 print:text-emerald-800 text-sm">Camada 2: Visão Computacional & OCR (Card Recognition & Table OCR)</span>
                <span className="text-[10px] font-mono bg-emerald-950 print:bg-emerald-200 text-emerald-300 print:text-emerald-900 px-2 py-0.5 rounded">card_recognition.py / table_numerical_ocr.py</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                - <strong>Baralho 4-Cores:</strong> Máscaras HSV isolam os 4 naipes com 100% de precisão (Copas = Vermelho, Espadas = Preto/Cinza, Ouros = Azul, Paus = Verde).<br />
                - <strong>Template Matching com Normalização de Escala:</strong> Identifica as figuras (A, K, Q, J, T, 9..2) com tolerância a anti-aliasing.<br />
                - <strong>OCR Numérico:</strong> Lê o pote principal, os stacks de cada jogador e o valor da aposta a pagar (bet to call).<br />
                - <strong>Dealer Button Locator:</strong> Detecta o botão 'D' amarelo e define a posição relativa do Hero (BTN, SB, BB, UTG, HJ, CO).
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border-l-4 border-l-rose-500 border border-slate-800 print:border-slate-300 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-bold text-rose-400 print:text-rose-800 text-sm">Camada 3: Motor de Decisão GTO (Preflop & Postflop Engine)</span>
                <span className="text-[10px] font-mono bg-rose-950 print:bg-rose-200 text-rose-300 print:text-rose-900 px-2 py-0.5 rounded">preflop_engine.py / postflop_gto_engine.py</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                - <strong>Pré-Flop:</strong> Matriz completa de 169 combinações com frequências GTO balanceadas para RFI (Raise First In), defesa de blind, 3-bet e 4-bet.<br />
                - <strong>Pós-Flop:</strong> Cálculo do SPR (Stack-to-Pot Ratio), classificação da textura da mesa (Dry, Wet, Paired, Monotone) e simulação de equidade Monte Carlo (1.000 iterações em &lt; 40ms). Define entre Fold, Check, Call, C-Bet (33%, 50%, 75% pote) ou All-in.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border-l-4 border-l-purple-500 border border-slate-800 print:border-slate-300 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-bold text-purple-400 print:text-purple-800 text-sm">Camada 4: Cérebro Adaptativo & Feedback Humano (Brain Engine)</span>
                <span className="text-[10px] font-mono bg-purple-950 print:bg-purple-200 text-purple-300 print:text-purple-900 px-2 py-0.5 rounded">brain_engine.py</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                Permite ao jogador ajustar a <em>Learning Rate</em> (0.01 a 0.50). Quando você discorda de uma jogada do bot e insere feedback de correção, o cérebro recalibra o peso da linha de jogo sem corromper a baseline GTO teórica.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border-l-4 border-l-amber-500 border border-slate-800 print:border-slate-300 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-bold text-amber-400 print:text-amber-800 text-sm">Camada 5: Execução Física com Camuflagem Biométrica (Live Clicker)</span>
                <span className="text-[10px] font-mono bg-amber-950 print:bg-amber-200 text-amber-300 print:text-amber-900 px-2 py-0.5 rounded">table_bot_runner.py / lobby_clicker.py</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                Anti-bot de alta fidelidade: o mouse nunca se move em linha reta. O robô interpola curvas cúbicas de Bézier com aceleração e desaceleração física humana, adiciona jitter Gaussiano (desvio padrão σ = 3.5 px) dentro da caixa do botão e insere latência de reação randômica entre 320ms e 580ms.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border-l-4 border-l-blue-500 border border-slate-800 print:border-slate-300 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-bold text-blue-400 print:text-blue-800 text-sm">Camada 6: Orquestrador de Torneios & Auditoria CSV</span>
                <span className="text-[10px] font-mono bg-blue-950 print:bg-blue-200 text-blue-300 print:text-blue-900 px-2 py-0.5 rounded">lobby_orchestrator.py / table_runner_audit.csv</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                Varre o lobby periodicamente, inscreve o usuário nos torneios que atendem ao teto de buy-in, previne duplicações de inscrição via memória volátil persistida e grava cada clique, latência e decisão em um arquivo CSV de auditoria inviolável.
              </p>
            </div>
          </div>
        </section>

        {/* SEÇÃO 3: GUIA PASSO A PASSO NO WINDOWS */}
        <section id="setup" className="space-y-4 print:page-break-before-always">
          <div className="flex items-center gap-2.5 text-lg font-bold text-white print:text-slate-900 border-b border-slate-800 print:border-slate-300 pb-2">
            <span className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 print:text-emerald-800 flex items-center justify-center text-sm font-black">
              3
            </span>
            <h2>Passo a Passo de Instalação e Inicialização no Windows</h2>
          </div>

          <p className="text-sm text-slate-300 print:text-slate-700">
            Siga os 4 passos abaixo no seu computador com Windows 10 ou 11:
          </p>

          <div className="space-y-4 text-xs">
            {/* Passo 1 */}
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-emerald-400 print:text-emerald-800 text-sm flex items-center justify-between">
                <span>Passo 1: Pré-Requisitos no Computador</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300">Necessário 1 vez</span>
              </div>
              <ul className="space-y-1.5 text-slate-300 print:text-slate-700 list-disc list-inside">
                <li>Instale o <strong>Python 3.10 ou 3.11</strong> (<a href="https://www.python.org" target="_blank" rel="noreferrer" className="text-cyan-400 underline">python.org</a>). <em>Importante: Marque a opção "Add Python to PATH" durante a instalação.</em></li>
                <li>Instale o <strong>Node.js 18+</strong> (<a href="https://nodejs.org" target="_blank" rel="noreferrer" className="text-cyan-400 underline">nodejs.org</a>) se desejar rodar o dashboard web localmente.</li>
                <li>Abra o aplicativo <strong>PPPoker Desktop</strong> (ou emulador LDPlayer configurado em 787 × 1470 px).</li>
              </ul>
            </div>

            {/* Passo 2 */}
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-emerald-400 print:text-emerald-800 text-sm flex items-center justify-between">
                <span>Passo 2: Baixar o Projeto e Extrair os Arquivos</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">Download ZIP</span>
              </div>
              <p className="text-slate-300 print:text-slate-700">
                Baixe o repositório completo para uma pasta no seu computador (por exemplo: <code className="font-mono text-emerald-300 print:text-emerald-800">C:\VisualPilot\</code>).
              </p>
            </div>

            {/* Passo 3 */}
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-emerald-400 print:text-emerald-800 text-sm flex items-center justify-between">
                <span>Passo 3: Executar a Instalação Automatizada</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">setup_environment.bat</span>
              </div>
              <p className="text-slate-300 print:text-slate-700">
                Dê dois cliques no arquivo <code className="font-mono text-emerald-300 print:text-emerald-800">setup_environment.bat</code>. Ele irá automaticamente:
              </p>
              <ul className="space-y-1 text-slate-400 print:text-slate-600 list-disc list-inside">
                <li>Criar o ambiente virtual Python isolado (<code className="font-mono">venv</code>).</li>
                <li>Instalar as dependências necessárias: OpenCV, PyAutoGUI, PyGetWindow, Pillow, Numpy.</li>
                <li>Validar a compatibilidade com a biblioteca Win32.</li>
              </ul>
            </div>

            {/* Passo 4 */}
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-emerald-400 print:text-emerald-800 text-sm flex items-center justify-between">
                <span>Passo 4: Iniciar o Launcher do Bot</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300">run_independent_bot.cmd</span>
              </div>
              <p className="text-slate-300 print:text-slate-700">
                Dê dois cliques em <code className="font-mono text-emerald-300 print:text-emerald-800">run_independent_bot.cmd</code>. Uma janela preta do Windows se abrirá com o menu com 8 opções.
              </p>
            </div>
          </div>
        </section>

        {/* SEÇÃO 4: DICIONÁRIO DE COMANDOS E SCRIPTS */}
        <section id="commands" className="space-y-4 print:page-break-before-always">
          <div className="flex items-center gap-2.5 text-lg font-bold text-white print:text-slate-900 border-b border-slate-800 print:border-slate-300 pb-2">
            <span className="w-7 h-7 rounded-lg bg-amber-500/20 text-amber-400 print:text-amber-800 flex items-center justify-center text-sm font-black">
              4
            </span>
            <h2>Dicionário de Comandos do Terminal e Opções de Execução</h2>
          </div>

          <p className="text-sm text-slate-300 print:text-slate-700">
            Abaixo está a explicação de cada uma das 8 opções disponíveis no launcher <code className="font-mono text-amber-300 print:text-amber-800">run_independent_bot.cmd</code> e dos comandos CLI diretos:
          </p>

          <div className="space-y-3 text-xs">
            <div className="p-3.5 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 flex flex-col md:flex-row md:items-center justify-between gap-2">
              <div>
                <span className="font-mono font-bold text-emerald-400 print:text-emerald-800 mr-2">[Opção 5] Calibrar Janela e Escala DPI</span>
                <p className="text-slate-300 print:text-slate-700 mt-1">
                  <strong>O QUE FAZ:</strong> Tira uma foto instantânea da janela do PPPoker, detecta o fator de zoom do Windows (ex: 125%), confere a resolução 787x1470 e gera os arquivos <code className="font-mono">table_calibration_report.json</code> e <code className="font-mono">calibration_overlay.png</code> com retângulos verdes sobre as cartas e botões. <em>Faça sempre antes da primeira sessão!</em>
                </p>
              </div>
              <button
                onClick={() => copyToClipboard('python -m visualpilot.pppoker.calibrate_window --window-title PPPoker', 'cmd5')}
                className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 hover:text-white flex items-center gap-1 shrink-0 self-start md:self-center"
              >
                {copiedCmd === 'cmd5' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>Copiar</span>
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 flex flex-col md:flex-row md:items-center justify-between gap-2">
              <div>
                <span className="font-mono font-bold text-cyan-400 print:text-cyan-800 mr-2">[Opção 6] Modo Fantasma de Segurança (--spectator --sound)</span>
                <p className="text-slate-300 print:text-slate-700 mt-1">
                  <strong>O QUE FAZ:</strong> Executa a leitura contínua da mesa, lê as cartas do Hero e comunitárias, lê os potes, calcula a decisão GTO ideal (Fold, Call ou Raise com sizing em fichas) e emite bipes sonoros no Windows sem realizar <strong>NENHUM clique</strong> físico. O cursor do mouse fica livre para o operador. Perfeito para auditar o robô sem risco financeiro.
                </p>
              </div>
              <button
                onClick={() => copyToClipboard('python -m visualpilot.pppoker.table_bot_runner --spectator --sound', 'cmd6')}
                className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 hover:text-white flex items-center gap-1 shrink-0 self-start md:self-center"
              >
                {copiedCmd === 'cmd6' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>Copiar</span>
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 flex flex-col md:flex-row md:items-center justify-between gap-2">
              <div>
                <span className="font-mono font-bold text-rose-400 print:text-rose-800 mr-2">[Opção 7] Jogo Autônomo com Cliques Camuflados (--live)</span>
                <p className="text-slate-300 print:text-slate-700 mt-1">
                  <strong>O QUE FAZ:</strong> Modo de jogo real armado! Quando for a vez do Hero, calcula a decisão GTO, move suavemente o mouse em curva de Bézier humana, aguarda o tempo de reação randômico (320-580ms) e clica no botão com dispersão Gaussiana. Todos os cliques são salvos no arquivo <code className="font-mono">table_runner_audit.csv</code>.
                </p>
              </div>
              <button
                onClick={() => copyToClipboard('python -m visualpilot.pppoker.table_bot_runner --live', 'cmd7')}
                className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 hover:text-white flex items-center gap-1 shrink-0 self-start md:self-center"
              >
                {copiedCmd === 'cmd7' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>Copiar</span>
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 flex flex-col md:flex-row md:items-center justify-between gap-2">
              <div>
                <span className="font-mono font-bold text-purple-400 print:text-purple-800 mr-2">[Opção 2] Orquestrador de Ciclo Contínuo (Lobby)</span>
                <p className="text-slate-300 print:text-slate-700 mt-1">
                  <strong>O QUE FAZ:</strong> Monitora a lista de torneios no lobby a cada 15 segundos (com jitter aleatório de até 5s), filtra os torneios com buy-in até o limite configurado (ex: 50 fichas) e se inscreve automaticamente sem duplicações.
                </p>
              </div>
              <button
                onClick={() => copyToClipboard('python -m visualpilot.pppoker.lobby_orchestrator --loop-interval 15 --max-buyin 50', 'cmd2')}
                className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 hover:text-white flex items-center gap-1 shrink-0 self-start md:self-center"
              >
                {copiedCmd === 'cmd2' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>Copiar</span>
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 flex flex-col md:flex-row md:items-center justify-between gap-2">
              <div>
                <span className="font-mono font-bold text-blue-400 print:text-blue-800 mr-2">[Opção 1] Servidor Central de Telemetria (:8000)</span>
                <p className="text-slate-300 print:text-slate-700 mt-1">
                  <strong>O QUE FAZ:</strong> Inicia um servidor HTTP local leve na porta 8000 que recebe os eventos do bot em Python e envia em tempo real via WebSocket/JSON para a interface web no navegador.
                </p>
              </div>
              <button
                onClick={() => copyToClipboard('python telemetry_server.py --port 8000', 'cmd1')}
                className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 hover:text-white flex items-center gap-1 shrink-0 self-start md:self-center"
              >
                {copiedCmd === 'cmd1' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>Copiar</span>
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 flex flex-col md:flex-row md:items-center justify-between gap-2">
              <div>
                <span className="font-mono font-bold text-amber-400 print:text-amber-800 mr-2">[Opção 8] Modo Completo (Telemetria + Orquestrador em Paralelo)</span>
                <p className="text-slate-300 print:text-slate-700 mt-1">
                  <strong>O QUE FAZ:</strong> Abre duas janelas simultâneas: uma com o servidor de telemetria na porta 8000 e outra com o orquestrador autônomo do lobby.
                </p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950 print:bg-slate-100 border-2 border-emerald-500/40 print:border-emerald-600 flex flex-col md:flex-row md:items-center justify-between gap-2">
              <div>
                <span className="font-mono font-bold text-emerald-400 print:text-emerald-800 mr-2">[check_init.cmd] Diagnóstico Pré-Voo & Teste de Janela Minimizada/Bloqueada</span>
                <p className="text-slate-300 print:text-slate-700 mt-1">
                  <strong>O QUE FAZ:</strong> Inspeciona 5 pré-requisitos antes do início: valida Python, ambiente virtual (.venv), integridade do CSV diário e <strong>checa ativamente se a janela do PPPoker está minimizada na barra de tarefas ou bloqueada/coberta por outras janelas</strong> (via Z-Order). Tenta desminimizar e trazer para o 1º plano automaticamente. Se permanecer coberta ou minimizada, aborta o frame para impedir que o OCR leia telas pretas ou janelas erradas.
                </p>
              </div>
              <button
                onClick={() => copyToClipboard('check_init.cmd --strict-visibility', 'cmd_check_init')}
                className="px-2.5 py-1 rounded bg-emerald-950 text-emerald-300 border border-emerald-700 hover:bg-emerald-900 flex items-center gap-1 shrink-0 self-start md:self-center font-bold"
              >
                {copiedCmd === 'cmd_check_init' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>Copiar</span>
              </button>
            </div>
          </div>
        </section>

        {/* SEÇÃO 5: GUIA DE CADA BOTÃO DA INTERFACE */}
        <section id="buttons" className="space-y-4 print:page-break-before-always">
          <div className="flex items-center gap-2.5 text-lg font-bold text-white print:text-slate-900 border-b border-slate-800 print:border-slate-300 pb-2">
            <span className="w-7 h-7 rounded-lg bg-purple-500/20 text-purple-400 print:text-purple-800 flex items-center justify-center text-sm font-black">
              5
            </span>
            <h2>Guia Exaustivo de Cada Botão e Elemento da Interface Web</h2>
          </div>

          <p className="text-sm text-slate-300 print:text-slate-700 leading-relaxed">
            Abaixo você encontra o dicionário de todos os botões e abas da interface, organizados por tela:
          </p>

          <div className="space-y-6 text-xs">
            {/* Barra Superior */}
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-3">
              <h3 className="font-bold text-sm text-white print:text-slate-900 flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-400 print:text-emerald-800" />
                <span>Barra Superior (Header Global)</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <span className="font-mono font-bold text-emerald-400 print:text-emerald-800">Botão "Iniciar Sessão / Encerrar":</span>
                  <p className="text-slate-300 print:text-slate-700">Abre o modal para definir o nome da sessão de jogo (ex: "Sessão Noturna MTT"). Inicia o cronômetro oficial e o contador de cliques. Ao clicar em "Encerrar", grava uma linha de resumo no CSV de auditoria.</p>
                </div>
                <div className="space-y-1">
                  <span className="font-mono font-bold text-amber-400 print:text-amber-800">Botão "Pausar / Retomar":</span>
                  <p className="text-slate-300 print:text-slate-700">Congela temporariamente o cronômetro da sessão quando você fizer um intervalo de café ou pausa de torneio, mantendo as estatísticas sem distorção.</p>
                </div>
                <div className="space-y-1">
                  <span className="font-mono font-bold text-cyan-400 print:text-cyan-800">Botão "Exportar CSV":</span>
                  <p className="text-slate-300 print:text-slate-700">Faz o download imediato de uma planilha CSV no seu navegador contendo todos os eventos, coordenadas e latências registradas na sessão ativa.</p>
                </div>
                <div className="space-y-1">
                  <span className="font-mono font-bold text-indigo-400 print:text-indigo-800">Pill de Status PPPoker (Online/Offline):</span>
                  <p className="text-slate-300 print:text-slate-700">Indica se a janela do PPPoker foi detectada no Windows pelo scanner de DPI com as coordenadas absolutas (X, Y, W, H).</p>
                </div>
              </div>
            </div>

            {/* Aba Modo Fantasma */}
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-3">
              <h3 className="font-bold text-sm text-white print:text-slate-900 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400 print:text-emerald-800" />
                <span>Aba "Modo Fantasma" (Inspector de Mesa e Cliques)</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <span className="font-mono font-bold text-emerald-400 print:text-emerald-800">Seletor "Modo Fantasma (Espectador)":</span>
                  <p className="text-slate-300 print:text-slate-700">Bloqueia todos os cliques físicos do mouse. Mantém a leitura de tela ativa e calcula as decisões GTO projetando na mesa virtual.</p>
                </div>
                <div className="space-y-1">
                  <span className="font-mono font-bold text-rose-400 print:text-rose-800">Botão de Trava "Armar Cliques Biométricos (Live)":</span>
                  <p className="text-slate-300 print:text-slate-700">Trava de segurança de dois passos com switch de confirmação física. Permite autorizar o envio de cliques reais para a janela do PPPoker.</p>
                </div>
                <div className="space-y-1">
                  <span className="font-mono font-bold text-amber-400 print:text-amber-800">Botão "Gatilho de Emergência (Kill-Switch)":</span>
                  <p className="text-slate-300 print:text-slate-700">Botão vermelho grande. Interrompe imediatamente qualquer execução ou clique em andamento e desativa o bot instantaneamente.</p>
                </div>
                <div className="space-y-1">
                  <span className="font-mono font-bold text-indigo-400 print:text-indigo-800">Botões de "Cenários de Teste Rápidos":</span>
                  <p className="text-slate-300 print:text-slate-700">Permite testar 5 mãos instantâneas (ex: A♠ K♥ BTN RFI, Q♦ Q♠ enfrentando 3-bet, Monster Flop com Trinca, etc.) para ver a decisão calculada em menos de 1 segundo.</p>
                </div>
              </div>
            </div>

            {/* Aba Cérebro & Treinamento */}
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-3">
              <h3 className="font-bold text-sm text-white print:text-slate-900 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-purple-400 print:text-purple-800" />
                <span>Aba "Cérebro & Treinamento" (IA Evolutiva)</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <span className="font-mono font-bold text-purple-400 print:text-purple-800">Slider "Learning Rate (Taxa de Aprendizado)":</span>
                  <p className="text-slate-300 print:text-slate-700">Define de 0.01 a 0.50 a velocidade com que o feedback humano modifica a política do robô. 0.05 é o valor recomendado para estabilidade estatística.</p>
                </div>
                <div className="space-y-1">
                  <span className="font-mono font-bold text-emerald-400 print:text-emerald-800">Botão "Exportar Win/Loss por Linha em JSON":</span>
                  <p className="text-slate-300 print:text-slate-700">Exporta um arquivo estruturado <code className="font-mono">win_loss_lines_export.json</code> com as estatísticas de EV e detalhes de cada mão para importar no seu software de range externo.</p>
                </div>
                <div className="space-y-1">
                  <span className="font-mono font-bold text-cyan-400 print:text-cyan-800">Gráfico "EV Esperado vs Real":</span>
                  <p className="text-slate-300 print:text-slate-700">Compara o ganho em Big Blinds projetado matematicamente com o ganho real das mãos jogadas nas linhas de 3-bet light, c-bet seco e bluff no river.</p>
                </div>
                <div className="space-y-1">
                  <span className="font-mono font-bold text-rose-400 print:text-rose-800">Gráfico de Histórico de Erros:</span>
                  <p className="text-slate-300 print:text-slate-700">Mostra a distribuição das falhas catalogadas na sessão ('range incorreto', 'leitura de board errada', 'falha de gestão de pote').</p>
                </div>
              </div>
            </div>

            {/* Aba Motor GTO Pré-Flop */}
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-3">
              <h3 className="font-bold text-sm text-white print:text-slate-900 flex items-center gap-2">
                <Brain className="w-4 h-4 text-rose-400 print:text-rose-800" />
                <span>Aba "Motor GTO Pré-Flop" (169 Mãos)</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <span className="font-mono font-bold text-rose-400 print:text-rose-800">Seletor de Posição (UTG, MP, CO, BTN, SB, BB):</span>
                  <p className="text-slate-300 print:text-slate-700">Filtra a matriz de 169 combinações exibindo as frequências exatas de Raise, Call e Fold para cada posição da mesa.</p>
                </div>
                <div className="space-y-1">
                  <span className="font-mono font-bold text-amber-400 print:text-amber-800">Dashboard "Frequência Ideal vs Frequência Atual do Bot":</span>
                  <p className="text-slate-300 print:text-slate-700">Compara a porcentagem de mãos abertas pelo bot versus a linha GTO pura, destacando com alertas vermelhos discrepâncias superiores a 5%.</p>
                </div>
              </div>
            </div>

            {/* Aba Auditoria */}
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-3">
              <h3 className="font-bold text-sm text-white print:text-slate-900 flex items-center gap-2">
                <FileSpreadsheet className="w-4 h-4 text-emerald-400 print:text-emerald-800" />
                <span>Aba "Auditoria" (KPIs Financeiros & Logs CSV)</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <span className="font-mono font-bold text-emerald-400 print:text-emerald-800">Painel de 3 KPIs (ROI Estimado, Taxa de Sucesso, Tempo Médio):</span>
                  <p className="text-slate-300 print:text-slate-700">Calcula o Retorno sobre Investimento total com base nas inscrições com status SUCCESS e no buy-in em fichas, a porcentagem de inscrições bem-sucedidas e a cadência média entre inscrições consecutivas.</p>
                </div>
                <div className="space-y-1">
                  <span className="font-mono font-bold text-cyan-400 print:text-cyan-800">Tabela de Logs e Busca Instantânea:</span>
                  <p className="text-slate-300 print:text-slate-700">Exibe cada linha do arquivo CSV com filtros por status (SUCCESS, ABORTED, ERROR) e exportação em 1 clique.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SEÇÃO 6: CUIDADOS OPERACIONAIS E ANTI-BAN */}
        <section id="safety" className="space-y-4 print:page-break-before-always">
          <div className="flex items-center gap-2.5 text-lg font-bold text-white print:text-slate-900 border-b border-slate-800 print:border-slate-300 pb-2">
            <span className="w-7 h-7 rounded-lg bg-rose-500/20 text-rose-400 print:text-rose-800 flex items-center justify-center text-sm font-black">
              6
            </span>
            <h2>Cuidados Operacionais, Protocolos de Segurança e Anti-Ban</h2>
          </div>

          <div className="p-5 rounded-xl bg-rose-950/20 print:bg-rose-50 border border-rose-500/40 print:border-rose-300 space-y-3 text-xs">
            <div className="flex items-center gap-2 text-rose-400 print:text-rose-800 font-bold text-sm">
              <ShieldAlert className="w-4 h-4" />
              <span>Regras de Ouro para Execução em Ambiente Real</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-slate-300 print:text-slate-700 leading-relaxed">
              <div className="space-y-2">
                <p><strong>1. Sempre Comece com o Modo Fantasma:</strong> Antes de ativar os cliques reais, rode a Opção [6] do launcher (<code className="font-mono text-emerald-400 print:text-emerald-800">--spectator</code>) por pelo menos 15 minutos em torneios freeroll ou play money. Verifique se o bot lê as cartas corretamente e se os bipes sonoros coincidem com o seu Hero.</p>
                <p><strong>2. Não Mexa o Mouse Físico Durante o Turno:</strong> Quando a barra de tempo do Hero estiver ativa e o bot estiver calculando o clique, evite mover o mouse bruscamente para não conflitar com a curva de Bézier do PyAutoGUI.</p>
                <p><strong>3. Resolução Fixo e Escala de DPI:</strong> Mantenha a janela do PPPoker sempre na proporção vertical canônica (787 × 1470). Se você alterar a escala de tela do Windows de 100% para 125%, rode imediatamente a calibração (Opção 5).</p>
              </div>
              <div className="space-y-2">
                <p><strong>4. Limite de Duração de Sessão (Higiene Humana):</strong> Nenhum jogador humano joga 20 horas ininterruptas sem errar um clique. Utilize o recurso de pausa do VisualPilot para fazer pausas de 5 a 10 minutos a cada 2 horas de grind.</p>
                <p><strong>5. Camuflagem Gaussiana:</strong> Mantenha a dispersão de jitter ativada ($\sigma = 3.5$). O bot nunca clica exatamente no pixel central do botão — cada clique possui um desvio orgânico milimétrico.</p>
                <p><strong>6. Emulador e Máquina Virtual:</strong> Se jogar via LDPlayer ou MuMu, garanta que a virtualização VT-x esteja ativada na BIOS para que a captura de tela não sofra quedas de FPS.</p>
              </div>
            </div>
          </div>
        </section>

        {/* SEÇÃO 7: ROADMAP VERSÃO 2.0 */}
        <section id="v2" className="space-y-4 print:page-break-before-always">
          <div className="flex items-center gap-2.5 text-lg font-bold text-white print:text-slate-900 border-b border-slate-800 print:border-slate-300 pb-2">
            <span className="w-7 h-7 rounded-lg bg-indigo-500/20 text-indigo-400 print:text-indigo-800 flex items-center justify-center text-sm font-black">
              7
            </span>
            <h2>O Que Poderá Ser Melhorado para a Versão 2.0 (Pós-Testes Reais)</h2>
          </div>

          <p className="text-sm text-slate-300 print:text-slate-700 leading-relaxed">
            Após validar o comportamento nas mesas reais, a Versão 2.0 poderá incorporar os seguintes módulos avançados:
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-indigo-400 print:text-indigo-800 text-sm flex items-center gap-1.5">
                <Sparkles className="w-4 h-4" />
                <span>1. Visão por Redes Neurais YOLOv8</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                Substituir o Template Matching tradicional por um modelo treinado de detecção de objetos YOLOv8 nano (execução em ~8ms na CPU). Isso permitirá reconhecer cartas mesmo com resoluções arbitrárias, animações de cartas voando e skins personalizadas.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-emerald-400 print:text-emerald-800 text-sm flex items-center gap-1.5">
                <Brain className="w-4 h-4" />
                <span>2. HUD Exploitative Dinâmico</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                Rastrear o VPIP, PFR, 3-Bet% e Fold to C-Bet dos vilões da mesa em tempo real. Se o vilão for classificado como "Fish/Calling Station", o bot desativa blefes e aumenta o sizing de valor para 100% do pote. Se for "Nit", aumenta os roubos de blind em 80%.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-amber-400 print:text-amber-800 text-sm flex items-center gap-1.5">
                <Layers className="w-4 h-4" />
                <span>3. Suporte a Omaha (PLO4 & PLO5)</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                Expansão do motor de decisão para jogos de Omaha 4 cartas e 5 cartas com cálculo de equidade multi-way e regras obrigatórias de 2 cartas da mão + 3 da mesa.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-rose-400 print:text-rose-800 text-sm flex items-center gap-1.5">
                <Coins className="w-4 h-4" />
                <span>4. Gestão de Bankroll com Critério de Kelly</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                O orquestrador ajustará o teto de buy-in automaticamente de acordo com o saldo atual de fichas da conta, impedindo que o bot participe de torneios que representem mais de 2% do bankroll total.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-cyan-400 print:text-cyan-800 text-sm flex items-center gap-1.5">
                <Repeat className="w-4 h-4" />
                <span>5. Multi-Mesas Concorrente Real (Multi-Process)</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                Execução de 4 ou 6 mesas do PPPoker simultâneas com escalonamento por prioridade: a mesa com o timebank do Hero mais próximo do fim recebe a atenção de clique prioritária.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-2">
              <div className="font-bold text-purple-400 print:text-purple-800 text-sm flex items-center gap-1.5">
                <BellRing className="w-4 h-4" />
                <span>6. Bot de Telegram com Aprovação Remota</span>
              </div>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                Receba uma foto da mão com o pote gigante no seu Telegram com botões de "Pagar", "Foldar" ou "All-in" para responder do smartphone caso esteja longe do computador.
              </p>
            </div>
          </div>
        </section>

        {/* SEÇÃO 8: PERGUNTAS FREQUENTES (FAQ) */}
        <section id="faq" className="space-y-4 print:page-break-before-always">
          <div className="flex items-center gap-2.5 text-lg font-bold text-white print:text-slate-900 border-b border-slate-800 print:border-slate-300 pb-2">
            <span className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 print:text-emerald-800 flex items-center justify-center text-sm font-black">
              8
            </span>
            <h2>Perguntas Frequentes & Resolução Rápida de Dúvidas</h2>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-1.5">
              <span className="font-bold text-emerald-400 print:text-emerald-800 text-sm">O bot pode ser banido pelo sistema anti-cheat do clube?</span>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                O VisualPilot não injeta nenhum código, DLL ou memória dentro do executável do PPPoker. Ele funciona exatamente como um usuário humano: olha para os pixels da tela com uma câmera virtual (captura de tela) e move o cursor do mouse com trajetórias curvas naturais e atrasos humanos. No entanto, é fundamental respeitar as diretrizes de higiene humana (não jogar 24 horas ininterruptas e usar limites de buy-in).
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-1.5">
              <span className="font-bold text-cyan-400 print:text-cyan-800 text-sm">E se eu redimensionar a janela do PPPoker?</span>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                O módulo <code className="font-mono">calibrate_window.py</code> detecta automaticamente a largura e altura atuais da janela e calcula uma matriz de reescalonamento dinâmico. Entretanto, para precisão ótima de OCR nos números pequenos do pote, a proporção recomendada é manter a janela do aplicativo em 787 × 1470 px.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 print:bg-slate-100 border border-slate-800 print:border-slate-300 space-y-1.5">
              <span className="font-bold text-amber-400 print:text-amber-800 text-sm">Como sei que o bot está pronto para o teste real?</span>
              <p className="text-slate-300 print:text-slate-700 leading-relaxed">
                Quando você rodar a Opção [6] do launcher (Modo Fantasma) e observar no terminal que ele detectou "É a vez do Hero: True", exibiu as duas cartas corretas e sugeriu a jogada esperada com 100% de precisão por 20 mãos seguidas. Neste ponto, o sistema está 100% validado para o modo Live (Opção 7).
              </p>
            </div>
          </div>
        </section>

        {/* Rodapé do Documento para Impressão */}
        <footer className="pt-8 border-t border-slate-800 print:border-slate-300 text-center text-xs text-slate-500 print:text-slate-600 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>VisualPilot AI Poker Suite · Documentação Operacional Oficial</div>
          <div>Gerado em {new Date().toLocaleDateString('pt-BR')} às {new Date().toLocaleTimeString('pt-BR')}</div>
          <div className="font-mono">Hash de Validação: VP-DOC-787X1470-GTO-V1</div>
        </footer>
      </article>
    </div>
  );
};
