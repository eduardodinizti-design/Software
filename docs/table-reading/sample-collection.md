# Coleta pontual para rotulagem humana

Uma execução coleta um único frame e salva apenas três regiões nativas de cada mesa completa detectada: cartas próprias com margem (x51–80%, y75–93%), banda comunitária já usada pelo leitor e faixa inferior dos botões (y92–100%). Não salva imagem inteira nem recorte completo da mesa. Não executa OCR, cliques, leitura contínua ou importação de treino.

No Windows, com a mesa aberta e HWND atual conhecido:

```
python coletar_amostras.py --hwnd 264430
```

O número é um exemplo; deve corresponder ao HWND atual. A captura usa exclusivamente `WindowCaptureEngine.capture_frame(hwnd=...)`; erro ou divergência do HWND interrompe a coleta.

Para uma captura existente acompanhada de seus metadados:

```
python coletar_amostras.py --image logs/diagnostics/capture-EXEMPLO.png --metadata logs/diagnostics/capture-EXEMPLO.json
```

`--max-tables` aceita 1–6; `--logs-root` altera a raiz de armazenamento (padrão `logs`). Use a mesma raiz dos diagnósticos para compartilhar o orçamento global.

Saída: `logs/leitura/leitura-UUID/resultado.json` e três PNGs por mesa. O manifesto registra identidade de origem, hash do frame, dimensões, caixas relativas, hashes dos PNGs e pixels, ausência de redimensionamento e proveniência live/offline. Todas as regiões têm `status: UNLABELED` e `labels: null`; detecção não atribui rótulos. PNGs podem mostrar cartas ausentes ou animações: revisão humana é obrigatória antes de qualquer uso posterior em treino.

Limites: até 2 MiB por bundle incluindo JSON, até 6 mesas, orçamento global 100 MiB gerenciado pelo `diagnostic_storage.store_bundle`. A rotação existente remove bundles reconhecidos antigos, respeitando `.keep`; arquivos externos/protegidos podem impedir a gravação. Falhas de metadados e tamanho de entrada são verificadas antes de criar arquivos. Coletar sem mesa completa falha sem salvar. O limite é de armazenamento, não uma garantia de suporte a determinada resolução.

Metadados offline são fornecidos pelo usuário: identidade e dimensões são verificadas, e `frame_sha256` também quando presente. Sem um hash prévio, o programa não consegue provar que um JSON de mesmas dimensões pertence à imagem; registra explicitamente essa proveniência, sem alegar uma captura Windows validada.

Validação em Linux: sete testes passaram com PNG real do acervo, igualdade exata dos pixels salvos, bounds e hashes, captura Windows simulada, entrada inválida, limite de seis e falha de orçamento sem gravações. Captura Windows real permanece a validar posteriormente.
