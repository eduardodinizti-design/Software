# Critério de entrega do piloto

Contagem de testes unitários não é aprovação do produto. Testes sintéticos com
limiar 0.75 não comprovam reconhecimento no runtime real, cujo limiar é 0.90.

## Verificações automatizadas disponíveis

- Suíte de regressão de captura, cartas, transporte, scheduler e persistência.
- Reprodução da geometria incorreta 5760 × 2160 encontrada no histórico real.
- Workflow Windows: suíte, dois builds e teste HTTP da Central congelada, sem
  stdin, sem variáveis STREAMLIT e com perfil de usuário temporário.
- O build preserva as configurações existentes e exige o teste de inicialização.

O teste HTTP não comprova que o frontend renderizou nem que o OCR funcionou.
Artefatos do workflow são candidatos de laboratório, não versões homologadas.

## Portões ainda pendentes para homologação

1. Executáveis completos em duas máquinas Windows: iniciar/parar/reiniciar,
   desconexão/reconexão, persistência, atualização preservando configurações.
2. Captura em dois monitores, escalas 100/125/150%, coordenadas negativas,
   janelas movidas/redimensionadas e parcialmente cobertas, uma e seis mesas.
3. Sequências com gabarito independente: todas as 52 cartas nas posições Hero
   e board, quatro naipes, transições pré-flop/flop/turn/river/nova mão,
   cartas ilegíveis e duplicidades. Usar o limiar real sem reduzi-lo para passar.
4. Fluxo captura → TCP → ROI → OCR → scheduler → painel → registro, sem
   trocar mesas/mãos nem reexibir leituras antigas como recentes.
5. Medir latência ponta a ponta p50/p95/máxima, CPU/RAM, perdas, expirações e
   erros por campo em seis mesas. Metas precisam ser cumpridas no conjunto,
   não apenas em imagens paradas ou chamadas isoladas.

Cada falha de campo vira caso reproduzível antes de solicitar nova tentativa
ao usuário. Portão não executado deve aparecer como pendente, nunca aprovado.
