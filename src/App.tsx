import React from 'react'

export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-white p-8 font-sans">
      <header className="max-w-4xl mx-auto mb-8">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
          VisualPilot - Central Operacional de Poker Multi-Mesas
        </h1>
        <p className="text-slate-400 mt-2">
          Rastreamento visual dinâmico de mesas Unity para PPPoker (Até 6 mesas simultâneas com identidade estável).
        </p>
      </header>
      <main className="max-w-4xl mx-auto bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl">
        <h2 className="text-xl font-semibold mb-4 text-emerald-400">Status do Sistema Multi-Mesas</h2>
        <p className="text-slate-300">
          O mecanismo de rastreamento visual (`MultiTableTracker`), validação de DPI e roteamento OCR opera ativamente em segundo plano.
        </p>
      </main>
    </div>
  )
}
