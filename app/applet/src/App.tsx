import React, { useState } from 'react';
import { 
  Activity, Download, FileText, Layers, Terminal, ShieldCheck, 
  Cpu, CheckCircle2, RefreshCw, Zap, ExternalLink, Code, Sparkles, Upload, Check
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'ai_vision' | 'monitor' | 'installer' | 'files'>('installer');
  const [copied, setCopied] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);

  const handleCopyCode = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const testImageAnalysis = async () => {
    setAnalyzing(true);
    try {
      const res = await fetch('/api/analyze-table', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_base64: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        })
      });
      const data = await res.json();
      setAnalysisResult(data);
    } catch (e: any) {
      setAnalysisResult({ status: 'ERROR', message: e.message });
    } finally {
      setAnalyzing(false);
    }
  };

  const batScript = `@echo off
title VisualPilot Clean Bot - Central Operacional
echo [VisualPilot v3.0] Iniciando Bot Limpo (Window Stream + Deterministic Engine)...
python -m pip install -r requirements.txt
python bot_standalone.py
pause`;

  const reqContent = `numpy>=1.20.0
opencv-python>=4.5.0
pytesseract>=0.3.8
pywin32>=300
mss>=6.1.0
pygetwindow>=0.0.9
requests>=2.25.0`;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-none">
      {/* Top Header */}
      <header className="bg-[#0b0f19] border-b border-slate-800 px-6 py-4 flex flex-col sm:flex-row items-center justify-between shadow-lg gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 via-teal-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent">
              VisualPilot v3.0 • Versão Limpa & Otimizada
            </h1>
            <p className="text-xs text-slate-400">Window Stream GDI (~3ms) + Deterministic Engine + Gemini AI Vision</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center bg-slate-900 border border-slate-800 p-1 rounded-xl shadow-inner flex-wrap gap-1">
          <button
            onClick={() => setActiveTab('installer')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'installer'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Download className="w-4 h-4" /> Download Versão Limpa (.ZIP)
          </button>
          <button
            onClick={() => setActiveTab('ai_vision')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'ai_vision'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Sparkles className="w-4 h-4 text-amber-300" /> Teste Visão IA (Gemini)
          </button>
          <button
            onClick={() => setActiveTab('monitor')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'monitor'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Activity className="w-4 h-4" /> Monitoramento
          </button>
          <button
            onClick={() => setActiveTab('files')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'files'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Code className="w-4 h-4" /> Arquivos Essenciais
          </button>
        </nav>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto p-6 bg-slate-950/90">
        <div className="max-w-6xl mx-auto space-y-6">

          {/* TAB: INSTALADOR & DOWNLOAD LIMPO */}
          {activeTab === 'installer' && (
            <div className="space-y-6">
              <div className="bg-[#0b0f19] border border-slate-800 rounded-2xl p-6 shadow-xl">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                    <Download className="w-5 h-5 text-emerald-400" /> Pacote Limpo Distribuível (.ZIP)
                  </h2>
                  <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2.5 py-1 rounded-full font-mono">
                    Apenas Arquivos Essenciais
                  </span>
                </div>
                <p className="text-xs text-slate-300 mb-6 leading-relaxed">
                  Removivemos todos os arquivos legados e obsoletos. Esta versão limpa contém estritamente o motor de alta performance necessário para rodar o bot na sua máquina sem ruído ou arquivos desnecessários.
                </p>

                {/* Primary Download Card */}
                <div className="bg-gradient-to-r from-emerald-950/40 to-cyan-950/40 border border-emerald-500/30 rounded-xl p-6 mb-6 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div>
                    <h3 className="text-base font-bold text-slate-100">VisualPilot_Bot_Clean_v3.0.zip</h3>
                    <p className="text-xs text-slate-300 mt-1">Contém: bot_standalone.py, window_stream.py, yolo_card_detector.py, prepare_templates.py, requirements.txt</p>
                  </div>
                  <a
                    href="./downloads/VisualPilot_Bot_Clean_v3.0.zip"
                    download
                    className="flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/30 transition-all cursor-pointer shrink-0"
                  >
                    <Download className="w-4 h-4" /> Baixar Versão Limpa (.ZIP)
                  </a>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-mono font-bold text-emerald-400">run_bot.bat</span>
                        <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-300">Windows</span>
                      </div>
                      <pre className="bg-slate-950 p-2.5 rounded border border-slate-800 text-[10px] font-mono text-slate-300 overflow-x-auto h-28">
                        {batScript}
                      </pre>
                    </div>
                    <button
                      onClick={() => handleCopyCode(batScript, 'bat')}
                      className="mt-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition-colors cursor-pointer"
                    >
                      {copied === 'bat' ? 'Copiado!' : 'Copiar Script'}
                    </button>
                  </div>

                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-mono font-bold text-amber-400">requirements.txt</span>
                        <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-300">Pip</span>
                      </div>
                      <pre className="bg-slate-950 p-2.5 rounded border border-slate-800 text-[10px] font-mono text-slate-300 overflow-x-auto h-28">
                        {reqContent}
                      </pre>
                    </div>
                    <button
                      onClick={() => handleCopyCode(reqContent, 'req')}
                      className="mt-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition-colors cursor-pointer"
                    >
                      {copied === 'req' ? 'Copiado!' : 'Copiar Requisitos'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: AI VISION TESTER */}
          {activeTab === 'ai_vision' && (
            <div className="space-y-6">
              <div className="bg-[#0b0f19] border border-slate-800 rounded-2xl p-6 shadow-xl">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-amber-400" /> Visão Multimodal com Gemini API
                  </h2>
                  <span className="text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2.5 py-1 rounded-full font-mono">
                    Zero-Shot Precision
                  </span>
                </div>
                <p className="text-xs text-slate-300 mb-6 leading-relaxed">
                  Teste o modelo <code className="text-emerald-400 font-mono">gemini-3.8-flash</code> para leitura de mesas de poker diretamente via API no servidor backend.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-slate-200 mb-2">Testar Endpoint `/api/analyze-table`</h3>
                      <p className="text-xs text-slate-400 mb-4">Envia uma imagem de teste para o servidor analisar as cartas e retornar o JSON estruturado.</p>
                    </div>
                    <button
                      onClick={testImageAnalysis}
                      disabled={analyzing}
                      className="w-full py-3 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-emerald-600/30 transition-all cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      {analyzing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                      {analyzing ? 'Analisando...' : 'Testar Conexão com Gemini API'}
                    </button>
                  </div>

                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 font-mono text-xs flex flex-col justify-between">
                    <div>
                      <span className="text-slate-400 block mb-2 font-sans font-bold">Resposta JSON:</span>
                      <pre className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-emerald-400 overflow-x-auto h-36">
                        {analysisResult ? JSON.stringify(analysisResult, null, 2) : '// Clique ao lado para testar...'}
                      </pre>
                    </div>
                    <div className="mt-4 text-[11px] text-slate-400 font-sans flex items-center justify-between">
                      <span>Modelo: <strong className="text-slate-200">gemini-3.8-flash</strong></span>
                      <span className="text-emerald-400 font-bold">Online</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: MONITORAMENTO */}
          {activeTab === 'monitor' && (
            <div className="space-y-6">
              <div className="bg-[#0b0f19] border border-slate-800 rounded-2xl p-6 shadow-xl">
                <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2 mb-2">
                  <Activity className="w-5 h-5 text-emerald-400" /> Status do Sistema Window Stream
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                    <span className="text-xs text-slate-400">Captura</span>
                    <div className="text-lg font-bold font-mono text-emerald-400 mt-1">GetClientRect + BitBlt (~3ms)</div>
                  </div>
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                    <span className="text-xs text-slate-400">Filtro de Janela</span>
                    <div className="text-xl font-bold font-mono text-cyan-400 mt-1">Vertical PPPoker</div>
                  </div>
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                    <span className="text-xs text-slate-400">Detecção</span>
                    <div className="text-xl font-bold font-mono text-amber-400 mt-1">Template Matching + Otsu</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: ARQUIVOS ESSENCIAIS */}
          {activeTab === 'files' && (
            <div className="space-y-6">
              <div className="bg-[#0b0f19] border border-slate-800 rounded-2xl p-6 shadow-xl">
                <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2 mb-2">
                  <Code className="w-5 h-5 text-emerald-400" /> Arquivos da Versão Limpa v3.0
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-mono text-xs mt-4">
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                    <span className="text-emerald-400 font-bold">bot_standalone.py</span>
                    <p className="text-[11px] text-slate-400 font-sans mt-0.5">Interface Tkinter e Loop de Monitoramento</p>
                  </div>
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                    <span className="text-emerald-400 font-bold">window_stream.py</span>
                    <p className="text-[11px] text-slate-400 font-sans mt-0.5">Capturador Win32 GDI BitBlt (~3ms)</p>
                  </div>
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                    <span className="text-emerald-400 font-bold">yolo_card_detector.py</span>
                    <p className="text-[11px] text-slate-400 font-sans mt-0.5">Detector Determinístico + Curto-Circuito OCR</p>
                  </div>
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                    <span className="text-emerald-400 font-bold">prepare_templates.py</span>
                    <p className="text-[11px] text-slate-400 font-sans mt-0.5">Utilitário de Binarização com Otsu</p>
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}
