# Central com acompanhamento visual

A Central recebeu uma prévia das mesas transmitidas pelo coletor, separada do resultado do OCR. As imagens são locais à conexão já existente PC → notebook; nenhuma imagem é enviada a um serviço externo de IA por esta funcionalidade.

## O que aparece

- Prévia RGB convertida em JPEG, limitada a 500 pixels de largura e até duas atualizações por segundo por mesa; até seis mesas em memória.
- Horário UTC de recebimento, idade do último frame e idade da imagem exibida.
- Cartas do Hero, board, etapa, pote, stack, botões/valores e ações visíveis de jogadores, conforme o leitor existente; campos sem reconhecimento permanecem pendentes.
- Idade da leitura e idade da amostra ao publicar. Esta última não mede o tempo completo de captura/rede nem isoladamente o tempo de execução do OCR.
- Alerta de imagem congelada depois de cinco segundos sem frame e alerta independente de leitura desatualizada.
- Tempo desde a primeira leitura consolidada com botões visíveis. A contagem não começa necessariamente no primeiro pixel em que os botões apareceram.
- Botão **Marcar decisão para revisão**: registra uma anotação temporal manual; não clica no PPPoker e não confirma qual jogada foi feita.
- Momentos recentes e download JSON. O diário integral permanece na pasta da sessão.

## Registro e limites

`<sessão>/acompanhamento/eventos.jsonl` registra amostras de leituras, aparição/desaparição de opções e marcadores manuais. As imagens ficam em `acompanhamento/evidencias/`, vinculadas por caminho e hash à leitura da mesma amostra. A prévia pode ser mais recente que a leitura; não é usada como evidência dessa leitura.

Amostragem de evidências: no máximo uma por mesa a cada dois segundos de observação consolidada, até 64 MB por sessão. Diário adicional limitado a 32 MB. Ao atingir limites, o painel avisa; a prévia continua. A interface mantém somente 30 eventos recentes por mesa. Não é gravação de vídeo contínua nem um clipe completo da mão.

Desaparecimento dos botões é um evento observado, nunca uma confirmação de fold/call/raise. Lacunas acima de cinco segundos, mudanças de mão/contexto e leituras incertas cancelam o intervalo. Sem botão ou contexto confiável, não se inventa um tempo de decisão. A posição/estratégia não ganhou inferências novas nesta entrega.

## Uso

Depois de atualizar e gerar a Central no Windows, abrir a Central no notebook, clicar **Iniciar coleta** e abrir o coletor no PC com uma mesa fictícia visível. A prévia aparece quando chegam frames, mesmo antes de o OCR terminar. A configuração de rede existente é reutilizada.

Para revisão, marcar o momento no painel e ao terminar clicar **Parar coleta**. Guardar a pasta da sessão indicada na tela: ela contém o histórico original e o acompanhamento adicional. O executável que já está no notebook não se atualiza sozinho.

## Validação

- Testes unitários de frescor, intervalo, cancelamento, isolamento/limites, marcadores e persistência.
- Testes de transporte verificam previews das seis identidades após receber pacotes TCP.
- Testes de reconexão com OCR real verificam imagem e arquivo de acompanhamento.
- Chromium + Streamlit + receptor TCP + OCR reais, usando frame real previamente gravado: prévia, leitura, marcador manual, registro e congelamento após interromper envio. Também tela de 390 pixels.
- Evidências: `targeted.log`, `unified.log`, `browser.json`, `browser-run.log` e screenshots.

A implementação foi feita em checkout separado para não modificar o código utilizado pela rodada de estratégia ativa. Testes realizados em Linux; não houve compilação de executável Windows nem teste físico entre os dois computadores nesta entrega.

Resultado final: **267 testes executados, 264 aprovados e 3 ignorados, sem falhas**. Nove verificações direcionadas passaram após os ajustes finais da apresentação. O ensaio de navegador registrou um marcador manual e duas amostras de leitura, confirmou o aviso de congelamento, sem erro JavaScript e sem overflow externo em 390 pixels.

Durante o ensaio foi corrigida a contagem quando o board ainda está pendente, mas os botões são legíveis na leitura consolidada. Isso permite medir a disponibilidade das opções sem inventar a etapa pré-flop. As ações e botões são exibidos em texto simples; os detalhes técnicos permanecem recolhidos.
