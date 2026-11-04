# Visual Pilot

Observação local de mesas de simulações com fichas fictícias no PPPoker, com registros para estudo. **Não escolhe nem executa jogadas.**

O motor de percepção do projeto anterior foi recuperado e conectado à aplicação. O modo padrão encontra mesas pelo tema azul e lê o baralho de quatro cores observado nas imagens fornecidas. Não exige cadastrar manualmente 52 cartas nem selecionar um perfil JSON para esse layout.

**Ainda não é uma versão homologada no Windows ou para seis mesas continuamente atualizadas.** Veja a [avaliação do reaproveitamento](docs/LEGACY_REUSE.md) e os [resultados reproduzidos com imagens](docs/pppoker-image-validation.json).

O [laboratório fictício](docs/LABORATORIO_FICTICIO.md) abre seis mesas e executa cinco trocas simultâneas. Todas foram reconhecidas sem mistura. Depois do aquecimento, Hero e board das seis mesas ficaram disponíveis em 0,66–0,72 s; o snapshot textual completo ainda levou até 20,44 s.

O [motor de regiões](docs/ROI_ENGINE.md) usa recortes calibrados nas imagens reais para ignorar animações fora dos campos observáveis sem perder mudanças pequenas de valor ou naipe.

O [baralho sintético de regressão](docs/DATASET_SINTETICO.md) completa as 36 combinações ausentes para testes automatizados, com proveniência explícita. A validação real continua limitada às 16 cartas presentes no material recebido.

A [integração configurável com o Range Coach Pro](docs/RANGE_COACH_CONNECTOR.md) consulta ranges e envia telemetria de torneios fictícios por HTTPS. Ela permanece desativada sem `nvt_config.ini` e não executa jogadas.

## Iniciar no Windows

