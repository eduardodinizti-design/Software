import React from 'react'
import { Download, Terminal, Cpu, ShieldCheck, FileText, CheckCircle2 } from 'lucide-react'

export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-white p-8 font-sans">
      <header className="max-w-4xl mx-auto mb-8">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
          VisualPilot - Central de Download do Bot PPPoker
        </h1>
        <p className="text-slate-400 mt-2">
          Baixe os arquivos atualizados com correção no detector YOLOv8 para execução local no Windows.
        </p>
      </header>

      <main className="max-w-4xl mx-auto space-y-6">
        {/* Download Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* bot_standalone.py */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <Terminal className="w-6 h-6 text-emerald-400" />
                <h3 className="text-lg font-semibold text-white">bot_standalone.py</h3>
              </div>
              <p className="text-slate-400 text-sm mb-4">
                Script principal em Python com interface Tkinter, captura de janelas Win32 e integração YOLOv8.
              </p>
            </div>
            <a
              href="/bot_standalone.py"
              download="bot_standalone.py"
              className="inline-flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-2 px-4 rounded-lg transition-colors text-sm"
            >
              <Download className="w-4 h-4" /> Baixar bot_standalone.py
            </a>
          </div>

          {/* yolo_card_detector.py */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <Cpu className="w-6 h-6 text-cyan-400" />
                <h3 className="text-lg font-semibold text-white">yolo_card_detector.py</h3>
              </div>
              <p className="text-slate-400 text-sm mb-4">
                Módulo neural YOLOv8 Nano otimizado para CPU com suporte a onnx_path e detecção de 52 cartas.
              </p>
            </div>
            <a
              href="/yolo_card_detector.py"
              download="yolo_card_detector.py"
              className="inline-flex items-center justify-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white font-medium py-2 px-4 rounded-lg transition-colors text-sm"
            >
              <Download className="w-4 h-4" /> Baixar yolo_card_detector.py
            </a>
          </div>

          {/* yolov8n_cards.onnx */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <ShieldCheck className="w-6 h-6 text-purple-400" />
                <h3 className="text-lg font-semibold text-white">yolov8n_cards.onnx</h3>
              </div>
              <p className="text-slate-400 text-sm mb-4">
                Modelo de pesos ONNX treinado para detecção de cartas em ~8ms (7.7 MB).
              </p>
            </div>
            <a
              href="/yolov8n_cards.onnx"
              download="yolov8n_cards.onnx"
              className="inline-flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 text-white font-medium py-2 px-4 rounded-lg transition-colors text-sm"
            >
              <Download className="w-4 h-4" /> Baixar yolov8n_cards.onnx
            </a>
          </div>

          {/* requirements.txt */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <FileText className="w-6 h-6 text-amber-400" />
                <h3 className="text-lg font-semibold text-white">requirements.txt</h3>
              </div>
              <p className="text-slate-400 text-sm mb-4">
                Lista de dependências Python (opencv-python, numpy, pytesseract, pillow, onnxruntime).
              </p>
            </div>
            <a
              href="/requirements.txt"
              download="requirements.txt"
              className="inline-flex items-center justify-center gap-2 bg-amber-600 hover:bg-amber-500 text-white font-medium py-2 px-4 rounded-lg transition-colors text-sm"
            >
              <Download className="w-4 h-4" /> Baixar requirements.txt
            </a>
          </div>
        </div>

        {/* Instructions */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
          <h2 className="text-xl font-semibold mb-3 text-emerald-400 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" /> Instruções de Instalação e Execução
          </h2>
          <ol className="list-decimal list-inside space-y-2 text-slate-300 text-sm">
            <li>Baixe todos os 4 arquivos acima na mesma pasta no seu computador (ex: <code className="bg-slate-950 px-2 py-0.5 rounded text-emerald-300">C:\Visualpilot</code>).</li>
            <li>Abra o terminal na pasta e instale as dependências: <code className="bg-slate-950 px-2 py-0.5 rounded text-cyan-300">pip install -r requirements.txt</code></li>
            <li>Execute o bot: <code className="bg-slate-950 px-2 py-0.5 rounded text-cyan-300">python bot_standalone.py</code></li>
          </ol>
        </div>
      </main>
    </div>
  )
}
