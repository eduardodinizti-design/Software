# Gabaritos do lobby Karekas ao vivo (Fase 3A)

Crops do PAINEL DO LOBBY extraídos do canvas real do PPPoker (HWND ao vivo,
`find_lobby_crop`), clube Karekas, em 09/11/2026. Cada imagem é 1005×1787 (o
painel recortado do canvas Unity 3840×1440, capturado em 5760×2160 por DPI 1.5×).

Servem para calibrar/validar offline a leitura do lobby (`grade_reader.read_grade`,
`lobby_runner`) — a linha de status do cartão ALTERNA entre o stack inicial e
"Registro encerra em N min", por isso capturas congeladas ajudam.

- `karekas-lobby-live-1.png` — PKOs de prêmio garantido grande (EXPLORE/WARRIOR/
  HIGH/TNT PKO).
- `karekas-lobby-live-2.png` — mix (DEEP FREEZEOUT, BOX MISTERY, SUNSET, WORLD,
  3 HANDED, FREEZEOUT).

Observação: são screenshots do lobby (lista de torneios), sem dados de conta
sensíveis. Ground truth e validações no doc `repo_visualpilot/docs/fase3-registrador/`.
