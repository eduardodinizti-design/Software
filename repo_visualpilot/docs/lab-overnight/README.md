# Laboratório sem acompanhamento contínuo

O executor automatiza experimentos predefinidos por até 6, 7 ou 8 horas por execução. Não altera código sozinho, não registra torneios e não opera o cliente de poker. A sessão do assistente não se transforma em serviço permanente: o computador que executa o laboratório precisa permanecer ligado, acordado e com o processo aberto.

## Plano de execução

1. Executar a suíte de testes; bloquear os experimentos se falhar.
2. Percorrer 10.140 combinações candidatas: 338 mãos físicas do Hero (duas variações de naipes para cada uma das 169 classes pré-flop), seis texturas de board e cinco contextos de posições. Casos incompatíveis com as cartas ou sem frequência de chegada no recorte NVT são excluídos com motivo.
3. Para cada caso de turn, calcular a referência com todos os rivers sob o modelo sintético de adversário.
4. Comparar três sementes com 6 amostras; se necessário, repetir com 12 e depois 24. Aceitar numericamente somente se a perda de EV contra a referência não ultrapassar 0,03 BB em nenhuma semente.
5. Salvar resultados, logs e checkpoints continuamente; parar ao concluir a fila, alcançar o limite ou receber solicitação de parada.

A fila alterna mãos, posições e boards, começa com board pareado e inclui quatro cartas do mesmo naipe, monotone, flush draw, overcard e conectado. A execução é adaptativa, não uma divisão rígida de horas: os casos difíceis recebem mais processamento. Cada tarefa tem limite de 180 segundos; a suíte inicial tem limite de 600 segundos. Falhas e limites excedidos ficam registrados para revisão, sem transformar resultado incompleto em aprovação.

Este lote amplia a validação numérica do turn considerando o river. Não comprova cobertura integral de flop, OCR, botões, captura Windows ou estratégia GTO. A estratégia de resposta do adversário é sintética, não um solver de equilíbrio.

## Iniciar no computador com o projeto Python

Na pasta raiz do projeto atualizado, com o ambiente `.venv` já instalado:

- Abrir `INICIAR_LAB_6H.bat`, `INICIAR_LAB_7H.bat` ou `INICIAR_LAB_8H.bat`.
- Manter a janela aberta e impedir suspensão do computador.
- Acompanhar `sessions/overnight/RELATORIO.txt` e `state.json`.
- Para interromper, abrir `PARAR_LAB_NOTURNO.bat`.
- Para retomar, abrir novamente o iniciador. Resultados concluídos são reutilizados.

Os iniciadores precisam do projeto Python completo; copiar somente o executável da Central não é suficiente. Os arquivos BAT foram preparados, mas não executados em Windows físico nesta rodada.

No Linux, a partir da raiz do projeto:

```sh
.venv/bin/python -m visualpilot.lab.overnight --hours 6 --output sessions/overnight --resume-stopped
```

Duas execuções não podem usar a mesma pasta simultaneamente. Mudanças de código, plano, versão Python ou arquivos de configuração rastreados exigem outra pasta de resultados, por exemplo `--output sessions/overnight-v2`. Um teste inicial que falhou permanece registrado; depois de corrigir a causa, usar uma pasta nova. Não apagar checkpoints para esconder falhas.

## Evidência desta entrega

- Sete testes específicos cobrem retomada, interrupção, timeout, exclusão mútua, mudança de código e refinamento quando as sementes concordam com uma escolha errada.
- Um cenário real de smoke test concluiu referência exata e três aproximações, com regret zero sob esse modelo. A retomada reutilizou os checkpoints.
- Evidência em `evidence/smoke-state.json` e `evidence/smoke-report.txt`; suíte completa em `unified.log`.
- A entrega inicial validou somente um ciclo curto. Posteriormente foi iniciada uma rodada na nuvem e substituída pela rodada ampliada, com resultados anteriores preservados. O teste curto não valida a estabilidade de uma noite inteira.

Ao final da rodada longa, revisar os casos rejeitados, excluídos e interrompidos antes de alterar código ou ampliar a cobertura. Mais amostras melhoram a estimativa; não corrigem automaticamente as hipóteses estratégicas do modelo.

## Ampliação de mãos

A fila expandida tem 10.140 candidatos únicos e ordem determinística. A verificação de cartas e frequência de chegada pré-flop encontrou 6.805 elegíveis, 1.550 com cartas repetidas entre Hero e board e 1.785 fora do range de chegada (exclusões contadas nessa ordem). Elegibilidade não é aprovação numérica nem validação estratégica.

A seleção de 338 mãos não cobre todas as 1.326 combinações físicas do Hold’em. As 169 classes são candidatas: uma classe pode ser excluída em determinadas posições por não estar no range NVT. As variações de naipes ajudam a testar blockers e draws, mas não representam todas as configurações possíveis.

O limite de seis horas permanece. O executor não promete concluir toda a fila nesse prazo; cenários restantes ficam pendentes. A rodada ampliada usa pasta própria para não misturar checkpoints de planos diferentes. O teste adicional verifica as 169 classes, duas variações por classe, unicidade dos cenários e diversidade de boards/posições no começo da fila.