Use Python **3.12 de 64 bits**, com Tcl/Tk e PATH habilitados. Na pasta do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\Iniciar.cmd
```

Clique em **Iniciar** para buscar mesas nos monitores. Mantenha as mesas visíveis e o painel do Visual Pilot fora delas. Clique em **Parar** para finalizar e salvar; fechar a janela também aguarda a finalização. O último registro continua disponível na pasta da sessão. F12 para enquanto o painel tem foco.

O modo PPPoker usa RapidOCR/ONNX local e seus modelos incluídos na dependência. **Não precisa de Tesseract**, tokens ou serviços externos. Não use a `.venv` do projeto antigo: recrie o ambiente com as dependências desta versão. Ela usa uma única distribuição OpenCV para evitar conflito entre `opencv-python` e `opencv-python-headless`.

## O que está integrado

- Localização visual por referência do chat do PPPoker em diferentes escalas; varredura de todos os monitores, inclusive coordenadas negativas.
- Vínculo de leitura com janelas nativas do Windows, quando disponível, e proteção contra janela movida/encoberta. O vínculo nativo melhora o acompanhamento; não autoriza cliques.
- Até seis mesas; mais mesas visíveis geram erro explícito, sem selecionar seis silenciosamente.
- Dois processos OCR e fila limitada a uma captura pendente por mesa, com substituição por captura recente e prioridade com controle de espera.
- Cache exato da área útil da mesa, inclusive para leituras parciais válidas. Alterações no título da janela não disparam OCR; mudanças nas cartas, jogadores, pote, stack ou botões invalidam o cache.
- Leitura separada de Hero, board, botões do Hero, etiquetas de ação dos jogadores, ID da mão, pote e stack do Hero.
- Confirmação de cartas por repetição na mesma mão com ID conhecido. ID ilegível não confirma uma mão por suposição. Tentativa de leitura e resultado validado são preservados separadamente.
- Invalidação das regiões que mudaram enquanto o OCR trabalhava; leituras com mais de cinco segundos ficam pendentes na interface. Idade corresponde à captura, não ao instante da ação do jogador.
- Evidências amostradas, diagnóstico por carta e métricas por mesa/sessão.

As ações dos jogadores são **etiquetas visíveis**, não eventos completos nem uma sequência reconstruída. Nomes truncados permanecem truncados e não são associados por popup. A quantia dessas etiquetas permanece desconhecida quando não foi lida. Os botões do Hero preservam valores no texto quando reconhecidos. Não há motivo estratégico inferido.

O board ausente ou ilegível permanece desconhecido: não se declara pré-flop pela simples ausência de reconhecimento. No motor recuperado, a confirmação explícita de pré-flop ainda precisa ser desenvolvida/validada. Flop, turn e river dependem de três, quatro ou cinco cartas legíveis; temas, animações e layouts novos precisam de avaliação adicional.

## Registros e evidências

Modo padrão:

```text
sessions/AAAA-MM-DD/Sessao_HHMMSS_microssegundos/
  session.json       # modo, início, layout e processos
  percepcao.jsonl     # observações, leitura original e contexto validado
  metricas.json       # OCR, atrasos, cobertura, descarte e espaço usado
  evidencias/*.png    # amostradas por mesa; não cobre cada ação
sessions/Observacao/  # descoberta/captura e acompanhamento das mesas em SQLite
```

A data usa o fuso do computador. A coleta salva os campos observados quando mudam, sem inventar dados de mãos anteriores. Evidências diferentes são amostradas a cada 10s por mesa, até 256 MiB por sessão; pixels idênticos podem compartilhar a mesma evidência. Ao atingir a cota, as observações continuam e a falta de nova evidência fica explícita. PNGs são gravados de forma síncrona; isso pode afetar latência. O JSONL é descarregado após cada registro, mas não garante integridade contra queda de energia ou disco cheio.

As imagens podem conter nomes mostrados no PPPoker. Permanecem locais; a aplicação não envia capturas. `sessions/` é ignorada pelo Git.

## Testar e reproduzir leituras

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m visualpilot.validate_pppoker
.\.venv\Scripts\python.exe tools\benchmark_pppoker.py --workers 2
```

O segundo comando processa os recortes rotulados disponíveis em `tests/fixtures/heldout_cards` e grava o relatório em `sessions/validation/pppoker-images.json`, incluindo quais imagens faltam. Essas imagens vieram do mesmo vídeo usado no projeto anterior, portanto não são uma amostra independente de outro ambiente.

Em Linux, os comandos usam `.venv/bin/python`; leitura de arquivos não precisa de display. Captura real e interface exigem uma sessão gráfica. O modo PPPoker sem interface é `python -m visualpilot.app --headless`; Ctrl+C finaliza a sessão.

## Modo experimental de templates

A base inicial foi preservada para reprodução e comparação. Para usá-la, passe explicitamente `--profile`:

```powershell
.\.venv\Scripts\python.exe -m visualpilot.app --profile profiles\meu-perfil.json
.\.venv\Scripts\python.exe -m visualpilot.app --headless --profile profiles\meu-perfil.json --replay capturas
```

Esse modo tem outro esquema de arquivos (`observations.jsonl`, `metrics.json`, `evidence/`) e requer um perfil calibrado. Veja [profiles/README.md](profiles/README.md). OCR textual nesse modo utiliza Tesseract instalado separadamente; `--tesseract` aceita o caminho do executável. O modo padrão PPPoker não depende dele.

Demo **sintético**, que apenas testa o fluxo de arquivos:

```powershell
.\.venv\Scripts\python.exe -m visualpilot.demo --output sessions\demo-input
.\.venv\Scripts\python.exe -m visualpilot.app --headless --profile sessions\demo-input\profile.json --replay sessions\demo-input\frames --interval 0.2
```

## Ainda necessário para aprovar a primeira versão

- Instalar e testar no seu Windows com o PPPoker atual, nos dois monitores e nas escalas/DPI usados de verdade.
- Conferir leituras de cartas e ações contra imagens/vídeo rotulados em outras sessões; avaliar cartas encobertas, animações e alterações de tema.
- Verificar mudança de mãos, janelas movidas/trocadas, nome/ID ilegível e expiração sem misturar informações.
- Medir revisita de cada mesa e quantas ficam recentes ao mesmo tempo durante uma sessão de seis mesas. O projeto anterior relata que seis mesas **não** passaram no critério de atualização contínua; isso não foi resolvido nesta integração.
- O benchmark atual confirmou seis mesas estáveis em 13,2 s e terminou com as seis leituras recentes. Três processos saturaram esta máquina e confirmaram apenas três mesas; por isso o padrão permanece em dois. O primeiro ciclo continua acima da meta e mesas com animação/mudanças frequentes reduzem o benefício do cache.
- Implementar/validar evidência positiva de pré-flop e conferir cobertura de pote, stack, botões e valores no idioma do cliente.

Ranges, decisões, GTO, cliques, identificação por popup e reconstrução completa em TXT continuam fora do escopo.
