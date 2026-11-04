import React, { useState } from 'react';
import {
  BookOpen,
  CheckCircle2,
  AlertTriangle,
  Play,
  Terminal,
  MousePointerClick,
  Eye,
  Layers,
  Sparkles,
  ChevronRight,
  HelpCircle,
  Copy,
  Check,
  ShieldCheck,
  Maximize2,
  FolderOpen,
  RotateCcw,
  Zap,
  Flame,
  Info,
  Gamepad2,
  Hand
} from 'lucide-react';

interface StepCardProps {
  number: string;
  title: string;
  subtitle: string;
  emoji: string;
  color: 'emerald' | 'amber' | 'cyan' | 'purple' | 'rose' | 'indigo';
  children: React.ReactNode;
}

function StepCard({ number, title, subtitle, emoji, color, children }: StepCardProps) {
  const colorMap = {
    emerald: 'border-emerald-700/60 bg-emerald-950/20 text-emerald-400',
    amber: 'border-amber-700/60 bg-amber-950/20 text-amber-400',
    cyan: 'border-cyan-700/60 bg-cyan-950/20 text-cyan-400',
    purple: 'border-purple-700/60 bg-purple-950/20 text-purple-400',
    rose: 'border-rose-700/60 bg-rose-950/20 text-rose-400',
    indigo: 'border-indigo-700/60 bg-indigo-950/20 text-indigo-400',
  };

  const badgeMap = {
    emerald: 'bg-emerald-500 text-slate-950',
    amber: 'bg-amber-500 text-slate-950',
    cyan: 'bg-cyan-500 text-slate-950',
    purple: 'bg-purple-500 text-slate-950',
    rose: 'bg-rose-500 text-slate-950',
    indigo: 'bg-indigo-500 text-slate-950',
  };

  return (
    <div className={`rounded-2xl border p-5 sm:p-6 transition-all duration-200 shadow-xl ${colorMap[color]}`}>
      <div className="flex items-start gap-3 sm:gap-4 mb-4">
        <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center font-black text-lg sm:text-xl shadow-lg shrink-0 ${badgeMap[color]}`}>
          {number}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xl sm:text-2xl">{emoji}</span>
            <h3 className="text-base sm:text-lg font-black text-white tracking-tight">
              {title}
            </h3>
          </div>
          <p className="text-xs sm:text-sm text-slate-300 font-medium mt-0.5">
            {subtitle}
          </p>
        </div>
      </div>
      <div className="text-slate-200 text-sm space-y-3 pl-0 sm:pl-16">
        {children}
      </div>
    </div>
  );
}

export function ManualVisualPilot() {
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

  // Checklist interativo para a Seção 3
  const [checklist, setChecklist] = useState<{ [key: string]: boolean }>({
    step1_pppoker_open: true,
    step2_four_colors: false,
    step3_blue_theme: false,
    step4_window_visible: true,
    step5_clean_board: false,
    step6_ocr_green: false,
  });

  const toggleCheck = (id: string) => {
    setChecklist(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const completedCount = Object.values(checklist).filter(Boolean).length;
  const totalCount = Object.keys(checklist).length;
  const progressPercent = Math.round((completedCount / totalCount) * 100);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCmd(id);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-200 max-w-5xl mx-auto">
      {/* Header Banner com estilo amigável e acolhedor */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-950 via-slate-900 to-emerald-950 border border-indigo-700/50 p-6 sm:p-8 shadow-2xl">
        <div className="absolute -right-8 -bottom-8 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute right-12 top-6 text-6xl opacity-20 select-none">🎯</div>

        <div className="relative z-10 space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 text-xs font-black uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span>Guia Passo a Passo Super Fácil</span>
          </div>

          <h1 className="text-2xl sm:text-4xl font-black text-white tracking-tight">
            Manual Descomplicado do VisualPilot
          </h1>

          <p className="text-sm sm:text-base text-slate-300 max-w-3xl leading-relaxed">
            Sem palavras difíceis ou termos complicados. Aqui está o passo a passo exato
            para você colocar tudo para rodar em 3 minutos, entender as cores das cartas e
            saber como o cérebro do robô toma decisões nas mesas!
          </p>

          <div className="pt-2 flex flex-wrap items-center gap-4 text-xs font-semibold text-slate-300">
            <span className="flex items-center gap-1.5 bg-slate-900/80 px-3 py-1.5 rounded-lg border border-slate-700">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Nível: Qualquer pessoa consegue</span>
            </span>
            <span className="flex items-center gap-1.5 bg-slate-900/80 px-3 py-1.5 rounded-lg border border-slate-700">
              <Eye className="w-4 h-4 text-cyan-400" />
              <span>Ilustrado com Cores Reais</span>
            </span>
            <span className="flex items-center gap-1.5 bg-slate-900/80 px-3 py-1.5 rounded-lg border border-slate-700">
              <ShieldCheck className="w-4 h-4 text-amber-400" />
              <span>100% Seguro no Desktop</span>
            </span>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SEÇÃO 1: COMO ABRIR O PPPOKER E O BOT                                      */}
      {/* ========================================================================= */}
      <section className="space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center font-black text-emerald-400">
              1
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-black text-white">
                Como Abrir o PPPoker e o Robô
              </h2>
              <p className="text-xs text-slate-400">A ordem certa para nada dar erro no Windows</p>
            </div>
          </div>
          <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-950 px-2.5 py-1 rounded-md border border-emerald-800">
            3 Passos Simples
          </span>
        </div>

        {/* Card de Esclarecimento: Qual Pasta e Qual Arquivo Usar? */}
        <div className="rounded-2xl border-2 border-indigo-500/70 bg-gradient-to-br from-indigo-950/80 via-slate-900 to-slate-950 p-5 sm:p-6 shadow-2xl space-y-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500 text-slate-950 flex items-center justify-center font-black shrink-0 shadow-lg">
              <FolderOpen className="w-5 h-5" />
            </div>
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 text-[11px] font-black uppercase tracking-wider mb-1">
                <HelpCircle className="w-3.5 h-3.5" />
                <span>Resposta Rápida: Qual pasta e arquivo usar?</span>
              </div>
              <h3 className="text-base sm:text-lg font-black text-white">
                Fique na pasta principal (raiz) e use apenas o <code className="text-emerald-400 font-mono bg-slate-900 px-2 py-0.5 rounded border border-emerald-800">MENU_INICIAR.bat</code>
              </h3>
              <p className="text-xs sm:text-sm text-slate-300 mt-1">
                Se você descompactou o projeto e viu pastas como <span className="font-mono text-cyan-300">repo_visualpilot</span>, <span className="font-mono text-cyan-300">src</span> ou <span className="font-mono text-cyan-300">app</span>, não se preocupe: você <strong>NÃO</strong> precisa entrar em nenhuma delas!
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
            {/* O que fazer */}
            <div className="p-4 rounded-xl border border-emerald-700/60 bg-emerald-950/30 space-y-2">
              <div className="flex items-center gap-2 text-emerald-400 font-black text-xs uppercase tracking-wide">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>O QUE VOCÊ DEVE FAZER:</span>
              </div>
              <ul className="text-xs text-slate-200 space-y-1.5 list-disc pl-4">
                <li>
                  Fique na <strong>pasta principal</strong> (ex: <code className="text-emerald-300 bg-slate-900 px-1 rounded font-mono">C:\...\EQUIPE</code>).
                </li>
                <li>
                  Dê dois cliques no arquivo <strong><code className="text-emerald-300 bg-slate-900 px-1 rounded font-mono">MENU_INICIAR.bat</code></strong> (ou no atalho <code className="text-emerald-300 bg-slate-900 px-1 rounded font-mono">iniciar.bat</code>).
                </li>
                <li>
                  Ele é o único arquivo necessário: ele prepara o ambiente e abre a central com todas as opções de 1 a 8.
                </li>
              </ul>
            </div>

            {/* O que NÃO fazer */}
            <div className="p-4 rounded-xl border border-rose-800/60 bg-rose-950/20 space-y-2">
              <div className="flex items-center gap-2 text-rose-400 font-black text-xs uppercase tracking-wide">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>O QUE VOCÊ NÃO PRECISA FAZER:</span>
              </div>
              <ul className="text-xs text-slate-300 space-y-1.5 list-disc pl-4">
                <li>
                  <strong>NÃO entre</strong> na pasta <code className="text-rose-300 bg-slate-900 px-1 rounded font-mono">repo_visualpilot</code>. Ela é apenas uma biblioteca interna de códigos Python.
                </li>
                <li>
                  <strong>NÃO execute</strong> scripts como <code className="text-rose-300 bg-slate-900 px-1 rounded font-mono">Iniciar.cmd</code> ou <code className="text-rose-300 bg-slate-900 px-1 rounded font-mono">INICIAR_LABORATORIO.bat</code> de dentro de subpastas.
                </li>
                <li>
                  O <code className="text-emerald-300 bg-slate-900 px-1 rounded font-mono">MENU_INICIAR.bat</code> já carrega tudo isso de forma transparente e automática.
                </li>
              </ul>
            </div>
          </div>

          {/* Estrutura Visual Simplificada */}
          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs space-y-1 text-slate-300">
            <div className="text-indigo-400 font-bold mb-1 flex items-center gap-2">
              <span>📁 Mapa Visual da Sua Pasta:</span>
            </div>
            <div className="text-slate-400 pl-2">
              <div>📁 C:\...\EQUIPE (ou o nome da pasta onde você descompactou) <span className="text-emerald-400 font-bold">← FIQUE AQUI!</span></div>
              <div className="pl-4 text-emerald-300 font-bold">├── 🎯 MENU_INICIAR.bat          ← EXECUTE SEMPRE ESTE ARQUIVO!</div>
              <div className="pl-4 text-amber-300 font-bold">├── 📦 VisualPilot.exe           ← Executável Único compilado (PyInstaller)</div>
              <div className="pl-4 text-cyan-300 font-bold">├── ⚡ INSTALADOR_E_ATUALIZADOR.bat ← 1-CLIQUE: Instala ou repara do zero sem quebrar!</div>
              <div className="pl-4 text-emerald-400 font-bold">├── 🔄 ATUALIZAR_PATCH.bat       ← Patch Delta: Baixa só arquivos modificados</div>
              <div className="pl-4 text-purple-300">├── ⚙️  build_executable.bat      ← Compilador de executável único</div>
              <div className="pl-4 text-emerald-300">├── 🚀 iniciar.bat               ← Atalho direto (chama o menu acima)</div>
              <div className="pl-4 text-slate-500">├── 📁 repo_visualpilot/         (código interno do robô - não mexer)</div>
              <div className="pl-4 text-slate-500">└── 📁 logs/                     (relatórios e auditoria gerados automaticamente)</div>
            </div>
          </div>

          {/* Destaque: Sistema de Patch Automático Delta */}
          <div className="p-4 rounded-xl border border-cyan-800/80 bg-cyan-950/30 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 shrink-0">
              <Zap className="w-5 h-5" />
            </div>
            <div className="space-y-1">
              <h4 className="font-bold text-xs text-cyan-300 uppercase tracking-wide">
                NOVIDADE: Sistema de Patch Automático Delta (Sem Substituir a Pasta!)
              </h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                Quando sair uma nova versão do bot, você <strong>NÃO precisa mais baixar nem copiar a pasta inteira</strong>. 
                Dê dois cliques em <code className="text-emerald-300 font-mono bg-slate-900 px-1 rounded">ATUALIZAR_PATCH.bat</code> ou aperte <code className="text-emerald-300 font-mono bg-slate-900 px-1 rounded">[P]</code> no menu: o sistema lê o <code className="text-cyan-300 font-mono">version.json</code>, identifica apenas os arquivos que mudaram e faz a substituição cirúrgica, <strong>preservando todos os seus logs, configurações e o ambiente virtual</strong> intactos!
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4">
          <StepCard
            number="1"
            title="Primeiro abra o jogo (PPPoker)"
            subtitle="O aplicativo precisa estar visível na sua tela antes de ligar o robô"
            emoji="🃏"
            color="emerald"
          >
            <p>
              Abra o aplicativo <strong>PPPoker</strong> no seu computador e faça login na sua conta normalmente.
            </p>
            <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
              <div className="flex items-center gap-2 text-amber-300 font-bold text-xs">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>REGRA DE OURO (MUITO IMPORTANTE):</span>
              </div>
              <p className="text-xs text-slate-300">
                <strong>NÃO minimize</strong> a janela do PPPoker na barra de tarefas! Deixe a janela aberta na tela. Se ela estiver minimizada ou escondida atrás de outros programas, os olhos do robô (OCR) enxergam apenas uma tela preta.
              </p>
            </div>
          </StepCard>

          <StepCard
            number="2"
            title="Dê dois cliques no arquivo 'MENU_INICIAR.bat'"
            subtitle="Ele fica dentro da pasta do projeto e abre a Central de Controle"
            emoji="🚀"
            color="cyan"
          >
            <p>
              Vá até a pasta do projeto (exemplo: <code className="bg-slate-900 px-1.5 py-0.5 rounded text-cyan-300 font-mono text-xs">C:\Users\...\EQUIPE</code>) e dê dois cliques no arquivo:
            </p>
            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900 border border-slate-800 font-mono text-xs text-cyan-300">
              <span className="font-bold flex items-center gap-2">
                <Terminal className="w-4 h-4 text-cyan-400" />
                MENU_INICIAR.bat
              </span>
              <button
                onClick={() => copyToClipboard('MENU_INICIAR.bat', 'bat')}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition-colors"
              >
                {copiedCmd === 'bat' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedCmd === 'bat' ? 'Copiado' : 'Copiar Nome'}</span>
              </button>
            </div>
            <p className="text-xs text-slate-400">
              Uma tela preta do Windows vai se abrir com as opções numeradas de 1 a 8.
            </p>
          </StepCard>

          <StepCard
            number="3"
            title="Siga a Ordem de Segurança (Fantasma Primeiro!)"
            subtitle="Basta digitar o número da opção e apertar a tecla ENTER"
            emoji="🎮"
            color="purple"
          >
            {/* Alerta de Segurança e Ordem Correta */}
            <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-600/60 text-xs text-amber-200 space-y-1.5 mb-3">
              <div className="flex items-center gap-2 font-black text-amber-300">
                <ShieldCheck className="w-4 h-4 shrink-0 text-amber-400" />
                <span>REGRA DE SEGURANÇA: NUNCA CLIQUE EM MODO AO VIVO DE PRIMEIRA!</span>
              </div>
              <p className="leading-relaxed">
                Antes de deixar o robô clicar na mesa, você deve <strong>SEMPRE</strong> rodar a <strong>Opção [3] (Modo Fantasma)</strong>. Nele, o robô apenas assiste e mostra o que faria com bipes, sem tocar no seu mouse. Quando você tiver certeza absoluta de que o OCR está lendo suas cartas certinho, aí sim você pode ir para a <strong>Opção [4] (Modo Ao Vivo)</strong>.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-2.5">
                <span className="w-6 h-6 rounded-md bg-purple-500/20 text-purple-300 font-black flex items-center justify-center shrink-0">1</span>
                <div>
                  <strong className="text-white block">Opção 1: Diagnóstico de Pré-Voo</strong>
                  <span className="text-slate-400">Testa se o Python, pacotes e a janela do PPPoker estão OK.</span>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-2.5">
                <span className="w-6 h-6 rounded-md bg-amber-500/20 text-amber-300 font-black flex items-center justify-center shrink-0">2</span>
                <div>
                  <strong className="text-white block">Opção 2: Instalar / Reparar</strong>
                  <span className="text-slate-400">Instala tudo o que estiver faltando de forma 100% automática.</span>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/60 flex items-start gap-2.5">
                <span className="w-6 h-6 rounded-md bg-emerald-500 text-slate-950 font-black flex items-center justify-center shrink-0">3</span>
                <div>
                  <strong className="text-emerald-300 block font-bold flex items-center gap-1.5">
                    <span>Opção 3: Modo Fantasma</span>
                    <span className="text-[9px] bg-emerald-500 text-slate-950 px-1 rounded font-black">COMECE AQUI</span>
                  </strong>
                  <span className="text-slate-300">Lê cartas e emite bipes, <strong>ZERO cliques no mouse</strong>. 100% seguro!</span>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-rose-950/20 border border-rose-800/60 flex items-start gap-2.5">
                <span className="w-6 h-6 rounded-md bg-rose-500/20 text-rose-300 font-black flex items-center justify-center shrink-0">4</span>
                <div>
                  <strong className="text-rose-300 block font-bold flex items-center gap-1.5">
                    <span>Opção 4: Modo Ao Vivo</span>
                    <span className="text-[9px] bg-rose-950 text-rose-300 border border-rose-800 px-1 rounded">SÓ APÓS O 3</span>
                  </strong>
                  <span className="text-slate-400">Executa cliques reais com curvas de Bézier e atraso humano.</span>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-2.5">
                <span className="w-6 h-6 rounded-md bg-cyan-500/20 text-cyan-300 font-black flex items-center justify-center shrink-0">5</span>
                <div>
                  <strong className="text-white block">Opção 5: Torneios do Lobby</strong>
                  <span className="text-slate-400">Inscreve você nos torneios do lobby respeitando o teto de buy-in.</span>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-2.5">
                <span className="w-6 h-6 rounded-md bg-indigo-500/20 text-indigo-300 font-black flex items-center justify-center shrink-0">6</span>
                <div>
                  <strong className="text-white block">Opção 6: Painel Web React</strong>
                  <span className="text-slate-400">Abre este dashboard completo no seu navegador (localhost:3000).</span>
                </div>
              </div>
            </div>
          </StepCard>
        </div>

        {/* RECURSO EM DESTAQUE: ASSUMIR CONTROLE TOTAL DAS MESAS (HUMAN TAKEOVER) */}
        <div className="rounded-2xl border-2 border-amber-500/70 bg-gradient-to-br from-amber-950/40 via-slate-900 to-slate-950 p-5 sm:p-6 shadow-2xl space-y-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500 text-slate-950 flex items-center justify-center font-black shrink-0 shadow-lg">
              <Gamepad2 className="w-5 h-5" />
            </div>
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[11px] font-black uppercase tracking-wider mb-1">
                <Zap className="w-3.5 h-3.5 text-amber-400" />
                <span>Novo Recurso de Controle: Intervenção Humana Instantânea</span>
              </div>
              <h3 className="text-base sm:text-lg font-black text-white">
                Como Pausar o Bot para Você Mesmo Jogar e Depois Devolver o Controle
              </h3>
              <p className="text-xs sm:text-sm text-slate-300 mt-1">
                A qualquer momento durante a sessão, você pode assumir 100% das decisões na mesa sem fechar o programa e sem brigas com o mouse.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-1">
            {/* Como Pausar */}
            <div className="p-4 rounded-xl border border-amber-700/60 bg-amber-950/20 space-y-2">
              <div className="flex items-center gap-2 text-amber-300 font-bold text-xs uppercase tracking-wide">
                <Hand className="w-4 h-4 shrink-0 text-amber-400" />
                <span>1. PARA PAUSAR E ASSUMIR AS MESAS:</span>
              </div>
              <ul className="text-xs text-slate-200 space-y-1.5 list-disc pl-4">
                <li>
                  Clique no botão <strong>"Assumir Controle"</strong> no topo da tela (ou simplesmente aperte a tecla <kbd className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-300 font-mono font-bold border border-slate-700">F12</kbd> no seu teclado).
                </li>
                <li>
                  <strong>O que acontece:</strong> O robô congela imediatamente o envio de qualquer clique. O mouse e teclado ficam <strong>100% livres para você</strong>.
                </li>
                <li>
                  Um banner dourado aparecerá no topo confirmando: <em className="text-amber-200">"Você está no controle manual total das mesas"</em>.
                </li>
                <li>
                  Jogue a mão normalmente no PPPoker, aposte, pague ou desista como preferir.
                </li>
              </ul>
            </div>

            {/* Como Retomar */}
            <div className="p-4 rounded-xl border border-emerald-700/60 bg-emerald-950/20 space-y-2">
              <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs uppercase tracking-wide">
                <Play className="w-4 h-4 shrink-0 fill-current text-emerald-400" />
                <span>2. PARA DEVOLVER O CONTROLE AO ROBÔ:</span>
              </div>
              <ul className="text-xs text-slate-200 space-y-1.5 list-disc pl-4">
                <li>
                  Quando você terminar a mão e quiser que o bot volte a trabalhar sozinho, clique no botão verde <strong>"Devolver Controle ao Bot (Retomar)"</strong> (ou tecle <kbd className="px-1.5 py-0.5 rounded bg-slate-800 text-emerald-300 font-mono font-bold border border-slate-700">F12</kbd>).
                </li>
                <li>
                  <strong>Segurança de 1.5s:</strong> O robô espera 1 segundo e meio para você tirar a mão do mouse com calma.
                </li>
                <li>
                  Ele reescaneia a mesa via OCR e volta a calcular o GTO e a jogar de forma 100% autônoma!
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* SEÇÃO 2: COMO USAR O MOTOR GTO PREFLOP & BARALHO DE 4 CORES               */}
      {/* ========================================================================= */}
      <section className="space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center font-black text-indigo-400">
              2
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-black text-white">
                Como Funciona o Motor GTO e as Cores das Cartas
              </h2>
              <p className="text-xs text-slate-400">Entenda de forma fácil as 4 cores e as decisões do robô</p>
            </div>
          </div>
          <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-950 px-2.5 py-1 rounded-md border border-indigo-800">
            Regra das 4 Cores
          </span>
        </div>

        {/* O Baralho de 4 Cores Explicado */}
        <div className="p-5 sm:p-6 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-4">
          <div className="space-y-1">
            <h3 className="text-base font-black text-white flex items-center gap-2">
              <span>🎨 Por que usamos 4 cores no PPPoker?</span>
            </h3>
            <p className="text-xs text-slate-300">
              No poker tradicional, Copas e Ouros são ambos vermelhos, e Espadas e Paus são pretos.
              Para que os olhos do robô nunca confundam os naipes, ative a opção <strong>Baralho de 4 Cores</strong> nas configurações do PPPoker:
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {/* Espadas */}
            <div className="p-3.5 rounded-xl border border-slate-700 bg-slate-950 flex flex-col items-center text-center space-y-1 shadow">
              <span className="text-3xl">♠</span>
              <span className="text-xs font-black text-white">Espadas (s)</span>
              <span className="text-[11px] font-bold text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                PRETO
              </span>
              <span className="text-[10px] text-slate-500">Ex: A♠, K♠</span>
            </div>

            {/* Copas */}
            <div className="p-3.5 rounded-xl border border-rose-900/70 bg-rose-950/20 flex flex-col items-center text-center space-y-1 shadow">
              <span className="text-3xl text-rose-500">♥</span>
              <span className="text-xs font-black text-rose-400">Copas (h)</span>
              <span className="text-[11px] font-bold text-rose-300 bg-rose-950 px-2 py-0.5 rounded border border-rose-800">
                VERMELHO
              </span>
              <span className="text-[10px] text-slate-500">Ex: A♥, Q♥</span>
            </div>

            {/* Ouros */}
            <div className="p-3.5 rounded-xl border border-blue-900/70 bg-blue-950/20 flex flex-col items-center text-center space-y-1 shadow">
              <span className="text-3xl text-blue-400">♦</span>
              <span className="text-xs font-black text-blue-300">Ouros (d)</span>
              <span className="text-[11px] font-bold text-blue-200 bg-blue-950 px-2 py-0.5 rounded border border-blue-800">
                AZUL
              </span>
              <span className="text-[10px] text-slate-500">Ex: K♦, J♦</span>
            </div>

            {/* Paus */}
            <div className="p-3.5 rounded-xl border border-emerald-900/70 bg-emerald-950/20 flex flex-col items-center text-center space-y-1 shadow">
              <span className="text-3xl text-emerald-400">♣</span>
              <span className="text-xs font-black text-emerald-300">Paus (c)</span>
              <span className="text-[11px] font-bold text-emerald-200 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-800">
                VERDE
              </span>
              <span className="text-[10px] text-slate-500">Ex: T♣, 9♣</span>
            </div>
          </div>
        </div>

        {/* As Cores das Ações no Motor GTO */}
        <div className="p-5 sm:p-6 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-4">
          <div className="space-y-1">
            <h3 className="text-base font-black text-white flex items-center gap-2">
              <span>🧠 O que significa cada cor nas decisões do robô?</span>
            </h3>
            <p className="text-xs text-slate-300">
              O motor GTO avalia as 169 combinações de mãos antes do flop e escolhe a jogada matematicamente perfeita. As cores na tela mostram o que fazer:
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* FOLD */}
            <div className="p-4 rounded-xl border border-slate-700 bg-slate-950 space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-3.5 h-3.5 rounded-full bg-slate-500" />
                <span className="text-xs font-black text-slate-200 uppercase tracking-wider">Cinza = FOLD (Desistir)</span>
              </div>
              <p className="text-xs text-slate-400">
                A mão é fraca para a posição. O robô clica no botão da esquerda (Desistir) para economizar fichas.
              </p>
            </div>

            {/* CALL / CHECK */}
            <div className="p-4 rounded-xl border border-amber-800/60 bg-amber-950/20 space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-3.5 h-3.5 rounded-full bg-amber-400" />
                <span className="text-xs font-black text-amber-300 uppercase tracking-wider">Amarelo = CALL / CHECK (Pagar)</span>
              </div>
              <p className="text-xs text-slate-300">
                A mão tem valor para ver as cartas comunitárias, mas não é forte o bastante para aumentar a aposta.
              </p>
            </div>

            {/* RAISE */}
            <div className="p-4 rounded-xl border border-rose-800/60 bg-rose-950/20 space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-3.5 h-3.5 rounded-full bg-rose-500" />
                <span className="text-xs font-black text-rose-300 uppercase tracking-wider">Vermelho = RAISE (Aumentar)</span>
              </div>
              <p className="text-xs text-slate-300">
                A mão é muito forte (ex: Ás-Ás, Rei-Rei, Ás-Rei)! O robô clica para aumentar e colocar pressão nos adversários.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* SEÇÃO 3: CHECK-LIST DE PRIMEIROS PASSOS PARA RECONHECIMENTO DE CARTAS      */}
      {/* ========================================================================= */}
      <section className="space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center font-black text-cyan-400">
              3
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-black text-white">
                Check-list: Suas Cartas Sendo Lidas Perfeitamente
              </h2>
              <p className="text-xs text-slate-400">Marque cada item abaixo para ter 100% de precisão no OCR</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono font-bold text-slate-300">
            <span>Progresso:</span>
            <span className={`px-2 py-0.5 rounded font-bold ${progressPercent === 100 ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-slate-800 text-cyan-400'}`}>
              {completedCount}/{totalCount} ({progressPercent}%)
            </span>
          </div>
        </div>

        {/* Barra de Progresso Visual */}
        <div className="w-full bg-slate-900 rounded-full h-2.5 overflow-hidden border border-slate-800">
          <div
            className="bg-gradient-to-r from-cyan-500 to-emerald-400 h-2.5 rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Itens do Checklist */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Item 1 */}
          <div
            onClick={() => toggleCheck('step1_pppoker_open')}
            className={`p-4 rounded-2xl border transition-all cursor-pointer flex items-start gap-3 select-none ${
              checklist.step1_pppoker_open
                ? 'bg-emerald-950/30 border-emerald-600/80 text-slate-100 shadow-md'
                : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <div className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center shrink-0 border ${
              checklist.step1_pppoker_open
                ? 'bg-emerald-500 border-emerald-400 text-slate-950'
                : 'border-slate-700 bg-slate-800'
            }`}>
              {checklist.step1_pppoker_open && <Check className="w-3.5 h-3.5 stroke-[3]" />}
            </div>
            <div>
              <strong className="text-xs sm:text-sm text-white block">1. Janela PPPoker Aberta</strong>
              <p className="text-[11px] text-slate-300 mt-0.5">
                O jogo está visível no monitor, sem estar minimizado na barra de tarefas.
              </p>
            </div>
          </div>

          {/* Item 2 */}
          <div
            onClick={() => toggleCheck('step2_four_colors')}
            className={`p-4 rounded-2xl border transition-all cursor-pointer flex items-start gap-3 select-none ${
              checklist.step2_four_colors
                ? 'bg-emerald-950/30 border-emerald-600/80 text-slate-100 shadow-md'
                : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <div className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center shrink-0 border ${
              checklist.step2_four_colors
                ? 'bg-emerald-500 border-emerald-400 text-slate-950'
                : 'border-slate-700 bg-slate-800'
            }`}>
              {checklist.step2_four_colors && <Check className="w-3.5 h-3.5 stroke-[3]" />}
            </div>
            <div>
              <strong className="text-xs sm:text-sm text-white block">2. Baralho de 4 Cores Ativado</strong>
              <p className="text-[11px] text-slate-300 mt-0.5">
                No menu de opções do PPPoker, o baralho de 4 cores está ligado (Azul para ouros e Verde para paus).
              </p>
            </div>
          </div>

          {/* Item 3 */}
          <div
            onClick={() => toggleCheck('step3_blue_theme')}
            className={`p-4 rounded-2xl border transition-all cursor-pointer flex items-start gap-3 select-none ${
              checklist.step3_blue_theme
                ? 'bg-emerald-950/30 border-emerald-600/80 text-slate-100 shadow-md'
                : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <div className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center shrink-0 border ${
              checklist.step3_blue_theme
                ? 'bg-emerald-500 border-emerald-400 text-slate-950'
                : 'border-slate-700 bg-slate-800'
            }`}>
              {checklist.step3_blue_theme && <Check className="w-3.5 h-3.5 stroke-[3]" />}
            </div>
            <div>
              <strong className="text-xs sm:text-sm text-white block">3. Tema da Mesa Padrão</strong>
              <p className="text-[11px] text-slate-300 mt-0.5">
                O feltro da mesa usa o tema azul ou clássico oficial, sem animações pesadas de fundo.
              </p>
            </div>
          </div>

          {/* Item 4 */}
          <div
            onClick={() => toggleCheck('step4_window_visible')}
            className={`p-4 rounded-2xl border transition-all cursor-pointer flex items-start gap-3 select-none ${
              checklist.step4_window_visible
                ? 'bg-emerald-950/30 border-emerald-600/80 text-slate-100 shadow-md'
                : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <div className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center shrink-0 border ${
              checklist.step4_window_visible
                ? 'bg-emerald-500 border-emerald-400 text-slate-950'
                : 'border-slate-700 bg-slate-800'
            }`}>
              {checklist.step4_window_visible && <Check className="w-3.5 h-3.5 stroke-[3]" />}
            </div>
            <div>
              <strong className="text-xs sm:text-sm text-white block">4. Sem Janelas Sobrepostas</strong>
              <p className="text-[11px] text-slate-300 mt-0.5">
                Nenhum navegador (Chrome, Edge) ou pasta está tapando a mesa do jogo no monitor.
              </p>
            </div>
          </div>

          {/* Item 5 */}
          <div
            onClick={() => toggleCheck('step5_clean_board')}
            className={`p-4 rounded-2xl border transition-all cursor-pointer flex items-start gap-3 select-none ${
              checklist.step5_clean_board
                ? 'bg-emerald-950/30 border-emerald-600/80 text-slate-100 shadow-md'
                : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <div className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center shrink-0 border ${
              checklist.step5_clean_board
                ? 'bg-emerald-500 border-emerald-400 text-slate-950'
                : 'border-slate-700 bg-slate-800'
            }`}>
              {checklist.step5_clean_board && <Check className="w-3.5 h-3.5 stroke-[3]" />}
            </div>
            <div>
              <strong className="text-xs sm:text-sm text-white block">5. Fichas em Big Blinds (BB)</strong>
              <p className="text-[11px] text-slate-300 mt-0.5">
                Se puder, marque para exibir os valores em Big Blinds para leituras mais precisas.
              </p>
            </div>
          </div>

          {/* Item 6 */}
          <div
            onClick={() => toggleCheck('step6_ocr_green')}
            className={`p-4 rounded-2xl border transition-all cursor-pointer flex items-start gap-3 select-none ${
              checklist.step6_ocr_green
                ? 'bg-emerald-950/30 border-emerald-600/80 text-slate-100 shadow-md'
                : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <div className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center shrink-0 border ${
              checklist.step6_ocr_green
                ? 'bg-emerald-500 border-emerald-400 text-slate-950'
                : 'border-slate-700 bg-slate-800'
            }`}>
              {checklist.step6_ocr_green && <Check className="w-3.5 h-3.5 stroke-[3]" />}
            </div>
            <div>
              <strong className="text-xs sm:text-sm text-white block">6. Teste de Cartas na Aba do Painel</strong>
              <p className="text-[11px] text-slate-300 mt-0.5">
                Clique na aba <strong>"Reconhecimento de Cartas"</strong> no menu ao lado para ver o visualizador em tempo real.
              </p>
            </div>
          </div>
        </div>

        {progressPercent === 100 && (
          <div className="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-600 text-emerald-300 text-xs font-semibold flex items-center gap-3 animate-in zoom-in-95 duration-200">
            <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0" />
            <div>
              <strong className="text-white text-sm block">Parabéns! Tudo configurado perfeitamente!</strong>
              <span>Seu ambiente está pronto para jogar com 100% de precisão de leitura e segurança total contra bloqueios.</span>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
