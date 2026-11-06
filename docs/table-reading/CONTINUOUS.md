# Observador contínuo experimental

Atualize a branch fix/strict-client-capture e execute:

```
python ler_mesas.py --hwnd 264430 --continuo
```

Ctrl+C encerra. HWND é o identificador da janela atual, não permanente. Não substitui automaticamente janela inválida. Mudança de PID/início do processo encerra a sessão.

Captura, detecção e OCR são sequenciais, em memória, sem escrita de imagens, JSON ou logs pelo observador. O console mantém linhas históricas identificadas por ciclo. A leitura anterior é invalidada antes de cada captura. Não existe histórico de mãos ou identidade persistente de mesas. Até seis candidatas por superfície; nesta fase validar uma mesa.

Intervalo alvo mínimo de 2 segundos entre inícios; se OCR demorar mais, a próxima captura aguarda o término. Não há fila acumulada. Resultados com idade superior a 10 segundos são descartados. --intervalo permite ajustar o intervalo. Idade medida desde início da captura; não detecta por si só frames congelados devolvidos pelo sistema gráfico. Movimento durante OCR ou transição visual não tem confirmação temporal neste estágio.

--save não pode ser usado com --continuo, para evitar gravações automáticas. Para evidência pontual, encerre e execute a leitura única com --save.

Seis testes de contrato cobrem falhas, recuperação, identidade, expiração, interrupção e intervalo inválido. São testes com dependências simuladas, não homologação de sessão PPPoker em Windows. O leitor de cartas permanece experimental, inclusive o caso 9d/9s ainda pendente de validação nos pixels originais.
