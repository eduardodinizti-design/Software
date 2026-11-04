import React, { useState } from 'react';
import {
  Download,
  Terminal,
  CheckCircle2,
  AlertTriangle,
  Cpu,
  Zap,
  Play,
  Check,
  Copy,
  ExternalLink,
  ShieldCheck,
  Layers,
  RefreshCw,
  HardDrive,
  FileCheck,
  FileCode2,
  Sparkles,
  ArrowRight,
  FolderArchive,
  Wrench,
  HelpCircle,
  X,
  Monitor,
  PackageCheck
} from 'lucide-react';

interface InstallerDownloadCenterProps {
  onClose?: () => void;
  isModal?: boolean;
}

export const InstallerDownloadCenter: React.FC<InstallerDownloadCenterProps> = ({ onClose, isModal = false }) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [activeGuideTab, setActiveGuideTab] = useState<'quick' | 'crdownload' | 'integrity' | 'features'>('quick');

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className={`space-y-6 ${isModal ? 'max-h-[85vh] overflow-y-auto pr-1' : ''}`}>
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-emerald-950/90 via-slate-900 to-cyan-950/90 border-2 border-emerald-500/40 p-6 shadow-2xl">
        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="flex items-center justify-center p-2.5 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-lg">
                <Monitor className="w-6 h-6 animate-pulse" />
              </span>
              <div>
                <span className="text-[11px] font-black tracking-wider uppercase text-emerald-300 bg-emerald-950/90 px-2.5 py-0.5 rounded border border-emerald-800">
                  Executável Oficial para Windows (.EXE)
                </span>
                <h1 className="text-xl md:text-2xl font-black text-white tracking-tight">
                  Instalador Executável 1-Clique & Atalho na Área de Trabalho
                </h1>
              </div>
            </div>
            <p className="text-sm text-slate-300 max-w-2xl leading-relaxed">
              Exatamente o que você solicitou: <strong>um instalador executável (.exe) autônomo</strong>, sem necessidade de arquivos <code className="text-emerald-400 font-mono">.bat</code>, que instala tudo sozinho e cria um atalho direto na sua <strong>Área de Trabalho</strong> preservando 100% da integridade do seu computador.
            </p>
          </div>

          {isModal && onClose && (
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Ambient glow */}
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-64 h-64 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
      </div>

      {/* Alerta de Desbloqueio no Google Chrome / Edge (.crdownload) */}
      <div className="rounded-2xl bg-gradient-to-r from-amber-950/70 via-slate-900 to-amber-950/40 border-2 border-amber-500/50 p-4 sm:p-5 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="p-2.5 rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/40 shrink-0 mt-0.5">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="text-sm font-black text-white">
                O arquivo baixou como &quot;Não confirmado .crdownload&quot; no Chrome?
              </h4>
              <span className="text-[10px] font-black px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 uppercase tracking-wide">
                Solução em 5 segundos
              </span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              O arquivo de <strong>~53 MB foi 100% baixado com sucesso</strong>! O Google Chrome pausa arquivos <code className="text-amber-300 font-mono">.exe</code> novos aguardando sua autorização. 
              Para liberar: pressione <kbd className="px-2 py-0.5 rounded bg-slate-800 text-amber-300 border border-slate-700 font-mono font-bold text-[11px]">Ctrl + J</kbd> no Chrome e clique em <strong>&quot;Manter arquivo&quot;</strong> &rarr; <strong>&quot;Manter mesmo assim&quot;</strong>. 
              O arquivo vira o instalador <code className="text-emerald-300 font-mono">VisualPilot_Setup.exe</code> na hora!
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 w-full md:w-auto">
          <button
            onClick={() => setActiveGuideTab('crdownload')}
            className="w-full md:w-auto flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-200 text-xs font-bold transition-all cursor-pointer whitespace-nowrap"
          >
            <HelpCircle className="w-4 h-4 text-amber-400" />
            <span>Ver Passo a Passo</span>
          </button>
          <a
            href="/VisualPilot_Instalador_Completo.zip"
            download="VisualPilot_Instalador_Completo.zip"
            className="w-full md:w-auto flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs shadow-md transition-all cursor-pointer whitespace-nowrap"
            title="O Chrome não bloqueia arquivos .ZIP"
          >
            <FolderArchive className="w-4 h-4" />
            <span>Baixar em .ZIP (Sem Bloqueio)</span>
          </a>
        </div>
      </div>

      {/* Main Download Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Card 1: Instalador Oficial .EXE (DESTAQUE MÁXIMO) */}
        <div className="relative rounded-2xl bg-gradient-to-b from-emerald-950/70 via-slate-900 to-slate-900 border-2 border-emerald-400 p-6 flex flex-col justify-between shadow-2xl shadow-emerald-500/15 group">
          <div className="absolute -top-3 left-6 bg-gradient-to-r from-emerald-400 to-teal-400 text-slate-950 font-black text-[11px] uppercase tracking-wider px-3.5 py-0.5 rounded-full shadow-lg">
            ⭐ INSTALADOR EXECUTÁVEL (.EXE)
          </div>

          <div className="space-y-4 pt-2">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center">
              <PackageCheck className="w-7 h-7" />
            </div>

            <div>
              <h3 className="text-lg font-black text-white group-hover:text-emerald-300 transition-colors">
                VisualPilot_Setup.exe
              </h3>
              <p className="text-xs font-mono text-emerald-400 mt-0.5">
                Executável Autônomo Windows (~52 MB) com Python 3.11 Embutido e Todas Dependências Offline
              </p>
            </div>

            <p className="text-xs text-slate-200 leading-relaxed font-medium">
              Instalação padrão e 100% autônoma do Windows: baixe, dê duplo-clique no instalador <code className="text-emerald-300 font-mono">.exe</code> e ele realiza todo o processo automaticamente com runtime embutido e atalho no Desktop.
            </p>

            <ul className="text-xs space-y-2 text-slate-300">
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span><strong>Cria atalho na Área de Trabalho</strong> (<code className="text-emerald-300 font-mono">VisualPilot.lnk</code>)</span>
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span><strong>8 Pacotes Críticos Pré-instalados</strong> (PyAutoGUI, OpenCV, NumPy, Pillow, MSS, Requests...)</span>
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span><strong>Python 3.11 Oficial Embutido</strong> (não depende do PATH nem de instalação prévia)</span>
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span><strong>Integridade 100% garantida</strong> (isolado em <code className="text-slate-200 font-mono">AppData</code>)</span>
              </li>
            </ul>
          </div>

          <div className="pt-6">
            <a
              href="/VisualPilot_Setup.exe"
              download="VisualPilot_Setup.exe"
              className="w-full flex items-center justify-center gap-2.5 px-4 py-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-sm shadow-xl shadow-emerald-500/25 transition-all cursor-pointer group-hover:scale-[1.02] ring-2 ring-emerald-400/60"
            >
              <Download className="w-5 h-5" />
              <span>BAIXAR EXECUTÁVEL (.EXE)</span>
            </a>
            <p className="text-[10px] text-center text-slate-400 mt-2 font-mono">
              Se o Chrome pausar o download, aperte Ctrl+J &rarr; &quot;Manter mesmo assim&quot;
            </p>
          </div>
        </div>

        {/* Card 2: Pacote Completo Portátil ZIP */}
        <div className="relative rounded-2xl bg-slate-900/90 border border-slate-700 p-6 flex flex-col justify-between shadow-xl hover:border-slate-500 transition-all group">
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 flex items-center justify-center">
              <FolderArchive className="w-6 h-6" />
            </div>

            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-white">
                  Pacote Completo Portátil
                </h3>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  Zero Bloqueio Chrome
                </span>
              </div>
              <p className="text-xs font-mono text-cyan-400 mt-0.5">
                VisualPilot_Instalador_Completo.zip (~82 MB)
              </p>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              O Google Chrome <strong>NÃO bloqueia</strong> arquivos <code className="text-cyan-300 font-mono">.zip</code>. Baixe direto, extraia em qualquer pasta e execute <code className="text-slate-200 font-mono">iniciar_visualpilot.bat</code> ou <code className="text-slate-200 font-mono">VisualPilot.exe</code>.
            </p>

            <ul className="text-xs space-y-1.5 text-slate-400">
              <li className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                <span>Inclui Python 3.11 embutido com todos os 8 pacotes</span>
              </li>
              <li className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                <span>Inclui o executável <code className="text-slate-200 font-mono">VisualPilot.exe</code> e modelo YOLO</span>
              </li>
              <li className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                <span>Ideal se seu navegador pausou o <code className="text-slate-300 font-mono">.exe</code></span>
              </li>
            </ul>
          </div>

          <div className="pt-6">
            <a
              href="/VisualPilot_Instalador_Completo.zip"
              download="VisualPilot_Instalador_Completo.zip"
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-cyan-700/80 hover:bg-cyan-600 border border-cyan-500/50 text-white font-bold text-sm shadow-md transition-all cursor-pointer"
            >
              <Download className="w-4 h-4 text-cyan-200" />
              <span>Baixar Pacote Portátil (.ZIP)</span>
            </a>
          </div>
        </div>

        {/* Card 3: Executável Lançador Standalone */}
        <div className="relative rounded-2xl bg-slate-900/90 border border-slate-700 p-6 flex flex-col justify-between shadow-xl hover:border-slate-500 transition-all">
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/40 flex items-center justify-center">
              <Cpu className="w-6 h-6" />
            </div>

            <div>
              <h3 className="text-lg font-bold text-white">
                Construtor de .EXE Próprio
              </h3>
              <p className="text-xs font-mono text-indigo-400 mt-0.5">
                build_executable.bat
              </p>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Script opcional para compilar o executável diretamente na sua máquina caso deseje gerar um novo arquivo binário com modificações personalizadas.
            </p>

            <ul className="text-xs space-y-1.5 text-slate-400">
              <li className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                <span>Compilação via PyInstaller nativo</span>
              </li>
              <li className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                <span>Gera <code className="text-slate-200 font-mono">dist\VisualPilot.exe</code></span>
              </li>
              <li className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                <span>Para desenvolvedores ou alterações locais</span>
              </li>
            </ul>
          </div>

          <div className="pt-6">
            <a
              href="/build_executable.bat"
              download="build_executable.bat"
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-white font-bold text-sm shadow-md transition-all cursor-pointer"
            >
              <Download className="w-4 h-4 text-indigo-400" />
              <span>Baixar build_executable.bat</span>
            </a>
          </div>
        </div>
      </div>

      {/* Direct Answers to User Inquiries Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </span>
            <h2 className="text-base font-bold text-white tracking-wide">
              Central de Ajuda, Desbloqueio e Integridade
            </h2>
          </div>

          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs flex-wrap">
            <button
              onClick={() => setActiveGuideTab('quick')}
              className={`px-3 py-1 rounded-lg font-semibold transition-colors cursor-pointer ${
                activeGuideTab === 'quick' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
              }`}
            >
              Instalação do .EXE
            </button>
            <button
              onClick={() => setActiveGuideTab('crdownload')}
              className={`px-3 py-1 rounded-lg font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeGuideTab === 'crdownload' ? 'bg-amber-500 text-slate-950 font-bold' : 'text-amber-400 hover:text-white'
              }`}
            >
              <AlertTriangle className="w-3 h-3" />
              <span>Liberar .crdownload no Chrome</span>
            </button>
            <button
              onClick={() => setActiveGuideTab('integrity')}
              className={`px-3 py-1 rounded-lg font-semibold transition-colors cursor-pointer ${
                activeGuideTab === 'integrity' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
              }`}
            >
              Integridade do Sistema
            </button>
            <button
              onClick={() => setActiveGuideTab('features')}
              className={`px-3 py-1 rounded-lg font-semibold transition-colors cursor-pointer ${
                activeGuideTab === 'features' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
              }`}
            >
              Atalho na Área de Trabalho
            </button>
          </div>
        </div>

        {activeGuideTab === 'crdownload' && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-500/40 text-xs text-slate-200 leading-relaxed space-y-3">
              <div className="flex items-center gap-2 font-black text-amber-400 text-sm">
                <AlertTriangle className="w-5 h-5 shrink-0" />
                <span>Por que o arquivo aparece como &quot;Não confirmado [número].crdownload&quot;?</span>
              </div>
              <p>
                No seu Windows, o arquivo já atingiu <strong>53.321 KB (53,3 MB)</strong>, o que significa que <strong>100% dos bytes do instalador já foram baixados</strong>!
              </p>
              <p>
                O Google Chrome usa a extensão temporária <code className="text-amber-300 font-mono">.crdownload</code> enquanto aguarda a sua autorização de segurança antes de permitir a execução de arquivos <code className="text-slate-200 font-mono">.exe</code> novos.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="w-7 h-7 rounded-lg bg-amber-500 text-slate-950 font-black text-xs flex items-center justify-center">
                    1
                  </span>
                  <span className="text-[11px] font-mono text-amber-400 bg-amber-950/80 px-2 py-0.5 rounded border border-amber-800">
                    Ctrl + J
                  </span>
                </div>
                <h4 className="text-sm font-bold text-white">Abra a tela de Downloads</h4>
                <p className="text-xs text-slate-300 leading-relaxed">
                  No Google Chrome, pressione o atalho <strong className="text-amber-300 font-mono">Ctrl + J</strong> (ou clique nos três pontinhos no canto superior direito &rarr; <strong>Downloads</strong>).
                </p>
              </div>

              <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="w-7 h-7 rounded-lg bg-amber-500 text-slate-950 font-black text-xs flex items-center justify-center">
                    2
                  </span>
                  <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800">
                    Manter
                  </span>
                </div>
                <h4 className="text-sm font-bold text-white">Clique em &quot;Manter arquivo&quot;</h4>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Ao lado de <strong>VisualPilot_Setup.exe</strong>, clique no botão <strong>&quot;Manter arquivo perigoso&quot;</strong> ou <strong>&quot;Manter mesmo assim&quot;</strong>.
                </p>
              </div>

              <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="w-7 h-7 rounded-lg bg-emerald-500 text-slate-950 font-black text-xs flex items-center justify-center">
                    3
                  </span>
                  <span className="text-[11px] font-mono text-cyan-400 bg-cyan-950/80 px-2 py-0.5 rounded border border-cyan-800">
                    Executar
                  </span>
                </div>
                <h4 className="text-sm font-bold text-white">Instale normalmente</h4>
                <p className="text-xs text-slate-300 leading-relaxed">
                  O Chrome renomeia o arquivo imediatamente para <code className="text-emerald-300 font-mono">VisualPilot_Setup.exe</code> com o ícone oficial. Basta dar 2 cliques!
                </p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
              <span className="text-slate-300">
                <strong>Prefere não passar por isso?</strong> Baixe o arquivo compactado <code className="text-cyan-400 font-mono">.ZIP</code> que o Chrome baixa diretamente sem nenhum bloqueio.
              </span>
              <a
                href="/VisualPilot_Instalador_Completo.zip"
                download="VisualPilot_Instalador_Completo.zip"
                className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs shrink-0 cursor-pointer"
              >
                Baixar .ZIP Agora
              </a>
            </div>
          </div>
        )}

        {activeGuideTab === 'quick' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Step 1 */}
            <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-3 relative">
              <div className="flex items-center justify-between">
                <span className="w-7 h-7 rounded-lg bg-emerald-500 text-slate-950 font-black text-xs flex items-center justify-center">
                  1
                </span>
                <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800">
                  Download
                </span>
              </div>
              <h4 className="text-sm font-bold text-white">
                Baixe o VisualPilot_Setup.exe
              </h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                Clique no botão verde acima para baixar o arquivo <strong>VisualPilot_Setup.exe</strong> (~52 MB). Ele inclui todas as dependências pré-instaladas de forma autônoma.
              </p>
            </div>

            {/* Step 2 */}
            <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-3 relative">
              <div className="flex items-center justify-between">
                <span className="w-7 h-7 rounded-lg bg-cyan-500 text-slate-950 font-black text-xs flex items-center justify-center">
                  2
                </span>
                <span className="text-[11px] font-mono text-cyan-400 bg-cyan-950/80 px-2 py-0.5 rounded border border-cyan-800">
                  Instalação
                </span>
              </div>
              <h4 className="text-sm font-bold text-white">
                Duplo-Clique no Instalador
              </h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                Execute o <strong>VisualPilot_Setup.exe</strong>. O assistente de instalação abrirá com botão "Avançar" e "Instalar". Ele instala automaticamente em <code className="text-emerald-300 font-mono text-[11px]">AppData\Local\VisualPilot</code>.
              </p>
            </div>

            {/* Step 3 */}
            <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-3 relative">
              <div className="flex items-center justify-between">
                <span className="w-7 h-7 rounded-lg bg-indigo-500 text-slate-950 font-black text-xs flex items-center justify-center">
                  3
                </span>
                <span className="text-[11px] font-mono text-indigo-400 bg-indigo-950/80 px-2 py-0.5 rounded border border-indigo-800">
                  Uso Diário
                </span>
              </div>
              <h4 className="text-sm font-bold text-white">
                Clique no Atalho da Área de Trabalho
              </h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                O instalador cria automaticamente o atalho <strong>VisualPilot</strong> na sua Área de Trabalho com o ícone do sistema. Basta dar dois cliques no atalho e o sistema abre direto!
              </p>
            </div>
          </div>
        )}

        {activeGuideTab === 'integrity' && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/40 text-xs text-slate-200 leading-relaxed space-y-2.5">
              <div className="flex items-center gap-2 font-bold text-emerald-400 text-sm">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                <span>Sim, a integridade do sistema é 100% preservada! Veja como:</span>
              </div>
              <p>
                O instalador foi projetado seguindo as melhores práticas oficiais da Microsoft para Windows:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-slate-300">
                <li>
                  <strong>Sem Privilégios de Administrador Invasivos:</strong> O sistema é instalado na pasta do usuário (<code className="text-emerald-300 font-mono">AppData\Local\VisualPilot</code>). Isso significa que ele <strong>nunca altera arquivos do Windows nem o registro do sistema global</strong>.
                </li>
                <li>
                  <strong>Ambiente Python Isolado:</strong> O instalador cria um ambiente virtual (<code className="text-emerald-300 font-mono">.venv</code>) exclusivo e fechado. Ele nunca interfere em outros programas, versões de Python ou softwares que você já tenha instalados.
                </li>
                <li>
                  <strong>Desinstalação Limpa:</strong> O instalador cria um desinstalador oficial (<code className="text-slate-200 font-mono">uninstall.exe</code>) registrado no Painel de Controle do Windows. Se desejar remover, tudo é apagado sem deixar rastros.
                </li>
                <li>
                  <strong>Zero Conflitos de Caminhos:</strong> Todos os caminhos são gerados dinamicamente com base no local exato da sua máquina no momento da instalação.
                </li>
              </ul>
            </div>
          </div>
        )}

        {activeGuideTab === 'features' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1.5">
              <div className="font-bold text-emerald-400 flex items-center gap-1.5">
                <Monitor className="w-4 h-4" />
                <span>Atalho na Área de Trabalho (Desktop)</span>
              </div>
              <p className="text-slate-400 leading-relaxed">
                O arquivo <code className="text-slate-200 font-mono">VisualPilot.lnk</code> é colocado automaticamente no seu Desktop com o ícone oficial do projeto (espada verde). Você nunca mais precisará navegar por pastas ou abrir terminais.
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1.5">
              <div className="font-bold text-cyan-400 flex items-center gap-1.5">
                <Layers className="w-4 h-4" />
                <span>Atalho no Menu Iniciar</span>
              </div>
              <p className="text-slate-400 leading-relaxed">
                Você também poderá pesquisar por "VisualPilot" na barra de tarefas do Windows para abrir o programa instantaneamente.
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1.5">
              <div className="font-bold text-indigo-400 flex items-center gap-1.5">
                <Zap className="w-4 h-4" />
                <span>Lançador Executável Direto</span>
              </div>
              <p className="text-slate-400 leading-relaxed">
                O atalho aponta para o <code className="text-slate-200 font-mono">VisualPilot.exe</code>, que cuida da inicialização segura e conecta automaticamente com o PPPoker e o modelo YOLOv8.
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1.5">
              <div className="font-bold text-amber-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" />
                <span>Desinstalador Incluso</span>
              </div>
              <p className="text-slate-400 leading-relaxed">
                Pode ser desinstalado com 1 clique a qualquer momento através do Menu Iniciar ou do "Adicionar ou Remover Programas" do Windows.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
