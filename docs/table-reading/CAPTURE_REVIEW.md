# Revisão do motor e observador — 2026-11-06

Base funcional: commit 2d7478f32493397ebd66f93f9c068d9e444bd2ed; inclui a política de armazenamento anterior. Revisão por inspeção do código e suíte local. Não representa novo ensaio nativo Windows.

| Item | Resultado | Evidência e limite |
|---|---|---|
| HWND/PID/executável/início do processo | CONFORME no código e contratos | WindowCaptureEngine._state, _signature e capture_frame; identidade comparada antes/depois. Lista por nome de executável não autentica assinatura do binário. |
| Seleção explícita sem substituição | CONFORME | test_explicit_invalid_does_not_select_other; ambiguidade bloqueada. |
| Área cliente e origem negativa | CONFORME | GetClientRect, ClientToScreen, GetDC(hwnd), BitBlt origem cliente 0,0. Sem fallback desktop. |
| Superfície Unity grande | CONFORME | Até 36 milhões de pixels, sem limite arbitrário de 1200px; captura real anterior 5760×2160 fornecida pelo usuário. |
| DPI | CONFORME por inspeção/contratos; NÃO VALIDADO em nova matriz Windows | Contexto de thread per-monitor e restauração em finally. Matriz de monitores/escalas ainda pendente. |
| GDI | CONFORME em caminhos inspecionados e contratos | Restaura objeto, DeleteObject bitmap, DeleteDC memória, ReleaseDC origem em finally; verifica falhas. Falhas de limpeza são reportadas, não garantia de que o SO liberou recurso quando a API falha. |
| Vazamento prolongado PPPoker | NÃO VALIDADO | Teste nativo anterior com janela controlada não substitui ensaio prolongado Unity. |
| Diagnóstico independente de OCR | MELHORADO | get_diagnostic_info retorna cópia dos metadados mais recentes; estado de DPI/lista de candidatos reinicializados por tentativa. Teste impede reaproveitar metadados de sucesso após falha. |
| Desempenho por etapa | FALHA de observabilidade corrigida | Agora mede captura, detecção, preparação OCR e leitura das cartas; observador acumula no máximo 120 amostras numéricas e apresenta mediana e p95 nearest-rank a cada 10 ciclos e ao encerrar. |
| Tempo real Windows por etapa | NÃO VALIDADO | Nenhum número de desempenho Windows novo é inventado nesta revisão. Executar observador atualizado. |
| Escrita de arquivos | CONFORME no observador | Métricas apenas em RAM/console, sem frames ou histórico acumulado. |
| Frame congelado/oclusão/alteração durante OCR | NÃO VALIDADO | Sucesso GDI não comprova atualização dos pixels. Identidade é conferida na captura; não há confirmação visual posterior ao OCR. |

Métrica cycle: tempo do início de captura ao término da análise, excluindo espera configurada e impressão. detection inclui conversão RGB e detecção; card_reading inclui OCR de ranks/naipes e pré-processamento; ocr_setup mede descoberta/verificação de Tesseract. Somente ciclos que chegam ao retorno da análise entram na janela estatística; falhas de captura continuam explícitas no console. Essas definições impedem confundir intervalo de 2s com custo de captura.

Validação local: 53 testes, 52 passaram, 1 teste exclusivo de Windows ignorado. Novos testes são contratos, não medições de precisão nem desempenho do PPPoker. Sem mudança de limiares ou fallback visual nesta revisão.

Próximo passo: executar por alguns minutos `python ler_mesas.py --hwnd 264430 --continuo --intervalo 1`, encerrar com Ctrl+C e comparar os TEMPOS FINAIS. O identificador deve corresponder à janela atual. Só então selecionar a otimização. O reconhecimento do K pequeno e do par 99 continua pendente de validação específica.
