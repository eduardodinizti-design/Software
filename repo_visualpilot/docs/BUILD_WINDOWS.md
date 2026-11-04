# Build dos executáveis Windows

O PyInstaller precisa ser executado no Windows de destino, com Python 3.12 de 64 bits. Na raiz do projeto, execute no PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build_windows.ps1
```

Saídas após aprovação das verificações:

- `dist\VisualPilot_Coletor\VisualPilot_Coletor.exe`
- `dist\VisualPilot_Central\VisualPilot_Central.exe`

O coletor usa `visualpilot/pppoker/stream_node.py`. Consulte `COMECE_AQUI_WINDOWS.txt` para configurar os dois computadores.

O build precisa de uma sessão gráfica disponível. O workflow configura o desktop
para 1920×1080 e instala Playwright/Chromium como dependências do laboratório.
Antes da selagem, os executáveis normais capturam mesas gravadas exibidas em uma
janela real, enviam por TCP e publicam OCR e prévias conferidos no navegador.
O teste inclui três mesas, movimentação, reinício, parada, ausência de Hero,
configuração incompleta e diagnóstico de conexão. Resultados e capturas ficam
em `diagnostics/desktop/`. Falha em qualquer etapa impede publicar o candidato.
A selagem confere o relatório Windows e os hashes dos dois pacotes completos.

O painel central abre o navegador e carrega o diagnóstico do Supabase. O indicador fica verde somente quando `nvt_config.ini` possui credenciais válidas e a consulta de diagnóstico responde.
