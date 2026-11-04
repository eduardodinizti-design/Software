# Relatório Consolidado do Projeto VisualPilot

---

## 1. Descrição Geral do Projeto

Projeto de automação distribuída para jogo de poker online (PPPoke), com dois computadores:

- **Coletor (PC):** captura as mesas de jogo na tela, processa imagens e transmite dados.  
- **Painel (Notebook):** recebe dados, reconhece cartas e estados, toma decisões e executa ações (automaticidade e controle manual).

Objetivo final: bot autônomo com controle manual, estável e robusto.

---

## 2. Arquitetura e Fluxo

1. Coletor captura ao vivo, segmenta janelas das mesas.  
2. Envia via rede local imagens compactadas (PNG).  
3. Painel realiza OCR, reconhece o estado dos torneios e mesas.  
4. Painel decide ações baseadas na leitura.  
5. Controle manual pode assumir a qualquer tempo.  
6. Logs, histórico e diagnósticos acompanham o processo.

---

## 3. Estado Atual Achado em Conversa

- **Módulo Lobby:** laboratorialmente implementado, capturando PNGs simulados, segmentando cartões, filtrando torneios por buy-in, tipo e status, com histórico persistente.  
- Testes: 398 testes executados, 9 cenários válidos, funcionamento comprovado no laboratório.  
- Ainda pendente calibração para o lobby real (PPPoke com DPI real e interface aberta).  
- Módulo modal de confirmação de registro esqueleto entregue com funções de captura, OCR, análise buy-in e clique em confirmar.  
- Controller básico que conecta lobby, clique em torneio, validação no detalhe e execução do registro também entregue em pseudocódigo para implementação.  
- Histórico de inscrições com persistência SQLite pronto para uso.

---

## 4. Planejamento de Fases e Módulos

### Fase 1: Calibração e interação básica

- Módulo 1: Captura da região do lobby PPPoker real (completo)  
- Módulo 2: Segmentação de cartões no PNG capturado  
- Módulo 3: OCR em cartões segmentados  
- Módulo 4: Cálculo posições para clique  
- Módulo 5: Execução do clique no torneio

### Fase 2: Registro automático no modal de confirmação

- Detectar modal, validar buy-in  
- Ajustar fichas fictícias  
- Confirmar/cancelar registro  
- Monitorar fechamento modal

### Fase 3: Integração e controle

- Controlador sequencial para registro completo  
- Controle manual e pausa/resumo  
- Comunicação Coletor-Painel otimizada

---

## 5. Método de Trabalho Conjunto

- Entrega de módulos em blocos fechados para testes isolados.  
- Uso do mini-checklist de validação padronizado para feedback.  
- Iterar ajustes com report detalhado para avançar fases.  
- Evitar dispersão e foco estrito no escopo e fases definidas.

---

## 6. Documentos Auxiliares Criados

- Template padrão para feedback e validação de módulos.  
- Exemplo de módulo para modal de confirmação com OCR e clique.  
- Exemplo de histórico com persistência SQLite.  
- Exemplo para controlador de registro sequencial.  
- Módulo para organização automática das mesas e manipulação do lobby.

---

## 7. Próximos Passos Imediatos

- Finalizar Módulo 2 da Fase 1 — segmentação de cartões no lobby real e validação.  
- Testar, revisar e validar com checklist.  
- Avançar sequencialmente modulando o fluxo.

---

# Fim do relatório consolidado
