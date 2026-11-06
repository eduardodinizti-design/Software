# Execução por bloco

Com dependências instaladas e Tesseract nativo com eng disponível:

```
python tools/run_lab_batch.py --assets public/assets/aistudio
```

O comando roda os contratos primeiro e os replays de desenvolvimento em até dois processos paralelos. Não abre PPPoker, não captura desktop e não executa cliques. Timeout por tarefa: 300 segundos. Resultados e logs em `docs/table-reading/batch/regression`. O status geral só passa se todos os processos retornarem zero. Verificar o log de contratos para skips nativos do Windows; exit zero não implica homologação Windows.

Imagens transformadas e reuso do mesmo flop são regressões, não novas mãos independentes. Resultados específicos de cada frente ficam no relatório consolidado; o batch básico não substitui cobertura ampla de ranks/naipes.

Entrega padrão de cada bloco: inventário atualizado; falhas por causa; mudanças comprovadas; regressão; uma publicação GitHub; pendências Windows agrupadas. Ausência de um PNG não bloqueia trabalho independente.

The integrated runner also includes extended Hero, board, colored-eight and detector replays. Tesseract uses OMP_THREAD_LIMIT=1 to avoid lab oversubscription; this is not a Windows performance claim.
