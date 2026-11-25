# Captura de mão do KKPoker (Electron) — plano

Engine (memória [[nvt-salas-engines]]): **KKPoker = Electron (Chromium + Node)**. Processo:
`KKPoker Global.exe` (ou `KKPoker.exe`). Sendo Electron, a mão trafega num **WebSocket** do
renderer — dá p/ observar por **CDP** (DevTools Protocol), sem Frida. É o caminho mais limpo
dos quatro.

## Estado
- Downstream agnóstico de sala: PRONTO (`room='KKPoker'`).
- Recon: `recon_kkpoker.py` (CDP via `websockets`): reabre o KKPoker com `--remote-debugging-port`,
  acha os alvos `/json/list`, habilita Network/Runtime e LOGA os frames WS (recv/send) do jogo.

## Sessão ao vivo
1. Feche o KKPoker. `python -I recon_kkpoker.py --launch` (reabre com a porta 9222).
2. Entre numa MESA, jogue 1 mão; observe `[kk]<=`/`=>` (frames WS).
3. Caracterizar o protocolo:
   - **texto/JSON (opcode 1):** ótimo — ler os campos direto e mapear o fluxo da mão.
   - **binário (opcode 2, protobuf):** pegar o payload (base64) e decodificar (como no PPPoker);
     achar o .proto/descritor no asar do app (`resources/app.asar`) ajuda muito.
4. Emitir EVENTOS NORMALIZADOS (mesmo contrato) → `HandAccumulator(room='KKPoker')` → `.txt` → NvtTracker.

## Se o CDP não subir (fuses do Electron)
Alguns Electron desligam o inspector por *fuses* (`EnableNodeCliInspectArguments`/
`RunAsNode`). Então:
- Checar as fuses do binário (REA: `inspect_electron_fuses`; tools `list_electron_targets`,
  `capture_electron_scenario`).
- Fallback: Frida no processo renderer hookando o WebSocket nativo do Chromium (ou o
  `app.asar` desempacotado p/ achar o dispatcher JS e hookar via CDP `Runtime.evaluate`).

## Notas
- `--remote-debugging-port` escuta só em 127.0.0.1; nada exposto p/ fora.
- Multi-conta: 1 processo por janela → discriminar mesa por PID/target.
- Decodificar o `app.asar` (JS do cliente) dá os nomes das mensagens e acelera tudo.
