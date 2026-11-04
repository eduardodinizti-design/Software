# Continuação — etapas do board e painel

## Ensaios executados

1. Auditoria das 36 fixtures sintéticas com CardRegionReader padrão (0.90),
   no ROI de turn: 34 reconhecidas, Kh e Ks pendentes. Evidência em
   production-threshold.json. Isso não mede cobertura real do baralho nem
   cobertura das cartas do Hero. O limite não foi reduzido.
2. Expansão do teste integrado de uma mesa: imagens-base gravadas, turn 2h e
   river 3c compostos com patches sintéticos. TCP local, OCR real, eventos
   parciais e completos, Hero Th/4d preservado, board e etapa comparados ao
   gabarito e diário JSONL verificado. Cinco cenários no mesmo runtime.
   Duas execuções aprovadas: pipeline-before.log (etapa na parcial) e
   pipeline-final.log (etapa e board também na leitura completa).
3. Streamlit 1.50.0 instalado no laboratório. AppTest executa a aplicação real,
   verifica Mesa 1 e JSON de river e aciona Parar. O controlador está isolado;
   não é um teste de navegador físico ou do transporte dentro do painel.
   Resultado: panel.log.

## Resultado e limites

A sequência controlada flop → turn → river passou nas duas vias de leitura.
Na execução pipeline-final, turn levou 0.653 s até a parcial e 3.026 s até a
completa; river 0.290 s e 2.440 s. São amostras de replay local, não SLA.

Nenhuma alteração no classificador foi necessária para esses cenários. As duas
cartas sintéticas pendentes permanecem uma lacuna explícita. Não ajustamos o
leitor para decorar fixtures ou reduzir o limite de aceitação.

Faltam: resolver a qualidade/leitura dos dois K sintéticos com evidência
independente, cartas em outras posições/escalas, captura e executáveis Windows,
frontend no navegador real e uma prova contínua captura→painel em duas máquinas.
Nenhuma instalação foi solicitada ao usuário.

Suíte final: 155 testes executados em 52,003 s, OK (3 skips).
Streamlit AppTest executado (não ignorado). `pip check`: nenhuma dependência quebrada.
