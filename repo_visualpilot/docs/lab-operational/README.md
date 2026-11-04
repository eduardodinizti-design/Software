# Reconhecimento do baralho colorido — rodada de correção

A etapa operacional 1 continua **não aprovada**. Há uma correção candidata real,
ativada explicitamente com `colored_deck=True`, mas não instalada no notebook nem
habilitada no coletor ou no serviço OCR padrão. As etapas 2–5 não foram aprovadas.

## Alterações executadas

- Localização por fundos vermelho, verde, azul e cinza, com verificação de geometria.
- Validação adicional do símbolo; fundo colorido sozinho não autoriza uma carta.
- OCR dos valores claros, incluindo cartas escurecidas após fold; concordância em
  duas versões com margem diferente e confiança mínima de 0,95.
- Alternativa que preserva antialiasing para dígitos fragmentados por JPEG.
- Remoção de pequenas pontes de ruído na borda antes da localização.
- Duplicidades e cartas incompletas continuam recusadas pelo leitor comum.
- Recorte experimental do flop ampliado **somente no benchmark**. A calibração
  geral de captura permanece pendente; não foi alterada globalmente por uma imagem.

## Evidências e ciclos

1. Leitor anterior: 12/18 casos passaram; os seis positivos falharam. Sete testes
   antigos passaram, demonstrando que eles não cobriam o novo baralho.
2. Localização por cor e inversão dos glifos: 17/18. A segunda leitura do 10 não
   atingiu a confiança exigida. Ajuste de enquadramento levou a 18/18.
3. Ampliação para 60 casos derivados: 57/60. Compressão/redução cortavam o segundo
   dígito do 10. Recorte de valor ampliado: 60/60.
4. Testes específicos de compressão do recorte (diferente de comprimir a mesa):
   detectada uma ponte de ruído até a borda. Abertura morfológica corrigiu localização,
   mas ainda restou erro de OCR. Uma filtragem intermediária piorou os resultados;
   não foi mantida.
5. Alternativa preservando antialiasing, usada quando a leitura binária não atende
   ao critério: oito testes específicos passaram e os 60 casos derivados passaram.
   A primeira suíte ampla capturou a falha intermediária; a suíte final foi repetida.

Os 60 casos contêm **20 positivos e 40 negativos**, de **três quadros reais**, sendo
apenas um quadro com cartas. As cinco cartas presentes são 2c, 4h, 9c, Th, 6c.
Variações de brilho, escala e JPEG não são novas mãos nem validação independente.

Arquivos verificáveis:

- `colored-baseline.json`: comportamento antes da correção.
- `colored-stress-before-rank-fix.json`: falhas reproduzidas na expansão de casos.
- `colored-stress.json`: última execução do benchmark, hash de cada imagem e diagnósticos.
- `colored-tests.log`: testes de recusa, duplicidade, compressão e limite de confiança.
- `full-regression.log`: suíte ampla na versão final do leitor.
- `full-regression-before-final-fix.log`: suíte anterior, com falha conhecida registrada.

## Acompanhamento de execução

O benchmark agora atualiza automaticamente um arquivo `*.status.json`: identificação
única da execução, PID, início, última atualização, casos concluídos e estado final.
`completed` significa rodada encerrada, **não** laboratório trabalhando em segundo
plano nem etapa operacional aprovada. Ausência de atualização não comprova processo
vivo; encerramento forçado da máquina pode deixar um estado `running` antigo.

## Limites que impedem aprovação

Faltam capturas independentes do mesmo padrão cobrindo os demais valores, sobretudo
figuras, espadas e ouros, turn/river, mudanças de posição/layout e situações ambíguas.
A cobertura real atual é de cinco cartas e dois naipes. Os recortes são material de
ajuste, não conjunto independente para estimar precisão. Os limiares de forma precisam
ser confrontados com exemplos negativos de outros símbolos. Posições, valores de
aposta e fase completa da mão não estão validados por este benchmark.

O algoritmo candidato não deve autorizar ações automáticas. Não é possível concluir
100% de confiabilidade a partir deste conjunto, mesmo com todos os seus casos aprovados.

## Fechamento desta rodada

Suíte final: **278 testes executados, 275 aprovados e três ignorados**, em 121,381 s.
Oito testes específicos do baralho colorido aprovados; benchmark final 60/60.
O caminho de erro do registro automático também foi exercitado: sessão inexistente
produz saída 1 e estado `interrupted_or_error`, em vez de sucesso silencioso.
`coverage.json` registra as 47 cartas sem captura real neste conjunto e a ausência
atual de conjunto independente. Nenhuma aprovação das cinco etapas foi emitida.
